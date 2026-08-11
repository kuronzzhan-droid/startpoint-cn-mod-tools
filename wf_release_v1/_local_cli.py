"""Private CLI handlers for one host-local managed target."""

from __future__ import annotations

import argparse
from pathlib import Path

from .errors import ReleaseError
from .platform import WindowsPlatformAdapter
from .probe import TargetFacts
from .target import ManagedTarget
from .transaction import InstallResult, install_release


def _facts_wire(facts: TargetFacts) -> dict[str, object]:
    return {
        "arch": facts.arch,
        "bundleId": facts.bundle_id,
        "capabilities": list(facts.capabilities),
        "cdnTargetVersion": facts.cdn_target_version,
        "contentDigest": facts.content_digest,
        "dependencyLock": facts.dependency_lock,
        "modeDigest": facts.mode_digest,
        "nodeAbi": facts.node_abi,
        "nodeVersion": facts.node_version,
        "patchOverlaySchema": facts.patch_overlay_schema,
        "platform": facts.platform,
        "runtimeApi": facts.runtime_api,
        "runtimeId": facts.runtime_id,
        "serverVersion": facts.server_version,
    }


def _result_wire(result: InstallResult) -> dict[str, object]:
    return {
        "errorCode": result.error_code,
        "operationId": result.operation_id,
        "outcome": result.outcome,
        "releaseId": result.release_id,
        "warnings": list(result.warnings),
    }


def run_probe(arguments: argparse.Namespace) -> dict[str, object]:
    target = ManagedTarget.load(Path(arguments.target))
    return _facts_wire(target.target_probe().run())


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


__all__ = ["run_install", "run_probe"]
