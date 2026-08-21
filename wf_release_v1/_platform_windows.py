"""Private Win32 process handles used by the release-v1 platform adapter."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
import subprocess

from .errors import ReleaseError


@dataclass(frozen=True)
class ProcessIdentity:
    creation_time: int
    executable: Path


class WindowsBackend:
    _QUERY_LIMITED_INFORMATION = 0x1000
    _SYNCHRONIZE = 0x00100000
    _TERMINATE = 0x0001
    _WAIT_OBJECT_0 = 0
    _WAIT_TIMEOUT = 258

    def __init__(self) -> None:
        if os.name != "nt":
            raise ReleaseError("WFREL_PLATFORM_INVALID", "Windows process management is unavailable")
        import ctypes
        from ctypes import wintypes

        self._ctypes = ctypes
        self._wintypes = wintypes
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self._kernel32.OpenProcess.restype = wintypes.HANDLE
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._kernel32.CloseHandle.restype = wintypes.BOOL
        self._kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ]
        self._kernel32.GetProcessTimes.restype = wintypes.BOOL
        self._kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
        ]
        self._kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        self._kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self._kernel32.WaitForSingleObject.restype = wintypes.DWORD
        self._kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        self._kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        self._kernel32.GenerateConsoleCtrlEvent.argtypes = [wintypes.DWORD, wintypes.DWORD]
        self._kernel32.GenerateConsoleCtrlEvent.restype = wintypes.BOOL
        self._kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self._kernel32.TerminateProcess.restype = wintypes.BOOL

    def spawn(
        self,
        command: tuple[str, ...],
        cwd: Path,
        environment: dict[str, str],
        *,
        capture_output: bool = True,
    ) -> object:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = 0
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
            stderr=subprocess.PIPE if capture_output else subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            startupinfo=startup,
        )
        handle = self.open_process(process.pid)
        if handle is None:
            process.kill()
            raise OSError("child process was unavailable")
        return type("SpawnedProcess", (), {
            "pid": process.pid,
            "handle": handle,
            "stdout": process.stdout,
            "stderr": process.stderr,
            "owner": process,
        })()

    def open_process(self, pid: int) -> object | None:
        rights = self._QUERY_LIMITED_INFORMATION | self._SYNCHRONIZE | self._TERMINATE
        handle = self._kernel32.OpenProcess(rights, False, pid)
        if handle:
            return handle
        error = self._ctypes.get_last_error()
        if error == 87:
            return None
        raise OSError(error, "process could not be opened")

    def identity(self, handle: object) -> ProcessIdentity:
        class FILETIME(self._ctypes.Structure):
            _fields_ = [("low", self._wintypes.DWORD), ("high", self._wintypes.DWORD)]

        created, exited, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        if not self._kernel32.GetProcessTimes(
            handle,
            self._ctypes.byref(created),
            self._ctypes.byref(exited),
            self._ctypes.byref(kernel),
            self._ctypes.byref(user),
        ):
            raise OSError(self._ctypes.get_last_error(), "process time was unavailable")
        size = self._wintypes.DWORD(32768)
        buffer = self._ctypes.create_unicode_buffer(size.value)
        if not self._kernel32.QueryFullProcessImageNameW(handle, 0, buffer, self._ctypes.byref(size)):
            raise OSError(self._ctypes.get_last_error(), "process image was unavailable")
        return ProcessIdentity((created.high << 32) | created.low, Path(buffer.value))

    def wait(self, handle: object, timeout: float) -> bool:
        milliseconds = min(0xFFFFFFFE, math.ceil(timeout * 1000))
        result = self._kernel32.WaitForSingleObject(handle, milliseconds)
        if result == self._WAIT_OBJECT_0:
            return True
        if result == self._WAIT_TIMEOUT:
            return False
        raise OSError(self._ctypes.get_last_error(), "process wait failed")

    def exit_code(self, handle: object) -> int:
        value = self._wintypes.DWORD()
        if not self._kernel32.GetExitCodeProcess(handle, self._ctypes.byref(value)):
            raise OSError(self._ctypes.get_last_error(), "process exit code was unavailable")
        return int(value.value)

    def send_ctrl_break(self, pid: int) -> None:
        if not self._kernel32.GenerateConsoleCtrlEvent(1, pid):
            raise OSError(self._ctypes.get_last_error(), "CTRL_BREAK could not be sent")

    def terminate(self, handle: object) -> None:
        if not self._kernel32.TerminateProcess(handle, 1):
            raise OSError(self._ctypes.get_last_error(), "process could not be terminated")

    def close(self, handle: object) -> None:
        self._kernel32.CloseHandle(handle)
