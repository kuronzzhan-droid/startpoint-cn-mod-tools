"""Resolve a unique manifest dependency chain and its ordered ZIP parts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from .archive_index import index_zip_names

VERSION = re.compile(r"^\d+\.\d+\.\d+$")
ARCHIVE = re.compile(r"^pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-(\d+)-.+\.zip$")


def version(value):
    if not isinstance(value, str) or not VERSION.fullmatch(value):
        raise ValueError(f"invalid version: {value!r}")
    return tuple(int(part) for part in value.split("."))


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def archive_names(entry):
    names = entry.get("chain") or [entry.get("archive")]
    if not isinstance(names, list) or not names:
        raise ValueError("manifest patch requires an archive or chain")
    numbers = []
    for name in names:
        match = ARCHIVE.fullmatch(name) if isinstance(name, str) else None
        if match is None or match.group(1, 2) != (entry["depends_on"], entry["version"]):
            raise ValueError(f"archive name does not match manifest edge: {name!r}")
        numbers.append((int(match[3]), name))
    numbers.sort()
    if [n for n, _ in numbers] != list(range(1, len(numbers) + 1)):
        raise ValueError(f"duplicate or missing archive seq: {names}")
    return [name for _, name in numbers]


def manifest_entries(manifest, directories, manifests=None):
    files = {Path(manifest)}
    if manifests is None:
        for directory in directories:
            files.update(path for path in directory.glob("manifest*.json")
                         if not path.name.startswith("manifest-entry-"))
    else:
        files.update(manifests)
    entries = []
    for filename in sorted(files):
        data = json.loads(filename.read_text(encoding="utf-8-sig"))
        patches = data.get("patches", [data]) if isinstance(data, dict) else None
        if not isinstance(patches, list):
            raise ValueError(f"invalid manifest patches: {filename}")
        for entry in patches:
            if not isinstance(entry, dict):
                raise ValueError(f"invalid manifest entry: {filename}")
            if entry.get("type", "patch") == "patch":
                entries.append(entry)
    return entries


def manifest_tip(manifest, directories, base_version, manifests=None):
    """Use the highest enabled manifest version; never fall back across a gap."""
    versions = [base_version]
    for entry in manifest_entries(manifest, directories, manifests):
        if entry.get("enabled", True) is False:
            continue
        target = entry.get("version")
        if target is not None:
            version(target)  # Invalid enabled versions must not be silently skipped.
            versions.append(target)
    tip = max(versions, key=version)
    resolve_chain(manifest, directories, base_version, tip, manifests)
    return tip


def resolve_chain(manifest, directories, base_version, tip, manifests=None):
    lower, upper = version(base_version), version(tip)
    if upper < lower:
        raise ValueError("tip precedes the configured store base version")
    by_version, enabled_states = {}, {}
    for entry in manifest_entries(manifest, directories, manifests):
        target = entry.get("version")
        # Disabled authoring templates can contain a version placeholder. They
        # are not chain edges; real disabled versions still participate in
        # conflict detection so an older manifest cannot resurrect them.
        if entry.get("enabled") is False and (not isinstance(target, str) or not VERSION.fullmatch(target)):
            continue
        if target is None or not (lower < version(target) <= upper):
            continue
        enabled = entry.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"manifest enabled must be boolean: {target}")
        if target in enabled_states and enabled_states[target] != enabled:
            raise ValueError(f"conflicting manifest enabled state for {target}")
        enabled_states[target] = enabled
        if not enabled:
            continue
        previous = entry.get("depends_on")
        if version(previous) >= version(target):
            raise ValueError(f"non-forward manifest edge: {previous} -> {target}")
        names = archive_names(entry)
        candidate = by_version.setdefault(target, {"version": target, "depends_on": previous,
                                                   "names": names, "integrity": {}})
        if (candidate["depends_on"], candidate["names"]) != (previous, names):
            raise ValueError(f"ambiguous manifest edge for {target}")
        for item in entry.get("archive_integrity", []):
            name = item.get("name")
            if name not in names:
                raise ValueError(f"integrity references archive outside edge: {name}")
            for field in ("sha256", "size"):
                if field not in item:
                    continue
                old = candidate["integrity"].setdefault(name, {}).setdefault(field, item[field])
                if old != item[field]:
                    raise ValueError(f"conflicting manifest {field}: {name}")
    reverse, current = [], tip
    while current != base_version:
        if current not in by_version:
            raise ValueError(f"manifest chain gap: cannot reach {current} from {base_version}")
        edge = by_version[current]
        reverse.append(edge)
        current = edge["depends_on"]
        if version(current) < lower:
            raise ValueError("manifest edge crosses the store baseline")
    return list(reversed(reverse))


def resolve_archives(edges, directories):
    archives, records = [], []
    found = index_zip_names(directories, {name for edge in edges for name in edge["names"]})
    for edge in edges:
        for name in edge["names"]:
            candidates = list(dict.fromkeys(found.get(name, [])))
            if not candidates:
                raise FileNotFoundError(f"manifest archive not found in configured directories: {name}")
            expected = edge["integrity"].get(name, {})
            if "sha256" in expected and (not isinstance(expected["sha256"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", expected["sha256"])):
                raise ValueError(f"invalid manifest SHA-256: {name}")
            if "size" in expected and (type(expected["size"]) is not int or expected["size"] < 0):
                raise ValueError(f"invalid manifest archive size: {name}")
            matching = []
            for candidate in candidates:
                if "size" in expected and candidate.stat().st_size != expected["size"]:
                    continue
                sha256 = digest(candidate)
                if "sha256" in expected and sha256 != expected["sha256"]:
                    continue
                matching.append((candidate, sha256))
            if not matching:
                raise ValueError(f"manifest archive integrity mismatch: {name}")
            hashes = {sha256 for _, sha256 in matching}
            if len(hashes) != 1:
                raise ValueError(f"same-named archive has conflicting bytes: {name}")
            sha256 = hashes.pop()
            archives.append(matching[0][0])
            records.append({"name": name, "sha256": sha256})
    return archives, records
