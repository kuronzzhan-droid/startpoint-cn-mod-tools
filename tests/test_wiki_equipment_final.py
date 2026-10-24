"""Final effects must combine native semantics, never matching Chinese prose."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_describe
from wf_wiki_equipment_final import KIND, final_effect_fields
from wf_wiki_equipment_helpers import PublicText
from wf_wiki_public import public_catalog


def ability(kind, slot, first, last, *, effect="32", learned=1, cap=99):
    layout = wf_describe.layout(kind)
    row = [""] * layout["ncols"]
    row[:2] = [str(slot), str(learned)]
    if kind == KIND:
        row[2:5] = [str(cap), "24", "48"]
    blocks = layout["blocks"]
    row[blocks["precondition1"] - 1] = "0"
    content = blocks["instant_content"]
    row[content:content + 2] = [effect, "0"]
    row[content + 4:content + 6] = [str(round(first * 1000)), str(round(last * 1000))]
    return row


def growth(row, kind):
    b = wf_describe.layout(kind)["blocks"]
    trigger = b["instant_trigger"]
    row[trigger:trigger + 8] = ["23", "7", "Red", "100000", "100000", "", "", "10"]
    row[b["precondition1"]:b["precondition1"] + 7] = ["2", "", "", "600000", "600000", "Red", ""]
    return row


class FinalEquipmentEffectsTests(unittest.TestCase):
    def setUp(self):
        source = Mock()
        source.table.return_value = {}
        self.text = PublicText(source)

    def render(self, base, enhanced, level=99):
        return final_effect_fields(base, enhanced, 5, level, self.text)

    def test_cross_table_addition_resolves_initial_max_and_stage_independently(self):
        base = [ability("ability_soul", 0, 10, 20)]
        extra = [ability(KIND, 0, 0, 10, cap=101)]
        actual = self.render(base, extra, 51)
        self.assertEqual(actual["finalEffects"], ["自身 攻击力 25%"])
        self.assertEqual(actual["initialFinalEffects"], ["自身 攻击力 15%"])
        self.assertEqual(self.render(base, extra, 101)["finalEffects"], ["自身 攻击力 30%"])

    def test_growth_sums_6_2_1_2_but_not_opening_and_reports_ten_trigger_ceiling(self):
        base = [ability("ability_soul", 0, 22.5, 45),
                growth(ability("ability_soul", 1, 6, 6, learned=5), "ability_soul")]
        extra = [growth(ability(KIND, i, value, value), KIND) for i, value in enumerate((2, 1, 2))]
        result = self.render(base, extra)
        self.assertEqual(len(result["finalEffects"]), 2)
        self.assertEqual(result["finalEffects"][0], "自身 攻击力 45%")
        self.assertIn("攻击力 11%", result["finalEffects"][1])
        self.assertIn("限10次", result["finalEffects"][1])
        self.assertIn("累计110%", result["finalEffects"][1])
        self.assertIn("攻击力 5%", result["initialFinalEffects"][1])
        self.assertNotIn("11%", json.dumps(result["initialFinalEffects"]))

    def test_every_non_strength_body_field_is_part_of_key(self):
        first = ability("ability_soul", 0, 10, 10)
        layout = wf_describe.layout(KIND)["blocks"]
        offsets = [layout["instant_content"] + 1, layout["instant_content"] + 2,
                   layout["precondition1"] + 5, layout["instant_trigger"] + 7,
                   layout["instant_delay"], layout["opening"] + 1]
        for offset in offsets:
            with self.subTest(offset=offset):
                other = ability(KIND, 0, 20, 20)
                other[offset] = "1"
                self.assertEqual(len(self.render([first], [other])["finalEffects"]), 2)

    def test_timed_override_dynamic_and_unrecognized_content_never_merge(self):
        for effect, offset, value in (("32", 8, "1000"), ("32", 10, "60"),
                                     ("32", 28, "2"), ("32", 35, "7"),
                                     ("0", 0, "0"), ("99999", 0, "99999")):
            with self.subTest(effect=effect, offset=offset):
                rows = [ability(kind, 0, 10, 10, effect=effect) for kind in ("ability_soul", KIND)]
                for kind, row in zip(("ability_soul", KIND), rows):
                    row[wf_describe.layout(kind)["blocks"]["instant_content"] + offset] = value
                result = self.render([rows[0]], [rows[1]])["finalEffects"]
                self.assertEqual(len(result), 2)

    def test_consuming_precontent_and_non_whitelisted_trigger_remain_separate(self):
        for block, value in (("instant_precontent", "0"), ("instant_trigger", "30")):
            rows = [ability(kind, 0, 10, 10) for kind in ("ability_soul", KIND)]
            for kind, row in zip(("ability_soul", KIND), rows):
                row[wf_describe.layout(kind)["blocks"][block]] = value
            self.assertEqual(len(self.render([rows[0]], [rows[1]])["finalEffects"]), 2)

    def test_slot_replacement_and_original_inputs_unchanged(self):
        base = [ability("ability_soul", 0, 1, 10), ability("ability_soul", 0, 5, 50, learned=5)]
        extra = [ability(KIND, 0, 20, 20)]
        before = copy.deepcopy((base, extra))
        actual = self.render(base, extra)
        self.assertEqual(actual["finalEffects"], ["自身 攻击力 70%"])
        self.assertEqual(actual["initialFinalEffects"], ["自身 攻击力 21%"])
        self.assertEqual((base, extra), before)

    def test_invoked_custom_mechanism_is_retained_without_private_paths(self):
        enums = wf_describe.enum_map()["enums"]["InstantAbilityContentMasterValue"]
        code = next(key for key, value in enums.items() if value == "InvokeSkill")
        row = ability(KIND, 2, 0, 0, effect=code)
        content = wf_describe.layout(KIND)["blocks"]["instant_content"]
        row[content + 23] = "hidden_program"
        self.text.custom["hidden_program"] = "每次吞噬协力球提升攻击，最多9次"
        fields = self.render([], [row])
        self.assertIn("最多9次", fields["finalEffects"][0])
        published = public_catalog({"meta": {}, "characters": [], "equipment": [{"id": "123", "enhancement": fields}]})
        self.assertEqual(published["equipment"][0]["enhancement"], fields)
        self.assertNotIn("hidden_program", json.dumps(published))


if __name__ == "__main__":
    unittest.main()
