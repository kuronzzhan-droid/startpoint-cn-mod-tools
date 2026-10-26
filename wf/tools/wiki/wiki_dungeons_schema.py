"""Verified dungeon master column mappings, separate from the export workflow."""
from __future__ import annotations

import re
import wf_mod_tool as core

NODE_TABLE = "master/quest/boss_battle_stage_node.orderedmap"
BOSS_QUEST = "master/quest/boss_battle_quest.orderedmap"
RANK_TABLE = "master/quest/quest_rank.orderedmap"
# Event title/banner/entry/preview columns from the matching *EventValues classes.
EVENTS = {
    "advent": ("降临战", 2, 4, 5, (7,)),
    "carnival": ("土俑嘉年华", 1, 3, 4, (5,)),
    "challenge_dungeon": ("挑战迷宫", 1, 3, 4, (5,)),
    "daily_exp_mana": ("经验与玛纳", 1, 3, 4, (5,)),
    "daily_week": ("摇曳迷宫", 1, 3, 4, (5,)),
    "expert_single": ("单人挑战", 1, 3, 4, (5, 6)),
    "hard_multi": ("共同决战", 2, 4, 5, (7,)),
    "raid": ("讨伐活动", 1, 3, 4, (5, 10)),
    "ranking": ("竞速挑战", 2, 4, 5, (6, 8)),
    "rush": ("连战活动", 1, 3, 4, (5,)),
    "score_attack": ("无限演武", 1, 3, 4, (5, 6)),
    "solo_time_attack": ("极时试炼", 1, 3, 4, (6,)),
    "story": ("剧情活动", 2, 4, 5, (6,)),
    "tower_dungeon": ("幽玄域", 1, 3, 4, (5, 7)),
    "world_story": ("世界活动", 2, 4, 5, (6, 7, 8)),
}
# Quest name / recommended element / enemy level / explicit rank columns.
# Verified against generated *QuestValues.as. Blank battle blocks stay blank.
QUEST_COLUMNS = {
    "boss": (2, 72, 106, 107), "advent": (2, 78, 112, 113),
    "carnival": (4, 69, 95, 96), "challenge_dungeon": (2, 73, 107, 108),
    "daily_exp_mana": (2, None, None, None), "daily_week": (1, None, None, None),
    "expert_single": (4, 75, 109, 110), "hard_multi": (2, 73, 107, 108),
    "raid": (4, 70, 96, 97), "ranking": (2, 68, 89, 90),
    "rush": (4, 69, 95, 96), "score_attack": (4, 73, 99, 100),
    "solo_time_attack": (3, 72, 98, 99), "story": (2, 74, 108, 109),
    "tower_dungeon": (2, 70, 96, 97), "world_story": (2, 73, 107, 108),
    "world_story_boss": (2, 72, 106, 107),
}
ELEMENTS = {"0": "风", "1": "火", "2": "水", "3": "雷", "4": "暗", "5": "光", "6": "无"}
QUEST_CATEGORIES = {"boss": (2,), "daily_week": (6,), "advent": (7, 8), "story": (10,),
                    "ranking": (11,), "challenge_dungeon": (13,), "daily_exp_mana": (14,),
                    "world_story": (18,), "world_story_boss": (19,), "tower_dungeon": (20,),
                    "expert_single": (21,), "carnival": (22,), "raid": (23,), "rush": (24,),
                    "solo_time_attack": (25,), "hard_multi": (26,), "score_attack": (27,)}
MODES = {
    ("rush", "700099"): ("深渊连战", "随机连战模式。", None),
    ("rush", "700098"): ("幻想连战", "幻想连战的活动入口。", None),
    ("rush", "700100"): ("深渊连战EX", "30 层独立连战及无尽入口；Rank 130，通关普通深渊 30 层后解锁。", None),
    ("advent", "300098"): ("幻想连战·协力挑战", "幻想连战的协力挑战入口。", None),
}


def event_table(kind):
    return f"master/quest/event/{kind}_event.orderedmap"


def quest_table(kind):
    suffix = {"story": "story_event_single_quest", "ranking": "ranking_event_single_quest",
              "world_story_boss": "world_story_event_boss_battle_quest"}.get(kind, f"{kind}_event_quest")
    return BOSS_QUEST if kind == "boss" else f"master/quest/event/{suffix}.orderedmap"


def table_paths():
    return [NODE_TABLE, BOSS_QUEST, RANK_TABLE, quest_table("world_story_boss")] + [
        path for kind in EVENTS for path in (event_table(kind), quest_table(kind))]


def cell(row, index):
    return row[index] if index is not None and index < len(row) else ""


def clean_text(value):
    return re.sub(r"::[^:]+::", "", value or "").replace("(None)", "").strip()


def leaf_rows(node):
    if isinstance(node, str):
        yield from core.read_csv_lines(node)
    elif isinstance(node, dict):
        for child in node.values():
            yield from leaf_rows(child)


def image_paths(value):
    result = []
    for path in (value or "").split(","):
        # Animation backgrounds are flatomo containers, not standalone PNGs.
        if path.startswith("quest/") and "/animation_background/" not in path:
            logical = path if path.endswith(".png") else path + ".png"
            if re.fullmatch(r"quest/[a-zA-Z0-9_/-]+\.png", logical) and logical not in result:
                result.append(logical)
    return result


def quest_details(node, kind, ranks, lookup=None, audit=None):
    name_col, element_col, level_col, rank_col = QUEST_COLUMNS[kind]
    result, seen = [], set()
    for row in leaf_rows(node):
        name = clean_text(cell(row, name_col))
        if not name:
            continue
        if audit is not None:
            audit["total"] += 1
            remote = next((lookup.get(f"{category}_{cell(row, 0)}") for category in QUEST_CATEGORIES[kind]
                           if f"{category}_{cell(row, 0)}" in lookup), None)
            if remote is not None:
                audit["matched"] += 1
                audit["sameName" if clean_text(remote) == name else "differentName"] += 1
        rank = next(leaf_rows(ranks.get(cell(row, rank_col), "")), [])
        difficulty = clean_text(cell(rank, 1))
        level = cell(row, level_col)
        if not difficulty and level.isdigit():
            for candidate in ranks.values():
                candidate = next(leaf_rows(candidate), [])
                if cell(candidate, 2).isdigit() and cell(candidate, 3).isdigit() and int(candidate[2]) <= int(level) <= int(candidate[3]):
                    difficulty = clean_text(cell(candidate, 1))
                    break
        if not difficulty:
            match = re.search(r"地狱级|超级\+?|高级\+?|中级|初级|Lv\s*\d+", name)
            difficulty = match[0] if match else ""
        element = ELEMENTS.get(cell(row, element_col), "")
        # Follow the native hide-recommended-element flag instead of exposing a hidden placeholder.
        if element_col is not None and cell(row, element_col + 1) == "true":
            element = ""
        value = (name, difficulty, element)
        if value not in seen:
            result.append(dict(zip(("name", "difficulty", "element"), value)))
            seen.add(value)
    return result
