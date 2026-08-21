"""Small shared fixtures for summer-thunder package unit tests."""

from __future__ import annotations

import tempfile
from functools import lru_cache
from pathlib import Path

from PIL import Image

import wf_action_skill_compile as action_compile
import wf_assets
import wf_character_requirements as requirements
import wf_flatomo_compile as flatomo_compile
import wf_summer_thunder_master_compile as master_compile
import wf_summer_thunder_server_compile as server_compile
import wf_summer_thunder_voice_compile as voice_compile
import wf_summer_thunder_package_assemble as package
from wf_summer_thunder_package_evidence import source_lock_evidence_bytes
from wf_summer_thunder_package_skill_gate import build_skill_follow_gate


def payload(logical: str) -> bytes:
    if logical.endswith(".png"):
        return wf_assets.PNG_FAKE + b"test-png"
    return ("payload:" + logical).encode("utf-8")


def required_roots() -> dict[str, dict[str, bytes]]:
    roots = {name: {} for name in package.ROOT_NAMES}
    for item in requirements.char_asset_requirements(package.CODE_NAME):
        if item.category == "required":
            root = package.expected_client_root(item.logical_path)
            roots[root][item.logical_path] = payload(item.logical_path)
    return roots


@lru_cache(maxsize=1)
def _accepted_skill_payloads() -> tuple[dict[str, bytes], dict[str, bytes], dict]:
    with tempfile.TemporaryDirectory() as temporary_name:
        temporary = Path(temporary_name)
        boxes = (
            (3, 27, 14, 38), (6, 27, 17, 38), (9, 21, 24, 45),
            (14, 21, 29, 45), (12, 14, 38, 51), (18, 14, 44, 51),
            (24, 14, 50, 51), (38, 11, 54, 55), (46, 22, 57, 44),
            (51, 22, 62, 44),
        )
        paths = []
        for index, box in enumerate(boxes):
            path = temporary / f"frame-{index}.png"
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            color = (255, 220, 30, 255) if index % 2 == 0 else (30, 220, 255, 255)
            for y in range(box[1], box[3]):
                for x in range(box[0], box[2]):
                    image.putpixel((x, y), color)
            image.save(path)
            paths.append(path)
        effect = flatomo_compile.compile_travelling_wave_effect(paths)
    action = action_compile.compile_summer_thunder_dragon_action_skills()
    return action, effect, build_skill_follow_gate(action, effect)


def complete_roots(*, accepted_skill: bool = False) -> dict[str, dict[str, bytes]]:
    roots = required_roots()
    extras = {
        *master_compile.TABLE_CODECS,
        *(
            f"character/{package.CODE_NAME}/voice/{relative}"
            for relative in (
                *voice_compile.AUTHOR_CUT_RELATIVES,
                *voice_compile.INGEST_RELATIVES,
            )
        ),
        *action_compile.compile_summer_thunder_dragon_action_skills(),
        f"battle/effect/skill_unique/{package.CODE_NAME}/fan_lightning/fan_lightning.atlas.amf3.deflate",
        f"battle/effect/skill_unique/{package.CODE_NAME}/fan_lightning/fan_lightning.png",
        f"battle/effect/skill_unique/{package.CODE_NAME}/fan_lightning/fan_lightning_wave.parts.amf3.deflate",
        f"battle/effect/skill_unique/{package.CODE_NAME}/fan_lightning/fan_lightning_wave.timeline.amf3.deflate",
        "battle/common/unique_condition/unique_cnmod_thunder_dragon_ascendant_amp.png",
        *server_compile.SERVER_PATHS,
    }
    for logical in extras:
        root = package.expected_client_root(logical)
        roots[root].setdefault(logical, payload(logical))
    if accepted_skill:
        action, effect, _gate = _accepted_skill_payloads()
        for logical, raw in {**action, **effect}.items():
            roots[package.expected_client_root(logical)][logical] = raw
    return roots


def complete_claims() -> list[dict]:
    claims = master_compile._claims()  # type: ignore[attr-defined]
    claims.extend(package.server_claim(logical) for logical in server_compile.SERVER_PATHS)
    return claims


def complete_image(
    *, skill_follow_gate: dict | None = None, accepted_skill: bool = False,
) -> package.PackageImage:
    roots = complete_roots(accepted_skill=accepted_skill)
    claims = complete_claims()
    acceptance = {
        "package_manifest_eligible": True,
        "writes_live": False,
    }
    accepted_gate = _accepted_skill_payloads()[2] if accepted_skill else None
    skill = skill_follow_gate or accepted_gate or {
        "status": "pending_exact_contract",
        "package_manifest_eligible": False,
        "writes_live": False,
    }
    source_locks = {
        "schema_version": 1,
        "artifacts": [],
        "authoring_table_sha256": {},
        "clean_release": {
            "client_base": "1.4.346",
            "table_count": 18,
            "writes_live": False,
        },
        "rebased_authoring_table_sha256": {},
        "server_shadow_sha256": {},
        "voice_source_sha256": {},
        "pure_output_sha256": {},
        "package_acceptance": acceptance,
        "skill_follow_gate": skill,
    }
    evidence = source_lock_evidence_bytes(source_locks)
    digest = package.sha256_bytes(evidence)
    manifest = package.build_manifest(
        roots=roots,
        table_claims=claims,
        package_version="1.0.0",
        requires_client_base="1.4.346",
        required_capabilities=("content.sync@1",),
        generator_git_head="b" * 40,
        source_locks_sha256=digest,
    )
    source_report = {
        "schema_version": 1,
        "status": "compiled_in_memory_hold_skill_follow",
        "writes_live": False,
        "formal_workspace_written": False,
        "production_contract": package.validate_production_contract(roots, claims),
        "source_locks": source_locks,
        "source_locks_sha256": digest,
        "package_acceptance": acceptance,
        "skill_follow_gate": skill,
    }
    return package.PackageImage(roots, manifest, source_report)
