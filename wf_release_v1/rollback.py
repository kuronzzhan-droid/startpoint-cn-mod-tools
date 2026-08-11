"""Explicit manual retry and previous-state rollback operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import secrets

from ._loopback_http import _timeout as _validated_timeout, wait_health_ready
from ._receipt_contract import OperationReceipt, new_operation_id
from ._transaction_content import (
    load_baseline_facts,
    load_content_switch,
    restore_content_switch,
)
from .compatibility import ActiveState
from .errors import ReleaseError
from .platform import LaunchEnvironment, PlatformAdapter
from .receipts import (
    commit_active_state,
    list_operation_receipts,
    load_active_state,
    load_operation_receipt,
    load_previous_state,
    write_phase_receipt,
)
from .target import ManagedTarget


@dataclass(frozen=True)
class RollbackResult:
    operation_id: str
    outcome: str
    to_release_id: str
    error_code: str | None
    data_compatibility_guaranteed: bool


def _error(code: str, message: str) -> ReleaseError:
    return ReleaseError(code, message)


def _release_ids(state: ActiveState) -> tuple[str, ...]:
    return tuple(item.release_id for item in state.releases)


def _environment(target: ManagedTarget) -> LaunchEnvironment:
    return LaunchEnvironment(target.data_root, target.cdn_root, target.modes_root)


def _stopped(platform: PlatformAdapter) -> None:
    if platform.current_process() is not None:
        raise _error("WFREL_PROCESS_RUNNING", "manual recovery requires a stopped target")


def _final_receipt(
    target: ManagedTarget,
    *,
    operation_id: str,
    release_id: str,
    phase: str,
    outcome: str,
    before_release_ids: tuple[str, ...],
    candidate_release_ids: tuple[str, ...],
    error_code: str | None,
    recovery_outcome: str | None,
) -> None:
    now = datetime.now(timezone.utc)
    write_phase_receipt(target.state_root, OperationReceipt(
        1,
        operation_id,
        release_id,
        phase,
        outcome,
        now,
        now,
        before_release_ids,
        candidate_release_ids,
        error_code,
        recovery_outcome,
    ))


def _recover_runtime(
    target: ManagedTarget,
    platform: PlatformAdapter,
    *,
    source_operation_id: str,
    release_id: str,
    runtime_operation_id: str,
    health_timeout: float,
) -> None:
    switch = load_content_switch(target, source_operation_id, release_id)
    baseline = load_baseline_facts(switch)
    restore_content_switch(switch)
    launch = target.launch_spec()
    process = platform.start_server(launch, _environment(target), runtime_operation_id)
    wait_health_ready(target.health_url, health_timeout)
    recovered = target.target_probe(timeout_seconds=health_timeout).run()
    if recovered != baseline or platform.current_process() != process:
        raise _error("WFREL_RECOVERY_FAILED", "recovered target disagrees with its witness")


def _stop_after_failure(platform: PlatformAdapter, timeout: float) -> None:
    try:
        process = platform.current_process()
        if process is not None:
            platform.stop_owned(process, timeout)
    except ReleaseError:
        pass


def recover_failed_operation(
    target: ManagedTarget,
    platform: PlatformAdapter,
    operation_id: str,
    *,
    health_timeout: float = 30.0,
) -> RollbackResult:
    """Retry one retained recovery_failed operation without mutating active state."""
    timeout = _validated_timeout(health_timeout)
    if not isinstance(target, ManagedTarget):
        raise _error("WFREL_STATE_CONFLICT", "managed target is invalid")
    original = load_operation_receipt(target.state_root, operation_id)
    if original.outcome != "recovery_failed" or original.recovery_outcome != "failed":
        raise _error("WFREL_STATE_CONFLICT", "operation is not recoverable")
    active = load_active_state(target.state_root)
    _stopped(platform)
    recovery_id = new_operation_id(datetime.now(timezone.utc), secrets.token_bytes(16))
    try:
        _recover_runtime(
            target,
            platform,
            source_operation_id=operation_id,
            release_id=original.release_id,
            runtime_operation_id=recovery_id,
            health_timeout=timeout,
        )
        _final_receipt(
            target,
            operation_id=recovery_id,
            release_id=original.release_id,
            phase=original.phase,
            outcome="recovered",
            before_release_ids=_release_ids(active),
            candidate_release_ids=original.candidate_release_ids,
            error_code=None,
            recovery_outcome="recovered",
        )
        return RollbackResult(
            recovery_id, "recovered", original.release_id, None, False
        )
    except ReleaseError:
        _stop_after_failure(platform, timeout)
        try:
            _final_receipt(
                target,
                operation_id=recovery_id,
                release_id=original.release_id,
                phase=original.phase,
                outcome="recovery_failed",
                before_release_ids=_release_ids(active),
                candidate_release_ids=original.candidate_release_ids,
                error_code="WFREL_RECOVERY_FAILED",
                recovery_outcome="failed",
            )
        except ReleaseError:
            pass
        return RollbackResult(
            recovery_id,
            "recovery_failed",
            original.release_id,
            "WFREL_RECOVERY_FAILED",
            False,
        )


def _install_receipt_for_previous(
    target: ManagedTarget,
    current: ActiveState,
    previous: ActiveState,
):
    before = _release_ids(previous)
    added = set(_release_ids(current)) - set(before)
    matches = tuple(
        receipt
        for receipt in list_operation_receipts(target.state_root)
        if receipt.phase == "COMMITTED"
        and receipt.outcome == "succeeded"
        and receipt.before_release_ids == before
        and receipt.release_id in added
    )
    if len(matches) != 1:
        raise _error("WFREL_STATE_CONFLICT", "previous install receipt is ambiguous")
    return matches[0]


def rollback_to_previous(
    target: ManagedTarget,
    platform: PlatformAdapter,
    to_release_id: str,
    *,
    health_timeout: float = 30.0,
) -> RollbackResult:
    """Rollback only to the retained previous release set, never an inferred state."""
    timeout = _validated_timeout(health_timeout)
    if not isinstance(target, ManagedTarget) or not isinstance(to_release_id, str):
        raise _error("WFREL_STATE_CONFLICT", "rollback target is invalid")
    current = load_active_state(target.state_root)
    previous = load_previous_state(target.state_root)
    if to_release_id not in _release_ids(previous) or current == previous:
        raise _error("WFREL_STATE_CONFLICT", "requested release is not the previous state")
    install = _install_receipt_for_previous(target, current, previous)
    _stopped(platform)
    rollback_id = new_operation_id(datetime.now(timezone.utc), secrets.token_bytes(16))
    try:
        _recover_runtime(
            target,
            platform,
            source_operation_id=install.operation_id,
            release_id=install.release_id,
            runtime_operation_id=rollback_id,
            health_timeout=timeout,
        )
        rolled = ActiveState(
            previous.client_version,
            previous.resource_baseline,
            previous.client_patch_profile,
            previous.releases,
            tuple(sorted({
                *previous.known_release_ids,
                *current.known_release_ids,
                *_release_ids(current),
            })),
        )
        commit_active_state(target.state_root, previous=current, active=rolled)
        try:
            _final_receipt(
                target,
                operation_id=rollback_id,
                release_id=to_release_id,
                phase="COMMITTED",
                outcome="succeeded",
                before_release_ids=_release_ids(current),
                candidate_release_ids=_release_ids(rolled),
                error_code=None,
                recovery_outcome=None,
            )
        except ReleaseError as warning:
            return RollbackResult(
                rollback_id, "succeeded", to_release_id, warning.code, False
            )
        return RollbackResult(rollback_id, "succeeded", to_release_id, None, False)
    except ReleaseError:
        _stop_after_failure(platform, timeout)
        try:
            _final_receipt(
                target,
                operation_id=rollback_id,
                release_id=to_release_id,
                phase="SWITCHED",
                outcome="recovery_failed",
                before_release_ids=_release_ids(current),
                candidate_release_ids=_release_ids(previous),
                error_code="WFREL_RECOVERY_FAILED",
                recovery_outcome="failed",
            )
        except ReleaseError:
            pass
        return RollbackResult(
            rollback_id,
            "recovery_failed",
            to_release_id,
            "WFREL_RECOVERY_FAILED",
            False,
        )


__all__ = [
    "RollbackResult", "recover_failed_operation", "rollback_to_previous",
]
