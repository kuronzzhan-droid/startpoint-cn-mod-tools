"""Private CLI handlers for one host-local managed target."""

from __future__ import annotations

import argparse
from pathlib import Path

from .errors import ReleaseError
from .bootstrap import BootstrapResult, bootstrap_target
from ._target_facts import target_facts_to_wire
from .legacy_transaction import install_legacy_release
from .legacy_rollback import rollback_legacy_to_previous
from .platform import WindowsPlatformAdapter
from .rollback import (
    RollbackResult,
    recover_failed_operation,
    rollback_to_previous,
)
from .resume import resume_target
from .target import ManagedTarget
from .target_capability import inspect_target_capability
from .target_planning import plan_target_install
from .transaction import InstallResult, install_release


def _result_wire(result: InstallResult) -> dict[str, object]:
    return {
        "errorCode": result.error_code,
        "operationId": result.operation_id,
        "outcome": result.outcome,
        "releaseId": result.release_id,
        "warnings": list(result.warnings),
    }


def _bootstrap_wire(result: BootstrapResult) -> dict[str, object]:
    return {
        **target_facts_to_wire(result.target_facts),
        "outcome": result.outcome,
        "targetProtocol": "capabilities-v1",
    }


def _rollback_wire(result: RollbackResult) -> dict[str, object]:
    return {
        "dataCompatibilityGuaranteed": result.data_compatibility_guaranteed,
        "errorCode": result.error_code,
        "operationId": result.operation_id,
        "outcome": result.outcome,
        "toReleaseId": result.to_release_id,
    }


def _platform(target: ManagedTarget) -> WindowsPlatformAdapter:
    launch = target.launch_spec()
    return WindowsPlatformAdapter(target.state_root, launch.executable)


def _legacy_not_committed(result: InstallResult | RollbackResult, action: str) -> ReleaseError:
    details = {"operationErrorCode": result.error_code} if result.error_code else None
    return ReleaseError(
        "WFREL_TRANSACTION_NOT_COMMITTED",
        f"legacy {action} did not commit",
        details,
    )


def run_probe(arguments: argparse.Namespace) -> dict[str, object]:
    target = ManagedTarget.load(Path(arguments.target))
    return inspect_target_capability(target, lambda: _platform(target)).to_wire()


def run_bootstrap(arguments: argparse.Namespace) -> dict[str, object]:
    target = ManagedTarget.load(Path(arguments.target))
    platform = _platform(target)
    return _bootstrap_wire(bootstrap_target(target, platform))


def run_resume(arguments: argparse.Namespace) -> dict[str, object]:
    target = ManagedTarget.load(Path(arguments.target))
    return resume_target(target, _platform(target)).to_wire()


def run_plan(arguments: argparse.Namespace) -> dict[str, object]:
    target = ManagedTarget.load(Path(arguments.target))
    return plan_target_install(
        Path(arguments.release), target, lambda: _platform(target)
    ).to_wire()


def run_install(arguments: argparse.Namespace) -> dict[str, object]:
    target = ManagedTarget.load(Path(arguments.target))
    platform = _platform(target)
    result = install_release(
        Path(arguments.release), target, platform, enforce_target_protocol=True
    )
    if result.outcome in {"recovered", "recovery_failed"}:
        raise ReleaseError(
            result.error_code or "WFREL_RECOVERY_FAILED",
            "install did not commit and recovery handling was required",
        )
    if result.outcome == "failed":
        raise ReleaseError(
            result.error_code or "WFREL_TRANSACTION_FAILED",
            "install failed before commit",
        )
    return _result_wire(result)


def run_legacy_install(arguments: argparse.Namespace) -> dict[str, object]:
    target = ManagedTarget.load(Path(arguments.target))
    platform = _platform(target)
    result = install_legacy_release(
        Path(arguments.release), target, platform, enforce_target_protocol=True
    )
    if result.outcome in {"recovered", "recovery_failed"}:
        raise _legacy_not_committed(result, "install")
    if result.outcome == "failed":
        raise ReleaseError(
            result.error_code or "WFREL_TRANSACTION_FAILED",
            "legacy install failed before commit",
        )
    return _result_wire(result)


def run_legacy_rollback(arguments: argparse.Namespace) -> dict[str, object]:
    target = ManagedTarget.load(Path(arguments.target))
    platform = _platform(target)
    result = rollback_legacy_to_previous(
        target, platform, arguments.to_release
    )
    if result.outcome in {"recovered", "recovery_failed", "failed"}:
        raise _legacy_not_committed(result, "rollback")
    return _rollback_wire(result)


def run_rollback(arguments: argparse.Namespace) -> dict[str, object]:
    operation_id = arguments.operation
    to_release_id = arguments.to_release
    expected_confirmation = (
        "RECOVER_FAILED_INSTALL"
        if operation_id is not None
        else "I_UNDERSTAND_DATA_DOWNGRADE_RISK"
    )
    if arguments.confirm != expected_confirmation:
        raise ReleaseError("WFREL_CLI_ARGUMENTS", "rollback confirmation is invalid")
    target = ManagedTarget.load(Path(arguments.target))
    launch = target.launch_spec()
    platform = WindowsPlatformAdapter(target.state_root, launch.executable)
    result = (
        recover_failed_operation(target, platform, operation_id)
        if operation_id is not None
        else rollback_to_previous(target, platform, to_release_id)
    )
    if result.outcome == "recovery_failed":
        raise ReleaseError(
            result.error_code or "WFREL_RECOVERY_FAILED",
            "manual recovery did not restore an accepted target",
        )
    return _rollback_wire(result)


__all__ = [
    "run_bootstrap", "run_install", "run_legacy_install", "run_legacy_rollback", "run_plan",
    "run_probe", "run_resume", "run_rollback",
]
