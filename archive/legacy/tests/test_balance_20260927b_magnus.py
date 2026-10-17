# -*- coding: utf-8 -*-
"""玛格诺斯「疾风同路」119990 ``lion_swordman_moon`` 2026-09-27 平衡第二批
（口径 A：无上限成长；口径 B3/B6：「引擎之炎」629 追击每次削韧 ≤1）。

fixture = live 输入快照（``fixtures/balance_20260927b_magnus.json``），驱动 ``revise()``：
每处改动的前后值、未改行/未改树节点逐字保留、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、
合法性门禁为空、DSL AMF3 往返与四道 DSL 门禁、面板规则、生成器输出 == revise() 输出、设计镜像已同步、
候选无漂移且版本只升不降。
生成器装配对比需要 ``.cdn/cn`` 官方基线与 live store（缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_magnus as M  # noqa: E402
import wf_balance_20260927c_magnus as MC  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kit_magnus as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_magnus.json"
UID = M.UID
CODE = M.CODE


def load_fixture() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


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


#: 第三轮（wf_balance_20260927c_magnus）接管的键：队长成长 6 行强度、能力 1 末尾旗号 2 行、队长 / 槽 1 / 槽 2 面板
#: （槽 2 = 面板合并轮删共鸣前缀）、6 棵 DSL。这些键的「生成器 == 修订输出」「候选 == 修订输出」由 test_balance_20260927c_magnus 断言。
C_TAKEN_CAS = {MC.CAS_LEADER, MC.CAS_SLOT1, MC.CAS_SLOT2}
C_TAKEN_LEADER_CELLS = {index: set(cols) for index, (cols, *_rest) in MC.LEADER_GROWTH.items()}


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


#: 队长新增 4 行的完整非空格（= [CODE,'0',''] + 能力行[5:]，能力 c≥5 → 队长 c−2，只改强度两列）。
_FIRE_L = {4: "2", 7: "600000", 8: "600000", 9: "Red"}
NEW_LEADER_ROWS = (
    {0: CODE, 1: "0", 3: "0", **_FIRE_L, 11: "0", 18: "0", 25: "2", 28: "300000", 29: "300000",
     32: "(None)", 33: "0", 37: "(None)", 44: "0", 45: "34", 46: "0", 49: "5000", 50: "5000"},
    {0: CODE, 1: "0", 3: "1", **_FIRE_L, 11: "0", 18: "0", 83: "(None)", 95: "134", 96: "0",
     98: "100000", 99: "100000", 100: "(None)", 102: UID, 106: "false", 107: "2", 108: "0",
     111: "5000", 112: "5000"},
    {0: CODE, 1: "0", 3: "1", **_FIRE_L, 11: "0", 18: "0", 83: "(None)", 95: "134", 96: "0",
     98: "100000", 99: "100000", 100: "(None)", 102: UID, 106: "false", 107: "0", 108: "0",
     111: "5000", 112: "5000"},
    {0: CODE, 1: "0", 3: "1", 4: "0", 11: "0", 18: "0", 83: "(None)", 95: "134", 96: "0",
     98: "100000", 99: "100000", 100: "(None)", 102: UID, 106: "false", 107: "411", 108: "5",
     109: "Red", 111: "500", 112: "500"},
)
NEW_LEADER_DESCRIBE = (
    "火·编成≥6 时: 强化弹射≥3 → 自身 技能伤害 5%",
    f"火·编成≥6 时: 持续·状态累积计数固有≥1[固有{UID}] → 自身 技能伤害 5%",
    f"火·编成≥6 时: 持续·状态累积计数固有≥1[固有{UID}] → 自身 攻击力 5%",
    f"持续·状态累积计数固有≥1[固有{UID}] → 赋予全队(火) 独立乘区技能伤害 0.5%",
)
#: 追击树唯一 CreateNormalAttack 的 p13 路径（根块第 3 条外层判定区 → 命中块参考点 → 爆炸判定区 → CNA）。
CHASE_P13_PATH = (11, 1, 2, 1, 23, 1, 1, 1, 11, 1, 1, 1, 23, 1, 0, 1, 13, 0)
NEW_LEADER_PANEL = (
    "火属性共鸣时，自身的强化弹射变为特殊强化弹射，造成的伤害按技能伤害结算\n"
    "火属性共鸣时，自身获得冲刺强化效果，冲刺冷却时间－30%\n"
    "火属性共鸣时，冲刺间隔缩短效果不会让自身的冲刺冷却时间进一步缩短\n"
    "火属性共鸣时，每发动3次强化弹射，火属性角色技能伤害＋20%、攻击力＋10%\n"
    "火属性共鸣时，每发动3次强化弹射，自身技能伤害＋5%\n"
    "火属性共鸣时，每发动3次强化弹射，火属性角色技能槽＋5%\n"
    "火属性共鸣时，每发动3次强化弹射，自身引擎点火＋7层\n"
    "火属性共鸣时，引擎点火每提升1层，自身技能伤害＋5%、攻击力＋5%\n"
    "自身引擎点火每提升1层，火属性角色技能伤害额外乘区＋0.5%\n"
    "自身持有「烈焰光环」期间，每次弹射，连击＋35"
)


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    # ---------------------------------------------------------------- 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         set(M.BEFORE))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (str(K.CID), K.CODE))
        self.assertEqual(M.PACKAGES, ["ma-magnus"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-magnus": "1.0.2"})   # 候选现值 1.0.1，只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertFalse(hasattr(M, "UNITS"))

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["leader"]), {M.CID})
        self.assertEqual(set(out["ability"]), {M.A1, M.A2, M.A3})
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER, *M.CAS_SLOT.values()})
        self.assertEqual(set(out["dsl"]), set(M.PROGRAMS))
        for kind in ("text", "table", "action", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)
        for key in out["cas"]:
            self.assertTrue(key.startswith("desc_override_" + CODE), key)
        for program in out["dsl"]:
            self.assertIn(CODE, program)

    # ---------------------------------------------------------------- 队长

    def test_leader_slows_the_two_pf3_team_rows_by_one_fifth(self):
        old, new = self.live["leader"][M.CID], self.out["leader"][M.CID]
        self.assertEqual((len(old), len(new)), (9, 13))
        self.assertEqual(changed_cells(old[1], new[1]),
                         {49: ("100000", "20000"), 50: ("100000", "20000")})
        self.assertEqual(changed_cells(old[2], new[2]),
                         {49: ("50000", "10000"), 50: ("50000", "10000")})
        self.assertEqual((new[1][45], new[1][46], new[1][32], new[1][33]), ("34", "5", "(None)", "0"))
        self.assertEqual((new[2][45], new[2][46], new[2][32], new[2][33]), ("32", "5", "(None)", "0"))

    def test_leader_keeps_the_other_nine_rows_verbatim(self):
        old, new = self.live["leader"][M.CID], self.out["leader"][M.CID]
        for index in (0, 3, 4, 5, 6, 7, 8):
            self.assertEqual(new[index], old[index], f"leader#{index}")
        # 充能行（队长 #3 全队技能槽 5%）按口径 A6 不动；#4 +7 层点火、#5 光环连击、#6–#8 629 不动
        self.assertEqual((new[3][45], new[3][49]), ("211", "5000"))
        self.assertEqual((new[4][45], new[4][49]), ("461", "700000"))

    def test_leader_appends_the_four_moved_rows_cell_by_cell(self):
        new = self.out["leader"][M.CID]
        for offset, (cells, text) in enumerate(zip(NEW_LEADER_ROWS, NEW_LEADER_DESCRIBE)):
            row = new[9 + offset]
            self.assertEqual(len(row), 124)
            self.assertEqual(nonempty(row), cells, f"leader#{9 + offset}")
            self.assertEqual(wf_describe.describe_rows([row], "leader_ability")[0], text)

    def test_moved_rows_are_the_transposed_ability_rows(self):
        """行 = [CODE,'0',''] + 能力行[5:]；除强度两列外逐字等于改前能力行。"""
        a1, a2, a3 = (self.live["ability"][key] for key in (M.A1, M.A2, M.A3))
        new = self.out["leader"][M.CID]
        pairs = ((a1[2], new[9], (49, 50)), (a2[0], new[10], (111, 112)),
                 (a2[1], new[11], (111, 112)), (a3[4], new[12], (111, 112)))
        for ability_row, leader_row, strength in pairs:
            expect = [CODE, "0", ""] + ability_row[5:]
            self.assertEqual(set(changed_cells(expect, leader_row)), set(strength))
        # 放缓倍率：每 3PF ×1/5；点火逐层 ×1/10
        self.assertEqual(int(new[9][49]) * 5, int(a1[2][51]))
        self.assertEqual(int(new[10][111]) * 10, int(a2[0][113]))
        self.assertEqual(int(new[11][111]) * 10, int(a2[1][113]))
        self.assertEqual(int(new[12][111]) * 10, int(a3[4][113]))

    def test_c06_self_row_is_not_merged_into_the_team_row(self):
        new = self.out["leader"][M.CID]
        pf3_skill = [r for r in new if r[3] == "0" and r[25] == "2" and r[45] == "34"]
        self.assertEqual([(r[46], r[49]) for r in pf3_skill], [("5", "20000"), ("0", "5000")])

    def test_leader_moved_rows_stay_unlimited_and_have_no_cooldown(self):
        new = self.out["leader"][M.CID]
        self.assertEqual((new[9][32], new[9][33]), ("(None)", "0"))
        for row in new[10:]:
            self.assertEqual((row[95], row[100], row[102]), ("134", "(None)", UID))
        self.assertEqual(new[12][4], "0", "原能力 3#4 无前置 ⇒ 转置后仍无前置")

    def test_leader_kinds_avoid_the_c7050_list(self):
        for row in self.out["leader"][M.CID]:
            self.assertNotIn(row[45], K.LEADER_FORBIDDEN_KINDS)
            self.assertNotIn(row[107], K.LEADER_FORBIDDEN_KINDS)

    # ---------------------------------------------------------------- 能力

    def test_ability1_limits_the_pf3_self_row_to_four(self):
        old, new = self.live["ability"][M.A1], self.out["ability"][M.A1]
        self.assertEqual(new[:2], old[:2])
        self.assertEqual(changed_cells(old[2], new[2]), {34: ("(None)", "4")})
        self.assertEqual(wf_describe.describe_rows([new[2]], "ability")[0],
                         "火·编成≥6 时: 强化弹射≥3(限4次) → 自身 技能伤害 25%")

    def test_ability2_caps_both_layer_rows_at_ten(self):
        old, new = self.live["ability"][M.A2], self.out["ability"][M.A2]
        for index, kind in ((0, "技能伤害"), (1, "攻击力")):
            self.assertEqual(changed_cells(old[index], new[index]),
                             {102: ("(None)", "10"), 113: ("50000", "15000"), 114: ("50000", "15000")})
            self.assertEqual(wf_describe.describe_rows([new[index]], "ability")[0],
                             f"火·编成≥6 时: 持续·状态累积计数固有≥1(限10次)[固有{UID}] → 自身 {kind} 15%")
        self.assertEqual({r[1] for r in new}, {"true"}, "能力 2 仍可副位")

    def test_ability3_caps_only_the_team_411_row(self):
        old, new = self.live["ability"][M.A3], self.out["ability"][M.A3]
        for index in (0, 1, 2, 3, 5):
            self.assertEqual(new[index], old[index], f"{M.A3}#{index}")
        self.assertEqual(changed_cells(old[4], new[4]),
                         {102: ("(None)", "10"), 113: ("5000", "1000"), 114: ("5000", "1000")})
        self.assertEqual(wf_describe.describe_rows([new[4]], "ability")[0],
                         f"持续·状态累积计数固有≥1(限10次)[固有{UID}] → 赋予全队(火) 独立乘区技能伤害 1%")
        self.assertEqual({r[1] for r in new}, {"false"}, "能力 3 整键主位限定保持")
        K._order_problems(new)                                   # 629 仍在 525 之前

    def test_every_moved_growth_now_has_a_limit_on_the_ability_side(self):
        """口径 A1：能力栏不再留无上限的成长行（限次/层上限为空或 (None) 的永久成长）。"""
        out = self.out["ability"]
        self.assertEqual(out[M.A1][2][34], "4")
        self.assertEqual([r[102] for r in out[M.A2]], ["10", "10"])
        self.assertEqual(out[M.A3][4][102], "10")
        self.assertEqual(out[M.A3][3][102], "1", "≥5 层平坦门槛本来就限 1 次，不动")

    # ---------------------------------------------------------------- 面板

    def test_leader_panel_text(self):
        old = self.live["cas"][M.CAS_LEADER][0][0].split("\n")
        new = self.out["cas"][M.CAS_LEADER][0][0]
        self.assertEqual(new, NEW_LEADER_PANEL)
        lines = new.split("\n")
        self.assertEqual(lines[:3], old[:3])
        self.assertEqual(lines[5:7], old[4:6])
        self.assertEqual(lines[-1], old[-1])

    def test_slot_panel_texts(self):
        self.assertEqual(self.out["cas"][M.CAS_SLOT[1]], [[
            "战斗开始时，自身技能槽＋50%\n"
            "火属性共鸣时，强化自身技能：光环范围扩大\n"
            "火属性共鸣时，每发动3次强化弹射，自身技能伤害＋25%（最多4次）\n"
            "自身引擎点火每提升1层，技能基础总倍率＋5倍（含引擎之炎及特殊强化弹射，最多10层）"]])
        self.assertEqual(self.out["cas"][M.CAS_SLOT[2]], [[
            "火属性共鸣时，引擎点火每提升1层，自身技能伤害＋15%、攻击力＋15%（最多10层）"]])
        old = self.live["cas"][M.CAS_SLOT[3]][0][0].split("\n")
        new = self.out["cas"][M.CAS_SLOT[3]][0][0].split("\n")
        self.assertEqual(new[:4] + new[5:], old[:4] + old[5:])
        self.assertEqual(new[4], M.MAIN_ICON + "自身引擎点火每提升1层，火属性角色技能伤害额外乘区＋1%（最多10层）")

    def test_panel_texts_obey_the_batch_rules(self):
        texts = {key: rows[0][0] for key, rows in self.out["cas"].items()}
        self.assertEqual(M.panel_problems(texts), [])
        for key, text in texts.items():
            self.assertNotIn("／", text)
            for word in ("无上限", "无限叠加", "不设上限", "可无限", "自身为队长时", "觉醒后", "生命值100%以下"):
                self.assertNotIn(word, text, key)
            for line in text.split("\n"):
                self.assertEqual(line.startswith(M.MAIN_ICON), key == M.CAS_SLOT[3], f"{key}: {line}")
        skill_flag = texts[M.CAS_SLOT[1]].split("\n")[1]
        self.assertEqual(KL.panel_problems(skill_flag, skill_flag=True), [], "536 条目不写数字与时间")

    def test_panel_problems_catch_violations(self):
        bad = {M.CAS_SLOT[2]: "引擎点火每提升1层，自身技能伤害＋15%（可无限累积）",
               M.CAS_SLOT[3]: "自身引擎点火每提升1层",
               M.CAS_SLOT[1]: "战斗开始时\n火属性共鸣时，强化自身技能：光环范围扩大10%"}
        problems = M.panel_problems(bad)
        self.assertTrue(any("可无限" in p for p in problems))
        self.assertTrue(any("main icon" in p for p in problems))
        self.assertTrue(any("numbers" in p for p in problems))

    # ---------------------------------------------------------------- 合法性

    def test_native_legality_gates_are_empty(self):
        cas_keys = set(K.CAS_TEXTS)
        for kind, table in (("leader", "leader_ability"), ("ability", "ability")):
            for key, rows in self.out[kind].items():
                for index, row in enumerate(rows):
                    label = f"{kind}:{key}#{index}"
                    self.assertEqual(L.client_legality_problems(table, row), [], label)
                    self.assertEqual(L.declared_block_field_problems(table, row), [], label)
                    self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, kind=table), [], label)
                    self.assertEqual(KL.row_problems(table, row, M.ELEMENT), {}, label)
                    self.assertEqual(L.required_client_capabilities(table, row), [], label)
                    self.assertEqual(M.row_gate_problems(kind, row, cas_keys), [], label)

    # ---------------------------------------------------------------- DSL

    def test_dsl_changes_only_the_binding_cap_and_the_chase_down(self):
        for program in M.PROGRAMS:
            old, new = self.live["dsl"][program], self.out["dsl"][program]
            expect = [((11, 1, 0, 1, 5), 99, 10)]
            if program == M.CHASE_PROGRAM:
                expect += [(CHASE_P13_PATH + (end,), 0.25, 0.2) for end in ("min", "max")]
            self.assertEqual(tree_diff(old, new), expect, program)
            self.assertEqual(new[11][1][0], ["Command", ["BindConditionAccumulationVariable", -17,
                                                         M.IGNITION_VARIABLE, ["DCUnique", int(UID)], 1, 10]])
            self.assertIsInstance(new[11][1][0][1][5], int, "保持 AMF3 int 形状（原值 99 也是 int）")
            self.assertEqual(new[10], 0, "buffTargetAs 0 = 技能伤害归属不变")

    def test_dsl_roundtrip_and_four_gates(self):
        for program, tree in self.out["dsl"].items():
            self.assertEqual(M.dsl_gate_problems(tree), [], program)
            self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [], program)
            self.assertEqual(L.action_dsl_subject_binding_problems(tree), [], program)
            self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [], program)
            self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [], program)
            raw = wf_dsl.encode_amf3(tree)
            self.assertEqual(wf_dsl.parse_dsl(raw)["tree"], tree, program)
            self.assertEqual(wf_dsl.encode_amf3(wf_dsl.parse_dsl(raw)["tree"]), raw, program)

    # ---------------------------------------------------------------- Down（口径 B3/B6）

    def test_chase_trigger_ct_puts_it_under_the_one_per_activation_cap(self):
        """口径 B3：629 触发 CT ≤3 秒（180 帧）的每次 ≤1。能力 3#1 = 触发 136、CT 36 帧（0.6 秒），行不改。"""
        old, new = self.live["ability"][M.A3][1], self.out["ability"][M.A3][1]
        self.assertEqual(new, old)
        self.assertEqual((new[47], new[27], new[35], new[71]), ("629", "136", "36", M.CHASE_PROGRAM))
        self.assertLessEqual(int(new[35]), 3 * 60)

    def test_chase_down_per_activation_drops_from_1_25_to_1(self):
        old, new = self.live["dsl"][M.CHASE_PROGRAM], self.out["dsl"][M.CHASE_PROGRAM]
        self.assertEqual(M.chase_down_per_activation(old), 1.25)
        self.assertEqual(M.chase_down_per_activation(new), 1.0)
        self.assertLessEqual(M.chase_down_per_activation(new), M.CHASE_DOWN_CAP)
        outer, burst, cna = M.chase_burst(new)
        self.assertEqual(cna[13], [{"min": 0.2, "max": 0.2}], "SLv min/max 都改")
        self.assertEqual(cna[14], [{"min": 0.25, "max": 0.25}], "p14 Fever 点不动")
        self.assertEqual(cna[6][0]["max"], 3.0, "倍率不动")
        self.assertEqual((outer[14], outer[15]),
                         (["CalculatedUsingMaxNumOfHits", 1], ["Some", [{"min": 1, "max": 1}]]))
        self.assertEqual((burst[13], burst[14], burst[15]),
                         (["SpecifyHitAreaLifetimeDirectly", 30], ["CalculatedUsingMaxNumOfHits", 5], ["None"]))
        # 母本（官方火龙）每次 = 4 × 0.25 = 1.0 ⇒ 改后与母本每次总量相同
        self.assertEqual(M.CHASE_HITS[1] * M.CHASE_DOWN[1], 4 * M.CHASE_DOWN[0])

    def test_other_trees_keep_their_down_values(self):
        """主技能 ≤30（口径 B1 名单外）；疾风同路 PF 15/20/25 顶格（口径 B5 保留）。"""
        def p13(tree):
            return [a[13] for a in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")]

        for program in M.PROGRAMS:
            if program != M.CHASE_PROGRAM:
                self.assertEqual(p13(self.out["dsl"][program]), p13(self.live["dsl"][program]), program)
        hits = {M.PROGRAMS[0]: [1, 10], M.PROGRAMS[1]: [1, 10],
                M.PROGRAMS[3]: [2, 1], M.PROGRAMS[4]: [3, 1], M.PROGRAMS[5]: [3, 1]}
        totals = {program: sum(v[0]["max"] * n for v, n in zip(p13(self.out["dsl"][program]), counts))
                  for program, counts in hits.items()}
        self.assertLessEqual(totals[M.PROGRAMS[0]], 30)
        self.assertLessEqual(totals[M.PROGRAMS[1]], 30)
        self.assertEqual([totals[M.PROGRAMS[n]] for n in (3, 4, 5)], [15, 20, 25])

    def test_chase_down_drift_is_rejected(self):
        base = self.live["dsl"][M.CHASE_PROGRAM]
        tree = deepcopy(base)
        M.chase_burst(tree)[2][13] = [{"min": 0.3, "max": 0.3}]        # p13 前像漂移
        with self.assertRaisesRegex(ValueError, "p13 preimage drift"):
            M.revise_tree(tree, M.CHASE_PROGRAM)
        tree = deepcopy(base)
        M.chase_burst(tree)[1][14] = ["CalculatedUsingMaxNumOfHits", 6]  # 段数漂移 ⇒ 削韧账要重算
        with self.assertRaisesRegex(ValueError, "hit accounting drift"):
            M.revise_tree(tree, M.CHASE_PROGRAM)
        tree = deepcopy(base)
        M.chase_burst(tree)[0][15] = ["None"]                             # 外层不再限 1 次
        with self.assertRaisesRegex(ValueError, "ball hit area drift"):
            M.revise_tree(tree, M.CHASE_PROGRAM)
        a3 = deepcopy(self.live["ability"][M.A3])
        a3[1][35] = "300"                                                 # CT 漂移 ⇒ B3 判定要重核
        with self.assertRaisesRegex(ValueError, "trigger/CT/program drifted"):
            M.ability3_rows(a3)

    def test_layer_contribution_is_capped_at_ten(self):
        """每整招 +5 倍/层（按段数分摊），变量 = min(层数/1, 10) ⇒ 10 层后不再增长。"""
        hits = {M.PROGRAMS[0]: [1, 10], M.PROGRAMS[1]: [1, 10], M.PROGRAMS[2]: [5],
                M.PROGRAMS[3]: [2, 1], M.PROGRAMS[4]: [3, 1], M.PROGRAMS[5]: [3, 1]}
        for program, tree in self.out["dsl"].items():
            bind = tree[11][1][0][1]
            attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
            per_layer = sum(a[6][0]["vlv"][0]["max"] * n for a, n in zip(attacks, hits[program]))
            self.assertAlmostEqual(per_layer, 5.0, places=6, msg=program)
            for layers in (0, 1, 5, 10, 11, 35, 99):
                variable = min(layers / bind[4], bind[5])
                self.assertAlmostEqual(per_layer * variable, 5.0 * min(layers, 10), places=6)

    # ---------------------------------------------------------------- fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["leader"][M.CID][0][0] = "mutated"
        out["ability"][M.A2][0][0] = "mutated"
        out["dsl"][M.PROGRAMS[0]][11][1][0][1][5] = 1
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.live)
            if kind == "cas":
                data[kind][key][0][0] += "。"
            elif kind == "dsl":
                data[kind][key][11][1][0][1][5] = 98
            else:
                data[kind][key][-1][1] = "drift"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))
            data = deepcopy(self.live)
            data[kind][key] = data[kind][key][:-1]
            with self.assertRaises(ValueError):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        for kind in ("leader", "ability", "cas", "dsl"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        a1, a2, a3 = (self.out["ability"][k] for k in (M.A1, M.A2, M.A3))
        live_a = [self.live["ability"][k] for k in (M.A1, M.A2, M.A3)]
        with self.assertRaises(ValueError):
            M.leader_rows(self.out["leader"][M.CID], *live_a)
        with self.assertRaises(ValueError):
            M.moved_leader_rows(a1, a2, a3)
        for func, rows in ((M.ability1_rows, a1), (M.ability2_rows, a2), (M.ability3_rows, a3)):
            with self.assertRaises(ValueError):
                func(rows)
        for func, key in ((M.leader_text, M.CAS_LEADER), (M.slot1_text, M.CAS_SLOT[1]),
                          (M.slot2_text, M.CAS_SLOT[2]), (M.slot3_text, M.CAS_SLOT[3])):
            with self.assertRaises(ValueError):
                func(self.out["cas"][key])
        for program in M.PROGRAMS:
            with self.assertRaises(ValueError):
                M.revise_tree(self.out["dsl"][program], program)

    def test_row_locators_are_content_based(self):
        leader = deepcopy(self.live["leader"][M.CID])
        live_a = [self.live["ability"][k] for k in (M.A1, M.A2, M.A3)]
        with self.assertRaises(ValueError):                    # 目标行挪位
            M.leader_rows([leader[0], leader[2], leader[1], *leader[3:]], *live_a)
        changed = deepcopy(leader)
        changed[1][32] = "10"                                   # 限次漂移
        with self.assertRaises(ValueError):
            M.leader_rows(changed, *live_a)
        a2 = deepcopy(self.live["ability"][M.A2])
        a2[1][104] = "11999002"                                 # 固有 id 漂移
        with self.assertRaises(ValueError):
            M.ability2_rows(a2)
        a3 = deepcopy(self.live["ability"][M.A3])
        a3[1], a3[2] = a3[2], a3[1]                             # 629/525 顺序被打乱
        with self.assertRaises(ValueError):
            M.ability3_rows(a3)
        tree = deepcopy(self.live["dsl"][M.PROGRAMS[0]])
        tree[11][1].insert(1, deepcopy(tree[11][1][0]))         # 第二条绑定
        with self.assertRaises(ValueError):
            M.revise_tree(tree, M.PROGRAMS[0])

    def test_self_check_rejects_extra_touch(self):
        with self.assertRaises(AssertionError):
            M._only_changed([["a", "b"]], [["x", "y"]], 0, (1,))


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_magnus 重跑必须产出与 revise() 相同的行/面板/DSL。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_panel_constants_equal_revise_output(self):
        # 第三轮（wf_balance_20260927c_magnus）改了队长 / 槽 1 面板：这两键的一致性移交 c 测试。
        for key, rows in self.out["cas"].items():
            if key in C_TAKEN_CAS:
                continue
            self.assertEqual([[K.CAS_TEXTS[key]]], rows, key)

    def test_plan_constants_carry_the_batch2_values(self):
        self.assertEqual(len(K.LEADER), 13)
        # 第三轮（wf_balance_20260927c_magnus）回调了队长 #1/#2/#9–#12 的强度：生成器现值 = 第三轮值
        # （与 revise() 一致由 c 测试断言）；行形状、donor、描述结构仍是第二批的，只差末尾百分数。
        self.assertEqual([(K.LEADER[i][2][49], K.LEADER[i][2][50]) for i in (1, 2)],
                         [(MC.LEADER_GROWTH[i][3],) * 2 for i in (1, 2)])
        self.assertEqual([item[0] for item in K.LEADER[9:]],
                         ["111183#1", "161063#3", "161063#2", "161123#0"])
        self.assertEqual([item[3].rsplit(" ", 1)[0] for item in K.LEADER[9:]],
                         [text.rsplit(" ", 1)[0] for text in NEW_LEADER_DESCRIBE])
        self.assertEqual(K.PLAN[1][2][2][34], "4")
        self.assertEqual([(c[102], c[113]) for _d, _s, c, _e in K.PLAN[2]], [("10", "15000")] * 2)
        self.assertEqual((K.PLAN[3][4][2][102], K.PLAN[3][4][2][113]), ("10", "1000"))
        self.assertEqual(K.IGNITION_DSL_CAP, 10)

    def test_chase_down_constants_match(self):
        self.assertEqual((K.CHASE_DOWN_DONOR, K.CHASE_DOWN), M.CHASE_DOWN)
        self.assertEqual(K.BURST_MAX_HITS, M.CHASE_HITS[1])
        self.assertEqual(K.CHASE_DOWN_CAP, M.CHASE_DOWN_CAP)
        chase_row = K.PLAN[3][1][2]
        self.assertEqual((chase_row[27], chase_row[35], chase_row[71]),
                         (*M.CHASE_TRIGGER_CT, M.CHASE_PROGRAM))

    def test_ignition_growth_wrapper_rejects_a_drifted_binding(self):
        tree = deepcopy(self.live["dsl"][M.PROGRAMS[2]])
        tree[11][1].pop(0)
        for attack in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"):
            del attack[6][0]["vlv"]
            attack[13] = [{"min": K.CHASE_DOWN, "max": K.CHASE_DOWN}]   # 第二批 B3：kit 在建树时已改 p13
        rebuilt, meta = K.ignition_growth(tree, (K.BURST_MAX_HITS,))
        self.assertEqual(rebuilt, self.out["dsl"][M.PROGRAMS[2]])
        self.assertEqual(meta["max_layers"], 10)
        with self.assertRaises(ValueError):                     # 重复套用 = 已有绑定
            K.ignition_growth(rebuilt, (K.BURST_MAX_HITS,))

    @unittest.skipUnless(_LIVE, "需要 .cdn/cn 官方基线与 live store")
    def test_generator_rows_equal_revise_output(self):
        from test_midautumn_kit_magnus import _ReadOnlyCtx
        built = K.build_rows(_ReadOnlyCtx())
        # 第三轮（wf_balance_20260927c_magnus）只改了队长成长 6 行的强度两列、在能力 1 末尾追加旗号 2 行：
        # 这些格移交 c 测试，其余格仍 == 第二批输出。
        self.assertEqual(len(built["leader"]), len(self.out["leader"][M.CID]))
        for index, (got, want) in enumerate(zip(built["leader"], self.out["leader"][M.CID])):
            taken = C_TAKEN_LEADER_CELLS.get(index, set())
            self.assertEqual([v for c, v in enumerate(got) if c not in taken],
                             [v for c, v in enumerate(want) if c not in taken], f"leader#{index}")
        for key, rows in self.out["ability"].items():
            self.assertEqual(built["ability"][key][:len(rows)], rows, key)
            self.assertEqual(len(built["ability"][key]), len(rows) + (key == MC.A1), key)
        for key in (f"{M.CID}4", f"{M.CID}5", f"{M.CID}6"):
            self.assertNotIn(key, self.out["ability"])
        self.assertEqual(sorted(built["capabilities"]), ["dash-parameter-v1"])

    @unittest.skipUnless(_LIVE, "需要 .cdn/cn 官方基线与 live store")
    def test_generator_trees_equal_revise_output(self):
        # 第三轮（wf_balance_20260927c_magnus）后这些是封顶 10 层的中间树（= 旗号 2 关支）；最终落盘树
        # （K.build_skill_trees：技能/追击包进旗号 2 分支、特殊 PF 三档上限 99）== c 输出由 c 测试断言。
        from test_midautumn_kit_magnus import _ReadOnlyCtx, _stub_families
        ctx, families = _ReadOnlyCtx(), _stub_families()
        built = {M.PROGRAMS[int(level) - 1]: K.build_main_tree(ctx, level, families)[0]
                 for level in ("1", "2")}
        built[M.PROGRAMS[2]] = K.build_chase_tree(ctx, families)[0]
        for level in (1, 2, 3):
            tree, _meta = K.build_pf_tree(ctx, level, families)
            _shell, skill, meta = K.PF_SKILL.split_tree(tree)
            built[M.PROGRAMS[2 + level]] = K.ignition_growth(skill, tuple(meta["hits"]))[0]
        for program in M.PROGRAMS:
            self.assertEqual(built[program], self.out["dsl"][program], program)

    @unittest.skipUnless(_LIVE, "需要 .cdn/cn 官方基线与 live store")
    def test_moved_row_kinds_have_leader_table_precedents(self):
        """队长新行：134→2/0 target 0 有官方先例；134→411 有 live 自制先例（口径 A4 放行名单：特克托）。"""
        from test_midautumn_kit_magnus import _ReadOnlyCtx
        ctx = _ReadOnlyCtx()
        seen = {"official": set(), "live": set()}
        for label, flat in (("official", ctx.official_flat(KL.LEADER)), ("live", ctx.live_flat(KL.LEADER))):
            for key, value in flat.items():
                if key == M.CID:
                    continue
                for row in core.read_csv_lines(value):
                    cell = (lambda i: row[i] if i < len(row) else "")
                    if cell(3) == "1":
                        seen[label].add(("during", cell(95), cell(107), cell(108)))
                        seen[label].add(("during_kind", cell(107)))
                    elif cell(3) == "0":
                        seen[label].add(("instant", cell(25), cell(45)))
                        seen[label].add(("instant_kind_target", cell(45), cell(46)))
        self.assertIn(("during", "134", "2", "0"), seen["official"])
        self.assertIn(("during", "134", "0", "0"), seen["official"])
        self.assertIn(("during", "134", "0", "5"), seen["official"])
        self.assertIn(("during_kind", "411"), seen["live"])
        self.assertIn(("instant", "2", "34"), seen["official"])
        self.assertIn(("instant_kind_target", "34", "0"), seen["official"])


WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]


class CandidateTests(unittest.TestCase):
    """候选 ma-magnus：无漂移（REVIEWED_DRIFT = {}）、版本只升不降；只读，不写包。"""

    @unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                         and (ROOT / "mod-tools/profiles.json").is_file(),
                         "local candidate workspace required")
    def test_candidate_has_no_file_drift_and_version_moves_forward(self):
        import zlib
        from wf_character_revision import RevisionCandidate
        import wf_share_update_codec as X
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        current = json.loads(before)
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                      package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                                      snapshot_key="revision_20260927b",
                                      reviewed_input_drift=M.REVIEWED_DRIFT,
                                      baseline_factory=lambda *a, **k: None)
        live = load_fixture()
        out = M.revise(reader(deepcopy(live)))
        # 主会话暂存回写后：候选 = live + 本批；回写前：候选 = live（本模块读取的 14 项逐字相同）。
        written_back = current.get("snapshot", {}).get("revision_20260927b") is not None
        want = out if written_back else {"leader": live["leader"], "ability": live["ability"],
                                          "cas": live["cas"], "dsl": live["dsl"]}
        version = tuple(int(x) for x in current["package_version"].split("."))
        target = tuple(int(x) for x in M.PACKAGE_VERSION[M.PACKAGES[0]].split("."))
        # 第三轮（wf_balance_20260927c_magnus）回写后版本再升一档；它改过的键（队长、能力 1、队长 / 槽 1 面板、
        # 6 棵 DSL）由 c 的 CandidateTests 断言，这里只核对第二批改过而第三轮没动的键。
        c_applied = version >= tuple(int(x) for x in MC.PACKAGE_VERSION[MC.PACKAGES[0]].split("."))
        if written_back and c_applied:
            self.assertGreater(version, target)
        elif written_back:
            self.assertEqual(version, target)
        else:
            self.assertLess(version, target)
        c_taken = {("leader", MC.CID), ("ability", MC.A1), *(("cas", key) for key in C_TAKEN_CAS)}
        tables = {"leader": "master/ability/leader_ability.orderedmap",
                  "ability": "master/ability/ability.orderedmap",
                  "cas": "master/string/custom_ability_string.orderedmap"}
        for kind, logical in tables.items():
            rows = X.unpack(candidate.read("common", logical))
            for key, value in want[kind].items():
                if c_applied and (kind, key) in c_taken:
                    continue
                self.assertEqual(X.csv_read(rows[key]), value, f"{kind}:{key}")
        for program, tree in want["dsl"].items():
            if c_applied:
                continue
            raw = candidate.read("common", wf_dsl.dsl_logical(program))
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], tree, program)
        self.assertEqual(before, manifest.read_bytes())


class MirrorTests(unittest.TestCase):
    PATHS = (ROOT / M.DESIGN_REL, ROOT / M.PANEL_REL)

    def setUp(self):
        if not all(path.is_file() for path in self.PATHS):
            self.skipTest("midautumn design mirrors missing")
        # 第三轮（wf_balance_20260927c_magnus）在能力 1 末尾追加了旗号 2 行、新增面板串：生成器已越过第二批，
        # 本模块的 mirror_updates 按第二批记录数重算会拒绝 ⇒ 镜像同步移交 c（test_balance_20260927c_magnus.MirrorTests）。
        if K.SWITCH_LEADER_STRING in K.CAS_TEXTS:
            self.skipTest("第三轮 c 接管设计镜像同步（wf_balance_20260927c_magnus.sync_mirrors）")
        self.docs = [json.loads(path.read_text(encoding="utf-8")) for path in self.PATHS]

    def test_mirrors_are_already_synced(self):
        self.assertEqual(M.sync_mirrors(ROOT, write=False), [])
        design, panel = self.docs
        self.assertEqual(K._design_problems(design), [])
        self.assertIn(M.MIRROR_TAG, design["plan_rework1"])
        block = design["plan_rework1"][M.MIRROR_TAG]
        self.assertEqual((block["ignition_dsl_cap"], block["chase_down_per_hit"],
                          block["chase_down_per_activation"]), (10, 0.2, 1.0))
        self.assertEqual([line["text"] for line in panel["leader"]["lines"]],
                         K.CAS_TEXTS[K.LEADER_OVERRIDE].split("\n"))
        for entry in panel["abilities"]:
            slot = int(entry["index"])
            if slot in (1, 2, 3):
                self.assertEqual([line["text"] for line in entry["lines"]],
                                 K.CAS_TEXTS[K.SLOT_OVERRIDE[slot]].replace(K.MAIN_ICON, "").split("\n"))

    def test_mirror_update_is_idempotent_and_pure(self):
        before = deepcopy(self.docs)
        once = M.mirror_updates(*self.docs)
        self.assertEqual(self.docs, before)
        self.assertEqual(M.mirror_updates(*once), once)


if __name__ == "__main__":
    unittest.main()
