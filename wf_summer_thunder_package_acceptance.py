#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Package-level acceptance that closes held UI/effect producer reports."""

from __future__ import annotations

import hashlib
import json
import zlib
from pathlib import Path
from typing import Any, Iterable, Mapping

import wf_action_skill_compile as action_compile
import wf_dsl
import wf_mod_tool as core
import wf_quest_lib as quest
import wf_summer_thunder_master_compile as master_compile
from wf_summer_thunder_package_contract import (
    CHARACTER_ID,
    CODE_NAME,
    PackageAssemblyError,
)


LOCKED_VISUAL_EVIDENCE = {
    "portrait_selection_sha256": "5a3e0ad0ee0cb86383379aad933a1747f04f90fb51a16dd526e6a4d7b833f4ad",
    "framing_audit_sha256": "eb87eaa399f5180daf5014fc2c61822bb372a973049db497c899e9aa638dcc76",
    "contact_sha256": {
        "accepted_pair_framing_boxes_contact.png": "c575cd4bffef305e636b87fffc790169fb624d3dad6f63775dfc1312f1f5869f",
        "skill_cutin_qa_contact.png": "d3bc433b5e8952d6cc5325b20fb80fb6e4098f658e70fa60c711d4a240fa25f7",
        "ui_derivatives_contact.png": "62eb94a88eda02d8a172175b9e15b718b5235e4a64f672f7b0a94408716889f3",
    },
    "user_approved_locked_pair": True,
    "writes_live": False,
}
LOCKED_ACTION_DSL_SHA256 = {
    (
        "battle/action/skill/action/rare5/"
        f"{CODE_NAME}${CODE_NAME}_1.action.dsl.amf3.deflate"
    ): "84862c8e962e56c14685183aae11437b0404234a4af3a8584adf5aca0155add2",
    (
        "battle/action/skill/action/rare5/"
        f"{CODE_NAME}${CODE_NAME}_2.action.dsl.amf3.deflate"
    ): "84862c8e962e56c14685183aae11437b0404234a4af3a8584adf5aca0155add2",
}
_EFFECT_PATH = (
    f"battle/effect/skill_unique/{CODE_NAME}/fan_lightning/fan_lightning_wave"
)
_VISUAL_PATHS = {
    "portrait_selection": (
        "art/portraits/accepted_v1/portrait_selection_v1.json"
    ),
    "framing_audit": (
        "art/portraits/framing_audit_v1/framing_audit_v1.json"
    ),
    "accepted_pair_framing_boxes_contact.png": (
        "art/portraits/framing_audit_v1/accepted_pair_framing_boxes_contact.png"
    ),
    "skill_cutin_qa_contact.png": (
        "art/ui/ui_assets_canary_v3/skill_cutin_qa_contact.png"
    ),
    "ui_derivatives_contact.png": (
        "art/ui/ui_assets_canary_v3/ui_derivatives_contact.png"
    ),
}


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_visual_evidence(build_root: Path) -> dict[str, Any]:
    """Hash and semantically validate the user-approved UI visual evidence."""

    root = Path(build_root)
    try:
        files = {
            name: (root / Path(*relative.split("/"))).read_bytes()
            for name, relative in _VISUAL_PATHS.items()
        }
        selection = json.loads(files["portrait_selection"].decode("utf-8"))
        framing = json.loads(files["framing_audit"].decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageAssemblyError("UI visual QA evidence is unreadable") from exc
    report = {
        "portrait_selection_sha256": _sha256(files["portrait_selection"]),
        "framing_audit_sha256": _sha256(files["framing_audit"]),
        "contact_sha256": {
            name: _sha256(files[name])
            for name in LOCKED_VISUAL_EVIDENCE["contact_sha256"]
        },
        "user_approved_locked_pair": (
            isinstance(selection, dict)
            and selection.get("status") == "user_approved_locked_pair"
            and selection.get("package_manifest_eligible") is True
            and selection.get("writes_live") is False
            and isinstance(framing, dict)
            and framing.get("input_policy", {}).get("accepted_pair_only") is True
            and framing.get("input_policy", {}).get("forbidden_source_used") is False
        ),
        "writes_live": False,
    }
    if report != LOCKED_VISUAL_EVIDENCE:
        raise PackageAssemblyError("UI visual QA evidence identity drift")
    return report


def _framing_rows(master_files: Mapping[str, bytes]) -> None:
    required = {
        master_compile.CHARACTER_IMAGE_LOGICAL,
        master_compile.FULL_SHOT_LOGICAL,
        master_compile.TRIMMED_IMAGE_LOGICAL,
    }
    if not required.issubset(master_files):
        raise PackageAssemblyError("three-table framing payload is incomplete")
    key = str(CHARACTER_ID)
    for logical in (
        master_compile.CHARACTER_IMAGE_LOGICAL,
        master_compile.FULL_SHOT_LOGICAL,
    ):
        try:
            ordered = core.read_orderedmap_raw_rows_from_bytes(
                master_files[logical], logical,
            )
            rows = dict(zip(ordered.keys, ordered.rows, strict=True))
            actual = quest.parse_node(rows[key])
        except Exception as exc:
            raise PackageAssemblyError("three-table framing row is unreadable") from exc
        if actual != master_compile.IMAGE_ROWS[logical]:
            raise PackageAssemblyError("three-table framing row drift")
    try:
        trim = core.read_orderedmap_file_from_bytes(
            master_files[master_compile.TRIMMED_IMAGE_LOGICAL]
        )
    except Exception as exc:
        raise PackageAssemblyError("three-table framing trim table is unreadable") from exc
    if any(trim.get(logical) != row for logical, row in master_compile.TRIM_ROWS.items()):
        raise PackageAssemblyError("three-table framing trim rows drift")


def _commands(value: Any) -> Iterable[list[Any]]:
    if isinstance(value, list):
        if len(value) == 2 and value[0] == "Command" and isinstance(value[1], list):
            yield value[1]
        for item in value:
            yield from _commands(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from _commands(item)


def _action_semantics(action_files: Mapping[str, bytes]) -> None:
    actual_hashes = {
        logical: _sha256(bytes(raw)) for logical, raw in action_files.items()
    }
    if actual_hashes != LOCKED_ACTION_DSL_SHA256:
        raise PackageAssemblyError("ActionDSL identity drift")
    for logical, raw in action_files.items():
        try:
            tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
        except Exception as exc:
            raise PackageAssemblyError(f"ActionDSL is unreadable: {logical}") from exc
        commands = list(_commands(tree))
        effects = [command for command in commands if command[:1] == ["ShowEffect"]]
        hit_areas = [command for command in commands if command[:1] == ["CreateHitArea"]]
        if len(effects) != 1 or effects[0][2] != ["SpecifyEffectDirectly", _EFFECT_PATH]:
            raise PackageAssemblyError("ActionDSL effect integration drift")
        if (
            len(hit_areas) != 1
            or ["CalculatedUsingMaxNumOfHits", 55] not in hit_areas[0]
            or ["Some", [{"min": 55, "max": 55}]] not in hit_areas[0]
        ):
            raise PackageAssemblyError("ActionDSL 55-hit integration drift")


def build_package_acceptance(
    *,
    ui_report: Mapping[str, Any],
    visual_evidence: Mapping[str, Any],
    master_files: Mapping[str, bytes],
    effect_report: Mapping[str, Any],
    effect_closure: Mapping[str, Any],
    action_files: Mapping[str, bytes],
) -> dict[str, Any]:
    """Close producer holds only after package-level integration readback."""

    if dict(visual_evidence) != LOCKED_VISUAL_EVIDENCE:
        raise PackageAssemblyError("UI visual QA evidence drift")
    qa = ui_report.get("skill_cutin_qa")
    if (
        ui_report.get("package_manifest_eligible") is not False
        or ui_report.get("writes_live") is not False
        or not isinstance(qa, Mapping)
        or set(qa) != {"0", "1"}
        or any(
            not isinstance(qa[form], Mapping)
            or qa[form].get("size") != [1024, 512]
            or qa[form].get("problems") != []
            for form in ("0", "1")
        )
    ):
        raise PackageAssemblyError("UI visual QA producer contract drift")
    _framing_rows(master_files)
    if (
        effect_report.get("package_manifest_eligible") is not False
        or effect_report.get("writes_live") is not False
        or any(
            effect_report.get(field) is not False
            for field in ("contains_character", "contains_scene", "contains_powerflip")
        )
    ):
        raise PackageAssemblyError("effect producer contract drift")
    if dict(effect_closure) != {
        "texture_reference_count": 10,
        "atlas_record_count": 10,
        "missing_textures": [],
    }:
        raise PackageAssemblyError("effect runtime closure drift")
    _action_semantics(action_files)
    return {
        "schema_version": 1,
        "package_manifest_eligible": True,
        "ui": {
            "producer_eligible": False,
            "closed_by": [
                "user-approved portrait pair and locked visual QA contact evidence",
                "skill cut-in alpha/size QA readback",
                "character_image/full_shot_image_attribute/trimmed_image readback",
            ],
            "visual_evidence": dict(visual_evidence),
            "framing_table_count": 3,
        },
        "effect": {
            "producer_eligible": False,
            "closed_by": [
                "10-of-10 runtime atlas texture closure",
                "two hash-locked ActionDSL programs reference the effect",
                "55-hit count and fixed effect path decoded from both programs",
            ],
            "action_program_count": 2,
            "hit_count": 55,
            "effect_path": _EFFECT_PATH,
            "action_sha256": dict(LOCKED_ACTION_DSL_SHA256),
        },
        "writes_live": False,
    }


__all__ = [
    "CHARACTER_ID", "LOCKED_VISUAL_EVIDENCE", "LOCKED_ACTION_DSL_SHA256",
    "load_visual_evidence", "build_package_acceptance",
]
