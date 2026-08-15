#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compile and audit the complete thunder-dragon 1.1.1 replacement image."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

import wf_abyss_gacha_package_audit as abyss_audit
import wf_abyss_gacha_package_contract as abyss_contract
import wf_character_pack as character_pack
from wf_pixelart_compile import SUMMER_THUNDER_TEMPLATE_SHA256
import wf_summer_thunder_package_contract as thunder
from wf_summer_thunder_package_sources import (
    _EFFECT_OUTPUT_SHA256,
    _NORMAL_OUTPUT_SHA256,
    _SPECIAL_OUTPUT_SHA256,
    LOCKED_NORMAL_V3,
)
from wf_thunder_hotfix_package_sources import (
    LockedDonorTemplate,
    SealedHotfixSource,
)
from wf_thunder_hotfix_payloads import (
    repair_gacha_schedule,
    repair_normal_and_special,
    repair_travelling_wave_effect,
)


PACKAGE_ID = thunder.PACKAGE_ID
CHARACTER_ID = thunder.CHARACTER_ID
CODE_NAME = thunder.CODE_NAME
ROOT_NAMES = thunder.ROOT_NAMES
PACKAGE_VERSION = "1.1.1"
REQUIRES_CLIENT_BASE = "1.4.348"
CONFIRMATION = "ASSEMBLE_CNMOD_THUNDER_DRAGON_ABYSS_GACHA_1_1_1"
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
    ("common", "master/gacha/gacha.orderedmap"),
    ("server", "cdndata/gacha.json"),
    ("server", "gacha.json"),
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
_EXPECTED_COUNTS = {"common": 67, "medium": 25, "android": 2, "server": 11}
_ACCEPTANCE = {
    "pixel_anchor_fixed": True,
    "special_alias_regenerated": True,
    "effect_single_anchor_fixed": True,
    "gacha_schedule_game_clock_compatible": True,
    "unchanged_payload_count": 99,
    "changed_payload_count": 6,
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
        "changed_payloads", "acceptance", "writes_live",
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
        {root: len(source.roots[root]) for root in ROOT_NAMES} != _EXPECTED_COUNTS
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
                "hotfix source shared asset does not match current 1.4.348 baseline"
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
    """Compile the full replacement image while changing exactly six payloads."""

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
        all_source = {
            **source.roots["common"],
            **source.roots["server"],
        }
        repaired_gacha, gacha_report = repair_gacha_schedule(
            all_source, expected_start_date=SOURCE_START_DATE
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise PackageAssemblyError(f"hotfix payload compilation failed: {exc}") from exc

    candidates = {
        ("common", CHANGED_PAYLOADS[0][1]): repaired_normal[CHANGED_PAYLOADS[0][1]],
        ("common", CHANGED_PAYLOADS[1][1]): repaired_special[CHANGED_PAYLOADS[1][1]],
        ("common", CHANGED_PAYLOADS[2][1]): repaired_effect[CHANGED_PAYLOADS[2][1]],
        ("common", CHANGED_PAYLOADS[3][1]): repaired_gacha[CHANGED_PAYLOADS[3][1]],
        ("server", CHANGED_PAYLOADS[4][1]): repaired_gacha[CHANGED_PAYLOADS[4][1]],
        ("server", CHANGED_PAYLOADS[5][1]): repaired_gacha[CHANGED_PAYLOADS[5][1]],
    }
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
            "shared_asset_baseline": [
                dict(item) for item in CURRENT_SHARED_ASSET_BASELINE
            ],
        },
        "repair_reports": {
            "pixel": pixel_report,
            "effect": effect_report,
            "gacha": gacha_report,
        },
        "changed_payloads": change_records,
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
    """Recompute the full image, evidence, and exact six-change contract."""

    if not isinstance(image, PackageImage) or set(image.roots) != set(ROOT_NAMES):
        raise PackageAssemblyError("hotfix package image type/roots are invalid")
    manifest = image.manifest
    identity = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "character_id": CHARACTER_ID,
        "code_name": CODE_NAME,
        "package_version": PACKAGE_VERSION,
        "requires_client_base": REQUIRES_CLIENT_BASE,
        "required_capabilities": ["content.sync@1"],
        "skills": {},
        "unique_condition": {},
    }
    if any(manifest.get(key) != value for key, value in identity.items()):
        raise PackageAssemblyError("hotfix manifest identity drift")
    if manifest.get("roots") != _manifest_entries(image.roots):
        raise PackageAssemblyError("hotfix manifest payload binding drift")
    root_report = thunder.validate_root_contract(
        image.roots, server_logicals=abyss_contract.SERVER_LOGICALS
    )
    if (
        root_report["root_counts"] != _EXPECTED_COUNTS
        or root_report["payload_count"] != 105
        or len(manifest.get("tables", [])) != 39
    ):
        raise PackageAssemblyError("hotfix inventory/count drift")
    report = image.source_report
    locks = report.get("source_locks") if isinstance(report, Mapping) else None
    if (
        report.get("schema_version") != 1
        or report.get("status") != "compiled_in_memory_ready"
        or report.get("writes_live") is not False
        or report.get("formal_workspace_written") is not False
        or report.get("acceptance") != _ACCEPTANCE
        or not isinstance(locks, Mapping)
    ):
        raise PackageAssemblyError("hotfix source report drift")
    evidence_sha = _sha(source_lock_evidence_bytes(locks))
    snapshot = manifest.get("snapshot")
    if (
        report.get("source_locks_sha256") != evidence_sha
        or not isinstance(snapshot, Mapping)
        or snapshot.get("source_locks_sha256") != evidence_sha
        or snapshot.get("accepted_asset_replacements")
        != [dict(item) for item in CURRENT_SHARED_ASSET_BASELINE]
    ):
        raise PackageAssemblyError("hotfix evidence/snapshot binding drift")
    source_record = locks.get("source_package")
    changes = locks.get("changed_payloads")
    if not isinstance(source_record, Mapping) or not isinstance(changes, list):
        raise PackageAssemblyError("hotfix source/change evidence is missing")
    source_hashes = source_record.get("payload_sha256")
    source_sizes = source_record.get("payload_size")
    if (
        not isinstance(source_hashes, Mapping)
        or set(source_hashes) != set(ROOT_NAMES)
        or not isinstance(source_sizes, Mapping)
        or set(source_sizes) != set(ROOT_NAMES)
    ):
        raise PackageAssemblyError("hotfix source payload evidence drift")
    if _sha(_canonical(manifest["tables"])) != source_record.get(
        "table_claims_sha256"
    ):
        raise PackageAssemblyError("hotfix table claims changed")
    repair_inputs = locks.get("repair_inputs")
    if not isinstance(repair_inputs, Mapping) or repair_inputs != {
        "donor_report_sha256": LOCKED_NORMAL_V3.report_sha256,
        "donor_template_sha256": dict(sorted(SUMMER_THUNDER_TEMPLATE_SHA256.items())),
        "normal_v3_sha256": dict(_NORMAL_OUTPUT_SHA256),
        "special_v3_sha256": dict(_SPECIAL_OUTPUT_SHA256),
        "effect_v1_sha256": dict(_EFFECT_OUTPUT_SHA256),
        "source_start_date": SOURCE_START_DATE,
        "shared_asset_baseline": [
            dict(item) for item in CURRENT_SHARED_ASSET_BASELINE
        ],
    }:
        raise PackageAssemblyError("hotfix repair input identity drift")
    repair_reports = locks.get("repair_reports")
    if not isinstance(repair_reports, Mapping) or set(repair_reports) != {
        "pixel", "effect", "gacha"
    }:
        raise PackageAssemblyError("hotfix repair reports are missing")
    pixel_report = repair_reports["pixel"]
    effect_report = repair_reports["effect"]
    gacha_report = repair_reports["gacha"]
    if (
        not isinstance(pixel_report, Mapping)
        or pixel_report.get("status") != "repaired_official_dragon_pivots"
        or pixel_report.get("writes_live") is not False
        or pixel_report.get("official_anchor_records") != 9
        or pixel_report.get("tick_32_source") != "base_0002"
        or not isinstance(effect_report, Mapping)
        or effect_report.get("status") != "repaired_single_anchor_application"
        or effect_report.get("writes_live") is not False
        or effect_report.get("root_identity_transform") != 1
        or effect_report.get("child_anchor_layers") != 10
        or not isinstance(gacha_report, Mapping)
        or gacha_report.get("status") != "repaired_game_clock_schedule"
        or gacha_report.get("writes_live") is not False
        or gacha_report.get("source_start_date") != SOURCE_START_DATE
        or gacha_report.get("start_date") != "2020-12-31 12:00:00"
        or gacha_report.get("changed_payload_count") != 3
    ):
        raise PackageAssemblyError("hotfix repair report semantic drift")
    change_by_path = {}
    for record in changes:
        if not isinstance(record, Mapping):
            raise PackageAssemblyError("hotfix change record is invalid")
        key = (record.get("root"), record.get("logical_path"))
        if key in change_by_path:
            raise PackageAssemblyError("hotfix duplicate change record")
        change_by_path[key] = record
    if tuple(change_by_path) != CHANGED_PAYLOADS:
        raise PackageAssemblyError("hotfix changed payload evidence is not exact")
    for root in ROOT_NAMES:
        root_hashes = source_hashes.get(root)
        root_sizes = source_sizes.get(root)
        if (
            not isinstance(root_hashes, Mapping)
            or set(root_hashes) != set(image.roots[root])
            or not isinstance(root_sizes, Mapping)
            or set(root_sizes) != set(image.roots[root])
        ):
            raise PackageAssemblyError("hotfix source payload path set drift")
        for logical, raw in image.roots[root].items():
            key = (root, logical)
            if key in change_by_path:
                record = change_by_path[key]
                if (
                    record.get("before_sha256") != root_hashes[logical]
                    or record.get("before_size") != root_sizes[logical]
                    or record.get("after_sha256") != _sha(raw)
                    or record.get("after_size") != len(raw)
                    or record.get("before_sha256") == record.get("after_sha256")
                ):
                    raise PackageAssemblyError(
                        f"hotfix changed payload binding drift: {root}:{logical}"
                    )
            elif _sha(raw) != root_hashes[logical]:
                raise PackageAssemblyError(
                    f"hotfix unexpected change outside allowlist: {root}:{logical}"
                )
    if locks.get("acceptance") != _ACCEPTANCE:
        raise PackageAssemblyError("hotfix acceptance drift")
    return {
        "integrity_ready": True,
        "apply_ready": True,
        "payload_count": root_report["payload_count"],
        "table_claim_count": len(manifest["tables"]),
        "root_counts": root_report["root_counts"],
        "changed_payload_count": len(CHANGED_PAYLOADS),
        "changed_payloads": list(CHANGED_PAYLOADS),
        "unchanged_payload_count": 99,
        "accepted_asset_replacements": [
            dict(item) for item in CURRENT_SHARED_ASSET_BASELINE
        ],
        "writes_live": False,
    }


__all__ = [
    "PACKAGE_ID", "CHARACTER_ID", "CODE_NAME", "ROOT_NAMES",
    "PACKAGE_VERSION", "REQUIRES_CLIENT_BASE", "CONFIRMATION",
    "CHANGED_PAYLOADS", "CURRENT_SHARED_ASSET_BASELINE",
    "PackageAssemblyError", "PackageImage", "source_lock_evidence_bytes",
    "compile_hotfix_package", "audit_hotfix_package",
]
