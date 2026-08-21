#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only production compilation for the summer-thunder character package."""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import wf_action_skill_compile as action_compile
import wf_character_requirements as requirements
import wf_dsl
import wf_mod_tool as core
import wf_summer_thunder_core_compile as core_compile
import wf_summer_thunder_master_compile as master_compile
import wf_summer_thunder_server_compile as server_compile
import wf_summer_thunder_skill_preview_compile as preview_compile
import wf_summer_thunder_voice_compile as voice_compile
import wf_summer_thunder_package_acceptance as package_acceptance
import wf_summer_thunder_package_base as package_base
import wf_summer_thunder_package_skill_gate as package_skill_gate
from wf_summer_thunder_package_contract import (
    CHARACTER_ID,
    CODE_NAME,
    PACKAGE_ID,
    ROOT_NAMES,
    PackageAssemblyError,
    PackageImage,
    build_manifest,
    expected_client_root,
    server_claim,
    sha256_bytes,
    validate_production_contract,
    validate_reference_closure,
)
from wf_summer_thunder_package_sources import (
    LOCKED_ARTIFACTS,
    LOCKED_EFFECT_V1,
    LOCKED_NORMAL_V3,
    LOCKED_SPECIAL_COMPAT_V3,
    LOCKED_UI_V3,
    ArtifactLock,
    load_locked_artifact_bundle,
    validate_special_reuse_payloads,
)
from wf_summer_thunder_package_evidence import (
    source_lock_evidence_bytes,
    validate_source_lock_binding,
)
from wf_summer_thunder_package_rebase import (
    rebase_authoring_scaffold,
    rebase_claimed_scaffold,
    validate_claimed_table_rebase,
    validate_clean_release_rebase,
)


@dataclass(frozen=True)
class ProductionInputs:
    """Explicit isolated roots used by the pure package compiler."""

    build_root: Path
    authoring_store: Path
    clean_release_store: Path
    server_shadow_assets: Path


def _resolved_directory(path: Path, label: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise PackageAssemblyError(f"{label} must be absolute")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise PackageAssemblyError(f"{label} does not exist") from exc
    if not resolved.is_dir():
        raise PackageAssemblyError(f"{label} is not a directory")
    return resolved


def _isolated_store(root: Path, store: Path, label: str) -> Path:
    stores_anchor = (root / "work" / "stores").resolve()
    try:
        relative = store.relative_to(stores_anchor)
    except ValueError as exc:
        raise PackageAssemblyError(f"{label} must be under work/stores") from exc
    if (
        len(relative.parts) != 3
        or relative.parts[-2:] != ("production", "upload")
        or any(part.casefold() == ".cdn" for part in store.parts)
    ):
        raise PackageAssemblyError(
            f"{label} must be work/stores/<name>/production/upload"
        )
    return store


def validate_isolated_inputs(
    inputs: ProductionInputs, *, tool_root: Path | None = None
) -> ProductionInputs:
    """Reject paths outside the build/two-store/server-shadow contract."""

    root = _resolved_directory(
        Path(tool_root) if tool_root is not None else Path(__file__).resolve().parent,
        "tool root",
    )
    build = _resolved_directory(inputs.build_root, "build root")
    authoring = _resolved_directory(inputs.authoring_store, "authoring store")
    clean = _resolved_directory(inputs.clean_release_store, "clean release store")
    server = _resolved_directory(inputs.server_shadow_assets, "server shadow")
    expected_build = (root / "work" / "builds" / PACKAGE_ID).resolve()
    if build != expected_build:
        raise PackageAssemblyError(
            f"build root must be the package build root: {expected_build}"
        )
    _isolated_store(root, authoring, "authoring store")
    _isolated_store(root, clean, "clean release store")
    if authoring == clean:
        raise PackageAssemblyError(
            "authoring and clean release stores must be distinct"
        )
    expected_clean = (
        root / "work" / "stores" / "cnmod_thunder_dragon_release_base"
        / "production" / "upload"
    ).resolve()
    if clean != expected_clean:
        raise PackageAssemblyError(
            f"clean release must be the locked release-base store: {expected_clean}"
        )
    expected_server = (build / "server_shadow" / "assets").resolve()
    if server != expected_server or any(
        part.casefold() == ".cdn" for part in server.parts
    ):
        raise PackageAssemblyError(
            f"server shadow must be the isolated assets root: {expected_server}"
        )
    return ProductionInputs(build, authoring, clean, server)


def _decode_effect_tree(raw: bytes, label: str) -> Any:
    try:
        return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
    except Exception as exc:
        raise PackageAssemblyError(f"cannot decode effect {label}") from exc


def validate_effect_runtime_texture_closure(
    files: Mapping[str, bytes],
) -> dict[str, Any]:
    """Prove every parts image reference is exported by the runtime atlas."""

    base = f"battle/effect/skill_unique/{CODE_NAME}/fan_lightning"
    parts_key = f"{base}/fan_lightning_wave.parts.amf3.deflate"
    atlas_key = f"{base}/fan_lightning.atlas.amf3.deflate"
    if parts_key not in files or atlas_key not in files:
        raise PackageAssemblyError("effect runtime closure inputs are missing")
    parts = _decode_effect_tree(files[parts_key], "parts")
    atlas = _decode_effect_tree(files[atlas_key], "atlas")
    if not isinstance(parts, dict) or not isinstance(atlas, list):
        raise PackageAssemblyError("effect runtime closure root type mismatch")
    texture_refs = {
        item["p"]
        for item in parts.get("i", ())
        if isinstance(item, dict) and isinstance(item.get("p"), str)
    }
    atlas_names = {
        item["n"]
        for item in atlas
        if isinstance(item, dict) and isinstance(item.get("n"), str)
    }
    missing = sorted(texture_refs - atlas_names)
    if missing:
        raise PackageAssemblyError(f"effect runtime atlas missing textures: {missing}")
    return {
        "texture_reference_count": len(texture_refs),
        "atlas_record_count": len(atlas_names),
        "missing_textures": [],
    }


def _store_file(store: Path, logical: str) -> bytes:
    path = core.table_path(store, logical)
    if not path.is_file():
        raise PackageAssemblyError(f"isolated store lacks table: {logical}")
    return path.read_bytes()


def _read_exact_tree(root: Path, relatives: Sequence[str], label: str) -> dict[str, bytes]:
    expected = set(relatives)
    disk = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*") if path.is_file()
    }
    if disk != expected:
        raise PackageAssemblyError(
            f"{label} source set mismatch: missing={sorted(expected-disk)}, "
            f"extra={sorted(disk-expected)}"
        )
    return {
        relative: (root / Path(*relative.split("/"))).read_bytes()
        for relative in relatives
    }


def _donor_rows(base_tables: Mapping[str, bytes], authoring_store: Path) -> dict[str, bytes]:
    character_rows = core.read_orderedmap_file_from_bytes(
        base_tables[master_compile.CHARACTER_LOGICAL]
    )
    try:
        status = core.read_orderedmap_raw_rows_from_bytes(
            base_tables[master_compile.STATUS_LOGICAL],
            master_compile.STATUS_LOGICAL,
        )
        status_rows = dict(zip(status.keys, status.rows, strict=True))
        awake_rows = core.read_orderedmap_file_from_bytes(
            _store_file(
                authoring_store,
                "master/character/character_awake_status.orderedmap",
            )
        )
        return {
            "thunder_dragon_character": character_rows["231001"].encode("utf-8"),
            "dragon_skin_character": character_rows["141099"].encode("utf-8"),
            "summer_thunder_character": character_rows["131104"].encode("utf-8"),
            "dragon_skin_status": status_rows["141099"],
            "scaffold_awake_status": awake_rows[str(CHARACTER_ID)].encode("utf-8"),
        }
    except KeyError as exc:
        raise PackageAssemblyError(f"authoring scaffold donor row is absent: {exc}") from exc


def _owned_references(
    master_files: Mapping[str, bytes],
    claims: Sequence[Mapping[str, Any]],
    action_files: Mapping[str, bytes],
) -> tuple[requirements.MasterAssetReference, ...]:
    flat_tables: dict[str, dict[str, str]] = {}
    nested_tables: dict[str, dict[str, dict[str, str]]] = {}
    for claim in claims:
        if claim.get("root") != "common":
            continue
        logical = claim["logical_path"]
        codec_id = claim["codec_id"]
        if codec_id == "flat":
            decoded = core.read_orderedmap_file_from_bytes(master_files[logical])
            flat_tables[logical] = {
                key: decoded[key] for key in claim["outer_keys"]
            }
        elif codec_id == "action_nested":
            decoded_nested = core.load_nested_table_bytes(master_files[logical], logical)
            nested_tables[logical] = {
                outer: decoded_nested.rows[outer].text_rows()
                for outer in claim["outer_keys"]
            }
    dsl_trees = {
        logical: wf_dsl.parse_dsl(zlib.decompress(payload, -15))["tree"]
        for logical, payload in action_files.items()
    }
    return requirements.extract_master_asset_references(
        flat_tables, nested_tables, dsl_trees
    )


def _merge_files(
    roots: dict[str, dict[str, bytes]], files: Mapping[str, bytes], label: str
) -> None:
    for logical, raw in files.items():
        root_name = expected_client_root(logical)
        if logical in roots[root_name]:
            raise PackageAssemblyError(f"duplicate payload from {label}: {logical}")
        roots[root_name][logical] = raw


def _artifact_source_record(lock: ArtifactLock) -> dict[str, Any]:
    return {
        "name": lock.name,
        "report_relative": lock.report_relative,
        "report_sha256": lock.report_sha256,
        "acceptance_relative": lock.acceptance_relative,
        "acceptance_sha256": lock.acceptance_sha256,
        "payload_sha256": dict(lock.payload_sha256),
    }


def compile_production_package(
    inputs: ProductionInputs,
    *,
    generator_git_head: str,
    package_version: str = "1.0.0",
    requires_client_base: str = "1.4.346",
) -> PackageImage:
    """Compile and verify the exact 83-file image without external writes."""

    inputs = validate_isolated_inputs(inputs)
    if len(generator_git_head) != 40 or any(
        char not in "0123456789abcdef" for char in generator_git_head.lower()
    ):
        raise PackageAssemblyError("generator_git_head must be a full 40-hex commit")

    roots: dict[str, dict[str, bytes]] = {name: {} for name in ROOT_NAMES}
    artifact_reports: dict[str, dict[str, Any]] = {}
    loaded_artifacts: dict[str, dict[str, bytes]] = {}
    for lock in LOCKED_ARTIFACTS:
        files, report, _acceptance = load_locked_artifact_bundle(inputs.build_root, lock)
        loaded_artifacts[lock.name] = files
        artifact_reports[lock.name] = report
        _merge_files(roots, files, lock.name)
    special_semantics = validate_special_reuse_payloads(
        loaded_artifacts[LOCKED_NORMAL_V3.name],
        loaded_artifacts[LOCKED_SPECIAL_COMPAT_V3.name],
        artifact_reports[LOCKED_SPECIAL_COMPAT_V3.name],
    )
    effect_semantics = validate_effect_runtime_texture_closure(
        loaded_artifacts[LOCKED_EFFECT_V1.name]
    )

    authoring_tables = {
        logical: _store_file(inputs.authoring_store, logical)
        for logical in master_compile.TABLE_CODECS
    }
    clean_tables = {
        logical: _store_file(inputs.clean_release_store, logical)
        for logical in master_compile.TABLE_CODECS
    }
    release_base_evidence = package_base.load_release_base_evidence(
        inputs.build_root, clean_tables
    )
    scaffold_claims = master_compile._claims()  # type: ignore[attr-defined]
    rebased_authoring, scaffold_rebase_report = rebase_authoring_scaffold(
        clean_tables, authoring_tables, scaffold_claims
    )
    compiled_core = core_compile.compile_summer_thunder_core(
        _donor_rows(rebased_authoring, inputs.authoring_store)
    )
    master_result = master_compile.compile_summer_thunder_master_tables(
        rebased_authoring, compiled_core
    )
    master_files = master_result["files"]
    client_claims = master_result["table_claims"]
    clean_canary = validate_clean_release_rebase(
        clean_tables, master_files, client_claims
    )
    _merge_files(roots, master_files, "client master compiler")

    voice_base = inputs.build_root / "art" / "voice"
    author_voice_root = (
        voice_base / "author_cut_v1" / "candidate_mp3" / "character"
        / CODE_NAME / "voice"
    )
    ingest_voice_root = (
        voice_base / "ingest_v1" / "candidate_mp3" / "character"
        / CODE_NAME / "voice"
    )
    author_voice = _read_exact_tree(
        author_voice_root, voice_compile.AUTHOR_CUT_RELATIVES, "author voice"
    )
    ingest_voice = _read_exact_tree(
        ingest_voice_root, voice_compile.INGEST_RELATIVES, "ingest voice"
    )
    voice_files, voice_tables, voice_report = (
        voice_compile.compile_summer_thunder_voice_assets(
            author_voice, ingest_voice
        )
    )
    speech_rows = core.read_orderedmap_file_from_bytes(
        master_files[master_compile.CHARACTER_SPEECH_LOGICAL]
    )
    expected_speech = voice_tables[master_compile.CHARACTER_SPEECH_LOGICAL][
        str(CHARACTER_ID)
    ]
    if speech_rows[str(CHARACTER_ID)] != expected_speech:
        raise PackageAssemblyError("voice speech row differs from compiled master")
    _merge_files(roots, voice_files, "voice compiler")

    action_files = action_compile.compile_summer_thunder_dragon_action_skills()
    preview_result = preview_compile.compile_summer_thunder_skill_preview()
    _merge_files(roots, action_files, "action DSL compiler")
    _merge_files(roots, preview_result["files"], "skill preview compiler")

    server_inputs = {
        logical: (inputs.server_shadow_assets / Path(*logical.split("/"))).read_bytes()
        for logical in server_compile.SERVER_PATHS
    }
    core_character = compiled_core["tables"]["character"][str(CHARACTER_ID)]
    core_text = compiled_core["tables"]["character_text"][str(CHARACTER_ID)]
    server_result = server_compile.compile_summer_thunder_server_files(
        server_inputs,
        character_rows=core.read_csv_lines(core_character),
        character_text_rows=core.read_csv_lines(core_text),
    )
    _merge_files(roots, server_result["files"], "server compiler")
    table_claims = [
        *client_claims,
        *(server_claim(logical) for logical in server_compile.SERVER_PATHS),
    ]

    references = _owned_references(master_files, client_claims, action_files)
    reference_report = validate_reference_closure(
        roots, references, package_condition_ids=(str(CHARACTER_ID),)
    )
    production_report = validate_production_contract(roots, table_claims)
    visual_evidence = package_acceptance.load_visual_evidence(inputs.build_root)
    package_acceptance_report = package_acceptance.build_package_acceptance(
        ui_report=artifact_reports[LOCKED_UI_V3.name],
        visual_evidence=visual_evidence,
        master_files=master_files,
        effect_report=artifact_reports[LOCKED_EFFECT_V1.name],
        effect_closure=effect_semantics,
        action_files=action_files,
    )
    skill_follow_gate = package_skill_gate.build_skill_follow_gate(
        action_files, loaded_artifacts[LOCKED_EFFECT_V1.name]
    )

    pure_reports = {
        "core": compiled_core["report"],
        "master": master_result["report"],
        "voice": voice_report,
        "preview": preview_result["report"],
        "server": server_result["report"],
        "action_output_sha256": {
            logical: sha256_bytes(raw) for logical, raw in sorted(action_files.items())
        },
    }
    if any(
        isinstance(report, dict) and report.get("writes_live") is not False
        for name, report in pure_reports.items()
        if name != "action_output_sha256"
    ):
        raise PackageAssemblyError("a pure compiler did not prove writes_live=false")
    source_locks = {
        "schema_version": 1,
        "artifacts": [_artifact_source_record(lock) for lock in LOCKED_ARTIFACTS],
        "authoring_table_sha256": {
            logical: sha256_bytes(raw) for logical, raw in authoring_tables.items()
        },
        "clean_release": release_base_evidence,
        "rebased_authoring_table_sha256": {
            logical: sha256_bytes(raw) for logical, raw in rebased_authoring.items()
        },
        "server_shadow_sha256": {
            logical: sha256_bytes(raw) for logical, raw in server_inputs.items()
        },
        "voice_source_sha256": voice_report["source_sha256"],
        "pure_output_sha256": {
            "master": master_result["report"]["output_sha256"],
            "voice": voice_report["output_sha256"],
            "action": pure_reports["action_output_sha256"],
            "preview": {preview_result["report"]["logical_path"]: preview_result["report"]["sha256"]},
            "server": server_result["report"]["sha256"],
        },
        "package_acceptance": package_acceptance_report,
        "skill_follow_gate": skill_follow_gate,
    }
    source_locks_sha256 = sha256_bytes(source_lock_evidence_bytes(source_locks))
    manifest = build_manifest(
        roots=roots,
        table_claims=table_claims,
        package_version=package_version,
        requires_client_base=requires_client_base,
        required_capabilities=("content.sync@1",),
        generator_git_head=generator_git_head.lower(),
        source_locks_sha256=source_locks_sha256,
    )
    source_report = {
        "schema_version": 1,
        "status": "compiled_in_memory_ready",
        "writes_live": False,
        "formal_workspace_written": False,
        "production_contract": production_report,
        "clean_release_canary": clean_canary,
        "scaffold_rebase": scaffold_rebase_report,
        "reference_closure": reference_report,
        "effect_runtime_closure": effect_semantics,
        "special_reuse": special_semantics,
        "reference_count": len(references),
        "source_locks_sha256": source_locks_sha256,
        "source_locks": source_locks,
        "pure_reports": pure_reports,
        "package_acceptance": package_acceptance_report,
        "skill_follow_gate": skill_follow_gate,
    }
    validate_source_lock_binding(manifest, source_report)
    return PackageImage(roots=roots, manifest=manifest, source_report=source_report)


__all__ = [
    "PACKAGE_ID", "ProductionInputs", "validate_isolated_inputs",
    "validate_claimed_table_rebase", "validate_clean_release_rebase",
    "rebase_claimed_scaffold", "rebase_authoring_scaffold",
    "validate_effect_runtime_texture_closure", "compile_production_package",
]
