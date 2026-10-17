# -*- coding: utf-8 -*-
"""索利兹 2026-09-27 第三轮（c）：队长三羽乌逐层成长 20%/20%/0.5% → 70%/70%/2%（成长复核回调）。

fixture = live 输入快照（``fixtures/balance_20260927c_soriz.json``，stage_batch.make_read(live_only=True)，链尾 1.4.1053），
驱动 ``revise()``：每处改动前后值、未改行逐字保留、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、合法性门禁为空、
面板规则、设计镜像纯函数幂等、生成器（配第三轮镜像）输出 == revise()（需要 .cdn / live store / 设计镜像，缺时跳过）。
面板口径（暂存前最后一轮，主会话 A/B/D）：测试侧独立写出规范化步骤（数字 → A → D「&」→ B 拆行/分项 → D 补共鸣），
与终稿逐字相同后过 ``mod-tools/wf_panel_merge_check.check``（仓库内校验器，硬依赖）；L3 拆行按「合并的逆」再核一遍
（终稿拆出的 4 行 → 原 L3 一行）；每处改写的数据依据（队长/能力3 行、722 三档覆盖树、进 Fever 629 树）逐项核对并做负对照。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_gbf as B  # noqa: E402
import wf_balance_20260927c_soriz as C  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
from wf_panel_merge_check import check as check_merge  # noqa: E402  面板合并校验器（仓库内，硬依赖）

FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_soriz.json'
LEADER_FORBIDDEN = {"422", "724", "713"}           # 队长表写这三个 kind = C7050
NUMERIC_TEXT_LINE = "每层「三羽乌」使自身攻击力+70%、强化弹射伤害+70%、强化弹射伤害额外+2%（独立乘区）。"
NEW_TEXT_LINE = "每层「三羽乌」使自身攻击力+70%，强化弹射伤害+70%、强化弹射伤害额外+2%（独立乘区）。"
#: 终稿（11 行，测试侧逐字写出）。
FINAL_PANEL_LINES = [
    "水属性角色攻击力+100%，自身强化弹射伤害+100%。",
    NEW_TEXT_LINE,
    "水属性共鸣时，FEVER模式中，水属性角色无法获得治疗。",
    "水属性共鸣时，FEVER模式中，自身强化弹射伤害+300%。",
    "水属性共鸣时，FEVER模式中，每次弹射的连击数+16。",
    "水属性共鸣时，FEVER模式中，每次强化弹射为水属性角色提供15%最大生命值的护盾，并使FEVER槽减少（槽上限的）20%。",
    "水属性共鸣时，FEVER模式中获得特殊的强化弹射：Lv1倍率提升至10倍、Lv2倍率提升至20倍、Lv3倍率提升至50倍，"
    "判定时间延长，连击数12。",
    "自身生命值每减少1%，自身攻击力+5%，强化弹射伤害+10%。",
    "水属性共鸣时，进入FEVER时，按自身已损失的生命值获得「不死不休」，每损失10%最大生命值1层，最多9层；"
    "已损失30%以上时，水属性角色各获得1次踏止（生命值保留1）。",
    "水属性角色受到致命伤害时，消耗3层「不死不休」并获得4秒无敌。",
    "FEVER结束时，「不死不休」与踏止全部消失。",
]


def normalize_numbers(text: str) -> str:
    """数值稿（测试侧独立写出）：只换第 2 行三羽乌每层数字。"""
    lines = text.split("\n")
    lines[1] = lines[1].replace("+20%", "+70%").replace("+0.5%", "+2%")
    return "\n".join(lines)


def normalize_panel_rules(text: str, *, split: bool = True) -> str:
    """面板口径（测试侧独立写出，行号 = 数值稿 8 行）：L2 按 A 改「，」；L5「&」按 D 改分项、分项后是 A 的形写「，」；
    L4 半角「/」同一 722 行 ⇒ 「、」分项；L6 补「水属性共鸣时，」；L3 按「；」拆 4 行（``split=False`` 时不拆）。"""
    lines = text.split("\n")
    lines[1] = lines[1].replace("自身攻击力+70%、强化弹射伤害", "自身攻击力+70%，强化弹射伤害")
    lines[4] = lines[4].replace("自身攻击力+5%&强化弹射伤害", "自身攻击力+5%，强化弹射伤害")
    lines[3] = re.sub(r"Lv1/Lv2/Lv3倍率提升至(\d+)倍/(\d+)倍/(\d+)倍",
                      lambda m: "、".join(f"Lv{n}倍率提升至{v}倍" for n, v in enumerate(m.groups(), start=1)), lines[3])
    lines[5] = "水属性共鸣时，" + lines[5]
    if split:
        head, body = lines[2].split("：", 1)
        lines[2:3] = [f"{head}，{item}。" for item in body[:-1].split("；")]
    return "\n".join(lines)


def load():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {(r["kind"], r["key"]): r["value"] for r in fixture["reads"]}


def reader(data):
    return lambda kind, key: data.get((kind, key))


def baseline_available() -> bool:
    profile = core.resolve_profile()
    return (profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()
            and (ROOT / C.DESIGN_REL).is_file())


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.pristine = deepcopy(cls.data)
        cls.result = C.revise(reader(deepcopy(cls.data)))

    def old(self, kind, key):
        return deepcopy(self.data[kind, key])


class ContractTests(Base):
    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(set(C.BEFORE), set(self.data))
        for (kind, key), want in C.BEFORE.items():
            self.assertEqual(want, C.digest(self.data[kind, key]), (kind, key))

    def test_baseline_is_the_published_batch2_state(self):
        # 第二批 revise() 的输出 == 本轮输入：c 以第二批发布后的 live（链尾 1.4.1053）为原像。
        fixture = json.loads((Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_gbf.json').read_text(encoding="utf-8"))
        inputs = fixture["inputs"]
        second = B.revise_soriz(lambda kind, key: deepcopy(inputs[kind].get(key)))
        self.assertEqual(second["leader"][C.CID], self.old("leader", C.CID))
        self.assertEqual(second["ability"][C.ABILITY3], self.old("ability", C.ABILITY3))
        self.assertEqual(second["cas"][C.CAS_LEADER], self.old("cas", C.CAS_LEADER))
        for key in C.INVOKE_STRINGS:
            self.assertEqual(inputs["cas"][key], self.old("cas", key))

    def test_module_exports_the_contract(self):
        self.assertEqual(("129986", "soriz"), (C.CID, C.CODE))
        self.assertEqual(["gbf-soriz-20260919"], C.PACKAGES)
        self.assertEqual({"gbf-soriz-20260919": "1.0.2"}, C.PACKAGE_VERSION)
        self.assertEqual(["panel-description-override-v2"], C.CAPABILITIES)
        self.assertEqual({}, C.REVIEWED_DRIFT)
        self.assertTrue(callable(C.revise))
        version = lambda value: tuple(int(p) for p in value.split("."))
        second = B.UNITS[0]["PACKAGE_VERSION"]["gbf-soriz-20260919"]
        self.assertGreater(version(C.PACKAGE_VERSION["gbf-soriz-20260919"]), version(second))
        manifest = ROOT / "work/character_packs/gbf-soriz-20260919/package/manifest.json"
        if manifest.is_file():
            current = json.loads(manifest.read_bytes())["package_version"]
            self.assertGreaterEqual(version(C.PACKAGE_VERSION["gbf-soriz-20260919"]), version(current))

    def test_only_changed_keys_are_returned(self):
        out = self.result
        self.assertEqual({"ability", "leader", "cas", "text", "table", "action", "dsl",
                          "server_text", "new_programs", "notes"}, set(out))
        self.assertEqual({C.CID}, set(out["leader"]))
        self.assertEqual({C.CAS_LEADER}, set(out["cas"]))
        for kind in ("ability", "text", "table", "action", "dsl", "server_text"):
            self.assertEqual({}, out[kind], kind)
        self.assertEqual([], out["new_programs"])
        self.assertFalse(out["notes"]["runtime_verified"])
        json.dumps(out["notes"], ensure_ascii=False)
        for key in out["cas"]:
            self.assertTrue(key.startswith("desc_override_" + C.CODE), key)

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.data)
        out = C.revise(reader(data))
        self.assertEqual(self.pristine, data)
        out["leader"][C.CID][9][111] = "mutated"
        out["cas"][C.CAS_LEADER][0][0] = "mutated"
        self.assertEqual(self.pristine, data)
        self.assertEqual(self.result, C.revise(reader(data)))

    def test_baseline_drift_is_rejected(self):
        for kind, key in C.BEFORE:
            drifted = deepcopy(self.data)
            value = drifted[kind, key]
            if kind == "cas":
                value[0][0] += "。"
            else:
                value[-1][-1] += "x"
            with self.subTest(item=(kind, key)), self.assertRaisesRegex(C.SorizBalanceError,
                                                                         "unreviewed live baseline"):
                C.revise(reader(drifted))
            missing = deepcopy(self.data)
            missing[kind, key] = None
            with self.subTest(missing=(kind, key)), self.assertRaises(ValueError):
                C.revise(reader(missing))

    def test_revise_rejects_its_own_output(self):
        live = deepcopy(self.data)
        live["leader", C.CID] = deepcopy(self.result["leader"][C.CID])
        live["cas", C.CAS_LEADER] = deepcopy(self.result["cas"][C.CAS_LEADER])
        with self.assertRaisesRegex(C.SorizBalanceError, "unreviewed live baseline"):
            C.revise(reader(live))
        # 纯函数层同样拒绝自身输出与第二批前的形态（BEFORE 之外的第二道锁）。
        with self.assertRaisesRegex(C.SorizBalanceError, "unexpected preimage"):
            C.soriz_leader(self.result["leader"][C.CID], self.old("ability", C.ABILITY3))
        with self.assertRaisesRegex(C.SorizBalanceError, "panel text layout"):
            C.soriz_leader_text(self.result["cas"][C.CAS_LEADER])
        with self.assertRaisesRegex(C.SorizBalanceError, "12x124"):
            C.soriz_leader(self.old("leader", C.CID)[:9], self.old("ability", C.ABILITY3))


class LeaderTests(Base):
    def test_leader_changes_only_the_three_crows_strengths(self):
        old, new = self.old("leader", C.CID), self.result["leader"][C.CID]
        self.assertEqual(12, len(new))
        diff = {i: {c: (a[c], b[c]) for c in range(124) if a[c] != b[c]}
                for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual({
            9: {111: ("20000", "70000"), 112: ("20000", "70000")},     # 每层攻击力 20% → 70%
            10: {111: ("20000", "70000"), 112: ("20000", "70000")},    # 每层强化弹射伤害 20% → 70%
            11: {111: ("500", "2000"), 112: ("500", "2000")},          # 每层独立乘区 0.5% → 2%
        }, diff)
        self.assertEqual(old[:9], new[:9])                              # 其余九行逐字不动
        for row, kind in zip(new[9:], ("0", "23", "413")):
            # 触发/层数来源/前置不变：during 134 三羽乌、不设上限、无共鸣前置（口径 D3 只改数值）。
            self.assertEqual(("1", "134", "(None)", C.CROWS, kind, "0"),
                             (row[3], row[95], row[100], row[102], row[107], row[4]))
        self.assertEqual(["持续·状态累积计数固有≥1[固有12998601] → 自身 攻击力 70%",
                          "持续·状态累积计数固有≥1[固有12998601] → 自身 强化弹射伤害 70%",
                          "持续·状态累积计数固有≥1[固有12998601] → 自身 独立乘区强化弹射伤害 2%"],
                         wf_describe.describe_rows(new[9:], "leader_ability"))
        self.assertFalse([r for r in new if r[45] in LEADER_FORBIDDEN or r[107] in LEADER_FORBIDDEN])

    def test_growth_band_is_two_thirds_rounded_up(self):
        for index, _kind, _name, original, before, after, _r in C.GROWTH:
            with self.subTest(index=index):
                self.assertGreaterEqual(after / original, 2 / 3)       # 不低于 2/3 下限
                self.assertLess(after / original, 0.75)                # 仍在 2/3 档（未跳到 7/10 以上的下一档）
                self.assertLessEqual(before * 5, original)             # 第二批 1/5（413 的 0.6% 按 C09 取 0.5%）
                self.assertGreater(after, before)                      # 本轮只回调、不再放缓
        self.assertEqual(0, C.GROWTH[0][5] % 5000)                     # 70%：5 的倍数
        self.assertEqual(0, C.GROWTH[1][5] % 5000)
        self.assertEqual(2000, C.GROWTH[2][5])                         # 3×2/3 = 2%（原值 ≤10%，不取 5 的倍数）

    def test_moved_rows_are_still_the_leader_copy_of_the_capped_ability3_rows(self):
        ability3 = self.old("ability", C.ABILITY3)
        for n, row in enumerate(self.result["leader"][C.CID][9:], start=1):
            formula = ["soriz_leader", "0", ""] + ability3[n][5:]
            self.assertEqual([100, 111, 112], [c for c in range(124) if formula[c] != row[c]])
            self.assertEqual(("10", "(None)"), (formula[100], row[100]))

    def test_ability3_capped_version_is_untouched(self):
        # 口径 D4：能力栏封顶版保持第二批值（15%/10%/1% × 最多 10 层）；本轮不返回能力3。
        ability3 = self.old("ability", C.ABILITY3)
        self.assertEqual([("10", "15000"), ("10", "10000"), ("10", "1000")],
                         [(ability3[i][102], ability3[i][113]) for i in (1, 2, 3)])
        broken = deepcopy(ability3)
        broken[3][113] = broken[3][114] = "2000"
        with self.assertRaisesRegex(C.SorizBalanceError, "capped batch-2 values drifted"):
            C.check_ability3(broken)

    def test_every_returned_row_passes_client_gates(self):
        strings = set(C.INVOKE_STRINGS) | set(self.result["cas"])
        for i, row in enumerate(self.result["leader"][C.CID]):
            with self.subTest(index=i):
                self.assertEqual(124, len(row))
                self.assertEqual([], L.client_legality_problems("leader_ability", row))
                self.assertEqual([], L.declared_block_field_problems("leader_ability", row))
                self.assertEqual([], L.invoke_skill_string_problems(row, strings, "leader_ability"))
                self.assertEqual([], L.ability_element_column_problems("leader_ability", row, 1))
                self.assertEqual({}, KL.row_problems("leader_ability", row, 1))
                self.assertEqual([], L.required_client_capabilities("leader_ability", row))
        fever_begin = self.result["leader"][C.CID][5]
        self.assertTrue(L.invoke_skill_string_problems(fever_begin, set(), "leader_ability"))   # 门禁确实在查


class PanelTests(Base):
    def test_leader_panel_is_the_final_text(self):
        old = self.old("cas", C.CAS_LEADER)[0][0].split("\n")
        rows = self.result["cas"][C.CAS_LEADER]
        self.assertEqual((1, 1), (len(rows), len(rows[0])))
        new = rows[0][0].split("\n")
        self.assertEqual((8, 11), (len(old), len(new)))                   # L3 拆 4 行
        self.assertEqual(FINAL_PANEL_LINES, new)
        self.assertEqual(list(C.NEW_LEADER_LINES), new)
        self.assertEqual(list(C.OLD_LEADER_LINES), old)
        # 数值稿：只换第 2 行数字（本模块首版输出）；终稿逐行由数值稿按面板口径推导（测试侧独立写出）。
        numeric = normalize_numbers(self.old("cas", C.CAS_LEADER)[0][0])
        self.assertEqual(NUMERIC_TEXT_LINE, numeric.split("\n")[1])
        self.assertEqual(C.NUMERIC_LEADER_TEXT, numeric)
        self.assertEqual(rows[0][0], normalize_panel_rules(numeric))
        # 未改的三行逐字（数值稿 L1/L7/L8 = 终稿 L1/L10/L11）。
        self.assertEqual([old[0], old[6], old[7]], [new[0], new[9], new[10]])
        self.assertFalse([line for line in new if line.startswith(C.MAIN_ICON)])   # 队长栏不画 Ⓜ

    def test_panel_text_obeys_the_batch_rules(self):
        text = self.result["cas"][C.CAS_LEADER][0][0]
        self.assertEqual([], C.panel_problems(text))
        self.assertEqual([], KL.panel_problems(text))
        for word in ("自身为队长时", "觉醒后", "生命值100%以下", "无上限", "无限叠加", "不设上限", "可无限", "／", "/", "&",
                     "共鸣时：", "Ⓜ"):
            self.assertNotIn(word, text)
        self.assertEqual([[text]], core.read_csv_lines(core.write_csv_lines([[text]])))
        # 门禁确实在查：live 原文（半角斜杠、「&」、「对象效果、强化弹射伤害」）逐条被拒。
        problems = C.panel_problems(C.OLD_LEADER_TEXT)
        self.assertIn("forbidden phrase '/'", problems)
        self.assertIn("forbidden phrase '&'", problems)
        self.assertEqual(1, sum("joins pf damage" in p for p in problems))       # 原 L2（L5 是「&」）
        self.assertEqual(1, sum("joins pf damage" in p for p in C.panel_problems(C.NUMERIC_LEADER_TEXT)))

    def test_panel_passes_check_merge(self):
        """仓库内校验器（硬依赖）：数值稿先按口径显式规范化（测试侧），与终稿逐行 verbatim；
        拆行按「合并的逆」再核：终稿（11 行）→ 不拆的规范化稿（8 行），校验器须认出 L3 是终稿 L3–L6 的合并。"""
        numeric = normalize_numbers(self.old("cas", C.CAS_LEADER)[0][0])
        final = self.result["cas"][C.CAS_LEADER][0][0]
        forward = check_merge(normalize_panel_rules(numeric), final, [])
        self.assertTrue(forward["ok"], forward["errors"])
        self.assertEqual([], forward["warnings"])
        self.assertEqual({"verbatim"}, set(forward["columns"][0]["kinds"].values()))
        unsplit = normalize_panel_rules(numeric, split=False)
        reverse = check_merge(final, unsplit, [])
        self.assertTrue(reverse["ok"], reverse["errors"])
        self.assertEqual([], reverse["warnings"])
        self.assertEqual({3: "merge"}, {k: v for k, v in reverse["columns"][0]["kinds"].items() if v != "verbatim"})
        self.assertEqual({3: 3, 4: 3, 5: 3, 6: 3}, {k: v for k, v in reverse["columns"][0]["mapping"].items() if v == 3})
        # 负对照：拆出的行改了数值 / 丢掉带数值的一项，逆向核对都失败（无数值的禁疗项由拆行测试逐字核对）。
        self.assertFalse(check_merge(final.replace("连击数+16", "连击数+15"), unsplit, [])["ok"])
        dropped = "\n".join(line for line in final.split("\n") if "连击数+16" not in line)
        self.assertFalse(check_merge(dropped, unsplit, [])["ok"])

    def test_rule_a_pf_damage_is_joined_with_a_comma(self):
        """A：「对象效果、强化弹射伤害」→「，」，不补对象；接在强化弹射伤害项后的 413 项保留「、」。"""
        new = self.result["cas"][C.CAS_LEADER][0][0].split("\n")
        self.assertIn("自身攻击力+70%，强化弹射伤害+70%、强化弹射伤害额外+2%（独立乘区）", new[1])
        self.assertIn("自身攻击力+5%，强化弹射伤害+10%", new[7])
        self.assertNotIn("自身强化弹射伤害+70%", new[1])                                  # 不补对象
        self.assertEqual(NUMERIC_TEXT_LINE.replace("+70%、强化弹射伤害+70%", "+70%，强化弹射伤害+70%"), new[1])
        self.assertEqual(C.OLD_LEADER_LINES[4].replace("&", "，"), new[7])              # D：「&」→ 分项 → A
        self.assertEqual([], C.pf_damage_join_problems("\n".join(new)))
        self.assertTrue(C.pf_damage_join_problems(NUMERIC_TEXT_LINE))
        self.assertTrue(C.pf_damage_join_problems(C.OLD_LEADER_LINES[4].replace("&", "、")))
        with self.assertRaisesRegex(C.SorizBalanceError, "rule-A shape"):
            C.join_pf_damage(new[1])                                                   # 已改过的不再改
        # 数据：L2 = #9 kind 0 自身 → #10 during 23 → #11 413；L5 = #7 kind 0 / #8 during 23 同条件。
        leader = self.result["leader"][C.CID]
        self.assertEqual(["0", "23", "413"], [leader[i][107] for i in (9, 10, 11)])
        self.assertEqual(["0", "23"], [leader[i][107] for i in (7, 8)])
        self.assertEqual(leader[7][95:107], leader[8][95:107])

    def test_rule_b_splits_the_fever_line_by_data_condition(self):
        """B：原 L3 一行四种数据条件 → 4 行，各带水共鸣；四组条件两两不同，能力3 #7/#8 同条件仍在一行。"""
        new = self.result["cas"][C.CAS_LEADER][0][0].split("\n")
        split = new[2:6]
        self.assertEqual(list(C.split_fever_line(C.OLD_LEADER_LINES[2])), split)
        for line in split:
            self.assertTrue(line.startswith("水属性共鸣时，FEVER模式中，"), line)
            self.assertTrue(line.endswith("。"), line)
            self.assertNotIn("；", line)
        body = C.OLD_LEADER_LINES[2][len("水属性共鸣时，FEVER模式中："):-1].split("；")
        self.assertEqual(body, [line[len("水属性共鸣时，FEVER模式中，"):-1] for line in split])   # 措辞逐字
        leader, ability3 = self.result["leader"][C.CID], self.old("ability", C.ABILITY3)
        self.assertEqual(["水·编成≥6 时: Fever≥1 → 自身 发动技能动作[soriz_fever_begin]",
                          "水·编成≥6 时: 持续·Fever → 自身 强化弹射伤害 300%",
                          "水·编成≥6 且 Fever 时: 弹射≥1 → 自身 追加连击 16"],
                         wf_describe.describe_rows([leader[5], leader[2], leader[3]], "leader_ability"))
        self.assertEqual(["水·编成≥6 且 Fever 且 队长 时: 强化弹射≥1 → 赋予全队(水) 屏障 15%",
                          "水·编成≥6 且 Fever 且 队长 时: 强化弹射≥1 → 自身 Fever槽增减(上限比例) -20%"],
                         wf_describe.describe_rows(ability3[7:9], "ability"))
        self.assertEqual([], C.panel_basis_problems(leader, ability3, self.trees()))

    def test_rule_b_itemizes_the_single_722_row_by_level(self):
        """B：半角「/」是同一条 722 行的三档（条件相同）⇒ 「、」分项；倍率/段数/判定时长按 live DSL 核对。"""
        new = self.result["cas"][C.CAS_LEADER][0][0].split("\n")
        self.assertEqual(C.OLD_LEADER_LINES[3].replace(
            "Lv1/Lv2/Lv3倍率提升至10倍/20倍/50倍", "Lv1倍率提升至10倍、Lv2倍率提升至20倍、Lv3倍率提升至50倍"), new[6])
        self.assertNotIn("/", new[6])
        leader = self.result["leader"][C.CID]
        self.assertEqual(1, sum(row[45] == "722" for row in leader))                     # 只有一条 722 行
        self.assertEqual(["水·编成≥6 时: 自身 强化弹射覆盖"], wf_describe.describe_rows([leader[4]], "leader_ability"))
        trees = self.trees()
        self.assertEqual([{"total": float(m), "hits": 12, "lifetime_ratio": 2.0} for m in (10, 20, 50)],
                         [C.pf_level_facts(trees[path]) for path in C.PF_TREES])

    def test_rule_d_adds_resonance_to_the_guts_gain_line(self):
        """D：「不死不休」获取行 = 队长 #5（水编成≥6 → soriz_fever_begin）⇒ 补「水属性共鸣时，」；消耗/清除行不补。"""
        new = self.result["cas"][C.CAS_LEADER][0][0].split("\n")
        self.assertEqual("水属性共鸣时，" + C.OLD_LEADER_LINES[5], new[8])
        self.assertFalse(new[9].startswith("水属性共鸣时"))
        self.assertFalse(new[10].startswith("水属性共鸣时"))
        leader = self.result["leader"][C.CID]
        self.assertEqual(["Blue"], C.resonance_tokens(leader[5], "leader_ability"))
        begin = json.dumps(self.trees()[C.FEVER_BEGIN_TREE])
        self.assertEqual(9, begin.count(f'"ACUnique", {C.GUTS}'))
        self.assertEqual(1, begin.count('"ACGuts"'))
        self.assertEqual(1, begin.count('"ACHealRejection"'))

    def test_panel_basis_fails_closed(self):
        leader, ability3, trees = deepcopy(self.result["leader"][C.CID]), self.old("ability", C.ABILITY3), self.trees()
        self.assertEqual([], C.panel_basis_problems(leader, ability3, trees))
        cases = {
            "L2 kind": lambda l, a, t: l[10].__setitem__(107, "55"),
            "L5 condition": lambda l, a, t: l[8].__setitem__(98, "2000"),
            "resonance on #5": lambda l, a, t: l[5].__setitem__(4, "0"),
            "shield resonance": lambda l, a, t: a[7].__setitem__(6, "0"),
            "combo trigger": lambda l, a, t: l[3].__setitem__(25, "2"),
            "722 row": lambda l, a, t: l[4].__setitem__(81, "3"),
            "Lv3 multiplier": lambda l, a, t: C._commands(C._commands(t[C.PF_TREES[2]], "ConditionalsFeverMode")[0][1],
                                                          "CreateNormalAttack")[0][6][0].update(min=4.0, max=4.0),
            "heal ban": lambda l, a, t: t.__setitem__(C.FEVER_BEGIN_TREE, json.loads(
                json.dumps(t[C.FEVER_BEGIN_TREE]).replace("ACHealRejection", "ACAttackPoint"))),
        }
        for name, mutate in cases.items():
            l, a, t = deepcopy(leader), deepcopy(ability3), deepcopy(trees)
            mutate(l, a, t)
            with self.subTest(case=name):
                self.assertTrue(C.panel_basis_problems(l, a, t))

    def trees(self):
        return {key: deepcopy(value) for (kind, key), value in self.data.items() if kind == "dsl"}


class MirrorTests(unittest.TestCase):
    PATH = ROOT / C.DESIGN_REL

    def setUp(self):
        if not self.PATH.is_file():
            self.skipTest("midautumn design mirror missing")
        self.doc = json.loads(self.PATH.read_text(encoding="utf-8"))

    def test_mirror_update_is_idempotent_and_pure(self):
        before = deepcopy(self.doc)
        once = C.soriz_mirror(self.doc)
        self.assertEqual(before, self.doc)
        self.assertEqual(once, C.soriz_mirror(once))
        rows = once["plan"]["leader_ability"]["rows"]
        self.assertEqual([("70000", "0"), ("70000", "23"), ("2000", "413")],
                         [(r["cells"]["111"], r["cells"]["107"]) for r in rows[9:]])
        self.assertEqual("\n".join(FINAL_PANEL_LINES), once["plan"]["texts"]["custom_ability_string"][C.CAS_LEADER])
        self.assertIn(C.MIRROR_TAG, once)
        self.assertEqual({"数值稿L2", "数值稿L3", "数值稿L4", "数值稿L5", "数值稿L6"}, set(once[C.MIRROR_TAG]["panel_rules"]))
        # 只动队长 #9-#11、队长面板与本轮标签；能力3 记录（封顶版）与其余键逐字不动。
        self.assertEqual(before["plan"]["ability"], once["plan"]["ability"])
        self.assertEqual(before["plan"]["leader_ability"]["rows"][:9], rows[:9])
        texts_before = dict(before["plan"]["texts"]["custom_ability_string"])
        texts_after = dict(once["plan"]["texts"]["custom_ability_string"])
        texts_before.pop(C.CAS_LEADER)
        texts_after.pop(C.CAS_LEADER)
        self.assertEqual(texts_before, texts_after)
        self.assertEqual({k: v for k, v in before.items() if k not in ("plan", C.MIRROR_TAG)},
                         {k: v for k, v in once.items() if k not in ("plan", C.MIRROR_TAG)})

    def test_mirror_state_is_batch2_or_batch3(self):
        # 磁盘镜像只能是第二批已同步或本轮已同步（终稿）；本轮已同步时 dry-run 不再报差。
        changed = C.sync_mirror(ROOT, write=False)
        if C.MIRROR_TAG in self.doc:
            self.assertEqual([], changed)
            self.assertEqual(C.NEW_LEADER_TEXT, self.doc["plan"]["texts"]["custom_ability_string"][C.CAS_LEADER])
        else:
            self.assertEqual([C.DESIGN_REL.as_posix()], changed)
            self.assertEqual("20000", self.doc["plan"]["leader_ability"]["rows"][9]["cells"]["111"])

    def test_mirror_accepts_live_numeric_and_final_panel_forms(self):
        """镜像面板接受 live 原文、数值稿（本模块首版 --write）与终稿三种形态，一律写成终稿；其余形态拒绝。"""
        for form, text in (("live", C.OLD_LEADER_TEXT), ("numeric", C.NUMERIC_LEADER_TEXT),
                           ("final", C.NEW_LEADER_TEXT)):
            doc = deepcopy(self.doc)
            doc["plan"]["texts"]["custom_ability_string"][C.CAS_LEADER] = text
            with self.subTest(form=form):
                self.assertEqual(C.NEW_LEADER_TEXT,
                                 C.soriz_mirror(doc)["plan"]["texts"]["custom_ability_string"][C.CAS_LEADER])
        doc = deepcopy(self.doc)
        doc["plan"]["texts"]["custom_ability_string"][C.CAS_LEADER] = C.NEW_LEADER_TEXT.replace("+300%", "+250%")
        with self.assertRaisesRegex(C.SorizBalanceError, "unexpected panel text"):
            C.soriz_mirror(doc)


@unittest.skipUnless(baseline_available(), "需要 .cdn/cn 官方基线、live store 与设计镜像")
class GeneratorSyncTests(Base):
    """生成器（wf_gbf_kit_soriz + 第三轮设计镜像）重跑 == revise() 输出。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import wf_gbf_duo as G
        import wf_seasonal7_build as SB
        import wf_gbf_kit_soriz as KIT
        cls.KIT = KIT
        cls.ctx = SB.KitContext(G.context("soriz"))
        cls.design = C.soriz_mirror(KIT.load_design(cls.ctx.root))

    def test_rows_equal_revise_output_and_match_the_design(self):
        KIT = self.KIT
        leader, ability, composer = KIT.build_rows(self.ctx, self.design)
        self.assertEqual(self.result["leader"][C.CID], leader)
        self.assertEqual(self.old("ability", C.ABILITY3), ability[C.ABILITY3])     # 能力3 不动
        self.assertEqual([], KIT.design_drift(composer, self.design))
        self.assertEqual([(int(kind), after) for _i, kind, _n, _o, _b, after, _r in C.GROWTH],
                         [(ck, per_layer) for ck, _n, _legacy, _capped, per_layer in KIT.CROWS_GROWTH])
        self.assertEqual([(int(kind), int(capped)) for kind, capped, _cap in C.A3_CAPPED.values()],
                         [(ck, capped) for ck, _n, _legacy, capped, _p in KIT.CROWS_GROWTH])

    def test_panel_strings_equal_revise_output(self):
        strings = self.KIT.cas_rows(self.design)
        self.assertEqual(self.result["cas"][C.CAS_LEADER], strings[C.CAS_LEADER])


if __name__ == "__main__":
    unittest.main()
