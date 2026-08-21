#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compile and audit the complete thunder-dragon 1.1.6 replacement image."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

import wf_abyss_gacha_package_audit as abyss_audit
import wf_abyss_gacha_banner_compile as banner_compile
import wf_abyss_gacha_package_contract as abyss_contract
import wf_abyss_gacha_contract as gacha_contract
import wf_character_pack as character_pack
import wf_summer_thunder_package_contract as thunder
from wf_summer_thunder_package_sources import (
    _EFFECT_OUTPUT_SHA256,
    _NORMAL_OUTPUT_SHA256,
    _SPECIAL_OUTPUT_SHA256,
)
from wf_thunder_hotfix_package_sources import (
    LockedDonorTemplate,
    SealedHotfixSource,
)
from wf_thunder_hotfix_payloads import (
    repair_gacha_contract,
    repair_normal_and_special,
    repair_travelling_wave_effect,
)
from wf_thunder_hotfix_gacha import GACHA_REPAIR_PATHS
from wf_thunder_hotfix_character import (
    CHARACTER_REPAIR_PATHS,
    repair_character_contract,
)


PACKAGE_ID = thunder.PACKAGE_ID
CHARACTER_ID = thunder.CHARACTER_ID
CODE_NAME = thunder.CODE_NAME
ROOT_NAMES = thunder.ROOT_NAMES
PACKAGE_VERSION = "1.1.6"
# Single flip point: the startpoint-cn client chain version that ships pickup
# character 139997 (泳皇女EX).  Every client-base claim below derives from it.
# The character package strand anchors on character-releases/active.json
# (base_version 1.4.324), so its published edge is 1.4.324 -> 1.4.325.
CLIENT_BASE_WITH_SWIM_PRINCESS_EX = "1.4.325"
REQUIRES_CLIENT_BASE = CLIENT_BASE_WITH_SWIM_PRINCESS_EX
SHARED_ASSET_BASELINE_CLIENT_VERSION = CLIENT_BASE_WITH_SWIM_PRINCESS_EX
CONFIRMATION = "ASSEMBLE_CNMOD_THUNDER_DRAGON_ABYSS_GACHA_1_1_6"
SOURCE_START_DATE = "2026-08-15 00:00:00"

_PIXEL_PREFIX = f"character/{CODE_NAME}/pixelart"
_EFFECT_PARTS = (
    f"battle/effect/skill_unique/{CODE_NAME}/fan_lightning/"
    "fan_lightning_wave.parts.amf3.deflate"
)
CHANGED_PAYLOADS = (
    ("common", f"{_PIXEL_PREFIX}/sprite_sheet.atlas.amf3.deflate"),
    ("common", f"{_PIXEL_PREFIX}/special_sprite_sheet.atlas.amf3.deflate"),
    ("common", _EFFECT_PARTS),
    *(
        (
            "server" if logical == "cdndata/character_text.json" else "common",
            logical,
        )
        for logical in CHARACTER_REPAIR_PATHS
    ),
    *(
        (
            "server" if logical in {"cdndata/gacha.json", "gacha.json"}
            else "common",
            logical,
        )
        for logical in GACHA_REPAIR_PATHS
    ),
)
ADDED_PAYLOADS = (
    ("common", gacha_contract.LIST_BANNER_PAYLOAD_LOGICAL),
    ("medium", gacha_contract.TOP_BANNER_PAYLOAD_LOGICAL),
)
CURRENT_SHARED_ASSET_BASELINE = (
    {
        "root": "common",
        "logical_path": "item/sprite_sheet.atlas.amf3.deflate",
        "before_sha256": (
            "34526c17de84f53e341324a3dd4ea63915987255f118e669ccda280db8abb2af"
        ),
        "before_size": 15925,
    },
    {
        "root": "common",
        "logical_path": "item/sprite_sheet.png",
        "before_sha256": (
            "13039ef5b3fe8429a4f356dc770620c4f3ccb273ab960a81a06d4fe0960abfc7"
        ),
        "before_size": 739512,
    },
)
_SOURCE_COUNTS = {"common": 67, "medium": 25, "android": 2, "server": 11}
_EXPECTED_COUNTS = {"common": 68, "medium": 26, "android": 2, "server": 11}
_ACCEPTANCE = {
    "pixel_anchor_fixed": True,
    "special_alias_regenerated": True,
    "effect_single_anchor_fixed": True,
    "gacha_schedule_game_clock_compatible": True,
    "gacha_standard_rank_rates": [50, 250, 700],
    "gacha_limited_pickup_count": len(gacha_contract.CHARACTER_IDS),
    "gacha_limited_rate_total_ratio": [1, 100],
    "gacha_limited_rate_each_ratio": [1, 900],
    "gacha_exchange_required_points": {"limited": 250, "standard": 250},
    "gacha_exchangeable_limited_count": len(
        gacha_contract.EXCHANGEABLE_CHARACTER_IDS
    ),
    "gacha_non_exchangeable_limited_ids": list(
        gacha_contract.NON_EXCHANGEABLE_CHARACTER_IDS
    ),
    "gacha_exchangeable_standard_count": 4,
    "gacha_ticket_only_payment": True,
    "gacha_exchange_button_enabled": True,
    "gacha_ticket_exec_types": {"single": 3, "ten": 4},
    "gacha_portrait_banner": {
        "logical_path": gacha_contract.TOP_BANNER_PAYLOAD_LOGICAL,
        "width": 1440,
        "height": 1789,
    },
    "gacha_list_banner": {
        "logical_path": gacha_contract.LIST_BANNER_PAYLOAD_LOGICAL,
        "width": 510,
        "height": 180,
    },
    "unchanged_payload_count": 88,
    "changed_payload_count": 17,
    "added_payload_count": 2,
    "package_manifest_eligible": True,
    "writes_live": False,
}

PackageAssemblyError = thunder.PackageAssemblyError
PackageImage = thunder.PackageImage


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


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
        raise PackageAssemblyError("hotfix evidence is not strict JSON") from exc


def source_lock_evidence_bytes(source_locks: Mapping[str, Any]) -> bytes:
    expected = {
        "schema_version", "source_package", "repair_inputs", "repair_reports",
        "changed_payloads", "added_payloads", "acceptance", "writes_live",
        "formal_workspace_written",
    }
    if (
        set(source_locks) != expected
        or source_locks.get("schema_version") != 1
        or source_locks.get("writes_live") is not False
        or source_locks.get("formal_workspace_written") is not False
    ):
        raise PackageAssemblyError("hotfix source-lock sections are not exact")
    return _canonical(source_locks) + b"\n"


def _manifest_entries(
    roots: Mapping[str, Mapping[str, bytes]],
) -> dict[str, list[dict[str, Any]]]:
    return {
        root: [
            {
                "logical_path": logical,
                "sha256": _sha(raw),
                "size": len(raw),
            }
            for logical, raw in sorted(roots[root].items())
        ]
        for root in ROOT_NAMES
    }


def _source_payload_hashes(
    source: SealedHotfixSource,
) -> dict[str, dict[str, str]]:
    return {
        root: {
            logical: _sha(raw) for logical, raw in sorted(source.roots[root].items())
        }
        for root in ROOT_NAMES
    }


def _validate_source(source: SealedHotfixSource) -> None:
    if not isinstance(source, SealedHotfixSource) or set(source.roots) != set(
        ROOT_NAMES
    ):
        raise PackageAssemblyError("hotfix source package type/roots are invalid")
    identity = {
        "package_id": PACKAGE_ID,
        "character_id": CHARACTER_ID,
        "code_name": CODE_NAME,
        "package_version": "1.1.0",
        "requires_client_base": "1.4.347",
    }
    if any(source.manifest.get(key) != value for key, value in identity.items()):
        raise PackageAssemblyError("hotfix source package identity drift")
    if (
        {root: len(source.roots[root]) for root in ROOT_NAMES} != _SOURCE_COUNTS
        or len(source.manifest.get("tables", [])) != 39
    ):
        raise PackageAssemblyError("hotfix source inventory drift")
    expected_entries = _manifest_entries(source.roots)
    if source.manifest.get("roots") != expected_entries:
        raise PackageAssemblyError("hotfix source payload binding drift")
    if source.manifest_sha256 != _sha(
        character_pack.canonical_manifest_bytes(dict(source.manifest))
    ):
        raise PackageAssemblyError("hotfix source manifest identity drift")
    if source.evidence_sha256 != _sha(
        abyss_audit.source_lock_evidence_bytes(source.source_locks)
    ):
        raise PackageAssemblyError("hotfix source evidence identity drift")
    for replacement in CURRENT_SHARED_ASSET_BASELINE:
        raw = source.roots[replacement["root"]].get(replacement["logical_path"])
        if (
            raw is None
            or len(raw) != replacement["before_size"]
            or _sha(raw) != replacement["before_sha256"]
        ):
            raise PackageAssemblyError(
                "hotfix source shared asset does not match current "
                f"{SHARED_ASSET_BASELINE_CLIENT_VERSION} baseline"
            )


def _validate_donor(donor: LockedDonorTemplate) -> None:
    if not isinstance(donor, LockedDonorTemplate) or set(donor.files) != set(
        donor.input_sha256
    ):
        raise PackageAssemblyError("hotfix donor template contract drift")
    for logical, raw in donor.files.items():
        if _sha(raw) != donor.input_sha256[logical]:
            raise PackageAssemblyError(f"hotfix donor SHA-256 drift: {logical}")


def compile_hotfix_package(
    source: SealedHotfixSource,
    donor: LockedDonorTemplate,
    *,
    generator_git_head: str,
) -> PackageImage:
    """Compile the full replacement image with seventeen changes and one new banner."""

    _validate_source(source)
    _validate_donor(donor)
    if not isinstance(generator_git_head, str) or re.fullmatch(
        r"[0-9a-f]{40}", generator_git_head
    ) is None:
        raise PackageAssemblyError("generator_git_head must be full lowercase hex")

    normal = {
        logical: source.roots["common"][logical]
        for logical, _digest in _NORMAL_OUTPUT_SHA256
    }
    special = {
        logical: source.roots["common"][logical]
        for logical, _digest in _SPECIAL_OUTPUT_SHA256
    }
    try:
        repaired_normal, repaired_special, pixel_report = repair_normal_and_special(
            normal,
            special,
            donor.files,
            source_prefix="character/thunder_dragon/pixelart",
            target_prefix=_PIXEL_PREFIX,
            expected_normal_sha256=dict(_NORMAL_OUTPUT_SHA256),
            expected_special_sha256=dict(_SPECIAL_OUTPUT_SHA256),
            expected_template_sha256=donor.input_sha256,
        )
        effect = {
            logical: source.roots["common"][logical]
            for logical, _digest in _EFFECT_OUTPUT_SHA256
        }
        repaired_effect, effect_report = repair_travelling_wave_effect(
            effect, expected_sha256=dict(_EFFECT_OUTPUT_SHA256)
        )
        character_source = {
            logical: source.roots[
                "server" if logical == "cdndata/character_text.json" else "common"
            ][logical]
            for logical in CHARACTER_REPAIR_PATHS
        }
        repaired_character, character_report = repair_character_contract(
            character_source
        )
        all_source = {
            **source.roots["common"],
            **source.roots["server"],
        }
        repaired_gacha, gacha_report = repair_gacha_contract(
            all_source, expected_start_date=SOURCE_START_DATE
        )
        banner_result = banner_compile.compile_locked_banners()
    except (KeyError, TypeError, ValueError) as exc:
        raise PackageAssemblyError(f"hotfix payload compilation failed: {exc}") from exc

    candidates: dict[tuple[str, str], bytes] = {
        ("common", CHANGED_PAYLOADS[0][1]): repaired_normal[CHANGED_PAYLOADS[0][1]],
        ("common", CHANGED_PAYLOADS[1][1]): repaired_special[CHANGED_PAYLOADS[1][1]],
        ("common", CHANGED_PAYLOADS[2][1]): repaired_effect[CHANGED_PAYLOADS[2][1]],
    }
    for root, logical in CHANGED_PAYLOADS[3:3 + len(CHARACTER_REPAIR_PATHS)]:
        candidates[(root, logical)] = repaired_character[logical]
    for root, logical in CHANGED_PAYLOADS[3 + len(CHARACTER_REPAIR_PATHS):]:
        candidates[(root, logical)] = repaired_gacha[logical]
    if tuple(candidates) != CHANGED_PAYLOADS:
        raise PackageAssemblyError("hotfix changed payload set/order drift")
    roots = {root: dict(source.roots[root]) for root in ROOT_NAMES}
    change_records = []
    for root, logical in CHANGED_PAYLOADS:
        before = roots[root][logical]
        after = candidates[(root, logical)]
        if before == after:
            raise PackageAssemblyError(f"hotfix payload did not change: {root}:{logical}")
        roots[root][logical] = after
        change_records.append({
            "root": root,
            "logical_path": logical,
            "before_sha256": _sha(before),
            "before_size": len(before),
            "after_sha256": _sha(after),
            "after_size": len(after),
        })
    added_records = []
    for root, logical in ADDED_PAYLOADS:
        if logical in roots[root]:
            raise PackageAssemblyError(
                f"hotfix added payload already exists: {root}:{logical}"
            )
        raw = banner_result.files.get(logical)
        if not isinstance(raw, bytes):
            raise PackageAssemblyError(
                f"hotfix added banner is missing: {root}:{logical}"
            )
        roots[root][logical] = raw
        added_records.append({
            "root": root,
            "logical_path": logical,
            "after_sha256": _sha(raw),
            "after_size": len(raw),
        })

    source_locks = {
        "schema_version": 1,
        "source_package": {
            "package_id": PACKAGE_ID,
            "package_version": "1.1.0",
            "requires_client_base": "1.4.347",
            "manifest_sha256": source.manifest_sha256,
            "workspace_input_sha256": source.workspace_input_sha256,
            "evidence_sha256": source.evidence_sha256,
            "payload_sha256": _source_payload_hashes(source),
            "payload_size": {
                root: {
                    logical: len(raw)
                    for logical, raw in sorted(source.roots[root].items())
                }
                for root in ROOT_NAMES
            },
            "table_claims_sha256": _sha(_canonical(source.manifest["tables"])),
        },
        "repair_inputs": {
            "donor_report_sha256": donor.report_sha256,
            "donor_template_sha256": dict(sorted(donor.input_sha256.items())),
            "normal_v3_sha256": dict(_NORMAL_OUTPUT_SHA256),
            "special_v3_sha256": dict(_SPECIAL_OUTPUT_SHA256),
            "effect_v1_sha256": dict(_EFFECT_OUTPUT_SHA256),
            "source_start_date": SOURCE_START_DATE,
            "standard_pool_donor_id": gacha_contract.STANDARD_POOL_DONOR_ID,
            "exchange_required_points": {"limited": 250, "standard": 250},
            "portrait_banner_source_sha256": next(
                spec.source_sha256 for spec in banner_compile.LOCKED_BANNERS
                if spec.logical_path == gacha_contract.TOP_BANNER_PAYLOAD_LOGICAL
            ),
            "portrait_banner_dimensions": [1440, 1789],
            "list_banner_source_sha256": next(
                spec.source_sha256 for spec in banner_compile.LOCKED_BANNERS
                if spec.logical_path == gacha_contract.LIST_BANNER_PAYLOAD_LOGICAL
            ),
            "list_banner_dimensions": [510, 180],
            "shared_asset_baseline": [
                dict(item) for item in CURRENT_SHARED_ASSET_BASELINE
            ],
        },
        "repair_reports": {
            "pixel": pixel_report,
            "effect": effect_report,
            "character": character_report,
            "gacha": gacha_report,
            "banner": dict(banner_result.report),
        },
        "changed_payloads": change_records,
        "added_payloads": added_records,
        "acceptance": dict(_ACCEPTANCE),
        "writes_live": False,
        "formal_workspace_written": False,
    }
    evidence = source_lock_evidence_bytes(source_locks)
    evidence_sha = _sha(evidence)
    manifest = thunder.build_manifest(
        roots=roots,
        table_claims=source.manifest["tables"],
        package_version=PACKAGE_VERSION,
        requires_client_base=REQUIRES_CLIENT_BASE,
        required_capabilities=("content.sync@1",),
        generator_git_head=generator_git_head,
        source_locks_sha256=evidence_sha,
        server_logicals=abyss_contract.SERVER_LOGICALS,
    )
    manifest["snapshot"].update({
        "source_package_manifest_sha256": source.manifest_sha256,
        "source_workspace_input_sha256": source.workspace_input_sha256,
        "accepted_asset_replacements": [
            dict(item) for item in CURRENT_SHARED_ASSET_BASELINE
        ],
    })
    report = {
        "schema_version": 1,
        "status": "compiled_in_memory_ready",
        "writes_live": False,
        "formal_workspace_written": False,
        "source_locks": source_locks,
        "source_locks_sha256": evidence_sha,
        "acceptance": dict(_ACCEPTANCE),
    }
    image = PackageImage(roots, manifest, report)
    audit_hotfix_package(image)
    return image


def audit_hotfix_package(image: PackageImage) -> dict[str, Any]:
    from wf_thunder_hotfix_package_audit import audit_hotfix_package as audit

    return audit(image)


__all__ = [
    "PACKAGE_ID", "CHARACTER_ID", "CODE_NAME", "ROOT_NAMES",
    "PACKAGE_VERSION", "CLIENT_BASE_WITH_SWIM_PRINCESS_EX",
    "REQUIRES_CLIENT_BASE", "SHARED_ASSET_BASELINE_CLIENT_VERSION",
    "CONFIRMATION",
    "CHANGED_PAYLOADS", "ADDED_PAYLOADS", "CURRENT_SHARED_ASSET_BASELINE",
    "PackageAssemblyError", "PackageImage", "source_lock_evidence_bytes",
    "compile_hotfix_package", "audit_hotfix_package",
]
