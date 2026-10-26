"""Strict APK bundled-table indexes and the ClientError 7051 collision gate."""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
import os
from pathlib import Path
import tempfile
import zipfile
import zlib

import wf_mod_tool as core
from wf.deliver.changeset import relative_path
from wf.paths import REPOSITORY
from .bundle_index import (SCHEMA, SUFFIX, BUNDLED_SUFFIX, BUNDLE_MEMBER, bundled_logical,
                           encoded as _encoded, extract as _extract, read_cache as _read_cache)
from .delivery_inputs import logical_candidates, read_delivery_members


def _digest(filename):
    with Path(filename).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _cache_directory(cache_dir):
    value = cache_dir or os.environ.get("WF_STUDIO_BUNDLE_CACHE")
    if value is None:
        value = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "wf-studio" / "bundle-index"
    directory = Path(value).expanduser().resolve()
    if directory.is_relative_to(REPOSITORY.resolve()):
        raise ValueError("APK bundle index cache must be outside the repository")
    return directory


def load_bundle_index(apk, *, logical_paths=(), cache_dir=None):
    """Return normal CDN logical paths -> keys, cached by the APK SHA-256.

    Logical names come from the existing recovered path list plus explicit inputs.
    Candidate changes invalidate the cache, including newly introduced tables.
    Cache and ZIP corruption raise; they never become an empty successful index.
    """
    apk = Path(apk)
    paths = set()
    for logical in logical_candidates(logical_paths, tables_only=True):
        if logical.endswith(BUNDLED_SUFFIX):
            logical = logical[:-len(BUNDLED_SUFFIX)] + SUFFIX
        paths.add(logical)
    paths = sorted(paths)
    paths_digest = hashlib.sha256(_encoded(paths)).hexdigest()
    digest = _digest(apk)
    directory = _cache_directory(cache_dir)
    filename = directory / (digest + ".json")
    if filename.is_file():
        cached = _read_cache(filename, digest, paths_digest)
        if cached is not None:
            return cached
    tables, hashed = _extract(apk, paths)
    if _digest(apk) != digest:
        raise ValueError("APK changed while extracting bundled tables")
    index = {"schema": SCHEMA, "sha256": digest, "pathsSha256": paths_digest,
             "tables": tables, "hashedTables": hashed}
    payload = {"index": index, "indexSha256": hashlib.sha256(_encoded(index)).hexdigest()}
    directory.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix=digest + "-", suffix=".tmp",
                                         dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(_encoded(payload) + b"\n")
        temporary.replace(filename)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return index


def bundled_keys(indexes, logical):
    """Union the selected APK keys for a normal CDN logical path (p13 reuse)."""
    digest = core.sha1_path(bundled_logical(logical))
    return {key for index in indexes for key in index["tables"].get(
        logical, index.get("hashedTables", {}).get(digest, []))}


def _staged_tables(tables):
    """Accept plain logical keys or compiler (root, logical) keys without flattening."""
    if not isinstance(tables, Mapping):
        raise ValueError("staged tables must be a mapping")
    outputs = {}
    for key, raw in tables.items():
        root, logical = key if isinstance(key, tuple) and len(key) == 2 else ("common", key)
        if not isinstance(logical, str) or root not in {"common", "medium", "android", "small", "ios"}:
            raise ValueError("invalid staged (root, logical) key")
        relative_path(logical)
        if not logical.endswith(SUFFIX):
            continue
        if root != "common":
            raise ValueError(f"output orderedmap must use common root: {logical}")
        if logical in outputs:
            raise ValueError(f"duplicate output orderedmap: {logical}")
        if not isinstance(raw, bytes):
            raise ValueError(f"staged orderedmap must contain bytes: {logical}")
        outputs[logical] = set(core.read_orderedmap_raw_rows_from_bytes(raw, logical).keys)
    return outputs


def check_bundle_keys(apks, *, tables=None, zips=(), delivery_dir=None, cache_dir=None,
                      logical_paths=(), loaded_indexes=None):
    """Produce the public bundle-check JSON; malformed selected inputs are errors."""
    report = {"status": "error", "apks": [], "tables": []}
    apks = list(apks or ())
    if not apks:
        return {**report, "status": "skipped", "reason": "未配置目标 APK，未核对内置表键"}
    try:
        if tables is not None and (zips or delivery_dir is not None):
            raise ValueError("provide staged tables or delivery ZIPs, not both")
        if tables is None:
            tables = {}
            for member in read_delivery_members(zips, delivery_dir=delivery_dir):
                if member.logical is None:
                    if member.root == "common":
                        raise ValueError(f"cannot identify common-root delivery member: {member.member}")
                    continue
                if member.logical.endswith(SUFFIX):
                    if member.root != "common":
                        raise ValueError(f"output orderedmap must use common root: {member.logical}")
                    if member.logical in tables:
                        raise ValueError(f"duplicate output orderedmap: {member.logical}")
                    tables[member.logical] = member.data
        outputs = _staged_tables(tables)
        indexes = []
        for apk in apks:
            index = load_bundle_index(apk, logical_paths=set(outputs) | set(logical_paths), cache_dir=cache_dir)
            indexes.append(index)
            if loaded_indexes is not None:
                loaded_indexes.append(index)
            report["apks"].append({"label": Path(apk).name, "sha256": index["sha256"],
                                   "bundledTables": len(index["hashedTables"])})
        for logical, keys in sorted(outputs.items()):
            report["tables"].append({"logical": logical, "bundledLogical": bundled_logical(logical),
                                     "collisions": sorted(keys & bundled_keys(indexes, logical))})
        report["status"] = "collision" if any(t["collisions"] for t in report["tables"]) else "ok"
    except (OSError, ValueError, TypeError, KeyError, zipfile.BadZipFile, RuntimeError, zlib.error) as exc:
        report["reason"] = f"{type(exc).__name__}: {exc}"
    return report
