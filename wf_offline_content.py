#!/usr/bin/env python3
"""Fail-closed content gate for the offline Android release bundle.

This module deliberately reads only the staged three-root snapshot and optional
character workspaces supplied by its caller.  It never falls back to the live
store: a missing, inaccessible, or byte-different claim is a release blocker.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import zlib
from collections.abc import Callable, Collection, Mapping
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

from wf_character_requirements import (
    ACTION_SKILL_TABLE,
    MasterAssetReference,
    SWITCHED_ACTION_SKILL_TABLE,
    build_master_reference_report,
    char_asset_requirements,
    extract_master_asset_references,
    required_asset_paths,
)
from wf_character_workspace import inspect_workspace, load_workspace
from wf_character_pack import (
    PackPreflightError,
    _parse_transaction_claims,
    canonical_manifest_bytes,
    validate_manifest,
)
from wf_offline_store import ManifestEntry, StoreRoots
from wf_quest_lib import hashed_rel
import wf_dsl
import wf_mod_tool as core
from wf_dual_pf_contract import (
    DUAL_PF_EFFECTS, DUAL_PF_KEYS, DUAL_PF_PROGRAMS, bind_native_programs,
)
from wf_rogue_validate import (
    RogueDataReport,
    RogueValidationError,
    validate_release_data_only,
)


CHARACTER_MASTER_LOGICAL = "master/character/character.orderedmap"
CHARACTER_STATUS_MASTER_LOGICAL = "master/character/character_status.orderedmap"
CHARACTER_TEXT_MASTER_LOGICAL = "master/character/character_text.orderedmap"
ABILITY_MASTER_LOGICAL = "master/ability/ability.orderedmap"
LEADER_ABILITY_MASTER_LOGICAL = "master/ability/leader_ability.orderedmap"
ACTION_SKILL_MASTER_LOGICAL = "master/skill/action_skill.orderedmap"
SWITCHED_ACTION_SKILL_MASTER_LOGICAL = "master/skill/switched_action_skill.orderedmap"
POWER_FLIP_ACTION_MASTER_LOGICAL = "master/skill/power_flip_action.orderedmap"
UNIQUE_CONDITION_MASTER_LOGICAL = "master/character/unique_condition.orderedmap"
CHARACTER_SPEECH_MASTER_LOGICAL = "master/character/character_speech.orderedmap"
CHARACTER_GACHA_SOUND_MASTER_LOGICAL = "master/character/character_gacha_sound.orderedmap"
MANA_BOARD2_OPEN_MASTER_LOGICAL = "master/mana_board/mana_board2_open_condition.orderedmap"
UPSKILL_MASTER_LOGICAL = "master/mana_board/upskill.orderedmap"
CHARACTER_IMAGE_MASTER_LOGICAL = "master/generated/character_image.orderedmap"
FULL_SHOT_ATTRIBUTE_MASTER_LOGICAL = "master/character/full_shot_image_attribute.orderedmap"
GENERATED_MANA_BOARD_MASTER_LOGICAL = "master/generated/mana_board.orderedmap"
MANA_NODE_MASTER_LOGICAL = "master/mana_board/mana_node.orderedmap"
TRIMMED_IMAGE_MASTER_LOGICAL = "master/generated/trimmed_image.orderedmap"
CHARACTER_AWAKE_STATUS_MASTER_LOGICAL = "master/character/character_awake_status.orderedmap"
SKILL_PREVIEW_CHARACTER_MASTER_LOGICAL = "master/skill_preview/skill_preview_character.orderedmap"
CHARACTER_STANCE_DETAIL_MASTER_LOGICAL = "master/stance_detail/character_stance_detail.orderedmap"
CUSTOM_ABILITY_STRING_MASTER_LOGICAL = "master/string/custom_ability_string.orderedmap"
_ROOTS = ("common", "medium", "android")
_PHASE4_PREFIXES = ("character/", "battle/", "sound_effect/", "voice/")
PLAYER_CHARACTER_LOGICAL = "master/player/player_character.orderedmap"
PLAYER_EQUIPMENT_LOGICAL = "master/player/player_equipment.orderedmap"
PLAYER_ITEM_LOGICAL = "master/player/player_item.orderedmap"
# Tracked release contract.  Task 9's Phase-4 extractor must equal this
# sequence exactly; accepting an arbitrary subset would silently drop a pcode
# asset from the offline bundle evidence.
SERIS_PHASE4_ASSET_LOGICALS = (
    "character/seris_dragon_king/pixelart/special",
    "character/seris_dragon_king/ui/skill_cutin_dragon",
    "character/seris_dragon_king/ui/battle_control_board_dragon",
    "character/seris_dragon_king/ui/battle_member_status_dragon",
)
SERIS_PHASE4_SITE_IDS = (
    "preload_seris_dual_form_assets",
    "switch_special_pixel_slot_preserve_frame_scale",
    "default_seris_human_power_flip",
    "dynamic_seris_skill_cutin",
    "dynamic_seris_member_status_path",
    "refresh_seris_member_status_texture",
    "dynamic_seris_control_board_path",
    "refresh_seris_control_board_texture",
    "route_seris_skill_voice_by_form",
)
RENDER_SCALE_SITE_IDS = ("pixel-art", "member-view", "character-cell")
SERIS_PHASE4_CONCRETE_MEMBERS = {
    "character/seris_dragon_king/pixelart/special": (
        "character/seris_dragon_king/pixelart/special_sprite_sheet.png",
        "character/seris_dragon_king/pixelart/special_sprite_sheet.atlas.amf3.deflate",
        "character/seris_dragon_king/pixelart/special.frame.amf3.deflate",
        "character/seris_dragon_king/pixelart/special.timeline.amf3.deflate",
    ),
    "character/seris_dragon_king/ui/skill_cutin_dragon": (
        "character/seris_dragon_king/ui/skill_cutin_dragon.png",
        "character/seris_dragon_king/ui/skill_cutin_dragon.atf.deflate",
    ),
    "character/seris_dragon_king/ui/battle_control_board_dragon": (
        "character/seris_dragon_king/ui/battle_control_board_dragon.png",
    ),
    "character/seris_dragon_king/ui/battle_member_status_dragon": (
        "character/seris_dragon_king/ui/battle_member_status_dragon.png",
    ),
}
SERIS_POWER_FLIP_KEYS = (
    "override_seris_human_powerflip",
    "override_seris_dragon_special",
)
SERIS_ACTION_PROGRAMS = (
    "battle/action/skill/seris_dragon_king/seris_dragon_king",
    "battle/action/skill/seris_dragon_king/seris_dragon_king_2",
    "battle/action/skill/seris_dragon_king/seris_dragon_king_matched",
    "battle/action/skill/seris_dragon_king/seris_dragon_king_matched_2",
)
SERIS_POWER_FLIP_PROGRAMS = (
    "battle/action/power_flip/action/override/override_seris_human_powerflip$override_seris_human_powerflip_lv1",
    "battle/action/power_flip/action/override/override_seris_human_powerflip$override_seris_human_powerflip_lv2",
    "battle/action/power_flip/action/override/override_seris_human_powerflip$override_seris_human_powerflip_lv3",
    "battle/action/power_flip/action/override/override_seris_dragon_special$override_seris_dragon_special_lv1",
    "battle/action/power_flip/action/override/override_seris_dragon_special$override_seris_dragon_special_lv2",
    "battle/action/power_flip/action/override/override_seris_dragon_special$override_seris_dragon_special_lv3",
)
SERIS_EFFECT_BASES = frozenset({
    "battle/effect/powerflip/effect_powerflip_attack_beam/powerflip_attack_beam_one",
    "battle/effect/powerflip/effect_powerflip_attack_beam/powerflip_attack_beam_two_small",
    "battle/effect/powerflip/effect_powerflip_attack_beam/powerflip_attack_beam_two_medium",
    "battle/effect/powerflip/effect_powerflip_attack_beam/powerflip_attack_beam_three_small",
    "battle/effect/powerflip/effect_powerflip_attack_beam/powerflip_attack_beam_three_medium",
    "battle/effect/powerflip/effect_powerflip_attack_beam/powerflip_attack_beam_three_large",
    "battle/effect/powerflip/effect_powerflip_attack_special/powerflip_attack_special_one",
    "battle/effect/powerflip/effect_powerflip_attack_special/powerflip_attack_special_two",
    "battle/effect/powerflip/effect_powerflip_attack_special/powerflip_attack_special_three",
    "battle/effect/powerflip/effect_powerflip_attack_special/powerflip_attack_special_player_one",
    "battle/effect/powerflip/effect_powerflip_attack_special/powerflip_attack_special_player_two",
    "battle/effect/powerflip/effect_powerflip_attack_special/powerflip_attack_special_player_three",
    "battle/effect/powerflip/seris_human_shooting_powerflip/seris_human_shooting_powerflip_lv1",
    "battle/effect/powerflip/seris_human_shooting_powerflip/seris_human_shooting_powerflip_lv2",
    "battle/effect/powerflip/seris_human_shooting_powerflip/seris_human_shooting_powerflip_lv3",
    "battle/effect/powerflip/seris_dragon_special_powerflip/seris_dragon_special_powerflip_lv1",
    "battle/effect/powerflip/seris_dragon_special_powerflip/seris_dragon_special_powerflip_lv2",
    "battle/effect/powerflip/seris_dragon_special_powerflip/seris_dragon_special_powerflip_lv3",
    "battle/effect/skill_unique/seris_human_royal_tide_ring/seris_human_royal_tide_ring",
    "battle/effect/skill_unique/seris_dragon_king/seris_dragon_king_transform",
    "battle/effect/skill_unique/seris_dragon_frozen_thunder_breath/seris_dragon_frozen_thunder_breath",
})
GERALD_UNCLAIMED_POWER_FLIP_KEY = "white_wolf_gerald_pf"
GERALD_LEADER_POWER_FLIP_LOCATION = (6, 80)
GERALD_POWER_FLIP_PROGRAMS = tuple(
    f"battle/action/power_flip/action/override/white_wolf_gerald_pf$white_wolf_gerald_pf_lv{level}"
    for level in range(1, 4)
)
WORKSPACE_ACTION_PROGRAMS = {
    (139999, "stella_summer_goddess"): (
        "battle/action/skill/action/rare5/stella_summer_goddess$stella_summer_goddess_1",
        "battle/action/skill/action/rare5/stella_summer_goddess$stella_summer_goddess_2",
    ),
    (149999, "white_wolf_gerald"): (
        "battle/action/skill/action/rare5/white_wolf_gerald$white_wolf_gerald_1",
        "battle/action/skill/action/rare5/white_wolf_gerald$white_wolf_gerald_2",
    ),
    (129992, "unicorn_lancer_rose"): (
        "battle/action/skill/action/rare5/unicorn_lancer_rose$unicorn_lancer_rose_1",
        "battle/action/skill/action/rare5/unicorn_lancer_rose$unicorn_lancer_rose_2",
    ),
    (139995, "fox_oracle_autumn"): (
        "battle/action/skill/action/rare5/fox_oracle_autumn$fox_oracle_autumn_1",
        "battle/action/skill/action/rare5/fox_oracle_autumn$fox_oracle_autumn_2",
    ),
}
WORKSPACE_ABILITY_PROGRAMS = {
    (139999, "stella_summer_goddess"): (),
    (149999, "white_wolf_gerald"): (
        "battle/action/skill/action/ability_skill/"
        "ability_skill_white_wolf_moon_fang$ability_skill_white_wolf_moon_fang",
        "battle/action/skill/action/ability_skill/"
        "ability_skill_gerald_time_rift$ability_skill_gerald_time_rift",
        "battle/action/skill/action/ability_skill/"
        "ability_skill_gerald_dash_lock$ability_skill_gerald_dash_lock",
    ),
    (129992, "unicorn_lancer_rose"): (),
    # V12(包 1.0.9):Fever 成长改回原生 134/461 层数计数,两条 I629 词条行与它们
    # 的 ability_skill DSL 一并下线,稻穗不再拥有任何词条动作程序。
    (139995, "fox_oracle_autumn"): (),
}
WORKSPACE_ABILITY_ROW_COUNTS = {
    (139999, "stella_summer_goddess"): (2, 2, 5, 1, 1, 1),
    (149999, "white_wolf_gerald"): (3, 2, 8, 2, 6, 1),
    (129992, "unicorn_lancer_rose"): (2, 3, 5, 2, 2, 2),
    (139995, "fox_oracle_autumn"): (6, 3, 8, 2, 2, 1),
}
WORKSPACE_LEADER_ROW_COUNTS = {
    (139999, "stella_summer_goddess"): 5,
    (149999, "white_wolf_gerald"): 10,
    (129992, "unicorn_lancer_rose"): 9,
    (139995, "fox_oracle_autumn"): 11,
}
WORKSPACE_ABILITY_PROGRAM_LOCATIONS = {
    (139999, "stella_summer_goddess"): (),
    (149999, "white_wolf_gerald"): (
        ("1499992", 0, 71, WORKSPACE_ABILITY_PROGRAMS[
            (149999, "white_wolf_gerald")
        ][1]),
        ("1499992", 1, 71, WORKSPACE_ABILITY_PROGRAMS[
            (149999, "white_wolf_gerald")
        ][2]),
        ("1499993", 6, 71, WORKSPACE_ABILITY_PROGRAMS[
            (149999, "white_wolf_gerald")
        ][0]),
    ),
    (129992, "unicorn_lancer_rose"): (),
    (139995, "fox_oracle_autumn"): (),
}
STELLA_EFFECT = "battle/effect/skill_unique/stella_ballot23/stella_ballot23"
GERALD_SKILL1_EFFECTS = frozenset({
        "battle/effect/skill_unique/white_wolf_gerald/clock_field",
        "battle/effect/skill_unique/white_wolf_gerald/crystal_burst",
        "battle/effect/skill_unique/white_wolf_gerald/moon_cross_single",
        "battle/effect/skill_unique/white_wolf_gerald/time_aura/time_aura",
        "battle/effect/skill_unique/white_wolf_gerald/time_stop",
    })
GERALD_SKILL2_EFFECTS = frozenset({
        "battle/effect/skill_unique/white_wolf_gerald/clock_field",
        "battle/effect/skill_unique/white_wolf_gerald/crystal_burst",
        "battle/effect/skill_unique/white_wolf_gerald/dash_trail",
        "battle/effect/skill_unique/white_wolf_gerald/moon_cross",
        "battle/effect/skill_unique/white_wolf_gerald/time_aura/time_aura",
    })
GERALD_MOON_FANG_EFFECTS = frozenset({
        "battle/effect/skill_unique/white_wolf_gerald/moon_cross",
        "battle/effect/skill_unique/white_wolf_gerald/rainbow_burst/rainbow_burst",
    })
GERALD_TIME_RIFT_EFFECTS = frozenset({
        "battle/effect/skill_unique/white_wolf_gerald/time_rift",
    })
UNICORN_LANCER_ROSE_SKILL_EFFECTS = frozenset({
    "battle/effect/skill_unique/unicorn_lancer_rose/lance/lance",
    "battle/effect/skill_unique/unicorn_lancer_rose/lance/lance_end",
    "battle/effect/skill_unique/unicorn_lancer_rose/unicorn_lancer_rose",
    "battle/effect/skill_unique/unicorn_lancer_rose/unicorn_lancer_rose_end",
    "battle/effect/skill_unique/unicorn_lancer_rose_api/unicorn_lancer_rose_api",
})
FOX_AUTUMN_ALL_EFFECT = "battle/effect/skill_unique/fox_oracle_autumn/fox_oracle_autumn_all"
FOX_AUTUMN_HIT_EFFECT = "battle/effect/skill_unique/fox_oracle_autumn/fox_oracle_autumn_hit"
FOX_AUTUMN_API_EFFECT = "battle/effect/skill_unique/fox_oracle_autumn_api/fox_oracle_autumn_api"
FOX_AUTUMN_SKILL_EFFECTS = frozenset({
    FOX_AUTUMN_ALL_EFFECT, FOX_AUTUMN_HIT_EFFECT, FOX_AUTUMN_API_EFFECT,
})
WORKSPACE_PROGRAM_EFFECTS = {
    **DUAL_PF_EFFECTS,
    WORKSPACE_ACTION_PROGRAMS[(139999, "stella_summer_goddess")][0]: frozenset({STELLA_EFFECT}),
    WORKSPACE_ACTION_PROGRAMS[(139999, "stella_summer_goddess")][1]: frozenset({STELLA_EFFECT}),
    WORKSPACE_ACTION_PROGRAMS[(149999, "white_wolf_gerald")][0]: GERALD_SKILL1_EFFECTS,
    WORKSPACE_ACTION_PROGRAMS[(149999, "white_wolf_gerald")][1]: GERALD_SKILL2_EFFECTS,
    WORKSPACE_ABILITY_PROGRAMS[(149999, "white_wolf_gerald")][0]: GERALD_MOON_FANG_EFFECTS,
    WORKSPACE_ABILITY_PROGRAMS[(149999, "white_wolf_gerald")][1]: GERALD_TIME_RIFT_EFFECTS,
    WORKSPACE_ABILITY_PROGRAMS[(149999, "white_wolf_gerald")][2]: frozenset(),
    **{
        program: frozenset({
            "battle/effect/powerflip/white_wolf_gerald_powerflip/"
            f"white_wolf_gerald_powerflip_lv{level}"
        })
        for level, program in enumerate(GERALD_POWER_FLIP_PROGRAMS, 1)
    },
    WORKSPACE_ACTION_PROGRAMS[(129992, "unicorn_lancer_rose")][0]:
        UNICORN_LANCER_ROSE_SKILL_EFFECTS,
    WORKSPACE_ACTION_PROGRAMS[(129992, "unicorn_lancer_rose")][1]:
        UNICORN_LANCER_ROSE_SKILL_EFFECTS,
    WORKSPACE_ACTION_PROGRAMS[(139995, "fox_oracle_autumn")][0]: FOX_AUTUMN_SKILL_EFFECTS,
    WORKSPACE_ACTION_PROGRAMS[(139995, "fox_oracle_autumn")][1]: FOX_AUTUMN_SKILL_EFFECTS,
}
SERVER_CHARACTER_LOGICALS = (
    "character.json",
    "cdndata/character.json",
    "cdndata/character_text.json",
    "mana_node.json",
)
EXPECTED_SERVER_SKILL_COUNTS = {
    129999: 6, 139999: 3, 149999: 6, 129992: 6, 139995: 6,
}


class ContentGateError(RuntimeError):
    pass


def validate_rogue_data(
    store: Path,
    assets_dir: Path,
    *,
    access_hook: Callable[[str], None] | None = None,
) -> RogueDataReport:
    """Local seam keeps the offline gate pure and easy to audit/test."""
    report = (
        validate_release_data_only(store, assets_dir)
        if access_hook is None
        else validate_release_data_only(
            store,
            assets_dir,
            access_hook=access_hook,
        )
    )
    if report.event_id != 700099 or report.round_count != 15:
        raise RogueValidationError("rush event 700099 must have exactly 15 rounds")
    if report.token_id != 2370099 or report.weapon_ids != tuple(range(8000101, 8000116)):
        raise RogueValidationError("rogue token or weapon set mismatch")
    if report.missing_logicals or not report.ready:
        raise RogueValidationError("rogue shop/mirror/reward/icon content is incomplete")
    return report


@dataclass(frozen=True, slots=True)
class CharacterReleaseSpec:
    character_id: int
    code_name: str


CHARACTERS = (
    CharacterReleaseSpec(129999, "seris_dragon_king"),
    CharacterReleaseSpec(139999, "stella_summer_goddess"),
    CharacterReleaseSpec(149999, "white_wolf_gerald"),
    CharacterReleaseSpec(129992, "unicorn_lancer_rose"),
    CharacterReleaseSpec(139995, "fox_oracle_autumn"),
)


@dataclass(frozen=True, slots=True)
class _WorkspaceMasterContract:
    logical_path: str
    codec_id: Literal["flat", "raw_outer", "action_nested", "switched_nested"]
    outer_keys: tuple[str, ...]
    inner_keys: tuple[tuple[str, tuple[str, ...]], ...] = ()


def _workspace_master_contracts(spec: CharacterReleaseSpec) -> tuple[_WorkspaceMasterContract, ...]:
    """Return the complete character-specific contract captured by real packs."""
    character_id = str(spec.character_id)
    abilities = tuple(f"{character_id}{index}" for index in range(1, 7))
    core_contracts = (
        _WorkspaceMasterContract(ABILITY_MASTER_LOGICAL, "flat", abilities),
        _WorkspaceMasterContract(LEADER_ABILITY_MASTER_LOGICAL, "flat", (character_id,)),
        _WorkspaceMasterContract(CHARACTER_MASTER_LOGICAL, "flat", (character_id,)),
        _WorkspaceMasterContract(CHARACTER_SPEECH_MASTER_LOGICAL, "flat", (character_id,)),
        _WorkspaceMasterContract(CHARACTER_STATUS_MASTER_LOGICAL, "raw_outer", (character_id,)),
        _WorkspaceMasterContract(CHARACTER_TEXT_MASTER_LOGICAL, "flat", (character_id,)),
        _WorkspaceMasterContract(FULL_SHOT_ATTRIBUTE_MASTER_LOGICAL, "raw_outer", (character_id,)),
        _WorkspaceMasterContract(CHARACTER_IMAGE_MASTER_LOGICAL, "raw_outer", (character_id,)),
        _WorkspaceMasterContract(GENERATED_MANA_BOARD_MASTER_LOGICAL, "raw_outer", (character_id,)),
        _WorkspaceMasterContract(MANA_BOARD2_OPEN_MASTER_LOGICAL, "flat", (character_id,)),
        _WorkspaceMasterContract(MANA_NODE_MASTER_LOGICAL, "raw_outer", (character_id,)),
        _WorkspaceMasterContract(
            ACTION_SKILL_MASTER_LOGICAL,
            "action_nested",
            (spec.code_name,),
            ((spec.code_name, ("1", "2")),),
        ),
    )
    if spec.character_id == 129999 and spec.code_name == "seris_dragon_king":
        trimmed = tuple(
            f"character/{spec.code_name}/ui/{name}"
            for name in (
                "full_shot_1440_1920_0", "full_shot_1440_1920_1",
                "skill_cutin_0", "skill_cutin_1", "skill_cutin_matched_0",
                "skill_cutin_matched_1", "skill_cutin_dragon",
            )
        )
        return (*core_contracts,
            _WorkspaceMasterContract(CHARACTER_AWAKE_STATUS_MASTER_LOGICAL, "flat", (character_id,)),
            _WorkspaceMasterContract(UNIQUE_CONDITION_MASTER_LOGICAL, "flat", ("22", "23")),
            _WorkspaceMasterContract(TRIMMED_IMAGE_MASTER_LOGICAL, "flat", trimmed),
            _WorkspaceMasterContract(POWER_FLIP_ACTION_MASTER_LOGICAL, "flat", SERIS_POWER_FLIP_KEYS),
            _WorkspaceMasterContract(
                SWITCHED_ACTION_SKILL_MASTER_LOGICAL,
                "switched_nested",
                (spec.code_name,),
                ((spec.code_name, ("1", "2")),),
            ),
        )
    if spec.character_id == 139999 and spec.code_name == "stella_summer_goddess":
        return (*core_contracts,
            _WorkspaceMasterContract(CHARACTER_GACHA_SOUND_MASTER_LOGICAL, "raw_outer", (character_id,)),
            _WorkspaceMasterContract(SKILL_PREVIEW_CHARACTER_MASTER_LOGICAL, "flat", (character_id,)),
            _WorkspaceMasterContract(CHARACTER_STANCE_DETAIL_MASTER_LOGICAL, "flat", (character_id,)),
        )
    if spec.character_id == 149999 and spec.code_name == "white_wolf_gerald":
        trimmed = tuple(
            f"character/{spec.code_name}/ui/{name}"
            for name in (
                "full_shot_1440_1920_0", "full_shot_1440_1920_1",
                "skill_cutin_0", "skill_cutin_1",
            )
        )
        return (*core_contracts,
            _WorkspaceMasterContract(CHARACTER_GACHA_SOUND_MASTER_LOGICAL, "raw_outer", (character_id,)),
            _WorkspaceMasterContract(SKILL_PREVIEW_CHARACTER_MASTER_LOGICAL, "flat", (character_id,)),
            _WorkspaceMasterContract(UPSKILL_MASTER_LOGICAL, "flat", (character_id,)),
            _WorkspaceMasterContract(CHARACTER_STANCE_DETAIL_MASTER_LOGICAL, "flat", (character_id,)),
            _WorkspaceMasterContract(TRIMMED_IMAGE_MASTER_LOGICAL, "flat", trimmed),
            _WorkspaceMasterContract(
                CUSTOM_ABILITY_STRING_MASTER_LOGICAL,
                "flat",
                ("ability_skill_white_wolf_moon_fang",),
            ),
        )
    if spec.character_id == 129992 and spec.code_name == "unicorn_lancer_rose":
        trimmed = tuple(
            f"character/{spec.code_name}/ui/{name}"
            for name in (
                "full_shot_1440_1920_0", "full_shot_1440_1920_1",
                "skill_cutin_0", "skill_cutin_1",
            )
        )
        return (*core_contracts,
            _WorkspaceMasterContract(POWER_FLIP_ACTION_MASTER_LOGICAL, "flat", (DUAL_PF_KEYS[(spec.character_id, spec.code_name)],)),
            _WorkspaceMasterContract(CHARACTER_AWAKE_STATUS_MASTER_LOGICAL, "flat", (character_id,)),
            _WorkspaceMasterContract(CHARACTER_GACHA_SOUND_MASTER_LOGICAL, "raw_outer", (character_id,)),
            _WorkspaceMasterContract(SKILL_PREVIEW_CHARACTER_MASTER_LOGICAL, "flat", (character_id,)),
            _WorkspaceMasterContract(UPSKILL_MASTER_LOGICAL, "flat", (character_id,)),
            _WorkspaceMasterContract(CHARACTER_STANCE_DETAIL_MASTER_LOGICAL, "flat", (character_id,)),
            _WorkspaceMasterContract(TRIMMED_IMAGE_MASTER_LOGICAL, "flat", trimmed),
            _WorkspaceMasterContract(UNIQUE_CONDITION_MASTER_LOGICAL, "flat", (character_id,)),
            _WorkspaceMasterContract(
                CUSTOM_ABILITY_STRING_MASTER_LOGICAL,
                "flat",
                ("change_skill_unicorn_lancer_rose", "override_string_unicorn_lancer_rose_dual_pf"),
            ),
        )
    if spec.character_id == 139995 and spec.code_name == "fox_oracle_autumn":
        trimmed = tuple(
            f"character/{spec.code_name}/ui/{name}"
            for name in (
                "full_shot_1440_1920_0", "full_shot_1440_1920_1",
                "skill_cutin_0", "skill_cutin_1",
            )
        )
        return (*core_contracts,
            _WorkspaceMasterContract(POWER_FLIP_ACTION_MASTER_LOGICAL, "flat", (DUAL_PF_KEYS[(spec.character_id, spec.code_name)],)),
            _WorkspaceMasterContract(CHARACTER_AWAKE_STATUS_MASTER_LOGICAL, "flat", (character_id,)),
            _WorkspaceMasterContract(CHARACTER_GACHA_SOUND_MASTER_LOGICAL, "raw_outer", (character_id,)),
            _WorkspaceMasterContract(SKILL_PREVIEW_CHARACTER_MASTER_LOGICAL, "flat", (character_id,)),
            _WorkspaceMasterContract(UPSKILL_MASTER_LOGICAL, "flat", (character_id,)),
            _WorkspaceMasterContract(CHARACTER_STANCE_DETAIL_MASTER_LOGICAL, "flat", (character_id,)),
            _WorkspaceMasterContract(TRIMMED_IMAGE_MASTER_LOGICAL, "flat", trimmed),
            _WorkspaceMasterContract(UNIQUE_CONDITION_MASTER_LOGICAL, "flat", ("139995", "1399951", "1399952")),
            _WorkspaceMasterContract(
                CUSTOM_ABILITY_STRING_MASTER_LOGICAL,
                "flat",
                ("ability_skill_fox_oracle_autumn_fever_pf",
                 "override_string_fox_oracle_autumn_dual_pf",
                 # 1.1.1: V11 panel override for ability 2 (「Fever模式中，无法获得Fever」 is a
                 # -2000% FeverPoint during row natively; the author wants the plain wording).
                 "desc_override_fox_oracle_autumn_2",
                 "desc_override_fox_oracle_autumn"),
            ),
        )
    raise ContentGateError(
        f"unsupported character workspace identity: {spec.character_id}/{spec.code_name}"
    )


@dataclass(frozen=True, slots=True)
class CharacterEvidenceReport:
    identity: Mapping[str, int | str]
    evidence_mode: Literal["sealed-workspace", "published-snapshot"]
    required_present: int
    required_total: int
    three_layer_consistent: bool
    bound_files: tuple[ManifestEntry, ...]
    missing: tuple[str, ...]
    seal_sha256: str
    rejected_workspace_reason: str | None = None


@dataclass(frozen=True, slots=True)
class OfflineContentReport:
    rogue: RogueDataReport
    characters: tuple[CharacterEvidenceReport, ...]
    client_gate_ready: bool | None
    ready: bool


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _strict_json_load(text: str, label: str) -> Any:
    """Reject JSON extensions that can silently alter a release decision."""
    def reject_constant(value: str) -> Any:
        raise ValueError(f"non-standard JSON constant {value}")

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        return json.loads(text, parse_constant=reject_constant, object_pairs_hook=reject_duplicates)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ContentGateError(f"{label} is unreadable: {exc}") from exc


def sha256_canonical_report(report: CharacterEvidenceReport) -> str:
    """Return a stable report seal, excluding the recursive seal field."""
    value = asdict(report)
    value["seal_sha256"] = ""
    return hashlib.sha256(_canonical(value)).hexdigest()


def _require_logical(logical: str, *, phase4: bool = False) -> str:
    if not isinstance(logical, str) or not logical or logical.startswith("/") or "\\" in logical:
        raise ContentGateError(f"unsafe {'Phase 4 ' if phase4 else ''}asset literal: {logical!r}")
    if any(part in ("", ".", "..") for part in logical.split("/")):
        raise ContentGateError(f"unsafe {'Phase 4 ' if phase4 else ''}asset literal: {logical!r}")
    if phase4 and not logical.startswith(_PHASE4_PREFIXES):
        raise ContentGateError(f"Phase 4 asset literal is outside permitted roots: {logical}")
    return logical


def _read_file_bytes(root: Path, logical: str, root_name: str) -> tuple[ManifestEntry, bytes]:
    path = Path(root) / hashed_rel(logical)
    try:
        before = path.lstat()
    except FileNotFoundError as exc:
        raise ContentGateError(f"missing logical {root_name}:{logical}") from exc
    except OSError as exc:
        raise ContentGateError(f"cannot inspect logical {root_name}:{logical}: {exc}") from exc
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    is_reparse = bool(getattr(before, "st_file_attributes", 0) & reparse)
    if stat.S_ISLNK(before.st_mode) or is_reparse:
        raise ContentGateError(f"reparse/symlink logical is forbidden: {root_name}:{logical}")
    if not stat.S_ISREG(before.st_mode):
        raise ContentGateError(f"logical is not a regular file: {root_name}:{logical}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags)
        try:
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise ContentGateError(f"logical changed before reading: {root_name}:{logical}")
            chunks: list[bytes] = []
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            finished = os.fstat(fd)
        finally:
            os.close(fd)
        raw = b"".join(chunks)
        after = path.lstat()
    except OSError as exc:
        raise ContentGateError(f"cannot read logical {root_name}:{logical}: {exc}") from exc
    if (
        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (finished.st_dev, finished.st_ino, finished.st_size, finished.st_mtime_ns)
        or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        or len(raw) != finished.st_size
    ):
        raise ContentGateError(f"logical changed while reading: {root_name}:{logical}")
    return (
        ManifestEntry(f"roots/{root_name}/{logical}", len(raw), hashlib.sha256(raw).hexdigest(), f"snapshot:{root_name}"),
        raw,
    )


def _read_file(root: Path, logical: str, root_name: str) -> ManifestEntry:
    return _read_file_bytes(root, logical, root_name)[0]


@dataclass(slots=True)
class _SnapshotEvidence:
    """One-operation byte and parse cache for an immutable three-root snapshot.

    A gate decision must never hash version A of a master and then parse
    version B.  Every caller in one release decision shares this object, so a
    logical is opened once and its ``ManifestEntry`` and semantic rows are
    derived from the same captured bytes.
    """

    snapshot: StoreRoots
    access_guard: Callable[[str, str], None] | None = None
    root_inventory: Mapping[str, Collection[str]] | None = None
    captures: dict[tuple[str, str], tuple[ManifestEntry, bytes]] = field(default_factory=dict)
    capture_signatures: dict[tuple[str, str], tuple[int, ...]] = field(default_factory=dict)
    owners: dict[str, tuple[str, ...]] = field(default_factory=dict)
    ordered_rows: dict[str, dict[str, bytes]] = field(default_factory=dict)

    def _capture_signature(self, root_name: str, logical: str) -> tuple[int, ...]:
        path = Path(getattr(self.snapshot, root_name)) / hashed_rel(logical)
        try:
            metadata = path.lstat()
        except OSError as exc:
            raise ContentGateError(f"cannot recheck captured logical {root_name}:{logical}: {exc}") from exc
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if (
            stat.S_ISLNK(metadata.st_mode)
            or bool(getattr(metadata, "st_file_attributes", 0) & reparse)
            or not stat.S_ISREG(metadata.st_mode)
        ):
            raise ContentGateError(f"captured logical is no longer a regular file: {root_name}:{logical}")
        return (
            int(getattr(metadata, "st_dev", 0)),
            int(getattr(metadata, "st_ino", 0)),
            int(metadata.st_size),
            int(metadata.st_mtime_ns),
            int(getattr(metadata, "st_ctime_ns", 0)),
            int(getattr(metadata, "st_file_attributes", 0)),
        )

    def _root_owners(self, logical: str) -> tuple[str, ...]:
        logical = _require_logical(logical)
        found: list[str] = []
        for root_name in _ROOTS:
            path = Path(getattr(self.snapshot, root_name)) / hashed_rel(logical)
            if self.root_inventory is not None:
                if set(self.root_inventory) != set(_ROOTS):
                    raise ContentGateError("snapshot root inventory schema is invalid")
                relative = str(hashed_rel(logical)).replace("\\", "/")
                if relative not in self.root_inventory[root_name]:
                    continue
                if self.access_guard is not None:
                    self.access_guard(root_name, logical)
            try:
                metadata = path.lstat()
            except FileNotFoundError:
                continue
            except OSError as exc:
                raise ContentGateError(f"cannot inspect logical {root_name}:{logical}: {exc}") from exc
            reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            if stat.S_ISLNK(metadata.st_mode) or bool(getattr(metadata, "st_file_attributes", 0) & reparse):
                raise ContentGateError(f"reparse/symlink logical is forbidden: {root_name}:{logical}")
            if not stat.S_ISREG(metadata.st_mode):
                raise ContentGateError(f"logical is not a regular file: {root_name}:{logical}")
            if self.access_guard is not None and self.root_inventory is None:
                self.access_guard(root_name, logical)
            found.append(root_name)
        result = tuple(found)
        previous = self.owners.get(logical)
        if previous is not None and previous != result:
            raise ContentGateError(
                f"snapshot root ownership changed for {logical}: before={previous} after={result}"
            )
        self.owners.setdefault(logical, result)
        return result

    def read_root(self, root_name: str, logical: str) -> tuple[ManifestEntry, bytes]:
        if root_name not in _ROOTS:
            raise ContentGateError(f"invalid snapshot root: {root_name!r}")
        logical = _require_logical(logical)
        owners = self._root_owners(logical)
        if not owners:
            raise ContentGateError(f"missing logical {root_name}:{logical}")
        if root_name not in owners:
            raise ContentGateError(
                f"root ownership mismatch for {logical}: expected {root_name}, actual {owners[0]}"
            )
        if len(owners) != 1:
            raise ContentGateError(f"ambiguous three-root logical: {logical}")
        key = (root_name, logical)
        if key not in self.captures:
            self.captures[key] = _read_file_bytes(
                Path(getattr(self.snapshot, root_name)), logical, root_name
            )
            self.capture_signatures[key] = self._capture_signature(root_name, logical)
        elif self._capture_signature(root_name, logical) != self.capture_signatures[key]:
            raise ContentGateError(f"snapshot logical changed after capture: {root_name}:{logical}")
        return self.captures[key]

    def resolve(self, logical: str) -> tuple[ManifestEntry, bytes]:
        logical = _require_logical(logical)
        owners = self._root_owners(logical)
        if not owners:
            raise ContentGateError(f"missing logical in frozen snapshot: {logical}")
        if len(owners) != 1:
            raise ContentGateError(f"ambiguous three-root logical: {logical}")
        return self.read_root(owners[0], logical)

    def ordered(self, logical: str) -> dict[str, bytes]:
        logical = _require_logical(logical)
        if logical in self.ordered_rows:
            # A parse cache is evidence, not permission to skip filesystem
            # drift checks.  Revalidate ownership/signature before returning
            # the rows derived from the captured bytes.
            self.resolve(logical)
            return self.ordered_rows[logical]
        entry, raw = self.resolve(logical)
        if entry.source != "snapshot:common":
            raise ContentGateError(f"master table must be in common root: {logical}")
        try:
            ordered = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
        except Exception as exc:
            raise ContentGateError(f"cannot parse master table {logical}: {exc}") from exc
        if len(set(ordered.keys)) != len(ordered.keys):
            raise ContentGateError(f"master table has duplicate outer keys: {logical}")
        rows = dict(zip(ordered.keys, ordered.rows))
        self.ordered_rows[logical] = rows
        return rows

    def audit(self) -> None:
        """Re-read every captured logical before sealing a ready decision.

        Metadata is only a fast drift signal: on Windows an in-place same-size
        rewrite can restore mtime while creation time remains unchanged.  A
        final release seal therefore compares fresh handle-bound bytes with the
        exact capture that supplied both hashes and parsed semantics.
        """
        for root_name, logical in tuple(self.captures):
            owners = self._root_owners(logical)
            if owners != (root_name,):
                raise ContentGateError(
                    f"snapshot root ownership changed before seal: {logical}: {owners!r}"
                )
            captured_entry, captured_raw = self.captures[(root_name, logical)]
            current_entry, current_raw = _read_file_bytes(
                Path(getattr(self.snapshot, root_name)), logical, root_name
            )
            if current_entry != captured_entry or current_raw != captured_raw:
                raise ContentGateError(
                    f"snapshot logical bytes changed after capture: {root_name}:{logical}"
                )
            current_signature = self._capture_signature(root_name, logical)
            if current_signature != self.capture_signatures[(root_name, logical)]:
                raise ContentGateError(
                    f"snapshot logical metadata changed after capture: {root_name}:{logical}"
                )


def _resolve_and_read_logical(snapshot: StoreRoots, logical: str) -> tuple[ManifestEntry, bytes]:
    return _SnapshotEvidence(snapshot).resolve(logical)


def _resolve_and_hash_logical(snapshot: StoreRoots, logical: str) -> ManifestEntry:
    return _resolve_and_read_logical(snapshot, logical)[0]


def verify_manifest_entries(
    entries: Collection[ManifestEntry],
    snapshot: StoreRoots,
    *,
    _evidence: _SnapshotEvidence | None = None,
) -> tuple[ManifestEntry, ...]:
    """Bind every claimed client-root entry by exact root, path, size and SHA."""
    evidence = _evidence or _SnapshotEvidence(snapshot)
    bound: list[ManifestEntry] = []
    for entry in entries:
        root_name = entry.source.removeprefix("snapshot:")
        if root_name not in _ROOTS:
            raise ContentGateError(f"manifest entry has invalid client root: {root_name!r}")
        prefix = f"roots/{root_name}/"
        if not entry.path.startswith(prefix):
            raise ContentGateError(f"manifest entry root/path mismatch: {entry.path}")
        logical = _require_logical(entry.path[len(prefix):])
        actual, _raw = evidence.read_root(root_name, logical)
        if actual.size != entry.size:
            raise ContentGateError(f"size mismatch for {root_name}:{entry.path}")
        if actual.sha256 != entry.sha256:
            raise ContentGateError(f"hash mismatch for {root_name}:{entry.path}")
        bound.append(actual)
    return tuple(bound)


def _required_37_logicals(code_name: str) -> set[str]:
    return {
        item.logical_path for item in char_asset_requirements(code_name)
        if item.category == "required"
    }


def expected_root_for_logical(logical: str) -> str:
    """Offline lookup ownership contract; never infer a root by first hit."""
    logical = _require_logical(logical)
    if logical.endswith(".atf.deflate"):
        return "android"
    if logical.startswith("character/") and "/ui/" in logical and logical.endswith(".png"):
        return "medium"
    return "common"


def expand_seris_phase4_asset_literals(asset_literals: Collection[str]) -> frozenset[str]:
    """Map Task9 P-code base literals to the concrete hashed store members."""
    values = tuple(_require_logical(value, phase4=True) for value in asset_literals)
    if len(set(values)) != len(values):
        raise ContentGateError("Phase 4 asset literal collection contains duplicates")
    literals = frozenset(values)
    required = frozenset(SERIS_PHASE4_ASSET_LOGICALS)
    if literals != required:
        missing = sorted(required - literals)
        extra = sorted(literals - required)
        detail = f"missing={missing}" if missing else f"unexpected={extra}"
        raise ContentGateError(f"Phase 4 asset literals do not match canonical contract: {detail}")
    return frozenset(member for literal in literals for member in SERIS_PHASE4_CONCRETE_MEMBERS[literal])


def _raw_ordered_rows(
    snapshot: StoreRoots,
    logical: str,
    *,
    _evidence: _SnapshotEvidence | None = None,
) -> dict[str, bytes]:
    return (_evidence or _SnapshotEvidence(snapshot)).ordered(logical)


def _character_references(
    snapshot: StoreRoots,
    spec: CharacterReleaseSpec,
    *,
    _evidence: _SnapshotEvidence | None = None,
) -> tuple[str, tuple[str, ...]]:
    row = _character_csv_row(snapshot, spec, _evidence=_evidence)
    action_skill = row[8]
    ability_ids = tuple(row[19:25])
    if not action_skill or any(not value or value == "0" for value in ability_ids):
        raise ContentGateError(f"character {spec.character_id} has incomplete action/ability references")
    return action_skill, ability_ids


def _character_csv_row(
    snapshot: StoreRoots,
    spec: CharacterReleaseSpec,
    *,
    _evidence: _SnapshotEvidence | None = None,
) -> list[str]:
    rows = _raw_ordered_rows(snapshot, CHARACTER_MASTER_LOGICAL, _evidence=_evidence)
    raw = rows.get(str(spec.character_id))
    if raw is None:
        raise ContentGateError(f"master outer key missing for character {spec.character_id}: {CHARACTER_MASTER_LOGICAL}")
    try:
        text = zlib.decompress(raw).decode("utf-8")
        parsed = core.read_csv_lines(text)
        row = parsed[0]
    except Exception as exc:
        raise ContentGateError(f"cannot decode character master row {spec.character_id}: {exc}") from exc
    if len(row) < 25:
        raise ContentGateError(f"character master row is too short for {spec.character_id}")
    if row[0] != spec.code_name:
        raise ContentGateError(
            f"character code_name mismatch: expected {spec.code_name}, actual {row[0]!r}"
        )
    if row[17] != str(spec.character_id):
        raise ContentGateError(f"character master ID column mismatch: expected {spec.character_id}, actual {row[17]!r}")
    return row


def _assert_character_master_identity(
    snapshot: StoreRoots,
    spec: CharacterReleaseSpec,
    *,
    _evidence: _SnapshotEvidence | None = None,
) -> tuple[ManifestEntry, ...]:
    evidence = _evidence or _SnapshotEvidence(snapshot)
    action_skill, ability_ids = _character_references(snapshot, spec, _evidence=evidence)
    entries: list[ManifestEntry] = [evidence.resolve(CHARACTER_MASTER_LOGICAL)[0]]
    # The exact ability/leader/skill key relationships are declared in package
    # table claims when a workspace is used.  Published-snapshot evidence has
    # no mutable manifest, so at minimum bind each referenced master container
    # and the directly addressable character/status/action outer keys.
    for logical, required_key in (
        (CHARACTER_STATUS_MASTER_LOGICAL, str(spec.character_id)),
        (CHARACTER_TEXT_MASTER_LOGICAL, str(spec.character_id)),
        (LEADER_ABILITY_MASTER_LOGICAL, str(spec.character_id)),
        (ACTION_SKILL_MASTER_LOGICAL, action_skill),
    ):
        entries.append(evidence.resolve(logical)[0])
        rows = _raw_ordered_rows(snapshot, logical, _evidence=evidence)
        keys = set(rows)
        if required_key is not None and required_key not in keys:
            raise ContentGateError(f"master outer key missing for {logical}: {required_key}")
        if not keys:
            raise ContentGateError(f"master reference table has no outer keys: {logical}")
    ability_rows = _raw_ordered_rows(snapshot, ABILITY_MASTER_LOGICAL, _evidence=evidence)
    entries.append(evidence.resolve(ABILITY_MASTER_LOGICAL)[0])
    for ability_id in ability_ids:
        if ability_id not in ability_rows:
            raise ContentGateError(f"master ability reference missing: {ability_id}")
    action_rows = _raw_ordered_rows(snapshot, ACTION_SKILL_MASTER_LOGICAL, _evidence=evidence)
    try:
        action_inner = core.read_orderedmap_raw_rows_from_bytes(action_rows[action_skill], f"{ACTION_SKILL_MASTER_LOGICAL}#{action_skill}")
    except Exception as exc:
        raise ContentGateError(f"master action skill inner map is unreadable: {action_skill}: {exc}") from exc
    if not {"1", "2"}.issubset(action_inner.keys):
        raise ContentGateError(f"master action skill inner keys missing: {action_skill}")
    return tuple(entries)


def _decode_flat_text(raw: bytes, label: str) -> str:
    try:
        return zlib.decompress(raw).decode("utf-8")
    except (UnicodeDecodeError, zlib.error) as exc:
        raise ContentGateError(f"master row is unreadable: {label}: {exc}") from exc


def _decode_nested_text_rows(
    rows: Mapping[str, bytes],
    *,
    logical: str,
    outer_key: str,
    required_inner: Collection[str],
    exact: bool = True,
) -> dict[str, str]:
    raw = rows.get(outer_key)
    if raw is None:
        raise ContentGateError(f"master outer key missing for {logical}: {outer_key}")
    try:
        nested = core.read_orderedmap_raw_rows_from_bytes(raw, f"{logical}#{outer_key}")
    except Exception as exc:
        raise ContentGateError(f"master inner map is unreadable: {logical}:{outer_key}: {exc}") from exc
    if len(set(nested.keys)) != len(nested.keys):
        raise ContentGateError(f"master inner map has duplicate keys: {logical}:{outer_key}")
    expected = {str(item) for item in required_inner}
    actual = set(nested.keys)
    expected_order = tuple(str(item) for item in required_inner)
    mismatch = tuple(nested.keys) != expected_order if exact else not expected.issubset(actual)
    if mismatch:
        raise ContentGateError(
            f"master inner keys mismatch: {logical}:{outer_key}: expected={sorted(expected)} actual={sorted(actual)}"
        )
    return {
        key: _decode_flat_text(raw_row, f"{logical}:{outer_key}:{key}")
        for key, raw_row in zip(nested.keys, nested.rows)
    }


def _decode_nested_raw_rows(raw: bytes, label: str) -> dict[str, bytes]:
    try:
        nested = core.read_orderedmap_raw_rows_from_bytes(raw, label)
    except Exception as exc:
        raise ContentGateError(f"master inner map is unreadable: {label}: {exc}") from exc
    if len(set(nested.keys)) != len(nested.keys):
        raise ContentGateError(f"master inner map has duplicate keys: {label}")
    return dict(zip(nested.keys, nested.rows))


def _dsl_unique_condition_ids(tree: Any) -> set[str]:
    """Extract ACUnique IDs that the generic master-reference extractor lacks."""
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, list):
            if node and node[0] == "ACUnique":
                if len(node) < 2 or isinstance(node[1], bool) or not (
                    isinstance(node[1], int)
                    or (isinstance(node[1], str) and node[1].isdigit())
                ):
                    raise ContentGateError(f"Seris DSL has malformed ACUnique node: {node!r}")
                found.add(str(node[1]))
            for item in node:
                walk(item)
        elif isinstance(node, Mapping):
            for item in node.values():
                walk(item)

    walk(tree)
    return found


def _bind_seris_published_closure(
    snapshot: StoreRoots,
    spec: CharacterReleaseSpec,
    evidence: _SnapshotEvidence,
) -> tuple[ManifestEntry, ...]:
    """Bind the complete published Seris master/DSL/effect closure.

    This function has no workspace input.  Every table row, DSL tree and
    derived asset is read from ``snapshot`` through ``evidence`` exactly once.
    """
    if (spec.character_id, spec.code_name) != (129999, "seris_dragon_king"):
        raise ContentGateError("published snapshot evidence is only defined for 129999/seris_dragon_king")

    bound: dict[tuple[str, str], ManifestEntry] = {}

    def bind_common(logical: str) -> bytes:
        entry, raw = evidence.read_root("common", logical)
        bound[(entry.source, entry.path)] = entry
        return raw

    character_row = _character_csv_row(snapshot, spec, _evidence=evidence)
    bind_common(CHARACTER_MASTER_LOGICAL)
    expected_character_cells = {
        0: "seris_dragon_king", 2: "5", 3: "1", 4: "Dragon",
        5: "ModDualForm", 6: "2", 7: "Male", 8: "seris_dragon_king",
        9: "1", 10: "28", 11: "22", 14: "seris_dragon_king",
        15: "false", 16: "false", 17: "129999", 27: "129999",
        36: "6,6,6,6,6,6",
    }
    if len(character_row) != 37 or any(
        character_row[index] != expected for index, expected in expected_character_cells.items()
    ):
        raise ContentGateError("Seris character master semantic shape does not match the 1.4.196 closure")
    ability_ids = tuple(character_row[19:25])
    if ability_ids != tuple(f"129999{index}" for index in range(1, 7)):
        raise ContentGateError(f"Seris ability references are not 1299991..1299996: {ability_ids!r}")
    if character_row[8] != spec.code_name or character_row[14] != spec.code_name:
        raise ContentGateError("Seris action/switched action references must both be seris_dragon_king")

    status_rows = evidence.ordered(CHARACTER_STATUS_MASTER_LOGICAL)
    bind_common(CHARACTER_STATUS_MASTER_LOGICAL)
    status = _decode_nested_text_rows(
        status_rows,
        logical=CHARACTER_STATUS_MASTER_LOGICAL,
        outer_key="129999",
        required_inner=("10", "1", "80", "100"),
    )
    for inner_key, value in status.items():
        rows = core.read_csv_lines(value)
        if len(rows) != 1 or len(rows[0]) != 2 or any(not cell.lstrip("-").isdigit() for cell in rows[0]):
            raise ContentGateError(f"Seris status row is malformed: {inner_key}")

    text_rows = evidence.ordered(CHARACTER_TEXT_MASTER_LOGICAL)
    bind_common(CHARACTER_TEXT_MASTER_LOGICAL)
    text = _decode_flat_text(
        text_rows.get("129999", b""), f"{CHARACTER_TEXT_MASTER_LOGICAL}:129999"
    )
    text_csv = core.read_csv_lines(text)
    if len(text_csv) != 1 or len(text_csv[0]) != 12 or not text_csv[0][0]:
        raise ContentGateError("Seris character text row is empty or malformed")

    ability_rows = evidence.ordered(ABILITY_MASTER_LOGICAL)
    bind_common(ABILITY_MASTER_LOGICAL)
    flat_tables: dict[str, dict[str, str]] = {
        ABILITY_MASTER_LOGICAL: {
            ability_id: _decode_flat_text(
                ability_rows[ability_id], f"{ABILITY_MASTER_LOGICAL}:{ability_id}"
            )
            for ability_id in ability_ids
            if ability_id in ability_rows
        }
    }
    if set(flat_tables[ABILITY_MASTER_LOGICAL]) != set(ability_ids):
        missing = sorted(set(ability_ids) - set(flat_tables[ABILITY_MASTER_LOGICAL]))
        raise ContentGateError(f"master ability reference missing: {missing[0]}")
    expected_ability_row_counts = (2, 1, 5, 1, 2, 1)
    expected_main_flags = ("true", "true", "false", "true", "true", "false")
    ability_required_columns = (0, 1, 2, 3, 5, 6, 13, 20, 27, 39, 46, 47, 85, 97, 108, 109, 123)
    for ability_id, expected_count, expected_main in zip(
        ability_ids, expected_ability_row_counts, expected_main_flags
    ):
        ability_csv = core.read_csv_lines(flat_tables[ABILITY_MASTER_LOGICAL][ability_id])
        actual_count = len(ability_csv)
        if actual_count != expected_count:
            raise ContentGateError(
                f"Seris ability row count mismatch for {ability_id}: "
                f"expected={expected_count} actual={actual_count}"
            )
        expected_name = f"seris_dragon_king_{ability_id[-1]}"
        if any(
            len(row) != 126
            or row[0] != expected_name
            or row[1] != expected_main
            or row[2] != "action_skill"
            or row[108] != "false"
            or any(not row[column] for column in ability_required_columns)
            for row in ability_csv
        ):
            raise ContentGateError(f"Seris ability row semantic shape mismatch: {ability_id}")

    leader_rows = evidence.ordered(LEADER_ABILITY_MASTER_LOGICAL)
    bind_common(LEADER_ABILITY_MASTER_LOGICAL)
    leader_raw = leader_rows.get("129999")
    if leader_raw is None:
        raise ContentGateError(f"master outer key missing for {LEADER_ABILITY_MASTER_LOGICAL}: 129999")
    leader_text = _decode_flat_text(leader_raw, f"{LEADER_ABILITY_MASTER_LOGICAL}:129999")
    flat_tables[LEADER_ABILITY_MASTER_LOGICAL] = {"129999": leader_text}
    leader_csv = core.read_csv_lines(leader_text)
    if len(leader_csv) != 9:
        raise ContentGateError(
            f"Seris leader row count mismatch: expected=9 actual={len(leader_csv)}"
        )
    leader_required_columns = (0, 1, 3, 4, 11, 18, 25, 37, 44, 83, 95, 106, 107)
    if any(
        len(row) != 124
        or row[0] != "seris_dragon_king_leader"
        or row[1] != "0"
        or row[106] != "false"
        or any(not row[column] for column in leader_required_columns)
        for row in leader_csv
    ):
        raise ContentGateError("Seris leader row semantic shape mismatch")
    leader_power_flip_keys = {
        row[118] for row in leader_csv
        if len(row) > 118 and row[118]
    }
    if leader_power_flip_keys != set(SERIS_POWER_FLIP_KEYS):
        raise ContentGateError(
            f"Seris leader power-flip references are incomplete: {sorted(leader_power_flip_keys)}"
        )

    action_rows = evidence.ordered(ACTION_SKILL_MASTER_LOGICAL)
    bind_common(ACTION_SKILL_MASTER_LOGICAL)
    action_inner = _decode_nested_text_rows(
        action_rows,
        logical=ACTION_SKILL_MASTER_LOGICAL,
        outer_key=spec.code_name,
        required_inner=("1", "2"),
    )
    switched_rows = evidence.ordered(SWITCHED_ACTION_SKILL_MASTER_LOGICAL)
    bind_common(SWITCHED_ACTION_SKILL_MASTER_LOGICAL)
    switched_inner = _decode_nested_text_rows(
        switched_rows,
        logical=SWITCHED_ACTION_SKILL_MASTER_LOGICAL,
        outer_key=spec.code_name,
        required_inner=("1", "2"),
    )
    nested_tables = {
        ACTION_SKILL_TABLE: {spec.code_name: action_inner},
        SWITCHED_ACTION_SKILL_TABLE: {spec.code_name: switched_inner},
    }
    action_csv = [core.read_csv_lines(action_inner[key]) for key in ("1", "2")]
    if any(
        len(rows) != 1 or len(rows[0]) != 24
        or any(not rows[0][column] for column in range(8))
        for rows in action_csv
    ):
        raise ContentGateError("Seris action skill row semantic shape mismatch")
    switched_csv = [core.read_csv_lines(switched_inner[key]) for key in ("1", "2")]
    if any(
        len(rows) != 1 or len(rows[0]) != 17
        or not rows[0][0] or not rows[0][1] or not rows[0][9]
        for rows in switched_csv
    ):
        raise ContentGateError("Seris switched action row semantic shape mismatch")

    base_references = extract_master_asset_references(flat_tables, nested_tables)
    action_programs = tuple(
        reference.value for reference in base_references if reference.kind == "skill_program"
    )
    if set(action_programs) != set(SERIS_ACTION_PROGRAMS) or len(action_programs) != 4:
        raise ContentGateError(f"Seris action/switched program closure mismatch: {action_programs!r}")

    power_flip_rows = evidence.ordered(POWER_FLIP_ACTION_MASTER_LOGICAL)
    bind_common(POWER_FLIP_ACTION_MASTER_LOGICAL)
    power_flip_programs: list[str] = []
    for outer_key in SERIS_POWER_FLIP_KEYS:
        raw = power_flip_rows.get(outer_key)
        if raw is None:
            raise ContentGateError(f"master outer key missing for {POWER_FLIP_ACTION_MASTER_LOGICAL}: {outer_key}")
        rows = core.read_csv_lines(_decode_flat_text(raw, f"{POWER_FLIP_ACTION_MASTER_LOGICAL}:{outer_key}"))
        if len(rows) != 1 or len(rows[0]) != 3 or any(not value for value in rows[0]):
            raise ContentGateError(f"Seris power-flip program row must contain exactly three programs: {outer_key}")
        power_flip_programs.extend(rows[0])
    if tuple(power_flip_programs) != SERIS_POWER_FLIP_PROGRAMS:
        raise ContentGateError(f"Seris power-flip program closure mismatch: {power_flip_programs!r}")

    condition_ids = {
        reference.value for reference in base_references if reference.kind == "unique_condition_id"
    }
    if not condition_ids:
        raise ContentGateError("Seris ability/leader closure has no unique condition IDs")
    unique_rows = evidence.ordered(UNIQUE_CONDITION_MASTER_LOGICAL)
    bind_common(UNIQUE_CONDITION_MASTER_LOGICAL)
    flat_tables[UNIQUE_CONDITION_MASTER_LOGICAL] = {}
    for condition_id in sorted(condition_ids):
        raw = unique_rows.get(condition_id)
        if raw is None:
            raise ContentGateError(f"Seris unique condition row is missing: {condition_id}")
        flat_tables[UNIQUE_CONDITION_MASTER_LOGICAL][condition_id] = _decode_flat_text(
            raw, f"{UNIQUE_CONDITION_MASTER_LOGICAL}:{condition_id}"
        )

    dsl_trees: dict[str, Any] = {}
    all_programs = (*action_programs, *power_flip_programs)
    if len(set(all_programs)) != 10:
        raise ContentGateError("Seris action/switched/PF closure must contain ten unique programs")
    for program in all_programs:
        dsl_logical = wf_dsl.dsl_logical(program)
        compressed = bind_common(dsl_logical)
        try:
            dsl_raw = zlib.decompress(compressed, -15)
            parsed = wf_dsl.parse_dsl(dsl_raw)
            tree = parsed["tree"]
        except Exception as exc:
            raise ContentGateError(f"Seris DSL is unreadable: {dsl_logical}: {exc}") from exc
        dsl_trees[dsl_logical] = tree

    for tree in dsl_trees.values():
        condition_ids.update(_dsl_unique_condition_ids(tree))
    if condition_ids != {"22", "23"}:
        raise ContentGateError(
            f"Seris unique condition closure must be exactly 22/23: {sorted(condition_ids)}"
        )
    for condition_id in sorted(condition_ids):
        if condition_id in flat_tables[UNIQUE_CONDITION_MASTER_LOGICAL]:
            continue
        raw = unique_rows.get(condition_id)
        if raw is None:
            raise ContentGateError(f"Seris unique condition row is missing: {condition_id}")
        flat_tables[UNIQUE_CONDITION_MASTER_LOGICAL][condition_id] = _decode_flat_text(
            raw, f"{UNIQUE_CONDITION_MASTER_LOGICAL}:{condition_id}"
        )

    references = extract_master_asset_references(flat_tables, nested_tables, dsl_trees)
    icons = {reference.value for reference in references if reference.kind == "unique_condition_icon"}
    if icons != {
        "battle/common/unique_condition/unique_seris_dragon_king",
        "battle/common/unique_condition/unique_seris_wet",
    }:
        raise ContentGateError(f"Seris unique condition icon closure mismatch: {sorted(icons)}")
    effects = {reference.value for reference in references if reference.kind == "skill_effect"}
    if effects != SERIS_EFFECT_BASES:
        raise ContentGateError(
            f"Seris DSL effect closure mismatch: missing={sorted(SERIS_EFFECT_BASES - effects)} "
            f"unexpected={sorted(effects - SERIS_EFFECT_BASES)}"
        )

    # Published closure tables which do carry 129999 in the current snapshot.
    # Tables known not to carry Seris (preview/upskill/stance/gacha sound) are
    # intentionally not treated as evidence.
    speech_rows = evidence.ordered(CHARACTER_SPEECH_MASTER_LOGICAL)
    bind_common(CHARACTER_SPEECH_MASTER_LOGICAL)
    speech_raw = speech_rows.get("129999")
    speech_csv = core.read_csv_lines(_decode_flat_text(
        speech_raw if speech_raw is not None else b"",
        f"{CHARACTER_SPEECH_MASTER_LOGICAL}:129999",
    ))
    if len(speech_csv) != 8 or any(len(row) != 5 for row in speech_csv):
        raise ContentGateError("Seris character speech closure must be exactly eight five-column rows")

    open_rows = evidence.ordered(MANA_BOARD2_OPEN_MASTER_LOGICAL)
    bind_common(MANA_BOARD2_OPEN_MASTER_LOGICAL)
    open_raw = open_rows.get("129999")
    open_csv = core.read_csv_lines(_decode_flat_text(
        open_raw if open_raw is not None else b"",
        f"{MANA_BOARD2_OPEN_MASTER_LOGICAL}:129999",
    ))
    if len(open_csv) != 1 or len(open_csv[0]) != 2 or any(not value for value in open_csv[0]):
        raise ContentGateError("Seris mana-board-2 open condition row is malformed")

    awake_rows = evidence.ordered(CHARACTER_AWAKE_STATUS_MASTER_LOGICAL)
    bind_common(CHARACTER_AWAKE_STATUS_MASTER_LOGICAL)
    awake_raw = awake_rows.get("129999")
    awake_csv = core.read_csv_lines(_decode_flat_text(
        awake_raw if awake_raw is not None else b"",
        f"{CHARACTER_AWAKE_STATUS_MASTER_LOGICAL}:129999",
    ))
    if awake_csv != [["0", "0"]]:
        raise ContentGateError("Seris awake-status closure must be the exact 0,0 row")

    for logical in (CHARACTER_IMAGE_MASTER_LOGICAL, FULL_SHOT_ATTRIBUTE_MASTER_LOGICAL):
        rows = evidence.ordered(logical)
        bind_common(logical)
        raw = rows.get("129999")
        if raw is None:
            raise ContentGateError(f"master outer key missing for {logical}: 129999")
        nested = _decode_nested_raw_rows(raw, f"{logical}#129999")
        if tuple(nested) != ("0", "1"):
            raise ContentGateError(f"Seris image master inner keys must be 0/1: {logical}")
        for inner_key, inner_raw in nested.items():
            values = core.read_csv_lines(_decode_flat_text(inner_raw, f"{logical}:129999:{inner_key}"))
            if len(values) != 1 or not values[0]:
                raise ContentGateError(f"Seris image master row is malformed: {logical}:{inner_key}")

    generated_board_nodes = {
        "1": ("13", "14", "16", "17", "18", "15", "7", "8", "10", "19", "20", "22", "23", "21", "11", "12", "9", "1", "2", "3", "4", "5", "6"),
        "2": tuple(str(index) for index in (*range(1, 8), *range(13, 19), *range(8, 13))),
    }
    mana_node_nodes = {
        "1": tuple(str(index) for index in range(1, 24)),
        "2": tuple(str(index) for index in range(1, 19)),
    }
    for logical, expected_nodes in (
        (GENERATED_MANA_BOARD_MASTER_LOGICAL, generated_board_nodes),
        (MANA_NODE_MASTER_LOGICAL, mana_node_nodes),
    ):
        rows = evidence.ordered(logical)
        bind_common(logical)
        raw = rows.get("129999")
        if raw is None:
            raise ContentGateError(f"master outer key missing for {logical}: 129999")
        boards = _decode_nested_raw_rows(raw, f"{logical}#129999")
        if tuple(boards) != ("1", "2"):
            raise ContentGateError(f"Seris mana master boards must be exactly 1/2: {logical}")
        for board_key, board_raw in boards.items():
            nodes = _decode_nested_raw_rows(board_raw, f"{logical}#129999#{board_key}")
            if tuple(nodes) != expected_nodes[board_key]:
                raise ContentGateError(f"Seris mana master node set mismatch: {logical}:{board_key}")
            for node_key, node_raw in nodes.items():
                values = core.read_csv_lines(_decode_flat_text(
                    node_raw, f"{logical}:129999:{board_key}:{node_key}"
                ))
                if len(values) != 1 or not values[0]:
                    raise ContentGateError(f"Seris mana master row is malformed: {logical}:{board_key}:{node_key}")

    trimmed_rows = evidence.ordered(TRIMMED_IMAGE_MASTER_LOGICAL)
    bind_common(TRIMMED_IMAGE_MASTER_LOGICAL)
    expected_trimmed = {
        f"character/seris_dragon_king/ui/{name}" for name in (
            "full_shot_1440_1920_0", "skill_cutin_0", "full_shot_1440_1920_1",
            "skill_cutin_1", "skill_cutin_matched_0", "skill_cutin_matched_1",
            "skill_cutin_dragon",
        )
    }
    actual_trimmed = {key for key in trimmed_rows if key.startswith("character/seris_dragon_king/")}
    if actual_trimmed != expected_trimmed:
        raise ContentGateError(
            f"Seris trimmed-image closure mismatch: missing={sorted(expected_trimmed - actual_trimmed)} "
            f"unexpected={sorted(actual_trimmed - expected_trimmed)}"
        )
    for outer_key in sorted(expected_trimmed):
        values = core.read_csv_lines(_decode_flat_text(
            trimmed_rows[outer_key], f"{TRIMMED_IMAGE_MASTER_LOGICAL}:{outer_key}"
        ))
        if len(values) != 1 or not values[0]:
            raise ContentGateError(f"Seris trimmed-image row is malformed: {outer_key}")

    for reference in references:
        if reference.kind == "unique_condition_id":
            continue
        for logical in required_asset_paths(reference):
            bind_common(logical)

    report = build_master_reference_report(
        references,
        package_asset_paths={entry.path.removeprefix("roots/common/") for entry in bound.values()},
        package_condition_ids=condition_ids,
        asset_exists=lambda _logical: False,
        condition_id_exists=lambda _condition_id: False,
    )
    if report.get("release_ready") is not True:
        missing = report.get("missing") or []
        raise ContentGateError(f"Seris master reference closure is incomplete: {missing[0] if missing else 'unknown'}")
    return tuple(bound[key] for key in sorted(bound))


def _bind_workspace_master_reference_closure(
    snapshot: StoreRoots,
    spec: CharacterReleaseSpec,
    evidence: _SnapshotEvidence,
) -> tuple[ManifestEntry, ...]:
    """Rebuild each workspace character's master -> DSL -> asset closure."""
    if (spec.character_id, spec.code_name) == (129999, "seris_dragon_king"):
        return _bind_seris_published_closure(snapshot, spec, evidence)

    identity = (spec.character_id, spec.code_name)
    expected_action_programs = WORKSPACE_ACTION_PROGRAMS.get(identity)
    expected_ability_programs = WORKSPACE_ABILITY_PROGRAMS.get(identity)
    expected_ability_counts = WORKSPACE_ABILITY_ROW_COUNTS.get(identity)
    expected_leader_count = WORKSPACE_LEADER_ROW_COUNTS.get(identity)
    expected_program_locations = WORKSPACE_ABILITY_PROGRAM_LOCATIONS.get(identity)
    if (
        expected_action_programs is None
        or expected_ability_programs is None
        or expected_ability_counts is None
        or expected_leader_count is None
        or expected_program_locations is None
    ):
        raise ContentGateError(
            f"workspace reference closure is unsupported: {spec.character_id}/{spec.code_name}"
        )

    bound: dict[tuple[str, str], ManifestEntry] = {}

    def bind_common(logical: str) -> bytes:
        entry, raw = evidence.read_root("common", logical)
        bound[(entry.source, entry.path)] = entry
        return raw

    character_row = _character_csv_row(snapshot, spec, _evidence=evidence)
    bind_common(CHARACTER_MASTER_LOGICAL)
    if len(character_row) != 37:
        raise ContentGateError(
            f"character {spec.character_id} master row must contain exactly 37 columns"
        )
    expected_ability_ids = tuple(
        f"{spec.character_id}{index}" for index in range(1, 7)
    )
    actual_ability_ids = tuple(character_row[19:25])
    if actual_ability_ids != expected_ability_ids:
        raise ContentGateError(
            f"character {spec.character_id} ability references mismatch: "
            f"expected={expected_ability_ids!r} actual={actual_ability_ids!r}"
        )
    if character_row[8] != spec.code_name:
        raise ContentGateError(
            f"character {spec.character_id} action reference mismatch: "
            f"expected {spec.code_name}, actual {character_row[8]!r}"
        )

    ability_rows = evidence.ordered(ABILITY_MASTER_LOGICAL)
    bind_common(ABILITY_MASTER_LOGICAL)
    flat_tables: dict[str, dict[str, str]] = {
        ABILITY_MASTER_LOGICAL: {},
        LEADER_ABILITY_MASTER_LOGICAL: {},
    }
    decoded_ability_rows: dict[str, list[list[str]]] = {}
    for ability_id, expected_count in zip(expected_ability_ids, expected_ability_counts):
        raw = ability_rows.get(ability_id)
        if raw is None:
            raise ContentGateError(f"master ability reference missing: {ability_id}")
        text = _decode_flat_text(
            raw, f"{ABILITY_MASTER_LOGICAL}:{ability_id}"
        )
        decoded = core.read_csv_lines(text)
        if len(decoded) != expected_count or any(len(row) != 126 for row in decoded):
            raise ContentGateError(
                f"character {spec.character_id} ability row shape mismatch: "
                f"{ability_id}: expected {expected_count}x126"
            )
        decoded_ability_rows[ability_id] = decoded
        flat_tables[ABILITY_MASTER_LOGICAL][ability_id] = text

    leader_rows = evidence.ordered(LEADER_ABILITY_MASTER_LOGICAL)
    bind_common(LEADER_ABILITY_MASTER_LOGICAL)
    leader_key = str(spec.character_id)
    leader_raw = leader_rows.get(leader_key)
    if leader_raw is None:
        raise ContentGateError(
            f"master outer key missing for {LEADER_ABILITY_MASTER_LOGICAL}: {leader_key}"
        )
    leader_text = _decode_flat_text(
        leader_raw, f"{LEADER_ABILITY_MASTER_LOGICAL}:{leader_key}"
    )
    decoded_leader_rows = core.read_csv_lines(leader_text)
    if (
        len(decoded_leader_rows) != expected_leader_count
        or any(len(row) != 124 for row in decoded_leader_rows)
    ):
        raise ContentGateError(
            f"character {spec.character_id} leader row shape mismatch: "
            f"expected {expected_leader_count}x124"
        )
    if identity == (149999, "white_wolf_gerald"):
        actual_locations = tuple(
            (row_index, column)
            for row_index, row in enumerate(decoded_leader_rows)
            for column, value in enumerate(row)
            if value == GERALD_UNCLAIMED_POWER_FLIP_KEY
        )
        if actual_locations != (GERALD_LEADER_POWER_FLIP_LOCATION,):
            raise ContentGateError(
                f"Gerald leader power-flip location mismatch: "
                f"expected={(GERALD_LEADER_POWER_FLIP_LOCATION,)!r} "
                f"actual={actual_locations!r}"
            )
    flat_tables[LEADER_ABILITY_MASTER_LOGICAL][leader_key] = leader_text

    action_rows = evidence.ordered(ACTION_SKILL_MASTER_LOGICAL)
    bind_common(ACTION_SKILL_MASTER_LOGICAL)
    action_inner = _decode_nested_text_rows(
        action_rows,
        logical=ACTION_SKILL_MASTER_LOGICAL,
        outer_key=spec.code_name,
        required_inner=("1", "2"),
    )
    decoded_action_rows = {
        inner_key: core.read_csv_lines(action_inner[inner_key])
        for inner_key in ("1", "2")
    }
    if any(
        len(rows) != 1 or len(rows[0]) != 24
        for rows in decoded_action_rows.values()
    ):
        raise ContentGateError(
            f"character {spec.character_id} normal action rows must each be exactly 1x24"
        )
    positioned_action_programs = tuple(
        decoded_action_rows[inner_key][0][7] for inner_key in ("1", "2")
    )
    if positioned_action_programs != expected_action_programs:
        raise ContentGateError(
            f"character {spec.character_id} normal action program closure mismatch: "
            f"expected={expected_action_programs!r} actual={positioned_action_programs!r}"
        )
    nested_tables = {ACTION_SKILL_TABLE: {spec.code_name: action_inner}}
    base_references = list(extract_master_asset_references(flat_tables, nested_tables))
    actual_action_programs = tuple(
        reference.value
        for reference in base_references
        if reference.kind == "skill_program"
    )
    if actual_action_programs != expected_action_programs:
        raise ContentGateError(
            f"character {spec.character_id} normal action program closure mismatch: "
            f"expected={expected_action_programs!r} actual={actual_action_programs!r}"
        )

    discovered_program_cells: list[tuple[str, int, int, str]] = []
    for ability_id, rows in decoded_ability_rows.items():
        for row_index, row in enumerate(rows):
            for column, value in enumerate(row):
                if value.startswith("battle/action/") and "$" in value:
                    discovered_program_cells.append((ability_id, row_index, column, value))
    for row_index, row in enumerate(decoded_leader_rows):
        for column, value in enumerate(row):
            if value.startswith("battle/action/") and "$" in value:
                discovered_program_cells.append((leader_key, row_index, column, value))
    if tuple(discovered_program_cells) != expected_program_locations:
        raise ContentGateError(
            f"character {spec.character_id} ability action program location mismatch: "
            f"expected={expected_program_locations!r} "
            f"actual={tuple(discovered_program_cells)!r}"
        )
    for ability_id, row_index, column, value in discovered_program_cells:
        base_references.append(MasterAssetReference(
            "skill_program", value,
            f"{ABILITY_MASTER_LOGICAL}:{ability_id} "
            f"row {row_index + 1} column {column}",
        ))

    for program in bind_native_programs(
        identity, decoded_leader_rows, evidence, bind_common, ContentGateError
    ):
        base_references.append(MasterAssetReference(
            "skill_program", program, f"{POWER_FLIP_ACTION_MASTER_LOGICAL}:native dual-PF"
        ))

    program_references: dict[str, MasterAssetReference] = {}
    for reference in base_references:
        if reference.kind == "skill_program":
            program_references.setdefault(reference.value, reference)
    dsl_trees: dict[str, Any] = {}
    for program, reference in program_references.items():
        dsl_logical = _require_logical(wf_dsl.dsl_logical(program))
        compressed = bind_common(dsl_logical)
        try:
            dsl_trees[dsl_logical] = wf_dsl.parse_dsl(
                zlib.decompress(compressed, -15)
            )["tree"]
        except Exception as exc:
            raise ContentGateError(
                f"workspace referenced DSL is unreadable: {reference.source}: "
                f"{dsl_logical}: {exc}"
            ) from exc
        effect_references = extract_master_asset_references(
            {}, {}, {dsl_logical: dsl_trees[dsl_logical]}
        )
        actual_effects = frozenset(
            item.value for item in effect_references if item.kind == "skill_effect"
        )
        expected_effects = WORKSPACE_PROGRAM_EFFECTS.get(program)
        if expected_effects is None or actual_effects != expected_effects:
            raise ContentGateError(
                f"workspace DSL effect closure mismatch for {program}: "
                f"expected={sorted(expected_effects or ())!r} "
                f"actual={sorted(actual_effects)!r}"
            )

    condition_ids = {
        reference.value
        for reference in base_references
        if reference.kind == "unique_condition_id"
    }
    for tree in dsl_trees.values():
        condition_ids.update(_dsl_unique_condition_ids(tree))
    if condition_ids:
        unique_rows = evidence.ordered(UNIQUE_CONDITION_MASTER_LOGICAL)
        bind_common(UNIQUE_CONDITION_MASTER_LOGICAL)
        flat_tables[UNIQUE_CONDITION_MASTER_LOGICAL] = {}
        for condition_id in sorted(condition_ids):
            raw = unique_rows.get(condition_id)
            if raw is None:
                raise ContentGateError(
                    f"workspace unique condition reference is missing: {condition_id}"
                )
            flat_tables[UNIQUE_CONDITION_MASTER_LOGICAL][condition_id] = _decode_flat_text(
                raw, f"{UNIQUE_CONDITION_MASTER_LOGICAL}:{condition_id}"
            )

    references = list(extract_master_asset_references(
        flat_tables, nested_tables, dsl_trees
    ))
    known = {(reference.kind, reference.value) for reference in references}
    for reference in base_references:
        key = (reference.kind, reference.value)
        if key not in known:
            references.append(reference)
            known.add(key)
    for condition_id in sorted(condition_ids):
        key = ("unique_condition_id", condition_id)
        if key not in known:
            references.append(MasterAssetReference(
                "unique_condition_id", condition_id, "workspace DSL closure"
            ))
            known.add(key)

    resolved_assets: set[str] = set()
    for reference in references:
        if reference.kind == "unique_condition_id":
            continue
        for logical in required_asset_paths(reference):
            logical = _require_logical(logical)
            entry, _raw = evidence.resolve(logical)
            expected_root = expected_root_for_logical(logical)
            if entry.source != f"snapshot:{expected_root}":
                raise ContentGateError(
                    f"workspace referenced asset root mismatch: {logical}: "
                    f"expected {expected_root}, actual {entry.source}"
                )
            bound[(entry.source, entry.path)] = entry
            resolved_assets.add(logical)

    report = build_master_reference_report(
        references,
        package_asset_paths=resolved_assets,
        package_condition_ids=condition_ids,
        asset_exists=lambda _logical: False,
        condition_id_exists=lambda _condition_id: False,
    )
    if report.get("release_ready") is not True:
        missing = report.get("missing") or []
        raise ContentGateError(
            f"workspace master reference closure is incomplete: "
            f"{missing[0] if missing else 'unknown'}"
        )
    return tuple(bound[key] for key in sorted(bound))


def _bind_seris_phase4_snapshot(
    snapshot: StoreRoots,
    phase4_asset_logicals: Collection[str],
    evidence: _SnapshotEvidence,
) -> tuple[ManifestEntry, ...]:
    """Bind the exact four P-code literals to their eight concrete root members."""
    concrete = expand_seris_phase4_asset_literals(phase4_asset_logicals)
    bound: list[ManifestEntry] = []
    for logical in sorted(concrete):
        expected_root = expected_root_for_logical(logical)
        entry, _raw = evidence.resolve(logical)
        actual_root = entry.source.removeprefix("snapshot:")
        if actual_root != expected_root:
            raise ContentGateError(
                f"root ownership mismatch for {logical}: "
                f"expected {expected_root}, actual {actual_root}"
            )
        bound.append(entry)
    return tuple(bound)


def build_published_snapshot_evidence(
    spec: CharacterReleaseSpec,
    snapshot: StoreRoots,
    *,
    phase4_asset_logicals: Collection[str],
    _evidence: _SnapshotEvidence | None = None,
) -> CharacterEvidenceReport:
    """Produce equivalent byte-bound evidence without reading any workspace."""
    evidence = _evidence or _SnapshotEvidence(snapshot)
    required37 = _required_37_logicals(spec.code_name)
    if len(required37) != 37:
        raise ContentGateError(f"character {spec.character_id} requirement matrix is not 37 entries")
    bound: list[ManifestEntry] = []
    for logical in sorted(required37):
        expected_root = expected_root_for_logical(logical)
        entry, _raw = evidence.resolve(logical)
        actual_root = entry.source.removeprefix("snapshot:")
        if actual_root != expected_root:
            raise ContentGateError(
                f"root ownership mismatch for {logical}: expected {expected_root}, actual {actual_root}"
            )
        bound.append(entry)
    if (spec.character_id, spec.code_name) == (129999, "seris_dragon_king"):
        bound.extend(_bind_seris_phase4_snapshot(snapshot, phase4_asset_logicals, evidence))
    bound.extend(_bind_published_character_contract(snapshot, spec, evidence))
    evidence.audit()
    deduplicated = {
        (entry.source, entry.path): entry for entry in bound
    }
    unsigned = CharacterEvidenceReport(
        identity={"character_id": spec.character_id, "code_name": spec.code_name},
        evidence_mode="published-snapshot",
        required_present=37,
        required_total=37,
        three_layer_consistent=True,
        bound_files=tuple(deduplicated[key] for key in sorted(deduplicated)),
        missing=(),
        seal_sha256="",
    )
    return replace(unsigned, seal_sha256=sha256_canonical_report(unsigned))


def _manifest_claim_entries(manifest: Mapping[str, Any]) -> tuple[ManifestEntry, ...]:
    roots = manifest.get("roots")
    if not isinstance(roots, Mapping):
        raise ContentGateError("workspace manifest roots are unreadable")
    entries: list[ManifestEntry] = []
    seen: set[str] = set()
    for root_name in _ROOTS:
        claims = roots.get(root_name)
        if not isinstance(claims, list):
            raise ContentGateError(f"workspace manifest root {root_name} is unreadable")
        for claim in claims:
            if not isinstance(claim, Mapping):
                raise ContentGateError(f"workspace manifest {root_name} claim is unreadable")
            logical, size, digest = claim.get("logical_path"), claim.get("size"), claim.get("sha256")
            if (
                not isinstance(logical, str)
                or type(size) is not int or size < 0
                or not isinstance(digest, str)
                or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                raise ContentGateError(f"workspace manifest {root_name} claim is invalid")
            logical = _require_logical(logical)
            expected_root = expected_root_for_logical(logical)
            if root_name != expected_root:
                raise ContentGateError(
                    f"workspace client claim root mismatch: {logical}: "
                    f"expected {expected_root}, actual {root_name}"
                )
            folded = logical.casefold()
            if folded in seen:
                raise ContentGateError(f"workspace manifest repeats client claim: {root_name}:{logical}")
            seen.add(folded)
            # Character workspaces are cumulative: their historical master
            # hashes legitimately predate later character/master edits.  Keep
            # validating the claim's shape and global path uniqueness, but
            # bind master bytes from the current staged snapshot after their
            # semantic ownership checks below.
            if not logical.startswith("master/"):
                entries.append(ManifestEntry(f"roots/{root_name}/{logical}", size, digest, f"snapshot:{root_name}"))
    return tuple(entries)


def _workspace_nonempty_csv(raw: bytes, label: str, *, nested: bool = False) -> list[list[str]]:
    kind = "nested" if nested else "flat"
    try:
        text = zlib.decompress(raw).decode("utf-8")
        rows = core.read_csv_lines(text)
    except Exception as exc:
        raise ContentGateError(f"workspace {kind} row is unreadable: {label}: {exc}") from exc
    if not rows or not any(
        isinstance(cell, str) and bool(cell.strip())
        for row in rows if isinstance(row, list)
        for cell in row
    ):
        raise ContentGateError(f"workspace {kind} row has no nonempty CSV cell: {label}")
    return rows


def _workspace_nested_map(raw: bytes, label: str) -> core.OrderedMap:
    try:
        nested = core.read_orderedmap_raw_rows_from_bytes(raw, label)
    except Exception as exc:
        raise ContentGateError(f"workspace nested row is unreadable: {label}: {exc}") from exc
    if not nested.keys:
        raise ContentGateError(f"workspace nested row is empty: {label}")
    if len(set(nested.keys)) != len(nested.keys):
        raise ContentGateError(f"workspace nested row has duplicate keys: {label}")
    return nested


def _workspace_nested_leaf_closure(raw: bytes, label: str, *, depth: int = 0) -> None:
    """Require a raw-outer subtree to terminate in nonempty compressed CSV leaves."""
    if depth > 8:
        raise ContentGateError(f"workspace nested row exceeds depth limit: {label}")
    try:
        _workspace_nonempty_csv(raw, label, nested=True)
        return
    except ContentGateError as flat_error:
        try:
            nested = _workspace_nested_map(raw, label)
        except ContentGateError as nested_error:
            raise ContentGateError(
                f"workspace nested row is unreadable: {label}: "
                f"neither compressed CSV nor orderedmap ({flat_error}; {nested_error})"
            ) from nested_error
    for key, child in zip(nested.keys, nested.rows):
        _workspace_nested_leaf_closure(child, f"{label}:{key}", depth=depth + 1)


def _workspace_validate_claim_rows(
    *,
    logical: str,
    codec_id: str,
    rows: Mapping[str, bytes],
    outer_keys: tuple[str, ...],
    inner_claims: Mapping[str, tuple[str, ...]],
) -> None:
    if codec_id == "flat":
        if inner_claims:
            raise ContentGateError(f"workspace flat table cannot declare inner keys: {logical}")
        for outer_key in outer_keys:
            _workspace_nonempty_csv(rows[outer_key], f"{logical}:{outer_key}")
        return
    if codec_id == "raw_outer":
        for outer_key in outer_keys:
            nested = _workspace_nested_map(rows[outer_key], f"{logical}:{outer_key}")
            declared = inner_claims.get(outer_key)
            if declared is not None and tuple(nested.keys) != declared:
                raise ContentGateError(
                    f"workspace nested inner keys mismatch: {logical}:{outer_key}: "
                    f"expected={list(declared)!r} actual={nested.keys!r}"
                )
            for inner_key, child in zip(nested.keys, nested.rows):
                _workspace_nested_leaf_closure(
                    child, f"{logical}:{outer_key}:{inner_key}", depth=1
                )
        return
    if codec_id in {"action_nested", "switched_nested"}:
        for outer_key in outer_keys:
            nested = _workspace_nested_map(rows[outer_key], f"{logical}:{outer_key}")
            declared = inner_claims.get(outer_key)
            if declared is None:
                raise ContentGateError(
                    f"workspace action table has no inner ownership claim: {logical}:{outer_key}"
                )
            if tuple(nested.keys) != declared:
                raise ContentGateError(
                    f"workspace action inner keys mismatch: {logical}:{outer_key}: "
                    f"expected={list(declared)!r} actual={nested.keys!r}"
                )
            for inner_key, child in zip(nested.keys, nested.rows):
                _workspace_nonempty_csv(
                    child, f"{logical}:{outer_key}:{inner_key}", nested=True
                )
        return
    raise ContentGateError(f"workspace master table codec is unsupported: {logical}:{codec_id!r}")


def _bind_gerald_unclaimed_power_flip(
    evidence: _SnapshotEvidence,
    root_claims: Mapping[str, set[str]],
) -> tuple[ManifestEntry, ...]:
    logical = POWER_FLIP_ACTION_MASTER_LOGICAL
    if logical not in root_claims.get("common", set()):
        raise ContentGateError("Gerald power-flip master root claim is missing")
    bound: dict[tuple[str, str], ManifestEntry] = {}
    master_entry, _master_raw = evidence.read_root("common", logical)
    bound[(master_entry.source, master_entry.path)] = master_entry
    rows = evidence.ordered(logical)
    raw = rows.get(GERALD_UNCLAIMED_POWER_FLIP_KEY)
    if raw is None:
        raise ContentGateError(
            f"Gerald sanctioned power-flip row is missing: {GERALD_UNCLAIMED_POWER_FLIP_KEY}"
        )
    try:
        parsed = core.read_csv_lines(zlib.decompress(raw).decode("utf-8"))
    except Exception as exc:
        raise ContentGateError(f"Gerald power-flip row is unreadable: {exc}") from exc
    if len(parsed) != 1 or len(parsed[0]) != 3 or any(not value.strip() for value in parsed[0]):
        raise ContentGateError("Gerald power-flip row must contain exactly three programs")
    programs = tuple(parsed[0])
    if programs != GERALD_POWER_FLIP_PROGRAMS:
        raise ContentGateError(
            f"Gerald power-flip program closure mismatch: {programs!r}"
        )

    dsl_trees: dict[str, Any] = {}
    for program in programs:
        dsl_logical = _require_logical(wf_dsl.dsl_logical(program))
        if dsl_logical not in root_claims.get("common", set()):
            raise ContentGateError(
                f"Gerald power-flip DSL is not declared in common root: {dsl_logical}"
            )
        entry, compressed = evidence.resolve(dsl_logical)
        if entry.source != "snapshot:common":
            raise ContentGateError(f"Gerald power-flip DSL root mismatch: {dsl_logical}")
        bound[(entry.source, entry.path)] = entry
        try:
            parsed_dsl = wf_dsl.parse_dsl(zlib.decompress(compressed, -15))
            tree = parsed_dsl["tree"]
        except Exception as exc:
            raise ContentGateError(f"Gerald power-flip DSL is unreadable: {dsl_logical}: {exc}") from exc
        dsl_trees[dsl_logical] = tree
        actual_effects = frozenset(
            reference.value
            for reference in extract_master_asset_references(
                {}, {}, {dsl_logical: tree}
            )
            if reference.kind == "skill_effect"
        )
        expected_effects = WORKSPACE_PROGRAM_EFFECTS[program]
        if actual_effects != expected_effects:
            raise ContentGateError(
                f"Gerald power-flip DSL effect closure mismatch for {program}: "
                f"expected={sorted(expected_effects)!r} actual={sorted(actual_effects)!r}"
            )

    references = extract_master_asset_references({}, {}, dsl_trees)
    for reference in references:
        for referenced_logical in required_asset_paths(reference):
            referenced_logical = _require_logical(referenced_logical)
            expected_root = expected_root_for_logical(referenced_logical)
            if referenced_logical not in root_claims.get(expected_root, set()):
                raise ContentGateError(
                    f"Gerald power-flip referenced asset is not declared: "
                    f"{expected_root}:{referenced_logical}"
                )
            entry, referenced_raw = evidence.resolve(referenced_logical)
            if entry.source != f"snapshot:{expected_root}" or not referenced_raw:
                raise ContentGateError(
                    f"Gerald power-flip referenced asset is unreadable: {referenced_logical}"
                )
            bound[(entry.source, entry.path)] = entry
    return tuple(bound[key] for key in sorted(bound))


def _gerald_published_root_claims() -> dict[str, set[str]]:
    """Derive Gerald's sanctioned PF closure without consulting a manifest."""
    claims = {root_name: set() for root_name in _ROOTS}
    claims["common"].add(POWER_FLIP_ACTION_MASTER_LOGICAL)
    for program in GERALD_POWER_FLIP_PROGRAMS:
        claims["common"].add(_require_logical(wf_dsl.dsl_logical(program)))
        for effect in WORKSPACE_PROGRAM_EFFECTS[program]:
            reference = MasterAssetReference("skill_effect", effect, "published Gerald PF")
            for logical in required_asset_paths(reference):
                logical = _require_logical(logical)
                claims[expected_root_for_logical(logical)].add(logical)
    return claims


def _bind_published_character_contract(
    snapshot: StoreRoots,
    spec: CharacterReleaseSpec,
    evidence: _SnapshotEvidence,
) -> tuple[ManifestEntry, ...]:
    """Bind the sealed-workspace master contract from staged bytes alone."""
    if (spec.character_id, spec.code_name) == (129999, "seris_dragon_king"):
        return _bind_seris_published_closure(snapshot, spec, evidence)

    bound: dict[tuple[str, str], ManifestEntry] = {}
    for contract in _workspace_master_contracts(spec):
        entry, _raw = evidence.read_root("common", contract.logical_path)
        rows = evidence.ordered(contract.logical_path)
        for outer_key in contract.outer_keys:
            if outer_key not in rows:
                raise ContentGateError(
                    f"published character table contract missing outer key: "
                    f"common:{contract.logical_path}:{outer_key}"
                )
        inner_claims = dict(contract.inner_keys)
        _workspace_validate_claim_rows(
            logical=contract.logical_path,
            codec_id=contract.codec_id,
            rows=rows,
            outer_keys=contract.outer_keys,
            inner_claims=inner_claims,
        )
        bound[(entry.source, entry.path)] = entry

    reference_entries = _bind_workspace_master_reference_closure(
        snapshot, spec, evidence
    )
    for entry in reference_entries:
        bound[(entry.source, entry.path)] = entry

    if (spec.character_id, spec.code_name) == (149999, "white_wolf_gerald"):
        for entry in _bind_gerald_unclaimed_power_flip(
            evidence, _gerald_published_root_claims()
        ):
            bound[(entry.source, entry.path)] = entry
    return tuple(bound[key] for key in sorted(bound))


def _verify_workspace_table_claims(
    spec: CharacterReleaseSpec,
    manifest: Mapping[str, Any],
    snapshot: StoreRoots,
    server_files: Mapping[str, bytes],
    *,
    _evidence: _SnapshotEvidence | None = None,
) -> tuple[ManifestEntry, ...]:
    """Bind declared character/action/ability/skill outer and inner keys.

    A workspace's file list proves bytes exist; its table claims prove those
    bytes actually carry the character's master rows.  Both are necessary.
    """
    evidence = _evidence or _SnapshotEvidence(snapshot)
    tables = manifest.get("tables")
    if not isinstance(tables, list) or not tables:
        raise ContentGateError("workspace manifest has no master table claims")
    action_skill, ability_ids = _character_references(snapshot, spec, _evidence=evidence)
    required_claims = {
        ("common", CHARACTER_MASTER_LOGICAL, str(spec.character_id)),
        ("common", CHARACTER_STATUS_MASTER_LOGICAL, str(spec.character_id)),
        ("common", CHARACTER_TEXT_MASTER_LOGICAL, str(spec.character_id)),
        ("common", LEADER_ABILITY_MASTER_LOGICAL, str(spec.character_id)),
        ("common", ACTION_SKILL_MASTER_LOGICAL, action_skill),
        *(("common", ABILITY_MASTER_LOGICAL, ability_id) for ability_id in ability_ids),
    }
    declared_keys: set[tuple[str, str, str]] = set()
    declared_inner_keys: set[tuple[str, str, str, str]] = set()
    server_table_keys: set[tuple[str, str]] = set()
    server_table_logicals: set[str] = set()
    staged_master_entries: dict[tuple[str, str], ManifestEntry] = {}
    root_claims = {
        root: {
            item.get("logical_path") for item in entries
            if isinstance(item, Mapping) and isinstance(item.get("logical_path"), str)
        }
        for root, entries in manifest["roots"].items()
        if root in _ROOTS and isinstance(entries, list)
    }
    master_root_claims: set[tuple[str, str]] = set()
    for root_name in _ROOTS:
        for logical in root_claims.get(root_name, set()):
            if isinstance(logical, str) and logical.startswith("master/"):
                if root_name != "common":
                    raise ContentGateError(
                        f"workspace master table must be declared in common root: {root_name}:{logical}"
                    )
                master_root_claims.add((root_name, logical))
    declared_master_tables: set[tuple[str, str]] = set()
    declared_codecs: dict[tuple[str, str], str] = {}
    for claim in tables:
        if not isinstance(claim, Mapping):
            raise ContentGateError("workspace master table claim is unreadable")
        root_name = claim.get("root")
        logical = claim.get("logical_path")
        outer_keys_raw = claim.get("outer_keys")
        codec_id = claim.get("codec_id")
        if (
            not isinstance(outer_keys_raw, list)
            or not outer_keys_raw
            or any(not isinstance(key, str) or not key for key in outer_keys_raw)
        ):
            raise ContentGateError("workspace master table claim is invalid")
        outer_keys = tuple(outer_keys_raw)
        if len(set(outer_keys)) != len(outer_keys):
            raise ContentGateError("workspace master table outer claims are invalid")
        if root_name == "server":
            if not isinstance(logical, str) or codec_id != "json_object":
                raise ContentGateError("workspace server table claim is invalid")
            logical = _require_logical(logical)
            if logical in server_table_logicals:
                raise ContentGateError(f"workspace server table claim repeats: {logical}")
            server_table_logicals.add(logical)
            raw = server_files.get(logical)
            if raw is None:
                raise ContentGateError(f"workspace server table is not declared in manifest roots: {logical}")
            try:
                parsed = _strict_json_load(raw.decode("utf-8"), f"workspace server table {logical}")
            except UnicodeDecodeError as exc:
                raise ContentGateError(f"workspace server table is unreadable: {logical}: {exc}") from exc
            if not isinstance(parsed, Mapping):
                raise ContentGateError(f"workspace server table must be an object: {logical}")
            for key in outer_keys:
                if str(key) not in parsed:
                    raise ContentGateError(f"workspace server outer key missing: {logical}:{key}")
                server_table_keys.add((logical, str(key)))
            continue
        if root_name not in _ROOTS or not isinstance(logical, str):
            raise ContentGateError("workspace master table claim is invalid")
        logical = _require_logical(logical)
        if logical.startswith("master/") and root_name != "common":
            raise ContentGateError(f"workspace master table claim must use common root: {root_name}:{logical}")
        if logical not in root_claims.get(root_name, set()):
            raise ContentGateError(f"workspace master table is not declared in manifest roots: {root_name}:{logical}")
        entry, raw = evidence.read_root(root_name, logical)
        if logical.startswith("master/"):
            if (root_name, logical) in declared_master_tables:
                raise ContentGateError(f"workspace master table claim repeats: {root_name}:{logical}")
            staged_master_entries[(root_name, logical)] = entry
            declared_master_tables.add((root_name, logical))
            declared_codecs[(root_name, logical)] = str(codec_id)
        try:
            if logical.startswith("master/"):
                rows = evidence.ordered(logical)
            else:
                outer = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
                rows = dict(zip(outer.keys, outer.rows))
        except Exception as exc:
            raise ContentGateError(f"workspace master table is unreadable: {logical}: {exc}") from exc
        for key in outer_keys:
            if key not in rows:
                raise ContentGateError(f"master outer key missing: {logical}:{key}")
            declared_keys.add((root_name, logical, key))
        inner_claims_raw = claim.get("inner_keys", [])
        if not isinstance(inner_claims_raw, list):
            raise ContentGateError(f"workspace master inner claims are unreadable: {logical}")
        inner_claims: dict[str, tuple[str, ...]] = {}
        for inner_claim in inner_claims_raw:
            if isinstance(inner_claim, Mapping):
                outer_key, keys = inner_claim.get("outer_key"), inner_claim.get("keys")
            elif isinstance(inner_claim, (list, tuple)) and len(inner_claim) == 2:
                outer_key, keys = inner_claim
            else:
                raise ContentGateError(f"workspace master inner claim is unreadable: {logical}")
            if (
                not isinstance(outer_key, str)
                or not outer_key
                or outer_key not in rows
                or outer_key not in outer_keys
                or not isinstance(keys, list)
                or not keys
                or any(not isinstance(key, str) or not key for key in keys)
            ):
                raise ContentGateError(f"workspace master inner claim is invalid: {logical}")
            normalized_keys = tuple(keys)
            if (
                len(set(normalized_keys)) != len(normalized_keys)
                or outer_key in inner_claims
            ):
                raise ContentGateError(f"workspace master inner claim is invalid: {logical}")
            inner_claims[outer_key] = normalized_keys
            for key in normalized_keys:
                declared_inner_keys.add((root_name, logical, outer_key, key))
        _workspace_validate_claim_rows(
            logical=logical,
            codec_id=str(codec_id),
            rows=rows,
            outer_keys=outer_keys,
            inner_claims=inner_claims,
        )

    missing_table_claims = sorted(master_root_claims - declared_master_tables)
    if spec.character_id == 149999 and spec.code_name == "white_wolf_gerald":
        gerald_pf_claim = ("common", POWER_FLIP_ACTION_MASTER_LOGICAL)
        if gerald_pf_claim not in master_root_claims:
            raise ContentGateError("Gerald power-flip master root claim is missing")
        _bind_gerald_unclaimed_power_flip(evidence, root_claims)
        staged_master_entries[gerald_pf_claim] = evidence.read_root(*gerald_pf_claim)[0]
        if gerald_pf_claim in missing_table_claims:
            missing_table_claims.remove(gerald_pf_claim)
    if missing_table_claims:
        root_name, logical = missing_table_claims[0]
        raise ContentGateError(
            f"workspace master root claim has no semantic table claim: {root_name}:{logical}"
        )
    missing_claims = sorted(required_claims - declared_keys)
    if missing_claims:
        root_name, logical, key = missing_claims[0]
        raise ContentGateError(f"workspace semantic ownership claim missing: {root_name}:{logical}:{key}")
    required_inner = {("common", ACTION_SKILL_MASTER_LOGICAL, action_skill, key) for key in ("1", "2")}
    missing_inner = sorted(required_inner - declared_inner_keys)
    if missing_inner:
        root_name, logical, outer_key, key = missing_inner[0]
        raise ContentGateError(
            f"workspace semantic inner ownership claim missing: {root_name}:{logical}:{outer_key}:{key}"
        )

    for contract in _workspace_master_contracts(spec):
        table_key = ("common", contract.logical_path)
        if table_key not in declared_master_tables:
            raise ContentGateError(
                f"workspace character table contract missing: "
                f"common:{contract.logical_path}"
            )
        actual_codec = declared_codecs.get(table_key)
        if actual_codec != contract.codec_id:
            raise ContentGateError(
                f"workspace character table codec mismatch: {contract.logical_path}: "
                f"expected {contract.codec_id}, actual {actual_codec!r}"
            )
        for outer_key in contract.outer_keys:
            if ("common", contract.logical_path, outer_key) not in declared_keys:
                raise ContentGateError(
                    f"workspace character table contract missing outer key: "
                    f"common:{contract.logical_path}:{outer_key}"
                )
        for outer_key, inner_keys in contract.inner_keys:
            for inner_key in inner_keys:
                if (
                    "common", contract.logical_path, outer_key, inner_key
                ) not in declared_inner_keys:
                    raise ContentGateError(
                        f"workspace character table contract missing inner key: "
                        f"common:{contract.logical_path}:{outer_key}:{inner_key}"
                    )

    reference_entries = _bind_workspace_master_reference_closure(
        snapshot, spec, evidence
    )

    required_server = {
        "character.json", "cdndata/character.json", "cdndata/character_text.json", "mana_node.json",
    }
    for logical in sorted(required_server):
        if (logical, str(spec.character_id)) not in server_table_keys:
            raise ContentGateError(f"workspace server semantic ownership claim missing: {logical}:{spec.character_id}")
    unexpected_server_tables = server_table_logicals - required_server
    if unexpected_server_tables:
        raise ContentGateError(f"workspace server semantic table claim is unexpected: {sorted(unexpected_server_tables)[0]}")
    try:
        client_row = _character_csv_row(snapshot, spec, _evidence=evidence)
        character_rows = _strict_json_load(
            server_files["cdndata/character.json"].decode("utf-8"), "workspace server table cdndata/character.json"
        )[str(spec.character_id)]
        if not isinstance(character_rows, list) or not character_rows or not isinstance(character_rows[0], list):
            raise ValueError("character rows are missing")
        if not character_rows[0] or character_rows[0][0] != client_row[0]:
            raise ContentGateError(
                f"workspace server character code_name mismatch: expected {client_row[0]}, actual {character_rows[0][0] if character_rows[0] else None!r}"
            )
        if character_rows != [client_row]:
            raise ValueError("character row differs from current client master")
        code_name = client_row[0]
        character_payload = _strict_json_load(server_files["character.json"].decode("utf-8"), "workspace server table character.json")[str(spec.character_id)]
        if (
            not isinstance(character_payload, Mapping)
            or set(character_payload) != {"element", "name", "rarity", "skill_count"}
            or not isinstance(character_payload.get("name"), str)
            or not character_payload["name"]
            or type(character_payload.get("rarity")) is not int
            or type(character_payload.get("element")) is not int
            or type(character_payload.get("skill_count")) is not int
            or character_payload["rarity"] != int(client_row[2])
            or character_payload["element"] != int(client_row[3])
            or character_payload["skill_count"] != EXPECTED_SERVER_SKILL_COUNTS[spec.character_id]
        ):
            raise ValueError("character payload shape/rarity/element/skill_count is invalid")
        text_rows = _strict_json_load(server_files["cdndata/character_text.json"].decode("utf-8"), "workspace server table cdndata/character_text.json")[str(spec.character_id)]
        client_text_raw = evidence.ordered(CHARACTER_TEXT_MASTER_LOGICAL)[str(spec.character_id)]
        client_text_rows = core.read_csv_lines(_decode_flat_text(
            client_text_raw, f"{CHARACTER_TEXT_MASTER_LOGICAL}:{spec.character_id}"
        ))
        if text_rows != client_text_rows or not client_text_rows or not client_text_rows[0]:
            raise ValueError("character text differs from current client master")
        if client_text_rows[0][0] != character_payload["name"]:
            raise ValueError("character text name is invalid")
        mana = _strict_json_load(server_files["mana_node.json"].decode("utf-8"), "workspace server table mana_node.json")[str(spec.character_id)]
        _mana_entry, expected_mana = _expected_mana_node_from_snapshot(spec, snapshot, evidence)
        if mana != expected_mana:
            raise ValueError("mana node record differs from current client master")
    except (KeyError, TypeError, ValueError) as exc:
        raise ContentGateError(f"workspace server character row is unreadable: {exc}") from exc
    if code_name != spec.code_name:
        raise ContentGateError(f"workspace server character code_name mismatch: expected {spec.code_name}, actual {code_name!r}")
    combined_entries = {
        (entry.source, entry.path): entry
        for entry in (
            *(staged_master_entries[key] for key in sorted(staged_master_entries)),
            *reference_entries,
        )
    }
    return tuple(combined_entries[key] for key in sorted(combined_entries))


def _verify_workspace_server_claims(
    manifest: Mapping[str, Any],
    workspace: Any,
    *,
    _package_files: Mapping[str, bytes] | None = None,
) -> dict[str, bytes]:
    claims = manifest["roots"].get("server")
    if not isinstance(claims, list) or not claims:
        raise ContentGateError("workspace server claims are missing")
    declared: set[str] = set()
    files: dict[str, bytes] = {}
    for claim in claims:
        if not isinstance(claim, Mapping):
            raise ContentGateError("workspace server claim is unreadable")
        logical, size, digest = claim.get("logical_path"), claim.get("size"), claim.get("sha256")
        if (
            not isinstance(logical, str) or type(size) is not int or size < 0
            or not isinstance(digest, str) or len(digest) != 64
            or any(char not in "0123456789abcdef" for char in digest)
        ):
            raise ContentGateError("workspace server claim is invalid")
        logical = _require_logical(logical)
        if logical in declared:
            raise ContentGateError(f"workspace server claim repeats: {logical}")
        declared.add(logical)
        relative = f"roots/server/{logical}"
        if _package_files is None:
            raw = _stable_read_path(
                workspace.package_dir / "roots" / "server" / logical,
                f"workspace server claim {logical}",
            )
        else:
            raw = _package_files.get(relative)
            if raw is None:
                raise ContentGateError(f"workspace server claim unreadable: {logical}: absent from stable package capture")
        if len(raw) != size or hashlib.sha256(raw).hexdigest() != digest:
            raise ContentGateError(f"workspace server claim hash/size mismatch: {logical}")
        try:
            parsed = _strict_json_load(raw.decode("utf-8"), f"workspace server claim {logical}")
        except UnicodeDecodeError as exc:
            raise ContentGateError(f"workspace server claim unreadable: {logical}: {exc}") from exc
        if not isinstance(parsed, Mapping):
            raise ContentGateError(f"workspace server claim must be a JSON object: {logical}")
        files[logical] = raw
    required = {"character.json", "cdndata/character.json", "cdndata/character_text.json", "mana_node.json"}
    missing = required - declared
    if missing:
        raise ContentGateError(f"workspace server semantic claims missing: {sorted(missing)[0]}")
    unexpected = declared - required
    if unexpected:
        raise ContentGateError(f"workspace server semantic claim is unexpected: {sorted(unexpected)[0]}")
    return files


def _verify_workspace_required_asset_roots(spec: CharacterReleaseSpec, manifest: Mapping[str, Any]) -> None:
    required = _required_37_logicals(spec.code_name)
    locations: dict[str, str] = {}
    for root_name in _ROOTS:
        for claim in manifest["roots"][root_name]:
            logical = claim["logical_path"]
            if logical in required:
                if logical in locations:
                    raise ContentGateError(f"workspace required asset is declared more than once: {logical}")
                locations[logical] = root_name
    for logical in sorted(required):
        actual = locations.get(logical)
        expected = expected_root_for_logical(logical)
        if actual != expected:
            raise ContentGateError(f"workspace required asset root mismatch: {logical}: expected {expected}, actual {actual}")


def _stable_read_path(path: Path, label: str) -> bytes:
    """Capture one regular file while proving path/handle identity stayed fixed."""
    path = Path(path)
    try:
        before = path.lstat()
    except OSError as exc:
        raise ContentGateError(f"{label} is unreadable: {exc}") from exc
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if stat.S_ISLNK(before.st_mode) or bool(getattr(before, "st_file_attributes", 0) & reparse):
        raise ContentGateError(f"{label} is a forbidden reparse/symlink")
    if not stat.S_ISREG(before.st_mode):
        raise ContentGateError(f"{label} is not a regular file")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if (
                not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            ):
                raise ContentGateError(f"{label} changed before reading")
            chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            finished = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        after = path.lstat()
    except OSError as exc:
        raise ContentGateError(f"{label} is unreadable: {exc}") from exc
    raw = b"".join(chunks)
    signature = lambda item: (item.st_dev, item.st_ino, item.st_mode, item.st_size, item.st_mtime_ns)
    if signature(before) != signature(opened) or signature(before) != signature(finished) or signature(before) != signature(after):
        raise ContentGateError(f"{label} changed while reading")
    if len(raw) != finished.st_size:
        raise ContentGateError(f"{label} changed while reading")
    return raw


def _workspace_inventory(package_dir: Path) -> tuple[str, ...]:
    package_dir = Path(package_dir)
    try:
        root_meta = package_dir.lstat()
    except OSError as exc:
        raise ContentGateError(f"workspace package is unreadable: {exc}") from exc
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    if not stat.S_ISDIR(root_meta.st_mode) or stat.S_ISLNK(root_meta.st_mode) or bool(
        getattr(root_meta, "st_file_attributes", 0) & reparse
    ):
        raise ContentGateError("workspace package must be a non-reparse directory")
    result: list[str] = []
    for current, directory_names, file_names in os.walk(package_dir, followlinks=False):
        directory_names.sort()
        file_names.sort()
        current_path = Path(current)
        for name in tuple(directory_names):
            path = current_path / name
            try:
                metadata = path.lstat()
            except OSError as exc:
                raise ContentGateError(f"workspace package directory is unreadable: {path}: {exc}") from exc
            if stat.S_ISLNK(metadata.st_mode) or bool(getattr(metadata, "st_file_attributes", 0) & reparse):
                raise ContentGateError(f"workspace package directory is a forbidden reparse/symlink: {path}")
            if not stat.S_ISDIR(metadata.st_mode):
                raise ContentGateError(f"workspace package member changed type: {path}")
        for name in file_names:
            path = current_path / name
            try:
                relative = path.relative_to(package_dir).as_posix()
            except ValueError as exc:
                raise ContentGateError(f"workspace package path escaped its root: {path}") from exc
            result.append(relative)
    return tuple(sorted(result))


def _stable_workspace_package_scan(
    package_dir: Path,
    expected_manifest_raw: bytes,
) -> tuple[str, dict[str, bytes]]:
    """Recompute workspace input_digest from one stable package capture."""
    before = _workspace_inventory(package_dir)
    if "manifest.json" not in before:
        raise ContentGateError("workspace package manifest.json is missing")
    captured = {
        relative: _stable_read_path(Path(package_dir) / Path(relative), f"workspace package {relative}")
        for relative in before
    }
    after = _workspace_inventory(package_dir)
    if after != before:
        raise ContentGateError("workspace package inventory changed during inspection")
    # Inventory equality alone cannot detect an in-place replacement.  Reopen
    # every member after the complete first pass and compare the bytes used by
    # the decision, so a manifest/master/server swap cannot hide behind an
    # unchanged filename set.
    for relative in before:
        current = _stable_read_path(
            Path(package_dir) / Path(relative),
            f"workspace package recheck {relative}",
        )
        if current != captured[relative]:
            raise ContentGateError(
                f"workspace package member changed during stable package scan: {relative}"
            )
    final_inventory = _workspace_inventory(package_dir)
    if final_inventory != before:
        raise ContentGateError("workspace package inventory changed during stable package scan")
    if captured["manifest.json"] != expected_manifest_raw:
        raise ContentGateError("workspace manifest changed during stable package scan")
    try:
        manifest_text = expected_manifest_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContentGateError(f"workspace manifest is unreadable: {exc}") from exc
    manifest = _strict_json_load(manifest_text, "workspace manifest")
    if not isinstance(manifest, Mapping):
        raise ContentGateError("workspace manifest must be an object")
    normalized = json.loads(json.dumps(manifest, ensure_ascii=False, allow_nan=False))
    qa = normalized.get("qa")
    if isinstance(qa, dict) and "workspace_input_sha256" in qa:
        qa["workspace_input_sha256"] = ""
    semantic_manifest = _canonical(normalized)
    entries = []
    for relative in before:
        raw = captured[relative]
        semantic = semantic_manifest if relative == "manifest.json" else raw
        entries.append({
            "path": relative,
            "size": len(semantic),
            "sha256": hashlib.sha256(semantic).hexdigest(),
        })
    return hashlib.sha256(_canonical(entries)).hexdigest(), captured


def _validate_captured_workspace_manifest(
    manifest: Mapping[str, Any],
    package_files: Mapping[str, bytes],
) -> None:
    """Run the canonical production manifest validator on captured bytes only.

    ``validate_manifest`` intentionally validates real files.  Materializing
    the already stable capture into an isolated temporary directory preserves
    that single implementation of the schema/hash/reference contract without
    reopening the mutable workspace package.
    """
    with tempfile.TemporaryDirectory(prefix="wf-offline-manifest-") as temp_name:
        anchor = Path(temp_name)
        for relative, raw in package_files.items():
            if (
                not isinstance(relative, str)
                or not relative
                or relative.startswith("/")
                or "\\" in relative
                or any(part in ("", ".", "..") for part in relative.split("/"))
            ):
                raise ContentGateError(
                    f"workspace captured package path is unsafe: {relative!r}"
                )
            destination = anchor.joinpath(*relative.split("/"))
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        errors = validate_manifest(
            dict(manifest), anchor, require_referenced_assets=True
        )
    if errors:
        raise ContentGateError(
            "workspace canonical manifest validation failed: " + "; ".join(errors)
        )
    try:
        _parse_transaction_claims(dict(manifest))
    except PackPreflightError as exc:
        raise ContentGateError(
            f"workspace transaction claim schema is invalid: {exc}"
        ) from exc
    qa = manifest.get("qa")
    if (
        not isinstance(qa, Mapping)
        or qa.get("delivery_mode") != "production"
        or qa.get("release_ready") is not True
        or qa.get("required_assets_present") != 37
        or qa.get("required_assets_total") != 37
    ):
        raise ContentGateError(
            "workspace manifest QA must be a sealed 37/37 production release"
        )


def _workspace_identity_hint(source: Path) -> tuple[int, str]:
    """Read only the tiny workspace identity before touching its package tree."""
    try:
        raw = _stable_read_path(Path(source) / "workspace.json", "workspace.json")
        payload = _strict_json_load(raw.decode("utf-8"), "workspace.json")
        identity = (int(payload["character_id"]), str(payload["code_name"]))
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise ContentGateError(f"workspace identity is unreadable: {exc}") from exc
    return identity


def _require_workspace_identity(spec: CharacterReleaseSpec, identity: tuple[int, str]) -> None:
    if identity != (spec.character_id, spec.code_name):
        raise ContentGateError(
            f"identity mismatch: expected {spec.character_id}/{spec.code_name}, got {identity[0]}/{identity[1]}"
        )


def verify_character_workspace_report(
    spec: CharacterReleaseSpec,
    report: Mapping[str, Any],
    snapshot: StoreRoots,
    *,
    _evidence: _SnapshotEvidence | None = None,
) -> CharacterEvidenceReport:
    effective: Mapping[str, Any] = report
    manifest: Mapping[str, Any] | None = None
    package_files: Mapping[str, bytes] | None = None
    workspace_path = report.get("_workspace_path")
    try:
        report_identity = report["identity"]
        _require_workspace_identity(spec, (int(report_identity["character_id"]), str(report_identity["code_name"])))
    except (KeyError, TypeError, ValueError) as exc:
        raise ContentGateError(f"workspace identity is unreadable: {exc}") from exc
    if workspace_path is None:
        raise ContentGateError("workspace provenance path is required")
    try:
        _require_workspace_identity(spec, _workspace_identity_hint(Path(workspace_path)))
        workspace = load_workspace(Path(workspace_path))
        manifest_path = workspace.package_dir / "manifest.json"
        manifest_before = _stable_read_path(manifest_path, "workspace manifest")
        try:
            manifest_text = manifest_before.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContentGateError(f"workspace manifest is unreadable: {exc}") from exc
        parsed_manifest = _strict_json_load(manifest_text, "workspace manifest")
        if not isinstance(parsed_manifest, Mapping):
            raise ContentGateError("workspace manifest must be an object")
        scanned = inspect_workspace(workspace)
        manifest_after = _stable_read_path(manifest_path, "workspace manifest")
        if manifest_after != manifest_before:
            raise ContentGateError("workspace manifest changed during inspection")
        stable_digest, package_files = _stable_workspace_package_scan(
            workspace.package_dir, manifest_before
        )
        _validate_captured_workspace_manifest(parsed_manifest, package_files)
        if scanned.get("input_digest") != stable_digest:
            raise ContentGateError(
                "workspace package changed during inspection or reported input digest is unstable"
            )
        manifest = parsed_manifest
        effective = scanned
    except ContentGateError:
        raise
    except Exception as exc:
        raise ContentGateError(f"workspace manifest is unreadable: {exc}") from exc
    try:
        identity = effective["identity"]
        actual = (int(identity["character_id"]), str(identity["code_name"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ContentGateError(f"workspace identity is unreadable: {exc}") from exc
    _require_workspace_identity(spec, actual)
    requirement = effective.get("requirement_report")
    if (
        not effective.get("release_ready")
        or not isinstance(requirement, Mapping)
        or requirement.get("required_present") != 37
        or requirement.get("required_total") != 37
        or effective.get("manifest_errors")
    ):
        raise ContentGateError(f"character {spec.character_id} is not 37/37 release-ready")
    layers = effective.get("three_layer_claim_status")
    if not isinstance(layers, Mapping) or layers.get("consistent") is not True:
        raise ContentGateError(f"character {spec.character_id} three-layer claims are incomplete")
    if not isinstance(manifest, Mapping):
        raise ContentGateError("workspace manifest is unreadable")
    if set(manifest.get("roots", {})) != {"common", "medium", "android", "server"}:
        raise ContentGateError("workspace manifest roots must be exactly common/medium/android/server")
    canonical_manifest = canonical_manifest_bytes(dict(manifest))
    canonical_manifest_sha256 = hashlib.sha256(canonical_manifest).hexdigest()
    qa = manifest.get("qa")
    if not isinstance(qa, Mapping) or qa.get("workspace_input_sha256") != effective.get("input_digest"):
        raise ContentGateError("workspace manifest seal drift")
    snapshot_evidence = _evidence or _SnapshotEvidence(snapshot)
    entries = list(verify_manifest_entries(
        _manifest_claim_entries(manifest), snapshot, _evidence=snapshot_evidence
    ))
    entries.append(ManifestEntry("manifest.json", len(canonical_manifest), canonical_manifest_sha256, "workspace:canonical-manifest"))
    server_files = _verify_workspace_server_claims(
        manifest, workspace, _package_files=package_files
    )
    entries.extend(
        ManifestEntry(
            f"roots/server/{logical}", len(raw), hashlib.sha256(raw).hexdigest(), "workspace:server"
        )
        for logical, raw in sorted(server_files.items())
    )
    _verify_workspace_required_asset_roots(spec, manifest)
    semantic_masters = _verify_workspace_table_claims(
        spec, manifest, snapshot, server_files, _evidence=snapshot_evidence
    )
    entries.extend(semantic_masters)
    snapshot_evidence.audit()
    unsigned = CharacterEvidenceReport(
        identity={"character_id": spec.character_id, "code_name": spec.code_name},
        evidence_mode="sealed-workspace",
        required_present=37,
        required_total=37,
        three_layer_consistent=True,
        bound_files=tuple(entries),
        missing=(),
        seal_sha256="",
    )
    return replace(unsigned, seal_sha256=sha256_canonical_report(unsigned))


@dataclass(frozen=True, slots=True)
class _CurrentServerAssets:
    parsed: Mapping[str, Mapping[str, Any]]
    entries: tuple[ManifestEntry, ...]


def _load_current_server_assets(assets_dir: Path) -> _CurrentServerAssets:
    """Capture the four explicit current server tables once; never fall back."""
    base = Path(assets_dir)
    parsed: dict[str, Mapping[str, Any]] = {}
    entries: list[ManifestEntry] = []
    for logical in SERVER_CHARACTER_LOGICALS:
        raw = _stable_read_path(base / Path(logical), f"current server asset {logical}")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ContentGateError(f"current server asset {logical} is unreadable: {exc}") from exc
        payload = _strict_json_load(text, f"current server asset {logical}")
        if not isinstance(payload, Mapping):
            raise ContentGateError(f"current server asset {logical} must be a JSON object")
        parsed[logical] = payload
        entries.append(ManifestEntry(
            f"assets/{logical}", len(raw), hashlib.sha256(raw).hexdigest(), "assets:server"
        ))
    return _CurrentServerAssets(parsed, tuple(entries))


def _expected_mana_node_from_snapshot(
    spec: CharacterReleaseSpec,
    snapshot: StoreRoots,
    evidence: _SnapshotEvidence,
) -> tuple[ManifestEntry, dict[str, dict[str, dict[str, Any]]]]:
    """Translate the exact staged mana-node master row into server JSON shape."""
    entry, _raw = evidence.resolve(MANA_NODE_MASTER_LOGICAL)
    rows = evidence.ordered(MANA_NODE_MASTER_LOGICAL)
    character_raw = rows.get(str(spec.character_id))
    if character_raw is None:
        raise ContentGateError(f"mana node master row is missing for {spec.character_id}")
    try:
        boards = core.read_orderedmap_raw_rows_from_bytes(
            character_raw, f"{MANA_NODE_MASTER_LOGICAL}#{spec.character_id}"
        )
    except Exception as exc:
        raise ContentGateError(f"mana node master boards are unreadable for {spec.character_id}: {exc}") from exc
    if len(set(boards.keys)) != len(boards.keys) or tuple(boards.keys) != ("1", "2"):
        raise ContentGateError(f"mana node master boards must be exactly 1 and 2 for {spec.character_id}")

    expected_counts = {"1": 23, "2": 18}
    prefix = str(spec.character_id * 2)
    translated: dict[str, dict[str, dict[str, Any]]] = {}
    for board_key, board_raw in zip(boards.keys, boards.rows):
        try:
            nodes = core.read_orderedmap_raw_rows_from_bytes(
                board_raw, f"{MANA_NODE_MASTER_LOGICAL}#{spec.character_id}/{board_key}"
            )
        except Exception as exc:
            raise ContentGateError(
                f"mana node master board {board_key} is unreadable for {spec.character_id}: {exc}"
            ) from exc
        expected_inner_keys = tuple(str(value) for value in range(1, expected_counts[board_key] + 1))
        if len(set(nodes.keys)) != len(nodes.keys) or tuple(nodes.keys) != expected_inner_keys:
            raise ContentGateError(
                f"mana node master board {board_key} keys are invalid for {spec.character_id}"
            )
        server_nodes: dict[str, dict[str, Any]] = {}
        base = 200 if board_key == "1" else 400
        for inner_key, node_raw in zip(nodes.keys, nodes.rows):
            label = f"{MANA_NODE_MASTER_LOGICAL}#{spec.character_id}/{board_key}/{inner_key}"
            parsed = core.read_csv_lines(_decode_flat_text(node_raw, label))
            if len(parsed) != 1 or len(parsed[0]) != 7:
                raise ContentGateError(f"mana node master row is malformed: {label}")
            row = parsed[0]
            expected_id = f"{prefix}{base + int(inner_key)}"
            item_ids = row[2].split(",") if row[2] else []
            item_costs = row[3].split(",") if row[3] else []
            if (
                row[0] != expected_id
                or len(item_ids) != len(item_costs)
                or len(set(item_ids)) != len(item_ids)
                or any(not item_id.isdigit() for item_id in item_ids)
                or any(not value.isdigit() or int(value) <= 0 for value in item_costs)
                or not row[4].isdigit()
                or any(not isinstance(value, str) for value in (row[1], row[5], row[6]))
            ):
                raise ContentGateError(f"mana node master row is invalid: {label}")
            server_nodes[expected_id] = {
                "field1": row[1],
                "field5": row[5],
                "field6": row[6],
                "items": {item_id: int(cost) for item_id, cost in zip(item_ids, item_costs)},
                "manaCost": int(row[4]),
            }
        translated[board_key] = server_nodes
    return entry, translated


def _bind_current_server_character(
    spec: CharacterReleaseSpec,
    report: CharacterEvidenceReport,
    snapshot: StoreRoots,
    server: _CurrentServerAssets,
    *,
    _evidence: _SnapshotEvidence,
) -> CharacterEvidenceReport:
    """Cross-check server-facing rows against the exact staged client bytes."""
    key = str(spec.character_id)
    client_row = _character_csv_row(snapshot, spec, _evidence=_evidence)
    mana_master_entry, expected_mana = _expected_mana_node_from_snapshot(
        spec, snapshot, _evidence
    )
    try:
        cdn_character = server.parsed["cdndata/character.json"][key]
        if cdn_character != [client_row]:
            raise ValueError("cdndata character row differs from staged client character row")

        character = server.parsed["character.json"][key]
        if not isinstance(character, Mapping) or set(character) != {
            "element", "name", "rarity", "skill_count",
        }:
            raise ValueError("character record shape is invalid")
        if (
            not isinstance(character["name"], str) or not character["name"]
            or isinstance(character["rarity"], bool) or not isinstance(character["rarity"], int)
            or isinstance(character["element"], bool) or not isinstance(character["element"], int)
            or isinstance(character["skill_count"], bool) or not isinstance(character["skill_count"], int)
            or character["skill_count"] != EXPECTED_SERVER_SKILL_COUNTS[spec.character_id]
            or character["rarity"] != int(client_row[2])
            or character["element"] != int(client_row[3])
        ):
            raise ValueError("character name/rarity/element/skill_count is invalid")

        text_rows = _raw_ordered_rows(
            snapshot, CHARACTER_TEXT_MASTER_LOGICAL, _evidence=_evidence
        )
        text_raw = text_rows[key]
        client_text = core.read_csv_lines(
            _decode_flat_text(text_raw, f"{CHARACTER_TEXT_MASTER_LOGICAL}:{key}")
        )
        server_text = server.parsed["cdndata/character_text.json"][key]
        if server_text != client_text or len(client_text) != 1 or len(client_text[0]) < 4:
            raise ValueError("cdndata character text differs from staged client character text")
        if client_text[0][0] != character["name"]:
            raise ValueError("character display name differs across current server tables")

        mana = server.parsed["mana_node.json"][key]
        if mana != expected_mana:
            raise ValueError("mana node server row differs from staged client mana-node master")
    except (KeyError, TypeError, ValueError) as exc:
        raise ContentGateError(
            f"current server character evidence is invalid for {spec.character_id}/{spec.code_name}: {exc}"
        ) from exc

    _evidence.audit()
    combined = {
        (entry.source, entry.path): entry
        for entry in (*report.bound_files, mana_master_entry, *server.entries)
    }
    unsigned = replace(
        report,
        three_layer_consistent=True,
        bound_files=tuple(combined[index] for index in sorted(combined)),
        seal_sha256="",
    )
    return replace(unsigned, seal_sha256=sha256_canonical_report(unsigned))


def assert_player_has_no_rogue_weapons(players: Mapping[str, Any]) -> None:
    player = players.get("1000")
    if not isinstance(player, Mapping):
        raise ContentGateError("Player 1000 possession record is missing")
    equipment = player.get("equipment", ())
    if not isinstance(equipment, (list, tuple, set)):
        raise ContentGateError("Player 1000 equipment possession record is unreadable")
    try:
        owned = {int(value) for value in equipment}
    except (TypeError, ValueError) as exc:
        raise ContentGateError("Player 1000 equipment possession record is invalid") from exc
    forbidden = set(range(8000101, 8000116)) & owned
    if forbidden:
        raise ContentGateError(f"Player 1000 must not hold rogue weapons: {sorted(forbidden)}")


def verify_player_1000_snapshot(
    snapshot: StoreRoots,
    *,
    _evidence: _SnapshotEvidence | None = None,
) -> None:
    """Check Task 4's byte-level overlay stayed character-only and level-one."""
    evidence = _evidence or _SnapshotEvidence(snapshot)
    entry, raw = evidence.resolve(PLAYER_CHARACTER_LOGICAL)
    if entry.source != "snapshot:common":
        raise ContentGateError("Player 1000 character record must be in common root")
    try:
        outer = core.read_orderedmap_raw_rows_from_bytes(raw, PLAYER_CHARACTER_LOGICAL)
        positions = [index for index, key in enumerate(outer.keys) if key == "1000"]
        if len(positions) != 1:
            raise ValueError("player 1000 must occur exactly once")
        inner = core.read_orderedmap_raw_rows_from_bytes(outer.rows[positions[0]], f"{PLAYER_CHARACTER_LOGICAL}#1000")
    except Exception as exc:
        raise ContentGateError(f"Player 1000 character record is unreadable: {exc}") from exc
    if len(set(inner.keys)) != len(inner.keys):
        raise ContentGateError("Player 1000 character possession record has duplicate keys")
    values: dict[str, str] = {}
    for key, compressed in zip(inner.keys, inner.rows):
        try:
            values[key] = zlib.decompress(compressed).decode("utf-8")
        except (UnicodeDecodeError, zlib.error) as exc:
            raise ContentGateError(f"Player 1000 character possession value is unreadable: {key}") from exc
    expected = {"1": "2", "129999": "1", "139999": "1", "149999": "1"}
    if values != expected:
        raise ContentGateError(f"Player 1000 character possession mapping is not the exact release overlay: {values!r}")


def verify_player_1000_equipment_snapshot(
    snapshot: StoreRoots,
    *,
    _evidence: _SnapshotEvidence | None = None,
) -> None:
    """The CN schema has no equipment table; item possession is the evidence table."""
    evidence = _evidence or _SnapshotEvidence(snapshot)
    present_roots: list[str] = []
    equipment_relative = str(hashed_rel(PLAYER_EQUIPMENT_LOGICAL)).replace("\\", "/")
    for root_name in _ROOTS:
        path = Path(getattr(snapshot, root_name)) / hashed_rel(PLAYER_EQUIPMENT_LOGICAL)
        if evidence.root_inventory is not None:
            if set(evidence.root_inventory) != set(_ROOTS):
                raise ContentGateError("snapshot root inventory schema is invalid")
            if equipment_relative not in evidence.root_inventory[root_name]:
                continue
            if evidence.access_guard is not None:
                evidence.access_guard(root_name, PLAYER_EQUIPMENT_LOGICAL)
            present_roots.append(root_name)
            continue
        try:
            path.lstat()
            if evidence.access_guard is not None:
                evidence.access_guard(root_name, PLAYER_EQUIPMENT_LOGICAL)
            present_roots.append(root_name)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ContentGateError(f"cannot inspect player equipment schema: {exc}") from exc
    if present_roots:
        raise ContentGateError(f"unexpected Player equipment schema drift: {sorted(present_roots)}")
    entry, raw = evidence.resolve(PLAYER_ITEM_LOGICAL)
    if entry.source != "snapshot:common":
        raise ContentGateError("Player 1000 item possession record must be in common root")
    try:
        outer = core.read_orderedmap_raw_rows_from_bytes(raw, PLAYER_ITEM_LOGICAL)
        positions = [index for index, key in enumerate(outer.keys) if key == "1000"]
        if not positions:
            return
        if len(positions) != 1:
            raise ValueError("player 1000 must occur exactly once")
        inner = core.read_orderedmap_raw_rows_from_bytes(
            outer.rows[positions[0]], f"{PLAYER_ITEM_LOGICAL}#1000"
        )
    except Exception as exc:
        raise ContentGateError(f"Player 1000 item possession record is unreadable: {exc}") from exc
    forbidden = {str(value) for value in range(8000101, 8000116)} & set(inner.keys)
    if forbidden:
        raise ContentGateError(f"Player 1000 must not hold rogue weapons: {sorted(forbidden)}")


def _client_gate(client_report: Path | None) -> bool | None:
    if client_report is None:
        return None
    try:
        data = _strict_json_load(Path(client_report).read_text(encoding="utf-8"), "client report")
    except (OSError, UnicodeDecodeError, ContentGateError) as exc:
        raise ContentGateError(f"client report is unreadable: {exc}") from exc
    if not isinstance(data, Mapping):
        raise ContentGateError("client report must be an object")
    required = {
        "output_sha256", "certificate_sha256", "patch_order", "stage_reports", "full_resource_version",
        "aligned", "signature_schemes", "verified",
    }
    if set(data) != required:
        raise ContentGateError("client report fields must exactly match ApkBuildReport")
    def require_sha(value: Any, label: str) -> str:
        if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ContentGateError(f"client report {label} must be a lowercase SHA-256 string")
        return value

    def require_fields(stage: Mapping[str, Any], fields: Collection[str], label: str) -> None:
        missing = set(fields) - set(stage)
        if missing:
            raise ContentGateError(f"client report {label} stage is missing fields: {sorted(missing)}")

    def require_hash_map(value: Any, keys: tuple[str, ...], label: str) -> None:
        if not isinstance(value, Mapping) or set(value) != set(keys):
            raise ContentGateError(f"client report {label} hash keys are invalid")
        for key in keys:
            require_sha(value[key], f"{label}.{key}")

    def require_sequence(value: Any, expected: tuple[str, ...], label: str) -> None:
        if not isinstance(value, list) or tuple(value) != expected:
            raise ContentGateError(f"client report {label} is invalid")

    for field in ("output_sha256", "certificate_sha256"):
        require_sha(data[field], field)
    if data["patch_order"] != ["abyss-mode-equipment", "seris-phase4", "render-scale", "resource-version"]:
        raise ContentGateError("client report patch_order is invalid")
    if not isinstance(data["stage_reports"], list) or len(data["stage_reports"]) != 4 or any(not isinstance(item, Mapping) for item in data["stage_reports"]):
        raise ContentGateError("client report stage_reports must contain four mappings")
    stages = data["stage_reports"]
    for index, stage in enumerate(stages):
        require_fields(stage, ("input_sha256", "output_sha256"), f"stage {index + 1}")
        require_sha(stage["input_sha256"], f"stage {index + 1}.input_sha256")
        require_sha(stage["output_sha256"], f"stage {index + 1}.output_sha256")
        if stage["input_sha256"] == stage["output_sha256"]:
            raise ContentGateError(f"client report stage {index + 1} is a no-op")
        if index and stage["input_sha256"] != stages[index - 1]["output_sha256"]:
            raise ContentGateError(f"client report stage hash chain breaks before stage {index + 1}")

    abyss, seris, render, resource = stages
    require_fields(
        abyss,
        ("stage", "target_class", "before_method_sha256", "after_method_sha256", "match_count"),
        "abyss",
    )
    if (
        abyss["stage"] != "abyss-mode-equipment"
        or abyss["target_class"] != "pinball.common.data.character.BattleCharacterLogic"
        or type(abyss["match_count"]) is not int
        or abyss["match_count"] != 1
    ):
        raise ContentGateError("client report abyss stage semantics are invalid")
    require_sha(abyss["before_method_sha256"], "abyss.before_method_sha256")
    require_sha(abyss["after_method_sha256"], "abyss.after_method_sha256")
    if abyss["before_method_sha256"] == abyss["after_method_sha256"]:
        raise ContentGateError("client report abyss stage is a no-op")

    require_fields(
        seris, ("site_ids", "before_hashes", "after_hashes", "asset_logicals", "verified"), "Seris",
    )
    require_sequence(seris["site_ids"], SERIS_PHASE4_SITE_IDS, "Seris stage site IDs")
    require_sequence(seris["asset_logicals"], SERIS_PHASE4_ASSET_LOGICALS, "Seris stage asset logicals")
    require_hash_map(seris["before_hashes"], SERIS_PHASE4_SITE_IDS, "Seris.before_hashes")
    require_hash_map(seris["after_hashes"], SERIS_PHASE4_SITE_IDS, "Seris.after_hashes")
    if any(
        seris["before_hashes"][site] == seris["after_hashes"][site]
        for site in SERIS_PHASE4_SITE_IDS
    ):
        raise ContentGateError("client report Seris stage contains a no-op site")
    if seris["verified"] is not True:
        raise ContentGateError("client report Seris stage is not verified")

    require_fields(render, ("site_ids", "before_hashes", "after_hashes", "verified"), "render")
    require_sequence(render["site_ids"], RENDER_SCALE_SITE_IDS, "render stage site IDs")
    require_hash_map(render["before_hashes"], RENDER_SCALE_SITE_IDS, "render.before_hashes")
    require_hash_map(render["after_hashes"], RENDER_SCALE_SITE_IDS, "render.after_hashes")
    if any(
        render["before_hashes"][site] == render["after_hashes"][site]
        for site in RENDER_SCALE_SITE_IDS
    ):
        raise ContentGateError("client report render stage contains a no-op site")
    if render["verified"] is not True:
        raise ContentGateError("client report render stage is not verified")

    require_fields(
        resource, ("source_version", "output_version", "is_full_package", "verified"), "resource-version",
    )
    if (
        resource["source_version"] != "1.4.54"
        or resource["output_version"] != "1.4.196"
        or resource["is_full_package"] is not True
        or resource["verified"] is not True
    ):
        raise ContentGateError("client report resource-version stage semantics are invalid")
    if data["full_resource_version"] != "1.4.196":
        raise ContentGateError("client report full_resource_version is invalid")
    if data["aligned"] is not True:
        raise ContentGateError("client report aligned must be true")
    schemes = data["signature_schemes"]
    if (
        not isinstance(schemes, Mapping)
        or set(schemes) != {"v1", "v2", "v3"}
        or any(schemes[name] is not True for name in ("v1", "v2", "v3"))
    ):
        raise ContentGateError("client report signature_schemes must be v1/v2/v3 true")
    if type(data["verified"]) is not bool:
        raise ContentGateError("client report verified must be boolean")
    return data["verified"]


def verify_character_release(
    spec: CharacterReleaseSpec,
    snapshot: StoreRoots,
    *,
    workspace_source: Path | None,
    phase4_asset_logicals: Collection[str],
    _evidence: _SnapshotEvidence | None = None,
) -> CharacterEvidenceReport:
    """Verify one character from a supplied seal or the frozen snapshot."""
    evidence = _evidence or _SnapshotEvidence(snapshot)
    if workspace_source is None:
        return build_published_snapshot_evidence(
            spec, snapshot, phase4_asset_logicals=phase4_asset_logicals,
            _evidence=evidence,
        )
    identity = _workspace_identity_hint(workspace_source)
    if identity != (spec.character_id, spec.code_name):
        if spec.character_id == 129999 and identity == (139999, "stella_summer_goddess"):
            report = build_published_snapshot_evidence(
                spec, snapshot, phase4_asset_logicals=phase4_asset_logicals,
                _evidence=evidence,
            )
            reason = (
                "identity mismatch: expected 129999/seris_dragon_king, got 139999/stella_summer_goddess"
            )
            unsigned = replace(report, rejected_workspace_reason=reason, seal_sha256="")
            return replace(unsigned, seal_sha256=sha256_canonical_report(unsigned))
        _require_workspace_identity(spec, identity)
    # The only package scan happens inside verify_character_workspace_report,
    # bracketed by stable manifest captures.  Do not perform an earlier,
    # unguarded inspect/load pass here.
    report = {
        "identity": {"character_id": identity[0], "code_name": identity[1]},
        "_workspace_path": str(workspace_source),
    }
    verified = verify_character_workspace_report(
        spec, report, snapshot, _evidence=evidence
    )
    if spec.character_id != 129999:
        return verified
    phase4_entries = _bind_seris_phase4_snapshot(
        snapshot, phase4_asset_logicals, evidence
    )
    evidence.audit()
    combined = {
        (entry.source, entry.path): entry
        for entry in (*verified.bound_files, *phase4_entries)
    }
    unsigned = replace(
        verified,
        bound_files=tuple(combined[key] for key in sorted(combined)),
        seal_sha256="",
    )
    return replace(unsigned, seal_sha256=sha256_canonical_report(unsigned))


def validate_offline_content(
    staged_roots: StoreRoots,
    *,
    workspace_sources: Mapping[str, Path] | None,
    phase4_asset_logicals: Collection[str],
    assets_dir: Path,
    client_report: Path | None = None,
    snapshot_access_guard: Callable[[str, str], None] | None = None,
    snapshot_root_inventory: Mapping[str, Collection[str]] | None = None,
) -> OfflineContentReport:
    """Validate all offline-only release content without consulting live state."""
    if workspace_sources is None:
        sources: dict[str, Path] = {}
    else:
        if not isinstance(workspace_sources, Mapping):
            raise ContentGateError("workspace source keys must be exactly the release characters")
        expected_keys = {spec.code_name for spec in CHARACTERS}
        actual_keys = set(workspace_sources)
        if (
            any(not isinstance(key, str) for key in actual_keys)
            or actual_keys != expected_keys
        ):
            missing = sorted(expected_keys - {key for key in actual_keys if isinstance(key, str)})
            unexpected = sorted(
                repr(key) for key in actual_keys
                if not isinstance(key, str) or key not in expected_keys
            )
            raise ContentGateError(
                f"workspace source keys must be exactly {sorted(expected_keys)!r}: "
                f"missing={missing!r} unexpected={unexpected!r}"
            )
        sources = {}
        for code_name in sorted(expected_keys):
            try:
                sources[code_name] = Path(workspace_sources[code_name])
            except (TypeError, ValueError) as exc:
                raise ContentGateError(
                    f"workspace source path is invalid for {code_name}"
                ) from exc
    if (snapshot_access_guard is None) != (snapshot_root_inventory is None):
        raise ContentGateError(
            "snapshot access guard and immutable root inventory must be supplied together"
        )
    snapshot_evidence = _SnapshotEvidence(
        staged_roots,
        access_guard=snapshot_access_guard,
        root_inventory=snapshot_root_inventory,
    )
    rogue = (
        validate_rogue_data(staged_roots.common, assets_dir)
        if snapshot_access_guard is None
        else validate_rogue_data(
            staged_roots.common,
            assets_dir,
            access_hook=lambda logical: snapshot_access_guard("common", logical),
        )
    )
    if snapshot_access_guard is None:
        verify_player_1000_snapshot(staged_roots)
        verify_player_1000_equipment_snapshot(staged_roots)
    else:
        verify_player_1000_snapshot(staged_roots, _evidence=snapshot_evidence)
        verify_player_1000_equipment_snapshot(
            staged_roots,
            _evidence=snapshot_evidence,
        )
    current_server = _load_current_server_assets(assets_dir)
    evidence: list[CharacterEvidenceReport] = []
    for spec in CHARACTERS:
        character_report = verify_character_release(
            spec, staged_roots, workspace_source=sources.get(spec.code_name),
            phase4_asset_logicals=phase4_asset_logicals,
            _evidence=snapshot_evidence,
        )
        evidence.append(_bind_current_server_character(
            spec, character_report, staged_roots, current_server,
            _evidence=snapshot_evidence,
        ))
    client_ready = _client_gate(client_report)
    return OfflineContentReport(rogue, tuple(evidence), client_ready, bool(rogue.ready and all(item.three_layer_consistent for item in evidence) and client_ready is not False))
