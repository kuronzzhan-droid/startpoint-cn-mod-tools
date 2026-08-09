"""One-way ownership projection for strict character package manifests."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath
import re
from typing import Final

from .canonical import normalize_relative_path
from .errors import ReleaseError
from .schema import OwnershipManifest


_ROOT_NAMES: Final = ("common", "medium", "android", "server")
_MANIFEST_KEYS: Final = frozenset(
    {
        "schema_version",
        "package_id",
        "character_id",
        "code_name",
        "package_version",
        "requires_client_base",
        "required_capabilities",
        "roots",
        "tables",
        "skills",
        "unique_condition",
        "qa",
        "snapshot",
    }
)
_FILE_KEYS: Final = frozenset({"logical_path", "sha256", "size"})
_TABLE_KEYS: Final = frozenset(
    {
        "root",
        "logical_path",
        "codec_id",
        "outer_keys",
        "inner_keys",
        "semantic_claims",
    }
)
_CODE_NAME_PATTERN: Final = re.compile(r"[a-z][a-z0-9_]*")
_SHA256_PATTERN: Final = re.compile(r"[0-9a-f]{64}")
_OWNERSHIP_PART_PATTERN: Final = re.compile(r"[^\s:]+")
_TABLE_NAME_PATTERN: Final = re.compile(r"[a-z][a-z0-9._-]*")


def _invalid(label: str, message: str) -> ReleaseError:
    return ReleaseError("WFREL_OWNERSHIP_INVALID", message, {"label": label})


def _exact_mapping(
    value: object,
    keys: frozenset[str],
    label: str,
) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != keys:
        raise _invalid(label, "object keys do not match the character manifest contract")
    return value


def _canonical_logical_path(value: object, label: str) -> str:
    if not isinstance(value, str) or "*" in value or "?" in value:
        raise _invalid(label, "value must be an exact logical path without wildcards")
    try:
        return normalize_relative_path(value)
    except ReleaseError as error:
        raise _invalid(label, "value must be a canonical logical path") from error


def _utf8_sorted_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values), key=lambda item: item.encode("utf-8")))


def _declared_payload_paths(value: object, label: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise _invalid(label, "declared payload paths must be an array")
    paths = [_canonical_logical_path(item, f"{label}[]") for item in value]
    if len(set(paths)) != len(paths):
        raise _invalid(label, "declared payload paths must be unique")
    return _utf8_sorted_unique(paths)


def _manifest_paths(manifest: Mapping[str, object]) -> tuple[tuple[str, ...], dict[str, set[str]]]:
    roots = _exact_mapping(
        manifest["roots"], frozenset(_ROOT_NAMES), "roots"
    )
    paths: list[str] = []
    paths_by_root: dict[str, set[str]] = {root: set() for root in _ROOT_NAMES}
    seen_paths: set[str] = set()
    for root in _ROOT_NAMES:
        entries = roots[root]
        if not isinstance(entries, list):
            raise _invalid(f"roots.{root}", "root declarations must be an array")
        for index, raw_entry in enumerate(entries):
            label = f"roots.{root}[{index}]"
            entry = _exact_mapping(raw_entry, _FILE_KEYS, label)
            logical_path = _canonical_logical_path(
                entry["logical_path"], f"{label}.logical_path"
            )
            sha256 = entry["sha256"]
            size = entry["size"]
            if not isinstance(sha256, str) or not _SHA256_PATTERN.fullmatch(sha256):
                raise _invalid(f"{label}.sha256", "value must be a lowercase SHA-256")
            if type(size) is not int or size < 0:
                raise _invalid(f"{label}.size", "value must be a non-negative integer")
            if logical_path in seen_paths:
                raise _invalid(f"{label}.logical_path", "logical path is duplicated")
            seen_paths.add(logical_path)
            paths_by_root[root].add(logical_path)
            paths.append(logical_path)
    if not paths:
        raise _invalid("roots", "at least one logical path is required")
    return _utf8_sorted_unique(paths), paths_by_root


def _manifest_records(
    manifest: Mapping[str, object],
    paths_by_root: Mapping[str, set[str]],
) -> tuple[str, ...]:
    tables = manifest["tables"]
    if not isinstance(tables, list):
        raise _invalid("tables", "table declarations must be an array")
    records: list[str] = []
    seen_table_claims: set[tuple[str, str]] = set()
    for index, raw_entry in enumerate(tables):
        label = f"tables[{index}]"
        entry = _exact_mapping(raw_entry, _TABLE_KEYS, label)
        root = entry["root"]
        if not isinstance(root, str) or root not in paths_by_root:
            raise _invalid(f"{label}.root", "table root is not supported")
        logical_path = _canonical_logical_path(
            entry["logical_path"], f"{label}.logical_path"
        )
        if logical_path not in paths_by_root[root]:
            raise _invalid(
                f"{label}.logical_path",
                "table path is not declared by the matching manifest root",
            )
        codec_id = entry["codec_id"]
        if not isinstance(codec_id, str) or not codec_id:
            raise _invalid(f"{label}.codec_id", "codec id must be a non-empty string")
        outer_keys = entry["outer_keys"]
        if not isinstance(outer_keys, list):
            raise _invalid(f"{label}.outer_keys", "outer keys must be an array")
        if any(
            not isinstance(key, str) or not _OWNERSHIP_PART_PATTERN.fullmatch(key)
            for key in outer_keys
        ) or len(set(outer_keys)) != len(outer_keys):
            raise _invalid(f"{label}.outer_keys", "outer keys are invalid or duplicated")
        table_claim = (root, logical_path)
        if table_claim in seen_table_claims:
            raise _invalid(f"{label}.logical_path", "table declaration is duplicated")
        seen_table_claims.add(table_claim)
        for field in ("inner_keys", "semantic_claims"):
            if not isinstance(entry[field], list):
                raise _invalid(f"{label}.{field}", "table claim field must be an array")
        table_name = PurePosixPath(logical_path).stem
        if not _TABLE_NAME_PATTERN.fullmatch(table_name):
            raise _invalid(f"{label}.logical_path", "table name cannot form an ownership key")
        records.extend(f"{table_name}:{key}" for key in outer_keys)
    if not records:
        raise _invalid("tables", "at least one owned table record is required")
    return _utf8_sorted_unique(records)


def project_character_ownership(
    *,
    workspace_manifest: Mapping[str, object],
    declared_server_paths: Sequence[str],
    declared_overlay_paths: Sequence[str],
) -> OwnershipManifest:
    """Project the only permitted ownership from one strict package manifest."""
    manifest = _exact_mapping(workspace_manifest, _MANIFEST_KEYS, "workspace_manifest")
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1:
        raise _invalid("schema_version", "character manifest schema version is unsupported")
    character_id = manifest["character_id"]
    if type(character_id) is not int or character_id <= 0:
        raise _invalid("character_id", "character id must be a positive integer")
    code_name = manifest["code_name"]
    if not isinstance(code_name, str) or not _CODE_NAME_PATTERN.fullmatch(code_name):
        raise _invalid("code_name", "code name does not match the workspace contract")

    paths, paths_by_root = _manifest_paths(manifest)
    records = _manifest_records(manifest, paths_by_root)
    declared_server = frozenset(
        _declared_payload_paths(declared_server_paths, "declared_server_paths")
    )
    declared_overlay = frozenset(
        _declared_payload_paths(declared_overlay_paths, "declared_overlay_paths")
    )
    expected_server = frozenset(paths_by_root["server"])
    expected_overlay = frozenset(
        path
        for root in ("common", "medium", "android")
        for path in paths_by_root[root]
    )
    if declared_server != expected_server or declared_overlay != expected_overlay:
        raise ReleaseError(
            "WFREL_OWNERSHIP_COVERAGE",
            "declared payload paths do not exactly match projected ownership partitions",
            {
                "missingServerCount": len(expected_server - declared_server),
                "extraServerCount": len(declared_server - expected_server),
                "missingOverlayCount": len(expected_overlay - declared_overlay),
                "extraOverlayCount": len(declared_overlay - expected_overlay),
            },
        )

    return OwnershipManifest(
        schema_version=1,
        entities=(f"character:{character_id}",),
        records=records,
        paths=paths,
    )
