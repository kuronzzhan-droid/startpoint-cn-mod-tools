#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent readback audit for the abyss-gacha replacement image."""

from __future__ import annotations

from typing import Any, Mapping

import wf_abyss_gacha_package_contract as contract
import wf_summer_thunder_package_contract as thunder


def source_lock_evidence_bytes(source_locks: Mapping[str, Any]) -> bytes:
    expected = {
        "schema_version",
        "source_package",
        "input_sha256",
        "component_reports",
        "acceptance",
        "new_output_sha256",
        "writes_live",
        "formal_workspace_written",
    }
    if (
        set(source_locks) != expected
        or source_locks.get("schema_version") != 1
        or source_locks.get("writes_live") is not False
        or source_locks.get("formal_workspace_written") is not False
    ):
        raise contract.PackageAssemblyError("source-lock sections are not exact")
    return contract._canonical(source_locks) + b"\n"


def _manifest_entries(
    image: contract.PackageImage,
) -> dict[str, list[dict[str, Any]]]:
    return {
        root: [
            {
                "logical_path": logical,
                "sha256": contract._sha(raw),
                "size": len(raw),
            }
            for logical, raw in sorted(image.roots[root].items())
        ]
        for root in contract.ROOT_NAMES
    }


def audit_package_image(image: contract.PackageImage) -> dict[str, Any]:
    """Recompute inventory, byte preservation, claims, and evidence binding."""

    if not isinstance(image, contract.PackageImage) or set(image.roots) != set(
        contract.ROOT_NAMES
    ):
        raise contract.PackageAssemblyError(
            "replacement package image type/roots are invalid"
        )
    manifest = image.manifest
    expected_identity = {
        "schema_version": 1,
        "package_id": contract.PACKAGE_ID,
        "character_id": contract.CHARACTER_ID,
        "code_name": contract.CODE_NAME,
        "package_version": contract.PACKAGE_VERSION,
        "requires_client_base": contract.REQUIRES_CLIENT_BASE,
        "required_capabilities": ["content.sync@1"],
        "skills": {},
        "unique_condition": {},
    }
    if any(
        manifest.get(field) != value for field, value in expected_identity.items()
    ):
        raise contract.PackageAssemblyError("replacement manifest identity drift")
    if manifest.get("roots") != _manifest_entries(image):
        raise contract.PackageAssemblyError(
            "replacement manifest payload binding drift"
        )
    qa = manifest.get("qa")
    if not isinstance(qa, Mapping) or dict(qa) != {
        "delivery_mode": "production",
        "release_ready": False,
        "required_assets_total": 37,
        "required_assets_present": 37,
        "workspace_input_sha256": "",
    }:
        raise contract.PackageAssemblyError("replacement manifest QA input drift")
    root_report = thunder.validate_root_contract(
        image.roots, server_logicals=contract.SERVER_LOGICALS
    )
    if (
        root_report["root_counts"] != contract.EXPECTED_ROOT_COUNTS
        or root_report["payload_count"] != contract.EXPECTED_PAYLOAD_COUNT
    ):
        raise contract.PackageAssemblyError("replacement payload/root count drift")

    report = image.source_report
    if (
        report.get("schema_version") != 1
        or report.get("status") != "compiled_in_memory_ready"
        or report.get("writes_live") is not False
        or report.get("formal_workspace_written") is not False
    ):
        raise contract.PackageAssemblyError(
            "replacement source report state drift"
        )
    locks = report.get("source_locks")
    if not isinstance(locks, Mapping):
        raise contract.PackageAssemblyError("source-lock report is missing")
    evidence = source_lock_evidence_bytes(locks)
    evidence_sha = contract._sha(evidence)
    snapshot = manifest.get("snapshot")
    if (
        not isinstance(snapshot, Mapping)
        or snapshot.get("source_locks_sha256") != evidence_sha
        or report.get("source_locks_sha256") != evidence_sha
    ):
        raise contract.PackageAssemblyError("source-lock manifest binding drift")
    input_sha256 = locks.get("input_sha256")
    component_reports = locks.get("component_reports")
    if not isinstance(input_sha256, Mapping) or not isinstance(
        component_reports, Mapping
    ):
        raise contract.PackageAssemblyError(
            "ticket shared asset source-lock evidence is missing"
        )
    expected_replacements = contract._accepted_asset_replacements(
        input_sha256, component_reports
    )
    if snapshot.get("accepted_asset_replacements") != expected_replacements:
        raise contract.PackageAssemblyError(
            "accepted asset replacement manifest binding drift"
        )
    drop_report = component_reports.get("drop")
    if (
        not isinstance(drop_report, Mapping)
        or drop_report.get("runtime_source_sync")
        != contract.DROP_RUNTIME_SOURCE_SYNC
    ):
        raise contract.PackageAssemblyError(
            "drop runtime source sync evidence drift"
        )
    source_record = locks.get("source_package")
    if not isinstance(source_record, Mapping):
        raise contract.PackageAssemblyError(
            "source-lock old package record is missing"
        )
    payload_hashes = source_record.get("payload_sha256")
    if not isinstance(payload_hashes, Mapping) or set(payload_hashes) != set(
        contract.ROOT_NAMES
    ):
        raise contract.PackageAssemblyError(
            "source-lock old payload hashes are invalid"
        )
    old_roots: dict[str, dict[str, bytes]] = {
        root: {} for root in contract.ROOT_NAMES
    }
    for root in contract.ROOT_NAMES:
        root_hashes = payload_hashes[root]
        if not isinstance(root_hashes, Mapping):
            raise contract.PackageAssemblyError(
                "source-lock old root hashes are invalid"
            )
        for logical, expected_sha in root_hashes.items():
            raw = image.roots[root].get(logical)
            if raw is None or contract._sha(raw) != expected_sha:
                raise contract.PackageAssemblyError(
                    f"old payload is not byte exact: {root}:{logical}"
                )
            old_roots[root][logical] = raw
    tables = manifest.get("tables")
    expected_claim_count = 22 + len(contract.expected_new_claims())
    if not isinstance(tables, list) or len(tables) != expected_claim_count:
        raise contract.PackageAssemblyError(
            "replacement table claim count drift"
        )
    old_contract = thunder.validate_production_contract(old_roots, tables[:22])
    if tables[22:] != contract.expected_new_claims():
        raise contract.PackageAssemblyError("replacement new table claims drift")
    new_pairs = {
        (root, logical)
        for root in contract.ROOT_NAMES
        for logical in image.roots[root]
        if logical not in old_roots[root]
    }
    if new_pairs != set(contract.NEW_PATHS):
        raise contract.PackageAssemblyError(
            "replacement new payload paths drift"
        )
    output_hashes = locks.get("new_output_sha256")
    if output_hashes != {
        f"{root}:{logical}": contract._sha(image.roots[root][logical])
        for root, logical in contract.NEW_PATHS
    }:
        raise contract.PackageAssemblyError(
            "replacement new output SHA-256 drift"
        )
    if (
        locks.get("acceptance") != contract._ACCEPTANCE
        or report.get("acceptance") != contract._ACCEPTANCE
    ):
        raise contract.PackageAssemblyError("replacement acceptance drift")

    result = {
        "integrity_ready": True,
        "apply_ready": True,
        "payload_count": root_report["payload_count"],
        "table_claim_count": len(tables),
        "root_counts": root_report["root_counts"],
        "old_payload_exact_count": old_contract["payload_count"],
        "new_payload_exact_count": len(new_pairs),
        "old_payloads_byte_exact": True,
        "new_paths_exact": True,
        "accepted_asset_replacements": expected_replacements,
        "all_references_closed": True,
        "eight_character_closure": True,
        "ticket_contract_closed": True,
        "shop_contract_closed": True,
        "drop_contract_closed": True,
        "drop_source_sync_closed": True,
        "drop_runtime_source_sync": dict(contract.DROP_RUNTIME_SOURCE_SYNC),
        "art_contract_closed": True,
        "writes_live": False,
    }
    report_contract = {
        key: result[key]
        for key in (
            "payload_count",
            "table_claim_count",
            "root_counts",
            "old_payload_exact_count",
            "new_payload_exact_count",
            "old_payloads_byte_exact",
        )
    }
    if report.get("package_contract") != report_contract:
        raise contract.PackageAssemblyError("replacement package report drift")
    return result


__all__ = ["source_lock_evidence_bytes", "audit_package_image"]
