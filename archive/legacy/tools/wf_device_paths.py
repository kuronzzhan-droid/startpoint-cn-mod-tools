"""Portable executable discovery for optional local device tools."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import os
from pathlib import Path
import shutil


Finder = Callable[[str], str | None]


def _explicit_file(environment: Mapping[str, str], key: str) -> Path | None:
    raw = environment.get(key)
    if raw is None:
        return None
    configured = raw.strip().strip('"').strip()
    if not configured:
        raise ValueError(f"{key} must be a non-empty path")
    candidate = Path(configured).expanduser()
    if not candidate.is_absolute():
        raise ValueError(f"{key} must be an absolute path: {configured}")
    candidate = candidate.resolve()
    if not candidate.is_file():
        raise ValueError(f"{key} is not an existing file: {candidate}")
    return candidate


def _program_roots(environment: Mapping[str, str]) -> list[Path]:
    roots = []
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        raw = environment.get(key)
        if raw and raw.strip():
            root = Path(raw.strip().strip('"')).expanduser()
            if root.is_absolute():
                roots.append(root)
    return roots


def find_adb(environment: Mapping[str, str] = os.environ,
             *, finder: Finder = shutil.which) -> str | None:
    explicit = _explicit_file(environment, "WF_ADB")
    if explicit is not None:
        return os.fspath(explicit)
    located = finder("adb") or finder("adb.exe")
    if located:
        return os.fspath(Path(located).resolve())
    suffixes = (
        Path("Netease/MuMuPlayer-12.0/shell/adb.exe"),
        Path("Netease/MuMu Player 12/shell/adb.exe"),
        Path("Netease/MuMuPlayerGlobal-12.0/shell/adb.exe"),
        Path("MuMuPlayer-12.0/shell/adb.exe"),
    )
    for root in _program_roots(environment):
        for suffix in suffixes:
            candidate = root / suffix
            if candidate.is_file():
                return os.fspath(candidate.resolve())
    return None


def find_mumu_manager(environment: Mapping[str, str] = os.environ,
                      *, finder: Finder = shutil.which) -> Path | None:
    explicit = _explicit_file(environment, "WF_MUMU_MANAGER")
    if explicit is not None:
        return explicit
    located = finder("MuMuManager") or finder("MuMuManager.exe")
    if located:
        return Path(located).resolve()
    suffixes = (
        Path("Netease/MuMuPlayer-12.0/shell/MuMuManager.exe"),
        Path("Netease/MuMu Player 12/shell/MuMuManager.exe"),
        Path("MuMuPlayer-12.0/shell/MuMuManager.exe"),
    )
    for root in _program_roots(environment):
        for suffix in suffixes:
            candidate = root / suffix
            if candidate.is_file():
                return candidate.resolve()
    return None
