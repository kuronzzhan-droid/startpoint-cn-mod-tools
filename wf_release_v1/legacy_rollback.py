"""Explicit rollback of one committed transition legacy CDN release."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import secrets

from ._legacy_files import LegacyFileSwitch, finalize_legacy_switch
from ._legacy_rollback_files import (
    prepare_legacy_removal,
    remove_legacy_archives,
    restore_removed_archives,
)
from ._loopback_http import _timeout as _validated_timeout
from ._receipt_contract import OperationReceipt, new_operation_id
from .compatibility import ActiveState
from .errors import ReleaseError
from .legacy_readiness import wait_legacy_ready
from .legacy_target import LegacyProcessStatus, LegacyTargetFacts, inspect_legacy_target
from .platform import LaunchEnvironment, PlatformAdapter
from .receipts import (
    commit_active_state,
    list_operation_receipts,
    load_active_state,
    load_previous_state,
    operation_reservation,
    write_phase_receipt,
)
from .rollback import RollbackResult
from .target import ManagedTarget
from .verifier import verify_release_contract
from .verifier_overlay import VerifiedOverlayChain


def _error(code: str, message: str) -> ReleaseError:
    return ReleaseError(code, message)


def _ids(state: ActiveState) -> tuple[str, ...]:
    return tuple(item.release_id for item in state.releases)


def _environment(target: ManagedTarget) -> LaunchEnvironment:
    return LaunchEnvironment(
        target.data_root,
        target.cdn_root,
        target.modes_root,
        listen_host=target.http_bind_host,
        listen_port=target.server_port,
        public_host=target.public_host,
        session_host=target.session_bind_host,
        session_port=target.session_port,
        session_public_host=target.session_public_host,
    )


def _install_receipt(
    target: ManagedTarget,
    current: ActiveState,
    previous: ActiveState,
) -> OperationReceipt:
    before = _ids(previous)
    added = set(_ids(current)) - set(before)
    matches = tuple(
        receipt
        for receipt in list_operation_receipts(target.state_root)
        if receipt.phase == "COMMITTED"
        and receipt.outcome == "succeeded"
        and receipt.before_release_ids == before
        and receipt.release_id in added
    )
    if len(matches) != 1:
        raise _error("WFREL_STATE_CONFLICT", "legacy install receipt is ambiguous")
    receipt = matches[0]
    if receipt.target_protocol != "legacy":
        raise _error("WFREL_TARGET_PROTOCOL", "legacy rollback requires a legacy receipt")
    return receipt


def _same(before: LegacyTargetFacts, recovered: LegacyTargetFacts) -> None:
    if before != recovered:
        raise _error("WFREL_RECOVERY_FAILED", "legacy rollback recovery facts disagree")


def rollback_legacy_to_previous(
    target: ManagedTarget,
    platform: PlatformAdapter,
    to_release_id: str,
    *,
    health_timeout: float = 30.0,
) -> RollbackResult:
    """Remove only the latest legacy Release and restore retained previous state."""
    timeout = _validated_timeout(health_timeout)
    if not isinstance(target, ManagedTarget) or not isinstance(to_release_id, str):
        raise _error("WFREL_STATE_CONFLICT", "legacy rollback target is invalid")
    started_at = datetime.now(timezone.utc)
    operation_id = new_operation_id(started_at, secrets.token_bytes(16))
    with operation_reservation(target.state_root, operation_id):
        return _rollback_legacy_to_previous_reserved(
            target,
            platform,
            to_release_id,
            timeout=timeout,
            operation_id=operation_id,
            started_at=started_at,
        )


def _rollback_legacy_to_previous_reserved(
    target: ManagedTarget,
    platform: PlatformAdapter,
    to_release_id: str,
    *,
    timeout: float,
    operation_id: str,
    started_at: datetime,
) -> RollbackResult:
    current = load_active_state(target.state_root)
    previous = load_previous_state(target.state_root)
    if to_release_id not in _ids(previous) or current == previous:
        raise _error("WFREL_STATE_CONFLICT", "requested release is not the previous state")
    install = _install_receipt(target, current, previous)
    archive = (
        target.state_root / "objects" / install.release_id.replace(":", "-", 1)
        / "release.wf-release.zip"
    )
    report, verified = verify_release_contract(archive)
    overlay = verified.overlay
    if (
        report.release_id != install.release_id
        or verified.manifest.release_id != install.release_id
        or not isinstance(overlay, VerifiedOverlayChain)
    ):
        raise _error("WFREL_STATE_CONFLICT", "legacy rollback object disagrees")
    initial = platform.current_process()
    before = inspect_legacy_target(target, platform)
    if platform.current_process() != initial:
        raise _error("WFREL_PROCESS_IDENTITY", "managed process changed during rollback plan")
    if initial is None or before.process_status is not LegacyProcessStatus.OWNED_RUNNING:
        raise _error(
            "WFREL_LEGACY_PROCESS_NOT_OWNED",
            "legacy rollback requires one owned running process",
        )
    if before.chain_tail != overlay.target_version:
        raise _error("WFREL_LEGACY_CDN_CONFLICT", "legacy rollback chain tail changed")

    launch = target.launch_spec()
    environment = _environment(target)
    receipt = OperationReceipt(
        2, operation_id, install.release_id, "CREATED", "in_progress",
        started_at, started_at,
        _ids(current), _ids(previous), None, None, "legacy",
    )

    def advance(
        phase: str,
        *,
        outcome: str = "in_progress",
        error_code: str | None = None,
        recovery_outcome: str | None = None,
    ) -> None:
        nonlocal receipt
        receipt = replace(
            receipt,
            phase=phase,
            outcome=outcome,
            updated_at=datetime.now(timezone.utc),
            error_code=error_code,
            recovery_outcome=recovery_outcome,
        )
        write_phase_receipt(target.state_root, receipt)

    write_phase_receipt(target.state_root, receipt)
    advance("VERIFIED")
    switch: LegacyFileSwitch | None = None
    stop_completed = False
    removal_started = False
    committed = False
    phase = "VERIFIED"
    try:
        platform.stop_owned(initial, timeout)
        stop_completed = True
        phase = "STOPPED"
        advance(phase)
        switch = prepare_legacy_removal(
            verified,
            target.component_roots.content,
            target.state_root,
            target.cdn_root,
            operation_id,
        )
        phase = "MATERIALIZED"
        advance(phase)
        removal_started = True
        remove_legacy_archives(switch)
        phase = "SWITCHED"
        advance(phase)
        started = platform.start_server(launch, environment, operation_id)
        phase = "STARTED"
        advance(phase)
        wait_legacy_ready(target.server_url, timeout)
        phase = "HEALTH_READY"
        advance(phase)
        accepted = inspect_legacy_target(target, platform)
        if accepted.chain_tail != overlay.from_version or platform.current_process() != started:
            raise _error("WFREL_LEGACY_CDN_READBACK", "legacy rollback readback disagrees")
        phase = "CAPABILITIES_ACCEPTED"
        advance(phase)
        rolled = ActiveState(
            previous.client_version,
            previous.resource_baseline,
            previous.client_patch_profile,
            previous.releases,
            tuple(sorted({*previous.known_release_ids, *current.known_release_ids, *_ids(current)})),
        )
        commit_active_state(target.state_root, previous=current, active=rolled)
        committed = True
        advance("COMMITTED", outcome="succeeded")
        try:
            finalize_legacy_switch(switch)
        except ReleaseError as warning:
            return RollbackResult(operation_id, "succeeded", to_release_id, warning.code, False)
        return RollbackResult(operation_id, "succeeded", to_release_id, None, False)
    except ReleaseError as failure:
        if committed:
            return RollbackResult(operation_id, "succeeded", to_release_id, failure.code, False)
        if not stop_completed:
            advance(phase, outcome="failed", error_code=failure.code)
            return RollbackResult(operation_id, "failed", to_release_id, failure.code, False)
        try:
            running = platform.current_process()
            if running is not None:
                platform.stop_owned(running, timeout)
            if switch is not None and removal_started:
                restore_removed_archives(switch)
            recovered = platform.start_server(launch, environment, operation_id)
            wait_legacy_ready(target.server_url, timeout)
            _same(before, inspect_legacy_target(target, platform))
            if platform.current_process() != recovered:
                raise _error("WFREL_RECOVERY_FAILED", "recovered process identity changed")
            if switch is not None:
                finalize_legacy_switch(switch)
            advance(
                phase,
                outcome="recovered",
                error_code=failure.code,
                recovery_outcome="recovered",
            )
            return RollbackResult(operation_id, "recovered", to_release_id, failure.code, False)
        except ReleaseError:
            try:
                running = platform.current_process()
                if running is not None:
                    platform.stop_owned(running, timeout)
            except ReleaseError:
                pass
            try:
                advance(
                    phase,
                    outcome="recovery_failed",
                    error_code="WFREL_RECOVERY_FAILED",
                    recovery_outcome="failed",
                )
            except ReleaseError:
                pass
            return RollbackResult(
                operation_id, "recovery_failed", to_release_id,
                "WFREL_RECOVERY_FAILED", False,
            )


__all__ = ["rollback_legacy_to_previous"]
