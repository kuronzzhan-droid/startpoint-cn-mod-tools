# -*- coding: utf-8 -*-
"""玛格诺斯「疾风同路」119990 ``lion_swordman_moon`` 2026-09-27 平衡第三轮（c）：
队长成长行数值回调（作者原话 3–6，口径 D1–D4）＋ 技能倍率撤封顶（U2/U6/U7）＋ 面板（U8）＋ 旗号 1 条目改实际效果（U9）。

fixture = 当前 live 输入快照（``fixtures/balance_20260927c_magnus.json``，链尾 1.4.1053 采集、1.4.1054 复核补采），驱动 ``revise()``：
每处改动的前后值、未改行/未改节点逐字保留、数值按作者档位与取整规则可复算、旗号 2 开关行逐格（含 live 先例同形）、
DSL 开关两支（关支 == live、开支只差上限且 == 第二批前）、vlv 作用域门禁（含删判定反例）、四道 DSL 门与 AMF3 往返、
面板规则、面板同条件合并（合并行逐字、数据条件签名、``wf_panel_merge_check`` 通过）与引擎点火效果行省略共鸣
（获取来源全带火共鸣、含删判定反例）、冲刺两行按数据删共鸣（主会话口径 4：数据只有前置 42，含删判定反例）、BEFORE 漂移与新键已存在拒绝、不改输入、对自身输出重跑拒绝、生成器输出 == revise() 输出、
设计镜像重算可过 kit 对账、候选无漂移且版本只升不降。
生成器装配对比需要 ``.cdn/cn`` 官方基线与 live store（缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927c_magnus as MC  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kit_magnus as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_panel_merge_check as PMC  # noqa: E402   面板合并校验器（仓库内，硬依赖）

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927c_magnus.json"
#: 第二批 fixture = 第二批前的 live（技能树点火上限 99）：用来核对「撤封顶 = 逐字恢复」。
FIXTURE_B = Path(__file__).parent / "fixtures/balance_20260927b_magnus.json"
UID = MC.UID
CODE = MC.CODE
BIND_PATH = (11, 1, 0, 1, 5)


def _load(path: Path) -> tuple[dict, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ({kind: value for kind, value in data.items() if not kind.startswith("_")},
            data.get("_context", {}))


def load_fixture() -> dict:
    return _load(FIXTURE)[0]


def reader(data: dict):
    def read(kind, key):
        return data[kind][key]
    return read


def _live_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


_LIVE = _live_available()


def nonempty(row) -> dict[int, str]:
    return {col: value for col, value in enumerate(row) if value != ""}


def changed_cells(old, new) -> dict[int, tuple[str, str]]:
    return {col: (a, b) for col, (a, b) in enumerate(zip(old, new)) if a != b}


def tree_diff(a, b, path=()):
    """两棵 DSL 树的逐节点差异路径（结构不同也报）。"""
    if type(a) is not type(b):
        return [(path, a, b)]
    if isinstance(a, list):
        if len(a) != len(b):
            return [(path, len(a), len(b))]
        out = []
        for index, (x, y) in enumerate(zip(a, b)):
            out += tree_diff(x, y, path + (index,))
        return out
    if isinstance(a, dict):
        if set(a) != set(b):
            return [(path, sorted(a), sorted(b))]
        out = []
        for key in a:
            out += tree_diff(a[key], b[key], path + (key,))
        return out
    return [] if a == b else [(path, a, b)]


#: 本轮之后的队长成长行描述（wf_describe 回读）。
NEW_LEADER_DESCRIBE = {
    1: "火·编成≥6 时: 强化弹射≥3 → 赋予全队(火) 技能伤害 80%",
    2: "火·编成≥6 时: 强化弹射≥3 → 赋予全队(火) 攻击力 40%",
    9: "火·编成≥6 时: 强化弹射≥3 → 自身 技能伤害 20%",
    10: f"火·编成≥6 时: 持续·状态累积计数固有≥1[固有{UID}] → 自身 技能伤害 35%",
    11: f"火·编成≥6 时: 持续·状态累积计数固有≥1[固有{UID}] → 自身 攻击力 35%",
    12: f"持续·状态累积计数固有≥1[固有{UID}] → 赋予全队(火) 独立乘区技能伤害 4%",
}
#: 本轮数值、合并前（逐效果一行）——合并与共鸣省略的来源（check_merge 的 orig）。
#: 第 1 行末尾「，威力随引擎点火层数提升」= 特殊强化弹射三档随点火成长（上限 99、不经旗号；队长强化弹射本体的效果）。
SPECIAL_PF_LINE = "火属性共鸣时，自身的强化弹射变为特殊强化弹射，造成的伤害按技能伤害结算，威力随引擎点火层数提升"
UNMERGED_LEADER_PANEL = (
    f"{SPECIAL_PF_LINE}\n"
    "火属性共鸣时，自身获得冲刺强化效果，冲刺冷却时间－30%\n"
    "火属性共鸣时，冲刺间隔缩短效果不会让自身的冲刺冷却时间进一步缩短\n"
    "火属性共鸣时，每发动3次强化弹射，火属性角色技能伤害＋80%、攻击力＋40%\n"
    "火属性共鸣时，每发动3次强化弹射，自身技能伤害＋20%\n"
    "火属性共鸣时，每发动3次强化弹射，火属性角色技能槽＋5%\n"
    "火属性共鸣时，每发动3次强化弹射，自身引擎点火＋7层\n"
    "火属性共鸣时，引擎点火每提升1层，自身技能伤害＋35%、攻击力＋35%\n"
    "火属性共鸣时，强化『烈焰轰鸣』：技能倍率随引擎点火层数持续提升（含引擎之炎）\n"
    "自身引擎点火每提升1层，火属性角色技能伤害额外乘区＋4%\n"
    "自身持有「烈焰光环」期间，每次弹射，连击＋35"
)
#: 作者点名的两组合并（按本轮数值）：L4–L7 → 一行；L8 删「火属性共鸣时，」后与 L9 → 一行（措辞按 scan.json）。
MERGED_PF3_LINE = ("火属性共鸣时，每发动3次强化弹射，火属性角色技能伤害＋80%、攻击力＋40%、技能槽＋5%，"
                   "自身技能伤害＋20%、引擎点火＋7层")
MERGED_LAYER_LINE = "自身引擎点火每提升1层，自身技能伤害＋35%、攻击力＋35%，火属性角色技能伤害额外乘区＋4%"
#: 冲刺两行（主会话口径 4）：数据在能力 5 #2/#3，只有前置 42（队长）、没有火共鸣 ⇒ 按数据删「火属性共鸣时，」。
DASH_LINES_AFTER = ("自身获得冲刺强化效果，冲刺冷却时间－30%",
                    "冲刺间隔缩短效果不会让自身的冲刺冷却时间进一步缩短")
NEW_LEADER_PANEL = (
    f"{SPECIAL_PF_LINE}\n"
    f"{DASH_LINES_AFTER[0]}\n"
    f"{DASH_LINES_AFTER[1]}\n"
    f"{MERGED_PF3_LINE}\n"
    f"{MERGED_LAYER_LINE}\n"
    "火属性共鸣时，强化『烈焰轰鸣』：技能倍率随引擎点火层数持续提升（含引擎之炎）\n"
    "自身持有「烈焰光环」期间，每次弹射，连击＋35"
)
OLD_SLOT2_PANEL = "火属性共鸣时，引擎点火每提升1层，自身技能伤害＋15%、攻击力＋15%（最多10层）"
NEW_SLOT2_PANEL = "引擎点火每提升1层，自身技能伤害＋15%、攻击力＋15%（最多10层）"
NEW_SLOT1_PANEL = (
    "战斗开始时，自身技能槽＋50%\n"
    "火属性共鸣时，强化『烈焰轰鸣』：斩劈的技能倍率提升\n"
    "火属性共鸣时，每发动3次强化弹射，自身技能伤害＋25%（最多4次）\n"
    "自身引擎点火每提升1层，技能基础总倍率＋5倍（含引擎之炎，最多10层）"
)
#: 每整招 +5 倍/层按段数分摊（第一批 wf_magnus_ignition_growth）：各树 CreateNormalAttack 的单目标命中段数。
HITS = {MC.PROGRAMS[0]: [1, 10], MC.PROGRAMS[1]: [1, 10], MC.PROGRAMS[2]: [5],
        MC.PROGRAMS[3]: [2, 1], MC.PROGRAMS[4]: [3, 1], MC.PROGRAMS[5]: [3, 1]}


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live, cls.context = _load(FIXTURE)
        cls.pre_b = _load(FIXTURE_B)[0]
        cls.out = MC.revise(reader(deepcopy(cls.live)))

    # ---------------------------------------------------------------- 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in MC.BEFORE.items():
            self.assertEqual(MC.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys}, set(MC.BEFORE))
        for kind, key in MC.ABSENT:
            self.assertNotIn(key, self.live.get(kind, {}))

    def test_module_contract_exports(self):
        self.assertEqual((MC.CID, MC.CODE), (str(K.CID), K.CODE))
        self.assertEqual(MC.PACKAGES, ["ma-magnus"])
        self.assertEqual(MC.PACKAGE_VERSION, {"ma-magnus": "1.0.3"})   # 候选现值 1.0.2（第二批回写），只升不降
        self.assertEqual(MC.CAPABILITIES, [])
        self.assertEqual(MC.REVIEWED_DRIFT, {})
        self.assertFalse(hasattr(MC, "UNITS"))

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["leader"]), {MC.CID})
        self.assertEqual(set(out["ability"]), {MC.A1})
        self.assertEqual(set(out["cas"]), {MC.CAS_LEADER, MC.CAS_SLOT1, MC.CAS_SLOT2, MC.CAS_SWITCH,
                                           MC.CAS_SWITCH_LEADER})
        self.assertEqual(set(out["dsl"]), set(MC.PROGRAMS))
        for kind in ("text", "table", "action", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)
        for key in out["cas"]:   # RevisionCandidate 命名空间
            self.assertTrue(key.startswith(("desc_override_" + CODE, "change_skill_" + CODE)), key)
        for program in out["dsl"]:
            self.assertIn(CODE, program)

    # ---------------------------------------------------------------- 队长（口径 D1–D3）

    def test_leader_changes_only_the_six_growth_strengths(self):
        old, new = self.live["leader"][MC.CID], self.out["leader"][MC.CID]
        self.assertEqual((len(old), len(new)), (13, 13))
        want = {1: ("20000", "80000"), 2: ("10000", "40000"), 9: ("5000", "20000"),
                10: ("5000", "35000"), 11: ("5000", "35000"), 12: ("500", "4000")}
        for index in range(13):
            if index in want:
                cols = (49, 50) if index in (1, 2, 9) else (111, 112)
                self.assertEqual(changed_cells(old[index], new[index]),
                                 {col: want[index] for col in cols}, f"leader#{index}")
                self.assertEqual(wf_describe.describe_rows([new[index]], "leader_ability")[0],
                                 NEW_LEADER_DESCRIBE[index])
            else:
                self.assertEqual(new[index], old[index], f"leader#{index}")

    def test_leader_values_follow_the_author_factors_and_rounding(self):
        """基数 = 第二批前原值；档位 4/5 / 7/10（D1 取 20）/ 2/3（向上取 5 的倍数）/ 4/5（<10% 取整数）。"""
        new = self.out["leader"][MC.CID]
        for index, (cols, original, current, value, factor, _label) in MC.LEADER_GROWTH.items():
            self.assertEqual(new[index][cols[0]], value)
            self.assertEqual(Fraction(int(original)) * MC.BATCH2_FACTOR[index], int(current), "第二批现值可复算")
            self.assertEqual(MC.suggested(original, factor), value)
            ratio = Fraction(int(value), int(original))
            self.assertGreaterEqual(ratio, Fraction(2, 3), f"#{index} 不得低于 2/3 下限")
            self.assertLessEqual(ratio, Fraction(4, 5), f"#{index} 不得高于 4/5")
        self.assertEqual({i: Fraction(int(v[3]), int(v[1])) for i, v in MC.LEADER_GROWTH.items()},
                         {1: Fraction(4, 5), 2: Fraction(4, 5), 9: Fraction(4, 5),
                          10: Fraction(7, 10), 11: Fraction(7, 10), 12: Fraction(4, 5)})
        # 取整规则本身：25×7/10 = 17.5 → 20（D1）；50×2/3 = 33.3 → 35（向上）；5×4/5 = 4（0.5% 步长）
        self.assertEqual(MC.suggested("25000", Fraction(2, 3)), "20000")
        self.assertEqual(MC.suggested("36000", Fraction(1)), "35000")      # 作者「36 就变成 35」
        self.assertEqual(MC.suggested("39000", Fraction(1)), "40000")      # 作者「39 就变成 40」
        self.assertEqual(MC.suggested("5000", Fraction(7, 10)), "3500")

    def test_leader_rows_keep_their_gates_d3(self):
        """口径 D3：不给成长行新增共鸣前置；#12（原能力 3#4 无前置）仍无前置。"""
        old, new = self.live["leader"][MC.CID], self.out["leader"][MC.CID]
        for index in MC.LEADER_GROWTH:
            self.assertEqual(new[index][4:11], old[index][4:11], f"leader#{index}")
        self.assertEqual(new[12][4], "0")
        self.assertEqual([new[i][4] for i in (1, 2, 9, 10, 11)], ["2"] * 5)

    def test_leader_keeps_the_pf_callers_and_no_flag_row(self):
        new = self.out["leader"][MC.CID]
        for index, program in zip((6, 7, 8), MC.PF_SKILL_PROGRAMS):
            self.assertEqual((new[index][45], new[index][25], new[index][69]), ("629", str(57 + index), program))
            self.assertEqual((new[index][4], new[index][9]), ("2", "Red"), "特殊 PF 本来就只在火共鸣时存在")
        for row in new:
            self.assertNotIn(row[45], ("536", "704", "705") + K.LEADER_FORBIDDEN_KINDS,
                             "零先例的「队长表 704 行」不做（口径 U6）")
            self.assertNotIn(row[107], K.LEADER_FORBIDDEN_KINDS)

    # ---------------------------------------------------------------- 能力 1：旗号 2 开关行（口径 U6）

    def test_ability1_appends_only_the_flag_row(self):
        old, new = self.live["ability"][MC.A1], self.out["ability"][MC.A1]
        self.assertEqual((len(old), len(new)), (3, 4))
        self.assertEqual(new[:3], old)
        row = new[3]
        self.assertEqual(len(row), 126)
        self.assertEqual(nonempty(row), MC.SWITCH_ROW)
        self.assertEqual(wf_describe.describe_rows([row], "ability")[0],
                         f"队长 且 火·编成≥6 时: 自身 切换技能Flag2[{MC.CAS_SWITCH_LEADER}]")
        self.assertEqual((row[3], row[5], row[27]), ("0", "0", "0"), "瞬发、无触发（持续块写旗号 = C2308）")
        self.assertEqual((row[6], row[13], row[16], row[17], row[18]), ("42", "2", "600000", "600000", "Red"))
        self.assertEqual(row[47], "704", "704 = 旗号 2")
        KL.check_ability_key(new, MC.A1, CODE, 1)

    def test_flag_row_has_the_live_precedent_shape(self):
        """live 罗尔夫中秋 1499866#4：704 + 前置 42 + 风编成≥6，与本行只差 c0/c2/c18/c70。"""
        key, index = MC.SWITCH_PRECEDENT
        precedent = self.context["ability_precedent"][key][index]
        self.assertEqual(precedent[47], "704")
        self.assertEqual(precedent[6], "42")
        diff = changed_cells(precedent, self.out["ability"][MC.A1][3])
        self.assertEqual(set(diff), {0, 2, 18, 70})

    def test_flag_1_row_is_untouched_and_is_not_the_leader_gate(self):
        """旗号 1（536）火编成≥6、c1=true ⇒ 不当队长也开着，不能复用；行不动，只改它的文案（U9）。"""
        row = self.out["ability"][MC.A1][1]
        self.assertEqual((row[47], row[6], row[70]), ("536", "2", MC.CAS_SWITCH))
        self.assertNotIn("42", (row[6], row[13], row[20]))

    # ---------------------------------------------------------------- 面板（口径 U8 / U9）

    def test_panel_texts(self):
        self.assertEqual(self.out["cas"][MC.CAS_LEADER], [[NEW_LEADER_PANEL]])
        self.assertEqual(self.out["cas"][MC.CAS_SLOT1], [[NEW_SLOT1_PANEL]])
        self.assertEqual(self.out["cas"][MC.CAS_SLOT2], [[NEW_SLOT2_PANEL]])
        self.assertEqual(self.out["cas"][MC.CAS_SWITCH], [["强化『烈焰轰鸣』：斩劈的技能倍率提升"]])
        self.assertEqual(self.out["cas"][MC.CAS_SWITCH_LEADER],
                         [["强化『烈焰轰鸣』：技能倍率随引擎点火层数持续提升（含引擎之炎）"]])
        old = self.live["cas"][MC.CAS_LEADER][0][0].split("\n")
        unmerged = UNMERGED_LEADER_PANEL.split("\n")
        self.assertEqual(tuple(unmerged), MC.UNMERGED_LEADER_LINES)
        self.assertEqual(unmerged[1:3] + unmerged[5:7] + unmerged[-1:], old[1:3] + old[5:7] + old[-1:],
                         "数值没变的行逐字保留")
        self.assertEqual(unmerged[0], old[0] + "，威力随引擎点火层数提升", "第 1 行只在末尾补特殊强化弹射的点火成长")
        self.assertEqual(unmerged[MC.LEADER_SKILL_LINE_AT], MC.LEADER_SKILL_LINE)
        self.assertTrue(unmerged[MC.LEADER_SKILL_LINE_AT - 1].startswith("火属性共鸣时，引擎点火每提升1层"))
        new = NEW_LEADER_PANEL.split("\n")
        self.assertEqual(len(new), 7)
        self.assertEqual(new[-1:], old[-1:], "未合并、未改数值的行逐字保留、原序")
        self.assertEqual(new[0], old[0] + MC.SPECIAL_PF_GROWTH, "第 1 行只在末尾补特殊强化弹射的点火成长")
        self.assertEqual(new[0], SPECIAL_PF_LINE)
        self.assertEqual(new[1:3], [line.removeprefix("火属性共鸣时，") for line in old[1:3]],
                         "冲刺两行只删前缀（口径 4），其余逐字")
        self.assertEqual(new[5], MC.LEADER_SKILL_LINE, "旗号 2 行紧跟点火逐层合并行")
        self.assertEqual(self.live["cas"][MC.CAS_SLOT2], [[OLD_SLOT2_PANEL]])
        self.assertEqual(NEW_SLOT2_PANEL, OLD_SLOT2_PANEL.removeprefix("火属性共鸣时，"), "只删前缀，其余逐字")
        old1 = self.live["cas"][MC.CAS_SLOT1][0][0].split("\n")
        new1 = NEW_SLOT1_PANEL.split("\n")
        self.assertEqual([new1[0], new1[2]], [old1[0], old1[2]])
        # 技能强化文案规范（R3）：只写本体「最多10层」，不写旗号 2 的「不受此限」；特殊强化弹射三档上限 99 不经旗号 ⇒ 去掉
        self.assertEqual(new1[3], old1[3].replace("及特殊强化弹射", ""))
        self.assertEqual(new1[1], "火属性共鸣时，" + self.out["cas"][MC.CAS_SWITCH][0][0], "旗号 1 面板行 = 共鸣前缀 + CAS")
        self.assertEqual(new[5], "火属性共鸣时，" + self.out["cas"][MC.CAS_SWITCH_LEADER][0][0],
                         "旗号 2 面板行 = 共鸣前缀 + CAS")

    # ---------------------------------------------------------------- 面板同条件合并 / 共鸣省略

    def test_merged_lines_are_verbatim(self):
        """作者点名：L4–L7 并一行；L8 删共鸣后与 L9 并一行（按本轮数值，措辞按 scan.json）；合并行在组首位置。"""
        groups = MC.LEADER_MERGE_GROUPS
        self.assertEqual([g["text"] for g in groups], [MERGED_PF3_LINE, MERGED_LAYER_LINE])
        self.assertEqual([g["lines"] for g in groups], [(3, 4, 5, 6), (7, 9)])
        self.assertEqual([g["omit"] for g in groups], [(), (7,)])
        new = NEW_LEADER_PANEL.split("\n")
        self.assertEqual((new[3], new[4]), (MERGED_PF3_LINE, MERGED_LAYER_LINE))
        self.assertEqual(MC.NEW_LEADER_LINES, tuple(new))
        # 合并与口径 4 的冲刺两行删前缀互不干扰：先删前缀再合并 == 改后面板
        self.assertEqual(MC.merged_lines(MC.prefix_dropped(MC.UNMERGED_LEADER_LINES, MC.DASH_LINES), groups),
                         tuple(new))
        self.assertEqual(MC.merge_text_problems(MC.UNMERGED_LEADER_LINES, groups), [])
        self.assertFalse(set(MC.DASH_LINES) & {i for g in groups for i in g["lines"]}, "冲刺两行不在任何合并组里")
        with self.assertRaises(ValueError):                    # 只能删真带前缀的行
            MC.prefix_dropped(MC.UNMERGED_LEADER_LINES, (MC.UNMERGED_LEADER_LINES.index(MC.OLD_LEADER_LINES[9]),))
        # 合并行数值 = 数据行强度（1000 = 1%；#4 的 461 强度 100000 = 1 层）
        rows = self.out["leader"][MC.CID]
        pct = {i: f"＋{int(rows[i][49]) // 1000}%" for i in (1, 2, 3, 9)}
        self.assertEqual(MERGED_PF3_LINE,
                         f"火属性共鸣时，每发动3次强化弹射，火属性角色技能伤害{pct[1]}、攻击力{pct[2]}、技能槽{pct[3]}，"
                         f"自身技能伤害{pct[9]}、引擎点火＋{int(rows[4][49]) // 100000}层")
        layer = {i: f"＋{int(rows[i][111]) / 1000:g}%" for i in (10, 11, 12)}
        self.assertEqual(MERGED_LAYER_LINE, f"自身引擎点火每提升1层，自身技能伤害{layer[10]}、攻击力{layer[11]}，"
                                            f"火属性角色技能伤害额外乘区{layer[12]}")

    def test_merge_text_self_check_catches_violations(self):
        good = MC.LEADER_MERGE_GROUPS
        lost = (dict(good[0], text=good[0]["text"].replace("、技能槽＋5%", "")),)
        self.assertTrue(any("effect tokens" in p for p in MC.merge_text_problems(MC.UNMERGED_LEADER_LINES, lost)))
        kept = (dict(good[1], text="火属性共鸣时，" + good[1]["text"]),)
        self.assertTrue(any("prefix" in p for p in MC.merge_text_problems(MC.UNMERGED_LEADER_LINES, kept)))
        unauthorised = (dict(good[0], text=good[0]["text"].removeprefix("火属性共鸣时，")),)
        self.assertTrue(any("prefix" in p for p in MC.merge_text_problems(MC.UNMERGED_LEADER_LINES, unauthorised)))

    def test_merge_groups_share_the_data_conditions(self):
        """组内数据行条件签名（前置 / 触发 / CT / 次数上限 / 觉醒 / 后缀）逐列相同，组外没有同签名的行。"""
        rows = self.out["leader"][MC.CID]
        self.assertEqual(MC.merge_group_problems(rows), [])
        for group in MC.LEADER_MERGE_GROUPS:
            sigs = {MC.condition_signature(rows[i], "leader", group["drop"]) for i in group["rows"]}
            self.assertEqual(len(sigs), 1, group["rows"])
        # 第 2 组只在去掉火共鸣后相同：#12 本身无前置（口径 D3 不补）
        self.assertNotEqual(MC.condition_signature(rows[10], "leader"), MC.condition_signature(rows[12], "leader"))
        # 反例：触发条件漂移 ⇒ 组内不再同条件；组外行同签名 ⇒ 漏并
        drifted = deepcopy(rows)
        drifted[9][28] = drifted[9][29] = "500000"
        self.assertTrue(any("differ" in p for p in MC.merge_group_problems(drifted)))
        extra = deepcopy(rows)
        extra[5] = deepcopy(extra[1])
        self.assertTrue(any("not merged" in p for p in MC.merge_group_problems(extra)))
        # 其余覆盖面板：能力 3 L2/L3 同条件但是 629 追击 + 消耗机制行（scan skip_mechanism，不并）
        a3 = self.live["ability"][f"{MC.CID}3"]
        self.assertEqual(MC.condition_signature(a3[1], "ability"), MC.condition_signature(a3[2], "ability"))
        self.assertEqual((a3[1][47], a3[2][47]), ("629", "525"))
        a1 = self.out["ability"][MC.A1]
        self.assertEqual(len({MC.condition_signature(row, "ability") for row in a1}), len(a1), "能力 1 各行条件互异")
        a5 = self.live["ability"][f"{MC.CID}5"]
        self.assertEqual(len({MC.condition_signature(row, "ability") for row in a5}), len(a5), "能力 5 各行条件互异")

    def test_resonance_omission_basis(self):
        """引擎点火全部获取来源（行 + DSL 授予节点）都带火编成≥6 ⇒ 按层数生效的效果不写「火属性共鸣时，」。"""
        tables = {("leader", MC.CID): self.out["leader"][MC.CID], ("ability", MC.A1): self.out["ability"][MC.A1],
                  **{("ability", key): self.live["ability"][key] for key in MC.BASIS_ABILITIES}}
        trees = {**self.out["dsl"], **{p: self.live["dsl"][p] for p in MC.PF_OVERRIDE_PROGRAMS}}
        self.assertEqual(MC.resonance_omission_problems(tables, trees), [])
        grants = [f"{t}:{k}#{i}" for (t, k), rows in tables.items() for i, row in enumerate(rows)
                  if any(role == "grant" for _c, role in MC.uid_roles(row, t))]
        self.assertEqual(tuple(grants), MC.IGNITION_SOURCES)
        for (table, key), rows in tables.items():
            for index, row in enumerate(rows):
                if any(role == "grant" for _c, role in MC.uid_roles(row, table)):
                    self.assertIn("Red", {MC.resonance_of(b) for b in MC.preconditions(row, table)}, (key, index))
        for program, tree in trees.items():
            self.assertTrue(all(role == "read" for _p, role in MC.dsl_uid_roles(tree)), program)
        # 被省略共鸣的面板行 ↔ 依赖点火层数的数据行（dt 134 固有 11999001），数据前置不动（仍带火共鸣）
        for table, key, indexes in MC.OMITTED_ROWS:
            for index in indexes:
                row = tables[(table, key)][index]
                self.assertIn((97 if table == "ability" else 95) + 7, [c for c, r in MC.uid_roles(row, table)
                                                                        if r == "depends"])
                self.assertIn("Red", {MC.resonance_of(b) for b in MC.preconditions(row, table)})
        self.assertEqual(self.out["ability"].keys(), {MC.A1}, "能力 2 行不改（只改面板）")
        # 技能 / 换形 / PF 覆盖程序路径都在已读范围内
        skill_paths = {fields[7] for _k, fields in self.context["action"][CODE]}
        voice_paths = {fields[0] for _lv, fields in self.context["switched"][f"{CODE}_voice_ready"]}
        self.assertEqual(skill_paths, set(MC.PROGRAMS[:2]))
        self.assertEqual(voice_paths, set(MC.PROGRAMS[:2]), "换形 voice_ready 与技能同路径")
        self.assertEqual(tuple(self.context["pf_action"][MC.PF_OVERRIDE_KEY][0]), MC.PF_OVERRIDE_PROGRAMS)

    def test_resonance_omission_rejects_a_source_without_resonance(self):
        """删判定反例：任一来源不带火共鸣 / DSL 出现授予 / 新来源 / 固有号写在认不出的格 ⇒ 报错，revise() 拒绝。"""
        base = {("leader", MC.CID): self.out["leader"][MC.CID], ("ability", MC.A1): self.out["ability"][MC.A1],
                **{("ability", key): self.live["ability"][key] for key in MC.BASIS_ABILITIES}}
        trees = {**self.out["dsl"], **{p: self.live["dsl"][p] for p in MC.PF_OVERRIDE_PROGRAMS}}
        tables = deepcopy(base)
        a3 = tables[("ability", f"{MC.CID}3")]
        a3[0][6:13] = ["0", "", "", "", "", "", ""]                  # 技能发动 +1 层：去掉火编成≥6
        self.assertTrue(any("without the fire resonance" in p for p in MC.resonance_omission_problems(tables, trees)))
        tables = deepcopy(base)
        tables[("ability", f"{MC.CID}6")].append(deepcopy(tables[("ability", f"{MC.CID}3")][5]))  # 多一条来源
        self.assertTrue(any("sources" in p for p in MC.resonance_omission_problems(tables, trees)))
        tables = deepcopy(base)
        tables[("ability", f"{MC.CID}4")][0][80] = MC.UID                                  # 认不出的格
        self.assertTrue(any("unrecognised" in p for p in MC.resonance_omission_problems(tables, trees)))
        tables = deepcopy(base)
        tables[("leader", MC.CID)][6][69] = "battle/action/skill/action/ability_skill/other$other"  # 未读的 629
        self.assertTrue(any("not read" in p for p in MC.resonance_omission_problems(tables, trees)))
        grant = deepcopy(trees)
        grant[MC.PF_OVERRIDE_PROGRAMS[0]][11][1].append(
            ["Command", ["CreateCondition", -17, [["ACUnique", int(MC.UID), 1]]]])        # DSL 授予
        self.assertTrue(any("DSL grant" in p for p in MC.resonance_omission_problems(base, grant)))
        # 走 revise()：fixture 里 DSL 授予（摘要也跟着改）⇒ 拒绝
        data = deepcopy(self.live)
        program = MC.PF_OVERRIDE_PROGRAMS[0]
        data["dsl"][program][11][1].append(["Command", ["CreateCondition", -17, [["ACUnique", int(MC.UID), 1]]]])
        before = dict(MC.BEFORE)
        try:
            MC.BEFORE[("dsl", program)] = MC.digest(data["dsl"][program])
            with self.assertRaisesRegex(ValueError, "resonance omission"):
                MC.revise(reader(data))
        finally:
            MC.BEFORE.clear()
            MC.BEFORE.update(before)

    def test_other_override_panels_need_no_change(self):
        """能力 3 / 5 覆盖面板：无可合并组、无「按点火层数生效且带共鸣」的行 ⇒ 不返回；能力 4 / 6 自动面板不新建覆盖。"""
        unchanged = self.context["cas_unchanged"]
        a3 = unchanged[f"desc_override_{CODE}_3"][0][0].split("\n")
        self.assertEqual([line.startswith(MC.MAIN_ICON) for line in a3], [True] * 6)
        with_prefix = [i for i, line in enumerate(a3) if "火属性共鸣时，" in line]
        self.assertEqual(with_prefix, [0, 5], "只有两条获取行带共鸣（获取本身要共鸣，保留）")
        a3_rows = self.live["ability"][f"{MC.CID}3"]
        self.assertEqual([[r for _c, r in MC.uid_roles(a3_rows[i], "ability")] for i in (0, 5)],
                         [["grant"], ["grant"]])
        self.assertEqual(K.CAS_TEXTS[K.SLOT_OVERRIDE[3]], unchanged[f"desc_override_{CODE}_3"][0][0])
        self.assertEqual(K.CAS_TEXTS[K.SLOT_OVERRIDE[5]], unchanged[f"desc_override_{CODE}_5"][0][0])
        for key in (f"desc_override_{CODE}_3", f"desc_override_{CODE}_5"):
            self.assertNotIn(key, self.out["cas"])
        for key in self.context["cas_absent"]:
            self.assertNotIn(key, self.out["cas"])
            self.assertNotIn(key, K.CAS_TEXTS)

    def test_check_merge_passes(self):
        """仓库校验器 wf_panel_merge_check：合并前（本轮数值）→ 合并后逐列通过，删前缀只在授权行
        （点火逐层行 = 共鸣省略；冲刺两行 = 口径 4 按数据改文字）；少授权任一行都必须报错。
        本角色本轮返回的覆盖面板没有「X属性共鸣时：」，orig 不需要口径 3 规范化（下面断言）。"""
        self.assertNotRegex(UNMERGED_LEADER_PANEL + OLD_SLOT2_PANEL, "属性共鸣时[：:]")
        omit = [index + 1 for index in MC.LEADER_MERGE_GROUPS[1]["omit"]]
        dash = [index + 1 for index in MC.DASH_LINES]
        self.assertEqual((omit, dash), ([8], [2, 3]))
        drops = [dict(line=line, resonance="Red") for line in dash + omit]
        result = PMC.check(UNMERGED_LEADER_PANEL, self.out["cas"][MC.CAS_LEADER][0][0], drops)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["warnings"], [])
        self.assertEqual(result["columns"][0]["mapping"],
                         {1: 1, 2: 2, 3: 3, 4: 4, 5: 4, 6: 4, 7: 4, 8: 5, 9: 6, 10: 5, 11: 7})
        self.assertEqual(result["columns"][0]["kinds"],
                         {1: "verbatim", 2: "prefix_drop", 3: "prefix_drop", 4: "merge", 5: "merge",
                          6: "verbatim", 7: "verbatim"})
        self.assertFalse(PMC.check(UNMERGED_LEADER_PANEL, NEW_LEADER_PANEL, [])["ok"], "不授权删前缀必须报错")
        for missing in (omit, dash[:1], dash[1:]):
            partial = [d for d in drops if d["line"] not in missing]
            self.assertFalse(PMC.check(UNMERGED_LEADER_PANEL, NEW_LEADER_PANEL, partial)["ok"], missing)
        result = PMC.check(OLD_SLOT2_PANEL, self.out["cas"][MC.CAS_SLOT2][0][0], [dict(line=1, resonance="Red")])
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["warnings"], [])
        for key, rows in self.out["cas"].items():   # 未合并的面板也过（逐字 / 无改动行）
            if key in (MC.CAS_LEADER, MC.CAS_SLOT2):
                continue
            self.assertEqual(PMC.check(rows[0][0], rows[0][0], [])["errors"], [], key)

    def test_dash_lines_follow_the_data(self):
        """口径 4：冲刺两行的数据 = 能力 5 #2/#3（during 422），前置只有 42（队长）、没有火共鸣 ⇒ 文案不写共鸣；
        数据不动（能力 5 不返回）。删判定反例：给 #2 补火共鸣 / 去掉 42 / 别处多一条 422 ⇒ 报错，revise() 拒绝。"""
        a5 = self.live["ability"][MC.A5]
        for index in MC.DASH_ROWS:
            row = a5[index]
            self.assertEqual((row[5], row[109], row[6], row[13], row[20]), ("1", "422", "42", "0", "0"), index)
            self.assertEqual({MC.resonance_of(b) for b in MC.preconditions(row, "ability")}, {None}, index)
            self.assertTrue(wf_describe.describe_rows([row], "ability")[0].startswith("队长 时: "), index)
        self.assertNotIn(MC.A5, self.out["ability"], "数据不动")
        lines = self.out["cas"][MC.CAS_LEADER][0][0].split("\n")
        self.assertEqual(tuple(lines[i] for _key, i in MC.DASH_PANEL_LINES), DASH_LINES_AFTER)
        self.assertEqual([k for k, _i in MC.DASH_PANEL_LINES], [MC.CAS_LEADER] * 2)
        tables = {("leader", MC.CID): self.out["leader"][MC.CID], ("ability", MC.A1): self.out["ability"][MC.A1],
                  **{("ability", key): self.live["ability"][key] for key in MC.BASIS_ABILITIES}}
        self.assertEqual(MC.dash_row_problems(tables), [])
        gated = deepcopy(tables)
        gated[("ability", MC.A5)][2][13:20] = ["2", "", "", "600000", "600000", "Red", ""]   # 补火编成≥6
        self.assertTrue(any("resonance" in p for p in MC.dash_row_problems(gated)))
        ungated = deepcopy(tables)
        ungated[("ability", MC.A5)][3][6] = "0"                                              # 去掉队长前置
        self.assertTrue(any("precondition 42" in p for p in MC.dash_row_problems(ungated)))
        extra = deepcopy(tables)
        extra[("ability", f"{MC.CID}6")].append(deepcopy(extra[("ability", MC.A5)][2]))     # 别处多一条 422
        self.assertTrue(any("dash-parameter rows" in p for p in MC.dash_row_problems(extra)))
        # 走 revise()：fixture 里能力 5 #2 补上火共鸣（摘要跟着改）⇒ 拒绝
        data = deepcopy(self.live)
        data["ability"][MC.A5][2][13:20] = ["2", "", "", "600000", "600000", "Red", ""]
        before = dict(MC.BEFORE)
        try:
            MC.BEFORE[("ability", MC.A5)] = MC.digest(data["ability"][MC.A5])
            with self.assertRaisesRegex(ValueError, "dash text"):
                MC.revise(reader(data))
        finally:
            MC.BEFORE.clear()
            MC.BEFORE.update(before)
        # 面板规则同样拦：冲刺行写回共鸣
        bad = self.out["cas"][MC.CAS_LEADER][0][0].replace(DASH_LINES_AFTER[0], "火属性共鸣时，" + DASH_LINES_AFTER[0])
        self.assertTrue(any("dash line" in p for p in MC.panel_problems({MC.CAS_LEADER: bad})))

    def test_special_pf_line_follows_the_data(self):
        """队长第 1 行「…，威力随引擎点火层数提升」：特殊强化弹射三档（队长 #6–#8 的 629，火编成≥6）每段倍率带点火逐层
        加法项、上限 99、不在旗号分支里（队长强化弹射本体的效果，不属于技能强化）。删判定反例：去掉某段 vlv / 上限留 10 /
        包进旗号分支 / 调用方漂移 ⇒ 报错；revise() 对缺 vlv 的输入拒绝。"""
        leader = self.out["leader"][MC.CID]
        trees = self.out["dsl"]
        self.assertEqual(MC.special_pf_growth_problems(leader, trees), [])
        self.assertEqual(self.out["cas"][MC.CAS_LEADER][0][0].split("\n")[0], MC.SPECIAL_PF_LINE)
        self.assertEqual(MC.SPECIAL_PF_LINE, SPECIAL_PF_LINE)
        for index, program in zip((6, 7, 8), MC.PF_SKILL_PROGRAMS):
            row = leader[index]
            self.assertEqual((row[45], row[69]), ("629", program))
            self.assertIn("Red", {MC.resonance_of(b) for b in MC.preconditions(row, "leader")}, "行首共鸣是真实门")
            tree = trees[program]
            self.assertEqual((MC.layer_cap(tree, flag_on=False), MC.layer_cap(tree, flag_on=True)), (99, 99))
            self.assertEqual(MC.layer_cap(self.live["dsl"][program], flag_on=False), 10, "改前 10 层封顶")
            for attack in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"):
                (term,) = attack[6]
                self.assertEqual([x["vid"] for x in term["vlv"]], [MC.IGNITION_VARIABLE], program)
                self.assertGreater(term["vlv"][0]["max"], 0, program)
        # 删判定反例
        program = MC.PF_SKILL_PROGRAMS[1]
        no_vlv = deepcopy(trees)
        del next(wf_dsl.iter_dsl_commands(no_vlv[program], "CreateNormalAttack"))[6][0]["vlv"]
        self.assertTrue(any("does not grow" in p for p in MC.special_pf_growth_problems(leader, no_vlv)))
        capped = deepcopy(trees)
        capped[program][11][1][0][1][5] = MC.IGNITION_CAP[0]
        self.assertTrue(any("cap-99" in p for p in MC.special_pf_growth_problems(leader, capped)))
        gated = deepcopy(trees)
        gated[program] = MC.gate_tree(self.live["dsl"][program])
        self.assertTrue(any("skill flag" in p for p in MC.special_pf_growth_problems(leader, gated)))
        drifted = deepcopy(leader)
        drifted[7][4:11] = ["0", "", "", "", "", "", ""]
        self.assertTrue(any("caller drifted" in p for p in MC.special_pf_growth_problems(drifted, trees)))
        # 走 revise()：fixture 里某档缺 vlv（摘要跟着改）⇒ 拒绝
        data = deepcopy(self.live)
        del next(wf_dsl.iter_dsl_commands(data["dsl"][program], "CreateNormalAttack"))[6][0]["vlv"]
        before = dict(MC.BEFORE)
        try:
            MC.BEFORE[("dsl", program)] = MC.digest(data["dsl"][program])
            with self.assertRaises(MC.MagnusCBalanceError):
                MC.revise(reader(data))
        finally:
            MC.BEFORE.clear()
            MC.BEFORE.update(before)

    def test_panel_texts_obey_the_batch_rules(self):
        texts = {key: rows[0][0] for key, rows in self.out["cas"].items()}
        self.assertEqual(MC.panel_problems(texts), [])
        for key, text in texts.items():
            self.assertNotIn("／", text)
            for word in ("无上限", "无限叠加", "不设上限", "可无限", "自身为队长时", "觉醒后", "生命值100%以下",
                         "光环的范围扩大", "光环范围扩大"):
                self.assertNotIn(word, text, key)
        for line in (texts[MC.CAS_SWITCH], texts[MC.CAS_SWITCH_LEADER], MC.LEADER_SKILL_LINE,
                     texts[MC.CAS_SLOT1].split("\n")[1]):
            self.assertEqual(KL.panel_problems(line, skill_flag=True), [], f"技能强化条目不写数字: {line}")
        # 技能强化文案规范（作者 2026-09-27，主会话口径 R2/R3）：强化后的效果只写在强化条目里（点名『烈焰轰鸣』），
        # 其余行不写「不受此限」「强化后」，也不用「强化自身技能」「强化技能」泛称。
        self.assertTrue(texts[MC.CAS_SLOT1].endswith("（含引擎之炎，最多10层）"))
        for key, text in texts.items():
            for word in ("不受此限", "强化后", "强化自身技能", "强化技能"):
                self.assertNotIn(word, text, key)
        self.assertEqual(MC.skill_flag_entry_problems(texts), [])

    def test_skill_flag_entries_follow_the_official_format(self):
        """R2：CAS 条目「强化『烈焰轰鸣』：<定性说明>」与面板对应行同文（面板多开关行真实前置「火属性共鸣时，」）；
        删判定反例：CAS 与面板不一致 / 不点名技能 / 面板回到泛称 / 点火行写回「不受此限」都要报错。"""
        texts = {key: rows[0][0] for key, rows in self.out["cas"].items()}
        self.assertEqual(texts[MC.CAS_SWITCH], "强化『烈焰轰鸣』：斩劈的技能倍率提升")
        self.assertEqual(texts[MC.CAS_SWITCH_LEADER], "强化『烈焰轰鸣』：技能倍率随引擎点火层数持续提升（含引擎之炎）")
        self.assertIn(MC.LEADER_SKILL_LINE, texts[MC.CAS_LEADER].split("\n"))
        drift = dict(texts, **{MC.CAS_SWITCH_LEADER: "强化『烈焰轰鸣』：技能倍率随引擎点火层数持续提升"})
        self.assertTrue(any(MC.CAS_LEADER in p for p in MC.skill_flag_entry_problems(drift)))
        generic = dict(texts, **{MC.CAS_SWITCH: "强化技能：斩劈的技能倍率提升"})
        self.assertTrue(any("skill-flag entry must read" in p for p in MC.skill_flag_entry_problems(generic)))
        panel = dict(texts, **{MC.CAS_SLOT1: texts[MC.CAS_SLOT1].replace("强化『烈焰轰鸣』", "强化自身技能")})
        problems = MC.panel_problems(panel)
        self.assertTrue(any("强化自身技能" in p for p in problems))
        self.assertTrue(any(f"panel entry of {MC.CAS_SWITCH}" in p for p in problems))
        capped = dict(texts, **{MC.CAS_SLOT1: texts[MC.CAS_SLOT1].replace(
            "最多10层）", "最多10层；担任队长且火属性共鸣时不受此限）")})
        self.assertTrue(any("不受此限" in p for p in MC.panel_problems(capped)))

    def test_panel_problems_catch_violations(self):
        bad = {MC.CAS_SWITCH_LEADER: "强化『烈焰轰鸣』：技能倍率提升10%",
               MC.CAS_LEADER: "火属性共鸣时，引擎点火层数不设上限",
               MC.CAS_SLOT1: MC.MAIN_ICON + "战斗开始时\n火属性共鸣时，强化自身技能：斩劈倍率＋5%"}
        problems = MC.panel_problems(bad)
        self.assertTrue(any(MC.CAS_SWITCH_LEADER in p and "numbers" in p for p in problems))
        self.assertTrue(any("不设上限" in p for p in problems))
        self.assertTrue(any("main icon" in p for p in problems))
        self.assertTrue(any(f"{MC.CAS_SLOT1}#1" in p and "numbers" in p for p in problems))

    def test_skill_descriptions_carry_no_layer_statement(self):
        """口径 U8 的技能描述子句没有落点：技能两档 / character_text / 服务端文本都不含点火层数与上限（未改）。"""
        texts = [fields[1] for _k, fields in self.context["action"][CODE]]
        texts += [cell for row in self.context["text"][MC.CID] for cell in row]
        texts += [cell for row in self.context["server_text"][MC.CID] for cell in row]
        self.assertTrue(texts)
        for text in texts:
            for word in ("点火", "层", "最多", "不受此限"):
                self.assertNotIn(word, text)

    # ---------------------------------------------------------------- 合法性

    def test_native_legality_gates_are_empty(self):
        cas_keys = set(K.CAS_TEXTS)
        self.assertIn(MC.CAS_SWITCH_LEADER, cas_keys)
        for kind, table in (("leader", "leader_ability"), ("ability", "ability")):
            for key, rows in self.out[kind].items():
                for index, row in enumerate(rows):
                    label = f"{kind}:{key}#{index}"
                    self.assertEqual(L.client_legality_problems(table, row), [], label)
                    self.assertEqual(L.declared_block_field_problems(table, row), [], label)
                    self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, kind=table), [], label)
                    self.assertEqual(KL.row_problems(table, row, MC.ELEMENT), {}, label)
                    self.assertEqual(L.required_client_capabilities(table, row), [], label)
                    self.assertEqual(MC.row_gate_problems(kind, row, cas_keys), [], label)
        flag_row = self.out["ability"][MC.A1][3]
        self.assertTrue(any("c70" in p for p in MC.row_gate_problems("ability", flag_row,
                                                                      cas_keys - {MC.CAS_SWITCH_LEADER})),
                        "旗号行的面板串必须同批写进 custom_ability_string")

    # ---------------------------------------------------------------- DSL（口径 U2 / U7）

    def test_pf_trees_only_restore_the_cap(self):
        for program in MC.PF_SKILL_PROGRAMS:
            old, new = self.live["dsl"][program], self.out["dsl"][program]
            self.assertEqual(tree_diff(old, new), [(BIND_PATH, 10, 99)], program)
            self.assertIsInstance(new[11][1][0][1][5], int)
            self.assertEqual(new, self.pre_b["dsl"][program], "撤封顶 = 第二批前 live 逐字")
            self.assertEqual(wf_dsl.encode_amf3(new), wf_dsl.encode_amf3(self.pre_b["dsl"][program]))

    def test_gated_trees_wrap_the_whole_root(self):
        for program in MC.GATED_PROGRAMS:
            old, new = self.live["dsl"][program], self.out["dsl"][program]
            self.assertEqual(new[:11], old[:11], "根头（含 buffTargetAs 0 = 技能伤害）不动")
            self.assertEqual(len(new[11][1]), 1)
            flag = new[11][1][0][1]
            self.assertEqual(flag[:2], ["ConditionalsChangeSkillFlag", 2])
            opened, closed = MC.branches(new)
            self.assertEqual(closed, old[11], "关支 = live 原段逐字（非队长 / 不共鸣仍 10 层，口径 U7）")
            self.assertEqual(tree_diff(closed, opened), [((1, 0, 1, 5), 10, 99)], "开支只差绑定上限")
            self.assertIsInstance(opened[1][0][1][5], int, "第二批前是 int 99")
            pre = self.pre_b["dsl"][program][11]
            if program == MC.CHASE_PROGRAM:
                # 开支保留第二批的削韧 p13 0.2（口径 B3/B6），只有这一处（SLv min/max）与第二批前不同
                diff = tree_diff(pre, opened)
                self.assertEqual(sorted(p[-1] for p, _a, _b in diff), ["max", "min"])
                self.assertTrue(all(p[-2:-1] == (0,) and p[-3] == 13 and (a, b) == (0.25, 0.2)
                                    for p, a, b in diff), diff)
            else:
                self.assertEqual(opened, pre, "开支 = 第二批前 live 根块逐字")

    def test_both_branches_keep_unique_bind_ids_and_one_aura_mark(self):
        for program in MC.GATED_PROGRAMS:
            for branch in MC.branches(self.out["dsl"][program]):
                ids = K._declared_ids(branch)
                self.assertEqual(len(ids), len(set(ids)), f"{program}: 每支内部绑定号唯一")
                marks = [c for c in wf_dsl.iter_dsl_commands(branch, "CreateCondition")
                         if c[2] and isinstance(c[2][0], list) and c[2][0][0] == "ACUnique"]
                want = [int(K.UID_AURA)] if program != MC.CHASE_PROGRAM else []
                self.assertEqual([c[2][0][1] for c in marks], want, program)
            self.assertEqual(K.gate_branches(self.out["dsl"][program]), list(MC.branches(self.out["dsl"][program])))

    def test_chase_down_is_kept_in_both_branches(self):
        for branch in MC.branches(self.out["dsl"][MC.CHASE_PROGRAM]):
            self.assertEqual([a[13] for a in wf_dsl.iter_dsl_commands(branch, "CreateNormalAttack")],
                             [[{"min": 0.2, "max": 0.2}]])

    def test_dsl_roundtrip_gates_and_variable_scope(self):
        for program, tree in self.out["dsl"].items():
            self.assertEqual(MC.dsl_gate_problems(tree), [], program)
            self.assertEqual(L.action_dsl_element_problems(tree, MC.ELEMENT), [], program)
            self.assertEqual(L.action_dsl_subject_binding_problems(tree), [], program)
            self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [], program)
            self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [], program)
            self.assertEqual(MC.variable_scope_problems(tree), [], program)
            raw = wf_dsl.encode_amf3(tree)
            self.assertEqual(wf_dsl.parse_dsl(raw)["tree"], tree, program)
            self.assertEqual(wf_dsl.encode_amf3(wf_dsl.parse_dsl(raw)["tree"]), raw, program)
        for program, tree in self.live["dsl"].items():
            self.assertEqual(MC.variable_scope_problems(tree), [], f"live {program}")

    def test_variable_scope_gate_catches_a_consumer_left_outside(self):
        """删判定反例：把消费点留在分支外（或绑定搬到消费点之后），门禁必须报错。"""
        tree = deepcopy(self.out["dsl"][MC.PROGRAMS[0]])
        opened, closed = MC.branches(tree)
        tree[11][1].append(opened[1].pop(3))            # 斩劈参考点（含 vlv 消费点）挪到分支外
        closed[1].pop(3)
        self.assertTrue(any("outside its binding scope" in p for p in MC.variable_scope_problems(tree)))
        self.assertTrue(any(p.startswith("variable:") for p in MC.dsl_gate_problems(tree)))
        tree = deepcopy(self.live["dsl"][MC.PROGRAMS[2]])
        tree[11][1].append(tree[11][1].pop(0))           # 绑定搬到消费点之后
        self.assertTrue(MC.variable_scope_problems(tree))

    def test_layer_contribution_by_flag_state(self):
        """每整招 +5 倍/层：开旗号（队长 且 火共鸣）99 层封顶；不开保留 10 层；特殊 PF 三档始终 99。"""
        for program, tree in self.out["dsl"].items():
            gated = program in MC.GATED_PROGRAMS
            for flag_on in (True, False):
                cap = MC.layer_cap(tree, flag_on=flag_on)
                self.assertEqual(cap, 99 if (flag_on or not gated) else 10, (program, flag_on))
                block = MC.branches(tree)[0 if flag_on else 1] if gated else tree[11]
                attacks = list(wf_dsl.iter_dsl_commands(block, "CreateNormalAttack"))
                per_layer = sum(a[6][0]["vlv"][0]["max"] * n for a, n in zip(attacks, HITS[program]))
                self.assertAlmostEqual(per_layer, 5.0, places=6, msg=program)
                for layers in (0, 10, 11, 40, 99):
                    self.assertAlmostEqual(per_layer * min(layers, cap), 5.0 * min(layers, cap), places=6)
        # 40 层（常驻估计）：开旗号 +200 倍，不开 +50 倍
        main = self.out["dsl"][MC.PROGRAMS[0]]
        self.assertEqual((5 * min(40, MC.layer_cap(main, flag_on=True)),
                          5 * min(40, MC.layer_cap(main, flag_on=False))), (200, 50))

    def test_other_tree_values_are_untouched(self):
        """倍率 / 段数 / 削韧 / 伤害归属：除绑定上限与分支包裹外一格不动。"""
        def attacks(tree):
            return [(a[6], a[13], a[14]) for a in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")]

        for program in MC.PROGRAMS:
            old, new = self.live["dsl"][program], self.out["dsl"][program]
            if program in MC.GATED_PROGRAMS:
                for branch in MC.branches(new):
                    self.assertEqual(attacks(branch), attacks(old), program)
                    self.assertEqual([a[24] for a in wf_dsl.iter_dsl_commands(branch, "CreateHitArea")],
                                     [a[24] for a in wf_dsl.iter_dsl_commands(old, "CreateHitArea")])
            else:
                self.assertEqual(attacks(new), attacks(old), program)

    # ---------------------------------------------------------------- fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = MC.revise(reader(data))
        self.assertEqual(data, self.live)
        out["leader"][MC.CID][0][0] = "mutated"
        out["ability"][MC.A1][0][0] = "mutated"
        MC.branches(out["dsl"][MC.PROGRAMS[0]])[1][1][0][1][5] = 1
        out["dsl"][MC.PROGRAMS[3]][11][1][0][1][5] = 1
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key in MC.BEFORE:
            data = deepcopy(self.live)
            if kind == "cas":
                data[kind][key][0][0] += "。"
            elif kind == "dsl" and key in MC.PROGRAMS:
                data[kind][key][11][1][0][1][5] = 98
            elif kind == "dsl":                               # 722 PF 覆盖（共鸣省略依据）：首条命令参数漂移
                data[kind][key][11][1][0][1][1] += 1
            else:
                data[kind][key][-1][1] = "drift"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                MC.revise(reader(data))
            data = deepcopy(self.live)
            data[kind][key] = data[kind][key][:-1]
            with self.assertRaises(ValueError):
                MC.revise(reader(data))

    def test_new_key_already_present_is_rejected(self):
        data = deepcopy(self.live)
        data["cas"][MC.CAS_SWITCH_LEADER] = [["强化『烈焰轰鸣』：技能倍率随引擎点火层数持续提升"]]
        with self.assertRaisesRegex(ValueError, "already exists"):
            MC.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        with self.assertRaises(ValueError):
            MC.leader_rows(self.out["leader"][MC.CID])
        with self.assertRaises(ValueError):
            MC.ability1_rows(self.out["ability"][MC.A1])
        for func, key in ((MC.leader_text, MC.CAS_LEADER), (MC.slot1_text, MC.CAS_SLOT1),
                          (MC.slot2_text, MC.CAS_SLOT2), (MC.switch_text, MC.CAS_SWITCH)):
            with self.assertRaises(ValueError):
                func(self.out["cas"][key])
        for program in MC.PROGRAMS:
            with self.assertRaises(ValueError):
                MC.revise_tree(self.out["dsl"][program], program)

    def test_row_locators_are_content_based(self):
        leader = deepcopy(self.live["leader"][MC.CID])
        with self.assertRaises(ValueError):                    # 目标行挪位
            MC.leader_rows([leader[0], leader[2], leader[1], *leader[3:]])
        changed = deepcopy(leader)
        changed[7][69] = MC.PF_SKILL_PROGRAMS[0]               # 特殊 PF 调用方漂移 ⇒ 撤封顶依据要重核
        with self.assertRaisesRegex(ValueError, "629 调用方"):
            MC.leader_rows(changed)
        changed = deepcopy(leader)
        changed[12][4] = "2"                                   # 前置漂移
        with self.assertRaises(ValueError):
            MC.leader_rows(changed)
        a1 = deepcopy(self.live["ability"][MC.A1])
        a1[1][47] = "704"                                      # 旗号行已存在 / 行漂移
        with self.assertRaises(ValueError):
            MC.ability1_rows(a1)
        tree = deepcopy(self.live["dsl"][MC.PROGRAMS[0]])
        tree[11][1].insert(1, deepcopy(tree[11][1][0]))         # 第二条绑定
        with self.assertRaises(ValueError):
            MC.revise_tree(tree, MC.PROGRAMS[0])
        tree = deepcopy(self.live["dsl"][MC.CHASE_PROGRAM])
        next(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))[13] = [{"min": 0.25, "max": 0.25}]
        with self.assertRaisesRegex(ValueError, "p13"):
            MC.revise_tree(tree, MC.CHASE_PROGRAM)

    def test_self_checks_reject_extra_touch(self):
        with self.assertRaises(ValueError):
            MC.branches(self.live["dsl"][MC.PROGRAMS[0]])


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_magnus 重跑必须产出与 revise() 相同的行/面板/DSL。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = MC.revise(reader(deepcopy(cls.live)))

    def test_panel_constants_equal_revise_output(self):
        for key, rows in self.out["cas"].items():
            self.assertEqual([[K.CAS_TEXTS[key]]], rows, key)
        self.assertIn(MC.CAS_SWITCH_LEADER, K.SPEC["extra_keys"][KL.CAS])
        self.assertIn(MC.CAS_SWITCH_LEADER, K.SKILL_FLAG_TEXT_KEYS)
        self.assertIn(MC.CAS_SWITCH, K.SKILL_FLAG_TEXT_KEYS)
        self.assertEqual(K.SWITCH_LEADER_STRING, MC.CAS_SWITCH_LEADER)

    def test_plan_constants_carry_the_third_round_values(self):
        self.assertEqual(len(K.LEADER), 13)
        for index, (cols, _orig, _cur, new, _f, _label) in MC.LEADER_GROWTH.items():
            self.assertEqual([K.LEADER[index][2][col] for col in cols], [new, new], f"leader#{index}")
            self.assertEqual(K.LEADER[index][3], NEW_LEADER_DESCRIBE[index])
        self.assertEqual(len(K.PLAN[1]), 4)
        donor, source, cells, expect = K.PLAN[1][3]
        self.assertEqual((donor, source), ("1111776#0", "official"))
        self.assertEqual(expect, MC.SWITCH_DESCRIBE)
        self.assertEqual({col: cells[col] for col in (6, 13, 16, 17, 18, 70)},
                         {col: MC.SWITCH_ROW[col] for col in (6, 13, 16, 17, 18, 70)})
        # 口径 D4：能力栏封顶版保持第二批值
        self.assertEqual(K.PLAN[1][2][2][34], "4")
        self.assertEqual([(c[102], c[113]) for _d, _s, c, _e in K.PLAN[2]], [("10", "15000")] * 2)
        self.assertEqual((K.PLAN[3][4][2][102], K.PLAN[3][4][2][113]), ("10", "1000"))
        self.assertEqual((K.IGNITION_DSL_CAP, K.IGNITION_LEADER_CAP), MC.IGNITION_CAP)
        self.assertEqual((K.LEADER_SKILL_FLAG, K.LEADER_SKILL_FLAG_KIND), (MC.SKILL_FLAG, MC.SKILL_FLAG_KIND))

    def test_leader_gate_and_pf_growth_reproduce_revise_output(self):
        """生成器的两道新变换直接作用在 live（= 第二批生成器输出）上，结果 == revise()（不需要官方基线）。"""
        for program in MC.GATED_PROGRAMS:
            gated, meta = K.leader_gate(self.live["dsl"][program])
            self.assertEqual(gated, self.out["dsl"][program], program)
            self.assertEqual((meta["open_cap"], meta["closed_cap"]), (99, 10))
            with self.assertRaises(K.KitError):                   # 重复套用
                K.leader_gate(gated)
        for program in MC.PF_SKILL_PROGRAMS:
            tree = deepcopy(self.live["dsl"][program])
            tree[11][1].pop(0)
            for attack in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"):
                del attack[6][0]["vlv"]
            rebuilt, meta = K.pf_ignition_growth(tree, tuple(HITS[program]))
            self.assertEqual(rebuilt, self.out["dsl"][program], program)
            self.assertEqual(meta["max_layers"], 99)
        drifted = deepcopy(self.live["dsl"][MC.PROGRAMS[0]])
        drifted[11][1][0][1][5] = 99
        with self.assertRaises(K.KitError):                       # 上限不是第二批的 10 ⇒ 拒绝
            K.leader_gate(drifted)

    @unittest.skipUnless(_LIVE, "需要 .cdn/cn 官方基线与 live store")
    def test_generator_rows_equal_revise_output(self):
        from test_midautumn_kit_magnus import _ReadOnlyCtx
        built = K.build_rows(_ReadOnlyCtx())
        self.assertEqual(built["leader"], self.out["leader"][MC.CID])
        self.assertEqual(built["ability"][MC.A1], self.out["ability"][MC.A1])
        self.assertEqual(sorted(built["capabilities"]), ["dash-parameter-v1"])

    @unittest.skipUnless(_LIVE, "需要 .cdn/cn 官方基线与 live store")
    def test_generator_trees_equal_revise_output(self):
        """K.build_skill_trees = write_skills 落盘的全部树；本模块改的 6 棵逐字相等。"""
        from test_midautumn_kit_magnus import _ReadOnlyCtx, _stub_families
        built = K.build_skill_trees(_ReadOnlyCtx(), _stub_families())
        trees = {program: tree for _kind, _level, program, tree, _meta in built}
        self.assertEqual([kind for kind, *_rest in built],
                         ["skill", "skill", "ignite", "pf_skill", "pf", "pf_skill", "pf", "pf_skill", "pf"])
        for program in MC.PROGRAMS:
            self.assertEqual(trees[program], self.out["dsl"][program], program)
        for kind, level, program, tree, meta in built:
            if kind in ("skill", "ignite"):
                self.assertEqual(meta["leader_gate"]["flag"], 2, program)
                K.burst_window_problems(program, tree)              # 克拉莉丝使用者寿命门禁仍过（两支各一处）
            self.assertEqual(wf_dsl.player_side_dsl_problems(tree), [], program)

    @unittest.skipUnless(_LIVE, "需要 .cdn/cn 官方基线与 live store")
    def test_flag_row_kinds_have_precedents(self):
        """704 在官方能力表有 11 行先例（官方队长表 0 行 ⇒ 不进队长表）；前置 42 在官方能力表 4 行。"""
        from test_midautumn_kit_magnus import _ReadOnlyCtx
        ctx = _ReadOnlyCtx()
        counts = {"ability_704": 0, "ability_pre42": 0, "leader_704": 0}
        for value in ctx.official_flat(KL.ABILITY).values():
            for row in core.read_csv_lines(value):
                row = list(row)
                if len(row) > 47 and row[5] == "0" and row[47] == "704":
                    counts["ability_704"] += 1
                if len(row) > 13 and "42" in (row[6], row[13]):
                    counts["ability_pre42"] += 1
        for value in ctx.official_flat(KL.LEADER).values():
            for row in core.read_csv_lines(value):
                if len(row) > 45 and row[45] == "704":
                    counts["leader_704"] += 1
        self.assertGreaterEqual(counts["ability_704"], 1)
        self.assertGreaterEqual(counts["ability_pre42"], 1)
        self.assertEqual(counts["leader_704"], 0, "官方队长表 704 零先例（若出现先例可重议 U6）")
        live = core.read_csv_lines(ctx.live_flat(KL.ABILITY)[MC.SWITCH_PRECEDENT[0]])
        precedent = list(live[MC.SWITCH_PRECEDENT[1]])
        self.assertEqual(set(changed_cells(precedent, self.out["ability"][MC.A1][3])), {0, 2, 18, 70})

    @unittest.skipUnless(_LIVE, "需要 live store")
    def test_no_other_key_references_the_ignition_state(self):
        """共鸣省略依据的全表面：live 整张能力表 / 队长表里写着 11999001 的只有玛格诺斯自己的键（revise() 已读的那些）。"""
        from test_midautumn_kit_magnus import _ReadOnlyCtx
        ctx = _ReadOnlyCtx()
        hits = set()
        for table, logical in (("ability", KL.ABILITY), ("leader", KL.LEADER)):
            for key, value in ctx.live_flat(logical).items():
                if UID in value:
                    hits.add((table, key))
        self.assertEqual(hits, {("leader", MC.CID), ("ability", MC.A2), ("ability", f"{MC.CID}3")})
        self.assertTrue(hits <= {("leader", MC.CID)} | {("ability", key) for key in (MC.A1, *MC.BASIS_ABILITIES)})


WORKSPACE = ROOT / "work/character_packs" / MC.PACKAGES[0]


class CandidateTests(unittest.TestCase):
    """候选 ma-magnus：无漂移（REVIEWED_DRIFT = {}）、版本只升不降、本轮输出可干跑回写；只读，不写包。"""

    @unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                         and (ROOT / "mod-tools/profiles.json").is_file(),
                         "local candidate workspace required")
    def test_candidate_has_no_drift_and_accepts_the_revision_dry(self):
        import zlib
        from wf_character_revision import RevisionCandidate, encode_tree
        import wf_share_update_codec as X
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        current = json.loads(before)
        version = tuple(int(x) for x in current["package_version"].split("."))
        target = tuple(int(x) for x in MC.PACKAGE_VERSION[MC.PACKAGES[0]].split("."))
        live = load_fixture()
        out = MC.revise(reader(deepcopy(live)))
        # 主会话暂存回写后：候选 = 本轮输出、版本 = 目标；回写前：候选 = live（本模块读取的 20 项逐字相同）。
        written_back = version >= target
        want = out if written_back else live
        if written_back:
            self.assertEqual(version, target)
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=MC.CID, code_name=MC.CODE,
                                      package_version=MC.PACKAGE_VERSION[MC.PACKAGES[0]],
                                      snapshot_key="revision_20260927c",
                                      reviewed_input_drift=MC.REVIEWED_DRIFT,
                                      baseline_factory=lambda *a, **k: None)
        tables = {"leader": "master/ability/leader_ability.orderedmap",
                  "ability": "master/ability/ability.orderedmap",
                  "cas": "master/string/custom_ability_string.orderedmap"}
        for kind, logical in tables.items():
            rows = X.unpack(candidate.read("common", logical))
            for key, value in want[kind].items():
                self.assertEqual(X.csv_read(rows[key]), value, f"{kind}:{key}")
            if not written_back and kind == "cas":
                self.assertNotIn(MC.CAS_SWITCH_LEADER, rows)
        for program, tree in want["dsl"].items():
            raw = candidate.read("common", wf_dsl.dsl_logical(program))
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], tree, program)
        if not written_back:
            for kind, logical in tables.items():
                candidate.splice(logical, out[kind])
            for program, tree in out["dsl"].items():
                candidate.emit("common", wf_dsl.dsl_logical(program), encode_tree(tree))
            evidence = candidate.finish({"dry_run": True}, apply=False)
            self.assertFalse(evidence["applied"])
            self.assertEqual(sorted(f["logical_path"] for f in evidence["changed_files"]),
                             sorted([*tables.values(), *(wf_dsl.dsl_logical(p) for p in MC.PROGRAMS)]))
        self.assertEqual(before, manifest.read_bytes())


class MirrorTests(unittest.TestCase):
    PATHS = (ROOT / MC.DESIGN_REL, ROOT / MC.PANEL_REL)

    def setUp(self):
        if not all(path.is_file() for path in self.PATHS):
            self.skipTest("midautumn design mirrors missing")
        self.docs = [json.loads(path.read_text(encoding="utf-8")) for path in self.PATHS]

    def test_mirror_update_satisfies_the_kit(self):
        """纯函数重算：kit 对账（_design_problems）为空、面板镜像逐行 == 覆盖串（写回后 kit 的 DesignDocumentTests 转绿）。"""
        design, panel = MC.mirror_updates(*self.docs)
        self.assertEqual(K._design_problems(design), [])
        self.assertIn(MC.MIRROR_TAG, design["plan_rework1"])
        block = design["plan_rework1"][MC.MIRROR_TAG]
        self.assertEqual((block["ignition_caps"], block["skill_flag"]["flag"], block["skill_flag"]["kind"]),
                         ({"closed": 10, "open": 99}, 2, "704"))
        self.assertEqual(len(design["plan_rework1"]["ability"]["keys"][MC.A1]["records"]), 4)
        self.assertEqual([m["merged"] for m in block["panel_merge"]], [MERGED_PF3_LINE, MERGED_LAYER_LINE])
        self.assertEqual([line["text"] for line in panel["leader"]["lines"]],
                         K.CAS_TEXTS[K.LEADER_OVERRIDE].split("\n"))
        self.assertEqual([line["text"] for line in panel["leader"]["lines"]], NEW_LEADER_PANEL.split("\n"))
        for entry in panel["abilities"]:
            slot = int(entry["index"])
            if slot in (1, 2, 3):
                self.assertEqual([line["text"] for line in entry["lines"]],
                                 K.CAS_TEXTS[K.SLOT_OVERRIDE[slot]].replace(K.MAIN_ICON, "").split("\n"))
        self.assertEqual(panel["notes"][-1], MC.MIRROR_NOTE)
        # 第二批标记块原样保留（历史）
        self.assertEqual(design["plan_rework1"].get("balance_20260927b"),
                         self.docs[0]["plan_rework1"].get("balance_20260927b"))

    def test_mirror_update_is_idempotent_and_pure(self):
        before = deepcopy(self.docs)
        once = MC.mirror_updates(*self.docs)
        self.assertEqual(self.docs, before)
        self.assertEqual(MC.mirror_updates(*once), once)

    def test_mirrors_are_synced_once_written(self):
        """写回（主会话 ``python -B -X utf8 mod-tools/wf_balance_20260927c_magnus.py --write``）之后必须无差异。"""
        if MC.MIRROR_TAG not in self.docs[0].get("plan_rework1", {}):
            self.skipTest("设计镜像待主会话 --write 回写（本单元不写 work/character_packs/*）")
        self.assertEqual(MC.sync_mirrors(ROOT, write=False), [])


if __name__ == "__main__":
    unittest.main()
