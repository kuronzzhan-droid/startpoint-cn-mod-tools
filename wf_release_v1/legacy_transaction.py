"""One explicit legacy CDN transition with exact pre-acceptance recovery."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import secrets

from ._legacy_files import (
    LegacyFileSwitch,
    _link_archive,
    finalize_legacy_switch,
    prepare_legacy_switch,
    restore_legacy_switch,
    verify_legacy_switch,
)
from ._loopback_http import _timeout as _validated_timeout
from ._receipt_contract import OperationReceipt, new_operation_id
from .compatibility import ActiveState
from .errors import ReleaseError
from .legacy_compatibility import LegacyInstallPlan, plan_legacy_install
from .legacy_readiness import wait_legacy_ready
from .legacy_target import LegacyTargetFacts, inspect_legacy_target
from .materialize import (
    import_verified_object,
    materialize_candidates,
    verify_candidates,
)
from .platform import LaunchEnvironment, PlatformAdapter
from .receipts import commit_active_state, operation_reservation, write_phase_receipt
from .target import ManagedTarget
from .target_capability import inspect_target_capability
from .transaction import InstallResult, _active_state, _next_active
from .verifier import verify_release_contract


def _error(code: str, message: str) -> ReleaseError:
    return ReleaseError(code, message)


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


def _same_legacy_target(before: LegacyTargetFacts, recovered: LegacyTargetFacts) -> None:
    if before != recovered:
        raise _error(
            "WFREL_RECOVERY_FAILED",
            "recovered legacy target facts disagree with the baseline",
        )


def _gate(plan: LegacyInstallPlan) -> None:
    if plan.installable:
        return
    code = plan.codes[0] if plan.codes else "WFREL_LEGACY_PLAN_INVALID"
    raise _error(code, "legacy install compatibility gate failed")


def apply_legacy_switch(switch: LegacyFileSwitch) -> None:
    """Link each staged archive without clobbering any existing CDN edge."""
    if not isinstance(switch, LegacyFileSwitch):
        raise _error("WFREL_LEGACY_CDN_IO", "legacy switch is invalid")
    for item, parent_identity in zip(
        switch.archives, switch.target_parent_identities, strict=True
    ):
        _link_archive(item, parent_identity)
    verify_legacy_switch(switch)


def install_legacy_release(
    release: Path,
    target: ManagedTarget,
    platform: PlatformAdapter,
    *,
    health_timeout: float = 30.0,
    enforce_target_protocol: bool = False,
) -> InstallResult:
    """Install one verified content-only Release into a transition legacy target."""
    if not isinstance(release, Path) or not isinstance(target, ManagedTarget):
        raise _error("WFREL_LEGACY_PLAN_INVALID", "legacy install input is invalid")
    if type(enforce_target_protocol) is not bool:
        raise _error("WFREL_LEGACY_PLAN_INVALID", "protocol gate is invalid")
    timeout = _validated_timeout(health_timeout)
    started_at = datetime.now(timezone.utc)
    operation_id = new_operation_id(started_at, secrets.token_bytes(16))
    with operation_reservation(target.state_root, operation_id):
        if enforce_target_protocol:
            capability = inspect_target_capability(target, platform)
            if capability.level != "transition":
                raise _error(
                    "WFREL_TARGET_PROTOCOL",
                    "legacy automatic install requires a transition target",
                )
        return _install_legacy_release_reserved(
            release,
            target,
            platform,
            timeout=timeout,
            operation_id=operation_id,
            started_at=started_at,
        )


def _install_legacy_release_reserved(
    release: Path,
    target: ManagedTarget,
    platform: PlatformAdapter,
    *,
    timeout: float,
    operation_id: str,
    started_at: datetime,
) -> InstallResult:
    report, verified = verify_release_contract(release)
    previous, _active_exists = _active_state(target)

    initial_process = platform.current_process()
    before = inspect_legacy_target(target, platform)
    if platform.current_process() != initial_process:
        raise _error("WFREL_PROCESS_IDENTITY", "managed process changed during planning")
    plan = plan_legacy_install(verified, before, previous)
    if plan.no_op:
        return InstallResult(report.release_id, None, "noop", None, ())
    _gate(plan)
    if initial_process is None:
        raise _error(
            "WFREL_LEGACY_PROCESS_NOT_OWNED",
            "legacy automatic install requires one owned running process",
        )
    launch = target.launch_spec()
    environment = _environment(target)

    receipt = OperationReceipt(
        2,
        operation_id,
        report.release_id,
        "CREATED",
        "in_progress",
        started_at,
        started_at,
        tuple(item.release_id for item in previous.releases),
        (report.release_id,),
        None,
        None,
        "legacy",
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
    apply_started = False
    committed = False
    phase = "VERIFIED"

    try:
        platform.stop_owned(initial_process, timeout)
        stop_completed = True
        phase = "STOPPED"
        advance(phase)

        stored = import_verified_object(release, target)
        candidates = materialize_candidates(stored, target, operation_id)
        verify_candidates(candidates)
        switch = prepare_legacy_switch(
            candidates,
            plan,
            target.state_root,
            target.cdn_root,
            operation_id,
        )
        phase = "MATERIALIZED"
        advance(phase)

        apply_started = True
        apply_legacy_switch(switch)
        phase = "SWITCHED"
        advance(phase)

        started = platform.start_server(launch, environment, operation_id)
        phase = "STARTED"
        advance(phase)
        wait_legacy_ready(target.server_url, timeout)
        phase = "HEALTH_READY"
        advance(phase)
        accepted = inspect_legacy_target(target, platform)
        if accepted.chain_tail != plan.target_version:
            raise _error(
                "WFREL_LEGACY_CDN_READBACK",
                "legacy CDN chain tail disagrees after restart",
            )
        verify_legacy_switch(switch)
        if platform.current_process() != started:
            raise _error("WFREL_PROCESS_IDENTITY", "restarted process identity changed")
        phase = "CAPABILITIES_ACCEPTED"
        advance(phase)

        active = _next_active(previous, verified)
        commit_active_state(target.state_root, previous=previous, active=active)
        committed = True
        advance("COMMITTED", outcome="succeeded")
        try:
            finalize_legacy_switch(switch)
        except ReleaseError as warning:
            return InstallResult(
                report.release_id,
                operation_id,
                "succeeded",
                None,
                (warning.code,),
            )
        return InstallResult(report.release_id, operation_id, "succeeded", None, ())
    except ReleaseError as failure:
        if committed:
            warnings = [failure.code]
            if switch is not None:
                try:
                    finalize_legacy_switch(switch)
                except ReleaseError as warning:
                    warnings.append(warning.code)
            return InstallResult(
                report.release_id,
                operation_id,
                "succeeded",
                None,
                tuple(dict.fromkeys(warnings)),
            )
        try:
            current = platform.current_process()
            if current is not None:
                platform.stop_owned(current, timeout)
            if switch is not None and apply_started:
                restore_legacy_switch(switch)
            recovered = platform.start_server(launch, environment, operation_id)
            wait_legacy_ready(target.server_url, timeout)
            recovered_facts = inspect_legacy_target(target, platform)
            _same_legacy_target(before, recovered_facts)
            if platform.current_process() != recovered:
                raise _error(
                    "WFREL_RECOVERY_FAILED", "recovered process identity changed"
                )
            if switch is not None:
                finalize_legacy_switch(switch)
            advance(
                phase,
                outcome="recovered" if stop_completed else "failed",
                error_code=failure.code,
                recovery_outcome="recovered" if stop_completed else None,
            )
            return InstallResult(
                report.release_id,
                operation_id,
                "recovered" if stop_completed else "failed",
                failure.code,
                (),
            )
        except ReleaseError:
            try:
                current = platform.current_process()
                if current is not None:
                    platform.stop_owned(current, timeout)
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
            return InstallResult(
                report.release_id,
                operation_id,
                "recovery_failed",
                "WFREL_RECOVERY_FAILED",
                (),
            )


__all__ = ["apply_legacy_switch", "install_legacy_release"]
