"""Private exact content-switch and current-pointer recovery helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import re
from typing import Final

from ._receipt_contract import _OPERATION_ID
from ._target_facts import target_facts_from_wire, target_facts_to_wire
from .canonical import canonical_json_bytes, load_json_strict_bytes
from .errors import ReleaseError
from .materialize import CandidateSet
from .receipts import _sync_directory, _write_exact
from .target import ManagedTarget
from .probe import TargetFacts


_MAX_POINTER_BYTES: Final = 256 * 1024
_REPARSE_POINT: Final = 0x0400
_DOTTED_VERSION: Final = re.compile(r"(?:0|[1-9][0-9]*)(?:\.(?:0|[1-9][0-9]*))+")
_RELEASE_ID: Final = re.compile(r"sha256:[0-9a-f]{64}")


def _error(message: str, *, code: str = "WFREL_TRANSACTION_FAILED") -> ReleaseError:
    return ReleaseError(code, message)


def _is_reparse(item: os.stat_result) -> bool:
    return stat.S_ISLNK(item.st_mode) or bool(
        getattr(item, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _directory(path: Path) -> tuple[int, int]:
    try:
        item = path.lstat()
    except OSError:
        raise _error("managed content directory is unavailable") from None
    if not stat.S_ISDIR(item.st_mode) or _is_reparse(item):
        raise _error("managed content directory is unsafe")
    return item.st_dev, item.st_ino


def _ensure_directory(parent: Path, name: str) -> Path:
    parent_identity = _directory(parent)
    child = parent / name
    try:
        child.mkdir()
    except FileExistsError:
        pass
    except OSError:
        raise _error("managed content directory could not be created") from None
    if _directory(parent) != parent_identity:
        raise _error("managed content directory changed")
    _directory(child)
    _sync_directory(parent)
    return child


def _stable_file(path: Path) -> bytes:
    try:
        before = path.lstat()
        if not stat.S_ISREG(before.st_mode) or _is_reparse(before):
            raise OSError("unsafe file")
        identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if before.st_size > _MAX_POINTER_BYTES:
            raise _error("content current pointer exceeds the size limit")
        chunks: list[bytes] = []
        size = 0
        with path.open("rb") as reader:
            opened = os.fstat(reader.fileno())
            if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != identity:
                raise OSError("opened identity changed")
            while size <= _MAX_POINTER_BYTES:
                chunk = reader.read(min(64 * 1024, _MAX_POINTER_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
            opened_after = os.fstat(reader.fileno())
        after = path.lstat()
    except ReleaseError:
        raise
    except OSError:
        raise _error("content current pointer is unavailable") from None
    raw = b"".join(chunks)
    if len(raw) != identity[2] or len(raw) > _MAX_POINTER_BYTES or (
        opened_after.st_dev, opened_after.st_ino,
        opened_after.st_size, opened_after.st_mtime_ns,
    ) != identity or (
        after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
    ) != identity or _is_reparse(after):
        raise _error("content current pointer changed while it was read")
    return raw


def _exclusive_file(path: Path, raw: bytes) -> None:
    try:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
        with os.fdopen(descriptor, "wb", buffering=0) as writer:
            _write_exact(writer, raw)
            writer.flush()
            os.fsync(writer.fileno())
    except OSError:
        raise _error("operation staging could not be written") from None


def _atomic_restore(path: Path, raw: bytes) -> None:
    parent = path.parent
    parent_identity = _directory(parent)
    temporary = parent / f".{path.name}.wf-release-v1-restore"
    try:
        if temporary.exists() or temporary.is_symlink():
            raise _error("content current restore staging already exists")
        _exclusive_file(temporary, raw)
        if _directory(parent) != parent_identity:
            raise _error("content current directory changed")
        os.replace(temporary, path)
        _sync_directory(parent)
    except ReleaseError:
        raise
    except OSError:
        raise _error("content current pointer could not be restored") from None
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


@dataclass(frozen=True)
class ContentSwitch:
    operation_id: str
    target_version: str
    candidate_version_root: Path = field(repr=False)
    active_version_root: Path = field(repr=False)
    staging_root: Path = field(repr=False)
    pointer: Path = field(repr=False)
    candidate_parent_identity: tuple[int, int] = field(repr=False)
    active_parent_identity: tuple[int, int] = field(repr=False)
    pointer_parent_identity: tuple[int, int] = field(repr=False)


def _target_version(candidates: CandidateSet) -> str:
    parts = tuple(PurePosixPath(item).parts for item in candidates.relative_paths)
    if not parts or any(len(item) < 3 or item[0] != "patches" for item in parts):
        raise _error("candidate content layout is invalid")
    versions = {item[1] for item in parts}
    if len(versions) != 1:
        raise _error("candidate content layout is invalid")
    return next(iter(versions))


def prepare_content_switch(
    candidates: CandidateSet,
    target: ManagedTarget,
    operation_id: str,
) -> ContentSwitch:
    """Snapshot the exact pointer and validate one not-yet-applied switch."""
    if (
        not isinstance(candidates, CandidateSet)
        or not isinstance(target, ManagedTarget)
        or not isinstance(operation_id, str)
        or _OPERATION_ID.fullmatch(operation_id) is None
        or candidates.content_root is None
        or candidates.server_root is not None
    ):
        raise _error("content switch input is invalid")
    version = _target_version(candidates)
    candidate_version = candidates.content_root / "patches" / version
    _directory(candidate_version)
    candidate_parent_identity = _directory(candidate_version.parent)
    active_patches = _ensure_directory(target.cdn_root, "patches")
    active_parent_identity = _directory(active_patches)
    active_version = active_patches / version
    if active_version.exists() or active_version.is_symlink():
        raise _error("active content version already exists", code="WFREL_STATE_CONFLICT")
    if _directory(candidate_version)[0] != _directory(active_patches)[0]:
        raise _error("candidate and active content roots must share one volume")

    staging = _ensure_directory(target.state_root, "staging")
    operation_staging = staging / operation_id
    try:
        operation_staging.mkdir()
    except OSError:
        raise _error("operation staging already exists", code="WFREL_STATE_CONFLICT") from None
    _directory(operation_staging)
    pointer = target.data_root / "state" / "content" / "current.json"
    pointer_parent_identity = _directory(pointer.parent)
    if pointer.exists() or pointer.is_symlink():
        raw = _stable_file(pointer)
        _exclusive_file(operation_staging / "content-current.json", raw)
        _exclusive_file(
            operation_staging / "content-current.sha256",
            hashlib.sha256(raw).hexdigest().encode("ascii") + b"\n",
        )
    else:
        _exclusive_file(operation_staging / "content-current.absent", b"absent\n")
    _exclusive_file(
        operation_staging / "content-target-version.txt",
        version.encode("ascii") + b"\n",
    )
    _sync_directory(operation_staging)
    _sync_directory(staging)
    return ContentSwitch(
        operation_id,
        version,
        candidate_version,
        active_version,
        operation_staging,
        pointer,
        candidate_parent_identity,
        active_parent_identity,
        pointer_parent_identity,
    )


def save_baseline_facts(switch: ContentSwitch, facts: TargetFacts) -> None:
    if not isinstance(switch, ContentSwitch):
        raise _error("content switch is invalid")
    raw = canonical_json_bytes(target_facts_to_wire(facts))
    _exclusive_file(switch.staging_root / "baseline-target-facts.json", raw)
    _sync_directory(switch.staging_root)


def load_baseline_facts(switch: ContentSwitch) -> TargetFacts:
    if not isinstance(switch, ContentSwitch):
        raise _error("content switch is invalid")
    raw = _stable_file(switch.staging_root / "baseline-target-facts.json")
    return target_facts_from_wire(load_json_strict_bytes(raw, label="baselineTargetFacts"))


def load_content_switch(
    target: ManagedTarget,
    operation_id: str,
    release_id: str,
) -> ContentSwitch:
    """Reconstruct one retained content switch without directory discovery."""
    if (
        not isinstance(target, ManagedTarget)
        or not isinstance(operation_id, str)
        or _OPERATION_ID.fullmatch(operation_id) is None
        or not isinstance(release_id, str)
        or _RELEASE_ID.fullmatch(release_id) is None
    ):
        raise _error("retained content switch identity is invalid")
    staging_root = target.state_root / "staging" / operation_id
    _directory(staging_root)
    raw_version = _stable_file(staging_root / "content-target-version.txt")
    try:
        version = raw_version.decode("ascii").removesuffix("\n")
    except UnicodeDecodeError:
        raise _error("retained content target version is invalid") from None
    if raw_version != version.encode("ascii") + b"\n" or _DOTTED_VERSION.fullmatch(version) is None:
        raise _error("retained content target version is invalid")
    release_root = target.component_roots.content / release_id.replace(":", "-", 1)
    candidate_parent = release_root / "patches"
    active_parent = target.cdn_root / "patches"
    candidate_version = candidate_parent / version
    active_version = active_parent / version
    candidate_exists = candidate_version.exists() or candidate_version.is_symlink()
    active_exists = active_version.exists() or active_version.is_symlink()
    if candidate_exists == active_exists:
        raise _error("retained content switch has an ambiguous component state")
    if candidate_exists:
        _directory(candidate_version)
    else:
        _directory(active_version)
    pointer = target.data_root / "state" / "content" / "current.json"
    return ContentSwitch(
        operation_id,
        version,
        candidate_version,
        active_version,
        staging_root,
        pointer,
        _directory(candidate_parent),
        _directory(active_parent),
        _directory(pointer.parent),
    )


def apply_content_switch(switch: ContentSwitch) -> None:
    """Perform only the atomic same-volume directory rename."""
    if not isinstance(switch, ContentSwitch):
        raise _error("content switch is invalid")
    if switch.active_version_root.exists() or switch.active_version_root.is_symlink():
        raise _error("active content version already exists", code="WFREL_STATE_CONFLICT")
    if (
        _directory(switch.candidate_version_root.parent)
        != switch.candidate_parent_identity
        or _directory(switch.active_version_root.parent)
        != switch.active_parent_identity
    ):
        raise _error("content switch parent changed")
    _directory(switch.candidate_version_root)
    try:
        os.rename(switch.candidate_version_root, switch.active_version_root)
    except OSError:
        raise _error("content component could not be switched") from None


def sync_content_switch(switch: ContentSwitch) -> None:
    _directory(switch.active_version_root)
    _sync_directory(switch.candidate_version_root.parent)
    _sync_directory(switch.active_version_root.parent)


def restore_content_switch(switch: ContentSwitch) -> None:
    """Restore the candidate directory and exact previous current pointer."""
    if not isinstance(switch, ContentSwitch):
        raise _error("content switch is invalid")
    candidate_exists = (
        switch.candidate_version_root.exists() or switch.candidate_version_root.is_symlink()
    )
    active_exists = switch.active_version_root.exists() or switch.active_version_root.is_symlink()
    if candidate_exists == active_exists:
        raise _error("content recovery state is ambiguous")
    if (
        _directory(switch.candidate_version_root.parent)
        != switch.candidate_parent_identity
        or _directory(switch.active_version_root.parent)
        != switch.active_parent_identity
    ):
        raise _error("content recovery parent changed")
    if active_exists:
        _directory(switch.active_version_root)
        try:
            os.rename(switch.active_version_root, switch.candidate_version_root)
        except OSError:
            raise _error("content component could not be restored") from None
        _sync_directory(switch.candidate_version_root.parent)
        _sync_directory(switch.active_version_root.parent)
    else:
        _directory(switch.candidate_version_root)

    saved = switch.staging_root / "content-current.json"
    digest = switch.staging_root / "content-current.sha256"
    absent = switch.staging_root / "content-current.absent"
    if _directory(switch.pointer.parent) != switch.pointer_parent_identity:
        raise _error("content current directory changed")
    if saved.is_file() and digest.is_file() and not absent.exists():
        raw = _stable_file(saved)
        expected = _stable_file(digest)
        actual = hashlib.sha256(raw).hexdigest().encode("ascii") + b"\n"
        if expected != actual:
            raise _error("saved content current pointer is corrupt")
        _atomic_restore(switch.pointer, raw)
    elif absent.is_file() and not saved.exists() and not digest.exists():
        try:
            if switch.pointer.exists() or switch.pointer.is_symlink():
                current = switch.pointer.lstat()
                if not stat.S_ISREG(current.st_mode) or _is_reparse(current):
                    raise _error("content current pointer is unsafe")
            switch.pointer.unlink(missing_ok=True)
            _sync_directory(switch.pointer.parent)
        except OSError:
            raise _error("content current pointer could not be removed") from None
    else:
        raise _error("saved content current pointer is incomplete")
