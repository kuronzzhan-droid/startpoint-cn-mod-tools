"""Private CLI handlers for one host-local managed target."""

from __future__ import annotations

import argparse
from pathlib import Path

from .errors import ReleaseError
from .platform import WindowsPlatformAdapter
from .rollback import (
    RollbackResult,
    recover_failed_operation,
    rollback_to_previous,
)
from ._target_facts import target_facts_to_wire
from .target import ManagedTarget
from .transaction import InstallResult, install_release


def _result_wire(result: InstallResult) -> dict[str, object]:
    return {
        "errorCode": result.error_code,
        "operationId": result.operation_id,
        "outcome": result.outcome,
        "releaseId": result.release_id,
        "warnings": list(result.warnings),
    }


def _rollback_wire(result: RollbackResult) -> dict[str, object]:
    return {
        "dataCompatibilityGuaranteed": result.data_compatibility_guaranteed,
        "errorCode": result.error_code,
        "operationId": result.operation_id,
        "outcome": result.outcome,
        "toReleaseId": result.to_release_id,
    }


def run_probe(arguments: argparse.Namespace) -> dict[str, object]:
    target = ManagedTarget.load(Path(arguments.target))
    return target_facts_to_wire(target.target_probe().run())


def run_install(arguments: argparse.Namespace) -> dict[str, object]:
    target = ManagedTarget.load(Path(arguments.target))
    launch = target.launch_spec()
    platform = WindowsPlatformAdapter(target.state_root, launch.executable)
    result = install_release(Path(arguments.release), target, platform)
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


__all__ = ["run_install", "run_probe", "run_rollback"]
