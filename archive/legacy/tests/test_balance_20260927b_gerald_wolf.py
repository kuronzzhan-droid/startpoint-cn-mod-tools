# -*- coding: utf-8 -*-
"""杰拉德 149999 ``white_wolf_gerald`` 2026-09-27 平衡调整第二批。

fixture = live 输入快照（``fixtures/balance_20260927b_gerald_wolf.json``，1.4.1049 只读取数），驱动 ``revise()``：
队长行7–9 成长 50%→5%、行10 Fever 眩晕蓄积 500%→50%、PF Lv3 时之刻印分支 p13 3→2.5（无刻印分支不动）、
技能两档时空侵蚀 Bind 上限 2147483647→10 的前后值；未改行/未改树节点逐字保留；BEFORE 漂移拒绝；不改输入；
对自身输出重跑拒绝；合法性门禁与四道 DSL 门禁为空、AMF3 往返；面板自动生成且过面板规则；
``wf_gerald_cast_growth.rewrite`` 对施技成长前的技能树重跑 == revise() 输出，三个杰拉德生成器重跑不回退本次改动；
候选工作区干跑拼接（需要本机工作区，缺时跳过）。
``_context`` 里是 revise() 不读取的 live 参照（PF Lv1/2、月牙斩、能力、字串、文本），只用来核对「保留」项的现值。
"""
from __future__ import annotations

from wf.paths import root_path

import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_gerald_wolf as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_dsl  # noqa: E402
import wf_gerald_cast_growth as G  # noqa: E402
import wf_gerald_percent_revision as PR  # noqa: E402
import wf_gerald_percent_skill as P  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_gerald_wolf.json"
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
#: 09-25 修订前捕获的 live 技能树（percent_skill 之后、cast_growth 之前 = cast_growth 的真实输入）。
CAPTURED_0925 = Path(('${WF_ROOT}/out/风巨蜥与校园希尔媞调整-20260925/before/live/common'.replace("${WF_ROOT}", str(root_path()))))
PF_KEY = "|".join(M.PF_ACTION)
FANG = ("battle/action/skill/action/ability_skill/ability_skill_white_wolf_moon_fang"
        "$ability_skill_white_wolf_moon_fang")
SKILLS = M.SKILLS
BIND_PATH = (11, 1, 0, 1, 2, 1, 0, 1)


def _key(kind, key):
    return "|".join(key) if kind == "table" else key


def load():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    inputs = {kind: value for kind, value in data.items() if not kind.startswith("_")}
    return inputs, data["_context"], data["_dsl_raw_sha256"]


def reader(inputs):
    def read(kind, key):
        return inputs[kind][_key(kind, key)]
    return read


def cells_diff(old, new):
    return {c: (a, b) for c, (a, b) in enumerate(zip(old, new)) if a != b}


def tree_diff(old, new, path=()):
    """[(路径, 旧, 新)]：连类型一起比（2147483647.0 与 2147483647 视为不同）。"""
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        return [d for i, (a, b) in enumerate(zip(old, new)) for d in tree_diff(a, b, path + (i,))]
    if isinstance(old, dict) and isinstance(new, dict) and old.keys() == new.keys():
        return [d for k in old for d in tree_diff(old[k], new[k], path + (k,))]
    return [] if (type(old) is type(new) and old == new) else [(path, old, new)]


def strip_cast_growth(tree):
    """live 技能树 → cast_growth 之前的形态：去掉强化分支首两条（Bind + 时空侵蚀 +1），比例伤害回到 5%。"""
    result = deepcopy(tree)
    enhanced = M._at(result, BIND_PATH[:-4])[2]
    assert enhanced[1][0][1][0] == "BindConditionAccumulationVariable"
    assert enhanced[1][1][1][0] == "CreateCondition"
    del enhanced[1][0:2]
    strikes = [n for _p, n in M._walk(result) if n and n[0] == "CreateRatioAttack" and len(n[3]) == 2]
    assert len(strikes) == 1
    strikes[0][3] = [{"min": 0.05, "max": 0.05}]
    return result


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.context, cls.raw_sha = load()
        cls.out = M.revise(reader(deepcopy(cls.inputs)))
        cls.old_leader = cls.inputs["leader"][M.CID]
        cls.new_leader = cls.out["leader"][M.CID]
        cls.old_pf = cls.inputs["dsl"][M.PF_LV3]
        cls.new_pf = cls.out["dsl"][M.PF_LV3]

    # ------------------------------------------------------------ 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.inputs[kind][_key(kind, key)]), want, (kind, key))
        self.assertEqual({(kind, key) for kind, keys in self.inputs.items() for key in keys},
                         {(kind, _key(kind, key)) for kind, key in M.BEFORE})
        # 候选 PF Lv3 的已审漂移哈希 = live 原始字节哈希（候选文件与 live 同字节，只是 manifest 未重封）。
        (tier, logical), sha = next(iter(M.REVIEWED_DRIFT.items()))
        self.assertEqual((tier, logical), ("common", wf_dsl.dsl_logical(M.PF_LV3)))
        self.assertEqual(self.raw_sha[M.PF_LV3], sha)
        # 技能两档：live 原始字节 = 候选 manifest 封口（无漂移，不需要登记）。
        self.assertEqual([self.raw_sha[p][:8] for p in SKILLS], ["8d323968", "f27b8a14"])

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), ("149999", "white_wolf_gerald"))
        self.assertEqual(M.PACKAGES, ["white_wolf_gerald"])
        self.assertEqual(M.PACKAGE_VERSION, {"white_wolf_gerald": "0.20260927"})  # 候选现值 0.20260925
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(len(M.REVIEWED_DRIFT), 1)
        self.assertEqual(M.ELEMENT, 4)
        json.dumps(self.out["notes"], ensure_ascii=False)
        self.assertFalse(self.out["notes"]["runtime_verified"])
        self.assertIn("a5_skill_growth_remainder_to_leader", self.out["notes"]["blocked"])

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["leader"]), {M.CID})
        self.assertEqual(set(out["dsl"]), {M.PF_LV3, *SKILLS})
        for kind in ("ability", "cas", "text", "table", "action", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        # 月牙斩、PF Lv1/2 都不在输出里（口径 B.3 保留、B.2 只改 Lv3）。
        for program in (FANG, M.PF_BASE + "1", M.PF_BASE + "2"):
            self.assertNotIn(program, out["dsl"])

    # ------------------------------------------------------------ 队长（成长 + Down，同一键串行按行改）

    def test_leader_changes_exactly_eight_cells(self):
        self.assertEqual((len(self.old_leader), len(self.new_leader)), (12, 12))
        seen = {i: cells_diff(a, b) for i, (a, b) in enumerate(zip(self.old_leader, self.new_leader)) if a != b}
        self.assertEqual(seen, {
            6: {49: ("50000", "5000"), 50: ("50000", "5000")},
            7: {49: ("50000", "5000"), 50: ("50000", "5000")},
            8: {49: ("50000", "5000"), 50: ("50000", "5000")},
            9: {111: ("500000", "50000"), 112: ("500000", "50000")},
        })
        for i in (0, 1, 2, 3, 4, 5, 10, 11):          # 未改行逐字保留
            self.assertEqual(self.new_leader[i], self.old_leader[i], i)
        self.assertTrue(all(len(row) == 124 for row in self.new_leader))

    def test_growth_rows_keep_trigger_and_uncapped_shape(self):
        """行7–9：光编成≥6、全队直击每 50 次、限次 (None)、CT 0、全队(光)；只把强度放缓到 1/10。"""
        for i, kind in ((6, "32"), (7, "33"), (8, "388")):
            row = self.new_leader[i]
            self.assertEqual((row[4], row[7], row[8], row[9]), ("2", "600000", "600000", "White"))
            self.assertEqual((row[25], row[26], row[27], row[28], row[29]),
                             ("20", "7", "White", "5000000", "5000000"))
            self.assertEqual((row[32], row[33]), ("(None)", "0"))
            self.assertEqual((row[45], row[46], row[47]), (kind, "5", "White"))
            self.assertEqual((row[49], row[50]), ("5000", "5000"))
            self.assertEqual(int(self.old_leader[i][49]) // int(row[49]), 10)   # ≥30 次/3 分钟 ⇒ ×1/10
        freq = self.out["notes"]["growth_frequency"]
        self.assertIn("1/10", freq["tier"])
        self.assertIn("60–200", freq["estimate_3min"])        # 计入 PF Lv3 6 段后的现实范围
        self.assertIn("+300%–+1000%", freq["typical_before_after"])

    def test_fever_stunify_row_is_team_fifty_percent(self):
        """口径 B.4 全谱（瞬发 22/51/183/241、持续 19/120）：本键只有行10 一条，全队 50%。"""
        row = self.new_leader[9]
        self.assertEqual((row[3], row[95], row[106], row[107], row[108], row[109]),
                         ("1", "4", "false", "19", "5", "White"))
        self.assertEqual((row[111], row[112]), ("50000", "50000"))
        self.assertEqual(M.STUNIFY_INSTANT_KINDS, ("22", "51", "183", "241"))
        self.assertEqual(M.STUNIFY_DURING_KINDS, ("19", "120"))
        stunify = [r for r in self.new_leader
                   if (r[3] == "1" and r[107] in ("19", "120"))
                   or (r[3] == "0" and r[45] in ("22", "51", "183", "241"))]
        self.assertEqual(stunify, [row])
        self.assertEqual(M.stunify_rows(self.new_leader), [(9, "5", 50000)])
        self.assertEqual(M.stunify_rows(self.old_leader), [(9, "5", 500000)])
        self.assertEqual(M.stunify_problems(self.new_leader), [])
        self.assertEqual(len(M.stunify_problems(self.old_leader)), 1)

    def test_stunify_gate_covers_every_b4_kind(self):
        """自检门覆盖全部六个 kind：任何一个以 >50%（全队）/ >100%（自身）出现都要红。"""
        blank = [""] * 124
        for kind in M.STUNIFY_INSTANT_KINDS:
            row = blank[:3] + ["0"] + blank[4:]
            row[45], row[46], row[49], row[50] = kind, "5", "60000", "60000"
            self.assertEqual(len(M.stunify_problems([row])), 1, kind)
            row[46], row[49], row[50] = "0", "100000", "100000"
            self.assertEqual(M.stunify_problems([row]), [], kind)
            row[50] = "150000"
            self.assertEqual(len(M.stunify_problems([row])), 1, kind)
        for kind in M.STUNIFY_DURING_KINDS:
            row = blank[:3] + ["1"] + blank[4:]
            row[107], row[108], row[111], row[112] = kind, "5", "50000", "60000"
            self.assertEqual(len(M.stunify_problems([row])), 1, kind)
        # leader_rows 的自检门：把行10 目标值换成 60% 就必须拒绝（全队 ≤50%）。
        with mock.patch.object(M, "STUN_NEW", ("60000", "60000")):
            with self.assertRaisesRegex(AssertionError, "Stunify"):
                M.leader_rows(deepcopy(self.old_leader))

    def test_kept_leader_rows(self):
        new = self.new_leader
        self.assertEqual((new[5][45], new[5][28], new[5][49]), ("255", "3500000", "1500000"))  # 35 直击造伤
        self.assertEqual((new[3][25], new[3][33], new[3][45], new[3][49]), ("144", "150", "211", "5000"))  # 充能 CT 不动
        self.assertEqual((new[10][45], new[10][68]), ("629", "ability_skill_gerald_time_rift"))
        self.assertEqual((new[11][45], new[11][68]), ("536", "change_skill_white_wolf_gerald"))

    # ------------------------------------------------------------ PF Lv3

    def test_pf_lv3_p13_changes_only_the_time_seal_attack(self):
        old_attacks = M.pf_attacks(self.old_pf)
        new_attacks = M.pf_attacks(self.new_pf)
        self.assertEqual([p for p, _a, _h in old_attacks], [p for p, _a, _h in new_attacks])
        self.assertEqual([p[4] for p, _a, _h in new_attacks], [3, 4])
        self.assertEqual([a[13] for _p, a, _h in old_attacks], [[{"min": 3, "max": 3}]] * 2)
        self.assertEqual([a[13] for _p, a, _h in new_attacks],
                         [[{"min": 2.5, "max": 2.5}], [{"min": 3, "max": 3}]])
        self.assertEqual(tree_diff(self.old_pf, self.new_pf), [
            ((11, 1, 0, 1, 3, 1, 1, 1, 23, 1, 0, 1, 13, 0, "min"), 3, 2.5),
            ((11, 1, 0, 1, 3, 1, 1, 1, 23, 1, 0, 1, 13, 0, "max"), 3, 2.5),
        ])

    def test_pf_detoughness_tops_out_at_lv3_cap(self):
        self.assertEqual(M.pf_detoughness(self.old_pf), {3: 30, 4: 15})
        self.assertEqual(M.pf_detoughness(self.new_pf), {3: 25.0, 4: 15})
        notes = self.out["notes"]["pf_lv3_detoughness"]
        self.assertEqual((notes["time_seal_branch"], notes["no_seal_branch"]), ([30, 25.0], [15, 15]))

    def test_other_pf_levels_already_within_caps_and_untouched(self):
        for level, cap, want in ((1, 15, {3: 9.0, 4: 4.5}), (2, 20, {3: 16, 4: 8})):
            tree = self.context["dsl"][M.PF_BASE + str(level)]
            self.assertEqual(M.pf_detoughness(tree), want, level)
            self.assertLessEqual(max(want.values()), cap)
        self.assertEqual(self.inputs["table"][PF_KEY], [[M.PF_BASE + str(level) for level in (1, 2, 3)]])

    # ------------------------------------------------------------ 技能两档：时空侵蚀层数封顶（口径 A.5）

    def test_skill_bind_cap_is_the_only_change(self):
        for program in SKILLS:
            old, new = self.inputs["dsl"][program], self.out["dsl"][program]
            self.assertEqual(tree_diff(old, new), [(BIND_PATH + (5,), 2147483647.0, 10)], program)
            self.assertEqual(M._at(new, BIND_PATH),
                             ["BindConditionAccumulationVariable", -17, 360, ["DCUnique", 14999903], 1, 10])
            self.assertIs(type(M._at(new, BIND_PATH)[5]), int)

    def test_skill_ratio_growth_is_capped_at_ten_casts(self):
        """case 101：v360 = min(层数/1, 上限) ⇒ 比例伤害 5%+1%×min(n,10)，最多 15%（改前第 21 次 25%）。"""
        for program in SKILLS:
            old, new = self.inputs["dsl"][program], self.out["dsl"][program]
            for prior, before, after in ((0, .05, .05), (1, .06, .06), (9, .14, .14), (10, .15, .15),
                                         (20, .25, .15), (1000, 10.05, .15)):
                self.assertAlmostEqual(M.skill_ratio_at(old, prior), before, msg=(program, prior))
                self.assertAlmostEqual(M.skill_ratio_at(new, prior), after, msg=(program, prior))
        notes = self.out["notes"]["skill_cast_growth"]
        self.assertIn("15%", notes["before_after"])

    def test_skill_counter_shape_and_precedent(self):
        """Bind 在强化分支首条、后接时空侵蚀 +1；变量 360 只喂比例伤害；形态同官方 blackflower_wiz_smr22 Bind(…,1,10)。"""
        for program in SKILLS:
            new = self.out["dsl"][program]
            path, bind = M.skill_counter_bind(new)
            self.assertEqual(path, BIND_PATH)
            self.assertEqual(bind[:5], M.BIND_PREFIX)
            self.assertEqual(M._at(new, BIND_PATH[:-4])[:2], ["ConditionalsChangeSkillFlag", 1])
            self.assertEqual(M._at(new, BIND_PATH[:-2] + (1, 1)), M.COUNTER_INCREMENT)
            strikes = [n for _p, n in M._walk(new) if n and n[0] == "CreateRatioAttack"]
            self.assertEqual(strikes, [M.RATIO_STRIKE, ["CreateRatioAttack", 301, 1, [{"min": 1.0, "max": 1.0}]]])
        official = ["BindConditionAccumulationVariable", -17, 1, ["DCUnique", 11], 1, 10]
        self.assertEqual((official[4], official[5]), (M.BIND_PREFIX[4], M.SKILL_CAP_NEW))

    def test_dsl_gates_and_amf3_roundtrip(self):
        for program in (M.PF_LV3, *SKILLS):
            tree = self.out["dsl"][program]
            self.assertEqual(M.dsl_problems(tree), [], program)
            self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [], program)
            self.assertEqual(L.action_dsl_subject_binding_problems(tree), [], program)
            self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [], program)
            self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [], program)
            self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree, program)
            decoded = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))["tree"]
            self.assertEqual(tree_diff(tree, decoded), [], program)       # 连类型（int 10）一起往返
            self.assertEqual(M.dsl_problems(self.inputs["dsl"][program]), [], program)   # 输入本来就过门禁（对照）

    # ------------------------------------------------------------ 合法性 / 面板

    def test_every_returned_row_passes_client_gates(self):
        cas_keys = set(self.context["cas"])
        for i, row in enumerate(self.new_leader):
            self.assertEqual(L.client_legality_problems("leader_ability", row), [], i)
            self.assertEqual(L.declared_block_field_problems("leader_ability", row), [], i)
            self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, "leader_ability"), [], i)
            self.assertEqual(L.required_client_capabilities("leader_ability", row), [], i)
            self.assertEqual(KL.row_problems("leader_ability", row), {}, i)
            self.assertEqual(M.row_problems(row, cas_keys), [], i)

    def test_leader_panel_is_auto_generated_and_obeys_panel_rules(self):
        self.assertIn("desc_override_black_wolf_knight", self.context["cas_absent"])
        self.assertEqual(M.LEADER_NAME, self.new_leader[0][0])
        lines = D.describe_rows(self.new_leader, "leader_ability")
        self.assertEqual(lines[6], "光·编成≥6 时: 编成直接攻击≥50 → 赋予全队(光) 攻击力 5%")
        self.assertEqual(lines[7], "光·编成≥6 时: 编成直接攻击≥50 → 赋予全队(光) Direct伤害 5%")
        self.assertEqual(lines[8], "光·编成≥6 时: 编成直接攻击≥50 → 赋予全队(光) 能力伤害 5%")
        self.assertEqual(lines[9], "持续·Fever → 赋予全队(光) 眩晕蓄积 50%")
        for line in lines:
            self.assertEqual(KL.panel_problems(line), [], line)
        old = D.describe_rows(self.old_leader, "leader_ability")
        self.assertEqual(old[9], "持续·Fever → 赋予全队(光) 眩晕蓄积 500%")
        self.assertEqual([a for a, b in zip(old, lines) if a != b], old[6:10])

    def test_texts_do_not_carry_the_changed_numbers(self):
        """技能描述 / 角色文本 / 服务端文本 / 技能强化与 PF 覆盖串 / 629 字串都没有本次改动的数值 ⇒ 不需要同步文案。"""
        texts = [row[0] for rows in self.context["cas"].values() for row in rows]
        texts += [fields[1] for _k, fields in self.context["action"][M.CODE]]
        texts += [cell for row in self.context["text"][M.CID] for cell in row]
        texts += [cell for row in self.context["server_text"][M.CID] for cell in row]
        for text in texts:
            for word in ("500%", "50%", "15%", "25%", "眩晕", "Down", "削韧", "生命值", "层", "无上限", "无限"):
                self.assertNotIn(word, text)
        self.assertEqual(self.context["cas"]["change_skill_white_wolf_gerald"],
                         [["强化自身技能效果，额外造成一定固定伤害。"]])
        # 作者 09-27 追加（wf_balance_20260927b_gerald2）：生成器文案改为无数字的「固定伤害 + 斩杀」版。
        import wf_balance_20260927b_gerald2 as M2
        self.assertEqual(self.context["cas"]["change_skill_white_wolf_gerald"][0][0], M2.OLD_CAS_TEXT)
        # 第三轮（wf_balance_20260927c_gerald_wolf）：以 gerald2 文案为输入点明技能名，生成器常量跟第三轮走。
        import wf_balance_20260927c_gerald_wolf as M3
        self.assertEqual(M3.OLD_CAS_FLAG_TEXT, M2.NEW_CAS_TEXT)
        self.assertEqual(G.ENHANCEMENT_TEXT, M3.NEW_CAS_FLAG_TEXT)

    # ------------------------------------------------------------ 保留项现值（口径 B.1 / B.3）

    def test_kept_skill_and_fang_values(self):
        actions = self.context["action"][M.CODE]
        self.assertEqual([(k, f[4], f[5]) for k, f in actions], [("1", "1500", "1500"), ("2", "1500", "1500")])
        self.assertLessEqual(73.5 * 550 / 1500, 30)
        fang = self.context["dsl"][FANG]
        attacks = M.pf_attacks(fang)
        self.assertEqual([a[13] for _p, a, _h in attacks],
                         [[{"min": 2.5, "max": 2.5}], [{"min": 0.25, "max": 0.25}]])
        self.assertEqual(attacks[0][0], (11, 1, 1, 1, 3, 1, 0, 1, 23, 1, 0, 1))   # open_points 里给的备选改点
        # 第一段：寿命 12 帧 < 最小命中间隔 60 帧 ⇒ 1 段；第二段 4 段 ⇒ 2.5 + 1.0 = 3.5
        self.assertEqual((attacks[0][2][13], attacks[0][2][14]),
                         (["SpecifyHitAreaLifetimeDirectly", 12], ["SpecifyMinHitIntervalDirectly", 60]))
        self.assertEqual(attacks[1][2][14], ["CalculatedUsingMaxNumOfHits", 4])
        self.assertAlmostEqual(2.5 * 1 + 0.25 * 4, 3.5)
        row = self.context["ability"]["1499993"][5]
        self.assertEqual((row[27], row[30], row[35], row[47], row[70]),
                         ("6", "1000000", "0", "629", "ability_skill_white_wolf_moon_fang"))
        # 技能削韧不动（口径 B.1 保留）：两档所有 CreateNormalAttack p13 与输入一致。
        for program in SKILLS:
            self.assertEqual([a[13] for _p, a, _h in M.pf_attacks(self.out["dsl"][program])],
                             [a[13] for _p, a, _h in M.pf_attacks(self.inputs["dsl"][program])])

    # ------------------------------------------------------------ fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.inputs)
        out = M.revise(reader(data))
        self.assertEqual(json.dumps(data, sort_keys=True), json.dumps(self.inputs, sort_keys=True))
        out["leader"][M.CID][6][49] = "mutated"
        M._at(out["dsl"][M.PF_LV3], M.pf_attacks(out["dsl"][M.PF_LV3])[0][0])[13] = "mutated"
        M._at(out["dsl"][SKILLS[0]], BIND_PATH)[5] = "mutated"
        self.assertEqual(json.dumps(data, sort_keys=True), json.dumps(self.inputs, sort_keys=True))

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.inputs)
            value = drifted[kind][_key(kind, key)]
            if kind == "dsl":
                value[10] = 4
            else:
                value[-1][-1] = value[-1][-1] + "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(drifted))
            missing = deepcopy(self.inputs)
            missing[kind][_key(kind, key)] = None
            with self.assertRaises(ValueError):
                M.revise(reader(missing))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        live = deepcopy(self.inputs)
        live["leader"].update(deepcopy(self.out["leader"]))
        live["dsl"].update(deepcopy(self.out["dsl"]))
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(live))
        with self.assertRaises(ValueError):
            M.leader_rows(self.new_leader)
        with self.assertRaises(ValueError):
            M.pf_lv3_tree(self.new_pf)
        for program in SKILLS:
            with self.assertRaisesRegex(ValueError, "Bind preimage"):
                M.skill_tree(self.out["dsl"][program])
        # 只有成长批已上、Down 批未上（或反过来）的半截状态也要拒绝。
        half = deepcopy(self.old_leader)
        half[9] = deepcopy(self.new_leader[9])
        with self.assertRaises(ValueError):
            M.leader_rows(half)
        half = deepcopy(self.new_leader)
        half[9] = deepcopy(self.old_leader[9])
        with self.assertRaises(ValueError):
            M.leader_rows(half)

    def test_row_locators_are_content_based(self):
        old = deepcopy(self.old_leader)
        moved = old[:6] + [old[7], old[6]] + old[8:]
        with self.assertRaises(ValueError):
            M.leader_rows(moved)
        kept = deepcopy(old)
        kept[5][49] = kept[5][50] = "1000000"            # 保留行被改也要红
        with self.assertRaises(ValueError):
            M.leader_rows(kept)
        capped = deepcopy(old)
        capped[7][32] = "10"                              # 有上限就不是本条无上限成长
        with self.assertRaises(ValueError):
            M.leader_rows(capped)
        with self.assertRaises(ValueError):
            M.leader_rows(old[:11])
        tree = deepcopy(self.old_pf)
        M._at(tree, M.pf_attacks(tree)[1][0])[13] = [{"min": 2, "max": 2}]
        with self.assertRaises(ValueError):
            M.pf_lv3_tree(tree)
        tree = deepcopy(self.old_pf)
        tree[11][1][0][1][1] = ["DCUnique", 1]            # 时之刻印分支漂移
        with self.assertRaises(ValueError):
            M.pf_lv3_tree(tree)

    def test_skill_locators_are_content_based(self):
        base = self.inputs["dsl"][SKILLS[0]]
        cases = []
        t = deepcopy(base); M._at(t, BIND_PATH)[2] = 361; cases.append(t)                 # 变量号漂移
        t = deepcopy(base); M._at(t, BIND_PATH)[3] = ["DCUnique", 1]; cases.append(t)    # 计数固有漂移
        t = deepcopy(base); M._at(t, BIND_PATH)[4] = 2; cases.append(t)                  # 除数漂移
        t = deepcopy(base); M._at(t, BIND_PATH)[5] = 20; cases.append(t)                 # 已有别的上限
        t = deepcopy(base); M._at(t, BIND_PATH[:-2] + (1, 1))[7] = "other"; cases.append(t)   # +1 漂移
        t = deepcopy(base); t[11][1].append(deepcopy(M._at(base, BIND_PATH[:-1]))); cases.append(t)  # 第二个 Bind
        t = deepcopy(base)
        strike = [n for _p, n in M._walk(t) if n and n[0] == "CreateRatioAttack" and len(n[3]) == 2][0]
        strike[3][1]["min"] = strike[3][1]["max"] = 0.02; cases.append(t)                # 每层增量漂移
        t = deepcopy(base); M._at(t, BIND_PATH[:-4])[1] = 2; cases.append(t)             # 不再是强化分支
        for i, tree in enumerate(cases):
            with self.assertRaises(ValueError, msg=i):
                M.skill_tree(tree)

    def test_power_flip_action_pointer_is_checked(self):
        data = deepcopy(self.inputs)
        data["table"][PF_KEY] = [[M.PF_BASE + "1", M.PF_BASE + "2", M.PF_BASE + "2"]]
        with mock.patch.dict(M.BEFORE, {("table", M.PF_ACTION): M.digest(data["table"][PF_KEY])}):
            with self.assertRaisesRegex(ValueError, "power_flip_action"):
                M.revise(reader(data))


class GeneratorTests(unittest.TestCase):
    """生成器同步：cast_growth.rewrite 输出 == revise() 输出；三个杰拉德生成器重跑都不会回退本次改动。"""

    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.context, _ = load()
        cls.out = M.revise(reader(deepcopy(cls.inputs)))
        cls.leader = cls.out["leader"][M.CID]

    def test_cast_growth_constants_match_the_revision(self):
        # 作者 09-27 追加撤回封顶（wf_balance_20260927b_gerald2）：生成器上限回到第二批改前的 2147483647.0。
        self.assertEqual((G.COUNTER_UID, G.COUNTER_VARIABLE, G.COUNTER_CAP),
                         (M.COUNTER_UID, M.COUNTER_VARIABLE, M.SKILL_CAP_OLD))
        self.assertIs(type(G.COUNTER_CAP), float)
        self.assertEqual(G.CONDITION_KEY, M.COUNTER_KEY)
        self.assertEqual(G.counter_row()[0][:5],
                         [M.COUNTER_KEY, "时空侵蚀", "battle/common/unique_condition/unique_gerald_time_seal",
                          "99999999", "2147483647"])        # 固有上限不动（只封 DSL 读数）

    def test_cast_growth_rewrite_equals_revise_output(self):
        """去掉 live 的施技成长两条命令、比例回到 5% 后重跑 rewrite()：作者 09-27 追加撤回封顶后，生成器输出 ==
        第二批改前（本 fixture 输入），与第二批输出只差 Bind 上限一格（不需要本机捕获）。"""
        for program in SKILLS:
            pre = strip_cast_growth(self.inputs["dsl"][program])
            self.assertEqual(tree_diff(G.rewrite(pre), self.inputs["dsl"][program]), [], program)
            self.assertEqual(tree_diff(G.rewrite(pre), self.out["dsl"][program]),
                             [(BIND_PATH + (5,), 2147483647.0, 10)], program)

    @unittest.skipUnless(CAPTURED_0925.is_dir(), "local 2026-09-25 captured live resources required")
    def test_cast_growth_rewrite_on_captured_input_equals_revise_output(self):
        """cast_growth 的真实输入（09-25 修订前捕获）：作者 09-27 追加撤回封顶后 rewrite() == 第二批改前
        （本 fixture 输入），连类型一致。"""
        for level, program in zip((1, 2), SKILLS):
            raw = (CAPTURED_0925 / P.ACTIVE_PATHS[level]).read_bytes()
            captured = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
            self.assertEqual(tree_diff(G.rewrite(captured), self.inputs["dsl"][program]), [], program)
            self.assertEqual(strip_cast_growth(self.inputs["dsl"][program]), captured)

    def test_cast_growth_rewrite_refuses_revised_trees(self):
        for program in SKILLS:
            # 已带 mul 的比例伤害先撞「ratio baseline changed」，再后面还有「existing variable binding」闸。
            with self.assertRaisesRegex(ValueError, "ratio baseline changed|unexpected existing variable binding"):
                G.rewrite(self.out["dsl"][program])
        with self.assertRaises(ValueError):
            G.rewrite(self.out["dsl"][M.PF_LV3])          # 需要唯一的 ConditionalsChangeSkillFlag(1)

    def test_cast_growth_relocate_does_not_touch_existing_leader_rows(self):
        """relocate 只把时空裂痕/技能强化两行从能力2/3 追加到队长末尾，已有的行（含本次改的 #6–#9）原样透传。"""
        rift, flag = self.leader[10], self.leader[11]
        a2 = [["black_wolf_knight_2", "false", "attack_red", "0", ""] + rift[3:]]
        a3 = [["black_wolf_knight_3", "false", "attack_red", "0", ""] + flag[3:]]
        self.assertEqual((len(a2[0]), len(a3[0])), (126, 126))
        existing = deepcopy(self.leader[:10])
        _a2, _a3, leaders = G.relocate(a2, a3, existing)
        self.assertEqual((_a2, _a3), ([], []))
        self.assertEqual(leaders[:10], self.leader[:10])
        self.assertEqual(existing, self.leader[:10])
        self.assertEqual(leaders, self.leader)

    def test_generator_sources_write_none_of_the_revised_cells(self):
        """源码层：三个生成器不含队长 c49/c50/c111/c112、PF 树、p13 的写点；percent 两个也不碰 Bind 上限。"""
        for module in (G, P, PR):
            source = Path(module.__file__).read_text(encoding="utf-8")
            tree = ast.parse(source)
            for word in ("leader_ability", "power_flip", "pf_lv", "500000", "50000"):
                self.assertNotIn(word, source, (module.__name__, word))
            subscripts = {node.slice.value for node in ast.walk(tree)
                          if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant)
                          and isinstance(node.slice.value, int)}
            self.assertFalse(subscripts & {13, 49, 50, 111, 112}, module.__name__)
        for module in (P, PR):
            self.assertNotIn("BindConditionAccumulationVariable", Path(module.__file__).read_text(encoding="utf-8"))

    def test_percent_generators_are_fail_closed_on_current_and_revised_skills(self):
        """patch_skill_bytes 按旧源 sha256 锁定：对当前 live 与修订后技能重跑都直接拒绝，不会覆盖任何东西。"""
        for level, program in zip((1, 2), SKILLS):
            for tree in (self.inputs["dsl"][program], self.out["dsl"][program]):
                with self.assertRaises(ValueError):
                    P.patch_skill_bytes(encode_tree(tree), level)
            with self.assertRaises(ValueError):
                P.rewrite_skill(self.out["dsl"][program])  # 旧的碰撞比例命令已不存在
        with self.assertRaises(ValueError):
            P.rewrite_skill(self.out["dsl"][M.PF_LV3])
        self.assertEqual(set(P.ACTIVE_PATHS.values()), {wf_dsl.dsl_logical(program) for program in SKILLS})
        self.assertEqual(PR.STRING_KEY, "change_skill_white_wolf_gerald")


@unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                     and (ROOT / "mod-tools/profiles.json").is_file(),
                     "local candidate workspace required")
class CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.context, _ = load()
        cls.out = M.revise(reader(deepcopy(cls.inputs)))

    def _kwargs(self):
        return dict(character_id=M.CID, code_name=M.CODE, snapshot_key="revision_20260927b",
                    package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                    baseline_factory=lambda *a, **k: None)

    def _tree(self, candidate, program):
        raw = candidate.read("common", wf_dsl.dsl_logical(program))
        return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]

    def test_candidate_accepts_only_the_reviewed_pf_drift_and_splices_dry(self):
        import wf_share_update_codec as X
        from wf_character_revision import RevisionCandidate
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        current = json.loads(before)["package_version"]
        # 作者 09-27 追加（wf_balance_20260927b_gerald2 撤回技能封顶）回写后版本会再升一档。
        import wf_balance_20260927b_gerald2 as M2
        version = lambda text: tuple(map(int, text.split(".")))
        appended = version(current) >= version(M2.PACKAGE_VERSION[M2.PACKAGES[0]])
        if not appended:
            self.assertGreaterEqual(version(M.PACKAGE_VERSION[M.PACKAGES[0]]), version(current))
        programs = (M.PF_LV3, *SKILLS)
        if json.loads(before).get("snapshot", {}).get("revision_20260927b") is not None:
            # 回写后：Lv3 与技能两档已重新封口，候选与本次输出一致；gerald2 回写后技能两档回到第二批改前（不封顶）。
            if not appended:
                self.assertEqual(M.PACKAGE_VERSION[M.PACKAGES[0]], current)
            candidate = RevisionCandidate(ROOT, WORKSPACE, **self._kwargs())
            leader = X.unpack(candidate.read("common", "master/ability/leader_ability.orderedmap"))
            # 第三轮（wf_balance_20260927c_gerald_wolf，以本模块输出为输入把 #6–#8 5%→40%）回写后候选 = 第三轮输出。
            import wf_balance_20260927c_gerald_wolf as M3
            want_leader = self.out["leader"][M.CID]
            if version(current) >= version(M3.PACKAGE_VERSION[M3.PACKAGES[0]]):
                want_leader = M3.leader_rows(want_leader)
            self.assertEqual(X.csv_read(leader[M.CID]), want_leader)
            for program in programs:
                want = self.inputs["dsl"][program] if appended and program in SKILLS else self.out["dsl"][program]
                self.assertEqual(tree_diff(self._tree(candidate, program), want), [], program)
            self.assertEqual(before, manifest.read_bytes())
            return
        with self.assertRaisesRegex(ValueError, "candidate drift"):
            RevisionCandidate(ROOT, WORKSPACE, **self._kwargs())
        candidate = RevisionCandidate(ROOT, WORKSPACE, reviewed_input_drift=M.REVIEWED_DRIFT, **self._kwargs())
        # 候选里这些输入与 live 快照一致（PF Lv3 只有 manifest 封口滞后；技能两档连封口都一致）。
        leader = X.unpack(candidate.read("common", "master/ability/leader_ability.orderedmap"))
        self.assertEqual(X.csv_read(leader[M.CID]), self.inputs["leader"][M.CID])
        for program in programs:
            self.assertEqual(tree_diff(self._tree(candidate, program), self.inputs["dsl"][program]), [], program)
        candidate.splice("master/ability/leader_ability.orderedmap", self.out["leader"])
        for program in programs:
            candidate.emit("common", wf_dsl.dsl_logical(program), encode_tree(self.out["dsl"][program]))
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertEqual(sorted(f["logical_path"] for f in evidence["changed_files"]),
                         sorted(["master/ability/leader_ability.orderedmap",
                                 *(wf_dsl.dsl_logical(program) for program in programs)]))
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
