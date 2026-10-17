"""Logical Win32 asset paths, preserved from the original toolkit API."""
from __future__ import annotations

import re
from pathlib import PureWindowsPath


WINDOWS_DEVICE_NAME_RE = re.compile(
    r"^(?:con|prn|aux|nul|com[1-9¹²³]|lpt[1-9¹²³]|conin\$|conout\$)(?:\.|$)",
    re.IGNORECASE | re.ASCII,
)


WINDOWS_FORBIDDEN_PATH_CHARS = frozenset('<>:"|?*')


WINDOWS_LOGICAL_PATH_TRANSLATION = str.maketrans(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ\\",
    "abcdefghijklmnopqrstuvwxyz/",
)


def logical_path_problem(logical_path: str) -> str | None:
    windows_path = PureWindowsPath(logical_path)
    if logical_path.startswith("/") or windows_path.is_absolute() or windows_path.drive:
        return "must be relative"
    if "\\" in logical_path:
        return "must use forward slashes"
    segments = logical_path.split("/")
    if any(segment == ".." for segment in segments):
        return "must not contain '..' segments"
    if any(segment in ("", ".") for segment in segments):
        return "must not contain empty or '.' segments"
    if any(segment.endswith((".", " ")) for segment in segments):
        return "must not contain segments ending in a dot or space"
    if any(
        ord(character) < 32 or character in WINDOWS_FORBIDDEN_PATH_CHARS
        for segment in segments for character in segment
    ):
        return "must not contain Win32-forbidden characters"
    if any(WINDOWS_DEVICE_NAME_RE.match(segment) for segment in segments):
        return "must not contain reserved Windows device names"
    return None


def windows_logical_path_key(logical_path: str) -> str:
    """Return the ASCII-case-insensitive identity used by logical Win32 roots."""
    return logical_path.translate(WINDOWS_LOGICAL_PATH_TRANSLATION)
