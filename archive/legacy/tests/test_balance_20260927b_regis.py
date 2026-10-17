"""雷吉斯 139994 · 2026-09-27 平衡第二批（无上限成长）的修订模块回归。

fixture = live 1.4.1049（= 第一批输出 = s7-regis 1.0.7）只读快照；逐项断言改动前后值、未改行/节点逐字保留、
BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、合法性与 DSL 门禁为空、面板规则，以及 kit
（wf_seasonal7_kit_regis）按「浪涌 → 第一批 → 第二批」顺序重跑与 revise() 一致。
"""
from __future__ import annotations

import inspect
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927_regis as B1  # noqa: E402
import wf_balance_20260927b_regis as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_regis_surge_stages as R  # noqa: E402
import wf_seasonal7_kit_regis as K  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402
from wf_seasonal7_kit_philia import cmds, dsl_gate_failures, dsl_gates  # noqa: E402

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures/balance_20260927b_regis.json"
B1_FIXTURE = HERE / "fixtures/balance_20260927_regis.json"
SURGE_FIXTURE = HERE / "fixtures/surge_anchor_before.json"
ROOT = HERE.parents[1]
L1, L2 = M.SKILL_PROGRAMS["1"], M.SKILL_PROGRAMS["2"]
MANIFEST_CAPS = {"kyubi-fever-ratio-v1", "panel-description-override-v2"}


def load(path=FIXTURE):
    fx = json.loads(path.read_bytes())
    return {(kind, tuple(key) if isinstance(key, list) else key): value for kind, key, value in fx["reads"]}


def reader(data):
    return lambda kind, key: data[kind, key]


def beam_total(tree, stacks: int) -> float:
    """按客户端语义（ActionEvaluator case 101：var = min(层数/除数, 上限)；vlv = min + (max−min)×var）
    求某层数下命中的那一档光束 10 段合计倍率。"""
    choice = tree[11][1][1]
    branch = choice
    while branch[0] == "Command":
        c = branch[1]
        branch = c[3] if stacks >= c[2] else c[4]
    bind, = cmds(branch, "BindConditionAccumulationVariable")
    attack, = cmds(branch, "CreateNormalAttack")
    area, = cmds(branch, "CreateHitArea")
    cell = attack[6][0]
    var = min(stacks / bind[4], bind[5])
    vlv = cell["vlv"][0]
    return area[14][1] * (cell["max"] + vlv["min"] + (vlv["max"] - vlv["min"]) * var)


class ReviseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.out = M.revise(reader(cls.data))

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    def assertOnly(self, before, after, cells):
        restored = deepcopy(after)
        for col, value in cells.items():
            restored[col] = value
        self.assertEqual(before, restored)

    # ---------------------------------------------------------------- 行
    def test_leader_team_rows_slowed_to_one_fifth(self):
        before, after = self.live("leader", M.CID), self.out["leader"][M.CID]
        self.assertEqual((7, 9), (len(before), len(after)))
        self.assertEqual(["150000", "150000"], before[0][111:113])
        self.assertEqual(["30000", "30000"], after[0][111:113])          # 雷队技伤每层 150% → 30%
        self.assertEqual(("2", "5", "Yellow"), (after[0][107], after[0][108], after[0][109]))
        self.assertOnly(before[0], after[0], {111: "150000", 112: "150000"})
        self.assertEqual(["100000", "100000"], before[1][111:113])
        self.assertEqual(["20000", "20000"], after[1][111:113])          # 雷队攻每层 100% → 20%
        self.assertOnly(before[1], after[1], {111: "100000", 112: "100000"})
        self.assertEqual(before[2:7], after[2:7])                        # 充能 / Fever / 461 行逐字保留
        self.assertEqual(["(None)", "(None)"], [after[0][100], after[1][100]])   # 队长侧仍不设上限

    def test_moved_self_rows_are_ability_rows_shifted_by_two(self):
        third, after = self.live("ability", M.THIRD_KEY), self.out["leader"][M.CID]
        for leader_row, ability_row, kind in ((after[7], third[3], "0"), (after[8], third[4], "2")):
            self.assertEqual([M.CODE, "0", ""], leader_row[:3])
            expect = deepcopy(ability_row[5:])
            expect[111 - 3] = expect[112 - 3] = "30000"                   # 150% × 1/5
            self.assertEqual(expect, leader_row[3:])
            self.assertEqual(("1", "134", "(None)", M.UID, kind, "0"),
                             (leader_row[3], leader_row[95], leader_row[100], leader_row[102],
                              leader_row[107], leader_row[108]))
            self.assertEqual(("0", "", ""), (leader_row[4], leader_row[7], leader_row[9]))   # 仍无共鸣前置
        described = wf_describe.describe_rows(after, "leader_ability")
        self.assertEqual("持续·状态累积计数固有≥1[固有13999401] → 自身 攻击力 30%", described[7])
        self.assertEqual("持续·状态累积计数固有≥1[固有13999401] → 自身 技能伤害 30%", described[8])

    def test_ability3_self_rows_capped_at_five_layers(self):
        before, after = self.live("ability", M.THIRD_KEY), self.out["ability"][M.THIRD_KEY]
        self.assertEqual(5, len(after))
        for i in (3, 4):
            self.assertEqual(("(None)", "150000", "150000"), (before[i][102], before[i][113], before[i][114]))
            self.assertEqual(("5", "30000", "30000"), (after[i][102], after[i][113], after[i][114]))
            self.assertOnly(before[i], after[i], {102: "(None)", 113: "150000", 114: "150000"})
        self.assertEqual(before[:3], after[:3])
        self.assertTrue(all(r[1] == "false" for r in after))              # 整键仍是主位限制
        described = wf_describe.describe_rows(after, "ability")
        self.assertIn("(限5次)", described[3])
        self.assertIn("攻击力 30%", described[3])
        self.assertIn("技能伤害 30%", described[4])

    def test_after_fingerprints(self):
        leader, third = self.out["leader"][M.CID], self.out["ability"][M.THIRD_KEY]
        for row, cells in ((leader[0], M.LEADER_TEAM_SKILL_AFTER), (leader[1], M.LEADER_TEAM_ATTACK_AFTER),
                           (leader[7], M.MOVED_SELF_ATTACK), (leader[8], M.MOVED_SELF_SKILL)):
            self.assertTrue(M._matches(row, M.LEADER_NCOLS, cells))
        for row, cells in ((third[3], M.THIRD_SELF_ATTACK_AFTER), (third[4], M.THIRD_SELF_SKILL_AFTER)):
            self.assertTrue(M._matches(row, M.ABILITY_NCOLS, cells))
        self.assertEqual(M.LEADER_ROWS_AFTER, len(leader))

    def test_official_shape_precedents(self):
        """能力侧 = 官方 1610631#1/#2（134 自身攻/技伤 c102=4），队长侧 = 官方 161063#2/#3（134 → 0/2 自身）。"""
        after = self.out["ability"][M.THIRD_KEY]
        for row in after[3:5]:
            self.assertEqual(("1", "134", "0", "100000", "100000", "false", "0"),
                             (row[5], row[97], row[98], row[100], row[101], row[108], row[110]))
            self.assertTrue(row[102].isdigit())

    def test_row_legality_and_capabilities(self):
        caps = set()
        for kind, rows in (("leader_ability", self.out["leader"][M.CID]),
                           ("ability", self.out["ability"][M.THIRD_KEY])):
            for row in rows:
                self.assertEqual([], L.client_legality_problems(kind, row))
                self.assertEqual([], L.declared_block_field_problems(kind, row))
                self.assertEqual([], L.invoke_skill_string_problems(row, {B1.STRIKE_KEY}, kind))
                caps.update(L.required_client_capabilities(kind, row))
        self.assertLessEqual(caps, MANIFEST_CAPS)
        self.assertEqual([], M.CAPABILITIES)
        self.assertEqual([], M.row_problems("leader_ability", self.out["leader"][M.CID]))

    # ---------------------------------------------------------------- DSL
    def test_bind_caps_99_to_5_and_nothing_else(self):
        for program in (L1, L2):
            before, after = self.live("dsl", program), self.out["dsl"][program]
            self.assertEqual([99.0] * 3, [b[5] for b in M.binds(before)])
            self.assertEqual([5.0] * 3, [b[5] for b in M.binds(after)])
            self.assertTrue(all(isinstance(b[5], float) for b in M.binds(after)))   # 仍是 double
            restored = deepcopy(after)
            for bind in M.binds(restored):
                bind[5] = 99.0
            self.assertEqual(before, restored)                           # 倍率 / vlv / 分支 / 特效逐节点不变

    def test_layer_contribution_stops_at_five(self):
        for program in (L1, L2):
            before, after = self.live("dsl", program), self.out["dsl"][program]
            for stacks, want in ((0, 50), (2, 80), (3, 120), (4, 135), (5, 175), (6, 175), (99, 175)):
                self.assertAlmostEqual(want, beam_total(after, stacks), places=6, msg=(program, stacks))
            self.assertAlmostEqual(190, beam_total(before, 6), places=6)       # 改前无上限
            self.assertAlmostEqual(1585, beam_total(before, 99), places=6)

    def test_dsl_gates_are_clean(self):
        for program, tree in self.out["dsl"].items():
            encode_tree(tree)
            self.assertEqual([], M.dsl_problems(tree), program)
            self.assertEqual([], L.action_dsl_element_problems(tree, 2), program)
            self.assertEqual([], L.action_dsl_subject_binding_problems(tree), program)
            self.assertEqual([], L.action_dsl_lookup_scope_problems(tree), program)
            self.assertEqual([], L.action_dsl_hit_area_target_problems(tree), program)
            self.assertEqual([], dsl_gate_failures(dsl_gates(tree, element=2)), program)

    # ---------------------------------------------------------------- 文案
    def test_descriptions_five_places(self):
        self.assertEqual(B1.DESCRIPTION.replace("每层额外＋15倍", "每层额外＋15倍（最多5层）"), M.DESCRIPTION)
        for value in (self.out["text"][M.CID], self.out["server_text"][M.CID]):
            self.assertEqual([M.DESCRIPTION] * 2, [value[0][5], value[0][7]])
        text_before = self.live("text", M.CID)
        text_before[0][5] = text_before[0][7] = M.DESCRIPTION
        self.assertEqual(text_before, self.out["text"][M.CID])
        server_before = self.live("server_text", M.CID)
        server_before[0][5] = server_before[0][7] = M.DESCRIPTION
        self.assertEqual(server_before, self.out["server_text"][M.CID])
        action_before = [(k, list(v)) for k, v in self.live("action", M.CODE)]
        for _k, fields in action_before:
            self.assertEqual(B1.DESCRIPTION, fields[1])
            fields[1] = M.DESCRIPTION
        self.assertEqual(action_before, [(k, list(v)) for k, v in self.out["action"][M.CODE]])
        self.assertEqual([], K.skill_desc_coverage_problems(
            [self.out["dsl"][p] for p in (L1, L2)], M.DESCRIPTION))

    def test_panel_texts(self):
        cas = self.out["cas"]
        self.assertEqual({M.PANEL_LEADER, M.PANEL_THIRD}, set(cas))
        old = self.live("cas", M.PANEL_LEADER)[0][0].split("\n")
        new = cas[M.PANEL_LEADER][0][0].split("\n")
        self.assertEqual(len(old) + 1, len(new))
        self.assertEqual("雷属性共鸣时，每层「浪涌充能」，雷属性角色技能伤害＋30%、攻击力＋20%", new[0])
        self.assertEqual("每层「浪涌充能」，自身攻击力＋30%、技能伤害＋30%", new[1])
        self.assertEqual(old[1:], new[2:])
        old3 = self.live("cas", M.PANEL_THIRD)[0][0].split("\n")
        new3 = cas[M.PANEL_THIRD][0][0].split("\n")
        self.assertEqual(old3[:3], new3[:3])
        self.assertEqual(M.MAIN_ICON + "每层「浪涌充能」，自身攻击力＋30%、技能伤害＋30%（最多5层）", new3[3])
        self.assertTrue(all(line.startswith(M.MAIN_ICON) for line in new3))
        self.assertFalse(any(line.startswith(M.MAIN_ICON) for line in new))
        for key, cells in cas.items():
            text = cells[0][0]
            self.assertEqual(M.PANEL_AFTER[key], text)
            self.assertEqual([], KL.panel_problems(text), key)
            self.assertEqual([], K.panel_text_problems(text), key)
            self.assertNotIn("／", text)
            for word in ("可无限", "无上限", "无限叠加", "不设上限", "自身为队长时", "觉醒后", "生命值100%以下"):
                self.assertNotIn(word, text)

    def test_main_slot_markers_still_match_rows(self):
        rows = {key: [["x", flag]] for key, flag in
                ((M.CID + "1", "false"), (M.CID + "2", "true"), (M.CID + "4", "true"),
                 (M.CID + "5", "true"), (M.CID + "6", "true"))}
        rows[M.THIRD_KEY] = self.out["ability"][M.THIRD_KEY]
        cas = {key: [[K.MAIN_ICON + "x"]] if key == K.CAS_KEYS[1] else [["x"]] for key in K.CAS_KEYS}
        cas.update(self.out["cas"])
        self.assertEqual([], K.main_slot_panel_problems(rows, cas))

    # ---------------------------------------------------------------- 契约
    def test_only_changed_keys_are_returned(self):
        norm = lambda v: json.loads(json.dumps(v, ensure_ascii=False))
        seen = set()
        for kind in ("ability", "leader", "cas", "text", "action", "dsl", "server_text", "table"):
            for key, value in self.out[kind].items():
                self.assertIn((kind, key), self.data)
                self.assertNotEqual(norm(self.data[kind, key]), norm(value), (kind, key))
                seen.add((kind, key))
        self.assertEqual(set(M.BEFORE), seen)
        self.assertEqual([], self.out["new_programs"])
        self.assertFalse(self.out["notes"]["runtime_verified"])

    def test_baseline_drift_is_rejected_and_inputs_are_not_mutated(self):
        snapshot = deepcopy(self.data)
        M.revise(reader(self.data))
        self.assertEqual(snapshot, self.data)
        for (kind, key) in M.BEFORE:
            drifted = deepcopy(self.data)
            value = drifted[kind, key]
            if kind == "dsl":
                value[1] = 3
            elif kind == "action":
                value[0][1][4] = "601"
            else:
                value[0][0] = value[0][0] + "x"
            with self.assertRaisesRegex(ValueError, "drifted"):
                M.revise(reader(drifted))

    def test_rerun_on_own_output_is_rejected(self):
        out = self.out
        staged = dict(self.data)
        for kind in ("ability", "leader", "cas", "text", "action", "dsl", "server_text"):
            for key, value in out[kind].items():
                staged[kind, key] = value
        with self.assertRaisesRegex(ValueError, "drifted"):
            M.revise(reader(staged))
        with self.assertRaisesRegex(ValueError, "batch-1 output|preimage"):
            M.growth_rows(out["leader"][M.CID], self.live("ability", M.THIRD_KEY))
        with self.assertRaisesRegex(ValueError, "preimage"):
            M.growth_rows(self.live("leader", M.CID), out["ability"][M.THIRD_KEY])
        for program in (L1, L2):
            with self.assertRaisesRegex(ValueError, "unreviewed"):
                M.skill_tree(out["dsl"][program])
        with self.assertRaisesRegex(ValueError, "batch-1"):
            M.description(M.DESCRIPTION)
        for key in M.PANEL_BEFORE:
            with self.assertRaisesRegex(ValueError, "batch-1"):
                M.panel_text(key, out["cas"][key][0][0])

    def test_unreviewed_shapes_are_rejected(self):
        leader = self.live("leader", M.CID)
        leader[0][100] = "10"                                            # 有人先给队长加了上限
        with self.assertRaisesRegex(ValueError, "preimage"):
            M.growth_rows(leader, self.live("ability", M.THIRD_KEY))
        third = self.live("ability", M.THIRD_KEY)
        third[4][109] = "154"                                            # 退回能力伤害
        with self.assertRaisesRegex(ValueError, "preimage"):
            M.growth_rows(self.live("leader", M.CID), third)
        tree = self.live("dsl", L1)
        M.binds(tree)[0][5] = 99                                         # int 上限（不同 AMF3 编码）
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            M.skill_tree(tree)
        old_tree = self.live("dsl", L1)
        old_tree[10] = 2                                                 # 第一批之前的能力伤害树
        with self.assertRaisesRegex(ValueError, "batch-1"):
            M.skill_tree(old_tree)


class GeneratorConsistencyTest(unittest.TestCase):
    """kit 走「浪涌 → 第一批 → 第二批」同一组函数，产物必须 == revise()。"""

    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.out = M.revise(reader(cls.data))
        cls.b1_data = load(B1_FIXTURE)
        cls.surge = json.loads(SURGE_FIXTURE.read_bytes())

    def test_kit_rows_after_surge_and_batch1_match_revise(self):
        leader, third = R.revise_rows(self.surge["139994"], self.surge["1399943"], self.surge["1399941"])
        ability = {M.CID + s: deepcopy(self.b1_data["ability", M.CID + s]) for s in ("2", "5")}
        ability[M.THIRD_KEY] = third
        leader, ability = K.balance_rows(leader, ability)
        self.assertEqual(self.data["leader", M.CID], leader)            # 第一批输出 == 本批输入
        self.assertEqual(self.data["ability", M.THIRD_KEY], ability[M.THIRD_KEY])
        leader, ability = K.balance_b_rows(leader, ability)
        self.assertEqual(self.out["leader"][M.CID], leader)
        self.assertEqual(self.out["ability"][M.THIRD_KEY], ability[M.THIRD_KEY])

    def test_kit_skill_trees_match_revise(self):
        matched = set()
        for source in self.surge["regis"]:
            tree = B1.skill_tree(R.revise_skill(source))
            for level, program in M.SKILL_PROGRAMS.items():
                if tree == self.data["dsl", program]:
                    self.assertEqual(self.out["dsl"][program], M.skill_tree(tree))
                    matched.add(level)
        self.assertEqual({"1", "2"}, matched)

    def test_kit_panel_and_description_match_revise(self):
        cas = {key: deepcopy(self.b1_data["cas", key]) for key in B1.PANEL_KEYS.values()}
        cas[K.CAS_KEYS[4]] = [["雷属性角色攻击力＋100%"]]
        panel = K.balance_b_panel(K.balance_panel(cas))
        for key, cells in self.out["cas"].items():
            self.assertEqual(cells, panel[key], key)
        for key in set(panel) - set(self.out["cas"]):
            self.assertEqual(K.balance_panel(cas)[key], panel[key], key)   # 其余键原样透传
        self.assertEqual(M.DESCRIPTION, M.description(B1.description(R.DESCRIPTION)))
        self.assertEqual(self.out["text"][M.CID][0][5], M.DESCRIPTION)
        with self.assertRaises(K.KitError):
            K.balance_b_panel({M.PANEL_THIRD: [["x"]]})

    def test_kit_build_applies_batch2_after_batch1(self):
        src = inspect.getsource(K.build)
        self.assertLess(src.index("balance_rows("), src.index("balance_b_rows("))
        self.assertLess(src.index("balance.skill_tree("), src.index("balance_b.skill_tree("))
        self.assertLess(src.index("cas_rows = balance_panel("), src.index("cas_rows = balance_b_panel("))
        self.assertIn("balance_b.description(balance.description(surge.DESCRIPTION))", src)
        self.assertLess(src.index("balance_b_panel("), src.index("main-slot marker mismatch after balance"))

    @unittest.skipUnless((ROOT / K.REVISION_REL).is_file(), "seasonal7 revision plan (gitignored work/) absent")
    def test_kit_chain_from_plan_matches_revise(self):
        revision = K.revision_rows(K.load_revision(ROOT))
        leader = [e["row_built"] for e in revision["leader"]]
        ability = {f"{K.CID}{slot[4:]}": [e["row_built"] for e in entries]
                   for slot, entries in revision["abilities"].items()}
        leader, ability[K.CID + "3"] = R.revise_rows(leader, ability[K.CID + "3"], ability[K.CID + "1"])
        leader, ability = K.balance_b_rows(*K.balance_rows(leader, ability))
        self.assertEqual(self.out["leader"][M.CID], leader)
        self.assertEqual(self.out["ability"][M.THIRD_KEY], ability[M.THIRD_KEY])
        cas = {item["key"]: [[item["text"]]] for item in revision["custom_strings"]}
        for slot, key in ((0, K.CAS_KEYS[0]), (3, K.CAS_KEYS[3])):
            cas[key][0][0] = R.revise_text(slot, cas[key][0][0])
        cas = K.balance_b_panel(K.balance_panel(cas))
        for key, cells in self.out["cas"].items():
            self.assertEqual(cells, cas[key], key)
        self.assertEqual([], K.main_slot_panel_problems(ability, cas))


if __name__ == "__main__":
    unittest.main()
