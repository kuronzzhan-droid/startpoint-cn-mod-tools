"""Verify official comparison provenance and previously unexamined dependencies."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_catalog_source import detect_roster
from wf_wiki_compare import official_comparison, dependency_view, program_label
from wf_wiki_categories import ALIASES, category_for


class Source:
    def __init__(self):
        character = [""] * 37
        for column, value in {0: "white_tiger", 2: "4", 3: "3", 6: "1", 8: "white_tiger", 9: "(None)",
                              17: "3", 18: "原队长技"}.items():
            character[column] = value
        character[19:25] = [str(n) for n in range(81, 87)]
        ability = [""] * 126
        ability[0], ability[47], ability[51], ability[52] = "attack_line", "32", "10000", "20000"
        self.base = {"character": {"10": [character]}, "leader": {"3": [["leader_line"]]},
                     "ability": {"81": [ability]}, "text": {"10": [["白", "", "原人物介绍", "白虎兽人"]]},
                     "status": {"10": [("100", 3088, 729), ("1", 46, 11)]},
                     "skill": {"white_tiger": {"2": [["原技能", "原技能说明", "", "", "580", "530", "", "battle/skill"]]}}}
        self.live = copy.deepcopy(self.base)
        self.trees = {"battle/skill.action.dsl.amf3.deflate": [["Command", ["Damage", 1]], ["Command", ["Damage", 1]]]}
        self.baseline = SimpleNamespace(official_tail="1.4.54")

    def table(self, name, official=False):
        return (self.base if official else self.live).get(name, {})

    def tree(self, logical, official=False):
        return self.trees.get(logical, [None, None])[0 if official else 1]

    def raw(self, logical, official=False):
        tree = self.tree(logical, official)
        return None if tree is None else json.dumps(tree).encode()


def get_item(result, section, index=0):
    return next(group for group in result["sections"] if group["key"] == section)["items"][index]


class OfficialComparisonTests(unittest.TestCase):
    def test_same_id_baseline_not_current_text_and_legacy_leader_key(self):
        source = Source()
        source.live["strings"] = {"desc_override_attack_line": [["当前专属说明"]]}
        source.live["leader"]["3"] = [["new_leader_line"]]
        result = official_comparison(source, "10")
        self.assertEqual(result["baseline"]["version"], "1.4.54")
        self.assertEqual(result["baseline"]["id"], "10")
        self.assertNotIn("当前专属说明", get_item(result, "abilities")["before"]["text"])
        self.assertEqual(get_item(result, "abilities")["after"]["text"], "当前专属说明")
        self.assertEqual(get_item(result, "leader")["before"]["key"], "3")
        self.assertEqual(get_item(result, "leader")["status"], "changed")

    def test_stats_and_skill_weights_report_actual_before_after(self):
        source = Source()
        source.live["status"]["10"][0] = ("100", 3993, 960)
        source.live["skill"]["white_tiger"]["2"][0][5] = "450"
        result = official_comparison(source, "10")
        stats = get_item(result, "stats", 1)
        self.assertEqual(stats["label"], "Lv100 基础数值")
        self.assertEqual(stats["before"]["values"], {"hp": 3088, "atk": 729})
        self.assertEqual(stats["after"]["values"], {"hp": 3993, "atk": 960})
        self.assertEqual(get_item(result, "skills")["before"]["values"]["gauge"], "530")
        self.assertEqual(get_item(result, "skills")["after"]["values"]["gauge"], "450")

    def test_new_variant_never_compares_to_template_or_similar_name(self):
        source = Source()
        source.live["character"]["139994"] = copy.deepcopy(source.base["character"]["10"])
        source.live["character"]["139994"][0][27] = "10"
        result = official_comparison(source, "139994")
        self.assertEqual(result["status"], "new")
        self.assertEqual(result["sections"], [])
        self.assertIsNone(result["baseline"])

    def test_unchanged_and_unavailable_are_distinct(self):
        source = Source()
        self.assertEqual(official_comparison(source, "10")["status"], "unchanged")
        source.base = {}
        self.assertEqual(official_comparison(source, "10")["status"], "unavailable")

    def test_missing_program_does_not_claim_full_equality(self):
        source = Source()
        source.trees = {}
        result = official_comparison(source, "10")
        self.assertEqual(result["status"], "unavailable")
        self.assertIn("缺失", result["summary"][0])
        compact = official_comparison(source, "10", verified_unchanged=True)
        self.assertEqual(compact["status"], "unavailable")

    def test_program_numbers_are_exact_not_inferred_total_damage(self):
        source = Source()
        source.trees["battle/skill.action.dsl.amf3.deflate"][1] = ["Command", ["Damage", 6.5]]
        result = official_comparison(source, "10")
        program = get_item(result, "programs")
        self.assertEqual(program["status"], "changed")
        self.assertEqual(program["changes"], [{"field": "DSL[1][1]", "before": 1, "after": 6.5}])
        self.assertEqual(get_item(result, "skills")["status"], "unchanged")

    def test_public_comparison_program_text_uses_readable_numeric_values(self):
        source = Source()
        source.trees["battle/skill.action.dsl.amf3.deflate"] = [
            ["Command", ["CreateNormalAttack", [], 5, [], [], [], [{"min": 2, "max": 3}]]],
            ["Command", ["CreateNormalAttack", [], 5, [], [], [], [{"min": 4, "max": 6}]]],
        ]
        data = get_item(official_comparison(source, "10"), "programs")
        self.assertIn("2→3倍", data["before"]["text"])
        self.assertIn("4→6倍", data["after"]["text"])
        self.assertNotIn("CreateNormalAttack", data["after"]["text"])
        self.assertEqual(data["label"], "主动技能 · 进化技能")
        self.assertEqual(program_label("A3:row2:PF3"), "能力 3 · 强化弹射 Lv3")

    def test_dependency_views_do_not_render_internal_row_strings(self):
        view = dependency_view("condition", [["internal_code", "光暗共鸣", "battle/path", "900", "3"]])
        self.assertEqual(view["text"], "光暗共鸣；持续 15 秒；叠加上限 3 层")
        self.assertNotIn("battle", dependency_view("power_flip", [["battle/path"]])["text"])

    def test_aliases_and_official_section_are_exact(self):
        self.assertEqual(ALIASES["151159"], ["光龙"])
        self.assertEqual(ALIASES["261089"], ["暗龙"])
        self.assertIn("周年雷吉斯", ALIASES["131020"])
        self.assertNotIn("139994", ALIASES)
        self.assertEqual(category_for("139994")[0], "原创与变体")
        self.assertEqual(category_for("131020")[0], "原版角色改动")


class DependencyDetectionTests(unittest.TestCase):
    def test_override_text_only_change_is_detected(self):
        source = Source()
        source.live["strings"] = {"desc_override_attack_line": [["新的面板说明"]]}
        roster, changed = detect_roster(source)
        self.assertEqual(roster, ["10"])
        self.assertIn("strings:desc_override_attack_line", changed["10"])

    def test_switched_skill_only_change_is_detected(self):
        source = Source()
        for side in (source.base, source.live):
            side["character"]["10"][0][14] = "form"
            side["switched"] = {"form": {"1": [["battle/form"]]}}
        source.live["switched"]["form"]["1"][0][0] = "battle/new_form"
        self.assertIn("switched:form", detect_roster(source)[1]["10"])

    def test_ability_invoke_program_only_change_is_detected(self):
        source = Source()
        for side in (source.base, source.live):
            row = side["ability"]["81"][0]
            row[47], row[70], row[71] = "629", "caption", "battle/actual_program"
        source.trees["battle/actual_program.action.dsl.amf3.deflate"] = [["Command", ["Damage", 1]], ["Command", ["Damage", 2]]]
        self.assertIn("dsl:battle/actual_program.action.dsl.amf3.deflate", detect_roster(source)[1]["10"])

    def test_unbound_condition_and_category_string_do_not_create_fake_mod(self):
        source = Source()
        for side in (source.base, source.live):
            side["ability"]["81"][0][2] = "special"
        source.live["power_flip"] = {"special": [["battle/unrelated"]]}
        source.live["condition"] = {"999": [["id", "其他角色状态"]]}
        self.assertEqual(detect_roster(source), ([], {}))


if __name__ == "__main__":
    unittest.main()
