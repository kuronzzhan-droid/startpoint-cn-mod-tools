"""Table ownership evidence for isolated character edit checkouts."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
from typing import Mapping

import wf_character_pack

from .canonical import canonical_json_bytes, load_json_strict_bytes, normalize_relative_path
from .errors import ReleaseError


_SESSION_KEYS = {
    "characterEditSessionVersion",
    "packageVersion",
    "sourceWorkspaceInputSha256",
    "tableClaims",
    "tables",
}
_TABLE_KEYS = {"baselineFile", "codecId", "logicalPath", "root", "sha256", "size"}
_REPARSE_POINT = 0x0400


def _fail(message: str) -> ReleaseError:
    return ReleaseError("WFREL_CHARACTER_EDIT_INVALID", message)


def _stable_bytes(path: Path) -> bytes:
    try:
        before = path.lstat()
        if (
            stat.S_ISLNK(before.st_mode)
            or getattr(before, "st_file_attributes", 0) & _REPARSE_POINT
            or not stat.S_ISREG(before.st_mode)
        ):
            raise OSError("not a regular file")
        raw = path.read_bytes()
        after = path.lstat()
    except OSError as error:
        raise _fail("character edit baseline is unavailable or unsafe") from error
    before_id = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    after_id = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if before_id != after_id or len(raw) != before.st_size:
        raise _fail("character edit baseline changed while being read")
    return raw


def _claims(manifest: Mapping[str, object]):
    try:
        return wf_character_pack._parse_transaction_claims(dict(manifest))  # type: ignore[attr-defined]
    except Exception as error:
        raise _fail("character table claims are invalid") from error


def _inspect(claim, raw: bytes):
    if claim.codec_id == "json_object":
        try:
            value = load_json_strict_bytes(raw, label=claim.logical_path)
        except (UnicodeError, ValueError, TypeError) as error:
            raise _fail("server table claim is not valid JSON") from error
        if not isinstance(value, dict) or set(value) != set(claim.outer_keys) or claim.inner_keys:
            raise _fail("server table claim does not match the target character row")
        return None
    codec = wf_character_pack.DEFAULT_CODECS.get(claim.codec_id)
    if codec is None:
        raise _fail("character table claim uses an unsupported editable codec")
    try:
        image = codec.inspect(raw, claim, claim.semantic_claims)
    except Exception as error:
        raise _fail("character table claim bytes are invalid") from error
    outer = {key for key, _row in image.outer_rows}
    inner = {(outer_key, key) for outer_key, key, _row in image.inner_rows}
    if not set(claim.outer_keys).issubset(outer):
        raise _fail("character table claim is missing an owned outer key")
    expected_inner = {
        (outer_key, key)
        for outer_key, keys in claim.inner_keys
        for key in keys
    }
    if not expected_inner.issubset(inner):
        raise _fail("character table claim is missing an owned inner key")
    return image


def validate_table_claims(
    manifest: Mapping[str, object], payloads: Mapping[str, bytes]
) -> None:
    for (root, logical), claim in _claims(manifest).items():
        raw = payloads.get(f"{root}/{logical}")
        if raw is None:
            raise _fail("character table claim has no declared file")
        _inspect(claim, raw)


def write_edit_baselines(
    evidence: Path,
    manifest: Mapping[str, object],
    payloads: Mapping[str, bytes],
    source_digest: str,
) -> None:
    package_version = manifest.get("package_version")
    if not isinstance(package_version, str):
        raise _fail("character edit package version is invalid")
    table_rows: list[dict[str, object]] = []
    baseline_root = evidence / "edit-baseline"
    baseline_root.mkdir(parents=True, exist_ok=False)
    for index, ((root, logical), claim) in enumerate(_claims(manifest).items()):
        raw = payloads.get(f"{root}/{logical}")
        if raw is None:
            raise _fail("character table claim has no declared file")
        _inspect(claim, raw)
        if claim.codec_id == "json_object":
            continue
        relative = f"edit-baseline/{index:04d}.bin"
        path = evidence / relative
        path.write_bytes(raw)
        table_rows.append({
            "baselineFile": relative,
            "codecId": claim.codec_id,
            "logicalPath": logical,
            "root": root,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
        })
    session = {
        "characterEditSessionVersion": 1,
        "packageVersion": package_version,
        "sourceWorkspaceInputSha256": source_digest,
        "tableClaims": json.loads(json.dumps(manifest.get("tables"))),
        "tables": table_rows,
    }
    (evidence / "edit-session.json").write_bytes(canonical_json_bytes(session))


def _session(evidence: Path, manifest: Mapping[str, object]) -> dict[tuple[str, str], bytes]:
    try:
        value = load_json_strict_bytes(
            _stable_bytes(evidence / "edit-session.json"), label="character edit session"
        )
    except (UnicodeError, ValueError, TypeError) as error:
        raise _fail("character edit session is invalid") from error
    if (
        not isinstance(value, dict)
        or set(value) != _SESSION_KEYS
        or value.get("characterEditSessionVersion") != 1
        or value.get("packageVersion") != manifest.get("package_version")
        or value.get("tableClaims") != manifest.get("tables")
    ):
        raise _fail("character edit session does not match the workspace")
    source_digest = value.get("sourceWorkspaceInputSha256")
    if (
        not isinstance(source_digest, str)
        or len(source_digest) != 64
        or any(character not in "0123456789abcdef" for character in source_digest)
    ):
        raise _fail("character edit session source digest is invalid")
    rows = value.get("tables")
    if not isinstance(rows, list):
        raise _fail("character edit session tables are invalid")
    result: dict[tuple[str, str], bytes] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != _TABLE_KEYS:
            raise _fail("character edit baseline claim is invalid")
        root = row.get("root")
        logical = row.get("logicalPath")
        codec = row.get("codecId")
        relative = row.get("baselineFile")
        if (
            root not in {"common", "medium", "android"}
            or not isinstance(logical, str)
            or not isinstance(codec, str)
            or not isinstance(relative, str)
        ):
            raise _fail("character edit baseline identity is invalid")
        try:
            normalize_relative_path(logical)
            normalize_relative_path(relative)
        except ReleaseError as error:
            raise _fail("character edit baseline path is invalid") from error
        if not relative.startswith("edit-baseline/"):
            raise _fail("character edit baseline path is invalid")
        marker = (root, logical)
        if marker in result:
            raise _fail("character edit baseline identity is duplicated")
        raw = _stable_bytes(evidence / Path(relative))
        if row.get("size") != len(raw) or row.get("sha256") != hashlib.sha256(raw).hexdigest():
            raise _fail("character edit baseline digest is invalid")
        result[marker] = raw
    return result


def _reject_unowned_changes(claim, baseline: bytes, current: bytes) -> None:
    before = _inspect(claim, baseline)
    after = _inspect(claim, current)
    assert before is not None and after is not None
    before_outer = tuple(key for key, _row in before.outer_rows)
    after_outer = tuple(key for key, _row in after.outer_rows)
    if before_outer != after_outer:
        raise _fail("character edit changed unowned table key ordering or membership")
    owned_outer = set(claim.outer_keys)
    before_rows = dict(before.outer_rows)
    after_rows = dict(after.outer_rows)
    inner_claims = {outer: set(keys) for outer, keys in claim.inner_keys}
    for outer in before_outer:
        if outer not in owned_outer and before_rows[outer] != after_rows[outer]:
            raise _fail("character edit changed an unowned table row")
        if outer in owned_outer and outer not in inner_claims:
            continue
        before_inner = [(key, row) for owner, key, row in before.inner_rows if owner == outer]
        after_inner = [(key, row) for owner, key, row in after.inner_rows if owner == outer]
        if tuple(key for key, _row in before_inner) != tuple(key for key, _row in after_inner):
            raise _fail("character edit changed unowned table key ordering or membership")
        owned_inner = inner_claims.get(outer, set())
        for (key, before_row), (_same, after_row) in zip(before_inner, after_inner):
            if key not in owned_inner and before_row != after_row:
                raise _fail("character edit changed an unowned table row")


def validate_edit_boundaries(
    evidence: Path,
    manifest: Mapping[str, object],
    payloads: Mapping[str, bytes],
) -> None:
    baselines = _session(evidence, manifest)
    claims = _claims(manifest)
    expected = {
        marker for marker, claim in claims.items() if claim.codec_id != "json_object"
    }
    if set(baselines) != expected:
        raise _fail("character edit baseline table set does not match the manifest")
    for marker, claim in claims.items():
        raw = payloads.get(f"{marker[0]}/{marker[1]}")
        if raw is None:
            raise _fail("character table claim has no declared file")
        if claim.codec_id == "json_object":
            _inspect(claim, raw)
        else:
            _reject_unowned_changes(claim, baselines[marker], raw)


__all__ = ["validate_edit_boundaries", "validate_table_claims", "write_edit_baselines"]
