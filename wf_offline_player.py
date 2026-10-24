#!/usr/bin/env python3
"""Apply the minimal initial-character overlay to a staged common store."""
from __future__ import annotations

import contextlib
import hashlib
import os
import secrets
import stat
import zlib
from dataclasses import dataclass
from pathlib import Path

import wf_mod_tool as core
import wf_offline_store as store


PLAYER_LOGICAL_PATH = "master/player/player_character.orderedmap"
PLAYER_RELATIVE_PATH = Path("51") / "b73a9401c1fae38366ee79f4274942254d389c"
PLAYER_ID = "1000"
INITIAL_CHARACTER_IDS = ("129999", "139999", "149999")
CHARACTER_LEVEL = "1"
TEMP_SUFFIX = ".wf-offline-new"


class PlayerOverlayError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PlayerOverlayReport:
    logical_path: str
    relative_path: str
    before_sha256: str
    after_sha256: str
    before_character_ids: tuple[str, ...]
    after_character_ids: tuple[str, ...]
    added_character_ids: tuple[str, ...]
    character_level: int


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _open_existing_at(
    parent_descriptor: int, name: str, *, nofollow_flag: int
) -> int:
    if name in ("", ".", "..") or Path(name).name != name:
        raise PlayerOverlayError(f"unsafe relative player filename: {name}")
    flags = os.O_RDONLY | nofollow_flag | getattr(os, "O_BINARY", 0)
    return os.open(name, flags, dir_fd=parent_descriptor)


def _replace_relative(parent_descriptor: int, source: str, target: str) -> None:
    os.replace(
        source,
        target,
        src_dir_fd=parent_descriptor,
        dst_dir_fd=parent_descriptor,
    )


def _file_identity(metadata: object) -> tuple[int, ...]:
    return store._opened_file_identity(metadata)


def _ownership_identity(metadata: object) -> tuple[int, int, int]:
    """Stable ownership fields; content mutations must not change this tuple."""
    return (
        int(getattr(metadata, "st_dev", 0)),
        int(getattr(metadata, "st_ino", 0)),
        stat.S_IFMT(int(getattr(metadata, "st_mode"))),
    )


def _require_regular(metadata: object, *, kind: str, path: Path) -> None:
    if store._is_reparse(metadata):
        raise PlayerOverlayError(f"reparse point is forbidden for {kind}: {path}")
    if not stat.S_ISREG(int(getattr(metadata, "st_mode"))):
        raise PlayerOverlayError(f"{kind} is not a regular file: {path}")


def _relative_lstat(parent_descriptor: int | None, path: Path, *, kind: str) -> object:
    try:
        if parent_descriptor is None:
            metadata = path.lstat()
        else:
            metadata = os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False)
    except OSError as error:
        raise PlayerOverlayError(f"cannot inspect {kind}: {path}: {error}") from error
    _require_regular(metadata, kind=kind, path=path)
    return metadata


def _check_windows_final_path(descriptor: int, path: Path, *, kind: str) -> None:
    final_path = store._windows_final_path(descriptor)
    if final_path is not None and os.path.normcase(os.fspath(final_path)) != os.path.normcase(
        os.fspath(store._absolute(path))
    ):
        raise PlayerOverlayError(
            f"opened {kind} final path mismatch: expected={path} actual={final_path}"
        )


def _open_bound_file(
    parent_descriptor: int | None,
    path: Path,
    expected_identity: tuple[int, ...],
    *,
    kind: str,
) -> int:
    named = _relative_lstat(parent_descriptor, path, kind=kind)
    if _file_identity(named) != expected_identity:
        raise PlayerOverlayError(f"{kind} identity changed before open: {path}")
    try:
        if parent_descriptor is None:
            descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        else:
            descriptor = _open_existing_at(
                parent_descriptor, path.name, nofollow_flag=os.O_NOFOLLOW
            )
    except OSError as error:
        raise PlayerOverlayError(f"cannot open {kind}: {path}: {error}") from error
    try:
        opened = os.fstat(descriptor)
        _require_regular(opened, kind=f"opened {kind}", path=path)
        if _file_identity(opened) != expected_identity:
            raise PlayerOverlayError(f"{kind} identity changed while opening: {path}")
        _check_windows_final_path(descriptor, path, kind=kind)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _read_bound_file(
    parent_descriptor: int | None,
    path: Path,
    expected_identity: tuple[int, ...],
    *,
    kind: str,
) -> bytes:
    if os.name == "nt" and parent_descriptor is None:
        return _read_windows_bound_file(path, expected_identity, kind=kind)
    descriptor = _open_bound_file(
        parent_descriptor, path, expected_identity, kind=kind
    )
    try:
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read()
        if _file_identity(os.fstat(descriptor)) != expected_identity:
            raise PlayerOverlayError(f"{kind} identity changed while reading: {path}")
        return raw
    finally:
        os.close(descriptor)


@contextlib.contextmanager
def _posix_transaction_guard(parent: Path, expected_signature: tuple[int, ...]):
    before = store._require_same_lstat(parent, expected_signature, kind="target parent")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        descriptor = os.open(parent, flags)
    except OSError as error:
        raise PlayerOverlayError(f"cannot open guarded target parent: {parent}: {error}") from error
    try:
        opened = os.fstat(descriptor)
        if store._is_reparse(opened):
            raise PlayerOverlayError(f"reparse point is forbidden for target parent: {parent}")
        if not stat.S_ISDIR(int(getattr(opened, "st_mode"))):
            raise PlayerOverlayError(f"opened target parent is not a directory: {parent}")
        if store._directory_identity(opened) != store._directory_identity(before):
            raise PlayerOverlayError(f"target parent changed while opening directory fd: {parent}")
        parent_mode = int(getattr(opened, "st_mode"))
        shared_writable = parent_mode & (stat.S_IWGRP | stat.S_IWOTH)
        if shared_writable and not parent_mode & stat.S_ISVTX:
            raise PlayerOverlayError(
                f"unsafe non-sticky shared-writable target parent: {parent}"
            )
        yield descriptor
    finally:
        with contextlib.suppress(OSError):
            os.close(descriptor)


@contextlib.contextmanager
def _windows_transaction_guard(parent: Path, expected_signature: tuple[int, ...]):
    import ctypes

    class FileIdInfo(ctypes.Structure):
        _fields_ = [
            ("volume_serial", ctypes.c_uint64),
            ("file_id", ctypes.c_ubyte * 16),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
    ]
    create_file.restype = ctypes.c_void_p
    handle = create_file(
        os.fspath(parent),
        0x0001 | 0x0080,
        0x0001 | 0x0002,
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        raise PlayerOverlayError(
            f"cannot open guarded Windows target parent: {parent}: "
            f"WinError {ctypes.get_last_error()}"
        )
    try:
        info = FileIdInfo()
        get_info = kernel32.GetFileInformationByHandleEx
        get_info.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        get_info.restype = ctypes.c_int
        if not get_info(ctypes.c_void_p(handle), 18, ctypes.byref(info), ctypes.sizeof(info)):
            raise PlayerOverlayError(
                f"cannot inspect guarded Windows target parent: {parent}: "
                f"WinError {ctypes.get_last_error()}"
            )
        opened_identity = store._file_id_stat_identity(
            int(info.volume_serial), int.from_bytes(bytes(info.file_id), "little")
        )
        if opened_identity != (expected_signature[0], expected_signature[1]):
            raise PlayerOverlayError(f"target parent changed while opening Windows handle: {parent}")
        final_path = store._windows_final_path_from_handle(handle)
        if os.path.normcase(os.fspath(final_path)) != os.path.normcase(
            os.fspath(store._absolute(parent))
        ):
            raise PlayerOverlayError(
                f"opened target parent final path mismatch: expected={parent} actual={final_path}"
            )
        store._require_same_lstat(parent, expected_signature, kind="target parent")
        yield None
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(handle))


def _windows_kernel32():
    import ctypes

    return ctypes.WinDLL("kernel32", use_last_error=True)


def _windows_file_id(handle: int) -> tuple[int, int]:
    import ctypes

    class FileIdInfo(ctypes.Structure):
        _fields_ = [
            ("volume_serial", ctypes.c_uint64),
            ("file_id", ctypes.c_ubyte * 16),
        ]

    kernel32 = _windows_kernel32()
    function = kernel32.GetFileInformationByHandleEx
    function.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    function.restype = ctypes.c_int
    info = FileIdInfo()
    if not function(
        ctypes.c_void_p(handle), 18, ctypes.byref(info), ctypes.sizeof(info)
    ):
        raise OSError(
            ctypes.get_last_error(),
            f"cannot inspect owned temporary FileId: WinError {ctypes.get_last_error()}",
        )
    return store._file_id_stat_identity(
        int(info.volume_serial), int.from_bytes(bytes(info.file_id), "little")
    )


def _close_windows_handle(handle: int | None, *, strict: bool = False) -> None:
    if handle is None:
        return
    import ctypes

    kernel32 = _windows_kernel32()
    if not kernel32.CloseHandle(ctypes.c_void_p(handle)) and strict:
        error = ctypes.get_last_error()
        raise OSError(error, f"CloseHandle failed: WinError {error}")


def _duplicate_windows_handle(handle: int) -> int:
    import ctypes

    kernel32 = _windows_kernel32()
    current_process = kernel32.GetCurrentProcess()
    duplicated = ctypes.c_void_p()
    function = kernel32.DuplicateHandle
    function.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_uint32,
        ctypes.c_int,
        ctypes.c_uint32,
    ]
    function.restype = ctypes.c_int
    if not function(
        ctypes.c_void_p(current_process),
        ctypes.c_void_p(handle),
        ctypes.c_void_p(current_process),
        ctypes.byref(duplicated),
        0,
        False,
        0x2,
    ):
        raise OSError(
            ctypes.get_last_error(),
            f"cannot duplicate owned temporary handle: WinError {ctypes.get_last_error()}",
        )
    return int(duplicated.value)


def _open_windows_owned_handle(path: Path) -> int:
    import ctypes

    kernel32 = _windows_kernel32()
    function = kernel32.CreateFileW
    function.argtypes = [
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
    ]
    function.restype = ctypes.c_void_p
    handle = function(
        os.fspath(path),
        0x80000000 | 0x40000000 | 0x00010000,
        0x0001 | 0x0002 | 0x0004,
        None,
        1,
        0x00200000,
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        raise OSError(
            ctypes.get_last_error(),
            f"cannot exclusively create temporary output: {path}: "
            f"WinError {ctypes.get_last_error()}",
        )
    return int(handle)


def _open_windows_existing_handle(path: Path, *, kind: str) -> int:
    import ctypes

    kernel32 = _windows_kernel32()
    function = kernel32.CreateFileW
    function.argtypes = [
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
    ]
    function.restype = ctypes.c_void_p
    handle = function(
        os.fspath(path),
        0x80000000,
        0x0001 | 0x0002 | 0x0004,
        None,
        3,
        0x00200000,
        None,
    )
    if handle == ctypes.c_void_p(-1).value:
        raise PlayerOverlayError(
            f"cannot open {kind}: {path}: WinError {ctypes.get_last_error()}"
        )
    return int(handle)


def _read_windows_bound_file(
    path: Path, expected_identity: tuple[int, ...], *, kind: str
) -> bytes:
    handle = _open_windows_existing_handle(path, kind=kind)
    descriptor: int | None = None
    duplicated_handle: int | None = None
    try:
        final_path = store._windows_final_path_from_handle(handle)
        if os.path.normcase(os.fspath(final_path)) != os.path.normcase(
            os.fspath(store._absolute(path))
        ):
            raise PlayerOverlayError(
                f"opened {kind} final path mismatch: expected={path} actual={final_path}"
            )
        duplicated_handle = _duplicate_windows_handle(handle)
        import msvcrt

        descriptor = msvcrt.open_osfhandle(
            duplicated_handle, os.O_RDONLY | getattr(os, "O_BINARY", 0)
        )
        duplicated_handle = None
        metadata = os.fstat(descriptor)
        _require_regular(metadata, kind=kind, path=path)
        if _file_identity(metadata) != expected_identity:
            raise PlayerOverlayError(f"{kind} changed while opening: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read()
        after = os.fstat(descriptor)
        if _file_identity(after) != expected_identity:
            raise PlayerOverlayError(f"{kind} changed while reading: {path}")
        return raw
    finally:
        if descriptor is not None:
            with contextlib.suppress(OSError):
                os.close(descriptor)
        _close_windows_handle(duplicated_handle)
        _close_windows_handle(handle)


def _set_windows_handle_name(
    handle: int, target: Path, *, info_class: int, flags: int
) -> None:
    import ctypes

    class RenameInfo(ctypes.Structure):
        _fields_ = [
            ("flags", ctypes.c_uint32),
            ("root_directory", ctypes.c_void_p),
            ("file_name_length", ctypes.c_uint32),
            ("file_name", ctypes.c_wchar * 1),
        ]

    encoded = os.fspath(store._absolute(target)).encode("utf-16-le")
    # FILE_RENAME_INFO has trailing alignment after WCHAR FileName[1].  Windows
    # requires the supplied buffer to include sizeof(FILE_RENAME_INFO), not just
    # the field offset, or it can consume bytes beyond the intended name.
    total_size = ctypes.sizeof(RenameInfo) + len(encoded)
    buffer = ctypes.create_string_buffer(total_size)
    ctypes.c_uint32.from_buffer(buffer, RenameInfo.flags.offset).value = flags
    ctypes.c_void_p.from_buffer(buffer, RenameInfo.root_directory.offset).value = None
    ctypes.c_uint32.from_buffer(buffer, RenameInfo.file_name_length.offset).value = len(encoded)
    ctypes.memmove(
        ctypes.addressof(buffer) + RenameInfo.file_name.offset, encoded, len(encoded)
    )
    kernel32 = _windows_kernel32()
    function = kernel32.SetFileInformationByHandle
    function.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32
    ]
    function.restype = ctypes.c_int
    if not function(
        ctypes.c_void_p(handle), info_class, ctypes.byref(buffer), total_size
    ):
        error = ctypes.get_last_error()
        raise OSError(error, f"handle rename failed: WinError {error}")


def _commit_windows_handle(handle: int, target: Path) -> None:
    try:
        _set_windows_handle_name(handle, target, info_class=22, flags=0x1 | 0x2)
    except OSError as error:
        error_code = getattr(error, "winerror", None) or error.errno
        if error_code not in (1, 50, 87, 123):
            raise
        _set_windows_handle_name(handle, target, info_class=3, flags=0x1)


def _dispose_windows_handle(handle: int) -> None:
    import ctypes

    kernel32 = _windows_kernel32()
    function = kernel32.SetFileInformationByHandle
    function.argtypes = [
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32
    ]
    function.restype = ctypes.c_int
    flags = ctypes.c_uint32(0x1 | 0x2 | 0x10)
    if function(
        ctypes.c_void_p(handle), 21, ctypes.byref(flags), ctypes.sizeof(flags)
    ):
        return
    first_error = ctypes.get_last_error()
    delete = ctypes.c_ubyte(1)
    if function(
        ctypes.c_void_p(handle), 4, ctypes.byref(delete), ctypes.sizeof(delete)
    ):
        return
    error = ctypes.get_last_error()
    raise OSError(
        error,
        f"handle cleanup failed: WinError {error} (FileDispositionInfoEx={first_error})",
    )


class _WindowsOwnedTemp:
    def __init__(self, path: Path, handle: int) -> None:
        self.path = path
        self.handle: int | None = handle
        self.file_id = _windows_file_id(handle)
        self.identity: tuple[int, ...] | None = None
        self.writer_descriptor: int | None = None

    @classmethod
    def create(cls, path: Path) -> "_WindowsOwnedTemp":
        handle = _open_windows_owned_handle(path)
        try:
            final_path = store._windows_final_path_from_handle(handle)
            if os.path.normcase(os.fspath(final_path)) != os.path.normcase(
                os.fspath(store._absolute(path))
            ):
                raise PlayerOverlayError(
                    f"owned temporary final path mismatch: expected={path} actual={final_path}"
                )
            return cls(path, handle)
        except BaseException as primary:
            cleanup_errors: list[BaseException] = []
            try:
                _dispose_windows_handle(handle)
            except BaseException as error:
                cleanup_errors.append(error)
            try:
                _close_windows_handle(handle, strict=True)
            except BaseException as error:
                cleanup_errors.append(error)
            if cleanup_errors:
                raise PlayerOverlayError(
                    f"{primary}; cleanup failed: "
                    + "; ".join(str(error) for error in cleanup_errors)
                ) from primary
            raise

    def _new_descriptor(self) -> int:
        import msvcrt

        if self.handle is None:
            raise PlayerOverlayError("owned temporary handle is closed")
        duplicated = _duplicate_windows_handle(self.handle)
        try:
            return msvcrt.open_osfhandle(
                duplicated, os.O_RDWR | getattr(os, "O_BINARY", 0)
            )
        except BaseException:
            _close_windows_handle(duplicated)
            raise

    def write(self, output: bytes) -> tuple[int, ...]:
        descriptor = self._new_descriptor()
        self.writer_descriptor = descriptor
        stream = None
        try:
            # The owner object, not the buffered stream, owns the CRT fd.  This
            # keeps success and every exception path on one os.close call.
            stream = os.fdopen(descriptor, "w+b", closefd=False)
            stream.write(output)
            stream.flush()
            os.fsync(stream.fileno())
            metadata = os.fstat(stream.fileno())
            _require_regular(metadata, kind="owned temporary output", path=self.path)
            if (int(getattr(metadata, "st_dev")), int(getattr(metadata, "st_ino"))) != self.file_id:
                raise PlayerOverlayError("owned temporary FileId changed while writing")
            self.identity = _file_identity(metadata)
            stream.close()
            return self.identity
        finally:
            if stream is not None and not getattr(stream, "closed", False):
                with contextlib.suppress(BaseException):
                    stream.close()
            if self.writer_descriptor is not None:
                try:
                    os.close(self.writer_descriptor)
                finally:
                    self.writer_descriptor = None

    def read_exact(self) -> bytes:
        descriptor = self._new_descriptor()
        try:
            os.lseek(descriptor, 0, os.SEEK_SET)
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                raw = stream.read()
            metadata = os.fstat(descriptor)
            if self.identity is None or _file_identity(metadata) != self.identity:
                raise PlayerOverlayError("owned temporary identity changed while reading")
            return raw
        finally:
            with contextlib.suppress(OSError):
                os.close(descriptor)

    def abort(self) -> BaseException | None:
        if self.handle is None:
            return None
        cleanup_errors: list[BaseException] = []
        try:
            _dispose_windows_handle(self.handle)
        except BaseException as error:
            cleanup_errors.append(error)
        if self.writer_descriptor is not None:
            try:
                os.close(self.writer_descriptor)
            except OSError as error:
                cleanup_errors.append(error)
            self.writer_descriptor = None
        try:
            _close_windows_handle(self.handle, strict=True)
        except BaseException as error:
            cleanup_errors.append(error)
        self.handle = None
        if cleanup_errors:
            return OSError("; ".join(str(error) for error in cleanup_errors))
        return None

    def finish_success(self) -> None:
        if self.writer_descriptor is not None:
            with contextlib.suppress(OSError):
                os.close(self.writer_descriptor)
            self.writer_descriptor = None
        _close_windows_handle(self.handle)
        self.handle = None


def _rmdir_owned_posix_transaction(
    parent_descriptor: int,
    directory_name: str,
    expected_ownership: tuple[int, int, int],
) -> bool:
    """Remove only a still-named owned txn dir; False means a new owner."""
    try:
        named = os.stat(
            directory_name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return True
    if (
        store._is_reparse(named)
        or not stat.S_ISDIR(int(getattr(named, "st_mode")))
        or _ownership_identity(named) != expected_ownership
    ):
        return False
    # Portable POSIX has no rmdir-by-fd.  The parent permission gate blocks
    # unprivileged non-owner replacement in the accepted mode cases; same-uid,
    # sticky-parent-owner, and privileged processes retain this narrow race.
    os.rmdir(directory_name, dir_fd=parent_descriptor)
    return True


class _PosixOwnedTemp:
    """Owned temp under a caller-created 0700 directory.

    POSIX has no portable replace-by-file-descriptor primitive.  Keeping the
    payload beneath a random private directory and using only held dirfds makes
    pathname commit/cleanup safe from unprivileged group/other writers when the
    parent is not shared-writable.  A sticky shared-writable parent is also
    accepted because POSIX prevents users who own neither the txn nor the sticky
    parent from renaming it.  This does not claim protection against a hostile
    same-uid process, the sticky parent owner, or a privileged process.  Those
    actors retain an unavoidable identity-check-to-rmdir window because POSIX
    has no portable rmdir-by-open-file-descriptor primitive.
    """

    PAYLOAD_NAME = "payload"

    def __init__(
        self,
        parent_descriptor: int,
        directory_name: str,
        directory_descriptor: int,
        descriptor: int,
        directory_ownership_identity: tuple[int, int, int],
    ) -> None:
        self.parent_descriptor = parent_descriptor
        self.directory_name = directory_name
        self.directory_descriptor: int | None = directory_descriptor
        self.descriptor: int | None = descriptor
        self.directory_ownership_identity = directory_ownership_identity
        initial = os.fstat(descriptor)
        self.ownership_identity = _ownership_identity(initial)
        self.content_identity: tuple[int, ...] | None = None

    @classmethod
    def create(cls, parent_descriptor: int) -> "_PosixOwnedTemp":
        directory_name = ""
        directory_descriptor: int | None = None
        descriptor: int | None = None
        directory_ownership_identity: tuple[int, int, int] | None = None
        for _ in range(32):
            candidate = f".wf-offline-txn-{secrets.token_hex(16)}"
            try:
                os.mkdir(candidate, 0o700, dir_fd=parent_descriptor)
            except FileExistsError:
                continue
            directory_name = candidate
            break
        if not directory_name:
            raise PlayerOverlayError("cannot allocate private overlay transaction directory")
        try:
            directory_descriptor = os.open(
                directory_name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                dir_fd=parent_descriptor,
            )
            directory_metadata = os.fstat(directory_descriptor)
            if not stat.S_ISDIR(int(getattr(directory_metadata, "st_mode"))):
                raise PlayerOverlayError("private overlay transaction path is not a directory")
            if stat.S_IMODE(int(getattr(directory_metadata, "st_mode"))) != 0o700:
                raise PlayerOverlayError("private overlay transaction directory is not mode 0700")
            directory_ownership_identity = _ownership_identity(directory_metadata)
            descriptor = store._open_exclusive_at(
                directory_descriptor,
                cls.PAYLOAD_NAME,
                nofollow_flag=os.O_NOFOLLOW,
            )
            payload_metadata = os.fstat(descriptor)
            _require_regular(
                payload_metadata,
                kind="owned POSIX temporary output",
                path=Path(directory_name) / cls.PAYLOAD_NAME,
            )
            return cls(
                parent_descriptor,
                directory_name,
                directory_descriptor,
                descriptor,
                directory_ownership_identity,
            )
        except BaseException as primary:
            cleanup_errors: list[BaseException] = []
            if descriptor is not None:
                try:
                    os.close(descriptor)
                except OSError as error:
                    cleanup_errors.append(error)
            if directory_descriptor is not None:
                try:
                    os.unlink(cls.PAYLOAD_NAME, dir_fd=directory_descriptor)
                except FileNotFoundError:
                    pass
                except OSError as error:
                    cleanup_errors.append(error)
                try:
                    os.close(directory_descriptor)
                except OSError as error:
                    cleanup_errors.append(error)
            if directory_ownership_identity is None:
                cleanup_errors.append(
                    PlayerOverlayError(
                        "cannot verify private transaction directory ownership for cleanup"
                    )
                )
            else:
                try:
                    if not _rmdir_owned_posix_transaction(
                        parent_descriptor,
                        directory_name,
                        directory_ownership_identity,
                    ):
                        cleanup_errors.append(
                            PlayerOverlayError(
                                "private transaction directory ownership changed during cleanup"
                            )
                        )
                except OSError as error:
                    cleanup_errors.append(error)
            if cleanup_errors:
                raise PlayerOverlayError(
                    f"{primary}; cleanup failed: "
                    + "; ".join(str(error) for error in cleanup_errors)
                ) from primary
            raise

    def write(self, output: bytes) -> tuple[int, ...]:
        if self.descriptor is None:
            raise PlayerOverlayError("owned POSIX temporary descriptor is closed")
        before = os.fstat(self.descriptor)
        _require_regular(
            before,
            kind="owned POSIX temporary output before write",
            path=Path(self.directory_name) / self.PAYLOAD_NAME,
        )
        if _ownership_identity(before) != self.ownership_identity:
            raise PlayerOverlayError("owned POSIX temporary owner changed before writing")
        stream = os.fdopen(self.descriptor, "w+b", closefd=False)
        stream.write(output)
        stream.flush()
        os.fsync(stream.fileno())
        metadata = os.fstat(stream.fileno())
        _require_regular(
            metadata,
            kind="written POSIX temporary output",
            path=Path(self.directory_name) / self.PAYLOAD_NAME,
        )
        if _ownership_identity(metadata) != self.ownership_identity:
            raise PlayerOverlayError("owned POSIX temporary identity changed while writing")
        self.content_identity = _file_identity(metadata)
        stream.close()
        return self.content_identity

    def read_exact(self) -> bytes:
        if self.descriptor is None:
            raise PlayerOverlayError("owned POSIX temporary descriptor is closed")
        os.lseek(self.descriptor, 0, os.SEEK_SET)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(self.descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        final = os.fstat(self.descriptor)
        if _ownership_identity(final) != self.ownership_identity:
            raise PlayerOverlayError("owned POSIX temporary owner changed while reading")
        if self.content_identity is None or _file_identity(final) != self.content_identity:
            raise PlayerOverlayError("owned POSIX temporary identity changed while reading")
        return b"".join(chunks)

    def commit(self, target_name: str) -> None:
        if self.directory_descriptor is None:
            raise PlayerOverlayError("owned POSIX transaction directory is closed")
        os.replace(
            self.PAYLOAD_NAME,
            target_name,
            src_dir_fd=self.directory_descriptor,
            dst_dir_fd=self.parent_descriptor,
        )

    def abort(self) -> BaseException | None:
        errors: list[BaseException] = []
        if self.directory_descriptor is not None:
            try:
                named = os.stat(
                    self.PAYLOAD_NAME,
                    dir_fd=self.directory_descriptor,
                    follow_symlinks=False,
                )
                if (
                    not store._is_reparse(named)
                    and _ownership_identity(named) == self.ownership_identity
                ):
                    os.unlink(self.PAYLOAD_NAME, dir_fd=self.directory_descriptor)
            except FileNotFoundError:
                pass
            except BaseException as error:
                errors.append(error)
        if self.descriptor is not None:
            try:
                os.close(self.descriptor)
            except BaseException as error:
                errors.append(error)
            self.descriptor = None
        if self.directory_descriptor is not None:
            try:
                os.close(self.directory_descriptor)
            except BaseException as error:
                errors.append(error)
            self.directory_descriptor = None
        try:
            if not _rmdir_owned_posix_transaction(
                self.parent_descriptor,
                self.directory_name,
                self.directory_ownership_identity,
            ):
                errors.append(
                    PlayerOverlayError(
                        "private transaction directory ownership changed during cleanup"
                    )
                )
        except BaseException as error:
            errors.append(error)
        if errors:
            return OSError("; ".join(str(error) for error in errors))
        return None

    def finish_success(self) -> None:
        if self.descriptor is not None:
            with contextlib.suppress(OSError):
                os.close(self.descriptor)
            self.descriptor = None
        if self.directory_descriptor is not None:
            with contextlib.suppress(OSError):
                os.close(self.directory_descriptor)
            self.directory_descriptor = None
        with contextlib.suppress(OSError):
            _rmdir_owned_posix_transaction(
                self.parent_descriptor,
                self.directory_name,
                self.directory_ownership_identity,
            )


def _transaction_guard(parent: Path, expected_signature: tuple[int, ...]):
    if os.name == "nt":
        return _windows_transaction_guard(parent, expected_signature)
    return _posix_transaction_guard(parent, expected_signature)


def _decode_raw_value(raw: bytes, *, character_id: str) -> str:
    try:
        return zlib.decompress(raw).decode("utf-8") if raw else ""
    except (UnicodeDecodeError, zlib.error) as error:
        raise PlayerOverlayError(
            f"cannot decode character level for player {PLAYER_ID}, character {character_id}"
        ) from error


def _verify_overlay_bytes(
    before_outer: core.OrderedMap,
    before_inner: core.OrderedMap,
    output: bytes,
    added_character_ids: tuple[str, ...],
) -> core.OrderedMap:
    try:
        after_outer = core.read_orderedmap_raw_rows_from_bytes(output, PLAYER_LOGICAL_PATH)
    except (ValueError, OSError, zlib.error) as error:
        raise PlayerOverlayError(f"overlay output does not reparse: {error}") from error
    if after_outer.keys != before_outer.keys or len(after_outer.rows) != len(before_outer.rows):
        raise PlayerOverlayError("outer orderedmap key or row drift after overlay")
    player_index = before_outer.keys.index(PLAYER_ID)
    for index, (before_row, after_row) in enumerate(zip(before_outer.rows, after_outer.rows)):
        if index != player_index and before_row != after_row:
            raise PlayerOverlayError("unrelated player row drift after overlay")
    try:
        after_inner = core.read_orderedmap_raw_rows_from_bytes(
            after_outer.rows[player_index], f"{PLAYER_LOGICAL_PATH}#{PLAYER_ID}"
        )
    except (ValueError, OSError, zlib.error) as error:
        raise PlayerOverlayError(f"player 1000 output does not reparse: {error}") from error
    before_count = len(before_inner.keys)
    if after_inner.keys[:before_count] != before_inner.keys:
        raise PlayerOverlayError("before-row key order drift after overlay")
    if after_inner.rows[:before_count] != before_inner.rows:
        raise PlayerOverlayError("before-row byte drift after overlay")
    if tuple(after_inner.keys[before_count:]) != added_character_ids:
        raise PlayerOverlayError("unexpected appended character rows after overlay")
    for character_id in INITIAL_CHARACTER_IDS:
        positions = [
            index for index, key in enumerate(after_inner.keys) if key == character_id
        ]
        if len(positions) != 1 or _decode_raw_value(
            after_inner.rows[positions[0]], character_id=character_id
        ) != CHARACTER_LEVEL:
            raise PlayerOverlayError("overlay output has an invalid initial character level")
    return after_inner


def _prepare_initial_characters(
    raw: bytes,
) -> tuple[bytes, PlayerOverlayReport, core.OrderedMap, core.OrderedMap]:
    try:
        outer = core.read_orderedmap_raw_rows_from_bytes(raw, PLAYER_LOGICAL_PATH)
    except (ValueError, OSError, zlib.error) as error:
        raise PlayerOverlayError(f"cannot parse {PLAYER_LOGICAL_PATH}: {error}") from error
    player_positions = [index for index, key in enumerate(outer.keys) if key == PLAYER_ID]
    if len(player_positions) != 1:
        raise PlayerOverlayError("player 1000 must exist exactly once")
    player_index = player_positions[0]
    try:
        before_inner = core.read_orderedmap_raw_rows_from_bytes(
            outer.rows[player_index], f"{PLAYER_LOGICAL_PATH}#{PLAYER_ID}"
        )
    except (ValueError, OSError, zlib.error) as error:
        raise PlayerOverlayError(f"cannot parse player 1000 character rows: {error}") from error

    added: list[str] = []
    for character_id in INITIAL_CHARACTER_IDS:
        positions = [
            index for index, key in enumerate(before_inner.keys) if key == character_id
        ]
        if len(positions) > 1:
            raise PlayerOverlayError(
                f"conflicting character level for player 1000 character {character_id}"
            )
        if positions:
            value = _decode_raw_value(
                before_inner.rows[positions[0]], character_id=character_id
            )
            if value != CHARACTER_LEVEL:
                raise PlayerOverlayError(
                    f"conflicting character level for player 1000 character {character_id}: {value!r}"
                )
        else:
            added.append(character_id)

    added_ids = tuple(added)
    if added_ids:
        after_inner_raw = core.build_orderedmap_raw_rows(
            core.OrderedMap(
                before_inner.logical_path,
                [*before_inner.keys, *added_ids],
                [
                    *before_inner.rows,
                    *(zlib.compress(CHARACTER_LEVEL.encode("utf-8")) for _ in added_ids),
                ],
                Path("[memory-bytes]"),
            )
        )
        outer_rows = list(outer.rows)
        outer_rows[player_index] = after_inner_raw
        output = core.build_orderedmap_raw_rows(
            core.OrderedMap(
                outer.logical_path,
                list(outer.keys),
                outer_rows,
                Path("[memory-bytes]"),
            )
        )
    else:
        output = raw

    after_inner = _verify_overlay_bytes(outer, before_inner, output, added_ids)
    report = PlayerOverlayReport(
        logical_path=PLAYER_LOGICAL_PATH,
        relative_path=PLAYER_RELATIVE_PATH.as_posix(),
        before_sha256=_sha256(raw),
        after_sha256=_sha256(output),
        before_character_ids=tuple(before_inner.keys),
        after_character_ids=tuple(after_inner.keys),
        added_character_ids=added_ids,
        character_level=int(CHARACTER_LEVEL),
    )
    return output, report, outer, before_inner


def add_initial_characters_to_bytes(raw: bytes) -> tuple[bytes, PlayerOverlayReport]:
    """Append absent initial characters to Player 1000 without re-encoding old rows."""
    output, report, _, _ = _prepare_initial_characters(raw)
    return output, report


def _apply_windows_owned_temp(
    temporary: Path,
    target: Path,
    target_identity: tuple[int, ...],
    before: bytes,
    output: bytes,
    report: PlayerOverlayReport,
    before_outer: core.OrderedMap,
    before_inner: core.OrderedMap,
) -> PlayerOverlayReport:
    owned: _WindowsOwnedTemp | None = None
    committed = False
    try:
        owned = _WindowsOwnedTemp.create(temporary)
        owned_identity = owned.write(output)

        handle_bytes = owned.read_exact()
        if handle_bytes != output or _sha256(handle_bytes) != report.after_sha256:
            raise PlayerOverlayError(
                "owned temporary output differs from prepared overlay"
            )
        _verify_overlay_bytes(
            before_outer,
            before_inner,
            handle_bytes,
            report.added_character_ids,
        )

        # These name-bound reads are deliberately retained as pre-commit checks.
        # The commit below is nevertheless bound to owned.handle, so a name swap
        # after the last check cannot redirect the bytes that are committed.
        written = _read_bound_file(
            None, temporary, owned_identity, kind="temporary output"
        )
        if written != output or _sha256(written) != report.after_sha256:
            raise PlayerOverlayError(
                "temporary output differs from prepared overlay"
            )
        _verify_overlay_bytes(
            before_outer,
            before_inner,
            written,
            report.added_character_ids,
        )

        rebound_target = _read_bound_file(
            None, target, target_identity, kind="target"
        )
        if rebound_target != before or _sha256(rebound_target) != report.before_sha256:
            raise PlayerOverlayError("target content changed before atomic replace")
        rebound_temp = _read_bound_file(
            None, temporary, owned_identity, kind="temporary output"
        )
        if rebound_temp != output or _sha256(rebound_temp) != report.after_sha256:
            raise PlayerOverlayError(
                "temporary output content changed before atomic replace"
            )

        try:
            assert owned.handle is not None
            _commit_windows_handle(owned.handle, target)
        except OSError as error:
            raise PlayerOverlayError(f"atomic replace failed: {error}") from error
        committed = True
        owned.finish_success()
        return report
    except BaseException as primary:
        cleanup_error = owned.abort() if owned is not None else None
        if cleanup_error is not None:
            raise PlayerOverlayError(
                f"{primary}; cleanup failed: {cleanup_error}"
            ) from primary
        if isinstance(primary, PlayerOverlayError):
            raise
        raise PlayerOverlayError(
            f"cannot write staged player overlay: {primary}"
        ) from primary
    finally:
        # Closing the already-committed handle is bookkeeping, not a validation
        # phase; it must never turn a successful atomic commit into a failure.
        if committed and owned is not None:
            owned.finish_success()


def _apply_posix_owned_temp(
    parent_descriptor: int,
    target: Path,
    target_identity: tuple[int, ...],
    before: bytes,
    output: bytes,
    report: PlayerOverlayReport,
    before_outer: core.OrderedMap,
    before_inner: core.OrderedMap,
) -> PlayerOverlayReport:
    owned: _PosixOwnedTemp | None = None
    committed = False
    try:
        owned = _PosixOwnedTemp.create(parent_descriptor)
        owned.write(output)
        written = owned.read_exact()
        if written != output or _sha256(written) != report.after_sha256:
            raise PlayerOverlayError(
                "owned POSIX temporary output differs from prepared overlay"
            )
        _verify_overlay_bytes(
            before_outer,
            before_inner,
            written,
            report.added_character_ids,
        )
        rebound_target = _read_bound_file(
            parent_descriptor, target, target_identity, kind="target"
        )
        if rebound_target != before or _sha256(rebound_target) != report.before_sha256:
            raise PlayerOverlayError("target content changed before atomic replace")
        try:
            owned.commit(target.name)
        except OSError as error:
            raise PlayerOverlayError(f"atomic replace failed: {error}") from error
        committed = True
        owned.finish_success()
        return report
    except BaseException as primary:
        cleanup_error = owned.abort() if owned is not None else None
        if cleanup_error is not None:
            raise PlayerOverlayError(
                f"{primary}; cleanup failed: {cleanup_error}"
            ) from primary
        if isinstance(primary, PlayerOverlayError):
            raise
        raise PlayerOverlayError(
            f"cannot write staged player overlay: {primary}"
        ) from primary
    finally:
        if committed and owned is not None:
            owned.finish_success()


def apply_initial_player_overlay(staged_common_root: Path) -> PlayerOverlayReport:
    """Atomically replace only the staged player-character member."""
    staged_common_root = Path(os.path.abspath(os.fspath(staged_common_root)))
    target = staged_common_root / PLAYER_RELATIVE_PATH
    temporary = target.with_name(target.name + TEMP_SUFFIX)
    try:
        root_metadata = store._checked_lstat(
            staged_common_root, kind="staged common root"
        )
        if not stat.S_ISDIR(int(getattr(root_metadata, "st_mode"))):
            raise PlayerOverlayError(
                f"staged common root is not a directory: {staged_common_root}"
            )
        parent_metadata = store._checked_lstat(target.parent, kind="target parent")
        if not stat.S_ISDIR(int(getattr(parent_metadata, "st_mode"))):
            raise PlayerOverlayError(f"target parent is not a directory: {target.parent}")
        target_metadata = store._checked_lstat(target, kind="target")
        _require_regular(target_metadata, kind="target", path=target)
        try:
            store._checked_lstat(temporary, kind="temporary output")
        except FileNotFoundError:
            pass
        except store.StoreError as error:
            if isinstance(error.__cause__, FileNotFoundError):
                pass
            else:
                raise
        else:
            raise PlayerOverlayError(f"temporary output already exists: {temporary}")

        parent_signature = store._stat_signature(parent_metadata)
        target_identity = _file_identity(target_metadata)
        with _transaction_guard(target.parent, parent_signature) as parent_descriptor:
            before = _read_bound_file(
                parent_descriptor, target, target_identity, kind="target"
            )
            output, report, before_outer, before_inner = _prepare_initial_characters(before)
            if output == before:
                return report

            if parent_descriptor is None:
                return _apply_windows_owned_temp(
                    temporary,
                    target,
                    target_identity,
                    before,
                    output,
                    report,
                    before_outer,
                    before_inner,
                )
            return _apply_posix_owned_temp(
                parent_descriptor,
                target,
                target_identity,
                before,
                output,
                report,
                before_outer,
                before_inner,
            )
    except store.StoreError as error:
        raise PlayerOverlayError(str(error)) from error
    except OSError as error:
        raise PlayerOverlayError(f"cannot apply staged player overlay: {error}") from error
