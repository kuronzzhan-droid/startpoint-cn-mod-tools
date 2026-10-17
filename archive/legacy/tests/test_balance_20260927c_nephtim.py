"""校园奈芙提姆 2026-09-27 第三轮（c）：队长 Fever 获得量成长 2%→15%、贯穿成长 1%→7%（成长复核回调）；
面板同条件合并（队长第4/6行、能力2 第1/2行）与共鸣省略（口径 6：星夜茶会只经带暗共鸣的技能旗号获得 ⇒
能力1 第2/3行删「暗属性共鸣时，」，依据在 revise() 里 fail closed）。"""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import unittest
from unittest import mock

pass  # Imports resolve from this checkout/package, not external source copies.

from test_bianca_dragon_abilities import official_sources
import wf_balance_20260927b_nephtim as B
import wf_balance_20260927c_nephtim as C
import wf_client_legality as legality
import wf_describe
import wf_midautumn_kitlib as kitlib
import wf_mod_tool as core
import wf_nephtim_fever_abilities as abilities
import wf_nephtim_fever_leader as leader
import wf_nephtim_fever_text as text
from wf_panel_merge_check import check as panel_merge_check  # 面板合并校验器（仓库内，硬依赖）

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927c_nephtim.json"
LEADER_KEY, A3_KEY = "169989", "1699893"

#: 成长复核只换数字后的中间态（9 行；check_merge 的原文）。
NUMBERS_LEADER_TEXT = (
    "暗属性共鸣时，强化弹射变为特殊型与辅助型组合。\n"
    "暗属性共鸣时，强化『午后星轨·甜蜜续杯』：额外赋予暗属性角色及协力球攻击力提升效果。\n"
    "暗属性共鸣时，Fever 模式中，强化后的技能发动时，自身获得或刷新「星夜茶会」，并赋予暗属性角色及协力球护盾。\n"
    "暗属性共鸣时，暗属性角色攻击力+200%、直接攻击伤害+400%。\n"
    "暗属性共鸣时，每达成35连击，暗属性角色获得的 Fever 槽上升量+15%。\n"
    "暗属性共鸣时，Fever 时间+100%。\n"
    "暗属性共鸣时，每有1个协力球消失时，暗属性角色技能槽+5%。\n"
    "暗属性共鸣时，每有1个协力球存在，自身直击判定次数+1。\n"
    "暗属性共鸣时，Fever 模式中，处于贯穿效果的时间每累计2秒，暗属性角色攻击力+7%、直接攻击伤害+7%。")
#: 同条件合并后的中间态：第4行（攻击/直击）与第6行（Fever 时间）同条件合并 ⇒ 8 行（check_merge 的输出）。
MERGED_LEADER_TEXT = (
    "暗属性共鸣时，强化弹射变为特殊型与辅助型组合。\n"
    "暗属性共鸣时，强化『午后星轨·甜蜜续杯』：额外赋予暗属性角色及协力球攻击力提升效果。\n"
    "暗属性共鸣时，Fever 模式中，强化后的技能发动时，自身获得或刷新「星夜茶会」，并赋予暗属性角色及协力球护盾。\n"
    "暗属性共鸣时，暗属性角色攻击力+200%、直接攻击伤害+400%，Fever 时间+100%。\n"
    "暗属性共鸣时，每达成35连击，暗属性角色获得的 Fever 槽上升量+15%。\n"
    "暗属性共鸣时，每有1个协力球消失时，暗属性角色技能槽+5%。\n"
    "暗属性共鸣时，每有1个协力球存在，自身直击判定次数+1。\n"
    "暗属性共鸣时，Fever 模式中，处于贯穿效果的时间每累计2秒，暗属性角色攻击力+7%、直接攻击伤害+7%。")
#: 本轮输出：再把同一条 I536 强化的第2、3行并成一行 =「暗属性共鸣时，」+ 条目原文（技能强化文案 R2）⇒ 7 行。
PROPOSED_LEADER_TEXT = (
    "暗属性共鸣时，强化弹射变为特殊型与辅助型组合。\n"
    "暗属性共鸣时，强化『午后星轨·甜蜜续杯』：额外赋予暗属性角色及协力球攻击力提升效果；Fever 模式中发动时，"
    "自身获得或刷新「星夜茶会」，并赋予暗属性角色及协力球护盾。\n"
    "暗属性共鸣时，暗属性角色攻击力+200%、直接攻击伤害+400%，Fever 时间+100%。\n"
    "暗属性共鸣时，每达成35连击，暗属性角色获得的 Fever 槽上升量+15%。\n"
    "暗属性共鸣时，每有1个协力球消失时，暗属性角色技能槽+5%。\n"
    "暗属性共鸣时，每有1个协力球存在，自身直击判定次数+1。\n"
    "暗属性共鸣时，Fever 模式中，处于贯穿效果的时间每累计2秒，暗属性角色攻击力+7%、直接攻击伤害+7%。")
PROPOSED_A2_TEXT = (
    "暗属性共鸣时，全队贯穿效果时间+40%，暗属性角色直接攻击伤害+250%。\n"
    "暗属性共鸣时，Fever 模式中，暗属性角色技能槽上限+10%。")
MAIN = " <icon id='main'>  "
#: 能力1：第2、3行（依赖持有星夜茶会）删「暗属性共鸣时，」，其余逐字（口径 6）。
PROPOSED_A1_TEXT = (
    MAIN + "战斗开始时，自身技能槽+50%。\n"
    + MAIN + "Fever 模式中，持有「星夜茶会」时，每经过2秒交替召唤1个光、暗属性协力球，各持续25秒且无法回复生命值，"
             "协力球最多同时存在9个；再次发动技能不会延长已有协力球的存在时间。\n"
    + MAIN + "Fever 模式中，持有「星夜茶会」时，协力球已达9个时，该次召唤改为自身攻击力+25%，持续20秒，可叠加。\n"
    + MAIN + "Fever 结束或自身倒下时，「星夜茶会」解除。")


def normalize_resonance_punctuation(value):
    """口径 3（显式规范化步骤）：「X属性共鸣时：」→「X属性共鸣时，」。本角色返回面板里没有冒号写法 ⇒ 恒等（测试断言）。"""
    return re.sub(r"(属性共鸣时)[：:]", r"\1，", value)


def _signed_numbers(text):
    return Counter(re.findall(r"[＋+－\-]\d+(?:\.\d+)?%", text))


def changed(before, after):
    return [i for i in range(len(before)) if before[i] != after[i]]


class NephtimBalance20260927cTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = json.loads(FIXTURE.read_bytes())
        cls.data = {(r["kind"], r["key"]): r["value"] for r in fixture["reads"]}
        cls.evidence = fixture["resonance_evidence"]
        cls.result = C.revise(cls.read_from(cls.data))

    @staticmethod
    def read_from(data):
        return lambda kind, key: data[kind, key]

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    # ------------------------------------------------------------------ 基线

    def test_fixture_is_the_reviewed_before_baseline(self):
        self.assertEqual(set(C.BEFORE), set(self.data))
        for item, expected in C.BEFORE.items():
            self.assertEqual(expected, C.digest(self.data[item]), item)

    def test_baseline_is_the_published_batch2_state(self):
        # 第二批 revise() 的输出 == 本轮输入：c 以第二批发布后的 live（链尾 1.4.1053）为原像。
        fixture = json.loads((Path(__file__).parent / "fixtures/balance_20260927b_nephtim.json").read_bytes())
        data = {(r["kind"], tuple(r["key"]) if isinstance(r["key"], list) else r["key"]): r["value"]
                for r in fixture["reads"]}
        second = B.revise(lambda kind, key: deepcopy(data[kind, key]))
        self.assertEqual(second["leader"][LEADER_KEY], self.live("leader", LEADER_KEY))
        self.assertEqual(second["ability"][A3_KEY], self.live("ability", A3_KEY))
        self.assertEqual(second["cas"][C.TEXT_LEADER], self.live("cas", C.TEXT_LEADER))
        for key in (C.CHANGE_SKILL_STRING_ID, C.PF_STRING_ID, C.BALL_HIT_STRING_ID):
            self.assertEqual(data["cas", key], self.live("cas", key))

    # ------------------------------------------------------------------ 队长

    def test_leader_only_the_three_growth_strengths_change(self):
        old = self.live("leader", LEADER_KEY)
        rows = self.result["leader"][LEADER_KEY]
        self.assertEqual(10, len(rows))
        self.assertEqual(C.LEADER_KINDS, [r[45] for r in rows])
        diff = {i: {c: (a[c], b[c]) for c in range(124) if a[c] != b[c]}
                for i, (a, b) in enumerate(zip(old, rows)) if a != b}
        self.assertEqual({
            4: {49: ("2000", "15000"), 50: ("2000", "15000")},     # 每35连击 Fever 获得量 2% → 15%
            8: {49: ("1000", "7000"), 50: ("1000", "7000")},       # 贯穿成长 攻击力 1% → 7%
            9: {49: ("1000", "7000"), 50: ("1000", "7000")},       # 贯穿成长 直击伤害 1% → 7%
        }, diff)
        for i in (0, 1, 2, 3, 5, 6, 7):
            self.assertEqual(old[i], rows[i], i)                    # 其余七行逐字不动
        # 触发、限次、前置不变：不限次、无 CT、暗共鸣（c4=2）；贯穿两行仍在 Fever 前置（c11=12）下。
        self.assertEqual(("12", "3500000", "(None)", "0", "2", "0"),
                         (rows[4][25], rows[4][28], rows[4][32], rows[4][33], rows[4][4], rows[4][11]))
        for row in rows[8:]:
            self.assertEqual(("235", "12000000", "(None)", "0", "2", "12"),
                             (row[25], row[30], row[32], row[33], row[4], row[11]))
        self.assertEqual(["暗·编成≥6 时: 连击≥35 → 赋予全队(暗) Fever点 15%",
                          "暗·编成≥6 且 Fever 时: 状态KeepFrame贯通≥1 → 赋予全队(暗) 攻击力 7%",
                          "暗·编成≥6 且 Fever 时: 状态KeepFrame贯通≥1 → 赋予全队(暗) Direct伤害 7%"],
                         wf_describe.describe_rows([rows[4], rows[8], rows[9]], "leader_ability"))

    def test_growth_bands_follow_the_author_rules(self):
        # 作者：2/3 为下限；4/5 为上限；数值尽量取 5 的倍数（原值 ≤10% 的行按整数取）。
        for index, original, before, after, band, _rounding in C.GROWTH:
            with self.subTest(index=index):
                ratio = after / original
                self.assertGreaterEqual(ratio, 2 / 3)
                self.assertLessEqual(ratio, 4 / 5)
                self.assertEqual(before * 10, original)            # 第二批 1/10
                self.assertEqual(0, after % 1000)                  # 整百分比
        self.assertEqual((15_000, "4/5"), (C.GROWTH[0][3], C.GROWTH[0][4]))
        self.assertEqual(0, 15_000 % 5_000)                        # 15%：5 的倍数
        self.assertEqual({(7_000, "2/3")}, {(g[3], g[4]) for g in C.GROWTH[1:]})

    def test_moved_rows_are_still_the_leader_copy_of_the_capped_ability3_rows(self):
        a3 = self.live("ability", A3_KEY)
        rows = self.result["leader"][LEADER_KEY]
        for row, source, content in zip(rows[8:], a3[2:4], ("32", "33")):
            formula = ["ruin_girl_campus", "0", ""] + source[5:]
            self.assertEqual([32, 49, 50], changed(formula, row))   # 限次（能力3 为 10）与强度
            self.assertEqual(("10", "(None)"), (formula[32], row[32]))
            self.assertEqual(content, row[45])

    def test_ability3_capped_version_is_untouched(self):
        # 口径 D4：能力栏封顶版保持第二批值；本轮不返回能力3。
        self.assertEqual({}, self.result["ability"])
        a3 = self.live("ability", A3_KEY)
        self.assertEqual([("10", "5000"), ("10", "10000")], [(r[34], r[51]) for r in a3[2:4]])
        broken = deepcopy(a3)
        broken[2][51] = broken[2][52] = "7000"
        with self.assertRaisesRegex(ValueError, "capped batch-2 values drifted"):
            C.check_ability3(broken)

    # ------------------------------------------------------------------ 面板

    def test_leader_panel_changes_only_the_two_numbers(self):
        self.assertEqual({C.TEXT_LEADER: [[PROPOSED_LEADER_TEXT]], C.TEXT_A2: [[PROPOSED_A2_TEXT]],
                          C.TEXT_A1: [[PROPOSED_A1_TEXT]]},
                         self.result["cas"])
        old = self.live("cas", C.TEXT_LEADER)[0][0].split("\n")
        numbers = C.leader_numbers_text(self.live("cas", C.TEXT_LEADER)[0][0])
        self.assertEqual(NUMBERS_LEADER_TEXT, numbers)
        new = numbers.split("\n")
        self.assertEqual(9, len(new))
        self.assertEqual([i for i in range(9) if old[i] != new[i]], [4, 8])
        self.assertEqual(old[4].replace("+2%", "+15%"), new[4])
        self.assertEqual(old[8].replace("+1%", "+7%"), new[8])
        for text in (PROPOSED_LEADER_TEXT, PROPOSED_A2_TEXT):
            self.assertEqual([], C.panel_problems(C.TEXT_LEADER, text))
            self.assertEqual([], kitlib.panel_problems(text))
            for phrase in ("可无限", "无上限", "无限叠加", "不设上限", "自身为队长时", "觉醒后", "生命值100%以下", "／",
                           "属性共鸣时："):
                self.assertNotIn(phrase, text)
            self.assertFalse([line for line in text.split("\n") if line.startswith(C.MAIN_ICON)])
            self.assertEqual([[text]], core.read_csv_lines(core.write_csv_lines([[text]])))
        # 能力1 仅主位（c1 = false）：每行自带主位图标；图标缺一行也拒绝
        self.assertEqual({"false"}, {row[1] for row in self.live("ability", C.A1)})
        self.assertEqual([], C.panel_problems(C.TEXT_A1, PROPOSED_A1_TEXT))
        self.assertEqual([], kitlib.panel_problems(PROPOSED_A1_TEXT))
        self.assertTrue(all(line.startswith(MAIN) for line in PROPOSED_A1_TEXT.split("\n")))
        self.assertTrue(C.panel_problems(C.TEXT_A1, PROPOSED_A1_TEXT.replace(MAIN, "", 1)))
        self.assertEqual([[PROPOSED_A1_TEXT]], core.read_csv_lines(core.write_csv_lines([[PROPOSED_A1_TEXT]])))
        for phrase in ("属性共鸣时：", "／", "自身为队长时", "觉醒后", "生命值100%以下", "无上限"):
            self.assertNotIn(phrase, PROPOSED_A1_TEXT)

    # ------------------------------------------------------------------ 面板同条件合并 / 共鸣省略

    def test_merged_lines_verbatim(self):
        """合并行逐字；合并行放在组首行位置，其余行逐字保留。"""
        numbers = NUMBERS_LEADER_TEXT.split("\n")
        final = MERGED_LEADER_TEXT.split("\n")
        self.assertEqual(8, len(final))
        self.assertEqual(MERGED_LEADER_TEXT, C.merge_leader_text(NUMBERS_LEADER_TEXT))
        self.assertEqual("暗属性共鸣时，暗属性角色攻击力+200%、直接攻击伤害+400%，Fever 时间+100%。", final[3])
        self.assertEqual(numbers[:3] + numbers[4:5] + numbers[6:], final[:3] + final[4:])
        self.assertEqual((C.LEADER_ATTACK_LINE, C.LEADER_FEVER_TIME_LINE), (numbers[3], numbers[5]))
        a2_old = self.live("cas", C.TEXT_A2)[0][0].split("\n")
        a2_new = PROPOSED_A2_TEXT.split("\n")
        self.assertEqual(list(C.OLD_A2_LINES), a2_old)
        self.assertEqual("暗属性共鸣时，全队贯穿效果时间+40%，暗属性角色直接攻击伤害+250%。", a2_new[0])
        self.assertEqual(a2_old[2], a2_new[1])                            # Fever 中技能槽上限那行逐字不动
        for before, after in ((NUMBERS_LEADER_TEXT, MERGED_LEADER_TEXT), (NUMBERS_LEADER_TEXT, PROPOSED_LEADER_TEXT),
                              (self.live("cas", C.TEXT_A2)[0][0], PROPOSED_A2_TEXT)):
            self.assertEqual(_signed_numbers(before), _signed_numbers(after))

    def test_enhancement_entry_is_one_line_equal_to_the_flag_string(self):
        """技能强化文案（R2）：同一条 I536 强化（队长 L#1）面板一行 =「暗属性共鸣时，」+ 条目原文；不写「强化后的技能」。"""
        final = PROPOSED_LEADER_TEXT.split("\n")
        merged = MERGED_LEADER_TEXT.split("\n")
        self.assertEqual(7, len(final))
        self.assertEqual(PROPOSED_LEADER_TEXT, C.merge_enhancement_text(MERGED_LEADER_TEXT))
        flag = self.live("cas", C.CHANGE_SKILL_STRING_ID)[0][0]
        self.assertEqual(flag, C.CHANGE_SKILL_TEXT)
        self.assertEqual(final[1], "暗属性共鸣时，" + flag + "。")
        self.assertEqual(list(C.ENHANCEMENT_OLD_LINES), merged[1:3])
        self.assertEqual(merged[:1] + merged[3:], final[:1] + final[2:])            # 其余行逐字、行序不变
        self.assertNotIn("强化后", PROPOSED_LEADER_TEXT)
        self.assertEqual([], kitlib.panel_problems(flag, skill_flag=True))
        self.assertTrue(flag.startswith("强化『午后星轨·甜蜜续杯』："))
        # 开关行：队长 L#1 = 暗编成≥6 → 536 → 本串
        flag_row = self.live("leader", LEADER_KEY)[C.FLAG_ROW]
        self.assertEqual((flag_row[45], flag_row[68], flag_row[4], flag_row[9]),
                         ("536", C.CHANGE_SKILL_STRING_ID, "2", "Black"))
        # 生成器：ENHANCEMENT_LINES 一行 == 本输出第2行
        import wf_nephtim_fever_text as T
        self.assertEqual(T.ENHANCEMENT_LINES, (final[1],))
        with self.assertRaisesRegex(ValueError, "enhancement lines"):
            C.merge_enhancement_text(PROPOSED_LEADER_TEXT)
        data = deepcopy(self.data)
        data["cas", C.CHANGE_SKILL_STRING_ID] = [["强化技能：" + flag]]
        with self.assertRaisesRegex(ValueError, "live drift"):
            C.revise(self.read_from(data))

    def test_merge_groups_are_one_data_condition(self):
        """合并组按数据核对：组内各行除效果列（kind/对象/元素/强度）外逐格相同。"""
        leader_rows = self.result["leader"][LEADER_KEY]
        self.assertEqual([], C.merge_condition_problems("leader_ability", leader_rows, C.LEADER_MERGE_ROWS))
        self.assertEqual(["33", "32", "56"], [leader_rows[i][45] for i in C.LEADER_MERGE_ROWS])
        a2 = self.live("ability", C.A2)
        self.assertEqual([], C.merge_condition_problems("ability", a2, C.A2_MERGE_ROWS))
        self.assertEqual([("190", "40000"), ("33", "250000")], [(r[47], r[51]) for r in a2[:2]])
        self.assertEqual({"true"}, {r[1] for r in a2})                       # 不限主位 ⇒ 面板无 Ⓜ
        # Fever 中技能槽上限（#2）多一个 Fever 前置，不在组里；第5行（每35连击）有触发，也不在组里
        self.assertTrue(C.merge_condition_problems("ability", a2, (0, 2)))
        self.assertTrue(C.merge_condition_problems("leader_ability", leader_rows, (3, 4)))
        for col, value in ((4, "0"), (25, "12"), (32, "10")):
            rows = deepcopy(leader_rows)
            rows[5][col] = value
            self.assertTrue(C.merge_condition_problems("leader_ability", rows, C.LEADER_MERGE_ROWS), col)

    def test_check_merge_passes(self):
        """面板合并校验器（wf_panel_merge_check，硬依赖）：原文先做口径 3 规范化（本角色恒等），再与输出比对；
        能力1 只允许删登记的第2、3行前缀。"""
        live = {key: self.live("cas", key)[0][0] for key in (C.TEXT_LEADER, C.TEXT_A2, C.TEXT_A1)}
        for key, value in live.items():
            self.assertEqual(normalize_resonance_punctuation(value), value, key)     # 口径 3：无冒号写法
        numbers = normalize_resonance_punctuation(C.leader_numbers_text(live[C.TEXT_LEADER]))
        self.assertEqual(NUMBERS_LEADER_TEXT, numbers)
        for orig, merged, drops, kinds in (
                (numbers, MERGED_LEADER_TEXT, [],
                 {1: "verbatim", 2: "verbatim", 3: "verbatim", 4: "merge", 5: "verbatim",
                  6: "verbatim", 7: "verbatim", 8: "verbatim"}),
                # 技能强化文案：同一条 I536 的第2、3行 → 一行（校验器按合并核对：效果与数值不丢），其余行逐字。
                (MERGED_LEADER_TEXT, PROPOSED_LEADER_TEXT, [],
                 {1: "verbatim", 2: "merge", 3: "verbatim", 4: "verbatim", 5: "verbatim", 6: "verbatim",
                  7: "verbatim"}),
                (normalize_resonance_punctuation(live[C.TEXT_A2]), PROPOSED_A2_TEXT, [],
                 {1: "merge", 2: "verbatim"}),
                (normalize_resonance_punctuation(live[C.TEXT_A1]), PROPOSED_A1_TEXT,
                 [dict(line=n, resonance="Black") for n in C.PREFIX_DROPS[C.TEXT_A1]],
                 {1: "verbatim", 2: "prefix_drop", 3: "prefix_drop", 4: "verbatim"})):
            result = panel_merge_check(orig, merged, prefix_drops=drops)
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual([], result["warnings"])
            self.assertEqual(kinds, result["columns"][0]["kinds"])
        # 负对照：不登记 prefix_drops 删前缀 ⇒ 校验器报错；登记了别的行 ⇒ 也报错
        self.assertFalse(panel_merge_check(live[C.TEXT_A1], PROPOSED_A1_TEXT, prefix_drops=[])["ok"])
        self.assertFalse(panel_merge_check(live[C.TEXT_A1], PROPOSED_A1_TEXT, prefix_drops=[1, 4])["ok"])

    def basis_inputs(self, data=None):
        data = self.data if data is None else data
        return (C.leader_rows(deepcopy(data["leader", LEADER_KEY]), deepcopy(data["ability", A3_KEY])),
                {key: deepcopy(data["ability", key]) for key in C.ABILITY_KEYS},
                deepcopy(data["action", C.CODE]),
                {program: deepcopy(data["dsl", program]) for program in C.BASIS_PROGRAMS})

    def test_resonance_prefix_basis(self):
        """口径 6：星夜茶会只经技能旗号分支获得、旗号唯一来源是带暗共鸣的队长 536 ⇒ 能力1 第2/3行删共鸣前缀。"""
        self.assertEqual({C.TEXT_A1: (2, 3)}, C.PREFIX_DROPS)
        self.assertEqual([], C.resonance_omission_problems(*self.basis_inputs()))
        flag = self.live("leader", LEADER_KEY)[C.FLAG_ROW]
        self.assertEqual(C.FLAG_CELLS, {i: v for i, v in enumerate(flag) if v != ""})
        self.assertEqual(["暗·编成≥6 时: 自身 切换技能形态[change_skill_ruin_girl_campus_fever]"],
                         wf_describe.describe_rows([flag], "leader_ability"))
        # 技能两档 = action_skill c7 = switched 语音版；授予全在 ChangeSkillFlag(1) 开支里（每档两处：获得 / 刷新）
        self.assertEqual(sorted(C.STATE_SOURCE_PROGRAMS),
                         sorted(fields[7] for _inner, fields in self.live("action", C.CODE)))
        for program in C.STATE_SOURCE_PROGRAMS:
            uses = C.dsl_state_uses(self.live("dsl", program))
            grants = [a for role, a in uses if role == "grant"]
            self.assertEqual(2, len(grants), program)
            self.assertTrue(all(C.in_flag_branch(a) for a in grants), program)
            self.assertEqual({"grant", "read"}, {role for role, _a in uses}, program)
        spawn = C.dsl_state_uses(self.live("dsl", C.SPAWN_PROGRAM))
        self.assertEqual({"read", "consume"}, {role for role, _a in spawn})
        self.assertTrue(all(C.in_holding_branch(a) for role, a in spawn if role == "consume"))
        for program in C.INVOKED_PROGRAMS[:1] + C.INVOKED_PROGRAMS[2:] + C.PF_OVERRIDE_PROGRAMS:
            self.assertEqual([], C.dsl_state_uses(self.live("dsl", program)), program)
        # 能力1 #1（两行省略所对应的数据行）：持有星夜茶会 KeepFrame 触发 → 629 fever_spawn；数据前置仍带暗共鸣
        a1 = self.live("ability", C.A1)
        self.assertEqual([(37, "depends")], C.table_uid_roles(a1[1], "ability"))
        self.assertEqual(("2", "232", "629", C.SPAWN_PROGRAM), (a1[1][6], a1[1][27], a1[1][47], a1[1][71]))
        # 全表证据（fixture 导出时对 live 1.4.1054 全能力 / 队长表 + store 全 DSL 暴力扫描）
        evidence = self.evidence
        self.assertEqual(C.STATE_UID, evidence["state_uid"])
        self.assertEqual([], evidence["row_grants"])
        self.assertEqual(["leader_ability:169989#1"], evidence["change_skill_rows"])
        self.assertEqual(["leader_ability:169989#1"], evidence["skill_flag_rows_full_tables"])
        self.assertEqual(["ability:1699891#1 c37 depends", "ability:1699891#2 c68 remove",
                          "ability:1699891#3 c12 depends", "ability:1699891#3 c68 remove"],
                         evidence["uid_cells_full_tables"])
        self.assertEqual({"ruin_girl_campus_voice_ready": sorted(C.STATE_SOURCE_PROGRAMS)},
                         evidence["switched_voice_ready_programs"])
        self.assertEqual(sorted((*C.STATE_SOURCE_PROGRAMS, C.SPAWN_PROGRAM)),
                         evidence["store_dsl_scan"]["dsl_files_referencing_uid"])
        self.assertEqual([], evidence["basis_problems_live"])
        for program, found in evidence["programs"].items():
            self.assertEqual(C.digest(self.live("dsl", program)), found["digest"], program)
            for chain in found["grant_chains"]:
                self.assertEqual("ConditionalsChangeSkillFlag", chain[0])
                self.assertNotIn(C.RESONANCE_CONDITIONAL, chain)            # 授予节点本身无共鸣节点：间接门控
        # 输出：能力1 只删第2、3行前缀；队长 / 能力2 各因合并省掉一个重复前缀；队长另因同一条 I536 强化两行并一行再省一个
        for key, removed in ((C.TEXT_LEADER, 2), (C.TEXT_A2, 1), (C.TEXT_A1, 2)):
            before = self.live("cas", key)[0][0]
            self.assertEqual(before.count("暗属性共鸣时，") - removed,
                             self.result["cas"][key][0][0].count("暗属性共鸣时，"), key)
        old_a1 = self.live("cas", C.TEXT_A1)[0][0].split("\n")
        new_a1 = PROPOSED_A1_TEXT.split("\n")
        self.assertEqual([old_a1[0], old_a1[3]], [new_a1[0], new_a1[3]])
        for index in (1, 2):
            self.assertEqual(old_a1[index].replace(MAIN + "暗属性共鸣时，", MAIN, 1), new_a1[index])

    def test_resonance_basis_fails_closed(self):
        """依据任一不成立 ⇒ resonance_omission_problems 报错，revise() 拒绝（BEFORE 已按新值复核也拒绝）。"""
        def dsl_grant(uid=C.STATE_UID):
            return ["Command", ["CreateCondition", -17, [["ACUnique", uid, [{"min": 1, "max": 1}]]]]]

        def mutate_leader(fn):
            def apply(leader_rows, abilities_, action, trees):
                fn(leader_rows)
            return apply

        mutations = {
            "flag row loses the dark resonance": mutate_leader(lambda r: r[C.FLAG_ROW].__setitem__(4, "0")),
            "second flag row (ability 704)": lambda l, a, x, t: a[C.CID + "6"][0].__setitem__(47, "704"),
            "second flag row (leader during 536)": mutate_leader(lambda r: r[2].__setitem__(107, "536")),
            "table grant (461 → 星夜茶会)": lambda l, a, x, t: (a[C.CID + "5"][0].__setitem__(47, "461"),
                                                                a[C.CID + "5"][0].__setitem__(68, str(C.STATE_UID))),
            "uid in an unrecognised cell": lambda l, a, x, t: a[C.A2][0].__setitem__(100, str(C.STATE_UID)),
            "DSL grant in a 629 program": lambda l, a, x, t: t[C.INVOKED_PROGRAMS[0]][11][1].append(dsl_grant()),
            "DSL grant in a PF override": lambda l, a, x, t: t[C.PF_OVERRIDE_PROGRAMS[2]][11][1].append(dsl_grant()),
            "skill grant outside the flag branch": lambda l, a, x, t: t[C.STATE_SOURCE_PROGRAMS[0]][11][1].append(
                dsl_grant()),
            "flag branch reads flag 2": lambda l, a, x, t: t[C.STATE_SOURCE_PROGRAMS[1]][11][1][5][1].__setitem__(1, 2),
            "skill has no grant left": lambda l, a, x, t: t.__setitem__(C.STATE_SOURCE_PROGRAMS[0],
                                                                        t[C.INVOKED_PROGRAMS[2]]),
            "consume outside the holding branch": lambda l, a, x, t: t[C.SPAWN_PROGRAM][11][1].append(
                ["Command", ["ConsumeUniqueCondition", -17, C.STATE_UID, ["Some", -1]]]),
            "bare uid in a DSL": lambda l, a, x, t: t[C.INVOKED_PROGRAMS[3]][11][1].append(
                ["Command", ["Wait", C.STATE_UID]]),
            "unread 629 program": lambda l, a, x, t: a[C.CID + "4"][1].__setitem__(71, "battle/action/x$y"),
            "unread PF override": mutate_leader(lambda r: r[0].__setitem__(80, "other_pf")),
            "skill program moved": lambda l, a, x, t: x[0][1].__setitem__(7, "battle/action/skill/action/rare5/x$x_1"),
            "fever_spawn gets a second caller": lambda l, a, x, t: a[C.CID + "3"][5].__setitem__(71, C.SPAWN_PROGRAM),
            "omitted row no longer holding-gated": lambda l, a, x, t: a[C.A1][1].__setitem__(27, "77"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name):
                inputs = self.basis_inputs()
                mutate(*inputs)
                self.assertTrue(C.resonance_omission_problems(*inputs), name)
        # 接线：能力5 出现授予行 ⇒ 即使 BEFORE 已按新值复核，revise() 也拒绝
        data = deepcopy(self.data)
        row = data["ability", C.CID + "5"][0]
        row[47], row[68] = "461", str(C.STATE_UID)
        with mock.patch.dict(C.BEFORE, {("ability", C.CID + "5"): C.digest(data["ability", C.CID + "5"])}):
            with self.assertRaisesRegex(ValueError, "resonance-prefix omission basis drifted"):
                C.revise(self.read_from(data))

    def test_state_grant_chain_walker(self):
        tree = ["ActionDsl", ["Command", ["ConditionalsFeverMode",
                                          ["Command", ["ConditionalsUnifyElement", 5,
                                                       ["Command", ["CreateCondition", -17,
                                                                    [["ACUnique", C.STATE_UID, 1]]]]]]]]]
        self.assertEqual([["ConditionalsFeverMode", "ConditionalsUnifyElement"]], C.state_grant_chains(tree))
        self.assertEqual([], C.state_grant_chains(tree, uid=1))

    # ------------------------------------------------------------------ 合同

    def test_only_changed_keys_are_returned_in_the_contract_shape(self):
        result = self.result
        self.assertEqual({"ability", "leader", "cas", "text", "table", "action", "dsl",
                          "server_text", "new_programs", "notes"}, set(result))
        self.assertEqual({LEADER_KEY}, set(result["leader"]))
        self.assertEqual({C.TEXT_LEADER, C.TEXT_A2, C.TEXT_A1}, set(result["cas"]))   # + 能力2 合并、能力1 共鸣省略
        for kind in ("ability", "text", "table", "action", "dsl", "server_text"):
            self.assertEqual({}, result[kind], kind)
        self.assertEqual([], result["new_programs"])
        json.dumps(result["notes"], ensure_ascii=False)
        self.assertFalse(result["notes"]["runtime_verified"])
        for key in result["cas"]:
            self.assertTrue(key.startswith(("desc_override_" + C.CODE, "change_skill_" + C.CODE, C.CODE)))

    def test_inputs_are_not_mutated_and_outputs_are_independent(self):
        data = deepcopy(self.data)
        before = deepcopy(data)
        result = C.revise(self.read_from(data))
        self.assertEqual(before, data)
        result["leader"][LEADER_KEY][4][49] = "changed"
        result["leader"][LEADER_KEY][8][49] = "changed"
        result["cas"][C.TEXT_LEADER][0][0] = "changed"
        self.assertEqual(before, data)
        self.assertEqual(self.result, C.revise(self.read_from(data)))

    def test_any_live_drift_fails_closed(self):
        for item in C.BEFORE:
            data = deepcopy(self.data)
            if item[0] == "dsl":
                data[item][11][1].append(["Command", ["Wait", 1]])             # DSL 树：根块多一条命令
            elif item[0] == "action":
                data[item][0][1][7] += "x"                                     # action_skill：程序路径漂移
            else:
                data[item][0][0] = data[item][0][0] + "x"
            with self.subTest(item=item), self.assertRaisesRegex(ValueError, "live drift"):
                C.revise(self.read_from(data))

    def test_rerunning_on_its_own_output_is_rejected(self):
        data = deepcopy(self.data)
        data["leader", LEADER_KEY] = deepcopy(self.result["leader"][LEADER_KEY])
        data["cas", C.TEXT_LEADER] = deepcopy(self.result["cas"][C.TEXT_LEADER])
        with self.assertRaisesRegex(ValueError, "live drift"):
            C.revise(self.read_from(data))
        # 纯函数层同样拒绝自身输出与第二批前的原值（BEFORE 之外的第二道锁）。
        with self.assertRaisesRegex(ValueError, "unexpected preimage"):
            C.leader_rows(self.result["leader"][LEADER_KEY], self.live("ability", A3_KEY))
        with self.assertRaisesRegex(ValueError, "leader panel"):
            C.leader_text(PROPOSED_LEADER_TEXT)
        with self.assertRaisesRegex(ValueError, "leader panel"):
            C.merge_leader_text(PROPOSED_LEADER_TEXT)
        with self.assertRaisesRegex(ValueError, "unexpected panel lines"):
            C.ability2_text(PROPOSED_A2_TEXT)
        with self.assertRaisesRegex(ValueError, "unexpected panel lines"):
            C.ability1_text(PROPOSED_A1_TEXT)
        original = self.live("leader", LEADER_KEY)
        original[4][49] = original[4][50] = "20000"
        with self.assertRaisesRegex(ValueError, "unexpected preimage"):
            C.leader_rows(original, self.live("ability", A3_KEY))
        with self.assertRaisesRegex(ValueError, "10x124"):
            C.leader_rows(self.live("leader", LEADER_KEY)[:8], self.live("ability", A3_KEY))

    def test_every_output_row_passes_the_client_gates(self):
        strings = {key for kind, key in self.data if kind == "cas"} | set(self.result["cas"])
        for index, row in enumerate(self.result["leader"][LEADER_KEY]):
            with self.subTest(index=index):
                self.assertEqual(124, len(row))
                self.assertEqual([], legality.client_legality_problems("leader_ability", row))
                self.assertEqual([], legality.declared_block_field_problems("leader_ability", row))
                self.assertEqual([], legality.ability_element_column_problems("leader_ability", row, 5))
                self.assertEqual([], legality.invoke_skill_string_problems(row, strings, "leader_ability"))
                self.assertEqual([], legality.required_client_capabilities("leader_ability", row))
                self.assertEqual({}, kitlib.row_problems("leader_ability", row, 5))
        self.assertEqual([], C.validate(self.result, strings))
        self.assertEqual(["panel-description-override-v2"], C.CAPABILITIES)
        for missing in (C.CHANGE_SKILL_STRING_ID, C.PF_STRING_ID, C.BALL_HIT_STRING_ID):
            with self.subTest(missing=missing):
                self.assertTrue(C.validate(self.result, strings - {missing}))

    # ------------------------------------------------------------------ 生成器一致性

    def test_generators_produce_exactly_the_revised_values(self):
        source, _ = official_sources()
        rows = abilities.ability_rows(source)
        leaders = leader.leader_rows(source)
        self.assertEqual(self.result["leader"][LEADER_KEY], leaders)
        self.assertEqual(self.live("ability", A3_KEY), rows[A3_KEY])        # 能力3 不动
        panels = text.panel_rows(rows, leaders, piercing_extension="dark_resonance")
        for key in (C.TEXT_LEADER, C.TEXT_A2, C.TEXT_A1):
            self.assertEqual(self.result["cas"][key], panels[key], key)
        for key in C.ABILITY_KEYS:                                          # 能力行都不动（只读核对）
            self.assertEqual(self.live("ability", key), rows[key], key)
        self.assertEqual((7_000, 15_000), (abilities.LEADER_PIERCING_GROWTH_STRENGTH,
                                           leader.FEVER_GAIN_GROWTH_STRENGTH))
        self.assertEqual((15, 7, 7), (leader.metadata()["fever_gain_growth"]["increase_percent"],
                                      leader.metadata()["piercing_growth"]["attack_percent"],
                                      leader.metadata()["piercing_growth"]["direct_damage_percent"]))
        self.assertEqual((5_000, 10_000, 10), (abilities.PIERCING_CAPPED_ATTACK_STRENGTH,
                                               abilities.PIERCING_CAPPED_DIRECT_STRENGTH,
                                               abilities.PIERCING_CAPPED_LIMIT))

    # ------------------------------------------------------------------ 候选

    def test_package_targets_and_versions_only_move_forward(self):
        self.assertEqual(B.PACKAGES, C.PACKAGES)
        self.assertEqual(set(C.PACKAGES), set(C.PACKAGE_VERSION))
        self.assertEqual({}, C.REVIEWED_DRIFT)
        version = lambda value: tuple(int(part) for part in value.split("."))
        for package, new in C.PACKAGE_VERSION.items():
            self.assertGreater(version(new), version(B.PACKAGE_VERSION[package]), package)
            manifest = ROOT / "work/character_packs" / package / "package/manifest.json"
            if manifest.is_file():
                current = json.loads(manifest.read_bytes())["package_version"]
                self.assertGreaterEqual(version(new), version(current), package)


if __name__ == "__main__":
    unittest.main()
