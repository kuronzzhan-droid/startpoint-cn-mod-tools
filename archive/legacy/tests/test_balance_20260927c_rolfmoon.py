# -*- coding: utf-8 -*-
"""罗尔夫「不落幕的安可」149986 ``black_wolf_knight_moon`` 2026-09-27 第三轮（成长复核）。

fixture = live 输入快照（``fixtures/balance_20260927c_rolfmoon.json``，链尾 1.4.1053 只读取数），驱动 ``revise()``：
每处改动的前后值、档位与取整、未改行/未改列逐字保留、面板数字 == 行值、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、
合法性门禁为空；live 输入 == 第二批输出（链式核对）；生成器输出 == revise() 输出（装配对比需要 ``.cdn/cn`` 官方基线与
live store，缺时跳过）；设计镜像已同步或处于「停在第二批、按本模块补齐 == 生成器」的过渡态；候选干跑拼接（缺时跳过）。
面板同条件合并（能力4 两行 → 一行）：合并行逐字、数据条件逐格相同、各面板同条件组按数据重算、
``wf_panel_merge_check`` 通过（仓库内校验器，硬依赖）、共鸣省略依据（本角色无固有状态）；
主会话口径 3：本轮返回的两块面板「风属性共鸣时：」→「风属性共鸣时，」（只改标点，check 的 orig 在测试里显式规范化）。
``_context`` 是 revise() 不读取的 live 参照（能力1/2/3/5、其余面板、文案），只用来核对「保留」项与合并/共鸣依据。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_rolfmoon as B2  # noqa: E402
import wf_balance_20260927c_rolfmoon as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_midautumn_kit_rolf as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_panel_merge_check as PMC  # noqa: E402   面板合并校验器（仓库内，硬依赖）

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927c_rolfmoon.json"
B2_FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_rolfmoon.json"
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
TABLES = {"leader": "master/ability/leader_ability.orderedmap", "ability": "master/ability/ability.orderedmap",
          "cas": "master/string/custom_ability_string.orderedmap"}
A3_KEY = B2.A3_KEY
#: 队长表效果列（instant c45–c50 / during c107–c112），与能力表 M.ABILITY_EFFECT_COLUMNS 同义。
LEADER_EFFECT_COLUMNS = frozenset(range(45, 51)) | frozenset(range(107, 113))
#: 固有状态授予内容 kind（461 自身/友方、413 敌方、436 最近敌人、459 触发敌人）。
GRANT_KINDS = {"461", "413", "436", "459"}


def normalize_resonance_punct(text: str) -> str:
    """口径 3 的规范化步骤（测试里显式写出，不借模块实现）：「X属性共鸣时：」→「X属性共鸣时，」，
    「：」后直接换行的并成一行。"""
    return re.sub(r"([火水雷风光暗]属性共鸣时)[：:]\n?", r"\1，", text)


def same_condition_groups(rows: list[list[str]], effect_columns) -> list[tuple[int, ...]]:
    """除效果列外逐格相同的行组（≥2 行）。"""
    groups: dict[tuple, list[int]] = {}
    for index, row in enumerate(rows):
        groups.setdefault(tuple(v for c, v in enumerate(row) if c not in effect_columns), []).append(index)
    return [tuple(v) for v in groups.values() if len(v) > 1]


def load() -> tuple[dict, dict]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}, data["_context"]


def reader(data: dict):
    def read(kind, key):
        if key not in data.get(kind, {}):
            raise KeyError(f"{kind}:{key}")
        return data[kind][key]
    return read


def cell_diff(a: list[str], b: list[str]) -> dict[int, tuple[str, str]]:
    return {i: (x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y}


def version(text: str) -> tuple[int, ...]:
    return tuple(map(int, text.split(".")))


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


def _kit_ctx():
    import wf_midautumn_common as MC
    import wf_midautumn_specs as MS
    import wf_seasonal7_build as B
    return B.KitContext(MC.MAPack(MS.get_spec("rolf"), record_sources=False))


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live, cls.context = load()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def old(self, kind, key):
        return self.live[kind][key]

    # ------------------------------------------------------------ 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys}, set(M.BEFORE))

    def test_live_input_is_the_batch2_output(self):
        """链式核对：live 1.4.1053 的三个键 == 第二批 revise() 对第二批 fixture 的输出；能力3 同理（本轮不读不写）。"""
        data = json.loads(B2_FIXTURE.read_text(encoding="utf-8"))
        b2 = B2.revise(reader({k: v for k, v in data.items() if not k.startswith("_")}))
        self.assertEqual(b2["leader"][M.LEADER_KEY], self.old("leader", M.LEADER_KEY))
        self.assertEqual(b2["ability"][M.A6_KEY], self.old("ability", M.A6_KEY))
        self.assertEqual(b2["cas"][M.CAS_LEADER], self.old("cas", M.CAS_LEADER))
        self.assertEqual(b2["ability"][A3_KEY], self.context["ability"][A3_KEY])
        self.assertEqual(b2["cas"][B2.CAS_A3], self.context["cas"][B2.CAS_A3])
        self.assertEqual([[M.B_PANEL_LEADER]], self.old("cas", M.CAS_LEADER))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (str(K.CID), K.CODE))
        self.assertEqual(M.PACKAGES, ["ma-rolf"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-rolf": "1.0.2"})     # 候选现值 1.0.1，只升不降
        self.assertEqual((M.CAPABILITIES, M.REVIEWED_DRIFT), ([], {}))
        self.assertEqual((M.CAS_LEADER, M.ELEMENT, M.MAIN_ICON), (K.CAS_LEADER, K.ELEMENT, K.MAIN_ICON))
        json.dumps(self.out["notes"], ensure_ascii=False)
        self.assertFalse(self.out["notes"]["runtime_verified"])

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {M.A6_KEY})                  # 能力4 行只读（核对合并组）
        self.assertEqual(set(out["leader"]), {M.LEADER_KEY})
        # 队长（成长 + 第4行强化条目）、能力4 合并、能力3 拆行 + 两条强化条目（技能强化文案 R2）
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER, M.CAS_A4, M.CAS_A3, M.CAS_FLAG, M.CAS_FLAG2})
        for kind in ("text", "table", "action", "server_text", "dsl"):             # 技能说明本来就只写本体，不改
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])

    # ------------------------------------------------------------ 队长 / 能力6

    def test_leader_only_the_direct_growth_cells_change(self):
        old, new = self.old("leader", M.LEADER_KEY), self.out["leader"][M.LEADER_KEY]
        self.assertEqual((len(old), len(new)), (7, 7))
        diffs = {i: cell_diff(a, b) for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(diffs, {3: {49: ("20000", "80000"), 50: ("20000", "80000")},
                                 4: {49: ("20000", "70000"), 50: ("20000", "70000")}})
        self.assertEqual((new[3][45], new[4][45]), ("32", "33"))
        for row in (new[3], new[4]):                                 # 风共鸣 + 每 100 直击，不限次
            self.assertEqual((row[4], row[9], row[25], row[26], row[28], row[32]),
                             ("2", "Green", "20", "7", "10000000", "(None)"))

    def test_ability6_only_the_growth_cells_change(self):
        old, new = self.old("ability", M.A6_KEY), self.out["ability"][M.A6_KEY]
        self.assertEqual((len(old), len(new)), (7, 7))
        diffs = {i: cell_diff(a, b) for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(diffs, {3: {51: ("2000", "7000"), 52: ("2000", "7000")},
                                 5: {51: ("5000", "35000"), 52: ("5000", "35000")},
                                 6: {51: ("5000", "35000"), 52: ("5000", "35000")}})
        self.assertEqual(new[:3] + new[4:5], old[:3] + old[4:5])     # 422×2、704、碰撞回槽逐字不动
        self.assertEqual((new[3][6], new[3][13], new[3][47]), ("42", "2", "693"))
        for row, kind in ((new[5], "32"), (new[6], "33")):          # IT 246 承载行：前置 42、无共鸣（与原行一致）
            self.assertEqual((row[6], row[13], row[27], row[32], row[34], row[47]),
                             ("42", "0", "246", "6000000", "(None)", kind))

    def test_tiers_and_rounding_follow_the_table(self):
        want = {("leader", 3): ("100000", (4, 5), "80000"), ("leader", 4): ("100000", (7, 10), "70000"),
                ("ability", 3): ("10000", (7, 10), "7000"), ("ability", 5): ("50000", (7, 10), "35000"),
                ("ability", 6): ("50000", (7, 10), "35000")}
        table = {**{("leader", i): v for i, v in M.LEADER_GROWTH.items()},
                 **{("ability", i): v for i, v in M.A6_GROWTH.items()}}
        self.assertEqual(set(want), set(table))
        for key, (original, factor, new) in want.items():
            with self.subTest(key=key):
                self.assertEqual((table[key][0], table[key][3], table[key][2]), (original, factor, new))
                self.assertEqual(M.rounded_growth(original, factor), new)
                self.assertGreaterEqual(int(new) * 3, int(original) * 2)
        # 第二批 live 值与第二批模块常量一致（数值表「批二」列）。
        self.assertEqual({v[1] for v in M.LEADER_GROWTH.values()}, {B2.DIRECT_GROWTH[1]})
        self.assertEqual((M.A6_GROWTH[3][1], M.A6_GROWTH[5][1]), (B2.DIRECT_GROWTH_IC693[1], B2.KEEP_FRAME_GROWTH[1]))
        # 原值（第二批前）与第二批模块的前像一致。
        self.assertEqual((M.LEADER_GROWTH[3][0], M.A6_GROWTH[3][0], M.A6_GROWTH[5][0]),
                         (B2.DIRECT_GROWTH[0], B2.DIRECT_GROWTH_IC693[0], B2.KEEP_FRAME_GROWTH[0]))

    def test_auto_describe_renders_the_new_rows(self):
        leader, a6 = self.out["leader"][M.LEADER_KEY], self.out["ability"][M.A6_KEY]
        self.assertEqual(D.describe_line(leader[3], "leader_ability"),
                         "风·编成≥6 时: 编成直接攻击≥100 → 赋予全队(风) 攻击力 80%")
        self.assertEqual(D.describe_line(leader[4], "leader_ability"),
                         "风·编成≥6 时: 编成直接攻击≥100 → 赋予全队(风) Direct伤害 70%")
        self.assertEqual(D.describe_line(a6[3], "ability"),
                         "队长 且 风·编成≥6 时: 编成直接攻击≥100 → 赋予全队(风) 独立乘区Direct伤害 7%")
        self.assertEqual(D.describe_line(a6[5], "ability"), "队长 时: 状态KeepFrameFixed速度↑≥1 → 自身 攻击力 35%")
        self.assertEqual(D.describe_line(a6[6], "ability"), "队长 时: 状态KeepFrameFixed速度↑≥1 → 自身 Direct伤害 35%")

    def test_ability3_capped_rows_are_kept(self):
        """口径 D4：能力栏的封顶版（能力3 #1/#2 持有型 +100%）保持第二批值，本轮不读不写。"""
        a3 = self.context["ability"][A3_KEY]
        self.assertEqual([(r[97], r[109], r[113]) for r in a3[1:3]], [("214", "0", "100000"), ("214", "1", "100000")])
        self.assertNotIn(A3_KEY, self.out["ability"])

    # ------------------------------------------------------------ 面板

    def test_leader_panel_changes_lines_5_and_6_only(self):
        """数字只改第 5/6 行；第 4 行（704 开关行）改成「风属性共鸣时，」+ 强化条目（技能强化文案 R2）；
        其余 4 行只把「风属性共鸣时：」改成「风属性共鸣时，」（口径 3），字面逐字。"""
        old = self.old("cas", M.CAS_LEADER)[0][0].split("\n")
        new = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual((len(old), len(new)), (7, 7))
        self.assertEqual(new[:3] + new[6:], [line.replace("风属性共鸣时：", "风属性共鸣时，") for line in old[:3] + old[6:]])
        self.assertEqual(old[3], "风属性共鸣时：自身发动技能时，技能所赋予的最大速度固定效果强化至4档，且不衰减技能槽能量获取")
        self.assertEqual(new[3], "风属性共鸣时，强化『月下独奏』：赋予的最大速度固定效果强化至最高档，且不衰减技能槽能量获取")
        self.assertEqual(new[3], "风属性共鸣时，" + self.out["cas"][M.CAS_FLAG2][0][0])
        self.assertEqual(sum("风属性共鸣时：" in line for line in old), 6)
        self.assertEqual(new[4], "风属性共鸣时，风属性角色每造成100次直接攻击，风属性角色攻击力＋80%、"
                                 "直击伤害＋70%，直击伤害额外乘区＋7%")
        self.assertEqual(new[5], "最大速度固定效果持续期间，每持续1秒，自身攻击力＋35%、直击伤害＋35%")

    def test_returned_panels_use_the_comma_resonance(self):
        """口径 3：本轮返回的每块覆盖面板都没有「X属性共鸣时：」；规范化只动标点（逐字符比对只差「：」→「，」），
        没有「：」后换行的写法（行数不变）；未返回的能力1/3 面板不在本轮范围（仍是「：」、不返回）。"""
        for key, rows in self.out["cas"].items():
            self.assertNotRegex(rows[0][0], "属性共鸣时[：:]", key)
        before = M.UNNORMALIZED_PANEL_LEADER
        after = M.PRE_FLAG_PANEL_LEADER                   # 规范化后、第 4 行强化条目改写前
        self.assertEqual(normalize_resonance_punct(before), after)
        self.assertEqual(M.normalize_resonance(before), after)
        self.assertEqual(len(before), len(after))
        self.assertEqual({(a, b) for a, b in zip(before, after) if a != b}, {("：", "，")})
        self.assertEqual(before.count("\n"), after.count("\n"))
        lines = after.split("\n")
        lines[M.FLAG2_LINE_INDEX] = M.NEW_FLAG2_LINE
        self.assertEqual("\n".join(lines), self.out["cas"][M.CAS_LEADER][0][0])
        self.assertEqual(M.normalize_resonance("风属性共鸣时：\n自身技能槽＋50%"), "风属性共鸣时，自身技能槽＋50%")
        # 能力1 面板不在本轮范围（仍是「：」、不返回）；能力3 面板随技能强化文案一并返回 ⇒ 按口径 3 规范化。
        self.assertIn("风属性共鸣时：", self.context["cas"][f"{M.CAS_LEADER}_1"][0][0])
        self.assertNotIn(f"{M.CAS_LEADER}_1", self.out["cas"])
        self.assertIn("风属性共鸣时：", self.live["cas"][M.CAS_A3][0][0])
        self.assertIn(M.CAS_A3, self.out["cas"])
        # 共鸣与数据相符（不需要按口径 4 删）：冲刺两行 = 能力6 #1/#2，L4 = 能力6 #4（704）都带队长 + 风编成≥6
        a6 = self.out["ability"][M.A6_KEY]
        for index, kind in ((1, "422"), (2, "422"), (4, "704")):
            self.assertIn(kind, (a6[index][47], a6[index][109]), index)
            self.assertTrue(D.describe_line(a6[index], "ability").startswith("队长 且 风·编成≥6 时: "), index)

    def test_panel_agrees_with_the_data(self):
        leader, a6 = self.out["leader"][M.LEADER_KEY], self.out["ability"][M.A6_KEY]
        pct = lambda value: f"＋{int(value) // 1000}%"    # noqa: E731
        lines = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertIn(f"攻击力{pct(leader[3][49])}、直击伤害{pct(leader[4][49])}，直击伤害额外乘区{pct(a6[3][51])}", lines[4])
        self.assertIn(f"自身攻击力{pct(a6[5][51])}、直击伤害{pct(a6[6][51])}", lines[5])
        self.assertEqual(re.findall(r"＋(\d+)%", lines[4]), ["80", "70", "7"])

    def test_panel_texts_obey_the_project_rules(self):
        for key in (M.CAS_LEADER, M.CAS_A4):
            text = self.out["cas"][key][0][0]
            self.assertNotIn("／", text)
            self.assertEqual(L.panel_override_capability(key), "panel-description-override-v2")
            for line in text.split("\n"):
                self.assertEqual(KL.panel_problems(line), [], line)
                for word in ("可无限", "无上限", "自身为队长时", "生命值100%以下", "觉醒后", "(None)", "<icon"):
                    self.assertNotIn(word, line)
        self.assertEqual(B2.panel_problems(self.out["cas"]), [])
        self.assertEqual(M.merge_text_problems(self.out["cas"]), [])

    def test_texts_do_not_carry_the_growth_numbers(self):
        texts = [cell for row in self.context["text"][M.CID] for cell in row]
        texts += [cell for row in self.context["server_text"][M.CID] for cell in row]
        texts += [fields[1] for _k, fields in self.context["action"][M.CODE]]
        texts += [rows[0][0] for rows in self.context["cas"].values()]
        for text in texts:
            for word in ("每造成100次", "每持续1秒", "＋80%", "＋70%", "＋35%"):
                self.assertNotIn(word, text)

    # ------------------------------------------------------------ 合法性

    def test_native_legality_gates_are_empty(self):
        cas_keys = set(K.CAS_TEXTS)
        for index, row in enumerate(self.out["leader"][M.LEADER_KEY]):
            label = f"leader#{index}"
            self.assertEqual(L.client_legality_problems("leader_ability", row), [], label)
            self.assertEqual(L.declared_block_field_problems("leader_ability", row), [], label)
            self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, "leader_ability"), [], label)
            self.assertEqual(KL.row_problems("leader_ability", row), {}, label)
        for index, row in enumerate(self.out["ability"][M.A6_KEY]):
            label = f"ability:{M.A6_KEY}#{index}"
            self.assertEqual(L.client_legality_problems("ability", row), [], label)
            self.assertEqual(L.declared_block_field_problems("ability", row), [], label)
            self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, "ability"), [], label)
            self.assertEqual(L.ability_element_column_problems("ability", row, M.ELEMENT), [], label)
            self.assertEqual(KL.row_problems("ability", row, M.ELEMENT), {}, label)
        for index in (3, 5, 6):
            self.assertEqual(L.required_client_capabilities("ability", self.out["ability"][M.A6_KEY][index]), [])

    # ------------------------------------------------------------ fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["leader"][M.LEADER_KEY][3][49] = "mutated"
        out["ability"][M.A6_KEY][5][51] = "mutated"
        out["cas"][M.CAS_LEADER][0][0] = "mutated"
        out["cas"][M.CAS_A4][0][0] = "mutated"
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.live)
            data[kind][key][0][0] += "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))
            data = deepcopy(self.live)
            data[kind][key] = None
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        for kind in ("leader", "ability", "cas"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.leader_rows(self.out["leader"][M.LEADER_KEY])
        with self.assertRaises(ValueError):
            M.ability6_rows(self.out["ability"][M.A6_KEY])
        with self.assertRaises(ValueError):
            M.leader_text(self.out["cas"][M.CAS_LEADER])
        with self.assertRaises(ValueError):
            M.ability4_text(self.out["cas"][M.CAS_A4])
        # 第二批前的旧态（100%/10%/50%）同样拒绝。
        rows = deepcopy(self.old("leader", M.LEADER_KEY))
        rows[3][49] = rows[3][50] = rows[4][49] = rows[4][50] = "100000"
        with self.assertRaises(ValueError):
            M.leader_rows(rows)

    def test_row_locators_are_content_based(self):
        leader = self.old("leader", M.LEADER_KEY)
        for mutate in (lambda r: r[3].__setitem__(32, "10"), lambda r: r[4].__setitem__(46, "0"),
                       lambda r: r.__setitem__(slice(3, 5), [r[4], r[3]]), lambda r: r.pop()):
            rows = deepcopy(leader)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.leader_rows(rows)
        a6 = self.old("ability", M.A6_KEY)
        for mutate in (lambda r: r[3].__setitem__(6, "0"), lambda r: r[5].__setitem__(27, "235"),
                       lambda r: r.__setitem__(slice(5, 7), [r[6], r[5]]), lambda r: r[6].__setitem__(13, "2"),
                       lambda r: r.append(list(r[0])), lambda r: r[0].__setitem__(2, "attack_green")):
            rows = deepcopy(a6)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.ability6_rows(rows)
        with self.assertRaises(ValueError):
            M.leader_text([[M.B_PANEL_LEADER + "\n"]])


class PanelMergeTests(unittest.TestCase):
    """面板同条件合并（能力4）与共鸣省略依据；按本轮数据重核扫描 panel_merge/scan.json。"""

    @classmethod
    def setUpClass(cls):
        cls.live, cls.context = load()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_merged_line_verbatim(self):
        self.assertEqual(self.live["cas"][M.CAS_A4],
                         [["风属性共鸣时：自身技能槽＋50%\n风属性共鸣时：赋予风属性角色技能充能速度＋10%"]])
        self.assertEqual(self.out["cas"][M.CAS_A4], [["风属性共鸣时，自身技能槽＋50%，赋予风属性角色技能充能速度＋10%"]])
        # 结构：条件只写一次（「，」），两个对象（自身 / 赋予风属性角色）的效果原措辞与数值逐字保留，用「，」分开。
        effects = [line.removeprefix("风属性共鸣时：") for line in M.OLD_A4_LINES]
        self.assertEqual(M.NEW_A4_LINES, ("风属性共鸣时，" + "，".join(effects),))
        self.assertEqual(M.PANEL_MERGES, {M.CAS_A4: (M.A4_KEY, (0, 1), (0, 1), M.OLD_A4_LINES, M.NEW_A4_LINES)})
        self.assertEqual(M.PREFIX_DROPS, {})

    def test_merge_group_is_one_data_condition(self):
        rows = self.live["ability"][M.A4_KEY]
        self.assertEqual(M.ability4_rows_problems(rows), [])
        diff = {c for c, (a, b) in enumerate(zip(rows[0], rows[1])) if a != b}
        self.assertEqual(diff, {47, 48, 49, 51, 52})                        # 只有效果列不同
        self.assertLessEqual(diff, M.ABILITY_EFFECT_COLUMNS)
        self.assertEqual([D.describe_line(r, "ability") for r in rows],
                         ["风·编成≥6 时: 自身 技能槽 50%", "风·编成≥6 时: 赋予全队(风) 技能槽充能 10%"])
        self.assertEqual(re.findall(r"＋(\d+)%", self.out["cas"][M.CAS_A4][0][0]),
                         [str(int(rows[0][51]) // 1000), str(int(rows[1][51]) // 1000)])   # 数字 == 行值

    def test_other_same_condition_groups_are_already_one_line_or_skipped(self):
        """按数据（除效果列外逐格相同）重算各面板的同条件组：只有能力4 需要新合并，其余已是一行或按规则不并。"""
        abilities = {**self.context["ability"], M.A4_KEY: self.live["ability"][M.A4_KEY],
                     M.A6_KEY: self.out["ability"][M.A6_KEY]}
        self.assertEqual(sorted(abilities), [f"{M.CID}{n}" for n in range(1, 7)])
        got = {key: same_condition_groups(rows, M.ABILITY_EFFECT_COLUMNS) for key, rows in abilities.items()}
        got["leader"] = same_condition_groups(self.out["leader"][M.LEADER_KEY], LEADER_EFFECT_COLUMNS)
        self.assertEqual(got, {"leader": [(0, 1, 2, 5, 6), (3, 4)], "1499861": [], "1499862": [],
                               "1499863": [(1, 2)], "1499864": [(0, 1)], "1499865": [], "1499866": [(5, 6)]})
        leader = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertIn("全体增益效果的持续时间＋100%（包括贯穿、最大速度固定）", leader[0])     # #0–#2 已是 L1
        self.assertTrue(leader[6].startswith("风属性共鸣时，战斗开始时，"))                  # #5/#6 = L7，文案条件不同
        self.assertIn("攻击力＋80%、直击伤害＋70%", leader[4])                              # #3/#4 已是 L5
        self.assertIn("自身攻击力＋35%、直击伤害＋35%", leader[5])                          # 能力6 #5/#6 已是队长 L6
        a3 = self.context["cas"][B2.CAS_A3][0][0].split("\n")
        self.assertIn("自身攻击力＋100%、直击伤害＋100%", a3[1])                            # 能力3 #1/#2 已是 L2
        self.assertEqual(set(M.NOT_MERGED), {f"{M.CAS_LEADER} L1+L7", f"{M.CAS_LEADER}_3 L1+L3", "already_one_line"})
        # 能力3 面板本轮因技能强化文案拆行而返回（不是同条件合并）；未改的覆盖面板（能力1/2/5/6）不返回，逐字保留。
        self.assertIn(M.CAS_A3, self.out["cas"])
        for n in (1, 2, 5, 6):
            self.assertNotIn(f"{M.CAS_LEADER}_{n}", self.out["cas"])
            self.assertIn(f"{M.CAS_LEADER}_{n}", self.context["cas"])

    def test_resonance_omission_basis(self):
        """本角色无固有状态：队长与能力 1–6 没有任何授予行 ⇒ 无可省的「X属性共鸣时，」；合并行保留共鸣条件。"""
        rows = [("leader", r, 45, 107) for r in self.out["leader"][M.LEADER_KEY]]
        abilities = {**self.context["ability"], M.A4_KEY: self.live["ability"][M.A4_KEY],
                     M.A6_KEY: self.out["ability"][M.A6_KEY]}
        rows += [("ability", r, 47, 109) for key in sorted(abilities) for r in abilities[key]]
        self.assertEqual([(t, r[i], r[d]) for t, r, i, d in rows if r[i] in GRANT_KINDS or r[d] in GRANT_KINDS], [])
        self.assertEqual(M.PREFIX_DROPS, {})
        self.assertIn("无固有状态", M.RESONANCE_BASIS)
        self.assertTrue(self.out["cas"][M.CAS_A4][0][0].startswith("风属性共鸣时，"))
        for row in self.live["ability"][M.A4_KEY]:
            self.assertEqual((row[6], row[9], row[11]), ("2", "600000", "Green"))   # 数据前置不动（风共鸣）

    def test_check_merge_passes(self):
        # 能力4：orig 先按口径 3 显式规范化（「：」→「，」），再核合并；不规范化同样通过（合并行本来就重写条件）。
        live_a4 = self.live["cas"][M.CAS_A4][0][0]
        orig_a4 = normalize_resonance_punct(live_a4)
        self.assertEqual(orig_a4, "风属性共鸣时，自身技能槽＋50%\n风属性共鸣时，赋予风属性角色技能充能速度＋10%")
        for orig in (orig_a4, live_a4):
            result = PMC.check(orig, self.out["cas"][M.CAS_A4][0][0], [])
            self.assertTrue(result["ok"], result["errors"])
            self.assertEqual((result["errors"], result["warnings"]), ([], []))
            self.assertEqual(result["columns"][0]["mapping"], {1: 1, 2: 1})
            self.assertEqual(result["columns"][0]["kinds"], {1: "merge"})
        # 负对照：删掉一个效果 / 改数值 / 没授权删共鸣 都会被拒。
        for bad in ("风属性共鸣时，自身技能槽＋50%", "风属性共鸣时，自身技能槽＋55%，赋予风属性角色技能充能速度＋10%",
                    "自身技能槽＋50%，赋予风属性角色技能充能速度＋10%"):
            self.assertFalse(PMC.check(orig_a4, bad, [])["ok"], bad)
        # 队长：本轮只改数字 + 口径 3 标点，不合并。orig = 本轮数值的第二批写法（「：」），显式规范化后逐行逐字 == 输出；
        # 不规范化则只有不带共鸣的第 6 行算逐字，其余 6 行都被判成「无来源 / 单来源改写」（check 要求未合并行逐字）。
        leader_out = self.out["cas"][M.CAS_LEADER][0][0]
        orig_leader = normalize_resonance_punct(M.UNNORMALIZED_PANEL_LEADER)
        # 第 4 行是已定改字（技能强化文案 R2，同 panels 模块的 pre_edits）：先施加到 orig，再核其余行逐字。
        pre = orig_leader.split("\n")
        self.assertEqual(pre[M.FLAG2_LINE_INDEX], M.OLD_FLAG2_LINE)
        pre[M.FLAG2_LINE_INDEX] = M.NEW_FLAG2_LINE
        self.assertFalse(PMC.check(orig_leader, leader_out, [])["ok"])       # 不施加改字 ⇒ 第 4 行无来源
        orig_leader = "\n".join(pre)
        result = PMC.check(orig_leader, leader_out, [])
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual((result["errors"], result["warnings"]), ([], []))
        self.assertEqual(result["columns"][0]["kinds"], {i: "verbatim" for i in range(1, 8)})
        raw = PMC.check(M.UNNORMALIZED_PANEL_LEADER, leader_out, [])
        self.assertFalse(raw["ok"])
        self.assertEqual([j for j, kind in raw["columns"][0]["kinds"].items() if kind == "verbatim"], [6])

    def test_merge_mutations_are_rejected(self):
        for mutate in (lambda d: d["ability"][M.A4_KEY][1].__setitem__(6, "0"),        # 去掉共鸣前置
                       lambda d: d["ability"][M.A4_KEY][1].__setitem__(1, "false"),    # c1 主位不同
                       lambda d: d["ability"][M.A4_KEY][1].__setitem__(34, "1")):      # 次数上限不同
            data = deepcopy(self.live)
            mutate(data)
            with self.assertRaises(ValueError):
                M.revise(reader(data))
            self.assertTrue(M.ability4_rows_problems(data["ability"][M.A4_KEY]))
        with self.assertRaises(ValueError):
            M.ability4_text([[self.live["cas"][M.CAS_A4][0][0] + "\n多一行"]])


class SkillEnhancementTextTests(unittest.TestCase):
    """作者「技能都强化效果只在队长技或者能力里面按照格式写,技能里面不要重复描述强化后的效果」（主会话口径 R1–R4）。"""

    @classmethod
    def setUpClass(cls):
        cls.live, cls.context = load()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_flag_entries_use_the_official_format(self):
        self.assertEqual(self.live["cas"][M.CAS_FLAG], [["风属性共鸣时强化技能：威力随连击数提升（按直接攻击伤害判定）"]])
        self.assertEqual(self.live["cas"][M.CAS_FLAG2],
                         [["担任队长并达成风属性共鸣时强化技能：把赋予的最大速度固定强化到最高档、不衰减技能槽能量获取"]])
        self.assertEqual(self.out["cas"][M.CAS_FLAG], [["强化『月下独奏』：威力随连击数提升"]])
        self.assertEqual(self.out["cas"][M.CAS_FLAG2],
                         [["强化『月下独奏』：赋予的最大速度固定效果强化至最高档，且不衰减技能槽能量获取"]])
        for key in (M.CAS_FLAG, M.CAS_FLAG2):
            text = self.out["cas"][key][0][0]
            self.assertEqual(M.flag_entry_problems(key, text), [], key)
            self.assertEqual(KL.panel_problems(text, skill_flag=True), [], key)
            for word in ("共鸣", "队长", "强化技能", "按直接攻击伤害判定"):
                self.assertNotIn(word, text)
            self.assertTrue(M.flag_entry_problems(key, self.live["cas"][key][0][0]), key)   # 旧写法不合格
        # 技能名 == live action_skill c0 / character_text c4
        self.assertEqual(self.context["action"][M.CODE][0][1][0], M.SKILL_NAME)
        self.assertEqual(self.context["text"][M.CID][0][4], M.SKILL_NAME)

    def test_skill_description_is_already_body_only(self):
        """R3：技能说明只写本体；「按直接攻击伤害判定」是两支共有的本体效果，已在技能说明里。"""
        descs = [fields[1] for _k, fields in self.context["action"][M.CODE]]
        descs += [self.context[kind][M.CID][0][c] for kind in ("text", "server_text") for c in (5, 7)]
        for text in descs:
            self.assertIn("两段均以直接攻击伤害判定", text)
            for word in ("强化", "共鸣", "队长", "连击数提升", "最高档"):
                self.assertNotIn(word, text)

    def test_panel_lines_carry_the_same_entry_with_the_resonance_prefix(self):
        leader = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual(leader[3], "风属性共鸣时，" + self.out["cas"][M.CAS_FLAG2][0][0])
        a3 = self.out["cas"][M.CAS_A3][0][0].split("\n")
        self.assertEqual(a3, [
            M.MAIN_ICON + "风属性共鸣时，风属性角色的直接攻击强化为3次（同类效果不叠加，取最大值），合计伤害额外乘区＋200%",
            M.MAIN_ICON + "自身处于最大速度固定状态时：自身攻击力＋100%、直击伤害＋100%",
            M.MAIN_ICON + "风属性共鸣时，" + self.out["cas"][M.CAS_FLAG][0][0],
            M.MAIN_ICON + "风属性共鸣时，每达成100连击，立即对最近的敌人发动自身技能的攻击效果（不消耗技能槽，冷却时间：5秒）",
            M.MAIN_ICON + "风属性共鸣时，每达成100连击，连击数＋50",
        ])
        live = self.live["cas"][M.CAS_A3][0][0].split("\n")
        # 第 1/2/4 行只改共鸣标点；第 3 行拆两行，追击行沿用原句（「→」改「，」）。
        self.assertEqual([normalize_resonance_punct(line) for line in (live[0], live[1], live[3])], [a3[0], a3[1], a3[4]])
        self.assertEqual(live[2].split("每达成100连击 → ")[1], a3[3].split("每达成100连击，")[1])
        self.assertEqual(B2.panel_problems({M.CAS_A3: self.out["cas"][M.CAS_A3]}), [])

    def test_basis_rows(self):
        """536（能力3 #3）/ 704（能力6 #4）开关行 c70 = 条目、带风≥6 共鸣（704 另有 42 仅队长）；追击行 = 629 #4。"""
        a3, a6 = self.live["ability"][M.A3_KEY], self.out["ability"][M.A6_KEY]
        self.assertEqual(M.flag_basis_problems(a3, a6), [])
        self.assertEqual((a3[3][47], a3[3][70], a3[3][6], a3[3][11]), ("536", M.CAS_FLAG, "2", "Green"))
        self.assertEqual((a6[4][47], a6[4][70], a6[4][6], a6[4][13], a6[4][18]), ("704", M.CAS_FLAG2, "42", "2", "Green"))
        self.assertEqual((a3[4][47], a3[4][27], a3[4][30], a3[4][35], a3[4][70]),
                         ("629", "12", "10000000", "300", "ability_skill_wolf_moon_encore"))
        self.assertTrue(D.describe_line(a3[3], "ability").startswith("风·编成≥6 时: "))
        for mutate in (lambda a, b: a[3].__setitem__(70, "x"), lambda a, b: a[3].__setitem__(6, "0"),
                       lambda a, b: b[4].__setitem__(6, "0"), lambda a, b: a[4].__setitem__(35, "360")):
            x, y = deepcopy(a3), deepcopy(a6)
            mutate(x, y)
            self.assertTrue(M.flag_basis_problems(x, y))

    def test_reapply_and_drift_are_rejected(self):
        for key in (M.CAS_FLAG, M.CAS_FLAG2):
            with self.assertRaises(ValueError):
                M.flag_text(key, self.out["cas"][key])
        with self.assertRaises(ValueError):
            M.ability3_text(self.out["cas"][M.CAS_A3])
        data = deepcopy(self.live)
        data["ability"][M.A3_KEY][3][70] = "x"
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(data))


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_rolf 重跑 == 本轮输出，不会把第二批值带回来。"""

    @classmethod
    def setUpClass(cls):
        cls.live, cls.context = load()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_constants_mirror_the_module(self):
        self.assertEqual(K.BALANCE_C, {"direct_growth_atk": M.LEADER_GROWTH[3][2],
                                       "direct_growth_direct": M.LEADER_GROWTH[4][2],
                                       "direct_growth_ic693": M.A6_GROWTH[3][2],
                                       "keep_frame_growth": M.A6_GROWTH[5][2]})
        self.assertEqual(M.A6_GROWTH[5][2], M.A6_GROWTH[6][2])
        self.assertEqual(K.BALANCE_B["hold_fixed_speed"], B2.HOLD_FIXED_SPEED)      # 能力3 持有型仍用第二批值
        self.assertEqual((K.LEADER_ROWS, K.ABILITY_RECORDS, len(K.PLAN[6])), (7, 21, 7))
        source = Path(K.__file__).read_text(encoding="utf-8")
        for stale in ('BALANCE_B["direct_growth"]', 'BALANCE_B["direct_growth_ic693"]', 'BALANCE_B["keep_frame_growth"]'):
            self.assertNotIn(stale, source)                                          # 行计划不再引用第二批成长值

    def test_panel_constants_equal_revise_output(self):
        self.assertEqual([[K.CAS_TEXTS[K.CAS_LEADER]]], self.out["cas"][M.CAS_LEADER])
        self.assertEqual(K.PANEL_LEADER, M.NEW_PANEL_LEADER)
        self.assertEqual([[K.CAS_TEXTS[K.CAS_ABILITY[3]]]], self.out["cas"][M.CAS_A3])       # 能力3 拆行
        self.assertEqual(K.PANEL_ABILITY[3], "\n".join(M.NEW_A3_LINES))
        for key in (M.CAS_FLAG, M.CAS_FLAG2):                                                # 两条强化条目
            self.assertEqual([[K.CAS_TEXTS[key]]], self.out["cas"][key], key)
        self.assertEqual((K.CAS_FLAG, K.CAS_FLAG2), (M.CAS_FLAG, M.CAS_FLAG2))
        self.assertEqual([[K.CAS_TEXTS[K.CAS_ABILITY[6]]]], self.context["cas"][f"{B2.CAS_LEADER}_6"])
        self.assertEqual(K.CAS_ABILITY[4], M.CAS_A4)
        self.assertEqual([[K.CAS_TEXTS[K.CAS_ABILITY[4]]]], self.out["cas"][M.CAS_A4])        # 能力4 合并行
        self.assertEqual(K.PANEL_ABILITY[4], "\n".join(M.NEW_A4_LINES))
        for n in (1, 2, 5):                                                                  # 未改面板 == live
            self.assertEqual([[K.CAS_TEXTS[K.CAS_ABILITY[n]]]], self.context["cas"][f"{B2.CAS_LEADER}_{n}"], n)

    def test_expect_gate_matches_the_revised_rows(self):
        leader = self.out["leader"][M.LEADER_KEY]
        for index, row in enumerate(leader):
            self.assertEqual(D.describe_line(row, "leader_ability"), K.EXPECT[f"leader#{index}"], index)
        for key, rows in ((M.A6_KEY, self.out["ability"][M.A6_KEY]), (A3_KEY, self.context["ability"][A3_KEY])):
            for index, row in enumerate(rows):
                self.assertEqual(D.describe_line(row, "ability"), K.EXPECT[f"{key}#{index}"], f"{key}#{index}")

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_rows_equal_revise_output(self):
        built = K.build_rows(_kit_ctx())
        self.assertEqual(built["leader"], self.out["leader"][M.LEADER_KEY])
        self.assertEqual(built["ability"][M.A6_KEY], self.out["ability"][M.A6_KEY])
        self.assertEqual(built["ability"][A3_KEY], self.context["ability"][A3_KEY])


class MirrorTests(unittest.TestCase):
    """设计镜像：已同步，或停在第二批（本轮禁止写 work/，由主会话 ``--write`` 落盘）且按本模块补齐后 == 生成器。"""
    PATHS = (ROOT / M.DESIGN_REL, ROOT / M.PANEL_REL)

    def setUp(self):
        if not all(path.is_file() for path in self.PATHS):
            self.skipTest("midautumn design mirrors missing (work/ is gitignored)")
        self.docs = [json.loads(path.read_text(encoding="utf-8")) for path in self.PATHS]

    def test_mirrors_are_synced_or_pending_this_module(self):
        design, panel = self.docs
        leader_text = "\n".join(line["text"] for line in panel["leader"]["lines"])
        pending = M.sync_mirrors(ROOT, write=False)
        if pending:
            # 过渡态：镜像逐字停在第二批（队长面板 == 第二批 live 文本，第二批块在、第三轮块不在），
            # 或停在口径 3 之前的第三轮（第三轮数字、「风属性共鸣时：」）。两种都按本模块补齐后 == 生成器。
            # 或停在技能强化文案改写前的第三轮（口径 3 已规范、第 4 行仍是旧写法）。
            self.assertIn(leader_text, (M.B_PANEL_LEADER, M.UNNORMALIZED_PANEL_LEADER, M.PRE_FLAG_PANEL_LEADER))
            if leader_text == M.B_PANEL_LEADER:
                self.assertNotIn(M.MIRROR_TAG, design["rework1"])
                self.assertEqual(design["rework1"][B2.MIRROR_TAG]["module"],
                                 "mod-tools/wf_balance_20260927b_rolfmoon.py")
            design, panel = M.mirror_updates(design, panel)
        self.assertEqual(K.design_problems(design), [])
        block = design["rework1"][M.MIRROR_TAG]
        self.assertEqual(block["module"], "mod-tools/wf_balance_20260927c_rolfmoon.py")
        self.assertEqual(block["panel"], {M.CAS_LEADER: K.PANEL_LEADER, M.CAS_A4: K.PANEL_ABILITY[4],
                                          M.CAS_A3: K.PANEL_ABILITY[3], M.CAS_FLAG: K.CAS_TEXTS[M.CAS_FLAG],
                                          M.CAS_FLAG2: K.CAS_TEXTS[M.CAS_FLAG2]})
        self.assertEqual("\n".join(line["text"] for line in panel["leader"]["lines"]), K.PANEL_LEADER)
        four = next(entry for entry in panel["abilities"] if entry["index"] == 4)
        self.assertEqual("\n".join(line["text"] for line in four["lines"]), K.PANEL_ABILITY[4])
        three = next(entry for entry in panel["abilities"] if entry["index"] == 3)
        self.assertEqual("\n".join(K.MAIN_ICON + line["text"] for line in three["lines"]), K.PANEL_ABILITY[3])
        self.assertEqual(panel["notes"][-1], M.MIRROR_NOTE)
        self.assertIn(B2.MIRROR_NOTE, panel["notes"])                     # 第二批记录保留

    def test_mirror_update_is_idempotent_and_pure(self):
        before = deepcopy(self.docs)
        once = M.mirror_updates(*self.docs)
        self.assertEqual(self.docs, before)
        self.assertEqual(M.mirror_updates(*once), once)
        design, panel = once
        self.assertEqual(design["rework1"][B2.MIRROR_TAG], before[0]["rework1"][B2.MIRROR_TAG])   # 第二批块逐字保留
        changed = [line for line in panel["leader"]["lines"] if line["text"] in (M.NEW_LEADER_LINE, M.NEW_KEEP_FRAME_LINE)]
        self.assertEqual(len(changed), 2)
        for line in changed:
            self.assertIn("2026-09-27 平衡第三轮", line["note"])
        four = next(entry for entry in panel["abilities"] if entry["index"] == 4)
        self.assertEqual([line["text"] for line in four["lines"]], list(M.NEW_A4_LINES))
        self.assertIn("平衡第三轮面板合并", four["lines"][0]["note"])


@unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                     and (ROOT / "mod-tools/profiles.json").is_file(),
                     "local candidate workspace required")
class CandidateTests(unittest.TestCase):
    def test_candidate_splices_only_the_reviewed_keys_dry(self):
        import wf_share_update_codec as X
        from wf_character_revision import RevisionCandidate
        live, _context = load()
        out = M.revise(reader(deepcopy(live)))
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        current = version(json.loads(before)["package_version"])
        mine = M.PACKAGE_VERSION[M.PACKAGES[0]]
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                      snapshot_key="revision_20260927c_growth", package_version=mine,
                                      reviewed_input_drift=M.REVIEWED_DRIFT,
                                      baseline_factory=lambda *a, **k: None)
        old = {kind: X.unpack(candidate.read("common", table)) for kind, table in TABLES.items()}
        cand = {(kind, key): X.csv_read(old[kind][key]) for kind, key in M.BEFORE}
        staged = cand["leader", M.LEADER_KEY] == out["leader"][M.LEADER_KEY]
        for kind, key in M.BEFORE:
            # 已回写 = 本轮输出（只读键 = live）；暂存前 = live 输入
            want = out[kind].get(key, live[kind][key]) if staged else live[kind][key]
            self.assertEqual(cand[kind, key], want, (kind, key, staged))
        if staged:
            self.assertGreaterEqual(current, version(mine))
        else:
            self.assertGreater(version(mine), current)
        for kind, table in TABLES.items():
            candidate.splice(table, out[kind])
        for kind, table in TABLES.items():
            new = X.unpack(candidate.read("common", table))
            for key in out[kind]:
                self.assertEqual(X.csv_read(new[key]), out[kind][key], (kind, key))
            self.assertEqual({k: v for k, v in old[kind].items() if k not in out[kind]},
                             {k: v for k, v in new.items() if k not in out[kind]}, kind)
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertEqual(sorted(f["logical_path"] for f in evidence["changed_files"]), sorted(TABLES.values()))
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
