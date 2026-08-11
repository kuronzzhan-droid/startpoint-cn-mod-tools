"""Stopped-service atomic Mode root switch with retained recovery state."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
from typing import Final

from ._receipt_contract import _OPERATION_ID
from ._transaction_content import _directory, _exclusive_file, _stable_file
from .errors import ReleaseError
from .materialize import CandidateSet
from .mode_candidates import verify_mode_candidate
from .receipts import _sync_directory
from .target import ManagedTarget


_RELEASE_ID: Final = re.compile(r"sha256:[0-9a-f]{64}")
_MARKER: Final = "mode-release-id.txt"


def _error(message: str, *, code: str = "WFREL_TRANSACTION_FAILED") -> ReleaseError:
    return ReleaseError(code, message)


@dataclass(frozen=True)
class ModeSwitch:
    operation_id: str
    release_id: str
    candidate_root: Path = field(repr=False)
    active_root: Path = field(repr=False)
    previous_root: Path = field(repr=False)
    staging_root: Path = field(repr=False)
    candidate_parent_identity: tuple[int, int] = field(repr=False)
    active_parent_identity: tuple[int, int] = field(repr=False)


def _marker(staging_root: Path, release_id: str) -> None:
    _exclusive_file(staging_root / _MARKER, release_id.encode("ascii") + b"\n")
    _sync_directory(staging_root)


def _switch(
    target: ManagedTarget,
    operation_id: str,
    release_id: str,
) -> ModeSwitch:
    release_name = release_id.replace(":", "-", 1)
    staging = target.state_root / "staging" / operation_id
    return ModeSwitch(
        operation_id,
        release_id,
        target.component_roots.modes / release_name,
        target.modes_root,
        staging / "modes-previous",
        staging,
        _directory(target.component_roots.modes),
        _directory(target.modes_root.parent),
    )


def prepare_mode_switch(
    candidates: CandidateSet,
    target: ManagedTarget,
    operation_id: str,
) -> ModeSwitch:
    """Pin one inactive candidate and exact active Mode root before switching."""
    if (
        not isinstance(candidates, CandidateSet)
        or not isinstance(target, ManagedTarget)
        or not isinstance(operation_id, str)
        or _OPERATION_ID.fullmatch(operation_id) is None
        or candidates.mode_candidate is None
        or candidates.modes_root != candidates.mode_candidate.root
    ):
        raise _error("Mode switch input is invalid")
    verify_mode_candidate(candidates.mode_candidate)
    switch = _switch(target, operation_id, candidates.release_id)
    if switch.candidate_root != candidates.modes_root:
        raise _error("Mode candidate identity is inconsistent")
    _directory(switch.staging_root)
    _directory(switch.active_root)
    if switch.previous_root.exists() or switch.previous_root.is_symlink():
        raise _error("retained Mode root already exists", code="WFREL_STATE_CONFLICT")
    if _directory(switch.candidate_root)[0] != _directory(switch.active_root.parent)[0]:
        raise _error("candidate and active Mode roots must share one volume")
    _marker(switch.staging_root, candidates.release_id)
    return switch


def apply_mode_switch(switch: ModeSwitch) -> None:
    """Replace the stopped target Mode root and retain the exact previous root."""
    if not isinstance(switch, ModeSwitch):
        raise _error("Mode switch is invalid")
    if (
        _directory(switch.candidate_root.parent) != switch.candidate_parent_identity
        or _directory(switch.active_root.parent) != switch.active_parent_identity
        or switch.previous_root.exists()
    ):
        raise _error("Mode switch parent changed")
    _directory(switch.candidate_root)
    _directory(switch.active_root)
    try:
        os.rename(switch.active_root, switch.previous_root)
        try:
            os.rename(switch.candidate_root, switch.active_root)
        except OSError:
            os.rename(switch.previous_root, switch.active_root)
            raise
    except OSError:
        raise _error("Mode component could not be switched") from None
    _sync_directory(switch.candidate_root.parent)
    _sync_directory(switch.active_root.parent)
    _sync_directory(switch.staging_root)


def restore_mode_switch(switch: ModeSwitch) -> None:
    """Restore the retained Mode root; repeated restoration is an explicit no-op."""
    if not isinstance(switch, ModeSwitch):
        raise _error("Mode switch is invalid")
    candidate_exists = switch.candidate_root.exists() or switch.candidate_root.is_symlink()
    active_exists = switch.active_root.exists() or switch.active_root.is_symlink()
    previous_exists = switch.previous_root.exists() or switch.previous_root.is_symlink()
    if active_exists and candidate_exists and not previous_exists:
        _directory(switch.active_root)
        _directory(switch.candidate_root)
        return
    if not active_exists or candidate_exists or not previous_exists:
        raise _error("retained Mode switch state is ambiguous")
    if (
        _directory(switch.candidate_root.parent) != switch.candidate_parent_identity
        or _directory(switch.active_root.parent) != switch.active_parent_identity
    ):
        raise _error("Mode recovery parent changed")
    _directory(switch.active_root)
    _directory(switch.previous_root)
    try:
        os.rename(switch.active_root, switch.candidate_root)
        try:
            os.rename(switch.previous_root, switch.active_root)
        except OSError:
            os.rename(switch.candidate_root, switch.active_root)
            raise
    except OSError:
        raise _error("Mode component could not be restored") from None
    _sync_directory(switch.candidate_root.parent)
    _sync_directory(switch.active_root.parent)
    _sync_directory(switch.staging_root)


def load_mode_switch(
    target: ManagedTarget,
    operation_id: str,
    release_id: str,
) -> ModeSwitch | None:
    """Reconstruct an optional retained Mode switch from one exact marker."""
    if (
        not isinstance(target, ManagedTarget)
        or not isinstance(operation_id, str)
        or _OPERATION_ID.fullmatch(operation_id) is None
        or not isinstance(release_id, str)
        or _RELEASE_ID.fullmatch(release_id) is None
    ):
        raise _error("retained Mode switch identity is invalid")
    staging = target.state_root / "staging" / operation_id
    marker = staging / _MARKER
    if not marker.exists() and not marker.is_symlink():
        return None
    if _stable_file(marker) != release_id.encode("ascii") + b"\n":
        raise _error("retained Mode switch marker is invalid")
    switch = _switch(target, operation_id, release_id)
    active = switch.active_root.exists() or switch.active_root.is_symlink()
    candidate = switch.candidate_root.exists() or switch.candidate_root.is_symlink()
    previous = switch.previous_root.exists() or switch.previous_root.is_symlink()
    if not active or (candidate == previous):
        raise _error("retained Mode switch state is ambiguous")
    _directory(switch.active_root)
    _directory(switch.candidate_root if candidate else switch.previous_root)
    return switch


__all__ = [
    "ModeSwitch",
    "apply_mode_switch",
    "load_mode_switch",
    "prepare_mode_switch",
    "restore_mode_switch",
]
