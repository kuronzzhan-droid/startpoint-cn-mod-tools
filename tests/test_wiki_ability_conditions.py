"""Native condition badges keep row scope and do not invent resonance."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_ability_conditions import ability_restrictions
from wf_wiki_catalog import ability_group
from wf_wiki_public import readable


def effect(*, unisonable="true", conditions=()):
    row = [""] * 126
    row[:6] = ["example", unisonable, "attack_red", "0", "", "0"]
    for offset, (kind, group, first, maximum) in zip((6, 13, 20), conditions):
        row[offset:offset + 7] = [kind, "", "", first, maximum, group, ""]
    return row


class AbilityConditionTests(unittest.TestCase):
    def test_deltaria_main_flag_and_self_fire_are_distinct(self):
        # Live 1111353: both effects have c1=false and no position precondition.
        row = effect(unisonable="false")
        row[0] = "golemclub_captain_3"
        self.assertEqual(ability_restrictions(row), {"operator": "AND", "items": [
            {"kind": "main", "label": "仅主位", "icon": "main"}]})
        fire = effect(conditions=[("3", "Red", "", "")])
        self.assertEqual(ability_restrictions(fire)["items"], [
            {"kind": "selfElement", "label": "自身为火属性", "icon": "fire", "element": "火"}])

    def test_main_unison_and_resonance_are_row_local_and(self):
        row = effect(unisonable="FALSE", conditions=[
            ("202", "", "", ""), ("2", "White", "600000", "600000")])
        before = deepcopy(row)
        result = ability_restrictions(row)
        self.assertEqual([item["kind"] for item in result["items"]], ["main", "resonance"])
        self.assertEqual(result["items"][1]["element"], "光")
        self.assertEqual(row, before)
        self.assertEqual(ability_restrictions(effect(conditions=[("203", "", "", "")]))["items"],
                         [{"kind": "unison", "label": "仅合击位", "icon": "unison"}])

    def test_or_groups_and_changing_thresholds_are_not_flattened(self):
        for condition in [
            ("2", "White,Black", "600000", "600000"),
            ("3", "Red,Beast", "", ""),
            ("2", "Red", "300000", "600000"),
            ("2", "Red", "600000", ""),
            ("2", "tag_boss", "600000", "600000"),
            ("999", "Red", "600000", "600000"),
        ]:
            with self.subTest(condition=condition):
                result = ability_restrictions(effect(unisonable="false", conditions=[condition]))
                self.assertEqual([item["kind"] for item in result["items"]], ["main"])

    def test_opening_and_short_rows_do_not_read_inapplicable_conditions(self):
        row = effect(conditions=[("202", "", "", "")])
        row[5] = "2"
        self.assertEqual(ability_restrictions(row)["items"], [])
        self.assertEqual(ability_restrictions([])["items"], [])

    def test_catalog_preserves_authored_text_and_public_safe_badges(self):
        rows = [effect(unisonable="false"), effect(conditions=[("203", "", "", "")])]
        class Source:
            def table(self, key):
                return {"ability": {"1": rows}, "strings": {"desc_override_example": [["原始文案"]]}}.get(key, {})
        with patch("wf_wiki_catalog.wf_describe.describe_rows", return_value=["条件原文甲", "条件原文乙"]), patch(
                "wf_wiki_catalog.related_programs", return_value=[]):
            result = ability_group(Source(), "ability", "1", "能力")
        self.assertEqual(result["description"], "原始文案")
        self.assertEqual([r["description"] for r in result["rows"]], ["条件原文甲", "条件原文乙"])
        public = readable(result)
        self.assertEqual([r["restrictions"]["items"][0]["kind"] for r in public["rows"]], ["main", "unison"])
        self.assertNotIn("example", json.dumps(public))
        self.assertNotIn("conditions", public)

    def test_native_asset_keys_cover_badges(self):
        spec = json.loads((Path(__file__).parents[1] / "wiki-ui-assets.json").read_text(encoding="utf-8"))
        icons = {item["key"]: item["textureName"] for item in spec if item["group"] == "abilityConditions"}
        self.assertEqual(set(icons), {"main", "unison", "fire", "water", "thunder", "wind", "light", "dark"})
        self.assertTrue(icons["main"].endswith("/round_main"))
        self.assertTrue(icons["unison"].endswith("/round_unison"))
        self.assertTrue(icons["fire"].endswith("/round_ability_red"))


if __name__ == "__main__":
    unittest.main()
