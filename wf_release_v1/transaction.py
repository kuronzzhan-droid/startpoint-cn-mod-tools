"""One explicit local install phase machine with pre-acceptance recovery."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
import secrets

from ._loopback_http import _timeout as _validated_health_timeout, wait_health_ready
from ._receipt_contract import OperationReceipt, new_operation_id
from ._transaction_content import (
    ContentSwitch,
    apply_content_switch,
    prepare_content_switch,
    restore_content_switch,
    save_baseline_facts,
    sync_content_switch,
)
from ._transaction_modes import (
    ModeSwitch,
    apply_mode_switch,
    prepare_mode_switch,
    restore_mode_switch,
)
from .compatibility import (
    ActiveRelease,
    ActiveState,
    CompatibilityReport,
    VerifiedRelease,
    evaluate_expected_state,
    evaluate_requirements,
)
from .errors import ReleaseError
from .materialize import (
    import_verified_object,
    load_verified_release,
    materialize_candidates,
    verify_candidates,
)
from .platform import LaunchEnvironment, PlatformAdapter
from .probe import TargetFacts
from .receipts import commit_active_state, load_active_state, write_phase_receipt
from .target import ManagedTarget
from .verifier import verify_release


@dataclass(frozen=True)
class InstallResult:
    release_id: str
    operation_id: str | None
    outcome: str
    error_code: str | None
    warnings: tuple[str, ...]


def _transaction_error(code: str, message: str) -> ReleaseError:
    return ReleaseError(code, message)


def _active_state(target: ManagedTarget) -> tuple[ActiveState, bool]:
    active_path = target.state_root / "active.json"
    if active_path.exists() or active_path.is_symlink():
        return load_active_state(target.state_root), True
    previous_path = target.state_root / "previous.json"
    if previous_path.exists() or previous_path.is_symlink():
        raise _transaction_error(
            "WFREL_STATE_CONFLICT", "active state is missing beside retained previous state"
        )
    compatibility = target.compatibility
    return ActiveState(
        client_version=compatibility.client_version,
        resource_baseline=compatibility.resource_baseline,
        client_patch_profile=compatibility.client_patch_profile,
        releases=(),
        known_release_ids=(),
    ), False


def _environment(target: ManagedTarget) -> LaunchEnvironment:
    return LaunchEnvironment(
        data_root=target.data_root,
        cdn_root=target.cdn_root,
        modes_root=target.modes_root,
    )


def _gate(report: CompatibilityReport) -> None:
    if report.compatible:
        return
    code = report.codes[0] if report.codes else "WFREL_TRANSACTION_FAILED"
    raise _transaction_error(code, "release compatibility gate failed")


def _next_active(previous: ActiveState, release: VerifiedRelease) -> ActiveState:
    replacements = set(release.manifest.replaces)
    retained = [item for item in previous.releases if item.release_id not in replacements]
    retained.append(ActiveRelease(release.manifest.release_id, release.ownership))
    releases = tuple(sorted(retained, key=lambda item: item.release_id))
    known = tuple(sorted({
        *previous.known_release_ids,
        *(item.release_id for item in previous.releases),
        release.manifest.release_id,
    }))
    return ActiveState(
        previous.client_version,
        previous.resource_baseline,
        previous.client_patch_profile,
        releases,
        known,
    )


def _same_target(before: TargetFacts, recovered: TargetFacts) -> None:
    if before != recovered:
        raise _transaction_error(
            "WFREL_RECOVERY_FAILED", "recovered target facts disagree with the baseline"
        )


def _restore_components(
    content: ContentSwitch,
    mode: ModeSwitch | None,
    *,
    mode_applied: bool,
) -> None:
    failure: ReleaseError | None = None
    if mode is not None and mode_applied:
        try:
            restore_mode_switch(mode)
        except ReleaseError as error:
            failure = error
    try:
        restore_content_switch(content)
    except ReleaseError as error:
        if failure is None:
            failure = error
    if failure is not None:
        raise failure


def install_release(
    release: Path,
    target: ManagedTarget,
    platform: PlatformAdapter,
    *,
    health_timeout: float = 30.0,
) -> InstallResult:
    """Verify, switch, double-accept and commit one content-only Release."""
    if not isinstance(release, Path) or not isinstance(target, ManagedTarget):
        raise _transaction_error("WFREL_TRANSACTION_FAILED", "install input is invalid")
    health_timeout = _validated_health_timeout(health_timeout)
    report = verify_release(release)
    previous, active_exists = _active_state(target)
    initial_process = platform.current_process()
    if any(item.release_id == report.release_id for item in previous.releases):
        return InstallResult(report.release_id, None, "noop", None, ())

    started_at = datetime.now(timezone.utc)
    operation_id = new_operation_id(started_at, secrets.token_bytes(16))
    receipt = OperationReceipt(
        schema_version=2,
        operation_id=operation_id,
        release_id=report.release_id,
        phase="CREATED",
        outcome="in_progress",
        started_at=started_at,
        updated_at=started_at,
        before_release_ids=tuple(item.release_id for item in previous.releases),
        candidate_release_ids=(report.release_id,),
        error_code=None,
        recovery_outcome=None,
        target_protocol="capabilities-v1",
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
    launch = None
    environment = None
    baseline_process = initial_process
    before_facts: TargetFacts | None = None
    switch: ContentSwitch | None = None
    mode_switch: ModeSwitch | None = None
    switched = False
    mode_switched = False
    committed = False
    phase = "CREATED"

    try:
        stored = import_verified_object(release, target)
        verified = load_verified_release(stored, target)
        if verified.manifest.release_id != report.release_id:
            raise _transaction_error(
                "WFREL_OBJECT_CORRUPT", "verified release identities disagree"
            )
        phase = "VERIFIED"
        advance(phase)
        launch = target.launch_spec()
        environment = _environment(target)

        if not active_exists and initial_process is not None:
            raise _transaction_error(
                "WFREL_STATE_CONFLICT",
                "initial managed process has no active state",
            )
        if baseline_process is None:
            baseline_process = platform.start_server(launch, environment, operation_id)
            phase = "BASE_STARTED"
            advance(phase)
            wait_health_ready(target.health_url, health_timeout)

        before_facts = target.target_probe(timeout_seconds=health_timeout).run()
        phase = "PROBED"
        advance(phase)
        _gate(evaluate_requirements(verified, before_facts, previous))

        platform.stop_owned(baseline_process, health_timeout)
        baseline_process = None
        phase = "STOPPED"
        advance(phase)

        candidates = materialize_candidates(stored, target, operation_id)
        verify_candidates(candidates)
        phase = "MATERIALIZED"
        advance(phase)

        switch = prepare_content_switch(candidates, target, operation_id)
        if candidates.modes_root is not None:
            mode_switch = prepare_mode_switch(candidates, target, operation_id)
        save_baseline_facts(switch, before_facts)
        apply_content_switch(switch)
        switched = True
        if mode_switch is not None:
            apply_mode_switch(mode_switch)
            mode_switched = True
        sync_content_switch(switch)
        phase = "SWITCHED"
        advance(phase)

        platform.prepare_content(launch, environment)
        platform.start_server(launch, environment, operation_id)
        phase = "STARTED"
        advance(phase)
        wait_health_ready(target.health_url, health_timeout)
        phase = "HEALTH_READY"
        advance(phase)
        accepted = target.target_probe(timeout_seconds=health_timeout).run()
        _gate(evaluate_expected_state(verified, accepted))
        phase = "CAPABILITIES_ACCEPTED"
        advance(phase)

        active = _next_active(previous, verified)
        commit_active_state(target.state_root, previous=previous, active=active)
        committed = True
        try:
            advance("COMMITTED", outcome="succeeded")
        except ReleaseError as warning:
            return InstallResult(
                report.release_id,
                operation_id,
                "succeeded",
                None,
                (warning.code,),
            )
        return InstallResult(report.release_id, operation_id, "succeeded", None, ())
    except ReleaseError as error:
        if committed:
            return InstallResult(
                report.release_id, operation_id, "succeeded", None, (error.code,)
            )

        if (
            switched
            and switch is not None
            and before_facts is not None
            and launch is not None
            and environment is not None
        ):
            try:
                current = platform.current_process()
                if current is not None:
                    platform.stop_owned(current, health_timeout)
                _restore_components(
                    switch,
                    mode_switch,
                    mode_applied=mode_switched,
                )
                recovered_process = platform.start_server(launch, environment, operation_id)
                wait_health_ready(target.health_url, health_timeout)
                recovered = target.target_probe(timeout_seconds=health_timeout).run()
                _same_target(before_facts, recovered)
                if platform.current_process() != recovered_process:
                    raise _transaction_error(
                        "WFREL_RECOVERY_FAILED", "recovered process identity changed"
                    )
                advance(
                    phase,
                    outcome="recovered",
                    error_code=error.code,
                    recovery_outcome="recovered",
                )
                return InstallResult(
                    report.release_id, operation_id, "recovered", error.code, ()
                )
            except ReleaseError:
                try:
                    current = platform.current_process()
                    if current is not None:
                        platform.stop_owned(current, health_timeout)
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

        try:
            current = platform.current_process()
            if initial_process is None:
                if current is not None:
                    platform.stop_owned(current, health_timeout)
            elif (
                current is None
                and before_facts is not None
                and launch is not None
                and environment is not None
            ):
                recovered_process = platform.start_server(launch, environment, operation_id)
                wait_health_ready(target.health_url, health_timeout)
                _same_target(
                    before_facts,
                    target.target_probe(timeout_seconds=health_timeout).run(),
                )
                if platform.current_process() != recovered_process:
                    raise _transaction_error(
                        "WFREL_RECOVERY_FAILED", "baseline process identity changed"
                    )
            advance(phase, outcome="failed", error_code=error.code)
            return InstallResult(report.release_id, operation_id, "failed", error.code, ())
        except ReleaseError:
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


__all__ = ["InstallResult", "install_release"]
