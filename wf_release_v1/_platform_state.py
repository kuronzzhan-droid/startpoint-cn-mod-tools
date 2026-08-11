"""Private exact process.json contract and atomic persistence."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat
from typing import Final

from .canonical import canonical_json_bytes, load_json_strict_bytes
from .errors import ReleaseError
from .receipts import (
    _atomic_write,
    _root_snapshot,
    _same_root,
    _snapshot,
    _state_lock,
    _sync_directory,
)


_MAX_PROCESS_BYTES: Final = 8 * 1024
_OPERATION_ID: Final = re.compile(r"[0-9]{8}T[0-9]{6}\.[0-9]{6}Z-[0-9a-f]{32}")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_PROCESS_KEYS: Final = frozenset({
    "schemaVersion", "operationId", "pid", "creationTime", "executableSha256",
})


def process_error(code: str, message: str) -> ReleaseError:
    return ReleaseError(code, message)


def validate_operation_id(value: object) -> str:
    if not isinstance(value, str) or _OPERATION_ID.fullmatch(value) is None:
        raise process_error("WFREL_PROCESS_INVALID", "operation identity is invalid")
    return value


@dataclass(frozen=True)
class ManagedProcess:
    pid: int
    creation_time: int
    executable_sha256: str
    operation_id: str

    def __post_init__(self) -> None:
        if type(self.pid) is not int or self.pid <= 0:
            raise process_error("WFREL_PROCESS_INVALID", "process identity is invalid")
        if type(self.creation_time) is not int or self.creation_time <= 0:
            raise process_error("WFREL_PROCESS_INVALID", "process identity is invalid")
        if not isinstance(self.executable_sha256, str) or _SHA256.fullmatch(self.executable_sha256) is None:
            raise process_error("WFREL_PROCESS_INVALID", "process identity is invalid")
        validate_operation_id(self.operation_id)

    def to_wire(self) -> dict[str, object]:
        return {
            "schemaVersion": 1,
            "operationId": self.operation_id,
            "pid": self.pid,
            "creationTime": self.creation_time,
            "executableSha256": self.executable_sha256,
        }


def _from_wire(value: object) -> ManagedProcess:
    if not isinstance(value, dict) or frozenset(value) != _PROCESS_KEYS:
        raise process_error("WFREL_PROCESS_INVALID", "process state keys do not match the contract")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
        raise process_error("WFREL_PROCESS_INVALID", "process state schema is not supported")
    return ManagedProcess(
        value["pid"], value["creationTime"], value["executableSha256"], value["operationId"],
    )  # type: ignore[arg-type]


class ProcessStateStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        _root_snapshot(root)

    @property
    def path(self) -> Path:
        return self.root / "process.json"

    def read(self) -> ManagedProcess | None:
        expected_root = _root_snapshot(self.root)
        try:
            before = _snapshot(self.path)
        except FileNotFoundError:
            return None
        except OSError:
            raise process_error("WFREL_PROCESS_INVALID", "process state is unavailable") from None
        if not before[4] or before[5] or before[2] > _MAX_PROCESS_BYTES:
            raise process_error("WFREL_PROCESS_INVALID", "process state is unavailable")
        try:
            with self.path.open("rb") as reader:
                opened = os.fstat(reader.fileno())
                raw = reader.read(_MAX_PROCESS_BYTES + 1)
                opened_after = os.fstat(reader.fileno())
            after = _snapshot(self.path)
        except OSError:
            raise process_error("WFREL_PROCESS_INVALID", "process state is unavailable") from None
        def identity(item: os.stat_result) -> tuple[int, int, int, int, bool]:
            return item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, stat.S_ISREG(item.st_mode)
        _same_root(self.root, expected_root)
        if (
            len(raw) > _MAX_PROCESS_BYTES
            or identity(opened) != before[:5]
            or identity(opened_after) != before[:5]
            or after != before
        ):
            raise process_error("WFREL_PROCESS_INVALID", "process state changed while it was read")
        try:
            return _from_wire(load_json_strict_bytes(raw, label="process state"))
        except ReleaseError as error:
            if error.code == "WFREL_PROCESS_INVALID":
                raise
            raise process_error("WFREL_PROCESS_INVALID", "process state is invalid") from None

    def write(self, process: ManagedProcess) -> None:
        raw = canonical_json_bytes(process.to_wire())
        try:
            with _state_lock(self.root) as expected_root:
                if self.path.exists():
                    raise process_error("WFREL_PROCESS_RUNNING", "managed process state already exists")
                _atomic_write(self.root, expected_root, self.root, self.path, raw)
        except ReleaseError:
            raise
        except OSError:
            raise process_error("WFREL_PROCESS_IO", "process state could not be written") from None

    def clear(self, expected: ManagedProcess) -> None:
        with _state_lock(self.root) as expected_root:
            current = self.read()
            if current is None:
                return
            if current != expected:
                raise process_error("WFREL_PROCESS_IDENTITY", "managed process state changed")
            try:
                self.path.unlink()
                _same_root(self.root, expected_root)
                _sync_directory(self.root)
            except OSError:
                raise process_error("WFREL_PROCESS_IO", "process state could not be cleared") from None
