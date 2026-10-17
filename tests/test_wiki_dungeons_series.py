"""Evidence-based series matching and prevention of borrowed mode artwork."""
from __future__ import annotations

import sys
import unittest
from unittest.mock import Mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_wiki_dungeons as exporter
import wf_wiki_dungeons_schema as schema
import wf_wiki_dungeons_series as series


class SeriesTests(unittest.TestCase):
    def test_activity_family_codes_cover_reruns_without_folding_collab_training(self):
        cases = (("advent", "advent_steam_robot_light_202306", "series-machina", "光"),
                 ("hard_multi", "hard_multi_advent_steam_robot_fire", "series-machina", "火"),
                 ("hard_multi", "hard_multi_steam_robot_another", "series-machina", "无属性"),
                 ("advent", "advent_discarded_dragon_fire2_2", "series-waste-dragons", "火"),
                 ("advent", "advent_spirit_beast_storm2", "series-spirit-beasts", "风"))
        for kind, code, identifier, label in cases:
            with self.subTest(code=code):
                self.assertEqual(series.event_series(kind, "1", [code]),
                                 {"seriesId": identifier, "variantLabel": label})
        for code in ("advent_spirit_beast_stormy", "other_steam_robot_fire",
                     "advent_steam_robot_storm", "advent_discarded_dragon_storm"):
            self.assertEqual(series.event_series("advent", "1", [code]), {})
        for code in ("hard_multi_spirit_beast_fire", "hard_multi_advent_discarded_dragon_water"):
            self.assertEqual(series.event_series("hard_multi", "1", [code]), {})
        self.assertEqual(series.event_series("advent", "1", ["kc_discarded_dragon_water"])["seriesId"],
                         "series-special-training")

    def test_boss_family_uses_enemy_artwork_and_never_recommended_party_element(self):
        for family, identifier in series.FAMILIES.items():
            for element in ("fire", "water", "thunder", "wind", "light", "dark"):
                row = [""] * 13
                row[0], row[1], row[12] = "降临讨伐", "无属性提示", f"quest/boss_battle/background/boss_battle_{family}_{element}"
                self.assertEqual(series.boss_series(row), {"seriesId": identifier, "variantLabel": series.ELEMENT_LABELS[element]})
        self.assertEqual(series.boss_series([""] * 12 + ["quest/boss_battle/background/mod_five_boss"]), {})

    def test_modes_keep_original_ids_and_do_not_invent_ex_from_endless_quest(self):
        class Source:
            def prefetch(self, paths):
                pass

            def table(self, path):
                if path == schema.event_table("rush"):
                    return {"700098": "mod_fifteen_stage_rush,幻想连战,,quest/event/banner/rush_event/mod_fifteen_stage_banner_001,quest/event/bossbattle_banner/rush_event/combat_diver_01_bossbattle_banner_001,quest/event/background/rush_event/combat_diver_01_background",
                            "700099": "mod_rogue_gauntlet,深渊连战,,quest/event/banner/rush_event/mod_rogue_gauntlet_banner_001,quest/event/bossbattle_banner/rush_event/mod_rogue_gauntlet_bossbattle_banner_001,quest/event/background/rush_event/combat_diver_01_background"}
                if path == schema.event_table("advent"):
                    return {"300098": "mod_fifteen_stage_multi,,幻想连战·协力挑战,,quest/event/banner/hard_multi/hard_multi_event_steam_robot_light,quest/event/bossbattle_banner/hard_multi/steam_robot_light,,quest/event/background/hard_multi/steam_robot_light"}
                if path == schema.quest_table("rush"):
                    return {"700099": {"99": "700099099,2,0,,深渊连战 无尽"}}
                return {}

        items = exporter.build_items(Source())
        self.assertEqual({item["id"] for item in items}, {"event-advent-300098", "event-rush-700098", "event-rush-700099"})
        self.assertEqual({item["variantLabel"] for item in items}, {"幻想连战", "普通深渊"})
        self.assertTrue(all(item["seriesId"] == "series-gauntlets" for item in items))
        media = [path for item in items for key in ("_banners", "_entries", "_previews") for path in item[key]]
        self.assertFalse(any("combat_diver" in path or "steam_robot" in path for path in media))
        self.assertEqual(items[0]["_banners"], items[1]["_banners"])
        self.assertIn(schema.event_table("rush"), items[0]["_sources"])
        self.assertIn("mod_rogue_gauntlet_bossbattle_banner", items[2]["_entries"][0])
        self.assertEqual(items[2]["quests"][0]["name"], "深渊连战 无尽")

    def test_optional_series_fields_must_be_valid_pair(self):
        series.validate_series({})
        series.validate_series({"seriesId": "series-gauntlets", "variantLabel": "普通深渊"})
        series.validate_series({"seriesId": "series-gauntlets", "variantLabel": "深渊连战EX"})
        for fields in ({"seriesId": "series-machina"}, {"variantLabel": "火"},
                       {"seriesId": "series-gauntlets", "variantLabel": "深渊 EX"},
                       {"seriesId": "series-spirit-beasts", "variantLabel": "无属性"}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                series.validate_series(fields)

    def test_ex_requires_its_own_real_master_row_and_keeps_its_own_quests(self):
        class Source:
            def prefetch(self, paths):
                pass

            def table(self, path):
                if path == schema.event_table("rush"):
                    return {"700099": "mod_rogue_gauntlet,深渊连战", "700100": "fixture_ex,深渊连战EX"}
                if path == schema.quest_table("rush"):
                    row = [""] * 103
                    row[0], row[4], row[95], row[96] = "700100001", "EX第一战", "80", "2"
                    return {"700099": {"99": "700099099,2,0,,普通无尽"},
                            "700100": {"1": ",".join(row), "99": "700100099,2,0,,EX无尽"}}
                if path == schema.RANK_TABLE:
                    return {"2": "middle,中级,80,89"}
                return {}

        normal, ex = exporter.build_items(Source())
        self.assertEqual(ex["id"], "event-rush-700100")
        self.assertEqual(ex["category"], "模式")
        self.assertEqual(ex["variantLabel"], "深渊连战EX")
        self.assertEqual([row["name"] for row in ex["quests"]], ["EX第一战", "EX无尽"])
        self.assertTrue(all(row["difficulty"] == "" for row in ex["quests"]))
        self.assertEqual([row["name"] for row in normal["quests"]], ["普通无尽"])

    def test_verified_mode_label_requires_both_actual_overlay_tables_and_keeps_private_audit(self):
        records = {logical: {"origin": "gray-snapshot", "patchVersion": "1.4.115", "archiveSha256": "a" * 64}
                   for logical in (schema.event_table("rush"), schema.quest_table("rush"))}
        source = Mock(records=records)
        source.source.return_value = {"label": "混合快照", "status": "mixed-snapshot", "checkedAt": "2026-09-30"}
        draft = exporter.base_item("event-rush-700100", "深渊连战EX", "模式", "", [], list(records), [], [], [])
        audit = {"total": 31, "matched": 0, "sameName": 0, "differentName": 0}
        draft["_questCheck"] = audit
        item = exporter.render_catalog(source, Mock(), [draft])["items"][0]
        self.assertEqual(item["source"]["label"], "灰服当前补丁已核对；游戏内开放状态未实测")
        self.assertNotIn("questLookup", item["source"])
        self.assertEqual(draft["_questCheck"], audit)
        self.assertFalse(series.verified_gauntlet_tables(source, "event-advent-300098"))
        del records[schema.quest_table("rush")]["archiveSha256"]
        self.assertFalse(series.verified_gauntlet_tables(source, "event-rush-700100"))


if __name__ == "__main__":
    unittest.main()
