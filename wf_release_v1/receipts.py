"""Canonical operation receipts and atomic managed-release state."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import secrets
import stat
from typing import BinaryIO, Final, Iterator

from .canonical import canonical_json_bytes, load_json_strict_bytes
from .compatibility import ActiveRelease, ActiveState
from .errors import ReleaseError
from .schema import OwnershipManifest, parse_ownership


_MAX_DOCUMENT_BYTES: Final = 256 * 1024
_LOCK_NAME: Final = ".wf-release-v1.lock"
_REPARSE_POINT_ATTRIBUTE: Final = 0x0400
_RELEASE_ID: Final = re.compile(r"sha256:[0-9a-f]{64}")
_OPERATION_ID: Final = re.compile(r"[0-9]{8}T[0-9]{6}\.[0-9]{6}Z-[0-9a-f]{32}")
_ERROR_CODE: Final = re.compile(r"WFREL_[A-Z0-9_]+")
_SAFE_TEXT: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+:-]{0,127}")
_PHASES: Final = frozenset({
    "CREATED", "VERIFIED", "PROBED", "STOPPED", "MATERIALIZED", "SWITCHED",
    "STARTED", "HEALTH_READY", "CAPABILITIES_ACCEPTED", "COMMITTED",
})
_OUTCOMES: Final = frozenset({
    "in_progress", "succeeded", "failed", "recovered", "recovery_failed",
})
_RECOVERY_OUTCOMES: Final = frozenset({None, "recovered", "failed"})
_STATE_KEYS: Final = frozenset({
    "schemaVersion", "clientVersion", "resourceBaseline", "clientPatchProfile",
    "releases", "knownReleaseIds",
})
_RECEIPT_KEYS: Final = frozenset({
    "schemaVersion", "operationId", "releaseId", "phase", "outcome", "startedAt",
    "updatedAt", "beforeReleaseIds", "candidateReleaseIds", "errorCode",
    "recoveryOutcome",
})


def _invalid(message: str) -> ReleaseError:
    return ReleaseError("WFREL_RECEIPT_INVALID", message)

def _state_invalid(message: str) -> ReleaseError:
    return ReleaseError("WFREL_STATE_INVALID", message)

def _validate_release_id(value: object, *, state: bool = False) -> str:
    if not isinstance(value, str) or _RELEASE_ID.fullmatch(value) is None:
        raise (_state_invalid("release identity is invalid") if state else _invalid("release identity is invalid"))
    return value

def _validate_release_ids(value: object, *, state: bool = False) -> tuple[str, ...]:
    error = _state_invalid if state else _invalid
    if not isinstance(value, tuple):
        raise error("release identities must be a tuple")
    parsed = tuple(_validate_release_id(item, state=state) for item in value)
    if tuple(sorted(set(parsed))) != parsed:
        raise error("release identities must be unique and canonically ordered")
    return parsed

def _wire_time(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise _invalid("receipt time must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_wire_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise _invalid("receipt time is invalid")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError:
        raise _invalid("receipt time is invalid") from None
    if _wire_time(parsed.replace(tzinfo=timezone.utc)) != value:
        raise _invalid("receipt time is not canonical")
    return parsed.replace(tzinfo=timezone.utc)


def new_operation_id(now: datetime, nonce: bytes) -> str:
    """Derive one deterministic, path-safe operation identity."""
    if not isinstance(nonce, bytes) or len(nonce) != 16:
        raise _invalid("operation nonce must contain exactly 16 bytes")
    timestamp = _wire_time(now).replace("-", "").replace(":", "")
    return f"{timestamp}-{nonce.hex()}"


@dataclass(frozen=True)
class OperationReceipt:
    schema_version: int
    operation_id: str
    release_id: str
    phase: str
    outcome: str
    started_at: datetime
    updated_at: datetime
    before_release_ids: tuple[str, ...]
    candidate_release_ids: tuple[str, ...]
    error_code: str | None
    recovery_outcome: str | None

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise _invalid("receipt schema version is not supported")
        if not isinstance(self.operation_id, str) or _OPERATION_ID.fullmatch(self.operation_id) is None:
            raise _invalid("operation identity is invalid")
        _validate_release_id(self.release_id)
        if not isinstance(self.phase, str) or self.phase not in _PHASES:
            raise _invalid("receipt phase is invalid")
        if not isinstance(self.outcome, str) or self.outcome not in _OUTCOMES:
            raise _invalid("receipt outcome is invalid")
        started = _wire_time(self.started_at)
        updated = _wire_time(self.updated_at)
        if updated < started:
            raise _invalid("receipt update precedes its start")
        _validate_release_ids(self.before_release_ids)
        _validate_release_ids(self.candidate_release_ids)
        if self.error_code is not None and (
            not isinstance(self.error_code, str)
            or _ERROR_CODE.fullmatch(self.error_code) is None
        ):
            raise _invalid("receipt error code is invalid")
        if self.recovery_outcome is not None and not (
            isinstance(self.recovery_outcome, str) and self.recovery_outcome in _RECOVERY_OUTCOMES):
            raise _invalid("receipt recovery outcome is invalid")

    def to_wire(self) -> dict[str, object]:
        return {
            "schemaVersion": self.schema_version, "operationId": self.operation_id,
            "releaseId": self.release_id, "phase": self.phase, "outcome": self.outcome,
            "startedAt": _wire_time(self.started_at), "updatedAt": _wire_time(self.updated_at),
            "beforeReleaseIds": list(self.before_release_ids),
            "candidateReleaseIds": list(self.candidate_release_ids), "errorCode": self.error_code,
            "recoveryOutcome": self.recovery_outcome,
        }


def _receipt_from_wire(value: object) -> OperationReceipt:
    if not isinstance(value, dict) or set(value) != _RECEIPT_KEYS:
        raise _invalid("receipt keys do not match the contract")
    before = value["beforeReleaseIds"]
    candidates = value["candidateReleaseIds"]
    if not isinstance(before, list) or not isinstance(candidates, list):
        raise _invalid("receipt release identities are invalid")
    return OperationReceipt(
        schema_version=value["schemaVersion"],  # type: ignore[arg-type]
        operation_id=value["operationId"],  # type: ignore[arg-type]
        release_id=value["releaseId"],  # type: ignore[arg-type]
        phase=value["phase"],  # type: ignore[arg-type]
        outcome=value["outcome"],  # type: ignore[arg-type]
        started_at=_parse_wire_time(value["startedAt"]),
        updated_at=_parse_wire_time(value["updatedAt"]),
        before_release_ids=tuple(before),  # type: ignore[arg-type]
        candidate_release_ids=tuple(candidates),  # type: ignore[arg-type]
        error_code=value["errorCode"],  # type: ignore[arg-type]
        recovery_outcome=value["recoveryOutcome"],  # type: ignore[arg-type]
    )


def _snapshot(path: Path) -> tuple[int, int, int, int, bool, bool]:
    return _stat_identity(path.lstat())

def _stat_identity(item: os.stat_result) -> tuple[int, int, int, int, bool, bool]:
    return (
        item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, stat.S_ISREG(item.st_mode),
        bool(getattr(item, "st_file_attributes", 0) & _REPARSE_POINT_ATTRIBUTE),
    )


def _directory_snapshot(path: Path) -> tuple[int, int]:
    item = path.lstat()
    if (
        not stat.S_ISDIR(item.st_mode)
        or stat.S_ISLNK(item.st_mode)
        or getattr(item, "st_file_attributes", 0) & _REPARSE_POINT_ATTRIBUTE
    ):
        raise _state_invalid("state root must be a non-reparse directory")
    return item.st_dev, item.st_ino

def _root_snapshot(root: Path) -> tuple[int, int]:
    if not isinstance(root, Path) or not root.is_absolute():
        raise _state_invalid("state root is invalid")
    canonical = Path(os.path.abspath(root))
    if root != canonical or canonical.parent == canonical or canonical == Path(os.path.abspath(Path.home())):
        raise _state_invalid("state root is invalid")
    try:
        return _directory_snapshot(root)
    except (FileNotFoundError, OSError):
        raise _state_invalid("state root is unavailable") from None


def _same_root(root: Path, expected: tuple[int, int]) -> None:
    try:
        current = _directory_snapshot(root)
    except (FileNotFoundError, OSError):
        raise _state_invalid("state root changed during the operation") from None
    if current != expected:
        raise _state_invalid("state root changed during the operation")

def _ensure_child_directory(root: Path, expected: tuple[int, int], name: str) -> Path:
    child = root / name
    try:
        child.mkdir()
    except FileExistsError:
        pass
    except OSError:
        raise ReleaseError("WFREL_STATE_IO", "state directory could not be created") from None
    _same_root(root, expected)
    try:
        _directory_snapshot(child)
    except (FileNotFoundError, OSError, ReleaseError):
        raise _state_invalid("state child must be a non-reparse directory") from None
    return child


def _sync_directory(path: Path) -> None:
    if os.name != "nt":
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(path, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                     wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD,
                                     wintypes.HANDLE]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    kernel32.FlushFileBuffers.restype = wintypes.BOOL
    handle = kernel32.CreateFileW(str(path), 0x40000000, 7, None, 3, 0x02000000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), "directory could not be opened")
    try:
        if not kernel32.FlushFileBuffers(handle):
            raise OSError(ctypes.get_last_error(), "directory could not be synchronized")
    finally:
        kernel32.CloseHandle(handle)


def _write_exact(writer: BinaryIO, raw: bytes) -> None:
    if writer.write(raw) != len(raw):
        raise OSError("state write was incomplete")

def _open_exclusive(path: Path) -> int:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    return os.open(path, flags, 0o600)


@contextmanager
def _state_lock(root: Path) -> Iterator[tuple[int, int]]:
    expected = _root_snapshot(root)
    lock_path = root / _LOCK_NAME
    try:
        descriptor = _open_exclusive(lock_path)
    except FileExistsError:
        raise ReleaseError("WFREL_STATE_LOCKED", "state root is already locked") from None
    except OSError:
        raise ReleaseError("WFREL_STATE_IO", "state lock could not be created") from None

    lock_snapshot: tuple[int, int, int, int, bool, bool] | None = None
    active_error = False
    try:
        raw = canonical_json_bytes(
            {
                "createdAt": _wire_time(datetime.now(timezone.utc)),
                "nonce": secrets.token_hex(16),
            }
        )
        with os.fdopen(descriptor, "wb", buffering=0) as writer:
            try:
                _write_exact(writer, raw)
                writer.flush()
                os.fsync(writer.fileno())
            except OSError:
                lock_snapshot = _stat_identity(os.fstat(writer.fileno()))
                raise ReleaseError("WFREL_STATE_IO", "state lock could not be initialized") from None
            lock_snapshot = _stat_identity(os.fstat(writer.fileno()))
        if not lock_snapshot[4] or lock_snapshot[5] or _snapshot(lock_path) != lock_snapshot:
            raise _state_invalid("state lock identity is invalid")
        _same_root(root, expected)
        yield expected
    except BaseException:
        active_error = True
        raise
    finally:
        try:
            if lock_snapshot is not None and _snapshot(lock_path) == lock_snapshot:
                lock_path.unlink()
                _sync_directory(root)
        except OSError:
            if not active_error:
                raise ReleaseError("WFREL_STATE_IO", "state lock could not be released") from None


def _atomic_write(
    root: Path,
    expected_root: tuple[int, int],
    parent: Path,
    destination: Path,
    raw: bytes,
) -> None:
    temp = parent / f".{destination.name}.{secrets.token_hex(16)}.tmp"
    try:
        try:
            existing = _snapshot(destination)
        except FileNotFoundError:
            existing = None
        if existing is not None and (not existing[4] or existing[5]):
            raise _state_invalid("state destination must be a regular file")
        descriptor = _open_exclusive(temp)
        with os.fdopen(descriptor, "wb", buffering=0) as writer:
            _write_exact(writer, raw)
            writer.flush()
            os.fsync(writer.fileno())
        _same_root(root, expected_root)
        _directory_snapshot(parent)
        os.replace(temp, destination)
        if not _snapshot(destination)[4] or _snapshot(destination)[5]:
            raise _state_invalid("state destination identity is invalid")
        _sync_directory(parent)
    except ReleaseError:
        raise
    except OSError:
        raise ReleaseError("WFREL_STATE_IO", "state document could not be committed") from None
    finally:
        try:
            if temp.exists() and not temp.is_symlink():
                temp.unlink()
        except OSError:
            pass


def _read_canonical(path: Path, *, kind: str) -> object:
    try:
        before = _snapshot(path)
        if not before[4] or before[5] or before[2] > _MAX_DOCUMENT_BYTES:
            raise _state_invalid(f"{kind} document is invalid")
        with path.open("rb") as reader:
            opened_identity = _stat_identity(os.fstat(reader.fileno()))
            raw = reader.read(_MAX_DOCUMENT_BYTES + 1)
            after_open = _stat_identity(os.fstat(reader.fileno()))
        after = _snapshot(path)
        if (
            opened_identity != before
            or opened_identity != after_open
            or after != before
            or len(raw) > _MAX_DOCUMENT_BYTES
        ):
            raise _state_invalid(f"{kind} document changed while reading")
        value = load_json_strict_bytes(raw, label=kind)
        if canonical_json_bytes(value) != raw:
            raise _state_invalid(f"{kind} document is not canonical")
        return value
    except ReleaseError as error:
        if error.code == "WFREL_STATE_INVALID":
            raise
        raise _state_invalid(f"{kind} document is invalid") from None
    except (FileNotFoundError, OSError):
        raise _state_invalid(f"{kind} document is unavailable") from None


def _state_to_wire(state: ActiveState) -> dict[str, object]:
    if not isinstance(state, ActiveState):
        raise _state_invalid("active state type is invalid")
    if (
        not isinstance(state.client_version, str)
        or _SAFE_TEXT.fullmatch(state.client_version) is None
        or not isinstance(state.resource_baseline, str)
        or _SAFE_TEXT.fullmatch(state.resource_baseline) is None
        or type(state.client_patch_profile) is not bool
        or not isinstance(state.releases, tuple)
    ):
        raise _state_invalid("active state facts are invalid")
    if any(not isinstance(item, ActiveRelease) or not isinstance(item.ownership, OwnershipManifest) for item in state.releases):
        raise _state_invalid("active release is invalid")
    release_ids = tuple(item.release_id for item in state.releases)
    _validate_release_ids(release_ids, state=True)
    known_ids = _validate_release_ids(state.known_release_ids, state=True)
    if not set(release_ids).issubset(known_ids):
        raise _state_invalid("active releases must be known")
    releases: list[dict[str, object]] = []
    for item in state.releases:
        ownership = item.ownership.to_wire()
        try:
            if parse_ownership(ownership) != item.ownership:
                raise ValueError
        except (ReleaseError, ValueError):
            raise _state_invalid("active ownership is invalid") from None
        releases.append({"releaseId": item.release_id, "ownership": ownership})
    return {
        "schemaVersion": 1, "clientVersion": state.client_version,
        "resourceBaseline": state.resource_baseline,
        "clientPatchProfile": state.client_patch_profile, "releases": releases,
        "knownReleaseIds": list(known_ids),
    }


def _state_from_wire(value: object) -> ActiveState:
    if not isinstance(value, dict) or set(value) != _STATE_KEYS:
        raise _state_invalid("active state keys do not match the contract")
    raw_releases = value["releases"]
    raw_known = value["knownReleaseIds"]
    if not isinstance(raw_releases, list) or not isinstance(raw_known, list):
        raise _state_invalid("active state release identities are invalid")
    releases: list[ActiveRelease] = []
    for raw in raw_releases:
        if not isinstance(raw, dict) or set(raw) != {"releaseId", "ownership"}:
            raise _state_invalid("active release keys do not match the contract")
        release_id = _validate_release_id(raw["releaseId"], state=True)
        try:
            ownership = parse_ownership(raw["ownership"])
        except ReleaseError:
            raise _state_invalid("active ownership is invalid") from None
        releases.append(ActiveRelease(release_id, ownership))
    try:
        state = ActiveState(
            client_version=value["clientVersion"],  # type: ignore[arg-type]
            resource_baseline=value["resourceBaseline"],  # type: ignore[arg-type]
            client_patch_profile=value["clientPatchProfile"],  # type: ignore[arg-type]
            releases=tuple(releases),
            known_release_ids=tuple(raw_known),  # type: ignore[arg-type]
        )
    except TypeError:
        raise _state_invalid("active state values are invalid") from None
    if _state_to_wire(state) != value:
        raise _state_invalid("active state values are invalid")
    return state


def load_active_state(root: Path) -> ActiveState:
    """Load one strict canonical active state without guessing defaults."""
    _root_snapshot(root)
    return _state_from_wire(_read_canonical(root / "active.json", kind="active state"))


def _validate_receipt_update(old: OperationReceipt, new: OperationReceipt) -> None:
    if (
        old.operation_id != new.operation_id
        or old.release_id != new.release_id
        or old.started_at != new.started_at
        or old.before_release_ids != new.before_release_ids
        or old.candidate_release_ids != new.candidate_release_ids
        or new.updated_at < old.updated_at
    ):
        raise ReleaseError("WFREL_RECEIPT_CONFLICT", "operation identity was reused")


def write_phase_receipt(root: Path, receipt: OperationReceipt) -> None:
    """Atomically create or advance one operation receipt."""
    if not isinstance(receipt, OperationReceipt):
        raise _invalid("receipt type is invalid")
    raw = canonical_json_bytes(receipt.to_wire())
    with _state_lock(root) as expected:
        receipts = _ensure_child_directory(root, expected, "receipts")
        destination = receipts / f"{receipt.operation_id}.json"
        if destination.exists() or destination.is_symlink():
            old = _receipt_from_wire(_read_canonical(destination, kind="operation receipt"))
            _validate_receipt_update(old, receipt)
        _atomic_write(root, expected, receipts, destination, raw)


def commit_active_state(
    root: Path,
    *,
    previous: ActiveState,
    active: ActiveState,
) -> None:
    """Persist previous first and make active.json the final commit point."""
    previous_raw = canonical_json_bytes(_state_to_wire(previous))
    active_raw = canonical_json_bytes(_state_to_wire(active))
    with _state_lock(root) as expected:
        active_path = root / "active.json"
        previous_path = root / "previous.json"
        if active_path.exists() or active_path.is_symlink():
            current = _state_from_wire(_read_canonical(active_path, kind="active state"))
            if current != previous:
                raise ReleaseError("WFREL_STATE_CONFLICT", "active state changed before commit")
        elif previous.releases or previous.known_release_ids:
            raise ReleaseError("WFREL_STATE_CONFLICT", "initial active state is unavailable")
        if previous_path.exists() or previous_path.is_symlink():
            _state_from_wire(_read_canonical(previous_path, kind="previous state"))
        _atomic_write(root, expected, root, previous_path, previous_raw)
        _atomic_write(root, expected, root, active_path, active_raw)


__all__ = ["OperationReceipt", "commit_active_state", "load_active_state",
           "new_operation_id", "write_phase_receipt"]
