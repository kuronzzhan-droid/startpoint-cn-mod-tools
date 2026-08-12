"""Explicit logical-path evidence for legacy hashed CDN payloads."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Final, Mapping

from ._legacy_zip import _portable_name, error
from .canonical import canonical_json_bytes, load_json_strict_bytes


_SALT: Final = "K6R9T9Hz22OpeIGEWB0ui6c6PYFQnJGy"
_PREFIXES: Final = {
    "common": "production/upload",
    "medium": "production/medium_upload",
    "android": "production/android_upload",
}


@dataclass(frozen=True)
class LegacyPath:
    root: str
    logical_path: str
    member: str

    def to_wire(self) -> dict[str, str]:
        return {"logicalPath": self.logical_path, "root": self.root}


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise error(f"{label} must be an object")
    return value


def _hashed_member(root: str, logical_path: str) -> str:
    digest = hashlib.sha1((logical_path + _SALT).encode("utf-8")).hexdigest()
    return f"{_PREFIXES[root]}/{digest[:2]}/{digest[2:]}"


def parse_path_map(raw: bytes) -> tuple[LegacyPath, ...]:
    value = _mapping(load_json_strict_bytes(raw, label="legacy path map"), "legacy path map")
    if set(value) != {"legacyPathMapVersion", "paths"} or value["legacyPathMapVersion"] != 1:
        raise error("legacy path map fields are invalid")
    items = value["paths"]
    if not isinstance(items, list) or not items:
        raise error("legacy path map must contain paths")
    result: list[LegacyPath] = []
    members: set[str] = set()
    for index, item in enumerate(items):
        entry = _mapping(item, f"legacy path map paths[{index}]")
        if set(entry) != {"logicalPath", "root"}:
            raise error("legacy path map entry fields are invalid")
        root = entry["root"]
        logical = entry["logicalPath"]
        if not isinstance(root, str) or root not in _PREFIXES:
            raise error("legacy path map root is invalid")
        if not isinstance(logical, str):
            raise error("legacy path map logical path is invalid")
        logical = _portable_name(logical)
        member = _hashed_member(root, logical)
        if member in members:
            raise error("legacy path map entry is duplicated")
        members.add(member)
        result.append(LegacyPath(root, logical, member))
    result.sort(key=lambda item: (item.root.encode("utf-8"), item.logical_path.encode("utf-8")))
    return tuple(result)


def path_map_bytes(paths: tuple[LegacyPath, ...]) -> bytes:
    return canonical_json_bytes({
        "legacyPathMapVersion": 1,
        "paths": [item.to_wire() for item in paths],
    })


__all__ = ["LegacyPath", "parse_path_map", "path_map_bytes"]
