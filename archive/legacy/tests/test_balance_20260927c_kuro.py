# -*- coding: utf-8 -*-
"""黑 139991 ``outlaw_panther_moon`` 2026-09-27 平衡第三轮（c：成长复核，只改数值）。

fixture = live 1.4.1053 输入快照（``fixtures/balance_20260927c_kuro.json``，BEFORE = make_read 返回值的摘要），
驱动 ``revise()``：两处数值的前后值与档位 / 取整、未改行 / 未改格逐字保留、面板与数据一致且守面板规则、
BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、合法性门禁为空、第二批输出首尾相接、生成器装配 == revise()
输出（需要 .cdn/cn 官方基线与 live store）、设计镜像（主会话 ``--write`` 前在内存里验证，写后验证落盘）。
第 4 节（面板同条件合并）：队长第 1、2 行、能力6 两行合并逐字、数据除效果 kind / 强度外逐列相同、
``wf_panel_merge_check.check`` 通过（仓库内校验器，硬依赖）、没有共鸣前缀被删（「豹步」来源无前置；live 全表核对两个
固有状态来源需要 live store）。第 5 节（本轮面板统一口径）：能力3 面板第 4 行「雷属性共鸣时：」→「，」（口径 3）；
上一稿按口径 5 拆分项的第 6 行随第 7 节 R2 删除，测试里显式写出「删 R2 两行 + 口径 3」再交给校验器；
所有返回面板无「共鸣时：」、无「／」。
第 6 节（作者追加「黑豹能力2改成5刃25次暖满」）：能力2#0 封顶版每次 2% → 5%、最多 25 次不变（叠满 125%），只动 c51/c52；
能力2 面板第 1 行同步数字、第 2 行逐字；fixture 补入 live 1.4.1054 的能力2 面板。
第 7 节（技能强化条目 R1–R4）：强化条目改官方格式定性、能力1 第 2 行同文加共鸣前缀、能力3 第 5、6 行（强化分支的抽取表 /
翻倍表）删除、技能描述不改；依据（开关行唯一、两档 DSL 旗号开支 / 关支逐节点差异、轮盘与翻倍、技能描述只写本体）逐条核对，
并对每条依据做变异（改了就必须拒绝）；fixture 补入 live 1.4.1054 的能力1/3/4/5、强化条目、能力1 面板、两档技能树、技能描述。
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import re
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_kuro as M2  # noqa: E402
import wf_balance_20260927c_kuro as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_midautumn_kit_kuro as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_kuro_full_dice as FD  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_panel_merge_check as PMC  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_kuro.json'
FIXTURE_B = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_kuro.json'
CANDIDATE = ROOT / "work/character_packs/ma-kuro"
MANIFEST = CANDIDATE / "package/manifest.json"


def load_fixture(path: Path = FIXTURE) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


def reader(data: dict):
    def read(kind, key):
        return data[kind][key]
    return read


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(x) for x in text.split("."))


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


def batch2_live() -> dict:
    """第二批 live 输入 + 第二批 revise() 输出 = 第三轮的 live（链尾 1.4.1053）全集。
    第三轮补读、第二批不涉及的键（面板合并的能力6 行 / 能力6 面板；第 7 节的能力1/4/5 行、强化条目、能力1 面板、技能树、
    技能描述）取本轮 fixture（= live）；第二批读写过的键（队长、能力2/3、队长 / 能力2 / 能力3 面板）仍由第二批输出给出。"""
    live = load_fixture(FIXTURE_B)
    out = M2.revise(reader(deepcopy(live)))
    for kind in ("leader", "ability", "cas"):
        live[kind].update(deepcopy(out[kind]))
    current = load_fixture()
    for kind, key in M.BEFORE:
        live.setdefault(kind, {}).setdefault(key, deepcopy(current[kind][key]))
    return live


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old2, cls.new2 = cls.live["ability"][M.ABILITY2_KEY], cls.out["ability"][M.ABILITY2_KEY]
        cls.old_leader, cls.new_leader = cls.live["leader"][M.LEADER_KEY], cls.out["leader"][M.LEADER_KEY]

    # ------------------------------------------------------------ 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         set(M.BEFORE))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE, M.ELEMENT, M.ELEMENT_TOKEN),
                         (K.CID_S, K.CODE, K.ELEMENT, K.ELEMENT_TOKEN))
        self.assertEqual(M.CAS_LEADER, K.CAS_LEADER)
        self.assertEqual(M.PACKAGES, ["ma-kuro"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-kuro": "1.0.3"})      # 候选现值 1.0.2（第二批），只升不降
        self.assertGreater(_version(M.PACKAGE_VERSION["ma-kuro"]), _version(M2.PACKAGE_VERSION["ma-kuro"]))
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {M.ABILITY2_KEY})          # 能力3 封顶版不动（D4）；能力1/3/4/5 只读
        self.assertEqual(set(out["leader"]), {M.LEADER_KEY})
        # 第 4 节：能力6 面板合并；第 5 节：能力3 面板口径 3（数值不动）；第 6 节：能力2 面板第 1 行数字；
        # 第 7 节：强化条目、能力1 面板第 2 行、能力3 面板删 R2 两行
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER, M.CAS_ABILITY1, M.CAS_ABILITY2, M.CAS_ABILITY3,
                                           M.CAS_ABILITY6, M.CAS_SWITCH})
        for kind in ("text", "table", "action", "dsl", "server_text"):  # R3/R4：技能描述与技能树不改
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        for key in out["cas"]:                                          # RevisionCandidate 命名空间（stage_batch.splice 同口径）
            self.assertTrue(key.startswith(("desc_override_" + M.CODE, "change_skill_" + M.CODE)), key)
        json.dumps(out["notes"], ensure_ascii=False)
        for kind in ("ability", "leader", "cas"):
            for key, value in out[kind].items():
                self.assertNotEqual(value, self.live[kind][key], f"{kind}:{key} returned but unchanged")

    # ------------------------------------------------------------ 能力2#3：技能命中 → 自身攻击力（仅队长）

    def test_leader_gated_hit_row_before_and_after(self):
        self.assertEqual((len(self.old2), len(self.new2)), (4, 4))
        self.assertEqual(self.new2[1:3], self.old2[1:3])                # 豹步两行逐字不动（#0 见第 6 节）
        old, new = self.old2[3], self.new2[3]
        self.assertEqual([i for i in range(126) if old[i] != new[i]], [51, 52])
        self.assertEqual([old[51], old[52]], ["5000", "5000"])
        self.assertEqual([new[51], new[52]], ["35000", "35000"])
        self.assertEqual((new[6], new[13], new[18], new[27], new[34], new[47], new[48]),
                         ("42", "2", "Yellow", "107", "(None)", "32", "0"))  # 仅队长 + 雷共鸣、不限次、自身攻击
        self.assertEqual(D.describe_line(new, "ability"), "队长 且 雷·编成≥6 时: 技能Hit≥1 → 自身 攻击力 35%")
        self.assertEqual([i for i, (a, b) in enumerate(zip(self.old2, self.new2)) if a != b], [0, 3])

    # ------------------------------------------------------------ 第 6 节：能力2#0 封顶版 2%×25 → 5%×25（作者追加）

    def test_capped_hit_row_is_five_percent_times_25(self):
        """作者原话「黑豹能力2改成5刃25次暖满」：5刃 = 每次 5%，25 次上限不变，叠满 = 125%；只动 c51/c52。"""
        self.assertEqual(M.AUTHOR_CAP_REQUEST, "黑豹能力2改成5刃25次暖满")
        old, new = self.old2[0], self.new2[0]
        self.assertEqual([i for i in range(126) if old[i] != new[i]], [51, 52])
        self.assertEqual([old[34], old[51], old[52]], ["25", "2000", "2000"])     # 第二批封顶版
        self.assertEqual([new[34], new[51], new[52]], ["25", "5000", "5000"])
        self.assertEqual(int(old[34]) * int(old[51]), 50000)                      # 叠满 50%
        self.assertEqual(int(new[34]) * int(new[51]), 125000)                     # 叠满 125%
        self.assertEqual((new[6], new[11], new[27], new[47], new[48]), ("2", "Yellow", "107", "32", "2"))  # 雷共鸣 技能Hit 给队长
        self.assertEqual(D.describe_line(new, "ability"), "雷·编成≥6 时: 技能Hit≥1(限25次) → 赋予队长 攻击力 5%")
        self.assertEqual(self.out["notes"]["changes"][f"ability:{M.ABILITY2_KEY}#0"], M.CAP_EDIT[-1])
        self.assertFalse([k for k in self.out["notes"]["kept"] if "2%×25" in k])

    def test_ability2_panel_changes_only_the_number(self):
        old = self.live["cas"][M.CAS_ABILITY2][0][0].split("\n")
        new = self.out["cas"][M.CAS_ABILITY2][0][0].split("\n")
        self.assertEqual(tuple(old), M.OLD_ABILITY2_LINES)
        self.assertEqual(new, ["雷属性共鸣时，自身技能每命中1次，队长攻击力＋5%，最多25次",
                               "自身处于「豹步」状态时：雷属性角色攻击力＋250%"])
        self.assertEqual(new[1], old[1])                                          # 豹步逐字不动
        self.assertEqual(new[0].replace("＋5%", "＋2%"), old[0])                  # 只改数字
        self.assertEqual(old[0], M2.NEW_ABILITY2_LINE)                            # live = 第二批写入
        for line in new:
            self.assertFalse(line.startswith(K.MAIN_ICON), line)                  # 能力2 c1=true，不带图标
        # 仓库内校验器：原文 = 本轮数值改后文案 ⇒ 逐字，无合并（#0–#3 触发 / 前置 / 次数上限各不同）
        result = PMC.check("\n".join(M.NEW_ABILITY2_LINES), "\n".join(new), [])
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(set(result["columns"][0]["kinds"].values()), {"verbatim"})
        self.assertEqual(self.out["notes"]["panel_merge"]["no_merge"][M.CAS_ABILITY2], M.ABILITY2_NO_MERGE)
        self.assertNotEqual((self.new2[0][6], self.new2[0][34]), (self.new2[1][6], self.new2[1][34]))

    def test_hit_row_is_two_thirds_rounded_up(self):
        """原 50%（第二批 ×1/10 = 5%）× 2/3 = 33.3% → 2/3 档一律向上取 5 的倍数 = 35%，不低于 2/3 下限。"""
        original = int(self.old2[3][51]) * 10
        self.assertEqual(original, 50000)
        new = int(self.new2[3][51])
        self.assertEqual(new, 35000)
        self.assertEqual(new % 5000, 0)
        self.assertGreaterEqual(Fraction(new, original), Fraction(2, 3))
        self.assertLess(Fraction(new - 5000, original), Fraction(2, 3))   # 最小的满足者

    # ------------------------------------------------------------ 队长#4：每次进入 Fever → 雷队直击

    def test_fever_leader_row_before_and_after(self):
        self.assertEqual((len(self.old_leader), len(self.new_leader)), (5, 5))
        self.assertEqual(self.new_leader[:4], self.old_leader[:4])
        old, new = self.old_leader[4], self.new_leader[4]
        self.assertEqual([i for i in range(124) if old[i] != new[i]], [49, 50])
        self.assertEqual([old[49], old[50]], ["30000", "30000"])
        self.assertEqual([new[49], new[50]], ["105000", "105000"])
        self.assertEqual((new[4], new[25], new[45], new[46], new[47]), ("0", "8", "33", "5", "Yellow"))  # 不加共鸣前置（D3）
        self.assertEqual(D.describe_line(new, "leader_ability"), "Fever≥1 → 赋予全队(雷) Direct伤害 105%")

    def test_fever_row_is_seven_tenths(self):
        original = int(self.old_leader[4][49]) * 5                      # 第二批 ×1/5
        self.assertEqual(original, 150000)
        self.assertEqual(Fraction(original) * Fraction(7, 10), int(self.new_leader[4][49]))
        self.assertEqual(int(self.new_leader[4][49]) % 5000, 0)

    def test_rounding_helper(self):
        self.assertEqual(M.rescale(50000, Fraction(2, 3), up=True), 35000)
        self.assertEqual(M.rescale(150000, Fraction(7, 10)), 105000)
        self.assertEqual(M.rescale(5000, Fraction(4, 5)), 4000)          # ≤10%：0.5% 档

    def test_native_legality_gates_are_empty(self):
        rows = [("leader_ability", f"leader#{i}", r) for i, r in enumerate(self.new_leader)]
        rows += [("ability", f"{M.ABILITY2_KEY}#{i}", r) for i, r in enumerate(self.new2)]
        for kind, label, row in rows:
            self.assertEqual(L.client_legality_problems(kind, row), [], label)
            self.assertEqual(L.declared_block_field_problems(kind, row), [], label)
            self.assertEqual(L.invoke_skill_string_problems(row, set(), kind=kind), [], label)
            self.assertEqual(L.ability_element_column_problems(kind, row, M.ELEMENT), [], label)
            self.assertEqual(KL.row_problems(kind, row, K.ELEMENT), {}, label)
        self.assertEqual(L.required_client_capabilities("leader_ability", self.new_leader[4]), [])
        self.assertEqual(L.required_client_capabilities("ability", self.new2[3]), [])
        self.assertEqual(L.required_client_capabilities("ability", self.new2[0]), [])

    # ------------------------------------------------------------ 面板

    def test_leader_panel_changes_only_the_two_growth_lines(self):
        """数值：追加两行改数字；第 4 节：原第 1、2 行（队长#0/#1 同条件）合并，其余行逐字、保序。"""
        old = self.live["cas"][M.CAS_LEADER][0][0].split("\n")
        new = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual((len(old), len(new)), (6, 5))
        self.assertEqual(new[0], "Fever中：赋予雷属性角色直接攻击伤害＋400%、攻击力＋200%")
        self.assertEqual(new[1:3], old[2:4])
        self.assertEqual(new[3], "雷属性共鸣时，自身技能每命中1次，自身攻击力＋35%")
        self.assertEqual(new[4], "每次进入Fever：雷属性角色直击伤害＋105%")
        self.assertEqual(tuple(old[4:]), M2.LEADER_ADDED_LINES)

    def test_panel_agrees_with_the_data(self):
        leader = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual(leader[3], f"雷属性共鸣时，自身技能每命中1次，自身攻击力＋{int(self.new2[3][51]) // 1000}%")
        self.assertEqual(leader[4], f"每次进入Fever：雷属性角色直击伤害＋{int(self.new_leader[4][49]) // 1000}%")
        rows = self.new_leader
        self.assertEqual(leader[0], f"Fever中：赋予雷属性角色直接攻击伤害＋{int(rows[0][111]) // 1000}%、"
                                    f"攻击力＋{int(rows[1][111]) // 1000}%")
        six = self.live["ability"][M.ABILITY6_KEY]
        self.assertEqual(self.out["cas"][M.CAS_ABILITY6][0][0],
                         f"雷属性角色免疫麻痹效果、生命值＋{int(six[1][51]) // 1000}%")
        cap = self.new2[0]
        self.assertEqual(self.out["cas"][M.CAS_ABILITY2][0][0].split("\n")[0],
                         f"雷属性共鸣时，自身技能每命中1次，队长攻击力＋{int(cap[51]) // 1000}%，最多{cap[34]}次")
        self.assertEqual(M.ability2_line(cap), M.NEW_ABILITY2_LINES[0])
        self.assertEqual(M.ability2_line(self.old2[0]), M.OLD_ABILITY2_LINES[0])

    def test_panel_obeys_the_project_rules(self):
        for key, rows in self.out["cas"].items():
            self.assertEqual(M.panel_rule_problems(key, rows[0][0]), [], key)
            for line in rows[0][0].split("\n"):
                self.assertEqual(KL.panel_problems(line.replace(K.MAIN_ICON, "")), [], line)
                # 队长块与能力6（c1=true）不带图标；能力3（主位限制，c1=false）每行带
                self.assertEqual(line.startswith(K.MAIN_ICON), key == M.CAS_ABILITY3, line)
                self.assertNotIn("／", line)
                for word in ("自身为队长时", "觉醒后", "可无限", "无上限", "生命值100%以下", "属性共鸣时："):
                    self.assertNotIn(word, line)

    # ------------------------------------------------------------ 第 4 节：面板同条件合并

    def test_merged_panels_verbatim(self):
        self.assertEqual(self.out["cas"][M.CAS_LEADER], [["\n".join((
            "Fever中：赋予雷属性角色直接攻击伤害＋400%、攻击力＋200%",
            "自身Fever持续时间延长＋25%",
            "雷属性共鸣时，非Fever状态下：发动技能，自身Fever槽＋50%",
            "雷属性共鸣时，自身技能每命中1次，自身攻击力＋35%",
            "每次进入Fever：雷属性角色直击伤害＋105%",
        ))]])
        self.assertEqual(self.out["cas"][M.CAS_ABILITY6], [["雷属性角色免疫麻痹效果、生命值＋25%"]])
        self.assertEqual(self.live["cas"][M.CAS_ABILITY6], [["雷属性角色免疫麻痹效果\n雷属性角色生命值＋25%"]])

    def test_merge_keeps_every_effect_and_only_drops_the_repeated_object(self):
        for key, (before, after, groups, _data) in M.PANEL_MERGES.items():
            shared = M.MERGE_SHARED_PREFIX[key]
            self.assertEqual(M.merge_lines(key), after, key)
            for j, src in groups.items():
                self.assertEqual(after[j], before[src[0]] + "、" + "、".join(before[i][len(shared):] for i in src[1:]))
                self.assertEqual(M.MERGED_LINES[after[j]], tuple(before[i] for i in src))
            # 未并的行逐字保序；效果数值记号多重集合不变
            rest = [line for i, line in enumerate(before) if not any(i in s for s in groups.values())]
            self.assertEqual([line for j, line in enumerate(after) if j not in groups], rest, key)
            signed = re.compile(r"[＋－]\d+(?:\.\d+)?%?")
            self.assertEqual(Counter(signed.findall("\n".join(before))), Counter(signed.findall("\n".join(after))))

    def test_merge_rows_share_every_condition_column(self):
        report = M.merge_data_checks({("leader", M.LEADER_KEY): self.new_leader,
                                      ("ability", M.ABILITY6_KEY): self.live["ability"][M.ABILITY6_KEY]})
        self.assertEqual(report[M.CAS_LEADER]["differing_columns"], [107, 111, 112])   # 效果 kind + 强度
        self.assertEqual(report[M.CAS_LEADER]["kinds"], ["1", "0"])                  # Direct伤害 / 攻击力
        self.assertEqual(report[M.CAS_ABILITY6]["differing_columns"], [47, 51, 52])
        self.assertEqual(report[M.CAS_ABILITY6]["kinds"], ["69", "205"])             # 麻痹无效 / HP
        self.assertEqual(self.out["notes"]["panel_merge"]["data"], report)
        # 任一条件列不同（触发 / 对象 / c1 / 次数上限）⇒ 不许合并 ⇒ revise() 拒绝
        for kind, key, index, col, value in (("leader", M.LEADER_KEY, 1, 95, "8"),
                                             ("leader", M.LEADER_KEY, 1, 109, "Red"),
                                             ("ability", M.ABILITY6_KEY, 1, 1, "false"),
                                             ("ability", M.ABILITY6_KEY, 1, 34, "3")):
            tables = {("leader", M.LEADER_KEY): deepcopy(self.new_leader),
                      ("ability", M.ABILITY6_KEY): deepcopy(self.live["ability"][M.ABILITY6_KEY])}
            tables[kind, key][index][col] = value
            with self.assertRaisesRegex(M.KuroBalanceCError, "differ outside the effect", msg=f"{key} c{col}"):
                M.merge_data_checks(tables)

    def test_check_merge_passes(self):
        """仓库内校验器 ``wf_panel_merge_check.check``（硬依赖）：两个合并组。队长 / 能力6 原文里没有「共鸣时：」，
        口径 3 规范化是恒等（显式核对），直接以数值改后文案为原文。"""
        for key, (before, after, groups, _data) in M.PANEL_MERGES.items():
            origin = "\n".join(before)
            self.assertEqual(re.sub(r"([火水雷风光暗]属性共鸣时)：", r"\1，", origin), origin, key)
            result = PMC.check(origin, "\n".join(after), [])
            self.assertTrue(result["ok"], (key, result["errors"]))
            self.assertEqual(result["warnings"], [], key)
            kinds = result["columns"][0]["kinds"]
            self.assertEqual(sorted(j for j, kind in kinds.items() if kind == "merge"), [j + 1 for j in groups], key)
            # 负对照：合并行漏掉一个效果 ⇒ 校验器必须拒绝
            broken = list(after)
            broken[min(groups)] = before[groups[min(groups)][0]]
            self.assertFalse(PMC.check(origin, "\n".join(broken), [])["ok"], key)

    # ------------------------------------------------------------ 第 5 节 / 第 7 节：能力3 面板（口径 3 + R2 删行）

    @staticmethod
    def _normalized_ability3(live_text: str) -> str:
        """校验原文的规范化步骤（显式写出，不借模块函数）：
        1. 第 7 节 R2：删去第 5、6 行（旗号 1 开支的随机抽取表、骰运 6 层翻倍表；定性并入能力1 强化条目）；
        2. 口径 3：「X属性共鸣时：」→「X属性共鸣时，」（能力3 没有「共鸣时：」后换行接效果的行，无需并行）。"""
        lines = live_text.split("\n")
        assert lines[4].startswith(M.MAIN_ICON + "强化技能：") and lines[5] == M.MAIN_ICON + FD.TEXT, lines[4:]
        return re.sub(r"([火水雷风光暗]属性共鸣时)：", r"\1，", "\n".join(lines[:4]))

    def test_ability3_panel_verbatim(self):
        icon = M.MAIN_ICON
        self.assertEqual(self.out["cas"][M.CAS_ABILITY3], [["\n".join((
            icon + "雷属性共鸣时，非Fever状态下：雷属性角色直接攻击合计每达到45次，自身Fever槽＋35%",
            icon + "每次进入Fever：雷属性角色直击伤害＋40%，最多3次",
            icon + "Fever中：雷属性角色每直击20次，自身Fever槽－50%",
            icon + "雷属性共鸣时，雷属性角色每直击500次，自身「骰运」＋1层，最多6层",
        ))]])

    def test_ability3_changes_only_punctuation_and_drops_the_enhancement_lines(self):
        old = self.live["cas"][M.CAS_ABILITY3][0][0].split("\n")
        new = self.out["cas"][M.CAS_ABILITY3][0][0].split("\n")
        self.assertEqual((len(old), len(new)), (6, 4))
        self.assertEqual(new[:3], old[:3])                                                # 其余行逐字
        self.assertEqual(new[3], old[3].replace("雷属性共鸣时：", "雷属性共鸣时，"))          # 口径 3：只改标点
        self.assertEqual(sorted(M.ABILITY3_FIXES), [3])
        # R2 删掉的两行 = live 第 5、6 行逐字（第 6 行 = full_dice.TEXT 原文）；两行都带数值与秒数、都在旗号 1 开支
        self.assertEqual(sorted(M.ABILITY3_R2_DROPS), [4, 5])
        for index, (text, _why) in M.ABILITY3_R2_DROPS.items():
            self.assertEqual(old[index], M.MAIN_ICON + text)
            self.assertTrue(re.search(r"\d", text) and ("秒" in text or "%" in text), text)
        self.assertEqual(old[5], M.MAIN_ICON + FD.TEXT)
        self.assertTrue(old[4].startswith(M.MAIN_ICON + "强化技能："))
        for line in new:
            self.assertNotIn("强化", line)
        # 删行不带走任何数据行的文案：能力3 #0–#3 仍各有一行（#3 = 骰运获取，最多 6 层 = 轮盘数 / 翻倍门槛）
        self.assertIn(f"最多{M.DICE_MAX}层", new[3])

    def test_ability3_check_merge_with_explicit_normalisation(self):
        live = self.live["cas"][M.CAS_ABILITY3][0][0]
        new = self.out["cas"][M.CAS_ABILITY3][0][0]
        origin = self._normalized_ability3(live)
        self.assertEqual(origin, new)                             # 规范化后即最终文案：本块无合并、无前缀省略
        self.assertNotIn("属性共鸣时：", origin)
        self.assertNotIn("／", origin)
        result = PMC.check(origin, new, [])
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(set(result["columns"][0]["kinds"].values()), {"verbatim"})
        # 负对照：不做规范化 ⇒ 第 4 行（改标点）与删掉的两行都被当成未授权改写
        raw = PMC.check(live, new, [])
        self.assertFalse(raw["ok"])

    def test_resonance_normalisation_helper(self):
        self.assertEqual(M.normalize_resonance("雷属性共鸣时：A\nB"), "雷属性共鸣时，A\nB")
        self.assertEqual(M.normalize_resonance("雷属性共鸣时：\nA＋1%\nB"), "雷属性共鸣时，A＋1%\nB")
        icon = M.MAIN_ICON
        self.assertEqual(M.normalize_resonance(icon + "Fever中，雷属性共鸣时：\n" + icon + "A＋1%"),
                         icon + "Fever中，雷属性共鸣时，A＋1%")
        self.assertEqual(M.normalize_resonance("Fever中：A"), "Fever中：A")           # 非共鸣条件的冒号不动
        for key, rows in self.out["cas"].items():
            self.assertEqual(M.normalize_resonance(rows[0][0]), rows[0][0], key)      # 返回面板已是规范写法
        self.assertEqual(M.panel_rule_problems("k", "雷属性共鸣时：A"), ["k: resonance must read 「X属性共鸣时，」"])
        self.assertEqual(M.panel_rule_problems("k", "A／B"), ["k: panel still carries 「／」"])

    def test_generator_ability3_panel_drops_the_enhancement_lines(self):
        """生成器能力3 面板 = 本轮 4 行（不带图标，图标由 _override_text 按 c1 加）；full_dice.TEXT（DSL 翻倍模块注记）本身不动。"""
        self.assertEqual(tuple(K.PANEL_ABILITY[3]), tuple(line.replace(M.MAIN_ICON, "") for line in M.NEW_ABILITY3_LINES))
        self.assertFalse(hasattr(K, "FULL_DICE_PANEL_TEXT"))
        self.assertIn("／", FD.TEXT)
        for line in K.PANEL_ABILITY[3]:
            self.assertNotIn("强化", line)
            self.assertNotIn(line, (FD.TEXT, M.FULL_DICE_LINE_SPLIT))

    def test_no_resonance_prefix_is_dropped(self):
        """共鸣省略依据：「豹步」获取行（能力2#2）无前置 ⇒ 不是共鸣隐含状态；「骰运」的效果行本来就没写共鸣。
        所以本轮只合并、不删任何「雷属性共鸣时，」：新旧面板里该前缀出现次数相同。"""
        self.assertEqual(M.step_basis(self.old2), f"{M.ABILITY2_KEY}#2（461，无前置）")
        for key, rows in self.out["cas"].items():
            self.assertEqual(rows[0][0].count("属性共鸣时"), self.live["cas"][key][0][0].count("属性共鸣时"), key)
        rows = deepcopy(self.old2)
        rows[2][6], rows[2][9], rows[2][10], rows[2][11] = "2", "600000", "600000", "Yellow"
        with self.assertRaisesRegex(M.KuroBalanceCError, "豹步"):
            M.step_basis(rows)

    @unittest.skipUnless(_baseline_available(), "需要 live store")
    def test_state_sources_against_the_whole_live_store(self):
        import wf_midautumn_common as MC
        import wf_midautumn_specs as MS
        import wf_seasonal7_build as B
        ctx = B.KitContext(MC.MAPack(MS.get_spec(K.KEY), record_sources=False))
        grants = {M.UID_DICE: [], M.UID_STEP: []}
        for table, ic, pres in ((KL.ABILITY, 47, (6, 13, 20)), (KL.LEADER, 45, (4, 11, 18))):
            for key, text in ctx.live_flat(table).items():
                for index, row in enumerate(ctx.csv_split(text)):
                    row = row + [""] * (130 - len(row))
                    if row[ic] in ("461", "413", "436", "459") and row[ic + 21] in grants:
                        resonance = [row[b + 5] for b in pres
                                     if (row[b], row[b + 3], row[b + 4]) == ("2", "600000", "600000")]
                        grants[row[ic + 21]].append((f"{key}#{index}", resonance))
        self.assertEqual(grants, {M.UID_DICE: [(f"{M.CID}3#3", ["Yellow"])],
                                  M.UID_STEP: [(f"{M.ABILITY2_KEY}#2", [])]})

    # ------------------------------------------------------------ fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["ability"][M.ABILITY2_KEY][3][51] = "mutated"
        out["leader"][M.LEADER_KEY][4][0] = "mutated"
        out["cas"][M.CAS_LEADER][0][0] = "mutated"
        self.assertEqual(data, self.live)

    def test_revise_is_deterministic(self):
        self.assertEqual(M.revise(reader(deepcopy(self.live))), self.out)

    def test_baseline_drift_is_rejected(self):
        for kind, key, mutate in (
                ("leader", M.LEADER_KEY, lambda v: v[4].__setitem__(49, "40000")),
                ("ability", M.ABILITY2_KEY, lambda v: v[3].__setitem__(51, "6000")),
                ("cas", M.CAS_LEADER, lambda v: v[0].__setitem__(0, v[0][0] + "\nx")),
                ("cas", M.CAS_ABILITY3, lambda v: v[0].__setitem__(0, v[0][0].replace("500次", "1000次"))),
                ("ability", M.ABILITY6_KEY, lambda v: v[1].__setitem__(51, "30000")),
                ("cas", M.CAS_ABILITY6, lambda v: v[0].__setitem__(0, v[0][0] + "。")),
                ("ability", M.ABILITY2_KEY, lambda v: v[0].__setitem__(34, "(None)")),
                ("cas", M.CAS_ABILITY2, lambda v: v[0].__setitem__(0, v[0][0].replace("＋2%", "＋5%"))),
                # 第 7 节补读的键（全部只读）：任一漂移都拒绝
                ("cas", M.CAS_SWITCH, lambda v: v[0].__setitem__(0, v[0][0].replace("，并按直接攻击伤害判定", ""))),
                ("cas", M.CAS_ABILITY1, lambda v: v[0].__setitem__(0, v[0][0].replace("：强化技能", "，强化技能"))),
                ("ability", M.ABILITY1_KEY, lambda v: v[1].__setitem__(1, "false")),
                ("ability", M.ABILITY3_KEY, lambda v: v[3].__setitem__(30, "100000000")),
                ("ability", M.ABILITY4_KEY, lambda v: v[0].__setitem__(35, "0")),
                ("ability", M.ABILITY5_KEY, lambda v: v[0].__setitem__(51, "30000")),
                ("dsl", M.PROGRAMS["1"], lambda v: v.__setitem__(1, 3)),
                ("dsl", M.PROGRAMS["2"], lambda v: v.__setitem__(1, 3)),
                ("action", M.CODE, lambda v: v[0][1].__setitem__(1, v[0][1][1] + "／强化后：随机增益")),
                ("text", M.CID, lambda v: v[0].__setitem__(7, v[0][7] + "x")),
                ("server_text", M.CID, lambda v: v[0].__setitem__(5, v[0][5] + "x"))):
            data = deepcopy(self.live)
            mutate(data[kind][key])
            with self.assertRaisesRegex(M.KuroBalanceCError, "unreviewed live baseline", msg=f"{kind}:{key}"):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        for kind in ("leader", "ability", "cas"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaises(M.KuroBalanceCError):
            M.revise(reader(data))
        with self.assertRaises(M.KuroBalanceCError):
            M.ability2_rows(self.new2)
        with self.assertRaises(M.KuroBalanceCError):
            M.leader_rows(self.new_leader)
        with self.assertRaises(M.KuroBalanceCError):
            M.leader_text(self.out["cas"][M.CAS_LEADER])
        with self.assertRaises(M.KuroBalanceCError):
            M.ability6_text(self.out["cas"][M.CAS_ABILITY6])
        with self.assertRaises(M.KuroBalanceCError):
            M.ability3_text(self.out["cas"][M.CAS_ABILITY3])
        with self.assertRaises(M.KuroBalanceCError):
            M.ability2_text(self.out["cas"][M.CAS_ABILITY2])
        with self.assertRaises(M.KuroBalanceCError):
            M.ability1_text(self.out["cas"][M.CAS_ABILITY1])
        with self.assertRaises(M.KuroBalanceCError):
            M.switch_text(self.out["cas"][M.CAS_SWITCH])
        half = deepcopy(self.old2)                     # 只有 #0 已是 5%（#3 仍是第二批）⇒ 封顶版不能再改一次
        half[0] = list(self.new2[0])
        with self.assertRaisesRegex(M.KuroBalanceCError, "capped skill-hit row"):
            M.ability2_rows(half)

    def test_row_locators_are_content_based(self):
        for mutate in (lambda r: r[3].__setitem__(6, "0"),              # 不再仅队长
                       lambda r: r[3].__setitem__(80, "x"),
                       lambda r: r.insert(0, list(r[0])),
                       lambda r: r[0].__setitem__(34, "30"),            # 封顶版次数上限不是 25
                       lambda r: r[0].__setitem__(48, "0"),             # 封顶版不再给队长
                       lambda r: r[0].__setitem__(80, "x")):
            rows = deepcopy(self.old2)
            mutate(rows)
            with self.assertRaises(M.KuroBalanceCError):
                M.ability2_rows(rows)
        for mutate in (lambda r: r[4].__setitem__(25, "23"),
                       lambda r: r.pop()):
            rows = deepcopy(self.old_leader)
            mutate(rows)
            with self.assertRaises(M.KuroBalanceCError):
                M.leader_rows(rows)


def _flag(tree) -> list:
    (flag,) = M._commands(tree, "ConditionalsChangeSkillFlag")
    return flag


def _wheel_gate(tree, wheel: int, option: int) -> list:
    """开支第 ``wheel`` 个轮盘第 ``option`` 项的「骰运 ≥6」翻倍门（参数表，引用树内节点，可就地改）。"""
    wheels = M._commands(_flag(tree)[2], "ConditionalsProbability")
    return wheels[wheel][1][1][option][1][1][1][0][1]


def _set_numbers(payload, value) -> None:
    for node in (payload if isinstance(payload, list) else [payload]):
        if isinstance(node, dict) and "min" in node:
            node["min"] = node["max"] = value
        elif isinstance(node, list):
            _set_numbers(node, value)


class SkillEnhancementTests(unittest.TestCase):
    """第 7 节（R1–R4）：强化条目官方格式定性、能力1 第 2 行同文加共鸣前缀、能力3 删 R2 两行、技能描述不改；
    依据（开关行唯一 / 两档 DSL 旗号开支 / 技能描述只写本体）逐条核对，每条依据做变异：改了就必须拒绝。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.trees = {program: cls.live["dsl"][program] for program in M.PROGRAMS.values()}
        cls.abilities = {key: cls.live["ability"][key] for key in M.ABILITY_KEYS}
        cls.leader = cls.live["leader"][M.LEADER_KEY]

    # ------------------------------------------------------------ R2：条目

    def test_entry_verbatim_and_official_format(self):
        self.assertEqual(self.live["cas"][M.CAS_SWITCH], [["强化『博饼·满堂彩』：摇碗的持续时间延长，威力随连击数提升，"
                                                           "并按直接攻击伤害判定"]])
        self.assertEqual(self.out["cas"][M.CAS_SWITCH], [[
            "强化『博饼·满堂彩』：摇碗的持续时间延长，威力随连击数提升；释放后随机抽取增益（攻击力提升、Fever槽上升、贯穿效果、"
            "直接攻击伤害提升、连击增加、队长技能槽上升），抽取次数随「骰运」层数提升，「骰运」达到上限时增益效果提升"]])
        text = self.out["cas"][M.CAS_SWITCH][0][0]
        self.assertTrue(text.startswith("强化『博饼·满堂彩』："))             # 官方格式、点名技能（= action_skill c0）
        self.assertEqual(KL.panel_problems(text, skill_flag=True), [])        # 无数字 / 秒 / %
        self.assertIsNone(re.search(r"\d|秒|%|％", text))
        for word in ("伤害判定", "强化技能", "属性共鸣时", "担任队长", "强化后", "——", "／"):
            self.assertNotIn(word, text)
        self.assertEqual(M.flag_entry_problems(text), [])
        self.assertEqual(self.out["notes"]["skill_enhancement"]["entry"]["to"], text)

    def test_entry_keeps_the_old_enhancements_and_drops_only_the_body_attribution(self):
        head = M.OLD_SWITCH_TEXT.split("，并按直接攻击伤害判定")[0]
        self.assertTrue(M.NEW_SWITCH_TEXT.startswith(head))                   # 原两项强化逐字保留在开头
        self.assertEqual(list(M.SWITCH_REMOVED), ["并按直接攻击伤害判定"])
        self.assertIn("（以直接攻击伤害判定）", M.SKILL_DESC)                   # 技能本体已写
        # 能力3 删掉的抽取表逐项在条目里有定性对应（原文名 → 条目名）；翻倍行 → 「达到上限时增益效果提升」
        roulette, full = M.ABILITY3_R2_DROPS[4][0], M.ABILITY3_R2_DROPS[5][0]
        for old, new in (("攻击力＋500%", "攻击力提升"), ("Fever槽大幅上升", "Fever槽上升"), ("贯穿效果", "贯穿效果"),
                         ("直击伤害＋500%", "直接攻击伤害提升"), ("连击＋500", "连击增加"), ("队长技能槽＋15%", "队长技能槽上升")):
            self.assertIn(old, roulette)
            self.assertIn(new, M.NEW_SWITCH_TEXT)
        self.assertIn("抽取次数随「骰运」层数提升", roulette)
        self.assertIn("抽取次数随「骰运」层数提升", M.NEW_SWITCH_TEXT)
        self.assertTrue(full.startswith("「骰运」达到6层时，上述抽取奖励翻倍"))
        self.assertIn("「骰运」达到上限时增益效果提升", M.NEW_SWITCH_TEXT)

    def test_entry_checker_rejects_bad_entries(self):
        for bad in (M.OLD_SWITCH_TEXT,
                    M.NEW_SWITCH_TEXT.replace("「骰运」达到上限时", "「骰运」达到6层时"),
                    "雷属性共鸣时，" + M.NEW_SWITCH_TEXT,
                    M.NEW_SWITCH_TEXT.replace("强化『博饼·满堂彩』：", "强化技能："),
                    M.NEW_SWITCH_TEXT.replace("，抽取次数随「骰运」层数提升", ""),
                    M.NEW_SWITCH_TEXT.replace("攻击力提升、", ""),
                    M.NEW_SWITCH_TEXT + "（持续15秒）",
                    M.NEW_SWITCH_TEXT + "，并按直接攻击伤害判定"):
            self.assertTrue(M.flag_entry_problems(bad), bad)

    def test_ability1_panel(self):
        old = self.live["cas"][M.CAS_ABILITY1][0][0].split("\n")
        new = self.out["cas"][M.CAS_ABILITY1][0][0].split("\n")
        self.assertEqual(tuple(old), M.OLD_ABILITY1_LINES)
        self.assertEqual(len(new), 2)
        self.assertEqual(new[0], old[0])                                               # 第 1 行逐字
        self.assertEqual(new[1], "雷属性共鸣时，" + self.out["cas"][M.CAS_SWITCH][0][0])  # 开关行：共鸣前缀 + 条目
        for line in new:
            self.assertFalse(line.startswith(K.MAIN_ICON), line)                       # 开关行 c1=true
        switch = self.live["ability"][M.ABILITY1_KEY][M.SWITCH_ROW]
        self.assertEqual((switch[1], switch[6], switch[11], switch[47], switch[70]),
                         ("true", "2", "Yellow", "536", M.CAS_SWITCH))
        self.assertEqual(D.describe_line(switch, "ability"), f"雷·编成≥6 时: 自身 切换技能形态[{M.CAS_SWITCH}]")
        # 仓库内校验器：原文 = live 换上 R2 条目行 ⇒ 逐字；直接拿 live 比 ⇒ 第 2 行是未授权改写
        origin = "\n".join((old[0], M.ABILITY1_SWITCH_LINE))
        result = PMC.check(origin, "\n".join(new), [])
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(set(result["columns"][0]["kinds"].values()), {"verbatim"})
        self.assertFalse(PMC.check("\n".join(old), "\n".join(new), [])["ok"])
        self.assertEqual(self.out["notes"]["panel_merge"]["no_merge"][M.CAS_ABILITY1], M.ABILITY1_NO_MERGE)

    def test_no_numeric_or_old_enhancement_text_left_on_returned_panels(self):
        joined = "\n".join(rows[0][0] for rows in self.out["cas"].values())
        for text in (M.ABILITY3_R2_DROPS[4][0], M.ABILITY3_R2_DROPS[5][0], M.FULL_DICE_LINE_SPLIT, M.OLD_SWITCH_TEXT,
                     "强化技能", "伤害判定"):
            self.assertNotIn(text, joined)
        # 强化描述只出现在条目本身与能力1 开关行（R2）
        self.assertEqual(sorted(key for key, rows in self.out["cas"].items() if "强化『" in rows[0][0]),
                         sorted((M.CAS_SWITCH, M.CAS_ABILITY1)))

    # ------------------------------------------------------------ R1：数据依据

    def test_switch_basis(self):
        basis = M.switch_basis(self.abilities, self.leader)
        self.assertEqual(self.out["notes"]["skill_enhancement"]["switch"], basis)

        def grant_dice_elsewhere(a, _l):
            a[M.ABILITY4_KEY][0][47], a[M.ABILITY4_KEY][0][68] = "461", M.UID_DICE

        mutations = {
            "ability3 gains a switch row": lambda a, _l: a[M.ABILITY3_KEY][0].__setitem__(47, "704"),
            "leader gains a switch row": lambda _a, l: l[0].__setitem__(107, "536"),
            "switch row becomes main-only": lambda a, _l: a[M.ABILITY1_KEY][1].__setitem__(1, "false"),
            "switch row loses resonance": lambda a, _l: a[M.ABILITY1_KEY][1].__setitem__(6, "0"),
            "switch row points elsewhere": lambda a, _l: a[M.ABILITY1_KEY][1].__setitem__(70, "x"),
            "ability1 line-1 data drifts": lambda a, _l: a[M.ABILITY1_KEY][0].__setitem__(51, "30000"),
            "dice granted elsewhere": grant_dice_elsewhere,
        }
        for name, mutate in mutations.items():
            abilities, leader = deepcopy(self.abilities), deepcopy(self.leader)
            mutate(abilities, leader)
            with self.assertRaises(M.KuroBalanceCError, msg=name):
                M.switch_basis(abilities, leader)

    # ------------------------------------------------------------ R1：DSL 依据

    def test_skill_flag_basis_against_both_trees(self):
        report = M.skill_flag_basis(self.trees)
        self.assertEqual(report, self.out["notes"]["skill_enhancement"]["dsl"])
        for level in M.ACTION_LEVELS:
            self.assertEqual(report[level]["wheels"], M.DICE_MAX)
            self.assertEqual(report[level]["draw_gates"], [2, 3, 4, 5, 6])
            self.assertEqual(report[level]["rewards"], list(M.REWARD_LABELS))
            self.assertEqual(report[level]["attribution_both_branches"], 4)
        # 旋钮 = 生成器 _enhance_event 的常量（寿命 ×1 + 特效寿命 ×2、段数 min/max、连击加成、收碗等待）
        knobs = Counter()
        knobs[tuple(map(str, K.HITAREA_LIFETIME))] += 1
        knobs[tuple(map(str, K.EFFECT_LIFETIME))] += 2
        knobs[tuple(map(str, K.HITAREA_MAX_HITS))] += 2
        knobs[tuple(map(str, K.CLOSE_WAIT))] += 1
        knobs[("false", "true")] += 1
        self.assertEqual(M.ENHANCED_KNOBS, knobs)
        self.assertEqual((K.ROULETTE_SLOTS, K.DICE_CAP, K.UID_DICE, K.LEADER_SELECTOR, K.HITAREA_BUFF_TARGET_AS),
                         (M.DICE_MAX, str(M.DICE_MAX), M.UID_DICE, M.LEADER_SELECTOR, M.DIRECT_ATTRIBUTION))

    def test_skill_flag_basis_rejects_every_mutation(self):
        def statements(tree):
            return tree[11][1]

        def combo_not_enhanced(tree):
            M._commands(_flag(tree)[2][1][0], "CreateNormalAttack")[0][8] = False

        def attribution_differs(tree):
            M._commands(_flag(tree)[3], "CreateHitArea")[0][24] = 0

        def attribution_auto_both(tree):
            for branch in _flag(tree)[2:4]:
                M._commands(branch[1][0], "CreateHitArea")[0][24] = 0

        def plain_lives_longer(tree):
            M._commands(_flag(tree)[3], "CreateHitArea")[0][13] = ["SpecifyHitAreaLifetimeDirectly", 180]

        def fewer_wheels(tree):
            on = _flag(tree)[2]
            on[1] = on[1][:2]

        def draw_gate_threshold(tree):
            gates = [g for g in M._commands(_flag(tree)[2], "ConditionalsConditionAccumulationNumber")
                     if M._commands(g[3], "ConditionalsProbability")]
            gates[0][2] = 3

        def unequal_weight(tree):
            wheels = M._commands(_flag(tree)[2], "ConditionalsProbability")
            wheels[0][1][1][0][1][0] = ["Command", ["ProbabilityWeight", 5]]

        def doubled_not_double(tree):
            _set_numbers(_wheel_gate(tree, 0, 0)[3][1][0][1][2][0][2], 7.0)

        def reward_is_a_loss(tree):
            gate = _wheel_gate(tree, 0, 1)                                    # Fever 项：原值与翻倍同改为负
            _set_numbers(gate[4][1][0][1][1], -250)
            _set_numbers(gate[3][1][0][1][1], -500)

        def reward_swapped(tree):
            gate = _wheel_gate(tree, 0, 4)                                    # 连击项换成攻击力项
            gate[3], gate[4] = deepcopy(_wheel_gate(tree, 0, 0)[3]), deepcopy(_wheel_gate(tree, 0, 0)[4])

        def roulette_in_plain(tree):
            flag = _flag(tree)
            flag[3][1].append(deepcopy(flag[2][1][1]))

        def endlag_restored(tree):
            M._commands(statements(tree), "StopBall")[0][3] = ["Stop"]

        def team_buff_changed(tree):
            team = [c for c in M._commands(statements(tree), "FindAllSubjects") if c[2] == 33][0]
            M._commands(team, "CreateCondition")[1][2][0][0] = "ACSpeedup"

        def second_flag(tree):
            statements(tree).append(["Command", ["ConditionalsChangeSkillFlag", 2, ["Block", []], ["Block", []]]])

        for mutate in (combo_not_enhanced, attribution_differs, attribution_auto_both, plain_lives_longer, fewer_wheels,
                       draw_gate_threshold, unequal_weight, doubled_not_double, reward_is_a_loss, reward_swapped,
                       roulette_in_plain, endlag_restored, team_buff_changed, second_flag):
            for program in M.PROGRAMS.values():
                trees = deepcopy(self.trees)
                mutate(trees[program])
                with self.assertRaises(M.KuroBalanceCError, msg=f"{mutate.__name__} {program}"):
                    M.skill_flag_basis(trees)

    # ------------------------------------------------------------ R3：技能描述

    def test_skill_description_is_body_only_and_unchanged(self):
        action, text, server = (self.live["action"][M.CODE], self.live["text"][M.CID], self.live["server_text"][M.CID])
        basis = M.skill_desc_basis(action, text, server)
        self.assertEqual(self.out["notes"]["skill_enhancement"]["skill_description"], basis)
        self.assertEqual((K.TEXTS["desc1"], K.TEXTS["desc2"]), (M.SKILL_DESC, M.SKILL_DESC))
        self.assertEqual((K.TEXTS["skill1"], K.TEXTS["skill2"]), (M.SKILL_NAME, M.SKILL_NAME + "＋"))
        self.assertEqual([fields[1] for _inner, fields in action], [M.SKILL_DESC] * 2)
        self.assertEqual([text[0][5], text[0][7], server[0][5], server[0][7]], [M.SKILL_DESC] * 4)
        for word in ("强化", "骰运", "随机", "抽取", "连击数", "共鸣", "Fever"):
            self.assertNotIn(word, M.SKILL_DESC)
        for kind in ("action", "text", "server_text", "dsl"):
            self.assertEqual(self.out[kind], {}, kind)
        # 变异：任一处混进强化描述 / 与 action c1 不一致 ⇒ 拒绝
        leak = M.SKILL_DESC + "／雷属性共鸣时强化：释放后随机抽取增益"
        bad_action = deepcopy(action)
        bad_action[0][1][1] = leak
        bad_text = deepcopy(text)
        bad_text[0][7] = leak
        bad_server = deepcopy(server)
        bad_server[0][5] = M.SKILL_DESC.replace("持续造成", "造成")
        for args in ((bad_action, text, server), (action, bad_text, server), (action, text, bad_server)):
            with self.assertRaises(M.KuroBalanceCError):
                M.skill_desc_basis(*args)


class ChainTests(unittest.TestCase):
    """第三轮排在第二批之后：第二批 revise() 的输出 == 第三轮的 live 输入。"""

    def test_batch2_output_is_the_batch3_input(self):
        live = load_fixture()
        after_b = batch2_live()
        for kind, key in M.BEFORE:
            self.assertEqual(after_b[kind][key], live[kind][key], f"{kind}:{key}")

    @unittest.skipUnless(MANIFEST.is_file(), "candidate workspace ma-kuro not present")
    def test_package_version_moves_forward(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        current, new = _version(manifest["package_version"]), _version(M.PACKAGE_VERSION["ma-kuro"])
        if current >= new:
            self.assertEqual(new, current)              # 已回写：候选现值 == 本模块版本
        else:
            self.assertEqual(current, _version(M2.PACKAGE_VERSION["ma-kuro"]))   # 回写前停在第二批
        self.assertTrue(set(M.CAPABILITIES) <= set(manifest["required_capabilities"]))

    @unittest.skipUnless(MANIFEST.is_file(), "candidate workspace ma-kuro not present")
    def test_candidate_equals_the_live_inputs(self):
        """回写前：候选 == 本轮 live 输入；回写后：候选 == live 输入 + 本轮 revise() 输出。"""
        import wf_share_update_codec as X
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        live = load_fixture()
        if _version(manifest["package_version"]) >= _version(M.PACKAGE_VERSION["ma-kuro"]):
            out = M.revise(reader(deepcopy(live)))
            for kind in ("leader", "ability", "cas"):
                live[kind].update(deepcopy(out[kind]))
        root = CANDIDATE / "package/roots/common"
        tables = {"leader": "master/ability/leader_ability.orderedmap",
                  "ability": "master/ability/ability.orderedmap",
                  "cas": "master/string/custom_ability_string.orderedmap"}
        for kind, logical in tables.items():
            rows = X.unpack((root / logical).read_bytes())
            for key, value in live[kind].items():
                self.assertEqual(X.csv_read(rows[key]), value, f"{kind}:{key}")


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_kuro 的行装配（官方 donor + 逐格改）== revise() 输出（其余键 == 第二批留下的 live）。"""

    @classmethod
    def setUpClass(cls):
        cls.out = M.revise(reader(load_fixture()))

    def test_generator_constants_equal_revise_output(self):
        donor, cells, expect = K.LEADER[M.FEVER_ROW]
        self.assertEqual((cells[49], cells[50]), tuple(self.out["leader"][M.LEADER_KEY][4][49:51]))
        self.assertEqual(expect, D.describe_line(self.out["leader"][M.LEADER_KEY][4], "leader_ability"))
        donor, cells, expect = K.ABILITY[M.ABILITY2_KEY][M.HIT_ROW]
        self.assertEqual((cells[51], cells[52]), tuple(self.out["ability"][M.ABILITY2_KEY][3][51:53]))
        self.assertEqual(expect, D.describe_line(self.out["ability"][M.ABILITY2_KEY][3], "ability"))
        donor, cells, expect = K.ABILITY[M.ABILITY2_KEY][M.CAP_ROW]              # 第 6 节
        self.assertEqual(cells, M.CAP_HIT_ROW | {51: "5000", 52: "5000"})       # 行形逐格同第二批，只换强度
        self.assertEqual((cells[51], cells[52]), tuple(self.out["ability"][M.ABILITY2_KEY][0][51:53]))
        self.assertEqual(expect, D.describe_line(self.out["ability"][M.ABILITY2_KEY][0], "ability"))

    def test_generator_panel_equals_revise_output(self):
        self.assertEqual(K.CAS_TEXTS[M.CAS_LEADER], self.out["cas"][M.CAS_LEADER][0][0])
        self.assertEqual(tuple(K.PANEL_LEADER), M.LEADER_PANEL_NEW)                # 第 4 节合并后 5 行
        self.assertEqual(K.CAS_TEXTS[M.CAS_ABILITY6], self.out["cas"][M.CAS_ABILITY6][0][0])
        self.assertEqual(K.CAS_ABILITY[6], M.CAS_ABILITY6)
        self.assertFalse(K._main_only(6))                                          # 能力6 不带主位图标
        # 第 5 节：能力3 面板（口径 3/5，数值不动）；主位限制槽每行带图标
        self.assertEqual(K.CAS_ABILITY[3], M.CAS_ABILITY3)
        self.assertEqual(K.CAS_TEXTS[M.CAS_ABILITY3], self.out["cas"][M.CAS_ABILITY3][0][0])
        self.assertTrue(K._main_only(3))
        # 第 6 节：能力2 面板第 1 行 2% → 5%
        self.assertEqual(K.CAS_ABILITY[2], M.CAS_ABILITY2)
        self.assertEqual(K.CAS_TEXTS[M.CAS_ABILITY2], self.out["cas"][M.CAS_ABILITY2][0][0])
        self.assertEqual(tuple(K.PANEL_ABILITY[2]), M.NEW_ABILITY2_LINES)
        self.assertFalse(K._main_only(2))
        # 第 7 节：强化条目（536 c70）与能力1 面板（开关行 c1=true ⇒ 不带图标）
        self.assertEqual(K.CAS_CHANGE_SKILL, M.CAS_SWITCH)
        self.assertEqual(K.SKILL_FLAG_TEXT_KEYS, (M.CAS_SWITCH,))
        self.assertEqual(K.CAS_SKILL_FLAG_TEXT, M.NEW_SWITCH_TEXT)
        self.assertEqual(K.CAS_TEXTS[M.CAS_SWITCH], self.out["cas"][M.CAS_SWITCH][0][0])
        self.assertEqual(K.CAS_ABILITY[1], M.CAS_ABILITY1)
        self.assertEqual(K.CAS_TEXTS[M.CAS_ABILITY1], self.out["cas"][M.CAS_ABILITY1][0][0])
        self.assertEqual(tuple(K.PANEL_ABILITY[1]), M.NEW_ABILITY1_LINES)
        self.assertFalse(K._main_only(1))
        self.assertEqual(K.ABILITY[M.ABILITY1_KEY][M.SWITCH_ROW][1], M.SWITCH_CELLS)   # 开关行格位 = 本模块核对的格位
        live = batch2_live()
        for key in K.CAS_TEXTS:                                                     # 其余覆盖键不在本轮返回
            if key.startswith("desc_override_") and key not in self.out["cas"] and key in live["cas"]:
                self.assertEqual(K.CAS_TEXTS[key], live["cas"][key][0][0], key)

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_trees_equal_live_and_satisfy_the_flag_basis(self):
        """第 7 节依据的来源：生成器两档技能树（官方母本 → mutate_tree → full_dice.apply）== live（fixture）逐节点相同，
        并通过 skill_flag_basis（本轮只改文字，树不动）。"""
        import wf_midautumn_common as MC
        import wf_midautumn_specs as MS
        import wf_seasonal7_build as B
        ctx = B.KitContext(MC.MAPack(MS.get_spec(K.KEY), record_sources=False))
        live = load_fixture()
        trees = {}
        for level, program in M.PROGRAMS.items():
            tree, _evidence = K.mutate_tree(ctx.template_dsl(K.donor_program(ctx, level)), level)
            trees[program] = FD.apply(tree)
            self.assertEqual(trees[program], live["dsl"][program], program)
        self.assertEqual(M.skill_flag_basis(trees), self.out["notes"]["skill_enhancement"]["dsl"])

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_rows_equal_revise_output(self):
        import wf_midautumn_common as MC
        import wf_midautumn_specs as MS
        import wf_seasonal7_build as B
        ctx = B.KitContext(MC.MAPack(MS.get_spec(K.KEY), record_sources=False))
        leader = [KL.build_row(ctx, "leader_ability", donor, cells, expect_describe=expect)[0]
                  for donor, cells, expect in K.LEADER]
        self.assertEqual(leader, self.out["leader"][M.LEADER_KEY])
        live = batch2_live()
        want = {M.ABILITY2_KEY: self.out["ability"][M.ABILITY2_KEY],
                M2.ABILITY3_KEY: live["ability"][M2.ABILITY3_KEY]}
        for key, rows_want in want.items():
            rows = []
            for donor, cells, expect in K.ABILITY[key]:
                source, _, donor_key = donor.partition("live:")
                source, donor_key = ("live", donor_key) if donor_key else ("official", source)
                rows.append(KL.build_row(ctx, "ability", donor_key, cells, source=source,
                                         element=K.ELEMENT, expect_describe=expect)[0])
            self.assertEqual(rows, rows_want, key)


@unittest.skipUnless((ROOT / M.DESIGN_REL).is_file() and (ROOT / M.PANEL_REL).is_file(),
                     "midautumn design mirrors not present")
class MirrorTests(unittest.TestCase):
    """设计镜像由主会话 ``python mod-tools/wf_balance_20260927c_kuro.py --write`` 落盘（本轮施工不写
    work/character_packs）。落盘前：在内存里同步后验证；落盘后：验证磁盘已同步。"""

    def setUp(self):
        self.disk = [json.loads((ROOT / rel).read_text(encoding="utf-8")) for rel in (M.DESIGN_REL, M.PANEL_REL)]
        self.synced = M.mirror_updates(*self.disk)

    def test_disk_is_synced_or_pending_exactly_this_round(self):
        """落盘后 pending 为空；落盘前（含本模块上一稿已 --write、第 7 节未写）pending = 内存同步后确有变化的文件。"""
        pending = M.sync_mirrors(ROOT)
        self.assertEqual(pending, [str(rel) for rel, old, new in zip((M.DESIGN_REL, M.PANEL_REL), self.disk, self.synced)
                                   if old != new])
        if M.MIRROR_TAG not in self.disk[0]:
            self.assertEqual(pending, [str(M.DESIGN_REL), str(M.PANEL_REL)])

    def test_synced_mirrors_match_the_generator(self):
        design, panel = self.synced
        self.assertEqual(M.mirror_updates(design, panel), (design, panel))      # 幂等
        rows = design["plan"]["leader_ability"]["rows"]
        self.assertEqual([r["desc_expected"] for r in rows], [e for _d, _c, e in K.LEADER])
        self.assertEqual(rows[4]["cells"]["49"], "105000")
        records = design["plan"]["ability"]["keys"][M.ABILITY2_KEY]["records"]
        self.assertEqual([r["desc_expected"] for r in records], [e for _d, _c, e in K.ABILITY[M.ABILITY2_KEY]])
        self.assertEqual(records[3]["cells"]["51"], "35000")
        self.assertEqual((records[0]["cells"]["34"], records[0]["cells"]["51"]), ("25", "5000"))   # 第 6 节
        two = next(entry for entry in panel["abilities"] if int(entry["index"]) == 2)
        self.assertEqual([line["text"] for line in two["lines"]], list(K.PANEL_ABILITY[2]))
        texts = {r["key"]: r["text"] for r in design["plan"]["texts"]["custom_ability_string"]["rows"]}
        self.assertEqual(texts, K.CAS_TEXTS)
        self.assertEqual([line["text"] for line in panel["leader"]["lines"]], list(K.PANEL_LEADER))
        six = next(entry for entry in panel["abilities"] if int(entry["index"]) == 6)
        self.assertEqual([line["text"] for line in six["lines"]], list(K.PANEL_ABILITY[6]))
        three = next(entry for entry in panel["abilities"] if int(entry["index"]) == 3)
        self.assertEqual([line["text"] for line in three["lines"]], list(K.PANEL_ABILITY[3]))
        one = next(entry for entry in panel["abilities"] if int(entry["index"]) == 1)
        self.assertEqual([line["text"] for line in one["lines"]], list(K.PANEL_ABILITY[1]))
        self.assertEqual(texts[M.CAS_SWITCH], M.NEW_SWITCH_TEXT)
        self.assertEqual(panel["notes"][-1], M.MIRROR_NOTE)
        self.assertEqual(sum(note.startswith("2026-09-27：作者平衡第三轮") for note in panel["notes"]), 1)
        self.assertEqual(panel["skill"], self.disk[1]["skill"])                 # R3：技能说明镜像不动

    def test_batch2_records_are_kept(self):
        design, panel = self.synced
        self.assertEqual(design[M2.MIRROR_TAG], self.disk[0][M2.MIRROR_TAG])
        self.assertIn(M2.MIRROR_NOTE, panel["notes"])
        for rel, old, new in zip(("design", "panel"), self.disk, self.synced):
            for key in set(old) - {"plan", "leader", "notes", "abilities", M.MIRROR_TAG}:
                self.assertEqual(new[key], old[key], f"{rel}:{key}")
        # 能力面板镜像只动能力1（第 7 节：第 2 行强化条目）、能力2（第 6 节：第 1 行数字）、能力3（口径 3 + R2 删行，
        # 按生成器整块同步）与能力6（合并）；其余槽逐字不动
        old_abilities = {int(e["index"]): e for e in self.disk[1]["abilities"]}
        for entry in panel["abilities"]:
            if int(entry["index"]) not in (1, 2, 3, 6):
                self.assertEqual(entry, old_abilities[int(entry["index"])])
        one = next(entry for entry in panel["abilities"] if int(entry["index"]) == 1)
        self.assertEqual({k: v for k, v in one.items() if k != "lines"},
                         {k: v for k, v in old_abilities[1].items() if k != "lines"})
        self.assertEqual(one["lines"][0], old_abilities[1]["lines"][0])        # 第 1 行逐字
        two = next(entry for entry in panel["abilities"] if int(entry["index"]) == 2)
        self.assertEqual({k: v for k, v in two.items() if k != "lines"},
                         {k: v for k, v in old_abilities[2].items() if k != "lines"})
        self.assertEqual(two["lines"][1], old_abilities[2]["lines"][1])        # 豹步行逐字
        three = next(entry for entry in panel["abilities"] if int(entry["index"]) == 3)
        self.assertEqual({k: v for k, v in three.items() if k != "lines"},
                         {k: v for k, v in old_abilities[3].items() if k != "lines"})

    def test_ability3_mirror_accepts_only_the_known_drift(self):
        """镜像能力3：只认第二批留下的已知漂移稿（1000 次、缺翻倍行）、本模块上一稿（口径 3/5 后、R2 前）或已同步稿，其余拒绝。"""
        design, panel = deepcopy(self.disk)
        three = next(entry for entry in panel["abilities"] if int(entry["index"]) == 3)
        for old in (M.MIRROR_ABILITY3_DRIFTED, M.PREVIOUS_ABILITY3_LINES):
            three["lines"] = [dict(text=text, status="changed") for text in old]
            synced = M.mirror_updates(design, panel)[1]
            got = next(entry for entry in synced["abilities"] if int(entry["index"]) == 3)
            self.assertEqual([line["text"] for line in got["lines"]], list(K.PANEL_ABILITY[3]))
        self.assertEqual(M.PREVIOUS_ABILITY3_LINES[:4], tuple(K.PANEL_ABILITY[3]))
        self.assertEqual(M.PREVIOUS_ABILITY3_LINES[4:], (M.ABILITY3_R2_DROPS[4][0], M.FULL_DICE_LINE_SPLIT))
        three["lines"][0]["text"] += "x"
        with self.assertRaisesRegex(ValueError, "ability 3 layout drifted"):
            M.mirror_updates(design, panel)

    def test_mirror_update_is_pure(self):
        before = deepcopy(self.disk)
        M.mirror_updates(*self.disk)
        self.assertEqual(self.disk, before)


if __name__ == "__main__":
    unittest.main()
