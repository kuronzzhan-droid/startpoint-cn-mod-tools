# -*- coding: utf-8 -*-
"""泽赫尔 159997 · 2026-09-27 平衡第三轮（成长复核）修订模块回归。

fixture = live 1.4.1053 只读快照（= 第二批产物，与候选 s7-zehr 1.0.8 逐字相同）。逐项断言：队长 #3 #4 #6 #7 #8
强度改到表值（35% / 25% / 2% / 20% / 20%）且按口径取整、其余格与其余 4 行逐字保留、队长覆盖文案四处数字
与行同源且其余 4 行逐字保留、能力 1/3 封顶版与其覆盖文案不动（D4）、BEFORE 漂移拒绝、不改输入、对自身输出
重跑拒绝、合法性与面板门禁为空，以及生成器「kit 回放 → 09-17 灯火修订 → 第二批 → 第三轮」== revise()。
面板同条件合并（能力6 两行 → 一行，kind 55 战斗级不补「自身」）：合并行逐字、数据条件逐格相同、各面板同条件组按数据重算、
``wf_panel_merge_check`` 通过（仓库内校验器，硬依赖）、共鸣省略依据（灯火正旺 / 灯芯）；主会话口径 1（kind 55 不补对象、
与前一个带对象的效果用「，」隔开；追加 A 扩到同形写法 ⇒ 队长 L1 / L7「、强化弹射伤害」改「，」，数据依据逐格核对）
与口径 3（返回面板无「X属性共鸣时：」）核对。
fixture 的 ``context_reads``（能力1–5 行、能力1/2/3 覆盖串）不进 BEFORE，只用来核对合并/共鸣依据。
"""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
import math
from pathlib import Path
import re
import sys
import unittest
from unittest import mock

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_zehr as B  # noqa: E402
import wf_balance_20260927c_zehr as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_panel_merge_check as PMC  # noqa: E402   面板合并校验器（仓库内，硬依赖）
import wf_seasonal7_kit_zehr as K  # noqa: E402
import wf_zehr_lamp_revision as R  # noqa: E402

HERE = Path(__file__).resolve().parent
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_zehr.json'
FIXTURE_B = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_zehr.json'
#: 队长表效果列（instant c45–c50 / during c107–c112），与能力表 M.ABILITY_EFFECT_COLUMNS 同义。
LEADER_EFFECT_COLUMNS = frozenset(range(45, 51)) | frozenset(range(107, 113))
A6_TEXT_AFTER = "光属性共鸣时，光属性角色技能充能速度＋15%，强化弹射伤害＋50%"

LEADER_TEXT_AFTER = "\n".join((
    "光属性共鸣时，光属性角色攻击力＋400%，强化弹射伤害＋200%",
    "赋予专属强化弹射：剑士型与辅助型同时生效，回旋斩持续时间延长、单击威力提升",
    "每达成35连击，强化弹射伤害＋35%",
    "每发动强化弹射，光属性角色攻击力＋25%",
    "光属性共鸣时，每发动3次强化弹射，接下来6次弹射各追加9连击",
    "每1层「灯芯」，强化弹射伤害额外乘区＋2%",
    "光属性共鸣时，每获得1次「灯火正旺」，光属性角色攻击力＋20%，强化弹射伤害＋20%（CT 5s）",
    "改变冲刺方向：朝点击侧斜下方冲刺，保留头目弱点与传送舱锁定",
))


def _load(path):
    fx = json.loads(path.read_text(encoding="utf-8"))
    return {(kind, tuple(key) if isinstance(key, list) else key): value for kind, key, value in fx["reads"]}, fx


def load():
    return _load(FIXTURE)[0]


def load_context():
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {(kind, key): value for kind, key, value in fx["context_reads"]}


def same_condition_groups(rows, effect_columns):
    """除效果列外逐格相同的行组（≥2 行）。"""
    groups = {}
    for index, row in enumerate(rows):
        groups.setdefault(tuple(v for c, v in enumerate(row) if c not in effect_columns), []).append(index)
    return [tuple(v) for v in groups.values() if len(v) > 1]


def reader(data):
    return lambda kind, key: data[kind, key]


def diff_cells(a, b):
    return {i: (x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y}


def pct(value: str) -> str:
    return f"{int(value) / 1000:g}%"


class ReviseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.out = M.revise(reader(cls.data))

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(set(self.data), set(M.BEFORE))
        for key, want in M.BEFORE.items():
            self.assertEqual(M.digest(self.data[key]), want, key)

    def test_input_is_the_batch2_output(self):
        b_out = B.revise(reader(_load(FIXTURE_B)[0]))
        self.assertEqual(b_out["leader"][M.CID], self.data["leader", M.CID])
        self.assertEqual(b_out["cas"][M.CAS_LEADER], self.data["cas", M.CAS_LEADER])

    def test_only_the_five_growth_rows_change(self):
        before, after = self.live("leader", M.CID), self.out["leader"][M.CID]
        self.assertEqual((9, 9), (len(before), len(after)))
        want = {3: {49: ("5000", "35000"), 50: ("5000", "35000")},
                4: {49: ("3500", "25000"), 50: ("3500", "25000")},
                6: {111: ("500", "2000"), 112: ("500", "2000")},
                7: {49: ("6000", "20000"), 50: ("6000", "20000")},
                8: {49: ("6000", "20000"), 50: ("6000", "20000")}}
        for i, (old, new) in enumerate(zip(before, after)):
            self.assertEqual(diff_cells(old, new), want.get(i, {}), i)
        self.assertEqual((after[3][4], after[4][4], after[6][4]), ("0", "0", "0"))   # D3：不新增共鸣前置
        self.assertEqual((after[7][33], after[8][33]), ("300", "300"))               # CT 5 秒不变
        self.assertEqual(after[6][100], "(None)")                                    # 灯芯行不限次

    def test_values_follow_the_rounding_rules(self):
        after = self.out["leader"][M.CID]
        for i, (_label, orig, b2, _tier, new) in M.GROWTH.items():
            col = M.C_VALUES[i][0][0]
            self.assertEqual(int(after[i][col]), new * 1000, i)
            self.assertGreaterEqual(new, orig * 2 / 3 - 1e-9, i)        # 不低于 2/3 下限
            self.assertLessEqual(new, orig * 4 / 5 + 1e-9, i)
            self.assertGreater(new, b2, i)
            if orig >= 20:
                self.assertEqual(new % 5, 0, i)                          # ≥20% 取 5 的倍数
        self.assertEqual((35, 25), tuple(math.ceil(orig * 2 / 3 / 5) * 5 for orig in (50, 35)))  # 2/3 向上取 5 的倍数
        self.assertEqual(2.0, round(3 * 7 / 10 * 2) / 2)                  # <10% 按 0.5 取整
        self.assertEqual(20, round(30 * 7 / 10 / 5) * 5)                  # 7/10 就近取 5 的倍数

    def test_describe_after(self):
        rows = self.out["leader"][M.CID]
        self.assertEqual({i: D.describe_line(rows[i], "leader_ability") for i in M.DESCRIBE_AFTER}, M.DESCRIBE_AFTER)

    def test_leader_text_exact_and_other_lines_kept(self):
        self.assertEqual(self.out["cas"][M.CAS_LEADER], [[LEADER_TEXT_AFTER]])
        old = self.live("cas", M.CAS_LEADER)[0][0].split("\n")
        new = LEADER_TEXT_AFTER.split("\n")
        self.assertEqual(len(old), len(new))
        changed = {i for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(changed, {0, 2, 3, 5, 6})                                # L1 只改分隔符（口径 1）
        self.assertEqual([(old[i], new[i]) for i in sorted(changed)], list(M.LEADER_TEXT_REWRITES))

    def test_panel_numbers_match_rows(self):
        leader = self.out["leader"][M.CID]
        self.assertIn(f"每达成35连击，强化弹射伤害＋{pct(leader[3][50])}", LEADER_TEXT_AFTER)
        self.assertIn(f"每发动强化弹射，光属性角色攻击力＋{pct(leader[4][50])}", LEADER_TEXT_AFTER)
        self.assertIn(f"额外乘区＋{pct(leader[6][112])}", LEADER_TEXT_AFTER)
        self.assertIn(f"光属性角色攻击力＋{pct(leader[0][50])}，强化弹射伤害＋{pct(leader[1][50])}", LEADER_TEXT_AFTER)
        self.assertIn(f"光属性角色攻击力＋{pct(leader[7][50])}，强化弹射伤害＋{pct(leader[8][50])}（CT 5s）",
                      LEADER_TEXT_AFTER)

    def test_panel_rules(self):
        text = self.out["cas"][M.CAS_LEADER][0][0]
        self.assertEqual(B.panel_problems({M.CAS_LEADER: text}), [])
        self.assertEqual(KL.panel_problems(text), [])
        self.assertEqual(K.panel_text_problems(text), [])
        self.assertNotIn("／", text)
        self.assertNotIn("icon", text)
        for word in ("可无限", "无上限", "自身为队长时", "觉醒后", "生命值100%以下", "最多99层"):
            self.assertNotIn(word, text)

    def test_row_legality_and_kit_gates(self):
        for row in self.out["leader"][M.CID]:
            self.assertEqual(L.client_legality_problems("leader_ability", row), [], row)
            self.assertEqual(L.declared_block_field_problems("leader_ability", row), [], row)
            self.assertEqual(L.invoke_skill_string_problems(row, B.STRINGS, "leader_ability"), [], row)
            self.assertEqual(L.ability_element_column_problems("leader_ability", row, M.ELEMENT), [], row)
            self.assertEqual(K.trigger_limit_problems("leader_ability", row), [], row)
        self.assertEqual(M.problems(self.out["leader"][M.CID], self.out["cas"][M.CAS_LEADER][0][0]), [])

    def test_no_new_client_capabilities(self):
        self.assertEqual(B.capability_set("leader_ability", self.out["leader"][M.CID]),
                         B.capability_set("leader_ability", self.live("leader", M.CID)))
        self.assertEqual(L.panel_override_capability(M.CAS_LEADER), "panel-description-override-v2")

    def test_only_changed_keys_are_returned(self):
        self.assertEqual(set(self.out["leader"]), {M.CID})
        self.assertEqual(set(self.out["cas"]), {M.CAS_LEADER, M.CAS_A6})        # 能力 1/3 覆盖文案不动（D4）；能力6 合并
        for kind in ("ability", "text", "table", "action", "dsl", "server_text", "new_programs"):
            self.assertFalse(self.out[kind], kind)                              # 能力 1/3 封顶版不动（D4）
        self.assertEqual((M.PACKAGES, M.PACKAGE_VERSION, M.CAPABILITIES, M.REVIEWED_DRIFT),
                         (["s7-zehr"], {"s7-zehr": "1.0.9"}, [], {}))
        self.assertEqual((M.CID, M.CODE), (B.CID, B.CODE))
        self.assertIs(self.out["notes"]["runtime_verified"], False)
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_baseline_drift_is_rejected_and_inputs_are_not_mutated(self):
        saved = deepcopy(self.data)
        M.revise(reader(self.data))
        self.assertEqual(self.data, saved)
        for kind, key in M.BEFORE:
            data = deepcopy(self.data)
            data[kind, key][0][0] += "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))

    def test_rerun_on_own_output_is_rejected_but_transforms_are_idempotent(self):
        data = deepcopy(self.data)
        data["leader", M.CID] = self.out["leader"][M.CID]
        data["cas", M.CAS_LEADER] = self.out["cas"][M.CAS_LEADER]
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(data))
        self.assertEqual(M.leader_rows(self.out["leader"][M.CID]), self.out["leader"][M.CID])
        self.assertEqual(M.leader_text(LEADER_TEXT_AFTER), LEADER_TEXT_AFTER)
        self.assertEqual(M.ability6_text(A6_TEXT_AFTER), A6_TEXT_AFTER)
        data = deepcopy(self.data)
        data["cas", M.CAS_A6] = self.out["cas"][M.CAS_A6]
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(data))

    def test_unreviewed_shapes_are_rejected(self):
        for index, col, value in ((3, 28, "3000000"), (4, 49, "3000"), (6, 102, "159997"),
                                  (7, 33, "0"), (8, 45, "32")):
            rows = self.live("leader", M.CID)
            rows[index][col] = value
            with self.assertRaises(ValueError, msg=(index, col)):
                M.leader_rows(rows)
        with self.assertRaises(ValueError):
            M.leader_rows(self.live("leader", M.CID)[:6])                         # 第二批之前的 6 行形态
        text = self.live("cas", M.CAS_LEADER)[0][0]
        with self.assertRaises(ValueError):
            M.leader_text(text.replace("＋3.5%", "＋4%"))
        with self.assertRaises(ValueError):
            M.leader_text(text + "\n多一行")


class PanelMergeTest(unittest.TestCase):
    """能力6 面板同条件合并与共鸣省略依据；按本轮数据重核扫描 panel_merge/scan.json。"""

    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.context = load_context()
        cls.out = M.revise(reader(cls.data))

    def test_merged_line_verbatim(self):
        self.assertEqual(self.data["cas", M.CAS_A6],
                         [["光属性共鸣时，光属性角色技能充能速度＋15%\n光属性共鸣时，强化弹射伤害＋50%"]])
        self.assertEqual(self.out["cas"][M.CAS_A6], [[A6_TEXT_AFTER]])
        # 条件只写一次；两个效果原措辞与数值逐字保留、用「，」分开；第二效果不补对象（kind 55 战斗级，R6）。
        effects = [line.removeprefix("光属性共鸣时，") for line in M.OLD_A6_LINES]
        self.assertEqual(M.NEW_A6_LINES, ("光属性共鸣时，" + "，".join(effects),))
        self.assertNotIn(M.FORBIDDEN_SELF_PF, A6_TEXT_AFTER)
        self.assertEqual(M.PANEL_MERGES, {M.CAS_A6: (M.A6, (0, 1), (0, 1), M.OLD_A6_LINES, M.NEW_A6_LINES)})
        self.assertEqual(M.PREFIX_DROPS, {})

    def test_merge_group_is_one_data_condition(self):
        rows = self.data["ability", M.A6]
        self.assertEqual(M.ability6_rows_problems(rows), [])
        diff = {c for c, (a, b) in enumerate(zip(rows[0], rows[1])) if a != b}
        self.assertEqual(diff, {2, 47, 48, 49, 51, 52})                     # 只有分类与效果列不同
        self.assertLessEqual(diff, M.ABILITY_EFFECT_COLUMNS)
        self.assertEqual([D.describe_line(r, "ability") for r in rows],
                         ["光·编成≥6 时: 赋予全队(光) 技能槽充能 15%", "光·编成≥6 时: 自身 强化弹射伤害 50%"])
        self.assertEqual((rows[1][47], rows[1][48]), ("55", ""))            # kind 55、target 空（战斗级，不读 target）
        self.assertEqual(re.findall(r"＋(\d+)%", A6_TEXT_AFTER),
                         [str(int(rows[0][51]) // 1000), str(int(rows[1][51]) // 1000)])   # 数字 == 行值

    def test_other_same_condition_groups_are_already_one_line_or_skipped(self):
        abilities = {key: rows for (kind, key), rows in self.context.items() if kind == "ability"}
        abilities[M.A6] = self.data["ability", M.A6]
        self.assertEqual(sorted(abilities), [f"{M.CID}{n}" for n in range(1, 7)])
        got = {key: same_condition_groups(rows, M.ABILITY_EFFECT_COLUMNS) for key, rows in abilities.items()}
        got["leader"] = same_condition_groups(self.out["leader"][M.CID], LEADER_EFFECT_COLUMNS)
        self.assertEqual(got, {"leader": [(0, 1), (7, 8)], "1599971": [], "1599972": [(0, 1)],
                               "1599973": [], "1599974": [], "1599975": [], "1599976": [(0, 1)]})
        # 只差内容参数列的两对（扫描签名算同条件）：能力1 #2/#3 只差 c68 授予的固有 id（灯火正旺 / 灯芯，已是 L3）；
        # 能力3 #1/#2 只差 during 422 冲刺参数（c113/c114/c118，不在面板上）。
        pairs = {(f"{M.CID}1", 2, 3): {68}, (f"{M.CID}3", 1, 2): {113, 114, 118}}
        for (key, a, b), cols in pairs.items():
            rows = abilities[key]
            self.assertEqual({c for c, (x, y) in enumerate(zip(rows[a], rows[b])) if x != y}, cols, key)
        leader = LEADER_TEXT_AFTER.split("\n")
        self.assertEqual(leader[0], "光属性共鸣时，光属性角色攻击力＋400%，强化弹射伤害＋200%")          # #0/#1 已是 L1
        self.assertIn("光属性角色攻击力＋20%，强化弹射伤害＋20%", leader[6])                     # #7/#8 已是 L7
        a1 = self.context["cas", f"desc_override_{M.CODE}_1"][0][0].split("\n")
        self.assertIn("赋予自身「灯火正旺」15秒，并累积1层「灯芯」", a1[2])                       # 能力1 #2/#3 已是 L3
        a2 = self.context["cas", f"desc_override_{M.CODE}_2"][0][0].split("\n")
        self.assertEqual(len(a2), 1)                                                              # 能力2 #0/#1 已是 L1
        a3_rows = self.context["ability", f"{M.CID}3"]
        self.assertNotEqual((a3_rows[0][34], a3_rows[0][35]), (a3_rows[3][34], a3_rows[3][35]))   # 限 8 次 ≠ 限 10 次
        self.assertEqual([D.describe_line(a3_rows[i], "ability").split(" → ")[0] for i in (0, 3)],
                         ["光·编成≥6 时: 连击≥55(限8次)(CT5秒)", "光·编成≥6 时: 连击≥55(限10次)(CT5秒)"])
        # 能力3 #1/#2（队长冲刺参数）不在面板上：覆盖串 5 行 = #0 #3 #4 #5 #6。
        self.assertEqual(len(self.context["cas", f"desc_override_{M.CODE}_3"][0][0].split("\n")), 5)
        # 未改的覆盖面板（能力1/2/3）不返回，逐字保留；能力4/5 无覆盖（自动面板，不新建）。
        for n in (1, 2, 3):
            self.assertNotIn(f"desc_override_{M.CODE}_{n}", self.out["cas"])

    def test_resonance_omission_basis(self):
        """灯火正旺 / 灯芯 全部来源带光共鸣，但依赖行文字本无共鸣前缀；「每获得1次「灯火正旺」」行的数据不依赖该状态。"""
        a1 = self.context["ability", f"{M.CID}1"]
        grants = sorted((i, r[68]) for i, r in enumerate(a1) if r[47] == "461")                # c68 = 固有 id
        self.assertEqual(grants, [(2, M.UID_LAMP), (3, M.UID_WICK)])
        for i, _uid in grants:
            self.assertEqual((a1[i][6], a1[i][9], a1[i][11]), ("2", "600000", "White"))      # 光共鸣前置
        others = [(key, i) for (kind, key), rows in self.context.items() if kind == "ability" and key != f"{M.CID}1"
                  for i, r in enumerate(rows) if r[47] == "461" or r[109] == "461"]
        others += [("leader", i) for i, r in enumerate(self.out["leader"][M.CID]) if r[45] == "461" or r[107] == "461"]
        self.assertEqual(others, [])                                                        # 队长/其余能力无授予行
        # 依赖行（数据读固有 id）的面板文字本无「光属性共鸣时，」⇒ 无可删前缀。
        leader_rows = self.out["leader"][M.CID]
        self.assertIn(f"固有{M.UID_WICK}", D.describe_line(leader_rows[6], "leader_ability"))
        self.assertEqual(LEADER_TEXT_AFTER.split("\n")[5], "每1层「灯芯」，强化弹射伤害额外乘区＋2%")
        a1_text = self.context["cas", f"desc_override_{M.CODE}_1"][0][0].split("\n")
        a3_text = self.context["cas", f"desc_override_{M.CODE}_3"][0][0].split("\n")
        for line in [a1_text[3]] + a3_text[2:]:
            self.assertRegex(line, "「灯芯」|持有「灯火正旺」期间")
            self.assertNotIn("属性共鸣时", line)
        # 「光属性共鸣时，每获得1次「灯火正旺」」的数据 = 连击≥55 + 光共鸣前置，不读固有状态 ⇒ 保留共鸣前缀（主会话口径）。
        a3 = self.context["ability", f"{M.CID}3"]
        for row, kind in ((leader_rows[7], "leader_ability"), (leader_rows[8], "leader_ability"),
                          (a3[0], "ability"), (a3[3], "ability")):
            desc = D.describe_line(row, kind)
            self.assertTrue(desc.startswith("光·编成≥6 时: 连击≥55"), desc)
            self.assertNotIn("固有", desc)
        self.assertTrue(LEADER_TEXT_AFTER.split("\n")[6].startswith("光属性共鸣时，每获得1次「灯火正旺」"))
        self.assertTrue(all(line.removeprefix(B.MAIN_ICON).startswith("光属性共鸣时，每获得1次「灯火正旺」")
                            for line in a3_text[:2]))
        self.assertEqual(M.PREFIX_DROPS, {})

    def test_check_merge_passes(self):
        old = self.data["cas", M.CAS_A6][0][0]
        self.assertNotRegex(old, "属性共鸣时[：:]")          # 口径 3：orig 无「：」，不需要规范化
        result = PMC.check(old, A6_TEXT_AFTER, [])
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual((result["errors"], result["warnings"]), ([], []))
        self.assertEqual(result["columns"][0]["mapping"], {1: 1, 2: 1})
        self.assertEqual(result["columns"][0]["kinds"], {1: "merge"})
        # 负对照：未授权删共鸣 / 改数值 / 丢效果 都会被拒。
        for bad in ("光属性角色技能充能速度＋15%，强化弹射伤害＋50%",
                    "光属性共鸣时，光属性角色技能充能速度＋15%，强化弹射伤害＋45%",
                    "光属性共鸣时，光属性角色技能充能速度＋15%"):
            self.assertFalse(PMC.check(old, bad, [])["ok"], bad)
        # 队长面板不做合并（行数不变）。原文 = live 同步第三轮改数（逐字断言）→ 口径 3（恒等）→ 口径 1（L1/L7「、」→「，」），
        # 之后逐行 verbatim；不做口径 1 规范化时，L1/L7 就是未登记的单来源改写（校验器必须报错，且只报这两行）。
        live = self.data["cas", M.CAS_LEADER][0][0]
        self.assertNotRegex(live, "属性共鸣时[：:]")
        lines = live.split("\n")
        for index, old_num, new_num in ((2, "＋5%", "＋35%"), (3, "＋3.5%", "＋25%"), (5, "＋0.5%", "＋2%"),
                                        (6, "＋6%", "＋20%")):
            lines[index] = lines[index].replace(old_num, new_num)
        numbers = "\n".join(lines)
        leader_orig = numbers.replace("、强化弹射伤害", "，强化弹射伤害")
        self.assertEqual(M.leader_text(live), leader_orig)
        result = PMC.check(leader_orig, LEADER_TEXT_AFTER, [])
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual((result["errors"], result["warnings"]), ([], []))
        self.assertEqual(result["columns"][0]["kinds"], {j: "verbatim" for j in range(1, 9)})
        raw = PMC.check(numbers, LEADER_TEXT_AFTER, [])
        self.assertFalse(raw["ok"])
        self.assertEqual([e.split("：")[0] for e in raw["errors"]],
                         ["[列1] 新文案第1行只有 1 个来源却被改写", "[列1] 新文案第7行只有 1 个来源却被改写"])

    def test_pf_damage_wording_and_resonance_punctuation(self):
        """口径 1：kind 55（强化弹射伤害，战场级）不补对象——合并行里它不带对象、与前面「光属性角色…」用「，」隔开，
        返回的面板都不写「自身强化弹射伤害」；追加 A：同形写法（队长 L1 / L7 的「、强化弹射伤害」）一律改「，」；
        口径 3：返回的面板没有「X属性共鸣时：」。"""
        rows = self.data["ability", M.A6]
        self.assertEqual((rows[0][47], rows[1][47]), ("35", "55"))
        self.assertTrue(A6_TEXT_AFTER.endswith("光属性角色技能充能速度＋15%，强化弹射伤害＋50%"))
        self.assertEqual(M.OLD_A6_LINES[1], "光属性共鸣时，强化弹射伤害＋50%")      # 原文本就没写对象
        for key, value in self.out["cas"].items():
            text = value[0][0]
            self.assertNotIn(M.FORBIDDEN_SELF_PF, text, key)
            self.assertNotIn(M.PF_DAMAGE_JOIN_OLD, text, key)
            self.assertNotRegex(text, "属性共鸣时[：:]", key)
        # 队长 L1 / L7（kit 设计稿原有的单行，非合并行）：live 里恰是这两处「、强化弹射伤害」，本轮只改分隔符（L7 另有改数）。
        old = self.data["cas", M.CAS_LEADER][0][0].split("\n")
        new = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual([i for i, line in enumerate(old) if M.PF_DAMAGE_JOIN_OLD in line], [0, 6])
        self.assertEqual(sorted(M.PF_DAMAGE_JOIN_ROWS), [0, 6])
        self.assertEqual(new[0], old[0].replace(M.PF_DAMAGE_JOIN_OLD, M.PF_DAMAGE_JOIN_NEW))
        for line in (new[0], new[6]):
            self.assertRegex(line, r"光属性角色攻击力＋\d+%，强化弹射伤害＋\d+%")
            self.assertEqual(line.count("强化弹射伤害"), 1)
        # 数据依据：前一效果 = 光队攻击（kind 32 → 5/White），强化弹射伤害 = kind 55、对象列空（战斗级，R6 不补「自身」）。
        leader = self.out["leader"][M.CID]
        self.assertEqual(M.pf_damage_problems(leader), [])
        for line, (team, pf) in M.PF_DAMAGE_JOIN_ROWS.items():
            self.assertEqual(tuple(leader[team][45:48]), ("32", "5", "White"), line)
            self.assertEqual(tuple(leader[pf][45:48]), ("55", "", ""), line)
            self.assertIn("攻击力", D.describe_line(leader[team], "leader_ability"))
            self.assertIn("强化弹射伤害", D.describe_line(leader[pf], "leader_ability"))
        self.assertIn("口径 1", self.out["notes"]["changes"][M.CAS_LEADER])
        self.assertEqual(set(self.out["notes"]["panel_merge"]["pf_damage_basis"]), {"L1", "L7"})

    def test_pf_damage_join_is_locked(self):
        """锁：队长 / 能力6 面板回退成「、强化弹射伤害」或补「自身」都会被报出；数据依据漂移 ⇒ problems 报、revise 拒绝。"""
        leader, text = self.out["leader"][M.CID], self.out["cas"][M.CAS_LEADER][0][0]
        self.assertEqual(M.problems(leader, text), [])
        for bad in (text.replace("＋400%，强化弹射", "＋400%、强化弹射"),
                    text.replace("＋20%，强化弹射", "＋20%、强化弹射"),
                    text.replace("＋400%，强化弹射", "＋400%，自身强化弹射")):
            self.assertNotEqual(bad, text)
            self.assertTrue(M.problems(leader, bad), bad)
        self.assertTrue(M.ability6_problems(self.data["ability", M.A6], A6_TEXT_AFTER.replace("，强化弹射", "、强化弹射")))
        for index, col, value in ((1, 45, "32"), (1, 46, "5"), (8, 45, "413"), (0, 45, "55"), (7, 47, "Red")):
            rows = deepcopy(leader)
            rows[index][col] = value
            self.assertTrue(M.pf_damage_problems(rows), (index, col))
        # revise 接线负例：把「#1 强化弹射伤害补了对象」的漂移行当作已审基线（只在此用例内改 BEFORE 摘要），revise 仍拒绝。
        data = deepcopy(self.data)
        data["leader", M.CID][1][46] = "5"
        with mock.patch.dict(M.BEFORE, {("leader", M.CID): M.digest(data["leader", M.CID])}):
            with self.assertRaisesRegex(ValueError, "c45–c47"):
                M.revise(reader(data))

    def test_panel_rules(self):
        self.assertEqual(M.ability6_problems(self.data["ability", M.A6], A6_TEXT_AFTER), [])
        self.assertEqual(K.panel_text_problems(A6_TEXT_AFTER, M.CAS_A6), [])
        self.assertEqual(KL.panel_problems(A6_TEXT_AFTER), [])
        self.assertEqual(L.panel_override_capability(M.CAS_A6), "panel-description-override-v2")
        self.assertTrue(M.ability6_problems(self.data["ability", M.A6],
                                            A6_TEXT_AFTER.replace("，强化弹射", "，自身强化弹射")))   # R6 负对照
        self.assertTrue(M.ability6_problems(self.data["ability", M.A6], A6_TEXT_AFTER.replace("时，", "时：", 1)))

    def test_merge_mutations_are_rejected(self):
        for index, col, value in ((1, 6, "0"), (1, 1, "false"), (1, 34, "1"), (1, 47, "33")):
            data = deepcopy(self.data)
            data["ability", M.A6] = deepcopy(data["ability", M.A6])
            data["ability", M.A6][index][col] = value
            self.assertTrue(M.ability6_rows_problems(data["ability", M.A6]), (index, col))
        with self.assertRaises(ValueError):
            M.ability6_text(M.OLD_A6_LINES[0])


class GeneratorConsistencyTest(unittest.TestCase):
    """生成器：kit 改版计划回放 → 09-17 灯火修订 → 第二批 → 第三轮，产物必须 == revise()。"""

    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.out = M.revise(reader(cls.data))
        _b_data, fx = _load(FIXTURE_B)
        cls.kit = fx["kit_rows"]

    def test_kit_lamp_batch2_round3_chain_matches_revise(self):
        from wf_seasonal_pf_revision import ZEHR_LEADER_TEXT
        a1, a3 = R.revise_rows(deepcopy(self.kit[B.A1]), deepcopy(self.kit[B.A3]))
        leader, _a1, _a3 = B.balance_rows(deepcopy(self.kit["leader"]), a1, a3)
        self.assertEqual(leader, self.data["leader", M.CID])                       # 本轮输入 == kit 第二批产物
        self.assertEqual(M.leader_rows(leader), self.out["leader"][M.CID])
        texts = B.panel_texts({B.CAS_LEADER: ZEHR_LEADER_TEXT,
                               **{key: R.revise_text(slot, self.kit["texts"][key])
                                  for slot, key in ((1, B.CAS_A1), (3, B.CAS_A3))}})
        self.assertEqual([[texts[M.CAS_LEADER]]], self.data["cas", M.CAS_LEADER])
        self.assertEqual([[M.leader_text(texts[M.CAS_LEADER])]], self.out["cas"][M.CAS_LEADER])

    def test_kit_ability6_text_matches_revise(self):
        """生成器：kit 的能力6 文案（plan.json → rev4_panel_text）== live 合并前文本；经 ability6_text == revise()。"""
        plan_path = Path(__file__).resolve().parents[2] / K.REVISION_REL
        if not plan_path.is_file():
            self.skipTest(f"{K.REVISION_REL} missing (work/ is gitignored)")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        kit_text = K.rev4_panel_text(M.CAS_A6, plan["texts"]["custom_ability_string"][M.CAS_A6]["value"])
        self.assertEqual([[kit_text]], self.data["cas", M.CAS_A6])
        self.assertEqual({M.CAS_A6: [[M.ability6_text(kit_text)]]},
                         {M.CAS_A6: self.out["cas"][M.CAS_A6]})
        src = inspect.getsource(K.build)
        order = ["balance_c.problems(", "balance_c.ability6_text(cas_rows[balance_c.CAS_A6][0][0])",
                 "balance_c.ability6_problems(", "for key, text in balance_texts.items():",
                 "ctx.write_flat(CAS, {balance_c.CAS_A6: cas_rows[balance_c.CAS_A6]})"]
        self.assertEqual(sorted(src.index(s) for s in order), [src.index(s) for s in order])

    def test_kit_build_applies_round3_after_batch2(self):
        src = inspect.getsource(K.build)
        order = ["balance_b.balance_rows(", "balance_b.panel_texts(", "balance_c.leader_rows(rows[\"leader\"])",
                 "balance_c.leader_text(", "balance_c.problems(", "for key, text in balance_texts.items():"]
        self.assertEqual(sorted(src.index(s) for s in order), [src.index(s) for s in order])
        last = src.index(order[-1])
        self.assertLess(last, src.index('ctx.write_flat(LEADER, {CID: rows["leader"]})', last))
        self.assertLess(last, src.index("ctx.write_flat(CAS, {key: cas_rows[key] for key in (balance_b.CAS_LEADER", last))
        self.assertIn("import wf_balance_20260927c_zehr as balance_c", src)
        self.assertIn("wf_balance_20260927c_zehr", K.__doc__)

    def test_frozen_inaho_donor_untouched(self):
        spec = K.FROZEN_DONORS[("ability", "LIVE", "1399951", 2)]
        self.assertEqual(spec["sha256"], "9b03a6b2f90c96d49384c5965f02ef00e7fdfb1d4362428a522480635c7f9fbf")
        self.assertEqual(len(K.FROZEN_DONORS), 1)


if __name__ == "__main__":
    unittest.main()
