"""Canonical operation receipts and atomic managed-release state."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import secrets
import stat
from typing import BinaryIO, Final, Iterator

from ._receipt_contract import (
    _OPERATION_ID,
    OperationReceipt,
    invalid_receipt as _invalid,
    invalid_state as _state_invalid,
    new_operation_id,
    receipt_from_wire as _receipt_from_wire,
    validate_receipt_update as _validate_receipt_update,
    validate_release_id as _validate_release_id,
    validate_release_ids as _validate_release_ids,
    _wire_time,
)
from .canonical import canonical_json_bytes, load_json_strict_bytes
from .compatibility import ActiveRelease, ActiveState
from .errors import ReleaseError
from .schema import OwnershipManifest, parse_ownership

_MAX_DOCUMENT_BYTES: Final = 256 * 1024
_LOCK_NAME: Final = ".wf-release-v1.lock"
_OPERATION_RESERVATION_NAME: Final = ".wf-release-v1.operation"
_REPARSE_POINT_ATTRIBUTE: Final = 0x0400
_SAFE_TEXT: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+:-]{0,127}")
_STATE_KEYS: Final = frozenset({
    "schemaVersion", "clientVersion", "resourceBaseline", "clientPatchProfile",
    "releases", "knownReleaseIds",
})

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
            current = _snapshot(lock_path)
            if lock_snapshot is None or current != lock_snapshot:
                if not active_error:
                    raise _state_invalid("state lock identity changed during the operation")
            else:
                lock_path.unlink()
                _sync_directory(root)
        except ReleaseError:
            if not active_error:
                raise
        except OSError:
            if not active_error:
                raise ReleaseError("WFREL_STATE_IO", "state lock could not be released") from None


@contextmanager
def operation_reservation(root: Path, operation_id: str) -> Iterator[None]:
    """Hold one nofollow operation-wide reservation across all release phases."""
    if not isinstance(operation_id, str) or _OPERATION_ID.fullmatch(operation_id) is None:
        raise _invalid("operation identity is invalid")
    expected = _root_snapshot(root)
    reservation = root / _OPERATION_RESERVATION_NAME
    try:
        descriptor = _open_exclusive(reservation)
    except FileExistsError:
        raise ReleaseError("WFREL_STATE_LOCKED", "target operation is already reserved") from None
    except OSError:
        raise ReleaseError("WFREL_STATE_IO", "target operation could not be reserved") from None

    reservation_snapshot: tuple[int, int, int, int, bool, bool] | None = None
    active_error = False
    try:
        raw = canonical_json_bytes({
            "createdAt": _wire_time(datetime.now(timezone.utc)),
            "operationId": operation_id,
        })
        with os.fdopen(descriptor, "wb", buffering=0) as writer:
            try:
                _write_exact(writer, raw)
                writer.flush()
                os.fsync(writer.fileno())
            except OSError:
                reservation_snapshot = _stat_identity(os.fstat(writer.fileno()))
                raise ReleaseError(
                    "WFREL_STATE_IO", "target operation reservation could not be initialized"
                ) from None
            reservation_snapshot = _stat_identity(os.fstat(writer.fileno()))
        if (
            not reservation_snapshot[4]
            or reservation_snapshot[5]
            or _snapshot(reservation) != reservation_snapshot
        ):
            raise _state_invalid("target operation reservation identity is invalid")
        _same_root(root, expected)
        _sync_directory(root)
        yield
    except BaseException:
        active_error = True
        raise
    finally:
        try:
            current = _snapshot(reservation)
            if reservation_snapshot is None or current != reservation_snapshot:
                if not active_error:
                    raise _state_invalid(
                        "target operation reservation identity changed during the operation"
                    )
            else:
                reservation.unlink()
                _sync_directory(root)
        except ReleaseError:
            if not active_error:
                raise
        except OSError:
            if not active_error:
                raise ReleaseError(
                    "WFREL_STATE_IO", "target operation reservation could not be released"
                ) from None

def _atomic_write(
    root: Path,
    expected_root: tuple[int, int],
    parent: Path,
    destination: Path,
    raw: bytes,
) -> None:
    token = secrets.token_hex(16)
    temp = parent / f".{destination.name}.{token}.tmp"
    rollback = parent / f".{destination.name}.{token}.rollback"
    temp_identity: tuple[int, int, int, int, bool, bool] | None = None
    rollback_identity: tuple[int, int, int, int, bool, bool] | None = None
    preserve_rollback = False
    try:
        try:
            existing = _snapshot(destination)
        except FileNotFoundError:
            existing = None
        if existing is not None and (not existing[4] or existing[5]):
            raise _state_invalid("state destination must be a regular file")
        descriptor = _open_exclusive(temp)
        with os.fdopen(descriptor, "wb", buffering=0) as writer:
            try:
                _write_exact(writer, raw)
                writer.flush()
                os.fsync(writer.fileno())
            except OSError:
                temp_identity = _stat_identity(os.fstat(writer.fileno()))
                raise
            temp_identity = _stat_identity(os.fstat(writer.fileno()))
        _same_root(root, expected_root)
        if temp_identity[2] != len(raw) or _snapshot(temp) != temp_identity:
            raise _state_invalid("state temporary file identity changed")
        if existing is not None:
            os.link(destination, rollback, follow_symlinks=False)
            rollback_identity = _snapshot(rollback)
            if rollback_identity != existing or _snapshot(destination) != existing:
                raise _state_invalid("state destination changed before commit")
        _directory_snapshot(parent)
        os.replace(temp, destination)
        try:
            committed = _snapshot(destination)
        except FileNotFoundError:
            committed = None
        if committed != temp_identity:
            if rollback_identity is None:
                try:
                    destination.unlink()
                except FileNotFoundError:
                    pass
            else:
                if _snapshot(rollback) != rollback_identity:
                    raise _state_invalid("state rollback identity changed")
                try:
                    os.replace(rollback, destination)
                except OSError:
                    preserve_rollback = True
                    _sync_directory(parent)
                    raise
                if _snapshot(destination) != rollback_identity:
                    raise _state_invalid("state destination could not be restored")
            _sync_directory(parent)
            raise _state_invalid("state destination identity is invalid")
        if rollback_identity is not None:
            rollback.unlink()
        _sync_directory(parent)
    except ReleaseError:
        raise
    except OSError:
        raise ReleaseError("WFREL_STATE_IO", "state document could not be committed") from None
    finally:
        for path, identity in ((temp, temp_identity), (rollback, rollback_identity)):
            try:
                disposable = path != rollback or not preserve_rollback
                if identity is not None and disposable and _snapshot(path) == identity:
                    path.unlink()
            except (FileNotFoundError, OSError):
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
        try:
            ownership = item.ownership.to_wire()
            if parse_ownership(ownership) != item.ownership:
                raise ValueError
        except (AttributeError, ReleaseError, TypeError, ValueError):
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

def load_previous_state(root: Path) -> ActiveState:
    """Load the exact previous commit point without falling back to active."""
    _root_snapshot(root)
    return _state_from_wire(_read_canonical(root / "previous.json", kind="previous state"))

def load_operation_receipt(root: Path, operation_id: str) -> OperationReceipt:
    """Load one exact operation receipt by its canonical identity."""
    if not isinstance(operation_id, str) or _OPERATION_ID.fullmatch(operation_id) is None:
        raise _invalid("operation identity is invalid")
    _root_snapshot(root)
    return _receipt_from_wire(_read_canonical(
        root / "receipts" / f"{operation_id}.json", kind="operation receipt"
    ))

def list_operation_receipts(root: Path) -> tuple[OperationReceipt, ...]:
    """Read the complete strict receipt directory in canonical identity order."""
    _root_snapshot(root)
    directory = root / "receipts"
    _directory_snapshot(directory)
    try:
        entries = tuple(os.scandir(directory))
    except OSError:
        raise _invalid("operation receipt directory is unavailable") from None
    operation_ids: list[str] = []
    for entry in entries:
        name = entry.name
        operation_id = name.removesuffix(".json")
        try:
            item = entry.stat(follow_symlinks=False)
        except OSError:
            raise _invalid("operation receipt is unavailable") from None
        if (
            name != f"{operation_id}.json"
            or _OPERATION_ID.fullmatch(operation_id) is None
            or not stat.S_ISREG(item.st_mode)
            or bool(getattr(item, "st_file_attributes", 0) & _REPARSE_POINT_ATTRIBUTE)
        ):
            raise _invalid("operation receipt directory contains an invalid member")
        operation_ids.append(operation_id)
    if len(operation_ids) != len(set(operation_ids)):
        raise _invalid("operation receipt identities are not unique")
    return tuple(
        load_operation_receipt(root, operation_id)
        for operation_id in sorted(operation_ids)
    )

def write_phase_receipt(root: Path, receipt: OperationReceipt) -> None:
    """Atomically create or advance one operation receipt."""
    if not isinstance(receipt, OperationReceipt):
        raise _invalid("receipt type is invalid")
    raw = canonical_json_bytes(receipt.to_wire())
    if len(raw) > _MAX_DOCUMENT_BYTES:
        raise _invalid("receipt document exceeds its size limit")
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
    if max(len(previous_raw), len(active_raw)) > _MAX_DOCUMENT_BYTES:
        raise _state_invalid("active state exceeds its size limit")
    with _state_lock(root) as expected:
        active_path = root / "active.json"
        previous_path = root / "previous.json"
        if active_path.exists() or active_path.is_symlink():
            current = _state_from_wire(_read_canonical(active_path, kind="active state"))
            if current != previous:
                raise ReleaseError("WFREL_STATE_CONFLICT", "active state changed before commit")
        else:
            if previous_path.exists() or previous_path.is_symlink():
                raise ReleaseError(
                    "WFREL_STATE_CONFLICT",
                    "previous state exists without an active commit point",
                )
            if previous.releases or previous.known_release_ids:
                raise ReleaseError("WFREL_STATE_CONFLICT", "initial active state is unavailable")
        if previous_path.exists() or previous_path.is_symlink():
            _state_from_wire(_read_canonical(previous_path, kind="previous state"))
        _atomic_write(root, expected, root, previous_path, previous_raw)
        _atomic_write(root, expected, root, active_path, active_raw)

__all__ = [
    "OperationReceipt", "commit_active_state", "list_operation_receipts",
    "load_active_state", "load_operation_receipt", "load_previous_state",
    "new_operation_id", "operation_reservation", "write_phase_receipt",
]
