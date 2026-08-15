"""Portable authority facade for receiver-relative no-follow I/O."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import stat

from .canonical import FileIdentity
from ._owned_receiver_windows import WINDOWS_API as _WIN_API
from ._path_io import native_path


class OwnedReceiverError(RuntimeError):
    pass


def _before_root_open(_root: Path) -> None:
    """Test seam immediately before binding the receiver root handle."""


def _leaf(name: str) -> str:
    if not name or name in {".", ".."} or "/" in name or "\\" in name or "\0" in name:
        raise OwnedReceiverError("receiver name is not one safe leaf")
    return name


def _parts(relative: str) -> tuple[str, ...]:
    parts = PurePosixPath(relative).parts
    if not parts or any(_leaf(part) != part for part in parts):
        raise OwnedReceiverError("receiver path is invalid")
    return parts


@dataclass
class _Entry:
    parent: "_Entry | None"
    name: str
    handle: int
    identity: tuple[int, ...]
    directory: bool
    created: bool
    closed: bool = False


class _Stream(io.RawIOBase):
    def __init__(self, owner: "OwnedReceiver", entry: _Entry) -> None:
        super().__init__()
        self.owner = owner
        self.entry = entry

    def writable(self) -> bool:
        return True

    def write(self, raw: bytes | bytearray) -> int:
        return self.owner._write(self.entry.handle, bytes(raw))

    def flush(self) -> None:
        if not self.closed:
            self.owner._flush(self.entry.handle)


class OwnedReceiver:
    """Keep receiver parents open and perform every child operation relative to them."""

    def __init__(
        self, root: Path, expected_identity: tuple[int, int] | None = None,
    ) -> None:
        self.root_path = Path(root)
        self.entries: dict[tuple[str, ...], _Entry] = {}
        self.committed = False
        self.closed = False
        _before_root_open(self.root_path)
        if os.name == "nt":
            assert _WIN_API is not None
            handle = _WIN_API.open_root(self.root_path)
        else:
            handle = os.open(
                self.root_path,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
        try:
            identity = self._identity(handle, directory=True)
            if expected_identity is not None:
                current = os.lstat(native_path(self.root_path))
                if (
                    current.st_dev, current.st_ino
                ) != expected_identity or (
                    os.name == "nt" and identity[1] != current.st_ino
                ) or (
                    os.name != "nt"
                    and (identity[0], identity[1]) != expected_identity
                ):
                    raise OwnedReceiverError("receiver root identity changed")
        except BaseException:
            self._close_handle(handle)
            raise
        self.root = _Entry(None, "", handle, identity, True, False)

    def __enter__(self) -> "OwnedReceiver":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close(success=exc_type is None and self.committed)

    def _identity(self, handle: int, *, directory: bool) -> tuple[int, ...]:
        if os.name == "nt":
            assert _WIN_API is not None
            return _WIN_API.identity(handle, directory=directory)
        item = os.fstat(handle)
        if bool(stat.S_ISDIR(item.st_mode)) != directory or stat.S_ISLNK(item.st_mode):
            raise OwnedReceiverError("receiver handle has the wrong type")
        return (item.st_dev, item.st_ino, item.st_mode, item.st_size, item.st_mtime_ns)

    def _open(self, parent: _Entry, name: str, *, directory: bool, create: bool) -> int:
        if os.name == "nt":
            assert _WIN_API is not None
            return _WIN_API.relative(
                parent.handle, name, directory=directory, create=create
            )
        flags = getattr(os, "O_NOFOLLOW", 0)
        if directory:
            if create:
                os.mkdir(name, mode=0o700, dir_fd=parent.handle)
            flags |= os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        else:
            flags |= os.O_RDWR if create else os.O_RDONLY
            if create:
                flags |= os.O_CREAT | os.O_EXCL
        return os.open(name, flags, 0o600, dir_fd=parent.handle)

    def _close_handle(self, handle: int) -> None:
        if os.name == "nt":
            assert _WIN_API is not None
            _WIN_API.close(handle)
        else:
            os.close(handle)

    def _discard_unregistered(
        self, parent: _Entry, name: str, handle: int, *, directory: bool,
    ) -> None:
        if os.name == "nt":
            assert _WIN_API is not None
            _WIN_API.dispose(handle)
            _WIN_API.close(handle)
            return
        self._close_handle(handle)
        if directory:
            os.rmdir(name, dir_fd=parent.handle)
        else:
            os.unlink(name, dir_fd=parent.handle)

    def _parent(self, parts: tuple[str, ...], *, create: bool) -> _Entry:
        current = self.root
        prefix: tuple[str, ...] = ()
        for name in parts:
            prefix += (name,)
            existing = self.entries.get(prefix)
            if existing is not None:
                current = existing
                continue
            handle = self._open(current, name, directory=True, create=create)
            try:
                identity = self._identity(handle, directory=True)
            except BaseException:
                if create:
                    self._discard_unregistered(
                        current, name, handle, directory=True
                    )
                else:
                    self._close_handle(handle)
                raise
            entry = _Entry(current, name, handle, identity, True, create)
            self.entries[prefix] = entry
            current = entry
        return current

    def create_file(self, relative: str, write, *, before_open=None) -> FileIdentity:
        parts = _parts(relative)
        parent = self._parent(parts[:-1], create=True)
        if before_open is not None:
            before_open()
        handle = self._open(parent, parts[-1], directory=False, create=True)
        try:
            identity = self._identity(handle, directory=False)
        except BaseException:
            self._discard_unregistered(
                parent, parts[-1], handle, directory=False
            )
            raise
        entry = _Entry(parent, parts[-1], handle, identity, False, True)
        self.entries[parts] = entry
        with _Stream(self, entry) as stream:
            write(stream)
        return self.file_identity(relative)

    def open_file(self, relative: str) -> _Entry:
        parts = _parts(relative)
        existing = self.entries.get(parts)
        if existing is not None:
            return existing
        parent = self._parent(parts[:-1], create=False)
        handle = self._open(parent, parts[-1], directory=False, create=False)
        try:
            identity = self._identity(handle, directory=False)
        except BaseException:
            self._close_handle(handle)
            raise
        entry = _Entry(parent, parts[-1], handle, identity, False, False)
        self.entries[parts] = entry
        return entry

    def file_identity(self, relative: str) -> FileIdentity:
        entry = self.open_file(relative)
        before = self._identity(entry.handle, directory=False)
        self._seek(entry.handle, 0, os.SEEK_SET)
        digest = hashlib.sha256()
        size = 0
        while chunk := self._read(entry.handle, 1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
        after = self._identity(entry.handle, directory=False)
        if before != after or size != after[3]:
            raise OwnedReceiverError("receiver file changed while it was read")
        entry.identity = after
        return FileIdentity(size, digest.hexdigest())

    def commit(self) -> None:
        self.committed = True

    def _seek(self, handle: int, offset: int, whence: int) -> int:
        if os.name == "nt":
            assert _WIN_API is not None
            return _WIN_API.seek(handle, offset, whence)
        return os.lseek(handle, offset, whence)

    def _read(self, handle: int, size: int) -> bytes:
        if os.name == "nt":
            assert _WIN_API is not None
            return _WIN_API.read(handle, size)
        return os.read(handle, size)

    def _write(self, handle: int, raw: bytes) -> int:
        if os.name == "nt":
            assert _WIN_API is not None
            return _WIN_API.write(handle, raw)
        return os.write(handle, raw)

    def _flush(self, handle: int) -> None:
        if os.name == "nt":
            assert _WIN_API is not None
            _WIN_API.flush(handle)
        else:
            os.fsync(handle)

    def _close(self, entry: _Entry) -> None:
        if not entry.closed:
            self._close_handle(entry.handle)
            entry.closed = True

    def _dispose_file(self, entry: _Entry) -> None:
        assert entry.parent is not None
        if os.name == "nt":
            assert _WIN_API is not None
            _WIN_API.identity(entry.handle, directory=False)
            _WIN_API.dispose(entry.handle)
            self._close(entry)
            return
        current = os.stat(
            entry.name, dir_fd=entry.parent.handle, follow_symlinks=False
        )
        opened = os.fstat(entry.handle)
        same_object = (
            current.st_dev, current.st_ino, stat.S_IFMT(current.st_mode)
        ) == (opened.st_dev, opened.st_ino, stat.S_IFMT(opened.st_mode))
        self._close(entry)
        if same_object:
            os.unlink(entry.name, dir_fd=entry.parent.handle)

    def close(self, *, success: bool) -> None:
        if self.closed:
            return
        failure: BaseException | None = None
        if not success:
            for entry in reversed(tuple(self.entries.values())):
                if entry.created and not entry.directory:
                    try:
                        self._dispose_file(entry)
                    except BaseException as error:
                        failure = failure or error
            for entry in reversed(tuple(self.entries.values())):
                if entry.created and entry.directory:
                    try:
                        if os.name == "nt":
                            assert _WIN_API is not None
                            _WIN_API.dispose(entry.handle)
                        else:
                            assert entry.parent is not None
                            os.rmdir(entry.name, dir_fd=entry.parent.handle)
                        self._close(entry)
                    except BaseException as error:
                        failure = failure or error
        for entry in reversed(tuple(self.entries.values())):
            try:
                self._close(entry)
            except BaseException as error:
                failure = failure or error
        try:
            self._close(self.root)
        except BaseException as error:
            failure = failure or error
        self.closed = True
        if failure is not None:
            raise OwnedReceiverError("receiver authority cleanup failed") from failure


__all__ = ["OwnedReceiver", "OwnedReceiverError"]
