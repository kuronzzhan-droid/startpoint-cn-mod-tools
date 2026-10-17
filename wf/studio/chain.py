"""Resolve the test-server patch chain beyond kulo active from a manifest.json.

The kulo ``asset-patch/manifest.json`` format lists every enabled edge with
``archive_integrity`` entries ({name, size, sha256}). Edges newer than the
active TIP are not present in kulo ``active/``; their ZIPs live in delivery
folders. This module finds each named ZIP in the given search directories and
picks the candidate whose size and SHA-256 match the manifest (several folders
hold different builds with the same file name).
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .source import edge_versions

MAX_DEPTH = 4


@dataclass
class ChainResult:
    manifest: Path
    zips: list[Path] = field(default_factory=list)
    missing: list[dict] = field(default_factory=list)
    patches: list[dict] = field(default_factory=list)  # manifest entries beyond the TIP


def _version_key(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in value.split("."))
    except ValueError:
        return (0,)


def index_zip_names(directories, wanted: set[str]) -> dict[str, list[Path]]:
    """Walk directories (bounded depth) and collect files whose name is wanted."""
    found: dict[str, list[Path]] = {}
    seen: set[Path] = set()
    for directory in directories:
        root = Path(directory)
        if not root.is_dir():
            continue
        stack = [(root, 0)]
        while stack:
            current, depth = stack.pop()
            try:
                resolved = current.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                with os.scandir(current) as entries:
                    for entry in entries:
                        if entry.is_dir(follow_symlinks=False):
                            if depth < MAX_DEPTH and entry.name not in ("node_modules", ".git", "__pycache__"):
                                stack.append((Path(entry.path), depth + 1))
                        elif entry.name in wanted:
                            found.setdefault(entry.name, []).append(Path(entry.path))
            except OSError:
                continue
    return found


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_chain(manifest: Path, search_dirs, *, after_tip: int) -> ChainResult:
    manifest = Path(manifest)
    data = json.loads(manifest.read_text("utf-8-sig"))
    entries = [p for p in data.get("patches", []) if p.get("enabled")
               and _version_key(str(p.get("version", "0"))) > (1, 4, after_tip)]
    entries.sort(key=lambda p: _version_key(str(p.get("version"))))
    wanted_items = []
    for entry in entries:
        integrity = entry.get("archive_integrity") or [{"name": n} for n in (entry.get("chain") or [entry.get("archive")]) if n]
        for item in integrity:
            wanted_items.append((entry, item))

    def seq(item):
        name = item[1].get("name", "")
        versions = edge_versions(name)
        number = name.split("-")[4] if versions and len(name.split("-")) > 4 else "0"
        return (_version_key(str(item[0].get("version"))), int(number) if number.isdigit() else 0)

    wanted_items.sort(key=seq)
    directories = [manifest.parent / "active", *search_dirs]
    found = index_zip_names(directories, {item.get("name") for _, item in wanted_items})
    result = ChainResult(manifest=manifest, patches=entries)
    for entry, item in wanted_items:
        name = item.get("name")
        chosen = None
        for candidate in found.get(name, []):
            try:
                if item.get("size") is not None and candidate.stat().st_size != item["size"]:
                    continue
                if item.get("sha256") and _sha256(candidate) != item["sha256"]:
                    continue
            except OSError:
                continue
            chosen = candidate
            break
        if chosen is None:
            result.missing.append({"version": entry.get("version"), "name": name,
                                   "candidates": [str(p) for p in found.get(name, [])]})
        else:
            result.zips.append(chosen)
    return result
