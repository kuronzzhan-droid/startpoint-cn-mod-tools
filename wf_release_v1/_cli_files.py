"""Stable bounded file reads used by local CLI metadata inputs."""

from __future__ import annotations

import os
from pathlib import Path
import stat
from typing import Final

from .errors import ReleaseError


_MAX_METADATA_BYTES: Final = 1024 * 1024
_REPARSE_POINT: Final = 0x0400


def _snapshot(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_mode,
    )


def _is_reparse(value: os.stat_result) -> bool:
    return stat.S_ISLNK(value.st_mode) or bool(
        getattr(value, "st_file_attributes", 0) & _REPARSE_POINT
    )


def read_stable_metadata(path: Path, *, label: str) -> bytes:
    """Read one regular file once while pinning its pathname and open identity."""
    descriptor = -1
    try:
        before_stat = os.lstat(path)
        if _is_reparse(before_stat) or not stat.S_ISREG(before_stat.st_mode):
            raise OSError("input is not a regular file")
        before = _snapshot(before_stat)
        descriptor = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        opened = os.fstat(descriptor)
        if _is_reparse(opened) or _snapshot(opened) != before:
            raise OSError("input identity changed before open")
        expected_size = opened.st_size
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            descriptor = -1
            raw = stream.read(_MAX_METADATA_BYTES + 1)
            after_open = os.fstat(stream.fileno())
        after_path = os.lstat(path)
        if (
            _snapshot(after_open) != before
            or _snapshot(after_path) != before
            or _is_reparse(after_path)
        ):
            raise OSError("input identity changed while reading")
        if expected_size > _MAX_METADATA_BYTES or len(raw) > _MAX_METADATA_BYTES:
            raise ReleaseError(
                "WFREL_REQUIRE_LIMIT",
                "requirements metadata exceeds the supported limit",
                {"label": label},
            )
        if len(raw) != expected_size:
            raise OSError("input length does not match its stable identity")
        return raw
    except OSError as error:
        raise ReleaseError(
            "WFREL_CLI_IO",
            "local input is unavailable or changed while being read",
            {"label": label},
        ) from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


__all__ = ["read_stable_metadata"]
