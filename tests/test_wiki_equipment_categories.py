"""Verified weapon series and source-driven classification remain read-only."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_wiki_equipment as equipment
import wf_wiki_equipment_categories as categories


def weapon(name="测试武器", kind="0", obtain="1"):
    return ["internal_test", name, kind, "", "", "", "item/test", "", "1",
            "false", "", "5", "0", "false", "1", obtain]


def shop(rewards):
    row = [""] * 50
    row[0] = "not_an_equipment_id"
    for slot, (kind, key, count) in enumerate(rewards):
        row[32 + 3 * slot:35 + 3 * slot] = [kind, key, count]
    return row


class Source:
    def __init__(self, data=None):
        self.data = data or {}
        self._tables, self.live_hashes, self.missing = {}, {}, set()
        self.verify_unchanged = Mock()

    def table(self, key):
        return self.data.get(key, {})

    def raw(self, key):
        return None


class EquipmentCategoryTests(unittest.TestCase):
    def test_fantasy_uses_the_eleven_exclusive_ids_not_name_fragments(self):
        for key in range(100013, 100024):
            self.assertEqual(categories.category_for(str(key), weapon()), "幻想武器")
        for key in ("100024", "3010023"):
            self.assertEqual(categories.category_for(key, weapon("幻想的胡萝卜剑")), "其他武器")

    def test_empress_and_pu_lilie_are_exact_independent_series(self):
        for label, keys in categories.SERIES_IDS.items():
            for key in keys:
                self.assertEqual(categories.category_for(key, weapon(), {key: "领主掉落与兑换"}), label)
        self.assertEqual(len(categories.SERIES_IDS["女帝武器"]), 2)
        self.assertEqual(len(categories.SERIES_IDS["普莉莉艾武器"]), 6)
        self.assertEqual(categories.category_for("999", weapon("女帝的普莉莉艾剑")), "其他武器")

    def test_all_existing_special_series_have_priority_over_sources(self):
        expected = {"5920001": "悖论武器", "5910101": "诅咒武器", "5010005": "羁绊武器",
                    "8000114": "深渊武器", "5900101": "五重决战武器"}
        for key, label in expected.items():
            self.assertEqual(categories.category_for(key, weapon(obtain="0"), {key: "活动武器"}), label)
        self.assertEqual(categories.category_for("100001", weapon(kind="1", obtain="0")), "世界弹射器宝珠")

    def test_native_quest_kinds_and_boss_coin_exchange(self):
        source = Source({categories.QUEST_SEARCH: {
            "1": [["0"], ["1"]], "2": [["6"], ["2"]], "3": [["7"]],
            "4": [["9"], ["10"]], "5": [["5"]], "6": [["6"]], "7": [["unknown"]]},
            categories.BOSS_SHOP: {"some_shop": [shop([("4", "6", "1")])]}})
        self.assertEqual(categories.source_categories(source), {
            "1": "主线武器", "2": "领主掉落与兑换", "3": "深层域武器",
            "4": "活动武器", "5": "活动武器", "6": "领主掉落与兑换"})

    def test_six_shop_slots_ignore_non_equipment_and_empty_rewards(self):
        row = shop([("0", "item", "1"), ("4", "zero", "0"), ("4", "a", "2"),
                    ("4", "", "1"), ("4", "b", "1"), ("4", "last", "1")])
        source = Source({categories.BOSS_SHOP: {"shop": [row, ["short"]]}})
        self.assertEqual(categories.source_categories(source), {
            "a": "领主掉落与兑换", "b": "领主掉落与兑换", "last": "领主掉落与兑换"})

    def test_source_rows_are_immutable_and_missing_sources_stay_unknown(self):
        source = Source({categories.QUEST_SEARCH: {"1": [["2", "native"]]},
                         categories.BOSS_SHOP: {"shop": [shop([("4", "2", "1")])]}})
        before = copy.deepcopy(source.data)
        categories.source_categories(source)
        self.assertEqual(source.data, before)
        self.assertEqual(categories.source_categories(Source()), {})
        self.assertEqual(categories.category_for("7", []), "其他武器")

    def test_gacha_requires_explicit_native_source_field(self):
        self.assertEqual(categories.category_for("5050009", weapon(obtain="0")), "装备扭蛋武器")
        self.assertEqual(categories.category_for("7", weapon("扭蛋剑")), "其他武器")

    def test_two_star_swords_join_display_group_without_paradox_decay(self):
        source = Source({equipment.EQUIPMENT: {
            key: [weapon("破星剑" if key != "5920001" else "PARADOX")]
            for key in ("300001", "300002", "5920001")}})
        before = copy.deepcopy(source.data)
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "assets").mkdir()
            for name, value in {"equipment_ids": [300001, 300002, 5920001],
                                "soul_item_ids": [], "equipment_element": {}, "equipment_enhancement_shop": {}}.items():
                (repo / "assets" / (name + ".json")).write_text(json.dumps(value), encoding="utf8")
            rules = repo / "client-patch/equipment-rules/rules.py"
            rules.parent.mkdir(parents=True)
            rules.write_text("class Config:\n    cursed_threshold: int = 2\n    decay_off: int = 4\n", encoding="utf8")
            originals = {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()}
            with patch.object(equipment.EquipmentImages, "image", return_value="media/test.webp"):
                result = equipment.build_equipment_catalog(repo, Mock(), source)
            self.assertEqual(originals, {p: p.read_bytes() for p in repo.rglob("*") if p.is_file()})
        first, second, paradox = result["equipment"]
        self.assertEqual(result["meta"]["counts"], {"悖论武器": 3})
        self.assertNotIn("partyRule", first)
        self.assertNotIn("partyRule", second)
        self.assertEqual(paradox["partyRule"], "paradoxDecay")
        self.assertEqual(source.data, before)
        source.verify_unchanged.assert_called_once()


if __name__ == "__main__":
    unittest.main()
