# -*- coding: utf-8 -*-
"""巴萨拉卡 169997 2026-09-27 平衡修订：主位限制、代受搬移、134→194、×0.8、能力5限次、队长成长、面板、技能描述。"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)

import wf_balance_20260927_vaseraga as B
import wf_client_legality as legality
import wf_mod_tool as core

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927_vaseraga.json"
MAIN = " <icon id='main'>  "
A = {slot: f"169997{slot}" for slot in range(1, 7)}

#: 作者 2026-09-27 确认的面板稿（按改动修正数值与行后的终稿）。
PROPOSED = {
    "desc_override_vaseraga_dark": (
        "暗属性共鸣时，暗属性角色攻击力＋300%、能力伤害＋300%，且暗属性角色即使成为棺柩，个体特殊效果也不会消失\n"
        "暗属性共鸣时，自身生命值50%以下时，暗属性角色技能充能速度＋20%、能力伤害＋400%\n"
        "暗属性共鸣时，自身生命值低于1%时，除自身外的暗属性角色技能槽＋50%（CT：20秒），"
        "暗属性角色攻击力＋300%（持续10秒，CT：10秒）\n"
        "暗属性共鸣时，自身发动技能时，受到最大生命值25%的伤害，技能槽＋30%，"
        "并获得攻击力＋300%、全属性抗性＋40%（持续20秒）\n"
        "暗属性共鸣时，自身每造成1次能力伤害，攻击力＋5%、能力伤害＋5%"),
    "desc_override_vaseraga_dark_1": (
        "暗属性共鸣时，队伍全员的总生命值每下降10%，自身攻击力＋25%、能力伤害＋40%（最多10层）"),
    "desc_override_vaseraga_dark_2": (
        "暗属性共鸣时，自身生命值75%以下时，自身全属性抗性＋10%、能力伤害＋80%\n"
        "暗属性共鸣时，自身生命值50%以下时，自身全属性抗性再＋10%、能力伤害再＋120%\n"
        "暗属性共鸣时，自身生命值25%以下时，自身全属性抗性再＋20%、能力伤害再＋200%"),
    "desc_override_vaseraga_dark_3": (
        MAIN + "暗属性共鸣时，「超负荷」期间，自身能力伤害＋160%、攻击力＋120%、全属性抗性＋10%，"
        "并每经过1秒对全体敌人造成8倍暗属性能力伤害\n"
        + MAIN + "暗属性共鸣时，自身发动技能时，自身代替其他队员承受伤害（持续20秒）\n"
        + MAIN + "暗属性共鸣时，战斗开始时及自身发动技能时，获得1次不死效果（无法消除）\n"
        + MAIN + "暗属性共鸣时，暗属性角色的棺柩计数－35"),
    "desc_override_vaseraga_dark_4": "暗属性共鸣时，战斗开始时，自身技能槽＋100%、技能槽最大值＋20%",
    "desc_override_vaseraga_dark_5": (
        "暗属性共鸣时，自身造成能力伤害时，自身技能槽＋5%（CT：2秒），暗属性角色能力伤害＋10%（CT：1.5秒，最多10次）"),
    "desc_override_vaseraga_dark_6": (
        "暗属性共鸣时，自身生命值低于1%时（限1次），获得无敌效果与逆境效果［最大＋40%］（持续8秒）\n"
        "暗属性共鸣时，自身因不死效果以生命值1抵抗住攻击时，获得无敌效果与逆境效果［最大＋40%］（持续8秒），"
        "并对全体敌人造成100倍暗属性能力伤害\n"
        "暗属性共鸣时，持有「古洛诺斯伤痕」时，自身对敌人造成的能力伤害＋15%（独立乘区）"),
}

SKILL_DESCRIPTION = (
    "向前方大范围挥动巨镰，造成20倍暗属性伤害／1秒后降下「血月」（16秒）：每秒对全场敌人造成1倍暗属性伤害"
    "（自身附近的敌人额外受到1倍），并赋予中毒、全属性抗性降低10%、暗属性抗性降低15%效果／"
    "血月命中的敌人与自身获得「古洛诺斯伤痕」／自身获得「超负荷」（16秒）、能力伤害提升400%（20秒）与无敌效果（5秒）")


def diff(a, b):
    return {i: (x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y}


def perturb(value):
    value = deepcopy(value)
    if isinstance(value[0], str):
        value[0] += "x"
    else:
        value[0][0] += "x"
    return value


class VaseragaBalance20260927Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = json.loads(FIXTURE.read_bytes())
        cls.data = {(r["kind"], tuple(r["key"]) if isinstance(r["key"], list) else r["key"]): r["value"]
                    for r in fixture["reads"]}
        cls.absent = fixture["absent_cas"]
        cls.result = B.revise(cls.read_from(cls.data))

    @staticmethod
    def read_from(data):
        return lambda kind, key: data[kind, key]

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    def rows(self, slot):
        return self.result["ability"][A[slot]]

    # ---------------------------------------------------------------- 基线 / 契约

    def test_fixture_is_the_reviewed_before_baseline(self):
        self.assertEqual(set(B.BEFORE), set(self.data))
        for item, expected in B.BEFORE.items():
            self.assertEqual(expected, B.digest(self.data[item]), item)
        self.assertEqual(list(B.PANEL_KEYS), self.absent)
        for key in B.PANEL_KEYS:
            self.assertNotIn(("cas", key), self.data)

    def test_contract_exports_and_package_version_moves_forward(self):
        self.assertEqual(("169997", "vaseraga_dark"), (B.CID, B.CODE))
        self.assertEqual(["vaseraga_dark"], B.PACKAGES)
        self.assertEqual(set(B.PACKAGES), set(B.PACKAGE_VERSION))
        self.assertEqual(["panel-description-override-v2"], B.CAPABILITIES)
        version = lambda text: tuple(int(part) for part in text.split("."))
        self.assertGreater(version(B.PACKAGE_VERSION["vaseraga_dark"]), version("0.1.1"))
        manifest = ROOT / "work/character_packs/vaseraga_dark/package/manifest.json"
        if manifest.is_file():
            current = json.loads(manifest.read_bytes())["package_version"]
            self.assertGreaterEqual(version(B.PACKAGE_VERSION["vaseraga_dark"]), version(current))
        self.assertFalse(hasattr(B, "REVIEWED_DRIFT"))  # 候选包文件与 manifest 无哈希漂移

    def test_only_changed_keys_are_returned_in_the_contract_shape(self):
        result = self.result
        self.assertEqual({"ability", "leader", "cas", "text", "table", "action", "dsl",
                          "server_text", "new_programs", "notes"}, set(result))
        self.assertEqual(set(A.values()), set(result["ability"]))
        self.assertEqual({"169997"}, set(result["leader"]))
        self.assertEqual(set(PROPOSED), set(result["cas"]))
        self.assertEqual({"169997"}, set(result["text"]))
        self.assertEqual({"169997"}, set(result["server_text"]))
        self.assertEqual({"vaseraga_dark"}, set(result["action"]))
        self.assertEqual({}, result["table"])
        self.assertEqual({}, result["dsl"])            # 技能 DSL 不改
        self.assertEqual([], result["new_programs"])
        json.dumps(result["notes"], ensure_ascii=False)
        self.assertFalse(result["notes"]["runtime_verified"])
        for key in result["cas"]:
            self.assertTrue(key.startswith(("desc_override_" + B.CODE, "change_skill_" + B.CODE, B.CODE)))

    # ---------------------------------------------------------------- 1. 主位限制

    def test_only_ability3_stays_main_only(self):
        for slot in range(1, 7):
            expected = {"false"} if slot == 3 else {"true"}
            self.assertEqual(expected, {r[1] for r in self.rows(slot)}, slot)
        # 原先的混合写法被统一：能力3 行2-4 true→false，能力6 行6 false→true。
        self.assertEqual(["false", "true", "true", "true", "false", "false", "false"],
                         [r[1] for r in self.live("ability", A[3])])
        self.assertEqual("false", self.live("ability", A[6])[5][1])
        # 本角色没有 202/203（主位/副位）前置需要清。
        for slot in range(1, 7):
            for row in self.rows(slot):
                self.assertFalse({row[6], row[13], row[20]} & {"202", "203"})

    def test_row_counts(self):
        self.assertEqual([2, 6, 8, 2, 2, 6], [len(self.rows(s)) for s in range(1, 7)])
        self.assertEqual([3, 7, 7, 2, 2, 6], [len(self.live("ability", A[s])) for s in range(1, 7)])
        self.assertEqual(13, len(self.result["leader"]["169997"]))

    # ---------------------------------------------------------------- 2. 代受搬移

    def test_scapegoat_moves_from_ability1_to_the_end_of_ability3(self):
        source = self.live("ability", A[1])[2]
        moved = self.rows(3)[7]
        self.assertEqual(("198", "1", "23"), (source[47], source[48], source[27]))
        self.assertEqual({0: ("vaseraga_dark_1", "vaseraga_dark_3")}, diff(source, moved))  # c1 本就是 false
        self.assertEqual("false", moved[1])
        self.assertNotIn("198", [r[47] for r in self.rows(1) if r[5] == "0"])
        self.assertEqual(["110", "110"], [r[97] for r in self.rows(1)])

    # ---------------------------------------------------------------- 3. 删能力2 行1

    def test_ability2_overload_grant_is_deleted(self):
        live = self.live("ability", A[2])
        self.assertEqual(("461", "1699979"), (live[0][47], live[0][68]))
        rows = self.rows(2)
        self.assertNotIn("461", [r[47] for r in rows])
        self.assertEqual(["4", "154"] * 3, [r[109] for r in rows])
        self.assertEqual(["75000", "75000", "50000", "50000", "25000", "25000"], [r[100] for r in rows])
        for old, new in zip(live[1:], rows):
            self.assertLessEqual(set(diff(old, new)), {1, 113, 114})

    # ---------------------------------------------------------------- 4. 能力3 134 → 194

    def test_ability3_overload_rows_count_the_instance_with_194(self):
        live = self.live("ability", A[3])
        rows = self.rows(3)
        for index, (content, value) in zip((1, 2, 3), (("154", "160000"), ("0", "120000"), ("4", "10000"))):
            self.assertEqual("134", live[index][97])
            row = rows[index]
            self.assertEqual({1, 97, 113, 114}, set(diff(live[index], row)))
            self.assertEqual({85: "(None)", 97: "194", 98: "0", 100: "100000", 101: "100000", 102: "1",
                              104: "1699979", 108: "false", 109: content, 110: "0", 113: value, 114: value},
                             {c: row[c] for c in range(85, 115) if row[c]})
        # 与本角色既有可用 194 行（能力6 行5，伤痕）同形：非空列集合相同，只差键名/主位/限次/固有/内容。
        scar = self.rows(6)[4]
        nonempty = lambda row: {i for i, v in enumerate(row) if v != ""}
        for row in rows[1:4]:
            self.assertEqual(nonempty(scar), nonempty(row))
            self.assertLessEqual(set(diff(scar, row)), {0, 1, 2, 102, 104, 109, 113, 114})

    def test_194_fix_is_what_the_stack_cap_requires(self):
        uniques = {uid: self.data["table", item][0] for uid, item in B.UNIQUE.items()}
        self.assertEqual(("960", "1"), (uniques["1699979"][3], uniques["1699979"][4]))
        before = {key: self.live("ability", key) for key in A.values()}
        self.assertEqual(3, len(B.accumulation_problems(before, uniques)))  # 旧 134 行：层数恒 0
        self.assertEqual([], B.accumulation_problems(self.result["ability"], uniques))
        try:
            from wf_seasonal7_kit_tekuto import accumulation_cap_problems
        except Exception as exc:  # pragma: no cover - 交叉核对是可选的
            self.skipTest(f"tekuto gate unavailable: {exc}")
        self.assertEqual(1, len(accumulation_cap_problems(before, [], uniques)))
        self.assertEqual([], accumulation_cap_problems(self.result["ability"], [], uniques))

    # ---------------------------------------------------------------- 5. ×0.8

    def test_ability_bonuses_are_scaled_by_0_8_to_the_nearest_5_percent(self):
        for (slot, number), (old, new) in B.SCALED.items():
            self.assertEqual(int(new), round(int(old) * 0.8 / 5000) * 5000, (slot, number))
            self.assertEqual(0, int(new) % 5000)
        # 按 live 行号逐格：除 c1 与强度两列外无其它变化。
        live_to_new = {1: {1: 0, 2: 1}, 2: {n: n - 2 for n in range(2, 8)}, 3: {2: 1, 3: 2, 4: 3},
                       6: {3: 2, 4: 3, 5: 4}}
        for (slot, number), (old, new) in B.SCALED.items():
            before = self.live("ability", A[slot])[number - 1]
            after = self.rows(slot)[live_to_new[slot][number]]
            cols = (113, 114) if before[5] == "1" else (51, 52)
            self.assertEqual([old, old], [before[c] for c in cols], (slot, number))
            self.assertEqual([new, new], [after[c] for c in cols], (slot, number))
            allowed = set(cols) | {1} | ({97} if slot == 3 else set())
            self.assertLessEqual(set(diff(before, after)), allowed, (slot, number))
        self.assertEqual(["25000", "40000"], [r[113] for r in self.rows(1)])
        self.assertEqual(["10000", "80000", "10000", "120000", "20000", "200000"], [r[113] for r in self.rows(2)])
        self.assertEqual(["40000", "40000", "15000"],
                         [self.rows(6)[2][51], self.rows(6)[3][51], self.rows(6)[4][113]])

    def test_untouched_rows_keep_every_cell_but_c1(self):
        # (能力槽, live 行下标, 新行下标)：8倍真伤、Guts×2、棺柩；技能槽类；能力5 行1；无敌×2、100倍真伤。
        pairs = [(3, i, i) for i in (0, 4, 5, 6)] + [(4, 0, 0), (4, 1, 1), (5, 0, 0)]
        pairs += [(6, i, i) for i in (0, 1, 5)]
        for slot, index, new_index in pairs:
            before = self.live("ability", A[slot])[index]
            after = self.rows(slot)[new_index]
            self.assertLessEqual(set(diff(before, after)), {1}, (slot, index))
        self.assertEqual(["800000", "3500000"], [self.rows(3)[0][51], self.rows(3)[6][51]])
        self.assertEqual("10000000", self.rows(6)[5][51])
        self.assertEqual(["100000", "100000"], [self.rows(3)[4][51], self.rows(3)[5][51]])

    # ---------------------------------------------------------------- 6. 能力5 行2

    def test_ability5_party_boost_is_10_percent_up_to_10_times(self):
        before, after = self.live("ability", A[5])[1], self.rows(5)[1]
        self.assertEqual({1: ("false", "true"), 34: ("(None)", "10"), 51: ("25000", "10000"),
                          52: ("25000", "10000")}, diff(before, after))
        self.assertEqual(("144", "0", "100000", "90", "388", "5", "Black"),
                         (after[27], after[28], after[30], after[35], after[47], after[48], after[49]))
        self.assertEqual(100, int(after[51]) * int(after[34]) // 1000)  # 最高 +100%

    # ---------------------------------------------------------------- 7. 队长成长

    def test_leader_growth_is_one_tenth_and_still_unlimited(self):
        before, after = self.live("leader", "169997"), self.result["leader"]["169997"]
        for index in range(13):
            expected = {49: ("50000", "5000"), 50: ("50000", "5000")} if index in (10, 11) else {}
            self.assertEqual(expected, diff(before[index], after[index]), index)
        for row in after[10:12]:
            self.assertEqual(("144", "(None)", "0"), (row[25], row[32], row[33]))
        self.assertEqual("1200", after[4][33])  # 以 live 为准（候选包 600 是既有漂移）

    # ---------------------------------------------------------------- 8. 面板

    def test_panel_texts_are_exactly_the_confirmed_wording(self):
        self.assertEqual({k: [[v]] for k, v in PROPOSED.items()}, self.result["cas"])
        for key, value in PROPOSED.items():
            for phrase in B.FORBIDDEN_PANEL_PHRASES:
                self.assertNotIn(phrase, value, key)
            lines = value.split("\n")
            self.assertEqual(key.endswith("_3"), all(line.startswith(MAIN) for line in lines), key)
            if not key.endswith("_3"):
                self.assertNotIn("<icon id='main'>", value, key)
            for line in lines:
                self.assertTrue(line.replace(MAIN, "").startswith("暗属性共鸣时，"), line)
            self.assertEqual([[value]], core.read_csv_lines(core.write_csv_lines([[value]])))
        self.assertEqual([5, 1, 3, 4, 1, 1, 3], [len(PROPOSED[k].split("\n")) for k in B.PANEL_KEYS])

    def test_panel_numbers_are_derived_from_the_revised_rows(self):
        uniques = {uid: self.data["table", item][0] for uid, item in B.UNIQUE.items()}
        ability, leader = deepcopy(self.result["ability"]), deepcopy(self.result["leader"]["169997"])
        ability[A[5]][1][51] = "20000"
        ability[A[5]][1][34] = "5"
        ability[A[6]][4][113] = "30000"
        ability[A[3]][2][113] = "90000"
        leader[10][49] = "7500"
        panels = B.panel_rows(ability, leader, uniques)
        self.assertIn("暗属性角色能力伤害＋20%（CT：1.5秒，最多5次）", panels[B.PANEL[5]][0][0])
        self.assertIn("能力伤害＋30%（独立乘区）", panels[B.PANEL[6]][0][0])
        self.assertIn("攻击力＋90%", panels[B.PANEL[3]][0][0])
        self.assertIn("攻击力＋7.5%、能力伤害＋5%", panels[B.PANEL_LEADER][0][0])
        # 主位图标跟 c1 走：能力3 整键放开后不再带图标。
        for row in ability[A[3]]:
            row[1] = "true"
        self.assertNotIn("<icon id='main'>", B.panel_rows(ability, leader, uniques)[B.PANEL[3]][0][0])

    def test_adversity_wording_follows_the_client_template(self):
        # ui_string ability_description_condition_content_adversity_buff = 逆境效果[最大 ::percent_up_down2::]
        text = PROPOSED["desc_override_vaseraga_dark_6"]
        self.assertEqual(2, text.count("逆境效果［最大＋40%］"))
        self.assertEqual(2, text.count("无敌效果"))

    def test_panel_validation_rejects_markup_mistakes(self):
        uniques = {uid: self.data["table", item][0] for uid, item in B.UNIQUE.items()}
        bad = {
            B.PANEL[3]: PROPOSED[B.PANEL[3]].replace(MAIN, "", 1),          # 主位槽漏图标
            B.PANEL[1]: MAIN + PROPOSED[B.PANEL[1]],                        # 非主位槽带图标
            B.PANEL[2]: PROPOSED[B.PANEL[2]].replace("\n", "／"),           # 用「／」挤成一行
            B.PANEL[4]: "自身为队长时，" + PROPOSED[B.PANEL[4]],            # 禁用措辞
        }
        for key, text in bad.items():
            result = deepcopy(self.result)
            result["cas"][key] = [[text]]
            with self.subTest(key=key):
                self.assertTrue(B.validate(result, uniques))
        result = deepcopy(self.result)
        result["ability"][A[3]][0][1] = "true"
        self.assertTrue(B.validate(result, uniques))  # c1 分布被破坏

    # ---------------------------------------------------------------- 9. 技能描述

    def test_skill_description_is_normalized_everywhere(self):
        for inner, fields in self.result["action"]["vaseraga_dark"]:
            self.assertEqual(SKILL_DESCRIPTION, fields[1], inner)
        before = dict((inner, fields) for inner, fields in self.live("action", "vaseraga_dark"))
        for inner, fields in self.result["action"]["vaseraga_dark"]:
            self.assertEqual({1}, set(diff(before[inner], fields)))
            self.assertEqual(B.PROGRAMS[inner], fields[7])
        for kind in ("text", "server_text"):
            old, new = self.live(kind, "169997")[0], self.result[kind]["169997"][0]
            self.assertEqual({5, 7, 9}, set(diff(old, new)), kind)
            self.assertEqual([SKILL_DESCRIPTION] * 3, [new[5], new[7], new[9]])
            self.assertEqual(["失落传说·古洛诺斯"] * 3, [new[4], new[6], new[8]])
        for stale in ("消耗自身最大生命", "技能槽增加20%", "代替其他队员", "200%攻击力"):
            self.assertNotIn(stale, SKILL_DESCRIPTION)
        # DSL 的持续伤害是 ACPoison：客户端状态名「中毒效果」，没有「流血」状态（按 DSL 改文案）。
        self.assertIn("赋予中毒、", SKILL_DESCRIPTION)
        self.assertNotIn("流血", SKILL_DESCRIPTION)

    def test_skill_description_numbers_come_from_both_dsl_levels(self):
        trees = [self.live("dsl", B.PROGRAMS[level]) for level in ("1", "2")]
        facts = [B.skill_facts(tree) for tree in trees]
        self.assertEqual(facts[0], facts[1])
        self.assertEqual({"swing": {"wait": 30, "multiplier": 20.0},
                          "moon": {"wait": 60, "lifetime": 960, "field_multiplier": 1.0, "near_multiplier": 1.0,
                                   "dot": "ACPoison", "all_resist": -0.1, "dark_resist": -0.15},
                          "self": {"ability_damage": 4.0, "ability_damage_frames": 1200, "invincible_frames": 300}},
                         facts[0])
        uniques = {uid: self.data["table", item][0] for uid, item in B.UNIQUE.items()}
        self.assertEqual(SKILL_DESCRIPTION, B.skill_description(facts[0], uniques))
        # 巨镰倍率改了描述跟着改；结构漂移直接拒绝。
        tree = deepcopy(trees[0])
        swing = tree[11][1][2][1][3][1][1][1]
        self.assertEqual("CreateHitArea", swing[0])
        swing[23][1][1][1][6] = [{"min": 25.0, "max": 25.0}]
        self.assertIn("造成25倍暗属性伤害", B.skill_description(B.skill_facts(tree), uniques))
        broken = deepcopy(trees[0])
        del broken[11][1][6]
        with self.assertRaises(B.VaseragaBalanceError):
            B.skill_facts(broken)
        data = deepcopy(self.data)
        data["dsl", B.PROGRAMS["2"]] = tree
        with self.assertRaises(B.VaseragaBalanceError):  # 两档不一致同样拒绝（BEFORE 先拦）
            B.revise(self.read_from(data))

    # ---------------------------------------------------------------- 门禁 / 纯函数

    def test_every_output_row_passes_the_client_gates(self):
        strings = set(self.result["cas"])
        for table, group in (("ability", self.result["ability"]), ("leader_ability", self.result["leader"])):
            for key, rows in group.items():
                for index, row in enumerate(rows, 1):
                    with self.subTest(table=table, key=key, row=index):
                        self.assertEqual(126 if table == "ability" else 124, len(row))
                        self.assertEqual([], legality.client_legality_problems(table, row))
                        self.assertEqual([], legality.declared_block_field_problems(table, row))
                        self.assertEqual([], legality.ability_element_column_problems(table, row, 5))
                        self.assertEqual([], legality.invoke_skill_string_problems(row, strings, table))
                        self.assertEqual([], legality.required_client_capabilities(table, row))
        for key in self.result["cas"]:
            self.assertEqual(["panel-description-override-v2"],
                             legality.required_client_capabilities(legality.CUSTOM_ABILITY_STRING_KIND, [key]))
        uniques = {uid: self.data["table", item][0] for uid, item in B.UNIQUE.items()}
        self.assertEqual([], B.validate(self.result, uniques))

    def test_inputs_are_not_mutated_and_outputs_are_independent(self):
        data = deepcopy(self.data)
        before = deepcopy(data)
        result = B.revise(self.read_from(data))
        self.assertEqual(before, data)
        result["ability"][A[3]][7][0] = "changed"
        result["leader"]["169997"][10][49] = "changed"
        result["text"]["169997"][0][5] = "changed"
        result["server_text"]["169997"][0][5] = "changed"
        result["action"]["vaseraga_dark"][0][1][1] = "changed"
        self.assertEqual(before, data)
        self.assertEqual(self.result, B.revise(self.read_from(before)))  # 确定性

    def test_any_live_drift_fails_closed(self):
        for item in B.BEFORE:
            data = deepcopy(self.data)
            data[item] = perturb(data[item])
            with self.subTest(item=item), self.assertRaisesRegex(ValueError, "live drift"):
                B.revise(self.read_from(data))
        # 已发布后的新值同样拒绝：重跑不会把 ×0.8 再乘一次。
        data = deepcopy(self.data)
        for kind in ("ability", "leader", "text", "server_text"):
            for key, rows in self.result[kind].items():
                data[kind, key] = deepcopy(rows)
        with self.assertRaisesRegex(ValueError, "live drift"):
            B.revise(self.read_from(data))
        # 面板键已存在（被别人抢先写入）也拒绝。
        data = deepcopy(self.data)
        data["cas", B.PANEL[4]] = [["x"]]
        with self.assertRaisesRegex(ValueError, "already exists"):
            B.revise(self.read_from(data))

    # ---------------------------------------------------------------- 官方先例（可选）

    def test_revised_rows_follow_official_precedents(self):
        cdn = ROOT / ".cdn/cn"
        if not cdn.is_dir():
            self.skipTest("official CDN archive unavailable")
        from wf_enhancement_policy import OfficialBaseline
        baseline = OfficialBaseline(cdn, cache_dir=ROOT / "mod-tools/work/official-baseline", write_cache=False)
        digest = core.sha1_path("master/ability/ability.orderedmap")
        official = core.read_orderedmap_file_from_bytes(baseline.get("common", digest[:2] + "/" + digest[2:]))
        rows = [row for value in official.values() for row in core.read_csv_lines(value) if len(row) > 115]
        during194 = [r for r in rows if r[5] == "1" and r[97] == "194"]
        self.assertTrue(during194)
        self.assertEqual({("0", "100000", "100000", "1", "false")},
                         {(r[98], r[100], r[101], r[102], r[108]) for r in during194 if r[98] == "0"})
        # notes 里的先例清单与官方表一致：自身来源（c98=0）6 条，另 3 条是 c98=5 的非自身形，分开标注。
        labelled = {}
        for key, value in official.items():
            for index, row in enumerate(core.read_csv_lines(value)):
                if len(row) > 115 and row[5] == "1" and row[97] == "194":
                    labelled[f"{key}#{index}"] = row
        fix_194 = self.result["notes"]["fix_194"]
        self.assertEqual({k for k, r in labelled.items() if r[98] == "0"}, set(fix_194["official_precedents"]))
        self.assertEqual({k for k, r in labelled.items() if r[98] != "0"},
                         set(fix_194["official_other_shape"]["rows"]))
        self.assertEqual({("5", "7")}, {(labelled[k][98], labelled[k][110])
                                        for k in fix_194["official_other_shape"]["rows"]})
        for row in self.rows(3)[1:4]:
            self.assertEqual(("0", "100000", "100000", "1", "false"), (row[98], row[100], row[101], row[102], row[108]))
        limited = [r for r in rows if r[5] == "0" and r[27] == "144" and r[47] == "388" and r[48] == "5"
                   and r[34] == "10"]
        self.assertTrue(limited, "official 144 → 388 party rows with a 10-trigger limit")


if __name__ == "__main__":
    unittest.main()
