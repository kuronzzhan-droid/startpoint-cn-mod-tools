#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Canonical source-lock evidence and manifest-summary binding."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from wf_summer_thunder_package_contract import PackageAssemblyError


EVIDENCE_RELATIVE = "evidence/package-source-locks.json"
_SECTIONS = {
    "schema_version",
    "artifacts",
    "authoring_table_sha256",
    "clean_release",
    "rebased_authoring_table_sha256",
    "server_shadow_sha256",
    "voice_source_sha256",
    "pure_output_sha256",
    "package_acceptance",
    "skill_follow_gate",
}


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PackageAssemblyError(f"{label} must be an object")
    return value


def source_lock_evidence_bytes(source_locks: Mapping[str, Any]) -> bytes:
    """Serialize the complete, validated source-lock report as its evidence file."""

    locks = _mapping(source_locks, "source locks")
    if set(locks) != _SECTIONS or locks.get("schema_version") != 1:
        raise PackageAssemblyError(
            "source-lock sections are not exact: "
            f"missing={sorted(_SECTIONS - set(locks))}, "
            f"extra={sorted(set(locks) - _SECTIONS)}"
        )
    clean = _mapping(locks["clean_release"], "release-base evidence")
    if (
        clean.get("client_base") != "1.4.346"
        or clean.get("table_count") != 18
        or clean.get("writes_live") is not False
    ):
        raise PackageAssemblyError("release-base evidence is not the locked 1.4.346 base")
    acceptance = _mapping(locks["package_acceptance"], "package acceptance")
    if (
        acceptance.get("package_manifest_eligible") is not True
        or acceptance.get("writes_live") is not False
    ):
        raise PackageAssemblyError("package acceptance is not eligible")
    skill = _mapping(locks["skill_follow_gate"], "skill-follow gate")
    if skill.get("writes_live") is not False:
        raise PackageAssemblyError("skill-follow gate does not prove writes_live=false")
    try:
        return (
            json.dumps(
                locks, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            + b"\n"
        )
    except (TypeError, ValueError) as exc:
        raise PackageAssemblyError("source-lock evidence is not strict JSON") from exc


def validate_source_lock_binding(
    manifest: Mapping[str, Any], source_report: Mapping[str, Any]
) -> bytes:
    """Return evidence bytes only when the report and manifest bind the same bytes."""

    snapshot = _mapping(manifest.get("snapshot"), "manifest snapshot")
    locks = _mapping(source_report.get("source_locks"), "source report locks")
    evidence = source_lock_evidence_bytes(locks)
    digest = hashlib.sha256(evidence).hexdigest()
    if (
        snapshot.get("source_locks_sha256") != digest
        or source_report.get("source_locks_sha256") != digest
    ):
        raise PackageAssemblyError("source-lock manifest binding drift")
    return evidence


__all__ = [
    "EVIDENCE_RELATIVE", "source_lock_evidence_bytes",
    "validate_source_lock_binding",
]
