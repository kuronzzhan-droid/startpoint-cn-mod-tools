"""Regression checks for exact native family grouping without erasing leaf IDs."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_dungeon_groups import GROUPS, group_fields, validate_series_fields
from wf_wiki_dungeon_story_groups import STORY_CODES, WORLD_STORIES
from wf_wiki_dungeons_series import boss_series, event_series
from wf_wiki_dungeons import build_items
from wf_wiki_dungeons_schema import event_table


class EventGroupTests(unittest.TestCase):
    def fields(self, kind, code, **columns):
        row = [""] * 24
        row[0] = code
        for column, value in columns.items():
            row[int(column.removeprefix("c"))] = value
        return event_series(kind, "1", row)

    def test_battle_families_group_explicit_sources_and_reject_near_matches(self):
        cases = (("raid", "raid_event_02", "series-raid-feast", "因龙之宴"),
                 ("raid", "raid_constant", "series-raid-feast", "常驻战阵"),
                 ("score_attack", "score_attack_event_01", "series-score-attack", "无限演武"),
                 ("rush", "combat_diver_constant_7", "series-combat-diver", "活动版本"),
                 ("advent", "advent_boss_epuration_20230515_20230531", "series-annihilator", "活动版本"),
                 ("advent", "advent_variant_empress_wind_20230929_20231012", "series-empresses", "碧之女王"))
        for kind, code, identifier, label in cases:
            with self.subTest(code=code):
                self.assertEqual(self.fields(kind, code), group_fields(identifier, label))
        for kind, code in (("rush", "combat_diver_08"), ("story", "raid_event_02"),
                           ("advent", "advent_boss_epuration_fake"), ("advent", "kc_discarded_dragon_fake")):
            self.assertEqual(self.fields(kind, code), {})

    def test_haniwa_uses_battle_type_to_keep_two_fire_modes_distinct(self):
        machine = self.fields("carnival", "haniwa_carnival_01", c19="haniwa_carnival_01")
        skill = self.fields("carnival", "haniwa_carnival_fire_constant", c19="haniwa_carnival_11")
        rerun = self.fields("carnival", "haniwa_carnival_fire_20230630_20230714", c19="haniwa_carnival_11")
        self.assertEqual(machine["variantLabel"], "闪火土机巨土俑")
        self.assertEqual(skill["variantLabel"], "闪火必杀巨土俑")
        self.assertEqual(skill, rerun)
        self.assertEqual(self.fields("carnival", "haniwa_carnival_fire_constant"), {})

    def test_queen_stage_art_maps_enemy_color_not_recommended_party(self):
        row = [""] * 13
        row[12] = "quest/boss_battle/background/boss_battle_empress_01"
        self.assertEqual(boss_series(row), group_fields("series-empresses", "青之女王"))
        row[12] = "quest/boss_battle/background/boss_battle_variant_empress_thunder.png"
        self.assertEqual(boss_series(row), group_fields("series-empresses", "金之女王"))

    def test_maze_and_time_trials_do_not_swallow_collapse_or_single_challenge(self):
        self.assertEqual(self.fields("daily_week", "week_sunday_red_campaign"), group_fields("series-kaleidoscope", "火"))
        self.assertEqual(self.fields("challenge_dungeon", "treasure_cave_quest"), group_fields("series-kaleidoscope", "宝物域"))
        self.assertEqual(self.fields("ranking", "time_attack_event_water_001_1"), group_fields("series-trials", "云水试炼"))
        self.assertEqual(self.fields("solo_time_attack", "solo_time_attack"), group_fields("series-trials", "极时试炼"))
        self.assertEqual(self.fields("expert_single", "expert_single_02", c11="expert_single_side_story"),
                         group_fields("series-recollection", "追忆试炼"))
        for kind, code in (("challenge_dungeon", "challenge_dungeon_01"), ("expert_single", "expert_single_01"),
                           ("expert_single", "expert_single_02"), ("tower_dungeon", "tower_dungeon_01")):
            self.assertEqual(self.fields(kind, code), {})

    def test_story_aliases_share_only_verified_canonical_story(self):
        for codes in STORY_CODES:
            expected = self.fields("world_story", codes[0])
            for code in codes:
                self.assertEqual(self.fields("world_story", code), expected)
        self.assertEqual(len(WORLD_STORIES), sum(map(len, STORY_CODES)))
        self.assertEqual(self.fields("world_story", "vt22_side_story_event")["variantLabel"], "胆怯PureYells！")
        self.assertNotEqual(self.fields("world_story", "summer_2020"), self.fields("world_story", "summer_2021"))
        self.assertEqual(self.fields("world_story", "summer_2023"), self.fields("world_story", "summer_2022"))
        self.assertEqual(self.fields("world_story", "summer_2024"), {})
        self.assertEqual(self.fields("advent", "summer_2022"), {})
        self.assertEqual(self.fields("story", "valen_21"), self.fields("world_story", "valen20_side_story_event"))

    def test_holiday_lottery_and_commemorative_battles_remain_distinct(self):
        self.assertEqual(self.fields("world_story", "holiday_activity_2024_02")["seriesId"], "series-holiday-lottery")
        self.assertEqual(self.fields("story", "newyear22_event")["seriesId"], "series-commemorative")
        self.assertEqual(self.fields("story", "release950day_event_1")["variantLabel"], "开服纪念")
        self.assertEqual(self.fields("story", "anv1half_countdown_event")["variantLabel"], "周年纪念")
        self.assertEqual(self.fields("story", "ny21_cat_fighter"), {})

    def test_christmas_story_is_not_the_christmas_raid(self):
        story = self.fields("story", "xmas1907")
        battle = self.fields("advent", "advent_xm20")
        self.assertNotEqual(story["seriesId"], battle["seriesId"])
        self.assertEqual(story, self.fields("story", "xmas19"))
        self.assertEqual(battle, self.fields("advent", "advent_xm22"))

    def test_public_vocabulary_requires_exact_title_and_closed_variants(self):
        for identifier, (_, variants) in GROUPS.items():
            for variant in variants:
                validate_series_fields(group_fields(identifier, variant))
        for fields in ({"seriesTitle": "试炼"}, {"seriesId": "series-trials", "variantLabel": "云水试炼"},
                       {"seriesId": "series-trials", "seriesTitle": "任意标题", "variantLabel": "云水试炼"},
                       {"seriesId": "series-trials", "seriesTitle": "试炼", "variantLabel": "不存在"}):
            with self.assertRaises(ValueError):
                validate_series_fields(fields)

    def test_grouping_preserves_rerun_ids_and_actual_mismatched_anniversary_title(self):
        class Source:
            def prefetch(self, paths):
                pass

            def table(self, logical):
                if logical == event_table("story"):
                    return {"100003": "valen_20,,激斗！情人节盛典攻防战！！", "100006": "valen_21,100003,激斗！情人节盛典攻防战！！",
                            "200028": "release950day_event_1,,开服880天纪念关卡"}
                return {}
        items = build_items(Source())
        self.assertEqual([item["id"] for item in items], ["event-story-100003", "event-story-100006", "event-story-200028"])
        self.assertEqual(items[0]["variantLabel"], items[1]["variantLabel"])
        self.assertEqual(items[2]["title"], "开服880天纪念关卡")


if __name__ == "__main__":
    unittest.main()
