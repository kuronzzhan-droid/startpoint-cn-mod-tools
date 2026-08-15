#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Exact in-memory contract for thunder-dragon 1.1.0 plus abyss gacha."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import wf_abyss_gacha_contract as gacha
import wf_character_pack as character_pack
import wf_summer_thunder_package_contract as thunder


PACKAGE_ID = thunder.PACKAGE_ID
CHARACTER_ID = thunder.CHARACTER_ID
CODE_NAME = thunder.CODE_NAME
ROOT_NAMES = thunder.ROOT_NAMES
PACKAGE_VERSION = "1.1.0"
REQUIRES_CLIENT_BASE = "1.4.347"
CONFIRMATION = "ASSEMBLE_CNMOD_THUNDER_DRAGON_ABYSS_GACHA_1_1_0"

ITEM_LOGICAL = "master/item/item.orderedmap"
ITEM_IDS_LOGICAL = "item_ids.json"
ITEM_SHEET_LOGICAL = "item/sprite_sheet.png"
ITEM_ATLAS_LOGICAL = "item/sprite_sheet.atlas.amf3.deflate"
SHOP_CLIENT_LOGICAL = "master/shop/event_item_shop.orderedmap"
SHOP_SERVER_LOGICAL = "event_item_shop.json"
SHOP_ID_MAP_LOGICAL = "event_item_shop_id_map.json"
ROGUE_EVENT_LOGICAL = "rogue_event.json"
ROGUE_EVENT_CLIENT_LOGICAL = "master/quest/event/cnmod_rogue_event.orderedmap"

NEW_PATHS: tuple[tuple[str, str], ...] = (
    *(("common", logical) for logical in gacha.COMMON_OUTPUT_PATHS),
    ("common", ITEM_LOGICAL),
    ("common", ITEM_SHEET_LOGICAL),
    ("common", ITEM_ATLAS_LOGICAL),
    ("common", SHOP_CLIENT_LOGICAL),
    ("common", ROGUE_EVENT_CLIENT_LOGICAL),
    ("common", gacha.LIST_BANNER_PAYLOAD_LOGICAL),
    ("medium", gacha.TOP_BANNER_PAYLOAD_LOGICAL),
    *(("server", logical) for logical in gacha.SERVER_OUTPUT_PATHS),
    ("server", ITEM_IDS_LOGICAL),
    ("server", SHOP_SERVER_LOGICAL),
    ("server", SHOP_ID_MAP_LOGICAL),
    ("server", ROGUE_EVENT_LOGICAL),
)
SERVER_LOGICALS = tuple(character_pack.SERVER_LOGICAL_PATHS) + tuple(
    logical for root, logical in NEW_PATHS if root == "server"
)
SOURCE_ROOT_COUNTS = {"common": 52, "medium": 25, "android": 2, "server": 4}
EXPECTED_ROOT_COUNTS = {
    root: SOURCE_ROOT_COUNTS[root] + sum(
        item_root == root for item_root, _logical in NEW_PATHS
    )
    for root in ROOT_NAMES
}
EXPECTED_PAYLOAD_COUNT = sum(EXPECTED_ROOT_COUNTS.values())
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_ACCEPTANCE = {
    "all_references_closed": True,
    "eight_character_closure": True,
    "ticket_contract_closed": True,
    "shop_contract_closed": True,
    "drop_contract_closed": True,
    "drop_source_sync_closed": True,
    "art_contract_closed": True,
    "unresolved_art_payloads": [],
    "package_manifest_eligible": True,
    "writes_live": False,
}
DROP_RUNTIME_SOURCE_SYNC = {
    "status": "independently_reviewed_source_ready",
    "server_commit_chain": [
        "b0412a2d8fb8fa9e27ce33167109e4d43fcb4c62",
        "983bea0913a216fb3c766ede068f1b87cba2a793",
        "930f410036da2f86ae109da89f50193c65b102c1",
        "c74e348caa89e56131da48661d654032edc009a5",
        "3d5be10cf1915cf4f1a84dd1db7478f94d18b316",
        "d195cb4daea2bfbe4fb58f7f76e89590c2df514f",
    ],
    "content_sync_generator_version": 4,
    "rogue_converter_version": 3,
    "interop_fixture_sha256": (
        "bb360da8f3968f3b7d1cd34d13624586535e9c72cdf44d6ca58c7729f34a90fb"
    ),
    "interop_fixture_size": 68,
    "outer_event_id": "700099",
    "ordered_rows": [
        ["1", "0", "999014", "1", "0.05"],
        ["1", "0", "11003", "1", "0.5"],
    ],
    "verification_scope": "source_and_tests_only_no_build_or_live",
    "writes_live": False,
}

PackageAssemblyError = thunder.PackageAssemblyError
PackageImage = thunder.PackageImage


@dataclass(frozen=True)
class SealedSourcePackage:
    roots: Mapping[str, Mapping[str, bytes]]
    manifest: Mapping[str, Any]
    workspace_input_sha256: str
    source_locks_sha256: str
    package_acceptance: Mapping[str, Any]
    skill_follow_gate: Mapping[str, Any]


@dataclass(frozen=True)
class AdditionBundle:
    roots: Mapping[str, Mapping[str, bytes]]
    table_claims: Sequence[Mapping[str, Any]]
    input_sha256: Mapping[str, str]
    component_reports: Mapping[str, Mapping[str, Any]]
    acceptance: Mapping[str, Any]


def _claim(root: str, logical: str, codec: str, *keys: str) -> dict[str, Any]:
    return {
        "root": root,
        "logical_path": logical,
        "codec_id": codec,
        "outer_keys": list(keys),
        "inner_keys": [],
        "semantic_claims": [],
    }


def expected_new_claims() -> list[dict[str, Any]]:
    claims = [
        _claim("common", gacha.GACHA_MASTER_LOGICAL, "flat", gacha.GACHA_KEY),
        _claim("common", gacha.FEATURE_LOGICAL, "raw_outer", gacha.GACHA_KEY),
        _claim("common", gacha.RARITY_ODDS_LOGICAL, "raw_outer", gacha.RARITY_ODDS_ID),
        _claim("common", gacha.CHARACTER_3_ODDS_LOGICAL, "raw_outer", gacha.CHARACTER_3_ODDS_ID),
        _claim("common", gacha.CHARACTER_4_ODDS_LOGICAL, "raw_outer", gacha.CHARACTER_4_ODDS_ID),
        _claim("common", gacha.CHARACTER_5_ODDS_LOGICAL, "raw_outer", gacha.CHARACTER_5_ODDS_ID),
        _claim("common", gacha.RICH_TEXT_MASTER_LOGICAL, "flat", gacha.RICH_TEXT_ID),
    ]
    claims.extend(
        _claim("server", logical, "json_object", gacha.GACHA_KEY)
        for logical in gacha.SERVER_OUTPUT_PATHS
    )
    claims.extend((
        _claim("common", ITEM_LOGICAL, "flat", "999013", "999014"),
        _claim("server", ITEM_IDS_LOGICAL, "json_integer_set", "999013", "999014"),
        _claim("common", SHOP_CLIENT_LOGICAL, "flat", "9700116", "9700117"),
        _claim(
            "server", SHOP_SERVER_LOGICAL, "json_event_shop_products",
            "9700116", "9700117",
        ),
        _claim("server", SHOP_ID_MAP_LOGICAL, "json_object", "9700116", "9700117"),
        _claim("common", ROGUE_EVENT_CLIENT_LOGICAL, "flat", "700099"),
        _claim("server", ROGUE_EVENT_LOGICAL, "json_rogue_events", "700099"),
    ))
    return claims


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PackageAssemblyError("package evidence is not strict JSON") from exc


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _valid_hash(value: object) -> bool:
    return isinstance(value, str) and _HASH_RE.fullmatch(value) is not None


def _payload_hashes(
    roots: Mapping[str, Mapping[str, bytes]],
) -> dict[str, dict[str, str]]:
    return {
        root: {
            logical: _sha(raw) for logical, raw in sorted(roots[root].items())
        }
        for root in ROOT_NAMES
    }


def _flat_hashes(
    roots: Mapping[str, Mapping[str, bytes]],
) -> dict[str, str]:
    return {
        f"{root}:{logical}": _sha(raw)
        for root in ROOT_NAMES for logical, raw in sorted(roots[root].items())
    }


def _accepted_asset_replacements(
    input_sha256: Mapping[str, str],
    component_reports: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    ticket_report = component_reports.get("tickets")
    if not isinstance(ticket_report, Mapping):
        raise PackageAssemblyError("ticket shared asset report is missing")
    raw_replacements = ticket_report.get("shared_asset_replacements")
    expected_paths = (ITEM_SHEET_LOGICAL, ITEM_ATLAS_LOGICAL)
    if not isinstance(raw_replacements, Mapping) or set(raw_replacements) != set(
        expected_paths
    ):
        raise PackageAssemblyError("ticket shared asset exact paths are not locked")

    accepted: list[dict[str, Any]] = []
    for logical in expected_paths:
        record = raw_replacements[logical]
        if not isinstance(record, Mapping) or set(record) != {
            "before_sha256", "before_size"
        }:
            raise PackageAssemblyError(
                f"ticket shared asset record is not exact: {logical}"
            )
        digest = record.get("before_sha256")
        size = record.get("before_size")
        if not _valid_hash(digest) or type(size) is not int or size < 0:
            raise PackageAssemblyError(
                f"ticket shared asset identity is invalid: {logical}"
            )
        if input_sha256.get(f"tickets:{logical}") != digest:
            raise PackageAssemblyError(
                f"ticket shared asset input hash binding drift: {logical}"
            )
        accepted.append({
            "root": "common",
            "logical_path": logical,
            "before_sha256": digest,
            "before_size": size,
        })

    preservation = ticket_report.get("shared_asset_preservation")
    if not isinstance(preservation, Mapping) or set(preservation) != {
        "sheet_prefix", "atlas_prefix"
    }:
        raise PackageAssemblyError("ticket shared asset prefix preservation is absent")
    sheet = preservation["sheet_prefix"]
    if not isinstance(sheet, Mapping) or set(sheet) != {
        "before_dimensions", "after_dimensions",
        "before_rgba_sha256", "after_prefix_rgba_sha256",
    }:
        raise PackageAssemblyError("ticket sheet prefix preservation is invalid")
    before_dimensions = sheet["before_dimensions"]
    after_dimensions = sheet["after_dimensions"]
    if (
        not isinstance(before_dimensions, list)
        or not isinstance(after_dimensions, list)
        or len(before_dimensions) != 2
        or len(after_dimensions) != 2
        or any(type(value) is not int or value <= 0 for value in before_dimensions)
        or any(type(value) is not int or value <= 0 for value in after_dimensions)
        or after_dimensions
        != [before_dimensions[0], before_dimensions[1] + 22]
        or not _valid_hash(sheet["before_rgba_sha256"])
        or sheet["before_rgba_sha256"] != sheet["after_prefix_rgba_sha256"]
    ):
        raise PackageAssemblyError("ticket sheet prefix preservation drift")

    atlas = preservation["atlas_prefix"]
    if not isinstance(atlas, Mapping) or set(atlas) != {
        "before_entry_count", "after_entry_count",
        "before_entries_sha256", "after_prefix_entries_sha256",
    }:
        raise PackageAssemblyError("ticket atlas prefix preservation is invalid")
    before_count = atlas["before_entry_count"]
    after_count = atlas["after_entry_count"]
    if (
        type(before_count) is not int
        or before_count < 0
        or type(after_count) is not int
        or after_count != before_count + 2
        or not _valid_hash(atlas["before_entries_sha256"])
        or atlas["before_entries_sha256"]
        != atlas["after_prefix_entries_sha256"]
    ):
        raise PackageAssemblyError("ticket atlas prefix preservation drift")
    return accepted


def _validate_source(source: SealedSourcePackage) -> dict[str, Any]:
    manifest = dict(source.manifest)
    if (
        manifest.get("package_id") != PACKAGE_ID
        or manifest.get("character_id") != CHARACTER_ID
        or manifest.get("code_name") != CODE_NAME
        or manifest.get("package_version") != "1.0.0"
        or manifest.get("requires_client_base") != "1.4.346"
    ):
        raise PackageAssemblyError("sealed source package identity/version drift")
    qa = manifest.get("qa")
    if not isinstance(qa, Mapping) or dict(qa) != {
        "delivery_mode": "production",
        "release_ready": True,
        "required_assets_total": 37,
        "required_assets_present": 37,
        "workspace_input_sha256": source.workspace_input_sha256,
    }:
        raise PackageAssemblyError("sealed source package QA binding drift")
    if not _valid_hash(source.workspace_input_sha256) or not _valid_hash(
        source.source_locks_sha256
    ):
        raise PackageAssemblyError("sealed source package hash binding is invalid")
    if (
        source.package_acceptance.get("package_manifest_eligible") is not True
        or source.package_acceptance.get("writes_live") is not False
        or source.skill_follow_gate.get("package_manifest_eligible") is not True
        or source.skill_follow_gate.get("writes_live") is not False
    ):
        raise PackageAssemblyError("sealed source package acceptance is not eligible")
    tables = manifest.get("tables")
    if not isinstance(tables, list):
        raise PackageAssemblyError("sealed source table claims are invalid")
    production = thunder.validate_production_contract(source.roots, tables)
    expected_entries = {
        root: [
            {
                "logical_path": logical,
                "sha256": _sha(raw),
                "size": len(raw),
            }
            for logical, raw in sorted(source.roots[root].items())
        ]
        for root in ROOT_NAMES
    }
    if manifest.get("roots") != expected_entries:
        raise PackageAssemblyError("sealed source manifest payload binding drift")
    return production


def _validate_additions(
    source: SealedSourcePackage, additions: AdditionBundle
) -> list[dict[str, Any]]:
    if set(additions.roots) != set(ROOT_NAMES):
        raise PackageAssemblyError("new payload roots are not exact")
    old_keys = {
        character_pack.windows_logical_path_key(logical): (root, logical)
        for root in ROOT_NAMES for logical in source.roots[root]
    }
    actual_pairs: set[tuple[str, str]] = set()
    for root in ROOT_NAMES:
        files = additions.roots[root]
        if not isinstance(files, Mapping):
            raise PackageAssemblyError(f"new payload root {root} must be a mapping")
        for logical, raw in files.items():
            problem = character_pack.logical_path_problem(logical)
            if problem:
                raise PackageAssemblyError(f"invalid new logical path {logical}: {problem}")
            key = character_pack.windows_logical_path_key(logical)
            if key in old_keys:
                raise PackageAssemblyError(
                    f"new payload aliases old payload: {logical}"
                )
            if not isinstance(raw, bytes):
                raise PackageAssemblyError(f"new payload is not bytes: {logical}")
            actual_pairs.add((root, logical))
    if actual_pairs != set(NEW_PATHS):
        raise PackageAssemblyError(
            "new payload set is not exact: "
            f"missing={sorted(set(NEW_PATHS)-actual_pairs)}, "
            f"extra={sorted(actual_pairs-set(NEW_PATHS))}"
        )
    if [dict(item) for item in additions.table_claims] != expected_new_claims():
        raise PackageAssemblyError("new table claims are not exact")
    if dict(additions.acceptance) != _ACCEPTANCE:
        raise PackageAssemblyError("combined package acceptance is not exact")
    required_components = {"gacha", "tickets", "shop", "drop", "banners"}
    if set(additions.component_reports) != required_components or any(
        not isinstance(report, Mapping) or report.get("writes_live") is not False
        for report in additions.component_reports.values()
    ):
        raise PackageAssemblyError("component acceptance reports are not exact")
    if additions.component_reports["drop"].get(
        "runtime_source_sync"
    ) != DROP_RUNTIME_SOURCE_SYNC:
        raise PackageAssemblyError("drop runtime source sync evidence is not exact")
    if not additions.input_sha256 or any(
        not isinstance(label, str) or not label or not _valid_hash(digest)
        for label, digest in additions.input_sha256.items()
    ):
        raise PackageAssemblyError("input SHA-256 evidence is not exact")
    return _accepted_asset_replacements(
        additions.input_sha256, additions.component_reports
    )


def source_lock_evidence_bytes(source_locks: Mapping[str, Any]) -> bytes:
    from wf_abyss_gacha_package_audit import source_lock_evidence_bytes as encode

    return encode(source_locks)


def build_package_image(
    source: SealedSourcePackage,
    additions: AdditionBundle,
    *,
    generator_git_head: str,
) -> PackageImage:
    """Build and self-audit the complete derived image without filesystem writes."""

    _validate_source(source)
    accepted_asset_replacements = _validate_additions(source, additions)
    if not isinstance(generator_git_head, str) or re.fullmatch(
        r"[0-9a-f]{40}", generator_git_head
    ) is None:
        raise PackageAssemblyError("generator_git_head must be full lowercase hex")

    roots = {
        root: {**source.roots[root], **additions.roots[root]}
        for root in ROOT_NAMES
    }
    source_locks = {
        "schema_version": 1,
        "source_package": {
            "package_id": PACKAGE_ID,
            "package_version": source.manifest["package_version"],
            "requires_client_base": source.manifest["requires_client_base"],
            "manifest_sha256": _sha(character_pack.canonical_manifest_bytes(
                dict(source.manifest)
            )),
            "workspace_input_sha256": source.workspace_input_sha256,
            "source_locks_sha256": source.source_locks_sha256,
            "payload_sha256": _payload_hashes(source.roots),
            "table_claims_sha256": _sha(_canonical(source.manifest["tables"])),
            "package_acceptance": dict(source.package_acceptance),
            "skill_follow_gate": dict(source.skill_follow_gate),
        },
        "input_sha256": dict(sorted(additions.input_sha256.items())),
        "component_reports": {
            name: dict(report)
            for name, report in sorted(additions.component_reports.items())
        },
        "acceptance": dict(additions.acceptance),
        "new_output_sha256": _flat_hashes(additions.roots),
        "writes_live": False,
        "formal_workspace_written": False,
    }
    evidence = source_lock_evidence_bytes(source_locks)
    evidence_sha = _sha(evidence)
    manifest = thunder.build_manifest(
        roots=roots,
        table_claims=[
            *(dict(item) for item in source.manifest["tables"]),
            *(dict(item) for item in additions.table_claims),
        ],
        package_version=PACKAGE_VERSION,
        requires_client_base=REQUIRES_CLIENT_BASE,
        required_capabilities=("content.sync@1",),
        generator_git_head=generator_git_head,
        source_locks_sha256=evidence_sha,
        server_logicals=SERVER_LOGICALS,
    )
    manifest["snapshot"].update({
        "source_package_manifest_sha256": source_locks["source_package"][
            "manifest_sha256"
        ],
        "source_workspace_input_sha256": source.workspace_input_sha256,
        "accepted_asset_replacements": accepted_asset_replacements,
    })
    contract_report = {
        "payload_count": sum(len(files) for files in roots.values()),
        "table_claim_count": len(manifest["tables"]),
        "root_counts": dict(EXPECTED_ROOT_COUNTS),
        "old_payload_exact_count": sum(len(files) for files in source.roots.values()),
        "new_payload_exact_count": sum(
            len(files) for files in additions.roots.values()
        ),
        "old_payloads_byte_exact": True,
    }
    source_report = {
        "schema_version": 1,
        "status": "compiled_in_memory_ready",
        "writes_live": False,
        "formal_workspace_written": False,
        "source_locks": source_locks,
        "source_locks_sha256": evidence_sha,
        "package_contract": contract_report,
        "acceptance": dict(additions.acceptance),
    }
    image = PackageImage(roots, manifest, source_report)
    audit_package_image(image)
    return image


def audit_package_image(image: PackageImage) -> dict[str, Any]:
    from wf_abyss_gacha_package_audit import audit_package_image as audit

    return audit(image)


__all__ = [
    "PACKAGE_ID", "CHARACTER_ID", "CODE_NAME", "ROOT_NAMES",
    "PACKAGE_VERSION", "REQUIRES_CLIENT_BASE", "CONFIRMATION", "NEW_PATHS",
    "DROP_RUNTIME_SOURCE_SYNC",
    "SERVER_LOGICALS", "SOURCE_ROOT_COUNTS", "EXPECTED_ROOT_COUNTS",
    "EXPECTED_PAYLOAD_COUNT", "ROGUE_EVENT_CLIENT_LOGICAL", "PackageAssemblyError",
    "PackageImage", "SealedSourcePackage", "AdditionBundle",
    "expected_new_claims", "source_lock_evidence_bytes", "build_package_image",
    "audit_package_image",
]
