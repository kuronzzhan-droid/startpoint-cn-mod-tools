"""Minimal Win32 handle backend for receiver-relative no-follow I/O."""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from pathlib import Path

from ._path_io import native_path


class _UnicodeString(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", wintypes.LPWSTR),
    ]


class _ObjectAttributes(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.ULONG),
        ("RootDirectory", wintypes.HANDLE),
        ("ObjectName", ctypes.POINTER(_UnicodeString)),
        ("Attributes", wintypes.ULONG),
        ("SecurityDescriptor", wintypes.LPVOID),
        ("SecurityQualityOfService", wintypes.LPVOID),
    ]


class _IoStatusBlock(ctypes.Structure):
    _fields_ = [("Status", ctypes.c_void_p), ("Information", ctypes.c_void_p)]


class _ByHandleInfo(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


class _DispositionInfo(ctypes.Structure):
    _fields_ = [("DeleteFile", wintypes.BOOL)]


class WindowsReceiverApi:
    SHARE_READ = 0x1
    SHARE_WRITE = 0x2
    OPEN_EXISTING = 3
    ATTR_NORMAL = 0x80
    ATTR_DIRECTORY = 0x10
    ATTR_REPARSE = 0x400
    FLAG_BACKUP = 0x02000000
    FLAG_OPEN_REPARSE = 0x00200000
    LIST_DIRECTORY = 0x1
    READ_DATA = 0x1
    WRITE_DATA = 0x2
    ADD_FILE = 0x2
    ADD_SUBDIRECTORY = 0x4
    READ_ATTRIBUTES = 0x80
    WRITE_ATTRIBUTES = 0x100
    TRAVERSE = 0x20
    DELETE = 0x00010000
    SYNCHRONIZE = 0x00100000
    OBJ_CASE_INSENSITIVE = 0x40
    FILE_OPEN = 1
    FILE_CREATE = 2
    DIRECTORY_FILE = 0x1
    SYNC_NONALERT = 0x20
    NON_DIRECTORY_FILE = 0x40
    OPEN_FOR_BACKUP = 0x4000
    OPEN_REPARSE = 0x00200000
    DISPOSITION_INFO = 4

    def __init__(self) -> None:
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.ntdll = ctypes.WinDLL("ntdll")
        self.CreateFileW = self.kernel32.CreateFileW
        self.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        self.CreateFileW.restype = wintypes.HANDLE
        self.CloseHandle = self.kernel32.CloseHandle
        self.CloseHandle.argtypes = [wintypes.HANDLE]
        self.CloseHandle.restype = wintypes.BOOL
        self.GetFileInformationByHandle = self.kernel32.GetFileInformationByHandle
        self.GetFileInformationByHandle.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(_ByHandleInfo),
        ]
        self.GetFileInformationByHandle.restype = wintypes.BOOL
        self.SetFilePointerEx = self.kernel32.SetFilePointerEx
        self.SetFilePointerEx.argtypes = [
            wintypes.HANDLE, ctypes.c_longlong,
            ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD,
        ]
        self.SetFilePointerEx.restype = wintypes.BOOL
        self.ReadFile = self.kernel32.ReadFile
        self.ReadFile.argtypes = [
            wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
        ]
        self.ReadFile.restype = wintypes.BOOL
        self.WriteFile = self.kernel32.WriteFile
        self.WriteFile.argtypes = [
            wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
        ]
        self.WriteFile.restype = wintypes.BOOL
        self.FlushFileBuffers = self.kernel32.FlushFileBuffers
        self.FlushFileBuffers.argtypes = [wintypes.HANDLE]
        self.FlushFileBuffers.restype = wintypes.BOOL
        self.SetFileInformationByHandle = self.kernel32.SetFileInformationByHandle
        self.SetFileInformationByHandle.argtypes = [
            wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
        ]
        self.SetFileInformationByHandle.restype = wintypes.BOOL
        self.NtCreateFile = self.ntdll.NtCreateFile
        self.NtCreateFile.argtypes = [
            ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD,
            ctypes.POINTER(_ObjectAttributes), ctypes.POINTER(_IoStatusBlock),
            ctypes.c_void_p, wintypes.ULONG, wintypes.ULONG, wintypes.ULONG,
            wintypes.ULONG, ctypes.c_void_p, wintypes.ULONG,
        ]
        self.NtCreateFile.restype = ctypes.c_long
        self.RtlNtStatusToDosError = self.ntdll.RtlNtStatusToDosError
        self.RtlNtStatusToDosError.argtypes = [ctypes.c_long]
        self.RtlNtStatusToDosError.restype = wintypes.ULONG

    @staticmethod
    def _raise(label: str) -> None:
        code = ctypes.get_last_error()
        raise OSError(code, f"{label}: {ctypes.FormatError(code)}")

    def open_root(self, path: Path) -> int:
        access = (
            self.LIST_DIRECTORY | self.ADD_FILE | self.ADD_SUBDIRECTORY
            | self.READ_ATTRIBUTES | self.WRITE_ATTRIBUTES
            | self.TRAVERSE | self.SYNCHRONIZE
        )
        handle = self.CreateFileW(
            native_path(path), access, self.SHARE_READ | self.SHARE_WRITE,
            None, self.OPEN_EXISTING,
            self.FLAG_BACKUP | self.FLAG_OPEN_REPARSE, None,
        )
        value = ctypes.cast(handle, ctypes.c_void_p).value
        if value in (None, ctypes.c_void_p(-1).value):
            self._raise("CreateFileW")
        return int(value)

    def relative(
        self, parent: int, name: str, *, directory: bool, create: bool,
    ) -> int:
        if not name or name in {".", ".."} or "/" in name or "\\" in name or "\0" in name:
            raise OSError("receiver name is not one safe leaf")
        buffer = ctypes.create_unicode_buffer(name)
        length = len(name.encode("utf-16-le"))
        unicode_name = _UnicodeString(
            length, length + ctypes.sizeof(wintypes.WCHAR),
            ctypes.cast(buffer, wintypes.LPWSTR),
        )
        attributes = _ObjectAttributes(
            ctypes.sizeof(_ObjectAttributes), wintypes.HANDLE(parent),
            ctypes.pointer(unicode_name), self.OBJ_CASE_INSENSITIVE,
            None, None,
        )
        io_status = _IoStatusBlock()
        output = wintypes.HANDLE()
        if directory:
            access = (
                self.LIST_DIRECTORY | self.ADD_FILE | self.ADD_SUBDIRECTORY
                | self.READ_ATTRIBUTES | self.WRITE_ATTRIBUTES | self.TRAVERSE
                | self.SYNCHRONIZE | (self.DELETE if create else 0)
            )
            options = (
                self.DIRECTORY_FILE | self.SYNC_NONALERT
                | self.OPEN_FOR_BACKUP | self.OPEN_REPARSE
            )
            attrs = self.ATTR_DIRECTORY
            share = self.SHARE_READ | self.SHARE_WRITE
        else:
            access = self.READ_DATA | self.READ_ATTRIBUTES | self.SYNCHRONIZE
            if create:
                access |= self.WRITE_DATA | self.WRITE_ATTRIBUTES | self.DELETE
            options = self.NON_DIRECTORY_FILE | self.SYNC_NONALERT | self.OPEN_REPARSE
            attrs = self.ATTR_NORMAL
            share = self.SHARE_READ
        status = self.NtCreateFile(
            ctypes.byref(output), access, ctypes.byref(attributes),
            ctypes.byref(io_status), None, attrs, share,
            self.FILE_CREATE if create else self.FILE_OPEN,
            options, None, 0,
        )
        if status < 0:
            code = int(self.RtlNtStatusToDosError(status))
            raise OSError(code, f"NtCreateFile: {ctypes.FormatError(code)}")
        value = ctypes.cast(output, ctypes.c_void_p).value
        if value is None:
            raise OSError("NtCreateFile returned a null handle")
        return int(value)

    def identity(self, handle: int, *, directory: bool) -> tuple[int, ...]:
        info = _ByHandleInfo()
        if not self.GetFileInformationByHandle(
            wintypes.HANDLE(handle), ctypes.byref(info)
        ):
            self._raise("GetFileInformationByHandle")
        attrs = int(info.dwFileAttributes)
        if attrs & self.ATTR_REPARSE or bool(attrs & self.ATTR_DIRECTORY) != directory:
            raise OSError("receiver handle is reparse or has the wrong type")
        return (
            int(info.dwVolumeSerialNumber),
            (int(info.nFileIndexHigh) << 32) | int(info.nFileIndexLow),
            attrs,
            (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow),
            (int(info.ftLastWriteTime.dwHighDateTime) << 32)
            | int(info.ftLastWriteTime.dwLowDateTime),
        )

    def seek(self, handle: int, offset: int, whence: int) -> int:
        result = ctypes.c_longlong()
        if not self.SetFilePointerEx(
            wintypes.HANDLE(handle), offset, ctypes.byref(result), whence
        ):
            self._raise("SetFilePointerEx")
        return int(result.value)

    def read(self, handle: int, size: int) -> bytes:
        if size <= 0:
            return b""
        buffer = ctypes.create_string_buffer(size)
        amount = wintypes.DWORD()
        if not self.ReadFile(
            wintypes.HANDLE(handle), buffer, size, ctypes.byref(amount), None
        ):
            self._raise("ReadFile")
        return buffer.raw[:amount.value]

    def write(self, handle: int, raw: bytes) -> int:
        buffer = ctypes.create_string_buffer(raw)
        amount = wintypes.DWORD()
        if not self.WriteFile(
            wintypes.HANDLE(handle), buffer, len(raw), ctypes.byref(amount), None
        ):
            self._raise("WriteFile")
        return int(amount.value)

    def flush(self, handle: int) -> None:
        if not self.FlushFileBuffers(wintypes.HANDLE(handle)):
            self._raise("FlushFileBuffers")

    def dispose(self, handle: int) -> None:
        info = _DispositionInfo(True)
        if not self.SetFileInformationByHandle(
            wintypes.HANDLE(handle), self.DISPOSITION_INFO,
            ctypes.byref(info), ctypes.sizeof(info),
        ):
            self._raise("SetFileInformationByHandle")

    def close(self, handle: int) -> None:
        if handle and not self.CloseHandle(wintypes.HANDLE(handle)):
            self._raise("CloseHandle")


WINDOWS_API = WindowsReceiverApi() if os.name == "nt" else None


__all__ = ["WINDOWS_API"]
