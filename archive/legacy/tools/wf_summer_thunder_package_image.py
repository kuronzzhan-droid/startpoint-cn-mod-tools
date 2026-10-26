#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Non-overridable audit of the complete in-memory production package."""

from __future__ import annotations

import re
from typing import Any, Mapping

from wf_summer_thunder_package_contract import (
    CHARACTER_ID,
    CODE_NAME,
    PACKAGE_ID,
    ROOT_NAMES,
    PackageAssemblyError,
    PackageImage,
    sha256_bytes,
    validate_production_contract,
)
from wf_summer_thunder_package_evidence import validate_source_lock_binding
from wf_summer_thunder_package_skill_gate import (
    validate_skill_follow_gate,
    validate_skill_follow_roots,
)


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PackageAssemblyError(f"{label} must be an object")
    return value


def _manifest_entries(image: PackageImage) -> dict[str, list[dict[str, Any]]]:
    return {
        root: [
            {
                "logical_path": logical,
                "sha256": sha256_bytes(raw),
                "size": len(raw),
            }
            for logical, raw in sorted(image.roots[root].items())
        ]
        for root in ROOT_NAMES
    }


def _validate_manifest(image: PackageImage) -> Mapping[str, Any]:
    manifest = _mapping(image.manifest, "manifest")
    expected_identity = {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "character_id": CHARACTER_ID,
        "code_name": CODE_NAME,
        "requires_client_base": "1.4.346",
        "required_capabilities": ["content.sync@1"],
        "skills": {},
        "unique_condition": {},
    }
    for field, expected in expected_identity.items():
        if manifest.get(field) != expected:
            raise PackageAssemblyError(f"manifest identity drift: {field}")
    version = manifest.get("package_version")
    if not isinstance(version, str) or not version or version == "0.0.0-draft":
        raise PackageAssemblyError("manifest package version is not production input")
    if manifest.get("roots") != _manifest_entries(image):
        raise PackageAssemblyError("manifest root entries drift from payload bytes")
    qa = _mapping(manifest.get("qa"), "manifest qa")
    if dict(qa) != {
        "delivery_mode": "production",
        "release_ready": False,
        "required_assets_total": 37,
        "required_assets_present": 37,
        "workspace_input_sha256": "",
    }:
        raise PackageAssemblyError("manifest QA input is not exact 37-of-37")
    snapshot = _mapping(manifest.get("snapshot"), "manifest snapshot")
    git_head = snapshot.get("generator_git_head")
    if not isinstance(git_head, str) or re.fullmatch(r"[0-9a-f]{40}", git_head) is None:
        raise PackageAssemblyError("manifest generator git head is not full lowercase hex")
    return manifest


def audit_package_image(image: PackageImage) -> dict[str, Any]:
    """Validate every invariant; pending external gates become explicit blockers."""

    if not isinstance(image, PackageImage):
        raise PackageAssemblyError("package image type is invalid")
    if set(image.roots) != set(ROOT_NAMES):
        raise PackageAssemblyError("package image root channels are not exact")
    manifest = _validate_manifest(image)
    claims = manifest.get("tables")
    if not isinstance(claims, list):
        raise PackageAssemblyError("manifest table claims must be a list")
    production = validate_production_contract(image.roots, claims)
    report = _mapping(image.source_report, "source report")
    if (
        report.get("writes_live") is not False
        or report.get("formal_workspace_written") is not False
        or report.get("production_contract") != production
    ):
        raise PackageAssemblyError("source report production readback drift")
    validate_source_lock_binding(manifest, report)
    locks = _mapping(report.get("source_locks"), "source locks")
    if report.get("package_acceptance") != locks.get("package_acceptance"):
        raise PackageAssemblyError("package acceptance/source-lock drift")
    if report.get("skill_follow_gate") != locks.get("skill_follow_gate"):
        raise PackageAssemblyError("skill-follow/source-lock drift")
    blockers: list[str] = []
    skill_gate = report.get("skill_follow_gate")
    if (
        isinstance(skill_gate, Mapping)
        and skill_gate.get("status") == "pending_exact_contract"
        and skill_gate.get("package_manifest_eligible") is False
    ):
        try:
            validate_skill_follow_gate(skill_gate)
        except PackageAssemblyError as exc:
            blockers.append(str(exc))
    else:
        validate_skill_follow_roots(image.roots, skill_gate)
    return {
        "integrity_ready": True,
        "apply_ready": not blockers,
        "blockers": blockers,
        "payload_count": production["payload_count"],
        "root_counts": production["root_counts"],
        "table_claim_count": production["table_claim_count"],
        "required_assets_present": production["required_present"],
        "missing_required": production["missing_required"],
        "source_locks_sha256": report["source_locks_sha256"],
        "writes_live": False,
    }


def require_apply_ready(image: PackageImage) -> dict[str, Any]:
    report = audit_package_image(image)
    if not report["apply_ready"]:
        raise PackageAssemblyError("; ".join(report["blockers"]))
    return report


__all__ = ["audit_package_image", "require_apply_ready"]
