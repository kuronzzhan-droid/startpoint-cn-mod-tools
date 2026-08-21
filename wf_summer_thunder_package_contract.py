#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure package inventory, claim, reference, and manifest contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import wf_action_skill_compile as action_compile
import wf_character_pack as character_pack
import wf_character_requirements as requirements
import wf_summer_thunder_master_compile as master_compile
import wf_summer_thunder_server_compile as server_compile
import wf_summer_thunder_voice_compile as voice_compile


CHARACTER_ID = 139998
CODE_NAME = "cnmod_thunder_dragon_ascendant"
PACKAGE_ID = CODE_NAME
ROOT_NAMES = character_pack.ROOT_NAMES
CONFIRMATION = "ASSEMBLE_CNMOD_THUNDER_DRAGON_ASCENDANT"
MASTER_TABLE_CLAIMS_SHA256 = (
    "99a2f2bb21a94090d05c65db47137b4845a10598ef26d111706b7aaa4c79e622"
)

_FORBIDDEN_SEGMENTS = frozenset(
    {"story", "words", "login", "expression", "expressions", "episode"}
)
_EFFECT_LOGICALS = frozenset(
    {
        f"battle/effect/skill_unique/{CODE_NAME}/fan_lightning/"
        "fan_lightning.atlas.amf3.deflate",
        f"battle/effect/skill_unique/{CODE_NAME}/fan_lightning/"
        "fan_lightning.png",
        f"battle/effect/skill_unique/{CODE_NAME}/fan_lightning/"
        "fan_lightning_wave.parts.amf3.deflate",
        f"battle/effect/skill_unique/{CODE_NAME}/fan_lightning/"
        "fan_lightning_wave.timeline.amf3.deflate",
    }
)
_UNIQUE_ICON_LOGICAL = (
    "battle/common/unique_condition/"
    "unique_cnmod_thunder_dragon_ascendant_amp.png"
)


class PackageAssemblyError(RuntimeError):
    """The locked inputs cannot safely be assembled."""


@dataclass(frozen=True)
class PackageImage:
    """Complete in-memory package image, before any workspace write."""

    roots: Mapping[str, Mapping[str, bytes]]
    manifest: Mapping[str, Any]
    source_report: Mapping[str, Any]


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def logical_segments(logical_path: str) -> tuple[str, ...]:
    normalized = logical_path.replace("\\", "/")
    segments = tuple(normalized.split("/"))
    if (
        not normalized
        or normalized.startswith("/")
        or normalized.endswith("/")
        or "" in segments
        or "." in segments
        or ".." in segments
        or "\\" in logical_path
    ):
        raise PackageAssemblyError(f"invalid logical path: {logical_path!r}")
    return segments


def expected_client_root(
    logical_path: str,
    *,
    server_logicals: Sequence[str] = character_pack.SERVER_LOGICAL_PATHS,
) -> str:
    """Return the one permitted package root for a logical path."""

    segments = logical_segments(logical_path)
    if logical_path in frozenset(server_logicals):
        return "server"
    if logical_path.endswith(".atf.deflate"):
        return "android"
    if (
        len(segments) == 3
        and segments[0] == "dynamic"
        and segments[1] == "gacha_banner"
        and logical_path.endswith(".png")
    ):
        return "medium"
    if (
        len(segments) >= 3
        and segments[0] == "character"
        and segments[1] == CODE_NAME
        and segments[2] == "ui"
        and not logical_path.endswith(".atlas.amf3.deflate")
    ):
        return "medium"
    return "common"


def all_logicals(
    roots: Mapping[str, Mapping[str, bytes]],
    *,
    server_logicals: Sequence[str] = character_pack.SERVER_LOGICAL_PATHS,
) -> dict[str, str]:
    seen: dict[str, str] = {}
    if set(roots) != set(ROOT_NAMES):
        raise PackageAssemblyError(
            f"root set mismatch: expected {list(ROOT_NAMES)}, got {sorted(roots)}"
        )
    for root_name in ROOT_NAMES:
        files = roots[root_name]
        if not isinstance(files, Mapping):
            raise PackageAssemblyError(f"root {root_name} must be a mapping")
        for logical_path, raw in files.items():
            segments = logical_segments(logical_path)
            forbidden = sorted(
                set(segment.lower() for segment in segments) & _FORBIDDEN_SEGMENTS
            )
            if forbidden:
                raise PackageAssemblyError(
                    f"forbidden segment {forbidden[0]!r} in {logical_path}"
                )
            if not isinstance(raw, bytes):
                raise PackageAssemblyError(f"payload is not bytes: {logical_path}")
            previous = seen.get(logical_path)
            if previous is not None:
                raise PackageAssemblyError(
                    f"duplicate logical path {logical_path!r} in {previous} and {root_name}"
                )
            expected = expected_client_root(
                logical_path, server_logicals=server_logicals
            )
            if root_name != expected:
                raise PackageAssemblyError(
                    f"root channel mismatch for {logical_path}: "
                    f"expected {expected}, got {root_name}"
                )
            seen[logical_path] = root_name
    return seen


def validate_root_contract(
    roots: Mapping[str, Mapping[str, bytes]],
    *,
    server_logicals: Sequence[str] = character_pack.SERVER_LOGICAL_PATHS,
) -> dict[str, Any]:
    """Validate roots and the exact canonical 37-item required-asset gate."""

    seen = all_logicals(roots, server_logicals=server_logicals)
    required = tuple(
        item.logical_path
        for item in requirements.char_asset_requirements(CODE_NAME)
        if item.category == "required"
    )
    if len(required) != 37 or len(set(required)) != 37:
        raise PackageAssemblyError(
            f"requirements contract drift: expected exactly 37, got {len(set(required))}"
        )
    missing = sorted(set(required) - set(seen))
    if missing:
        raise PackageAssemblyError(f"missing required assets: {missing}")
    return {
        "required_total": 37,
        "required_present": 37,
        "missing_required": [],
        "root_counts": {name: len(roots[name]) for name in ROOT_NAMES},
        "payload_count": sum(len(roots[name]) for name in ROOT_NAMES),
    }


def expected_production_logicals() -> frozenset[str]:
    required = {
        item.logical_path
        for item in requirements.char_asset_requirements(CODE_NAME)
        if item.category == "required"
    }
    voice = {
        f"character/{CODE_NAME}/voice/{relative}"
        for relative in (
            *voice_compile.AUTHOR_CUT_RELATIVES,
            *voice_compile.INGEST_RELATIVES,
        )
    }
    stored_programs = {
        f"{program}.action.dsl.amf3.deflate"
        for program in action_compile.PROGRAM_PATHS.values()
    }
    return frozenset(
        required
        | set(master_compile.TABLE_CODECS)
        | voice
        | stored_programs
        | _EFFECT_LOGICALS
        | {_UNIQUE_ICON_LOGICAL}
        | set(server_compile.SERVER_PATHS)
    )


def server_claim(logical_path: str) -> dict[str, Any]:
    return {
        "root": "server",
        "logical_path": logical_path,
        "codec_id": "json_object",
        "outer_keys": [str(CHARACTER_ID)],
        "inner_keys": [],
        "semantic_claims": [],
    }


def validate_production_contract(
    roots: Mapping[str, Mapping[str, bytes]],
    table_claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Validate the exact 83-file/22-claim production inventory."""

    report = validate_root_contract(roots)
    actual = {
        logical_path
        for root_name in ROOT_NAMES
        for logical_path in roots[root_name]
    }
    expected = expected_production_logicals()
    if actual != expected:
        raise PackageAssemblyError(
            "production inventory mismatch: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )
    expected_counts = {"common": 52, "medium": 25, "android": 2, "server": 4}
    if report["root_counts"] != expected_counts or report["payload_count"] != 83:
        raise PackageAssemblyError(
            f"production root count drift: {report['root_counts']}"
        )

    claims = [dict(claim) for claim in table_claims]
    if len(claims) != 22:
        raise PackageAssemblyError(
            f"table claim count drift: expected 22, got {len(claims)}"
        )
    client_claims = [claim for claim in claims if claim.get("root") == "common"]
    server_claims = [claim for claim in claims if claim.get("root") == "server"]
    claims_sha256 = sha256_bytes(
        json.dumps(
            client_claims,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    if claims_sha256 != MASTER_TABLE_CLAIMS_SHA256:
        raise PackageAssemblyError(
            "client master claims drift: "
            f"expected {MASTER_TABLE_CLAIMS_SHA256}, got {claims_sha256}"
        )
    expected_server_claims = [
        server_claim(logical) for logical in server_compile.SERVER_PATHS
    ]
    if server_claims != expected_server_claims:
        raise PackageAssemblyError("server table claims are not exact")
    if {claim.get("logical_path") for claim in claims} != (
        set(master_compile.TABLE_CODECS) | set(server_compile.SERVER_PATHS)
    ):
        raise PackageAssemblyError("table claim logical coverage is not exact")
    custom_pf = any(
        "power_flip" in logical.lower() and "/voice/" not in logical.lower()
        for logical in actual
    )
    if custom_pf:
        raise PackageAssemblyError(
            "custom power-flip asset is forbidden for this package"
        )
    return {
        **report,
        "table_claim_count": len(claims),
        "client_claims_sha256": claims_sha256,
        "custom_power_flip_assets": False,
    }


def validate_reference_closure(
    roots: Mapping[str, Mapping[str, bytes]],
    references: Sequence[requirements.MasterAssetReference],
    *,
    package_condition_ids: Sequence[str],
) -> dict[str, Any]:
    """Require every owned master/DSL reference to resolve inside the package."""

    declared = {
        logical_path
        for root_name in ("common", "medium", "android")
        for logical_path in roots[root_name]
    }
    report = requirements.build_master_reference_report(
        references,
        package_asset_paths=declared,
        package_condition_ids=package_condition_ids,
    )
    if report["missing"]:
        raise PackageAssemblyError(
            f"master reference closure failed: {report['missing']}"
        )
    return report


def draft_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "character_id": CHARACTER_ID,
        "code_name": CODE_NAME,
        "package_version": "0.0.0-draft",
        "requires_client_base": "UNSET",
        "required_capabilities": [],
        "roots": {name: [] for name in ROOT_NAMES},
        "tables": [],
        "skills": {},
        "unique_condition": {},
        "qa": {
            "delivery_mode": "production",
            "release_ready": False,
            "required_assets_total": 37,
            "required_assets_present": 0,
            "workspace_input_sha256": "",
        },
        "snapshot": {},
    }


def build_manifest(
    *,
    roots: Mapping[str, Mapping[str, bytes]],
    table_claims: Sequence[Mapping[str, Any]],
    package_version: str,
    requires_client_base: str,
    required_capabilities: Sequence[str],
    generator_git_head: str,
    source_locks_sha256: str,
    server_logicals: Sequence[str] = character_pack.SERVER_LOGICAL_PATHS,
) -> dict[str, Any]:
    """Build the deterministic, unsealed production manifest input."""

    gate = validate_root_contract(roots, server_logicals=server_logicals)
    entries: dict[str, list[dict[str, Any]]] = {}
    for root_name in ROOT_NAMES:
        entries[root_name] = [
            {
                "logical_path": logical_path,
                "sha256": sha256_bytes(raw),
                "size": len(raw),
            }
            for logical_path, raw in sorted(roots[root_name].items())
        ]
    return {
        "schema_version": 1,
        "package_id": PACKAGE_ID,
        "character_id": CHARACTER_ID,
        "code_name": CODE_NAME,
        "package_version": package_version,
        "requires_client_base": requires_client_base,
        "required_capabilities": list(required_capabilities),
        "roots": entries,
        "tables": [dict(claim) for claim in table_claims],
        "skills": {},
        "unique_condition": {},
        "qa": {
            "delivery_mode": "production",
            "release_ready": False,
            "required_assets_total": gate["required_total"],
            "required_assets_present": gate["required_present"],
            "workspace_input_sha256": "",
        },
        "snapshot": {
            "generator_git_head": generator_git_head,
            "source_locks_sha256": source_locks_sha256,
        },
    }


__all__ = [
    "CHARACTER_ID", "CODE_NAME", "PACKAGE_ID", "ROOT_NAMES", "CONFIRMATION",
    "MASTER_TABLE_CLAIMS_SHA256", "PackageAssemblyError", "PackageImage",
    "sha256_bytes", "logical_segments", "expected_client_root", "all_logicals",
    "validate_root_contract", "expected_production_logicals", "server_claim",
    "validate_production_contract", "validate_reference_closure", "draft_manifest",
    "build_manifest",
]
