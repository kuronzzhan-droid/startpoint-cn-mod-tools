"""Native code mappings for additional recurring dungeon families."""
from __future__ import annotations

import re

from wf_wiki_dungeon_groups import GROUPS, group_fields
from wf_wiki_dungeon_story_groups import story_series
from wf_wiki_dungeons_schema import cell


COLOR_LABELS = {"red": "火", "blue": "水", "yellow": "雷", "green": "风", "white": "光", "black": "暗"}
EMPRESSES = {"fire": "赤之女王", "water": "青之女王", "thunder": "金之女王",
             "wind": "碧之女王", "light": "皓之女王", "dark": "墨之女王"}
HANIWA_TYPES = dict(zip(("01", "02", "03", "04", "05", "06", "07", "11"), GROUPS["series-haniwa"][1]))
RAIDS = dict(zip((f"raid_event_{i:02d}" for i in range(1, 7)), GROUPS["series-raid-feast"][1]))
RAIDS["raid_constant"] = "常驻战阵"
TRIALS = {"red": "闪火试炼", "water": "云水试炼", "yellow": "奔雷试炼", "green": "旋风试炼", "white": "溢光试炼"}
# Explicit known activity families; training entries deliberately stay separate
# from the dragons/guardians that they borrow as their combat opponent.
ADVENT_CODES = {
    "series-special-training": ("kc_yokai_emaki_big_boss", "kc_summer_2023", "kc_summer_2021", "kc_hero_big_boss",
                                "kc_guardian_golem_light", "kc_discarded_dragon_water", "kc_anv1"),
    "series-halloween": ("advent_hw20", "advent_hw21", "advent_hw22", "advent_hw23", "advent_variant_hw_fire_20231031_20231113"),
    "series-christmas-battle": ("advent_xm20", "advent_xm21", "advent_xm22"),
    "series-collab-z": ("advent_Zcollab_event", "advent_Zcollab_event2"),
    "series-collab-r": ("advent_Rcollab_event", "advent_revival_Rcollab_event"),
    "series-collab-g": ("advent_Gcollab_event", "advent_Gcollab_constant"),
    "series-collab-u": ("advent_u_collabo_event", "advent_u_collabo_constant"),
    "series-eye-dragon": ("advent_eye_dragon_multibattle_202310", "advent_eye_dragon_202503_multibattle"),
}
ADVENT_GROUPS = {code: identifier for identifier, codes in ADVENT_CODES.items() for code in codes}


def extra_event_series(kind, row):
    code = cell(row, 0)
    if kind == "raid" and code in RAIDS:
        return group_fields("series-raid-feast", RAIDS[code])
    if kind == "score_attack" and code == "score_attack_event_01":
        return group_fields("series-score-attack", "无限演武")
    if kind == "carnival" and code.startswith("haniwa_carnival_"):
        # c19 is the native boss-battle type. Fire has both machine and skill
        # variants, so recommended element alone would combine different fights.
        match = re.fullmatch(r"haniwa_carnival_(\d\d)", cell(row, 19))
        if match and match[1] in HANIWA_TYPES:
            return group_fields("series-haniwa", HANIWA_TYPES[match[1]])
    if kind == "rush" and re.fullmatch(r"combat_diver_(?:0[1-7]|constant_[1-7])", code):
        return group_fields("series-combat-diver", "活动版本")
    if kind == "daily_week":
        if code == "week_everyday_all":
            return group_fields("series-kaleidoscope", "培育素材")
        match = re.fullmatch(r"week_(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)_(red|blue|yellow|green|white|black)(?:_campaign)?", code)
        if match:
            return group_fields("series-kaleidoscope", COLOR_LABELS[match[1]])
    if kind == "challenge_dungeon" and code == "treasure_cave_quest":
        return group_fields("series-kaleidoscope", "宝物域")
    if kind == "expert_single" and code == "expert_single_02" and cell(row, 11) == "expert_single_side_story":
        return group_fields("series-recollection", "追忆试炼")
    if kind == "ranking":
        match = re.fullmatch(r"time_attack_event_(red|water|yellow|green|white)_001(?:_1)?", code)
        if match:
            return group_fields("series-trials", TRIALS[match[1]])
    if kind == "solo_time_attack" and code == "solo_time_attack":
        return group_fields("series-trials", "极时试炼")
    if kind == "advent":
        match = re.fullmatch(r"advent_variant_empress_(fire|water|thunder|wind|light|dark)_\d{8}_\d{8}", code)
        if match:
            return group_fields("series-empresses", EMPRESSES[match[1]])
        if re.fullmatch(r"(?:boss_epuration_event_0[12]|advent_boss_epuration_(?:5|\d{8}_\d{8}))", code):
            return group_fields("series-annihilator", "活动版本")
        if code in ADVENT_GROUPS:
            identifier = ADVENT_GROUPS[code]
            return group_fields(identifier, GROUPS[identifier][1][0])
    return story_series(kind, code)


def extra_boss_series(path):
    match = re.fullmatch(r"quest/boss_battle/background/boss_battle_(.+?)(?:\.png)?", path)
    if not match:
        return {}
    code = match[1]
    empress = {"empress_01": "青之女王", "empress_02": "赤之女王", "empress_03": "碧之女王"}
    empress.update({"variant_empress_" + color: label for color, label in EMPRESSES.items()})
    if code in empress:
        return group_fields("series-empresses", empress[code])
    identifier = {"halloween": "series-halloween", "xmas": "series-christmas-battle",
                  "eye_dragon": "series-eye-dragon", "Pcollab_02": "series-ark-guardian"}.get(code)
    return group_fields(identifier, GROUPS[identifier][1][0]) if identifier else {}
