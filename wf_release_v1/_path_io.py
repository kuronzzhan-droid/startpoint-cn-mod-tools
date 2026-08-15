"""Small host-path adapter for Windows extended-length release staging paths."""

from __future__ import annotations

import os
from pathlib import Path


def native_path(path: Path) -> str:
    """Return an absolute OS path, using Win32 extended-length syntax when needed."""
    absolute = os.path.abspath(os.fspath(path))
    if os.name != "nt" or absolute.startswith("\\\\?\\"):
        return absolute
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute[2:]
    return "\\\\?\\" + absolute


__all__ = ["native_path"]
