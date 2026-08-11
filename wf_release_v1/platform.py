"""Host-owned launch environment and local process lifecycle boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import stat
import threading
from typing import BinaryIO, Final, Protocol

from ._platform_state import (
    ManagedProcess,
    ProcessStateStore,
    process_error as _process_error,
    validate_operation_id,
)
from ._platform_windows import ProcessIdentity, WindowsBackend as _WindowsBackend
from .errors import ReleaseError
from .receipts import _root_snapshot
from .target import LaunchSpec


_FORBIDDEN_ENVIRONMENT: Final = (
    "WDFP_DATABASE_DIR",
    "CONTENT_DIR",
    "CONTENT_STORE_DIR",
    "CONTENT_STATE_DIR",
    "CONTENT_RUNTIME_DIR",
)


def _platform_error(message: str) -> ReleaseError:
    return ReleaseError("WFREL_PLATFORM_INVALID", message)


def _canonical_path(value: object, label: str) -> Path:
    if not isinstance(value, Path) or not value.is_absolute():
        raise _platform_error(f"{label} must be an absolute canonical path")
    canonical = Path(os.path.abspath(value))
    if canonical != value or any("\x00" in part or ":" in part for part in value.parts[1:]):
        raise _platform_error(f"{label} must be an absolute canonical path")
    return canonical


def _paths_overlap(first: Path, second: Path) -> bool:
    left, right = os.path.normcase(os.fspath(first)), os.path.normcase(os.fspath(second))
    try:
        common = os.path.commonpath((left, right))
    except ValueError:
        return False
    return common == left or common == right


def _regular_file(path: Path, label: str) -> None:
    try:
        item = path.lstat()
    except OSError:
        raise _platform_error(f"{label} is unavailable") from None
    if (
        not stat.S_ISREG(item.st_mode)
        or stat.S_ISLNK(item.st_mode)
        or bool(getattr(item, "st_file_attributes", 0) & 0x0400)
    ):
        raise _platform_error(f"{label} is unavailable")


def _directory(path: Path, label: str) -> None:
    current = path
    while True:
        try:
            item = current.lstat()
        except FileNotFoundError:
            if current == path:
                raise _platform_error(f"{label} is unavailable") from None
        except OSError:
            raise _platform_error(f"{label} is unavailable") from None
        else:
            if stat.S_ISLNK(item.st_mode) or bool(getattr(item, "st_file_attributes", 0) & 0x0400):
                raise _platform_error(f"{label} must not traverse a reparse point")
            if current == path and not stat.S_ISDIR(item.st_mode):
                raise _platform_error(f"{label} is unavailable")
        if current.parent == current:
            return
        current = current.parent


def _validate_timeout(value: object, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise _platform_error(f"{label} is invalid")
    return float(value)


def _sha256_file(path: Path) -> str:
    try:
        before = path.stat()
        if not stat.S_ISREG(before.st_mode):
            raise OSError("not a regular file")
        digest = hashlib.sha256()
        with path.open("rb") as reader:
            opened = os.fstat(reader.fileno())
            if (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns) != (
                before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
            ):
                raise OSError("file identity changed")
            while chunk := reader.read(1024 * 1024):
                digest.update(chunk)
            opened_after = os.fstat(reader.fileno())
        after = path.stat()
    except OSError:
        raise _process_error("WFREL_PROCESS_IDENTITY", "runtime executable is unavailable") from None
    expected = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    if expected != (
        opened_after.st_dev, opened_after.st_ino, opened_after.st_size, opened_after.st_mtime_ns,
    ) or expected != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise _process_error("WFREL_PROCESS_IDENTITY", "runtime executable identity changed")
    return digest.hexdigest()


@dataclass(frozen=True)
class LaunchEnvironment:
    data_root: Path
    cdn_root: Path
    modes_root: Path
    native_binding: Path | None = None

    def __post_init__(self) -> None:
        roots = (
            _canonical_path(self.data_root, "data root"),
            _canonical_path(self.cdn_root, "CDN root"),
            _canonical_path(self.modes_root, "Modes root"),
        )
        if any(
            _paths_overlap(left, right)
            for index, left in enumerate(roots)
            for right in roots[index + 1:]
        ):
            raise _platform_error("launch roots must not overlap")
        for root, label in zip(roots, ("data root", "CDN root", "Modes root"), strict=True):
            _directory(root, label)
        if self.native_binding is not None:
            binding = _canonical_path(self.native_binding, "native binding")
            _regular_file(binding, "native binding")
            if binding.suffix.lower() not in {".node", ".so"}:
                raise _platform_error("native binding is unavailable")


def build_child_environment(
    launch: LaunchSpec,
    environment: LaunchEnvironment,
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build one child-only environment without mutating the parent mapping."""
    if not isinstance(launch, LaunchSpec) or not isinstance(environment, LaunchEnvironment):
        raise _platform_error("launch configuration is invalid")
    source = os.environ if base is None else base
    if not isinstance(source, Mapping) or any(
        not isinstance(key, str) or not isinstance(value, str)
        for key, value in source.items()
    ):
        raise _platform_error("parent environment is invalid")
    child = dict(source)
    for name in (*_FORBIDDEN_ENVIRONMENT, "BETTER_SQLITE3_NATIVE_BINDING"):
        child.pop(name, None)
    try:
        runtime_root = launch.executable.parents[2]
    except IndexError:
        raise _platform_error("runtime executable layout is invalid") from None
    node_path = runtime_root / "node_modules"
    _directory(node_path, "runtime node_modules")
    child.update({
        "EMBEDDED_RUNTIME": "1",
        "ASSET_MODE": "local",
        "DATA_DIR": os.fspath(environment.data_root),
        "CDN_DIR": os.fspath(environment.cdn_root),
        "MODES_DIR": os.fspath(environment.modes_root),
        "NODE_PATH": os.fspath(node_path),
    })
    if environment.native_binding is not None:
        child["BETTER_SQLITE3_NATIVE_BINDING"] = os.fspath(environment.native_binding)
    return child


@dataclass(frozen=True)
class CaptureStats:
    stdout_bytes: int
    stderr_bytes: int
    stdout_truncated: bool
    stderr_truncated: bool


class PlatformAdapter(Protocol):
    def current_process(self) -> ManagedProcess | None: ...
    def stop_owned(self, process: ManagedProcess, timeout: float) -> bool: ...
    def prepare_content(self, launch: LaunchSpec, environment: LaunchEnvironment) -> None: ...
    def start_server(
        self, launch: LaunchSpec, environment: LaunchEnvironment, operation_id: str,
    ) -> ManagedProcess: ...
    def wait_exited(self, process: ManagedProcess, timeout: float) -> bool: ...


class _Drain:
    def __init__(self, stream: BinaryIO | None, limit: int) -> None:
        self._stream = stream
        self._limit = limit
        self._captured = 0
        self._truncated = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        if self._stream is None:
            return
        try:
            while chunk := self._stream.read(8192):
                with self._lock:
                    remaining = max(0, self._limit - self._captured)
                    self._captured += min(len(chunk), remaining)
                    self._truncated = self._truncated or len(chunk) > remaining
        except (OSError, ValueError):
            pass
        finally:
            try:
                self._stream.close()
            except (OSError, ValueError):
                pass

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout)

    def snapshot(self) -> tuple[int, bool]:
        with self._lock:
            return self._captured, self._truncated


class _Capture:
    def __init__(self, stdout: BinaryIO | None, stderr: BinaryIO | None, limit: int) -> None:
        self._stdout = _Drain(stdout, limit)
        self._stderr = _Drain(stderr, limit)

    def start(self) -> None:
        self._stdout.start()
        self._stderr.start()

    def finish(self) -> CaptureStats:
        self._stdout.join(1.0)
        self._stderr.join(1.0)
        stdout_bytes, stdout_truncated = self._stdout.snapshot()
        stderr_bytes, stderr_truncated = self._stderr.snapshot()
        return CaptureStats(stdout_bytes, stderr_bytes, stdout_truncated, stderr_truncated)


class _ProcessBackend(Protocol):
    def spawn(self, command: tuple[str, ...], cwd: Path, environment: dict[str, str]) -> object: ...
    def open_process(self, pid: int) -> object | None: ...
    def identity(self, handle: object) -> ProcessIdentity: ...
    def wait(self, handle: object, timeout: float) -> bool: ...
    def exit_code(self, handle: object) -> int: ...
    def send_ctrl_break(self, pid: int) -> None: ...
    def terminate(self, handle: object) -> None: ...
    def close(self, handle: object) -> None: ...


class WindowsPlatformAdapter:
    def __init__(
        self,
        state_root: Path,
        expected_executable: Path,
        *,
        backend: _ProcessBackend | None = None,
        base_environment: Mapping[str, str] | None = None,
        capture_limit: int = 64 * 1024,
        startup_grace_seconds: float = 0.1,
        prepare_timeout_seconds: float = 120.0,
    ) -> None:
        state_root = _canonical_path(state_root, "state root")
        _root_snapshot(state_root)
        self._state = ProcessStateStore(state_root)
        self._expected_executable = _canonical_path(expected_executable, "runtime executable")
        self._expected_sha256 = _sha256_file(self._expected_executable)
        if type(capture_limit) is not int or capture_limit <= 0 or capture_limit > 1024 * 1024:
            raise _platform_error("capture limit is invalid")
        self._capture_limit = capture_limit
        self._startup_grace = _validate_timeout(startup_grace_seconds, "startup grace")
        self._prepare_timeout = _validate_timeout(prepare_timeout_seconds, "prepare timeout")
        self._backend = _WindowsBackend() if backend is None else backend
        self._base_environment = dict(os.environ if base_environment is None else base_environment)
        self.last_capture_stats = CaptureStats(0, 0, False, False)
        self._captures: dict[int, _Capture] = {}

    def _finish_capture(self, pid: int) -> None:
        capture = self._captures.pop(pid, None)
        if capture is not None:
            self.last_capture_stats = capture.finish()

    def _validate_launch(self, launch: LaunchSpec) -> None:
        if not isinstance(launch, LaunchSpec):
            raise _platform_error("launch specification is invalid")
        for label, path in (
            ("runtime executable", launch.executable), ("prepare entry", launch.prepare_entry),
            ("server entry", launch.server_entry), ("working directory", launch.cwd),
        ):
            _canonical_path(path, label)
        _regular_file(launch.executable, "runtime executable")
        _regular_file(launch.prepare_entry, "prepare entry")
        _regular_file(launch.server_entry, "server entry")
        try:
            cwd_item = launch.cwd.lstat()
        except OSError:
            raise _platform_error("working directory is unavailable") from None
        if not stat.S_ISDIR(cwd_item.st_mode) or stat.S_ISLNK(cwd_item.st_mode):
            raise _platform_error("working directory is unavailable")
        if launch.executable != self._expected_executable:
            raise _process_error("WFREL_PROCESS_IDENTITY", "runtime executable does not match the target")
        try:
            launch.prepare_entry.relative_to(launch.cwd)
            launch.server_entry.relative_to(launch.cwd)
        except ValueError:
            raise _platform_error("server entries escape the server bundle") from None

    def _verify_handle(self, handle: object, process: ManagedProcess) -> None:
        try:
            identity = self._backend.identity(handle)
        except (OSError, ValueError, ReleaseError):
            raise _process_error("WFREL_PROCESS_IDENTITY", "managed process identity is unavailable") from None
        if (
            identity.creation_time != process.creation_time
            or identity.executable != self._expected_executable
            or _sha256_file(identity.executable) != process.executable_sha256
            or process.executable_sha256 != self._expected_sha256
        ):
            raise _process_error("WFREL_PROCESS_IDENTITY", "managed process identity changed")

    def _verify_started_handle(self, handle: object) -> ProcessIdentity:
        try:
            identity = self._backend.identity(handle)
        except (OSError, ValueError, ReleaseError):
            raise _process_error("WFREL_PROCESS_IDENTITY", "started process identity is unavailable") from None
        if identity.executable != self._expected_executable or _sha256_file(identity.executable) != self._expected_sha256:
            raise _process_error("WFREL_PROCESS_IDENTITY", "started process image does not match the target")
        return identity

    def current_process(self) -> ManagedProcess | None:
        process = self._state.read()
        if process is None:
            return None
        try:
            handle = self._backend.open_process(process.pid)
        except OSError:
            raise _process_error("WFREL_PROCESS_IDENTITY", "managed process identity is unavailable") from None
        if handle is None:
            self._state.clear(process)
            self._finish_capture(process.pid)
            return None
        try:
            self._verify_handle(handle, process)
            return process
        finally:
            self._backend.close(handle)

    def _spawn(self, command: tuple[str, ...], launch: LaunchSpec, environment: LaunchEnvironment) -> object:
        child_environment = build_child_environment(launch, environment, self._base_environment)
        try:
            spawned = self._backend.spawn(command, launch.cwd, child_environment)
        except (OSError, ValueError):
            raise _process_error("WFREL_PROCESS_START", "managed process could not be started") from None
        capture = _Capture(spawned.stdout, spawned.stderr, self._capture_limit)
        capture.start()
        self._captures[spawned.pid] = capture
        return spawned

    def prepare_content(self, launch: LaunchSpec, environment: LaunchEnvironment) -> None:
        self._validate_launch(launch)
        spawned = self._spawn(
            (os.fspath(launch.executable), os.fspath(launch.prepare_entry)), launch, environment,
        )
        try:
            if not self._backend.wait(spawned.handle, self._prepare_timeout):
                self._verify_started_handle(spawned.handle)
                self._backend.terminate(spawned.handle)
                self._backend.wait(spawned.handle, 5.0)
                raise _process_error("WFREL_PROCESS_TIMEOUT", "content preparation timed out")
            if self._backend.exit_code(spawned.handle) != 0:
                raise _process_error("WFREL_PROCESS_START", "content preparation failed")
        except ReleaseError:
            raise
        except (OSError, ValueError):
            raise _process_error("WFREL_PROCESS_START", "content preparation failed") from None
        finally:
            self.last_capture_stats = self._captures.pop(spawned.pid).finish()
            self._backend.close(spawned.handle)

    def start_server(
        self, launch: LaunchSpec, environment: LaunchEnvironment, operation_id: str,
    ) -> ManagedProcess:
        self._validate_launch(launch)
        validate_operation_id(operation_id)
        if self.current_process() is not None:
            raise _process_error("WFREL_PROCESS_RUNNING", "managed server is already running")
        spawned = self._spawn(
            (os.fspath(launch.executable), os.fspath(launch.server_entry)), launch, environment,
        )
        committed = False
        try:
            if self._backend.wait(spawned.handle, self._startup_grace):
                self._finish_capture(spawned.pid)
                raise _process_error("WFREL_PROCESS_START", "managed server exited during startup")
            identity = self._verify_started_handle(spawned.handle)
            process = ManagedProcess(
                spawned.pid, identity.creation_time, _sha256_file(identity.executable), operation_id,
            )
            if process.executable_sha256 != self._expected_sha256:
                raise _process_error("WFREL_PROCESS_IDENTITY", "started process image changed")
            self._state.write(process)
            committed = True
            return process
        except ReleaseError:
            if not committed:
                try:
                    if not self._backend.wait(spawned.handle, 0.0):
                        self._backend.terminate(spawned.handle)
                except OSError:
                    pass
            raise
        except (OSError, ValueError):
            try:
                if not self._backend.wait(spawned.handle, 0.0):
                    self._backend.terminate(spawned.handle)
            except OSError:
                pass
            raise _process_error("WFREL_PROCESS_START", "managed server could not be started") from None
        finally:
            if not committed:
                self._finish_capture(spawned.pid)
            self._backend.close(spawned.handle)

    def stop_owned(self, process: ManagedProcess, timeout: float) -> bool:
        timeout = _validate_timeout(timeout, "stop timeout")
        if not isinstance(process, ManagedProcess) or self._state.read() != process:
            raise _process_error("WFREL_PROCESS_IDENTITY", "process is not owned by this target")
        try:
            handle = self._backend.open_process(process.pid)
        except OSError:
            raise _process_error("WFREL_PROCESS_IDENTITY", "managed process identity is unavailable") from None
        if handle is None:
            self._state.clear(process)
            self._finish_capture(process.pid)
            return False
        forced = False
        try:
            self._verify_handle(handle, process)
            try:
                self._backend.send_ctrl_break(process.pid)
            except OSError:
                pass
            if not self._backend.wait(handle, timeout):
                self._verify_handle(handle, process)
                self._backend.terminate(handle)
                forced = True
                if not self._backend.wait(handle, 5.0):
                    raise _process_error("WFREL_PROCESS_TIMEOUT", "managed process did not exit")
            self._state.clear(process)
            self._finish_capture(process.pid)
            return forced
        except ReleaseError:
            raise
        except OSError:
            raise _process_error("WFREL_PROCESS_STOP", "managed process could not be stopped") from None
        finally:
            self._backend.close(handle)

    def wait_exited(self, process: ManagedProcess, timeout: float) -> bool:
        timeout = _validate_timeout(timeout, "wait timeout")
        if not isinstance(process, ManagedProcess) or self._state.read() != process:
            raise _process_error("WFREL_PROCESS_IDENTITY", "process is not owned by this target")
        try:
            handle = self._backend.open_process(process.pid)
        except OSError:
            raise _process_error("WFREL_PROCESS_IDENTITY", "managed process identity is unavailable") from None
        if handle is None:
            self._state.clear(process)
            self._finish_capture(process.pid)
            return True
        try:
            self._verify_handle(handle, process)
            exited = self._backend.wait(handle, timeout)
            if exited:
                self._state.clear(process)
                self._finish_capture(process.pid)
            return exited
        finally:
            self._backend.close(handle)
