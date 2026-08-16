#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent full-image audit for the thunder-dragon 1.1.6 hotfix."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import wf_abyss_gacha_package_contract as abyss_contract
import wf_abyss_gacha_banner_compile as banner_compile
import wf_abyss_gacha_contract as gacha_contract
from wf_pixelart_compile import SUMMER_THUNDER_TEMPLATE_SHA256
import wf_summer_thunder_package_contract as thunder
from wf_summer_thunder_package_sources import (
    _EFFECT_OUTPUT_SHA256,
    _NORMAL_OUTPUT_SHA256,
    _SPECIAL_OUTPUT_SHA256,
    LOCKED_NORMAL_V3,
)
import wf_thunder_hotfix_package as contract


def _repair_evidence(locks: Mapping[str, Any]) -> None:
    expected_inputs = {
        "donor_report_sha256": LOCKED_NORMAL_V3.report_sha256,
        "donor_template_sha256": dict(sorted(SUMMER_THUNDER_TEMPLATE_SHA256.items())),
        "normal_v3_sha256": dict(_NORMAL_OUTPUT_SHA256),
        "special_v3_sha256": dict(_SPECIAL_OUTPUT_SHA256),
        "effect_v1_sha256": dict(_EFFECT_OUTPUT_SHA256),
        "source_start_date": contract.SOURCE_START_DATE,
        "standard_pool_donor_id": "700004",
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
            dict(item) for item in contract.CURRENT_SHARED_ASSET_BASELINE
        ],
    }
    if locks.get("repair_inputs") != expected_inputs:
        raise contract.PackageAssemblyError("hotfix repair input identity drift")
    reports = locks.get("repair_reports")
    if not isinstance(reports, Mapping) or set(reports) != {
        "pixel", "effect", "character", "gacha", "banner"
    }:
        raise contract.PackageAssemblyError("hotfix repair reports are missing")
    pixel = reports["pixel"]
    effect = reports["effect"]
    character = reports["character"]
    gacha = reports["gacha"]
    banner = reports["banner"]
    if (
        not isinstance(pixel, Mapping)
        or pixel.get("status") != "repaired_official_dragon_pivots"
        or pixel.get("writes_live") is not False
        or pixel.get("official_anchor_records") != 9
        or pixel.get("tick_32_source") != "base_0002"
        or not isinstance(effect, Mapping)
        or effect.get("status") != "repaired_single_anchor_application"
        or effect.get("writes_live") is not False
        or effect.get("root_identity_transform") != 1
        or effect.get("child_anchor_layers") != 10
        or not isinstance(character, Mapping)
        or character.get("status") != "recompiled_summer_thunder_character_contract"
        or character.get("changed_payload_count") != 6
        or character.get("unique_condition_duration_frames") != 600
        or character.get("leader_paralysis_duration_frames") != 180
        or character.get("ability3_other_gauge_percent") != 25
        or character.get("ability4_self_gauge_percent") != 100
        or character.get("ability5_thunder_attack_percent") != 90
        or character.get("ability5_thunder_ability_damage_percent") != 90
        or character.get("ability6_self_charge_speed_percent") != 15
        or character.get("skill_description_extra_multiplier_mentions") != 0
        or character.get("writes_live") is not False
        or not isinstance(gacha, Mapping)
        or gacha.get("status") != "repaired_ticket_only_pool_exchange_contract"
        or gacha.get("writes_live") is not False
        or gacha.get("source_start_date") != contract.SOURCE_START_DATE
        or gacha.get("start_date") != "2020-12-31 12:00:00"
        or gacha.get("rank_rates") != [50, 250, 700]
        or gacha.get("guarantee_rarity") != 4
        or gacha.get("exchange_required_points")
        != {"limited": 250, "standard": 250}
        or gacha.get("limited_pickup_count") != 9
        or gacha.get("exchangeable_limited_count") != 8
        or gacha.get("non_exchangeable_limited_count") != 1
        or gacha.get("non_exchangeable_limited_ids") != [139997]
        or gacha.get("limited_rate_total_ratio") != [1, 100]
        or gacha.get("limited_rate_each_ratio") != [1, 900]
        or gacha.get("exchangeable_standard_count") != 4
        or gacha.get("page_kind") != 2
        or gacha.get("ticket_exec_types") != {"single": 3, "ten": 4}
        or gacha.get("changed_payload_count") != 8
        or not isinstance(banner, Mapping)
        or banner.get("status") != "compiled_wf_storage_banners"
        or banner.get("package_manifest_eligible") is not True
        or banner.get("writes_live") is not False
        or banner.get("payload_count") != 2
        or banner.get("logical_paths") != sorted({
            gacha_contract.LIST_BANNER_PAYLOAD_LOGICAL,
            gacha_contract.TOP_BANNER_PAYLOAD_LOGICAL,
        })
    ):
        raise contract.PackageAssemblyError("hotfix repair report semantic drift")


def audit_hotfix_package(image: contract.PackageImage) -> dict[str, Any]:
    """Recompute the full image, evidence, seventeen changes, and two additions."""

    if not isinstance(image, contract.PackageImage) or set(image.roots) != set(
        contract.ROOT_NAMES
    ):
        raise contract.PackageAssemblyError("hotfix package image type/roots are invalid")
    manifest = image.manifest
    identity = {
        "schema_version": 1, "package_id": contract.PACKAGE_ID,
        "character_id": contract.CHARACTER_ID, "code_name": contract.CODE_NAME,
        "package_version": contract.PACKAGE_VERSION,
        "requires_client_base": contract.REQUIRES_CLIENT_BASE,
        "required_capabilities": ["content.sync@1"], "skills": {},
        "unique_condition": {},
    }
    if any(manifest.get(key) != value for key, value in identity.items()):
        raise contract.PackageAssemblyError("hotfix manifest identity drift")
    if manifest.get("roots") != contract._manifest_entries(image.roots):
        raise contract.PackageAssemblyError("hotfix manifest payload binding drift")
    root_report = thunder.validate_root_contract(
        image.roots, server_logicals=abyss_contract.SERVER_LOGICALS
    )
    if (
        root_report["root_counts"] != contract._EXPECTED_COUNTS
        or root_report["payload_count"] != 107
        or len(manifest.get("tables", [])) != 39
    ):
        raise contract.PackageAssemblyError("hotfix inventory/count drift")
    report = image.source_report
    locks = report.get("source_locks") if isinstance(report, Mapping) else None
    if (
        report.get("schema_version") != 1
        or report.get("status") != "compiled_in_memory_ready"
        or report.get("writes_live") is not False
        or report.get("formal_workspace_written") is not False
        or report.get("acceptance") != contract._ACCEPTANCE
        or not isinstance(locks, Mapping)
    ):
        raise contract.PackageAssemblyError("hotfix source report drift")
    evidence_sha = contract._sha(contract.source_lock_evidence_bytes(locks))
    snapshot = manifest.get("snapshot")
    if (
        report.get("source_locks_sha256") != evidence_sha
        or not isinstance(snapshot, Mapping)
        or snapshot.get("source_locks_sha256") != evidence_sha
        or snapshot.get("accepted_asset_replacements")
        != [dict(item) for item in contract.CURRENT_SHARED_ASSET_BASELINE]
    ):
        raise contract.PackageAssemblyError("hotfix evidence/snapshot binding drift")
    source = locks.get("source_package")
    changes = locks.get("changed_payloads")
    additions = locks.get("added_payloads")
    if (
        not isinstance(source, Mapping)
        or not isinstance(changes, list)
        or not isinstance(additions, list)
    ):
        raise contract.PackageAssemblyError("hotfix source/change evidence is missing")
    hashes, sizes = source.get("payload_sha256"), source.get("payload_size")
    if (
        not isinstance(hashes, Mapping) or set(hashes) != set(contract.ROOT_NAMES)
        or not isinstance(sizes, Mapping) or set(sizes) != set(contract.ROOT_NAMES)
        or contract._sha(contract._canonical(manifest["tables"]))
        != source.get("table_claims_sha256")
    ):
        raise contract.PackageAssemblyError("hotfix source payload/claim evidence drift")
    _repair_evidence(locks)
    by_path = {}
    for record in changes:
        if not isinstance(record, Mapping):
            raise contract.PackageAssemblyError("hotfix change record is invalid")
        key = (record.get("root"), record.get("logical_path"))
        if key in by_path:
            raise contract.PackageAssemblyError("hotfix duplicate change record")
        by_path[key] = record
    if tuple(by_path) != contract.CHANGED_PAYLOADS:
        raise contract.PackageAssemblyError("hotfix changed payload evidence is not exact")
    added_by_path = {}
    for record in additions:
        if not isinstance(record, Mapping):
            raise contract.PackageAssemblyError("hotfix addition record is invalid")
        key = (record.get("root"), record.get("logical_path"))
        if key in added_by_path or key in by_path:
            raise contract.PackageAssemblyError("hotfix duplicate addition record")
        added_by_path[key] = record
    if tuple(added_by_path) != contract.ADDED_PAYLOADS:
        raise contract.PackageAssemblyError("hotfix added payload evidence is not exact")
    for root in contract.ROOT_NAMES:
        root_hashes, root_sizes = hashes.get(root), sizes.get(root)
        expected_target_paths = set(root_hashes or ()) | {
            logical for added_root, logical in contract.ADDED_PAYLOADS
            if added_root == root
        }
        if (
            not isinstance(root_hashes, Mapping)
            or set(image.roots[root]) != expected_target_paths
            or not isinstance(root_sizes, Mapping)
            or set(root_sizes) != set(root_hashes)
        ):
            raise contract.PackageAssemblyError("hotfix source payload path set drift")
        for logical, raw in image.roots[root].items():
            record = by_path.get((root, logical))
            addition = added_by_path.get((root, logical))
            if addition is not None:
                if (
                    logical in root_hashes
                    or addition.get("after_sha256") != contract._sha(raw)
                    or addition.get("after_size") != len(raw)
                ):
                    raise contract.PackageAssemblyError(
                        f"hotfix added payload binding drift: {root}:{logical}"
                    )
            elif record is None:
                if contract._sha(raw) != root_hashes[logical]:
                    raise contract.PackageAssemblyError(
                        f"hotfix unexpected change outside allowlist: {root}:{logical}"
                    )
            elif (
                record.get("before_sha256") != root_hashes[logical]
                or record.get("before_size") != root_sizes[logical]
                or record.get("after_sha256") != contract._sha(raw)
                or record.get("after_size") != len(raw)
                or record.get("before_sha256") == record.get("after_sha256")
            ):
                raise contract.PackageAssemblyError(
                    f"hotfix changed payload binding drift: {root}:{logical}"
                )
    if locks.get("acceptance") != contract._ACCEPTANCE:
        raise contract.PackageAssemblyError("hotfix acceptance drift")
    return {
        "integrity_ready": True, "apply_ready": True,
        "payload_count": root_report["payload_count"],
        "table_claim_count": len(manifest["tables"]),
        "root_counts": root_report["root_counts"],
        "changed_payload_count": len(contract.CHANGED_PAYLOADS),
        "changed_payloads": list(contract.CHANGED_PAYLOADS),
        "added_payload_count": len(contract.ADDED_PAYLOADS),
        "added_payloads": list(contract.ADDED_PAYLOADS),
        "unchanged_payload_count": 88,
        "accepted_asset_replacements": [
            dict(item) for item in contract.CURRENT_SHARED_ASSET_BASELINE
        ],
        "writes_live": False,
    }


__all__ = ["audit_hotfix_package"]
