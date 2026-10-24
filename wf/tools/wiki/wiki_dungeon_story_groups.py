"""Exact narrative-family aliases and official commemoration source codes."""
from __future__ import annotations

import re

from wf_wiki_dungeon_groups import STORY_TITLES, group_fields


# Original event, rerun and permanent side-story codes verified in the masters.
# Do not strip arbitrary dates/numbers: summer_2023 is this particular rerun,
# while summer_2020 and summer_2021 are different stories.
STORY_CODES = (
    ("cyberpunk01", "cyberpunk01_re01", "cyberpunk01_side_story_event"),
    ("fake_princess_01", "fakeprincess01_re01", "fakeprincess01_side_story_event"),
    ("summer_2020", "summer_2020_re01", "summer_2020_side_story_event"),
    ("yokai_emaki_01", "yokai_emaki_01_re01", "yokai_emaki_01_side_story_event"),
    ("anv1", "anv1_re01", "anv1_side_story_event"),
    ("valen20_side_story_event",),
    ("desert_bonds_01", "desert_bonds_01_re01", "desert_bonds_01_side_story_event"),
    ("cyberpunk02_hero", "cyberpunk02_re01", "cyberpunk02_side_story_event"),
    ("summer_2021", "summer_2021_re01", "summer_2021_side_story_event"),
    ("crown_beasts", "crown_beasts_re01", "crown_beasts_2023_12", "crown_beasts_side_story_event"),
    ("anv2", "anv2_re01", "anv2_2024_02", "anv2_side_story_event"),
    ("vt22", "vt22_re01", "vt22_side_story_event"),
    ("2halfanv", "2halfanv_re01", "2halfanv_side_story_event"),
    ("summer_2022", "summer_2023", "summer_2022_side_story_event"),
    ("anv3", "anv3_re01", "anv3_side_story_event"),
    ("anv3half", "anv3half_re01", "anv3half_side_story_event"),
)
WORLD_STORIES = {code: title for title, codes in zip(STORY_TITLES, STORY_CODES) for code in codes}
HOLIDAYS = {
    "holiday_activity": "十一黄金周", "holiday_activity_2023_1": "新年",
    "holiday_activity_2023_2": "五一黄金周", "holiday_activity_2023_3": "十一黄金周",
    "holiday_activity_2024_02": "新年", "holiday_activity_2024_05": "五一黄金周",
    "holiday_activity_2024_10": "十一黄金周", "holiday_activity_2025_01": "新年",
    "holiday_activity_2025_05": "五一黄金周",
}


def story_series(kind, code):
    if kind == "world_story":
        if code in WORLD_STORIES:
            return group_fields("series-side-stories", WORLD_STORIES[code])
        if code in HOLIDAYS:
            return group_fields("series-holiday-lottery", HOLIDAYS[code])
    if kind != "story":
        return {}
    # valen_21's originalEventId points to valen_20; the permanent story uses
    # valen_21's banner. Their original IDs remain separate inside the variant.
    if code in ("valen_20", "valen_21"):
        return group_fields("series-side-stories", STORY_TITLES[5])
    if code in ("xmas19", "xmas1907"):
        return group_fields("series-christmas-story", "活动版本")
    if re.fullmatch(r"release\d+day_event_1", code):
        return group_fields("series-commemorative", "开服纪念")
    if re.fullmatch(r"anv(?:1|1half|2|3|4)_(?:release|countdown)_event", code):
        return group_fields("series-commemorative", "周年纪念")
    if code in ("valentine21_event", "newyear22_event"):
        return group_fields("series-commemorative", "节日纪念")
    if code == "reset_marathon_event_001":
        return group_fields("series-commemorative", "特别纪念")
    return {}
