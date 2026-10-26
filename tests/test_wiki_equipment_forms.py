"""PARADOX milestone levels must not borrow the highest-level endpoints."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_describe
from wf_wiki_equipment_helpers import PublicText
from wf_wiki_equipment_forms import KIND, TEAM_KINDS, paradox_forms, row_at_level
from wf_wiki_public import public_catalog


def row(kind, slot, effect, first, last, learn=1, cap=119, chosen=False):
    layout = wf_describe.layout(kind)
    result = [""] * layout["ncols"]
    result[:2] = [str(slot), str(learn)]
    if kind == KIND:
        result[2] = str(cap)
    blocks = layout["blocks"]
    pre, content = blocks["precondition1"], blocks["instant_content"]
    result[pre - 1] = "0"
    result[pre] = "3" if chosen else "0"
    result[pre + 5] = "tag_trio" if chosen else ""
    result[content:content + 2] = [effect, "" if effect in TEAM_KINDS else "0"]
    scale = 100000 if effect == "226" else 1000
    result[content + 4:content + 6] = [str(round(first * scale)), str(round(last * scale))]
    return result


class EquipmentFormTests(unittest.TestCase):
    def setUp(self):
        source = Mock()
        source.table.return_value = {}
        self.text = PublicText(source)
        self.text.groups["tag_trio"] = "基诺维／杰拉德／凯尔"
        self.text.custom.update({
            "enhanced_pixelart_tier2_item/private/paradox_lv120": "200,item/private/paradox_lv200",
            "enhanced_frame_override_item/private/paradox_lv200": "item/private/frame",
        })
        self.images = Mock()
        self.images.image.side_effect = lambda logical: {
            "item/private/paradox_lv120": "media/form120.webp",
            "item/private/paradox_lv200": "media/form200.webp",
            "item/private/frame": "media/frame.webp",
        }[logical]
        specs = [(k, 550, 230, 20, 220, False) for k in ("32", "33", "34", "55", "388")]
        specs += [(k, 10, 9.5, .5, 10.5, False) for k in ("723", "693", "694", "695", "696")]
        specs += [("35", 20, 9.25, .75, 20.75, False), ("245", 50, 47.5, 2.5, 2.5, False),
                  ("717", 100, 46.25, 3.75, 53.75, False), ("32", 150, 93.75, 6.25, 106.25, True)]
        self.soul, self.enhanced = [], []
        for effect, base, grown, first, last, chosen in specs:
            self.soul.append(row("ability_soul", len(self.soul), effect, base, base, chosen=chosen))
            self.enhanced.append(row(KIND, len(self.enhanced), effect, 0, grown, chosen=chosen))
            self.enhanced.append(row(KIND, len(self.enhanced), effect, first, last, 120, 200, chosen))
        self.soul.append(row("ability_soul", len(self.soul), "226", 35, 35))
        self.enhanced.append(row(KIND, len(self.enhanced), "226", 15, 15, 120, 120))
        self.entry = {"id": "5920001", "maxAwakeningLevel": 5,
            "stats": {"awakened": {"hp": 495, "atk": 221}},
            "enhancement": {"maxLevel": 200, "name": "PARADOX·终式", "description": "120级进入终式",
                            "panelDescription": "119后续涨至200", "note": "原值"}}
        self.erow = ["200", "120", "PARADOX·终式", "120", "item/private/paradox_lv120"]
        self.points = [{"level": 120, "hp": 50, "atk": 10}, {"level": 200, "hp": 100, "atk": 40}]

    def forms(self):
        return paradox_forms(self.entry, self.erow, self.soul, self.enhanced, self.points, self.text, self.images)

    def test_120_and_200_totals_have_independent_endpoints(self):
        first, last = self.forms()
        for form, atk, multiplier, charge, unison, chosen in (
                (first, 800, 20, 30, 150, 250), (last, 1000, 30, 50, 200, 350)):
            summary = form["finalDescription"]
            for phrase in (f"自身攻击力 +{atk}%", f"强化弹射伤害 +{atk}%",
                           f"独立乘区强化弹射伤害 +{multiplier}%", f"技能充能速度 +{charge}%",
                           f"追加合击角色攻击力比例 +{unison}%", f"时额外攻击力 +{chosen}%",
                           "技能槽上限 +100%", "每次弹射追加连击 +50次"):
                self.assertIn(phrase, summary)
        self.assertIn("自身 攻击力 20%", first["effects"])
        self.assertIn("自身 攻击力 220%", last["effects"])
        self.assertIn("自身 攻击力 800%", first["finalEffects"])
        self.assertIn("自身 攻击力 1000%", last["finalEffects"])
        self.assertIn("自身 攻击力 800%", first["initialFinalEffects"])

    def test_snapshots_keep_source_rows_and_entry_immutable(self):
        before = copy.deepcopy((self.entry, self.erow, self.soul, self.enhanced, self.points))
        self.forms()
        self.assertEqual(before, (self.entry, self.erow, self.soul, self.enhanced, self.points))
        for level, expected in ((120, "20000"), (200, "220000")):
            self.assertEqual(row_at_level(self.enhanced[1], level)[51:53], [expected, expected])

    def test_initial_summary_uses_initial_endpoint_and_unlocked_slots_for_each_stage(self):
        before_max = [form["finalDescription"] for form in self.forms()]
        content = wf_describe.layout("ability_soul")["blocks"]["instant_content"]
        self.soul[0][content + 4] = "220000"
        forms = self.forms()
        self.assertEqual([form["finalDescription"] for form in forms], before_max)
        for form, expected in zip(forms, (470, 670)):
            self.assertIn("含初始本体", form["initialFinalDescription"])
            self.assertIn(f"自身攻击力 +{expected}%", form["initialFinalDescription"])
            self.assertIn("时额外攻击力", form["initialFinalDescription"])
        self.soul.append(row("ability_soul", len(self.soul), "32", 100, 100, learn=5))
        added = self.forms()
        self.assertEqual([form["initialFinalDescription"] for form in added],
                         [form["initialFinalDescription"] for form in forms])
        self.assertIn("自身攻击力 +900%", added[0]["finalDescription"])

    def test_each_form_has_its_own_icon_stats_and_only_200_has_frame(self):
        first, last = self.forms()
        self.assertEqual([first["level"], last["level"]], [120, 200])
        self.assertEqual(first["stats"]["total"], {"hp": 545, "atk": 231})
        self.assertEqual(last["stats"]["total"], {"hp": 595, "atk": 261})
        self.assertNotEqual(first["icon"], last["icon"])
        self.assertNotIn("frame", first)
        self.assertEqual(last["frame"], "media/frame.webp")
        self.assertIn("Lv200仍为8段", last["note"])

    def test_public_forms_do_not_include_internal_keys_or_source_paths(self):
        self.entry["enhancement"]["forms"] = self.forms()
        published = public_catalog({"meta": {}, "characters": [], "equipment": [self.entry]})
        serialized = json.dumps(published, ensure_ascii=False)
        for private in ("5920001", "tag_trio", "item/private", "enhanced_pixelart", "raw", "commands"):
            self.assertNotIn(private, serialized)
        self.assertIn("media/form120.webp", serialized)
        self.assertIn("自身攻击力 +800%", serialized)
        self.assertEqual(published["equipment"][0]["enhancement"]["forms"][0]["initialFinalDescription"],
                         self.entry["enhancement"]["forms"][0]["initialFinalDescription"])


if __name__ == "__main__":
    unittest.main()
