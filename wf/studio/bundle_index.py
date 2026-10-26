"""Strict extraction and cache validation for APK bundled orderedmaps."""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile

import wf_mod_tool as core
from wf.deliver.changeset import relative_path

SCHEMA = "wf-studio-bundle-keys/2"
SUFFIX = ".orderedmap"
BUNDLED_SUFFIX = "_iosbundled.orderedmap"
BUNDLE_MEMBER = re.compile(r"^production/android_bundle/([0-9a-f]{2})/([0-9a-f]{38})$")


def bundled_logical(logical):
    relative_path(logical)
    if not logical.endswith(SUFFIX) or logical.endswith(BUNDLED_SUFFIX):
        raise ValueError(f"expected CDN orderedmap logical path: {logical}")
    return logical[:-len(SUFFIX)] + BUNDLED_SUFFIX


def encoded(document):
    return json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _zip_names(archive, label):
    names = {}
    for entry in archive.infolist():
        relative_path(entry.filename.rstrip("/"))
        if entry.filename in names:
            raise ValueError(f"duplicate {label} ZIP member: {entry.filename}")
        names[entry.filename] = entry
    return names


def _has_index_header(raw):
    # No asset magic identifies orderedmap. Its uint32 length is immediately
    # followed by a zlib header; retain this signal even if the length is damaged.
    return (len(raw) >= 6 and raw[4] & 15 == 8 and raw[4] >> 4 <= 7
            and (raw[4] * 256 + raw[5]) % 31 == 0)


def extract(apk, paths):
    with zipfile.ZipFile(apk) as outer:
        names = _zip_names(outer, "APK")
        bundles = [name for name in names if name.rsplit("/", 1)[-1] == "bundle.zip"]
        if bundles != ["assets/bundle.zip"]:
            raise ValueError("APK must contain exactly one assets/bundle.zip and no other bundle.zip")
        if outer.testzip() is not None:
            raise ValueError("corrupt APK ZIP member")
        bundle_raw = outer.read(names["assets/bundle.zip"])
    tables, hashed = {}, {}
    logicals = {core.sha1_path(bundled_logical(logical)): logical for logical in paths}
    with zipfile.ZipFile(io.BytesIO(bundle_raw)) as bundle:
        names = _zip_names(bundle, "bundle")
        if not any(not info.is_dir() for info in names.values()):
            raise ValueError("APK assets/bundle.zip is empty")
        if bundle.testzip() is not None:
            raise ValueError("corrupt APK bundle ZIP member")
        for name, info in names.items():
            if info.is_dir():
                continue
            match = BUNDLE_MEMBER.fullmatch(name)
            if match is None:
                if name.startswith("production/android_bundle/"):
                    raise ValueError(f"invalid APK bundled member path: {name}")
                continue
            digest = match[1] + match[2]
            logical = logicals.get(digest)
            raw = bundle.read(info)
            if logical is None and not _has_index_header(raw):
                continue
            label = bundled_logical(logical) if logical else name
            table = core.read_orderedmap_raw_rows_from_bytes(raw, label)
            hashed[digest] = sorted(table.keys)
            if logical is not None:
                tables[logical] = hashed[digest]
    return tables, hashed


def read_cache(filename, digest, paths_digest):
    cached = json.loads(filename.read_text("utf-8"))
    if not isinstance(cached, dict) or set(cached) != {"index", "indexSha256"}:
        raise ValueError("invalid APK bundle index cache envelope")
    index = cached["index"]
    if not isinstance(index, dict):
        raise ValueError("APK bundle index cache must contain an object")
    if hashlib.sha256(encoded(index)).hexdigest() != cached["indexSha256"]:
        raise ValueError("APK bundle index cache checksum mismatch")
    if index.get("sha256") != digest:
        raise ValueError("APK bundle index cache identity mismatch")
    # Version 1 lacked anonymous table scanning; regenerate rather than reuse it.
    if index.get("schema") == "wf-studio-bundle-keys/1":
        return None
    if index.get("schema") != SCHEMA:
        raise ValueError("APK bundle index cache schema mismatch")
    if not isinstance(index.get("pathsSha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", index["pathsSha256"]):
        raise ValueError("invalid APK bundle index cache candidate digest")
    for field in ("tables", "hashedTables"):
        if not isinstance(index.get(field), dict) or any(
                not isinstance(key, str) or not isinstance(keys, list)
                or any(not isinstance(item, str) for item in keys) or keys != sorted(set(keys))
                for key, keys in index[field].items()):
            raise ValueError(f"invalid APK bundle index cache {field}")
    if any(not re.fullmatch(r"[0-9a-f]{40}", key) for key in index["hashedTables"]):
        raise ValueError("invalid APK bundle index cache table digest")
    for logical, keys in index["tables"].items():
        hashed = core.sha1_path(bundled_logical(logical))
        if index["hashedTables"].get(hashed) != keys:
            raise ValueError("APK bundle index cache logical/hash table mismatch")
    return index if index.get("pathsSha256") == paths_digest else None
