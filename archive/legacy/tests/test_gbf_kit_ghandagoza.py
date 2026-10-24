# -*- coding: utf-8 -*-
"""冈达葛萨 kit 的完成态契约（不是草稿契约）。

断言的是「机制真的落进包里」：行/树/固有状态/面板文案/图集预算都按设计稿定稿的形态存在。
每条断言都配一个会把它打红的反例（删掉判定就变红，是验收判据）。
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_gbf_duo as G  # noqa: E402
import wf_gbf_duo_dsl as D  # noqa: E402
import wf_gbf_kit_ghandagoza as KIT  # noqa: E402
import wf_midautumn_kitlib as K  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402

PACK = ROOT / "work/character_packs/gbf-ghandagoza-20260919"
DESIGN = ROOT / "work/character_packs/midautumn-20260920/design/ghandagoza.json"
LEADER_FORBIDDEN = {"422", "724", "713"}        # 队长表写这三个 kind = C7050


def design():
    return json.loads(DESIGN.read_text(encoding="utf-8"))


class DslContracts(unittest.TestCase):
    """DSL 形态：这些错法都是静默失效/崩溃，往返自检抓不到。"""

    def test_create_condition_target_kind_is_member(self):
        # 下标 10 写 1 = 施法 C16102（记忆卡 wf-createcondition-target-kind）。
        node = D.condition(1, ["ACParalysis", D.v(600)])[1]
        self.assertEqual(node[10], 3)
        self.assertEqual(D.condition(1, ["ACParalysis", D.v(600)], target_kind=2)[1][10], 2)

    def test_skill_tree_selects_whole_party_including_self(self):
        # 35 = 除自身外：冈达葛萨本人拿不到压血/护盾，能力1「自身每损失1%」永不触发。
        for tree in (KIT.skill_tree(), KIT.opening_tree()):
            for find in C.commands(tree, "FindAllSubjects"):
                self.assertIn(find[2], (33, 49), f"unexpected selector {find[2]}")
        self.assertEqual({f[2] for f in C.commands(KIT.opening_tree(), "FindAllSubjects")}, {33})

    def test_skill_grants_the_unique_the_ability_rows_watch(self):
        uniques = {node[1] for node in C.walk(KIT.skill_tree())
                   if isinstance(node, list) and node and node[0] == "ACUnique"}
        self.assertEqual(uniques, {int(KIT.SEABREAK)})
        watched = set()
        for block in design()["plan"]["ability"]["keys"].values():
            for record in block["records"]:
                if str(record["cells"].get("97", "")) == "134":
                    watched.add(int(record["cells"]["104"]))
        self.assertEqual(watched, uniques, "during 134 看的固有号必须与技能付与的一致")

    def test_adversity_is_written_at_the_engine_clamp(self):
        # NormalAttackCalculator 把状态来源的逆境 min/max 各钳 0.5：写 1.5 与写 0.5 同效。
        values = [node for node in C.walk(KIT.skill_tree())
                  if isinstance(node, list) and node and node[0] == "ACAdversity"]
        self.assertTrue(values)
        for node in values:
            self.assertEqual((node[2], node[3]), (D.v(0.5), D.v(0.5)))

    def test_trees_match_the_design_and_pass_every_gate(self):
        plan = design()
        for name, tree in (("skill", KIT.skill_tree()), ("opening", KIT.opening_tree())):
            KIT.check_against_design(plan, name, tree)
            self.assertEqual(KIT.dsl_gate_problems(tree), [])
        with self.assertRaises(K.KitError):
            KIT.check_against_design(plan, "opening", D.tree(D.cmd("StopBall", -18, 10,
                                                                   ["RestoreToSpeedBeforeActionExecution"],
                                                                   ["EF"], 0)))

    def test_empty_branch_is_a_block_not_donothing(self):
        # ["DoNothing"] 是 IfTargetNotFound 的枚举，写进分支 = 进游戏 F1009。
        branches = [node[3] for node in C.walk(KIT.skill_tree())
                    if isinstance(node, list) and node and node[0] == "ConditionalsHealthPointRatioOf"]
        self.assertTrue(branches)
        for branch in branches:
            self.assertEqual(branch, ["Block", []])


class RowContracts(unittest.TestCase):
    """行装配：donor + 逐格改，过 wf_client_legality 与 wf_describe 回读。"""

    @classmethod
    def setUpClass(cls):
        from wf_seasonal7_build import KitContext
        cls.ctx = KitContext(G.context("ghandagoza"))
        cls.design = design()
        cls.leader, cls.abilities, cls.evidence = KIT.build_tables(cls.ctx, cls.design)

    def test_every_row_is_legal_and_reads_back_as_designed(self):
        for row in self.leader:
            self.assertEqual(K.row_problems("leader_ability", row), {})
        for rows in self.abilities.values():
            for row in rows:
                self.assertEqual(K.row_problems("ability", row, KIT.ELEMENT), {})
        expected = [r["desc_expected"] for r in self.design["plan"]["leader_ability"]["rows"]]
        self.assertEqual([e["describe"] for e in self.evidence[:len(expected)]], expected)

    def test_leader_table_carries_no_patch_only_kinds(self):
        for row in self.leader:
            self.assertNotIn(row[45], LEADER_FORBIDDEN)
            self.assertNotIn(row[107], LEADER_FORBIDDEN)

    def test_no_row_needs_a_client_patch(self):
        self.assertEqual(sorted({c for e in self.evidence for c in e["capabilities"]}), [])

    def test_statue_group_and_main_slot_flag_are_single_valued_per_key(self):
        for key, rows in self.abilities.items():
            K.check_ability_key(rows, key, KIT.CODE, int(key[-1]))
            self.assertEqual({r[2] for r in rows}, {KIT.STATUE_GROUP[key]})
        with self.assertRaises(K.KitError):
            mixed = [list(self.abilities["1299871"][0]), list(self.abilities["1299871"][1])]
            mixed[1][2] = "action_skill"
            K.check_ability_key(mixed, "1299871", KIT.CODE, 1)

    def test_invoke_skill_row_comes_first_and_has_a_string_row(self):
        rows = self.abilities["1299873"]
        self.assertEqual(rows[0][47], "629")
        self.assertEqual(rows[0][70], KIT.OPENING)
        self.assertEqual(rows[0][71], KIT.OPENING_PROGRAM)
        keys = {r["key"] for r in self.design["plan"]["texts"]["custom_ability_string"]["rows"]}
        self.assertIn(KIT.OPENING, keys)                     # 缺行 = 进战斗 C8601
        self.assertIn("change_skill_ghandagoza", keys)
        self.assertEqual(self.abilities["1299876"][0][70], "change_skill_ghandagoza")

    def test_battle_level_pf_rows_carry_no_target(self):
        # during 23 / 413 不读 target：留着 target 会让面板回读成「赋予全队」= 死行文本。
        for rows in self.abilities.values():
            for row in rows:
                if row[109] in ("23", "413"):
                    self.assertEqual((row[110], row[111]), ("", ""))

    def test_unique_conditions_are_eight_digit_with_real_caps(self):
        uniques = KIT.unique_rows(self.ctx)
        self.assertEqual(sorted(uniques), [KIT.BREAK, KIT.SEABREAK])
        for key, row in uniques.items():
            self.assertEqual(len(key), 8)
            self.assertNotIn(row[4], ("", "(None)"))         # (None) = 上限 1，叠层全死
        self.assertEqual(uniques[KIT.BREAK][4], "5")
        self.assertEqual(uniques[KIT.BREAK][9], "false")     # 不可驱散
        self.assertEqual(uniques[KIT.BREAK][10], "true")     # 强制付与（越过 boss 抗性）
        self.assertEqual(uniques[KIT.BREAK][11], "1")        # Bad ⇒ 喂能力5 的敌方减益计数


class PanelContracts(unittest.TestCase):
    def test_panel_text_follows_the_batch_rules(self):
        rows = design()["plan"]["texts"]["custom_ability_string"]["rows"]
        for record in rows:
            skill_flag = record["key"] == "change_skill_ghandagoza"
            self.assertEqual(K.panel_problems(record["text"], skill_flag=skill_flag), [],
                             record["key"])
        self.assertTrue(K.panel_problems("自身为队长时，攻击力＋10%"))
        self.assertTrue(K.panel_problems("强化『炎天呑舟正拳突击』15秒", skill_flag=True))

    def test_power_flip_lines_never_claim_an_element_scope(self):
        # 55 / during 23 / during 413 都是 battle 级：写「水属性角色强化弹射伤害」= 死行文本。
        for record in design()["plan"]["texts"]["custom_ability_string"]["rows"]:
            for line in record["text"].split("\n"):
                if "强化弹射伤害" in line and "独立乘区" not in line:
                    self.assertNotIn("水属性角色强化弹射", line.replace(" ", ""))


class PackageContracts(unittest.TestCase):
    """包里的定稿产物（跑过 kit,manifest 之后才有）。"""

    @classmethod
    def setUpClass(cls):
        report = PACK / "evidence/kit-report.json"
        if not report.is_file():
            raise unittest.SkipTest("kit 尚未跑过")
        cls.report = json.loads(report.read_text(encoding="utf-8"))
        cls.manifest = json.loads((PACK / "package/manifest.json").read_text(encoding="utf-8"))

    def test_kit_report_is_a_completion_not_a_draft(self):
        self.assertEqual(self.report["status"], K.READY)
        self.assertEqual(self.report["required_capabilities"], ["panel-description-override-v2"])
        self.assertNotIn(KIT.PLACEHOLDER_CAPABILITY, self.manifest["required_capabilities"])
        self.assertEqual(self.manifest["required_capabilities"], ["panel-description-override-v2"])
        self.assertTrue(self.report["deviations"])

    def test_manifest_claims_the_new_keys(self):
        tables = {t["logical_path"] if isinstance(t, dict) else t for t in self.manifest["tables"]}
        for logical in ("master/character/unique_condition.orderedmap",
                        "master/string/custom_ability_string.orderedmap",
                        "master/ability/ability.orderedmap",
                        "master/ability/leader_ability.orderedmap"):
            self.assertIn(logical, tables)
        self.assertEqual(sorted(self.manifest["unique_condition"]), [KIT.BREAK, KIT.SEABREAK])
        programs = self.report["skills"]["programs"]
        self.assertTrue(any(KIT.OPENING in p for p in programs))

    def test_effect_family_was_repacked_and_fits_the_atlas_budget(self):
        repack = self.report["effect_repack"]
        self.assertLess(repack["mpx_after"], 0.55)
        self.assertLess(repack["mpx_after"], repack["mpx_before"])
        budget = self.report["atlas_budget"]
        self.assertLessEqual(budget["subject"]["layer0_pct"], 5.0)
        for scenario in budget["scenarios"]:
            self.assertTrue(scenario["fits"], scenario["scenario"])

    def test_parts_matrix_was_divided_back_instead_of_bumping_show_effect(self):
        raw = (PACK / "package/roots/common" / KIT.FX_PARTS).read_bytes()
        parts = C.amf_parse(raw)
        factor = int(round(4096 / KIT.FX_SCALE))
        self.assertEqual({(m["a"], m["d"]) for m in parts["t"][1:]}, {(factor, factor)})
        scales = [node[12] for node in C.walk(KIT.skill_tree())
                  if isinstance(node, list) and node and node[0] == "ShowEffect"]
        self.assertEqual(scales, [["Some", D.v(0.55)]])


if __name__ == "__main__":
    unittest.main()
