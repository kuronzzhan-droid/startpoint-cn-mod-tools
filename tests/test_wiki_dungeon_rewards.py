"""Boundary and runtime-behaviour checks for the public reward projection."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wf_wiki_dungeon_rewards_mapping import boss_shop_links
from wf_wiki_dungeon_rewards import build_payload
from wf_wiki_dungeon_rewards_rules import QuestRewards, folder_rewards, rogue_round
from wf_wiki_dungeon_rewards_schema import PREFIX, read_payload, validate_payload
from wf_wiki_dungeon_rewards_shops import build_shops, project_product
from wf_wiki_dungeon_rewards_sources import Names
from wf_wiki_dungeon_rewards_special import fantasy_schedule, score_rewards
from wf_wiki_public import public_id


class Assets:
    def __init__(self, data=None):
        self.data = data or {}

    def get(self, name):
        return self.data.get(name, {})

    def merged(self, base, extra):
        return {**self.get(base), **self.get(extra)}

    def rogue(self):
        return {}


def fixture_names(assets=None):
    assets = assets or Assets()
    assets.data.setdefault("item_lookup.json", {"1": "素材", "14040": "星之记忆结晶", "40193": "令牌"})
    return Names(assets, {"equipment": [{"id": public_id("w", "123"), "name": "武器甲"}], "characters": []})


def fixture_payload():
    return {"schemaVersion": 1, "source": {"label": "灰服快照", "status": "gray-snapshot", "checkedAt": "2026-09-30T00:00:00Z"},
            "dungeons": {"event-rush-1": {"quests": [], "shopIds": ["shop-one"], "notes": []}},
            "shops": [{"id": "shop-one", "title": "兑换", "dungeonIds": ["event-rush-1"], "notes": [], "items": []}]}


class ContractTests(unittest.TestCase):
    def test_valid_reciprocal_contract(self):
        validate_payload(fixture_payload(), dungeon_ids={"event-rush-1"})

    def test_reject_private_extra_fields(self):
        data = fixture_payload()
        data["shops"][0]["rawId"] = "1"
        with self.assertRaises(ValueError):
            validate_payload(data)

    def test_reject_private_paths(self):
        data = fixture_payload()
        data["source"]["label"] = "C:/secret/data.json"
        with self.assertRaises(ValueError):
            validate_payload(data)

    def test_reject_one_sided_link(self):
        data = fixture_payload()
        data["shops"][0]["dungeonIds"] = []
        with self.assertRaises(ValueError):
            validate_payload(data)

    def test_reject_non_gray_source(self):
        data = fixture_payload()
        data["source"]["status"] = "local"
        with self.assertRaises(ValueError):
            validate_payload(data)

    def test_reject_unverified_weapon(self):
        data = fixture_payload()
        data["shops"][0]["items"] = [project_product({"rewards": [{"type": 4, "id": 123}]}, fixture_names())]
        with self.assertRaises(ValueError):
            validate_payload(data, equipment_ids=set())

    def test_read_never_executes_trailing_script(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.js"
            path.write_text(PREFIX + json.dumps(fixture_payload()) + ";alert(1);", encoding="utf-8")
            with self.assertRaises(ValueError):
                read_payload(path)

    def test_reject_duplicate_json_keys(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "data.js"
            path.write_text(PREFIX + '{"schemaVersion":1,"schemaVersion":1};', encoding="utf-8")
            with self.assertRaises(ValueError):
                read_payload(path)


class RewardRulesTests(unittest.TestCase):
    def setUp(self):
        self.assets = Assets({"clear_reward.json": {"1": {"type": 3, "count": 15}},
            "score_reward.json": {"7": [{"type": 1, "id": 9, "rarity": 0.01}]},
            "rare_score_reward.json": {"9": [{"type": 1, "id": 123, "count": 1}]}})
        self.names = fixture_names(self.assets)
        self.rules = QuestRewards(self.assets, self.names)

    def test_first_and_ss_separate(self):
        row = self.rules.regular("boss", "1", {"clearRewardId": 1, "sPlusRewardId": 1}, "Boss")
        self.assertEqual(row["firstClear"][0]["amountText"], "15")
        self.assertEqual(len(row["sPlus"]), 1)
        self.assertEqual(row["drops"], [])

    def test_recollection_ss_runtime_override(self):
        row = self.rules.regular("expert_single", "1", {"sPlusRewardId": 1}, "追忆")
        self.assertEqual(row["sPlus"][0]["name"], "星之记忆结晶")
        self.assertEqual(row["sPlus"][0]["amountText"], "3")

    def test_inclusive_rare_roll_matches_gray_runtime(self):
        row = self.rules.regular("boss", "1", {"scoreRewardGroupId": 7}, "Boss")
        self.assertIn("2%", row["drops"][0]["probabilityText"])

    def test_rare_probability_does_not_round_down_float_boundary(self):
        self.rules.score["7"][0]["rarity"] = 0.29
        row = self.rules.regular("boss", "1", {"scoreRewardGroupId": 7}, "Boss")
        self.assertIn("30%", row["drops"][0]["probabilityText"])

    def test_boss_profile_exact_rare_one_percent(self):
        self.rules.score["209990"] = [{"type": 1, "id": 3099900, "rarity": 0.01},
                                     {"type": 0, "reward_type": 0, "id": 40193, "count": 99}]
        self.rules.rare["3099900"] = [{"type": 2, "id": 129990}]
        row = self.rules.regular("boss", "1020004", {"scoreRewardGroupId": 209990}, "八岐")
        self.assertIn("1%", row["drops"][0]["probabilityText"])
        self.assertEqual(row["drops"][1]["amountText"], "单人 1／协力 3")

    def test_ex_endless_omits_template_rewards(self):
        row = self.rules.regular("rush", "700100099", {"clearRewardId": 1, "scoreRewardGroupId": 7, "manaReward": 999}, "EX无尽")
        self.assertEqual(row["drops"] + row["firstClear"] + row["sPlus"], [])
        self.assertTrue(row["notes"])

    def test_master_difficulty_preserved(self):
        row = self.rules.regular("raid", "1", {"_wikiDifficulty": "超级"}, "护像之宴")
        self.assertEqual(row["difficulty"], "超级")

    def test_raw_equipment_enum_differs_from_shop_enum(self):
        self.assertEqual(self.names.raw_reward({"type": 1, "id": 123})["kind"], "equipment")
        self.assertEqual(self.names.raw_reward({"type": 1}, shop=True)["kind"], "exp")

    def test_element_rare_granted_as_item_without_dynamic_mapping(self):
        self.assertEqual(self.names.raw_reward({"type": 7, "id": 1})["name"], "素材")

    def test_independent_rogue_slots_and_round_curve(self):
        config = {"per_round_drops": [{"type": "item", "id": 1, "count": 2, "slots": 3,
            "guaranteed_slots": 1, "chance": {"start": 0.1, "per_round": 0.1, "base_round": 1}, "rounds": [1, 4]}]}
        row = rogue_round(self.names, config, 3)[0]
        self.assertEqual(row["amountText"], "2–6")
        self.assertIn("30%", row["probabilityText"])
        self.assertEqual(rogue_round(self.names, config, 5), [])

    def test_rogue_exclusions(self):
        config = {"per_round_drops": [{"type": "item", "id": 1, "exclude_rounds": [4]}]}
        self.assertEqual(rogue_round(self.names, config, 4), [])
        self.assertEqual(rogue_round(self.names, config, 3)[0]["amountText"], "1")

    def test_pool_describes_conditional_weight_not_false_global_probability(self):
        config = {"pool_draws": 2, "drop_pool": [{"type": "equipment", "id": 123, "weight": 3}]}
        note = rogue_round(self.names, config, 1)[0]["probabilityText"]
        self.assertIn("权重 3", note)
        self.assertIn("队伍属性", note)
        self.assertNotIn("%", note)

    def test_abyss_only_finite_folder_has_clear_rewards(self):
        self.assets.data["rush_event_quest_folder.json"] = {"700099": {"1": [{"type": 0, "id": 1}], "2": [{"type": 0, "id": 1}]}}
        self.assertEqual(len(folder_rewards(self.names, self.assets, "700099", {})), 1)

    def test_folder_random_missing_type_defaults_to_item(self):
        rows = folder_rewards(self.names, self.assets, "700099", {
            "folder_clear_random": [{"pool": [1], "count": [2, 4], "pick": 1}]})
        self.assertEqual(rows[0]["drops"][0]["kind"], "item")
        self.assertEqual(rows[0]["drops"][0]["amountText"], "2–4")

    def test_fantasy_parser_rejects_executable_expressions(self):
        source = "export const MODE15_SOLO_FIXED_REWARDS: Record<number, unknown> = {\n    1: evil(),\n};"
        with self.assertRaises(ValueError):
            fantasy_schedule(source)

    def test_fantasy_parser_resolves_all_twelve_rounds(self):
        stages = [1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14]
        source = 'const ELEMENT_TIER_1 = [1, 5] as const;\n'
        source += 'export const MODE15_SOLO_FIXED_REWARDS: Record<number, unknown> = {\n'
        source += ''.join(f'    {stage}: itemSet(ELEMENT_TIER_1, {stage}),\n' for stage in stages) + '};'
        self.assertEqual(fantasy_schedule(source)[14], [(1, 14), (5, 14)])

    def test_fantasy_native_folder_mirror_is_not_double_counted(self):
        key = "event-rush-700098"
        self.assets.data["rush_event_quest_folder.json"] = {"700098": {"1": [{"type": 0, "id": 1, "count": 1}]}}
        special = {"name": "完整通关", "difficulty": "", "firstClear": [], "sPlus": [],
                   "drops": [self.names.reward("item", 1)], "notes": []}
        with patch("wf_wiki_dungeon_rewards.special_mode_rewards", return_value={key: [special]}):
            data, _ = build_payload(self.assets, {"equipment": [], "characters": []},
                {"items": [{"id": key, "title": "幻想连战"}]}, {}, gray_source=Path("fixture"))
        self.assertEqual(len(data["dungeons"][key]["quests"]), 1)
        self.assertFalse(any("尚未对应" in note for note in data["dungeons"][key]["notes"]))

    def test_score_thresholds_grouped_per_quest(self):
        self.assets.data["score_attack_border_reward.json"] = {"1_2": [
            {"score": score, "rewards": [{"id": 1, "amount": 2}]} for score in (100, 200)]}
        rows = score_rewards(self.assets, self.names, "event-score-attack-1", [
            ("score_attack", "1", {"eventId": 1, "scoreAttackQuestId": 2}, "演武")])
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["firstClear"]), 2)


class ShopTests(unittest.TestCase):
    def test_no_stock_is_runtime_unlimited(self):
        self.assertEqual(project_product({}, fixture_names())["stock"], -1)

    def test_collection_event_uses_reference_title_with_provenance(self):
        assets = Assets({"event_item_shop.json": {"9": {"1": {"123": {}}}},
            "event_item_shop_id_map.json": {"123": {"eventType": 9, "eventId": 1}}})
        shops = build_shops(assets, fixture_names(assets), {"items": []}, {}, collect_titles={"1": "周年纪念"})
        self.assertEqual(shops[0]["title"], "周年纪念 · 兑换商店")
        self.assertEqual(shops[0]["dungeonIds"], [])
        self.assertTrue(any("客户端元表参考" in note for note in shops[0]["notes"]))

    def test_utc_dates_follow_runtime(self):
        row = project_product({"availableFrom": "2026-01-01 10:00:00", "stock": 5}, fixture_names())
        self.assertEqual(row["availableFrom"], "2026-01-01T10:00:00Z")
        self.assertEqual(row["stock"], 5)

    def test_shop_association_uses_event_type_and_boss_column(self):
        assets = Assets({"boss_coin_shop.json": {"21": {"201": {}}},
            "boss_coin_shop_item_category_map.json": {"201": 21},
            "event_item_shop.json": {"0": {"1": {"101": {}}}},
            "event_item_shop_id_map.json": {"101": {"eventType": 0, "eventId": 1}}})
        leaves = ["boss-1-22", "event-advent-1", "event-carnival-1"]
        catalog = {"items": [{"id": key, "title": key} for key in leaves]}
        dungeons = {key: {"shopIds": []} for key in leaves}
        shops = build_shops(assets, fixture_names(assets), catalog, dungeons, {"21": ["boss-1-22"]})
        self.assertEqual(shops[0]["dungeonIds"], ["boss-1-22"])
        self.assertEqual(shops[1]["dungeonIds"], ["event-advent-1"])
        self.assertEqual(dungeons["event-carnival-1"]["shopIds"], [])

    def test_normal_and_ex_share_exact_shop_identity(self):
        assets = Assets({"event_item_shop.json": {"11": {"700099": {"101": {}}}},
            "event_item_shop_id_map.json": {"101": {"eventType": 11, "eventId": 700099}}})
        leaves = ["event-rush-700099", "event-rush-700100"]
        catalog = {"items": [{"id": key, "title": key} for key in leaves]}
        dungeons = {key: {"shopIds": []} for key in leaves}
        shops = build_shops(assets, fixture_names(assets), catalog, dungeons)
        self.assertEqual(len(shops), 1)
        self.assertEqual(dungeons[leaves[0]]["shopIds"], dungeons[leaves[1]]["shopIds"])

    def test_dormant_five_boss_product_removed(self):
        assets = Assets({"event_item_shop.json": {"11": {"700099": {"59001010": {}}}}})
        self.assertEqual(build_shops(assets, fixture_names(assets), {"items": []}, {}), [])

    def test_purchase_mapping_mismatch_fails_closed(self):
        assets = Assets({"boss_coin_shop.json": {"21": {"201": {}}}})
        with self.assertRaises(ValueError):
            build_shops(assets, fixture_names(assets), {"items": []}, {})

    def test_boss_shop_mapping_reads_c6(self):
        class Sources:
            def table(self, _):
                return {"1": {"22": 'a,b,c,d,e,f,21'}}
        self.assertEqual(boss_shop_links(Sources(), {"items": [{"id": "boss-1-22"}]}), {"21": ["boss-1-22"]})


if __name__ == "__main__":
    unittest.main()
