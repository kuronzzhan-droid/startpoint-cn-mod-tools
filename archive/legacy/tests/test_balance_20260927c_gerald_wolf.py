# -*- coding: utf-8 -*-
"""杰拉德 149999 ``white_wolf_gerald`` 2026-09-27 第三轮（成长复核）：队长 #6–#8 每 50 直击 +5% → +40%。

fixture = live 输入快照（``fixtures/balance_20260927c_gerald_wolf.json``，链尾 1.4.1053 只读取数），驱动 ``revise()``：
改动的前后值、未改行逐字保留、档位与取整、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、合法性门禁为空、
自动面板回读；live 输入 == 第二批输出（链式核对）；生成器（relocate 透传）不回退；候选工作区干跑拼接（缺时跳过）。
面板同条件合并（能力1 L1+L3 → 一行，L2「战斗开始时」不并）：合并行逐字、数据条件逐格相同、``wf_panel_merge_check``
通过（仓库内校验器，硬依赖）、共鸣省略依据（不适用）、自动面板不新建覆盖；口径 3：返回面板本无「X属性共鸣时」。
技能说明本体按数据改字（作者「杰拉德数据是消除 2 个、全属性是要这个」）：text/服务端三处字面、两档 DSL 关支事实核对、
六处说明一致、数据变异拒绝（``TextDescFactTests``）。
``_context`` 是 revise() 不读取的 live 参照（文案、字串、能力3 行、不存在的覆盖键），只用来核对「文案不含这些数值」
与合并/共鸣依据。
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

import wf_balance_20260927b_gerald_wolf as B2  # noqa: E402
import wf_balance_20260927c_gerald_wolf as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_gerald_cast_growth as G  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_panel_merge_check as PMC  # noqa: E402   面板合并校验器（仓库内，硬依赖）

FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_gerald_wolf.json'
B2_FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_gerald_wolf.json'
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
LEADER_TABLE = "master/ability/leader_ability.orderedmap"
CAS_TABLE = "master/string/custom_ability_string.orderedmap"


def load():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}, data["_context"]


def reader(inputs):
    def read(kind, key):
        if key not in inputs.get(kind, {}):
            raise KeyError(f"{kind}:{key}")
        return inputs[kind][key]
    return read


def cells_diff(old, new):
    return {c: (a, b) for c, (a, b) in enumerate(zip(old, new)) if a != b}


def version(text):
    return tuple(map(int, text.split(".")))


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.context = load()
        cls.out = M.revise(reader(deepcopy(cls.inputs)))
        cls.old = cls.inputs["leader"][M.CID]
        cls.new = cls.out["leader"][M.CID]

    # ------------------------------------------------------------ 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.inputs[kind][key]), want, (kind, key))
        self.assertEqual({(kind, key) for kind, keys in self.inputs.items() for key in keys}, set(M.BEFORE))

    def test_live_input_is_the_batch2_output(self):
        """链式核对：本轮输入（live 1.4.1053）== 第二批 revise() 对第二批 fixture 的输出（gerald2 未动队长）。"""
        data = json.loads(B2_FIXTURE.read_text(encoding="utf-8"))
        b2_inputs = {k: v for k, v in data.items() if not k.startswith("_")}
        b2_out = B2.revise(lambda kind, key: b2_inputs[kind]["|".join(key) if kind == "table" else key])
        self.assertEqual(b2_out["leader"][M.CID], self.old)

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), ("149999", "white_wolf_gerald"))
        self.assertEqual(M.PACKAGES, ["white_wolf_gerald"])
        self.assertEqual(M.PACKAGE_VERSION, {"white_wolf_gerald": "0.20260927.2"})   # 候选现值 0.20260927.1
        self.assertEqual((M.CAPABILITIES, M.REVIEWED_DRIFT), ([], {}))
        self.assertEqual(M.ELEMENT, 4)
        json.dumps(self.out["notes"], ensure_ascii=False)
        self.assertFalse(self.out["notes"]["runtime_verified"])

    def test_only_the_leader_key_and_the_merged_panel_are_returned(self):
        self.assertEqual(set(self.out["leader"]), {M.CID})
        # 能力1 面板同条件合并 + 技能强化条目（R2）
        self.assertEqual(set(self.out["cas"]), {M.CAS_A1, M.CAS_FLAG})
        # 技能说明（R3）：action_skill 两档、character_text、服务端镜像
        self.assertEqual((set(self.out["action"]), set(self.out["text"]), set(self.out["server_text"])),
                         ({M.CODE}, {M.CID}, {M.CID}))
        for kind in ("ability", "table", "dsl"):                             # 能力1 行、两档 DSL 只读
            self.assertEqual(self.out[kind], {}, kind)
        self.assertEqual(self.out["new_programs"], [])

    # ------------------------------------------------------------ 队长 #6–#8

    def test_leader_changes_exactly_six_cells(self):
        self.assertEqual((len(self.old), len(self.new)), (12, 12))
        seen = {i: cells_diff(a, b) for i, (a, b) in enumerate(zip(self.old, self.new)) if a != b}
        self.assertEqual(seen, {i: {49: ("5000", "40000"), 50: ("5000", "40000")} for i in (6, 7, 8)})
        for i in (0, 1, 2, 3, 4, 5, 9, 10, 11):          # 未改行逐字保留
            self.assertEqual(self.new[i], self.old[i], i)
        self.assertTrue(all(len(row) == 124 for row in self.new))

    def test_growth_rows_keep_trigger_and_uncapped_shape(self):
        """光编成≥6、全队直击每 50 次、限次 (None)、CT 0、全队(光)；只把强度改成原值 × 4/5。"""
        for i, kind in ((6, "32"), (7, "33"), (8, "388")):
            row = self.new[i]
            self.assertEqual((row[4], row[7], row[8], row[9]), ("2", "600000", "600000", "White"))
            self.assertEqual((row[25], row[26], row[27], row[28], row[29]),
                             ("20", "7", "White", "5000000", "5000000"))
            self.assertEqual((row[32], row[33]), ("(None)", "0"))
            self.assertEqual((row[45], row[46], row[47]), (kind, "5", "White"))
            self.assertEqual((row[49], row[50]), ("40000", "40000"))
            self.assertEqual(int(row[49]) * 5, int(B2.GROWTH_OLD[0]) * 4)       # 原 50% × 4/5
            self.assertEqual(int(row[49]) % 5000, 0)                            # 5 的倍数

    def test_rounding_rule(self):
        self.assertEqual(M.rounded_growth("50000", (4, 5)), "40000")
        self.assertEqual(M.rounded_growth("50000", (7, 10)), "35000")           # 数值表备选档
        self.assertEqual(M.rounded_growth("40000", (4, 5)), "30000")            # 32 → 30（就近）
        self.assertEqual(M.rounded_growth("160000", (4, 5)), "130000")          # 128 → 130
        self.assertEqual(M.rounded_growth("5000", (7, 10)), "3500")             # <20% 取 0.5
        with self.assertRaises(ValueError):
            M.rounded_growth("25000", (1, 2))                                    # 低于 2/3

    def test_kept_rows(self):
        new = self.new
        self.assertEqual(B2.stunify_rows(new), [(9, "5", 50000)])              # 第二批 Down 不动
        self.assertEqual((new[5][45], new[5][28], new[5][49]), ("255", "3500000", "1500000"))
        self.assertEqual((new[10][45], new[10][68]), ("629", "ability_skill_gerald_time_rift"))
        self.assertEqual((new[11][45], new[11][4], new[11][9], new[11][68]),
                         ("536", "2", "White", "change_skill_white_wolf_gerald"))

    def test_auto_panel_reads_forty_percent(self):
        self.assertIn("desc_override_black_wolf_knight", self.context["cas_absent"])
        lines = D.describe_rows(self.new, "leader_ability")
        self.assertEqual(lines[6], "光·编成≥6 时: 编成直接攻击≥50 → 赋予全队(光) 攻击力 40%")
        self.assertEqual(lines[7], "光·编成≥6 时: 编成直接攻击≥50 → 赋予全队(光) Direct伤害 40%")
        self.assertEqual(lines[8], "光·编成≥6 时: 编成直接攻击≥50 → 赋予全队(光) 能力伤害 40%")
        old = D.describe_rows(self.old, "leader_ability")
        self.assertEqual([a for a, b in zip(old, lines) if a != b], old[6:9])
        for line in lines:
            self.assertEqual(KL.panel_problems(line), [], line)

    def test_texts_do_not_carry_the_growth_numbers(self):
        texts = [row[0] for rows in self.context["cas"].values() for row in rows]
        texts += [fields[1] for _k, fields in self.context["action"][M.CODE]]
        texts += [cell for row in self.context["text"][M.CID] for cell in row]
        texts += [cell for row in self.context["server_text"][M.CID] for cell in row]
        for text in texts:
            for word in ("40%", "50次", "直接攻击每", "能力伤害提升"):
                self.assertNotIn(word, text)

    def test_every_row_passes_client_gates(self):
        cas_keys = {"change_skill_white_wolf_gerald", "ability_skill_gerald_time_rift"}
        for i, row in enumerate(self.new):
            self.assertEqual(L.client_legality_problems("leader_ability", row), [], i)
            self.assertEqual(L.declared_block_field_problems("leader_ability", row), [], i)
            self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, "leader_ability"), [], i)
            self.assertEqual(L.required_client_capabilities("leader_ability", row), [], i)
            self.assertEqual(KL.row_problems("leader_ability", row), {}, i)
        for i in M.GROWTH_ROWS:
            self.assertEqual(M.row_problems(self.new[i]), [], i)

    # ------------------------------------------------------------ fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.inputs)
        out = M.revise(reader(data))
        self.assertEqual(data, self.inputs)
        out["leader"][M.CID][6][49] = "mutated"
        out["cas"][M.CAS_A1][0][0] = "mutated"
        self.assertEqual(data, self.inputs)

    def test_baseline_drift_is_rejected(self):
        drifted = deepcopy(self.inputs)
        drifted["leader"][M.CID][-1][-1] += "x"
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(drifted))
        for kind, key in (("ability", M.A1_KEY), ("cas", M.CAS_A1)):
            drifted = deepcopy(self.inputs)
            drifted[kind][key][0][0] += "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(drifted))
        missing = deepcopy(self.inputs)
        missing["leader"][M.CID] = None
        with self.assertRaises(ValueError):
            M.revise(reader(missing))

    def test_a_leader_panel_override_is_rejected(self):
        data = deepcopy(self.inputs)
        data["cas"][M.LEADER_PANEL_KEY] = [["覆盖"]]
        with self.assertRaisesRegex(ValueError, "no longer auto-generated"):
            M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        live = deepcopy(self.inputs)
        live["leader"].update(deepcopy(self.out["leader"]))
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(live))
        with self.assertRaises(ValueError):
            M.leader_rows(self.new)
        with self.assertRaises(ValueError):
            M.ability1_text(self.out["cas"][M.CAS_A1])
        # 第二批前（50%）的旧态同样拒绝：只接受 live 的 5%。
        pre_batch2 = deepcopy(self.old)
        for index in M.GROWTH_ROWS:
            pre_batch2[index][49] = pre_batch2[index][50] = "50000"
        with self.assertRaises(ValueError):
            M.leader_rows(pre_batch2)

    def test_row_locators_are_content_based(self):
        old = deepcopy(self.old)
        with self.assertRaises(ValueError):
            M.leader_rows(old[:6] + [old[7], old[6]] + old[8:])
        for index, col, value in ((7, 32, "10"), (5, 49, "1000000"), (9, 111, "500000"),
                                  (11, 9, "Red"), (6, 46, "0")):
            rows = deepcopy(old)
            rows[index][col] = value
            with self.assertRaises(ValueError, msg=(index, col)):
                M.leader_rows(rows)
        with self.assertRaises(ValueError):
            M.leader_rows(old[:11])


class PanelMergeTests(unittest.TestCase):
    """能力1 面板同条件合并与共鸣省略依据；按本轮数据重核扫描 panel_merge/scan.json。"""

    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.context = load()
        cls.out = M.revise(reader(deepcopy(cls.inputs)))

    def test_merged_panel_verbatim(self):
        self.assertEqual(self.inputs["cas"][M.CAS_A1], [["自身弱化效果无效。\n战斗开始时，自身技能槽+100%。\n"
                                                          "自身技能槽最大值+50%。\n作为合击角色编成时，自身无法因技能或能力效果"
                                                          "增加技能槽（战斗开始时除外）。"]])
        self.assertEqual(self.out["cas"][M.CAS_A1], [["自身弱化效果无效、技能槽最大值+50%。\n战斗开始时，自身技能槽+100%。\n"
                                                       "作为合击角色编成时，自身无法因技能或能力效果增加技能槽（战斗开始时除外）。"]])
        old, new = M.OLD_A1_LINES, M.NEW_A1_LINES
        # 合并行 = L1 + L3 去掉重复对象「自身」，句号只在行末；放在 L1 位置；L2、L4 逐字保留、行序不变。
        self.assertEqual(new[0], old[0].rstrip("。") + "、" + old[2].removeprefix("自身").rstrip("。") + "。")
        self.assertEqual(new[1:], (old[1], old[3]))
        self.assertEqual(M.PANEL_MERGES, {M.CAS_A1: (M.A1_KEY, (0, 2), (0, 2), old, new)})
        self.assertEqual(M.PREFIX_DROPS, {})

    def test_merge_group_is_one_data_condition(self):
        rows = self.inputs["ability"][M.A1_KEY]
        self.assertEqual(M.ability1_rows_problems(rows), [])
        self.assertEqual([D.describe_line(r, "ability") for r in rows],
                         ["自身 减益无效", "自身 技能槽 100%", "自身 2号位技能槽 50%",
                          "持有者为协力 时: 持续·HP≥ → 自身 限制技能槽增加 0%"])
        diff = lambda a, b: {c for c, (x, y) in enumerate(zip(rows[a], rows[b])) if x != y}   # noqa: E731
        self.assertEqual(diff(0, 2), {47, 51, 52})                        # 合并的两行只有效果列不同
        # #1（kind 211 一次性充能）数据同条件，但文案写「战斗开始时」⇒ 文案条件不同，按规则不并（扫描 skipped_groups）。
        self.assertLessEqual(diff(0, 1), M.ABILITY_EFFECT_COLUMNS)
        self.assertEqual(rows[M.A1_SAME_CONDITION_NOT_MERGED][47], "211")
        self.assertTrue(M.NEW_A1_LINES[1].startswith("战斗开始时，"))
        # #3（合击位限制）条件不同。
        self.assertTrue(diff(0, 3) - M.ABILITY_EFFECT_COLUMNS)
        self.assertIn("+50%", M.NEW_A1_LINES[0])
        self.assertEqual(rows[2][51], "50000")                            # 数字 == 行值

    def test_auto_panels_get_no_new_override(self):
        """队长与能力 2–6 是自动面板（覆盖键在 live 不存在）⇒ 不新建覆盖文案。"""
        self.assertEqual(list(M.AUTO_PANEL_KEYS), self.context["cas_absent"])
        self.assertFalse(set(self.out["cas"]) & set(M.AUTO_PANEL_KEYS))

    def test_resonance_omission_basis(self):
        """「时之刻印」全部来源带光共鸣，但没有覆盖面板行依赖它；能力1 面板本无「X属性共鸣时，」⇒ 无可省前缀。"""
        a3 = self.context["ability"]["1499993"]
        grants = [(i, r[68]) for i, r in enumerate(a3) if r[47] == "461"]            # c68 = 固有 id
        self.assertEqual(grants, [(0, "1499989")])                       # 唯一授予行：能力3 #0 → 时之刻印
        self.assertEqual((a3[0][6], a3[0][9], a3[0][11]), ("2", "600000", "White"))   # 光共鸣前置
        for text in (self.inputs["cas"][M.CAS_A1][0][0], self.out["cas"][M.CAS_A1][0][0]):
            self.assertIsNone(re.search(r"属性共鸣时", text))
            self.assertNotIn("时之刻印", text)
        self.assertEqual(M.PREFIX_DROPS, {})
        self.assertIn("时之刻印", M.RESONANCE_BASIS)

    def test_check_merge_passes(self):
        self.assertNotRegex(self.inputs["cas"][M.CAS_A1][0][0], "属性共鸣时")   # 口径 3：orig 无共鸣写法，不需要规范化
        result = PMC.check(self.inputs["cas"][M.CAS_A1][0][0], self.out["cas"][M.CAS_A1][0][0], [])
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual((result["errors"], result["warnings"]), ([], []))
        self.assertEqual(result["columns"][0]["mapping"], {1: 1, 2: 2, 3: 1, 4: 3})
        self.assertEqual(result["columns"][0]["kinds"], {1: "merge", 2: "verbatim", 3: "verbatim"})
        bad = self.out["cas"][M.CAS_A1][0][0].replace("+50%", "+55%")
        self.assertFalse(PMC.check(self.inputs["cas"][M.CAS_A1][0][0], bad, [])["ok"])

    def test_panel_rules(self):
        self.assertEqual(M.panel_problems(self.out["cas"]), [])
        text = self.out["cas"][M.CAS_A1][0][0]
        for word in ("／", "自身为队长时", "觉醒后", "生命值100%以下", "<icon"):
            self.assertNotIn(word, text)
        for line in text.split("\n"):
            self.assertEqual(KL.panel_problems(line), [], line)
        self.assertEqual(L.panel_override_capability(M.CAS_A1), "panel-description-override-v2")

    def test_merge_mutations_are_rejected(self):
        for index, col, value in ((2, 5, "1"), (2, 1, "false"), (2, 6, "2"), (2, 34, "1")):
            data = deepcopy(self.inputs)
            data["ability"][M.A1_KEY][index][col] = value
            with self.assertRaises(ValueError, msg=(index, col)):
                M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.ability1_text([[M.PANEL_MERGES[M.CAS_A1][3][0]]])


class SkillEnhancementTextTests(unittest.TestCase):
    """作者「技能里面不要重复描述强化后的效果」（主会话口径 R1–R4）：强化条目点明技能名，技能说明删「强化后」整段。"""

    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.context = load()
        cls.out = M.revise(reader(deepcopy(cls.inputs)))

    def test_flag_entry_names_the_skill(self):
        self.assertEqual(self.inputs["cas"][M.CAS_FLAG],
                         [["强化自身技能：追加按敌人当前生命值计算的固定伤害（随技能发动次数提高），并斩杀低生命值的敌人"]])
        self.assertEqual(self.out["cas"][M.CAS_FLAG],
                         [["强化『月耀一闪』：追加按敌人当前生命值计算的固定伤害（随技能发动次数提高），并斩杀低生命值的敌人"]])
        text = self.out["cas"][M.CAS_FLAG][0][0]
        self.assertEqual(M.flag_entry_problems(text), [])
        self.assertEqual(KL.panel_problems(text, skill_flag=True), [])
        self.assertFalse(any(ch.isdigit() for ch in text))
        self.assertNotIn("共鸣", text)                                    # 客户端按 536 前置拼「光属性共鸣时」
        self.assertEqual(M.flag_entry_problems(self.inputs["cas"][M.CAS_FLAG][0][0]),
                         ["skill flag: must start with one of ('强化『月耀一闪』', '为『月耀一闪』追加'): "
                          + self.inputs["cas"][M.CAS_FLAG][0][0],
                          "skill flag: banned wording '强化自身技能'"])

    def test_skill_descriptions_drop_the_enhanced_segment(self):
        segment = ("／强化后：对最近的敌人追加造成其当前生命值5%的固定伤害（每次发动技能提高1%），"
                   "敌人生命值低于最大生命值5%时直接斩杀")
        self.assertEqual(M.ENHANCED_SEGMENT, segment)
        actions = self.inputs["action"][M.CODE]
        new_actions = self.out["action"][M.CODE]
        self.assertEqual([inner for inner, _f in new_actions], ["1", "2"])
        for (inner, old), (_inner, new) in zip(actions, new_actions):
            self.assertEqual(old[1], new[1] + segment, inner)
            self.assertEqual([c for c, (a, b) in enumerate(zip(old, new)) if a != b], [1], inner)
            self.assertTrue(new[1].endswith("／赋予队伍最大速度固定＋贯穿＋浮游效果（技能伤害以直接攻击伤害计算）"))
        for kind in ("text", "server_text"):
            old, new = self.inputs[kind][M.CID], self.out[kind][M.CID]
            self.assertEqual([c for c, (a, b) in enumerate(zip(old[0], new[0])) if a != b], [5, 7], kind)
            for col in (5, 7):
                # 删「强化后」段 + 本体按数据改三处字面（TextDescFactTests 逐字核对）。
                self.assertEqual(old[0][col], M.BODY_TEXT_DESC + segment, (kind, col))
                self.assertEqual(new[0][col], M.NEW_TEXT_DESC, (kind, col))
                self.assertTrue(new[0][col].endswith("／赋予队伍最大速度固定＋贯穿＋浮游效果"), (kind, col))
        self.assertEqual(self.out["text"][M.CID], self.out["server_text"][M.CID])
        for text in [f[1] for _i, f in new_actions] + [self.out["text"][M.CID][0][c] for c in (5, 7)]:
            self.assertEqual(M.desc_problems(text), [], text)
            for word in ("强化后", "斩杀", "固定伤害", "共鸣", "5%", "1%"):
                self.assertNotIn(word, text)
        # action 改后 == gerald2 追加前的技能本体文字；text 本体 == gerald2 追加前的文字（改字前）。
        import wf_balance_20260927b_gerald2 as G2
        self.assertEqual((M.NEW_ACTION_DESC, M.BODY_TEXT_DESC), (G2.OLD_ACTION_DESC, G2.OLD_TEXT_DESC))

    def test_removed_segment_is_the_flag_one_branch(self):
        """R1：删掉的内容只在 ConditionalsChangeSkillFlag(1) 开支里，旗号 1 = 队长 #11 的 536（光≥6 共鸣）。"""
        self.assertEqual(M.skill_flag_basis_problems(self.out["leader"][M.CID],
                                                     {p: self.inputs["dsl"][p] for p in B2.SKILLS}), [])
        row = self.out["leader"][M.CID][11]
        self.assertEqual((row[45], row[4], row[7], row[9], row[68]), ("536", "2", "600000", "White", M.CAS_FLAG))
        # 变异：旗号改成 2 / 关支也挂固定伤害 ⇒ 依据不成立。
        import wf_balance_20260927b_gerald2 as G2
        for program in B2.SKILLS:
            tree = deepcopy(self.inputs["dsl"][program])
            flag = G2.enhanced_branches(tree)
            self.assertEqual(flag[1][0], "Block")
            G2.B2._at(tree, flag[0])[1] = 2
            with self.assertRaises(ValueError):
                M.revise(reader({**self.inputs, "dsl": {**self.inputs["dsl"], program: tree}}))
            self.assertTrue(M.skill_flag_basis_problems(self.out["leader"][M.CID],
                                                        {**self.inputs["dsl"], program: tree}))

    def test_live_drift_and_reapply_are_rejected(self):
        for kind, key in (("cas", M.CAS_FLAG), ("text", M.CID), ("server_text", M.CID)):
            data = deepcopy(self.inputs)
            data[kind][key][0][0] += "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))
        data = deepcopy(self.inputs)
        data["action"][M.CODE][0][1][1] += "x"
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(data))
        # 对自身输出重跑（绕过摘要）⇒ 改前文字核对拒绝。
        own = {("cas", M.CAS_FLAG): self.out["cas"][M.CAS_FLAG], ("action", M.CODE): self.out["action"][M.CODE],
               ("text", M.CID): self.out["text"][M.CID], ("server_text", M.CID): self.out["server_text"][M.CID]}
        for item, value in own.items():
            inputs = {k: deepcopy(self.inputs[k[0]][k[1]]) for k in M.BEFORE}
            inputs[item] = deepcopy(value)
            with self.assertRaises(ValueError, msg=item):
                M.skill_text_outputs(inputs)

    def test_generator_constant_equals_the_revision(self):
        self.assertEqual(G.ENHANCEMENT_TEXT, self.out["cas"][M.CAS_FLAG][0][0])
        self.assertEqual(G.ENHANCEMENT_TEXT, M.NEW_CAS_FLAG_TEXT)


class TextDescFactTests(unittest.TestCase):
    """作者「杰拉德数据是消除 2 个、全属性是要这个」：character_text / 服务端本体按两档 DSL 关支改字，六处说明事实一致。"""

    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.context = load()
        cls.out = M.revise(reader(deepcopy(cls.inputs)))
        cls.trees = {p: cls.inputs["dsl"][p] for p in B2.SKILLS}

    def descs(self, out=None):
        out = out or self.out
        return ([f[1] for _i, f in out["action"][M.CODE]]
                + [out[kind][M.CID][0][c] for kind in ("text", "server_text") for c in (5, 7)])

    def test_new_text_verbatim(self):
        self.assertEqual(M.NEW_TEXT_DESC,
                         "时空为之凝滞的一闪。展开时之魔法阵，向最近的敌人突进并对接触到的敌人造成光属性伤害／"
                         "以全屏月牙交叉斩对全体敌人造成光属性伤害 ＋ 消除2个强化效果 ＋ 赋予累积全属性抗性降低效果／"
                         "赋予队伍最大速度固定＋贯穿＋浮游效果")
        self.assertEqual([(old, new) for old, new, _b in M.TEXT_DESC_FIXES],
                         [("对领域内全体敌人", "对全体敌人"), ("强制消除1个强化效果", "消除2个强化效果"),
                          ("赋予累积光属性抗性降低效果", "赋予累积全属性抗性降低效果")])
        body = M.BODY_TEXT_DESC
        for old, new, _basis in M.TEXT_DESC_FIXES:
            body = body.replace(old, new)
        self.assertEqual(body, M.NEW_TEXT_DESC)                           # 只改这三处字面
        # action 本体本来就与数据一致，不改字（只删「强化后」段）。
        for text in (M.NEW_ACTION_DESC,):
            for phrase in ("以全屏月牙交叉斩对全体敌人", "消除敌人的2个强化效果", "赋予敌人累积全属性抗性降低效果"):
                self.assertIn(phrase, text)

    def test_plain_branch_facts_match_the_text(self):
        for program in B2.SKILLS:
            facts = M.plain_branch_facts(self.trees[program])
            self.assertEqual(facts["deletes"], [(2, 2)], program)                 # 命中敌人，删除 2 条
            self.assertEqual(facts["delete_kinds"], [["DCAll", 2]], program)      # 强化效果
            self.assertEqual(facts["tolerance_lowers"], [True], program)          # 降抗
            self.assertEqual(facts["tolerance_elements"], [254], program)          # 全属性
            self.assertEqual(facts["strike_areas"], [(-1, (1500, 2000))] * 2, program)   # 场地点全屏矩形
            self.assertEqual((facts["domain_in_plain"], facts["domain_in_enhanced"]), (False, True), program)
        self.assertEqual(M.desc_fact_problems(self.trees, self.descs()), [])

    def test_six_descriptions_agree(self):
        descs = self.descs()
        self.assertEqual(len(descs), 6)
        self.assertEqual(len(set(descs[2:])), 1)                          # text c5/c7 == 服务端 [5]/[7]
        self.assertEqual(descs[0], descs[1])                              # action 两档同文
        for text in descs:
            for word in ("领域", "强制消除", "光属性抗性", "1个强化效果"):
                self.assertNotIn(word, text)
        # 改前本体：旧写法三项全部被门禁报出。
        old_body = [self.inputs["text"][M.CID][0][5].removesuffix(M.ENHANCED_SEGMENT)]
        found = M.desc_fact_problems(self.trees, old_body)
        for name in ("delete", "tolerance", "full_screen"):
            self.assertTrue(any(f"missing {name} fact" in p for p in found), name)
        for word in ("领域", "强制消除", "光属性抗性", "1个强化效果"):
            self.assertTrue(any(repr(word) in p for p in found), word)

    def test_data_mutations_are_rejected(self):
        """数据变了（删 1 条 / 单属性 / 非全屏 / 领域进关支）⇒ 文字依据不成立，revise 拒绝。"""
        import wf_balance_20260927b_gerald2 as G2

        def mutate(program, fn):
            tree = deepcopy(self.inputs["dsl"][program])
            _f, _enhanced, plain = G2.enhanced_branches(tree)
            fn(plain)
            return tree

        def delete_one(plain):
            G2._nodes(plain, "DeleteCondition")[0][1][3] = 1

        def debuff_kind(plain):
            G2._nodes(plain, "DeleteCondition")[0][1][2] = ["DCAll", 3]

        def tolerance_up(plain):
            G2._nodes(plain, "ACToleranceOfElement")[0][1][3] = [{"min": 0.15, "max": 0.15}]

        def light_only(plain):
            G2._nodes(plain, "ACToleranceOfElement")[0][1][2] = 5

        def small_area(plain):
            for _p, node in G2._nodes(plain, "CreateHitArea"):
                if node[9][0] == "Rectangle":
                    node[9][1][0] = {"min": 600, "max": 600}

        def domain_in_plain(plain):
            G2._nodes(plain, "ShowEffect")[0][1][1] = "時空領域演出"

        for fn in (delete_one, debuff_kind, tolerance_up, light_only, small_area, domain_in_plain):
            for program in B2.SKILLS:
                tree = mutate(program, fn)
                self.assertTrue(M.desc_fact_problems({**self.trees, program: tree}, self.descs()),
                                (fn.__name__, program))
                with self.assertRaises(ValueError, msg=(fn.__name__, program)):
                    M.revise(reader({**self.inputs, "dsl": {**self.inputs["dsl"], program: tree}}))


class GeneratorTests(unittest.TestCase):
    """三格没有现行生成器：relocate 透传既有队长行，重跑不回退。"""

    @classmethod
    def setUpClass(cls):
        cls.inputs, _ = load()
        cls.leader = M.revise(reader(deepcopy(cls.inputs)))["leader"][M.CID]

    def test_cast_growth_relocate_passes_the_revised_rows_through(self):
        rift, flag = self.leader[10], self.leader[11]
        a2 = [["black_wolf_knight_2", "false", "attack_red", "0", ""] + rift[3:]]
        a3 = [["black_wolf_knight_3", "false", "attack_red", "0", ""] + flag[3:]]
        existing = deepcopy(self.leader[:10])
        _a2, _a3, leaders = G.relocate(a2, a3, existing)
        self.assertEqual((_a2, _a3), ([], []))
        self.assertEqual(leaders, self.leader)

    def test_no_generator_source_writes_the_growth_cells(self):
        for name in ("wf_gerald_cast_growth.py", "wf_gerald_percent_skill.py", "wf_gerald_percent_revision.py"):
            source = (ROOT / "mod-tools" / name).read_text(encoding="utf-8")
            for word in ("leader_ability", "40000", "5000000"):
                self.assertNotIn(word, source, (name, word))

    def test_no_generator_writes_the_ability1_panel(self):
        """能力1 覆盖串没有生成器（只在候选包与 live）：mod-tools 顶层源码里只有本模块写它。"""
        writers = [path.name for path in (ROOT / "mod-tools").glob("*.py")
                   if "自身弱化效果无效" in path.read_text(encoding="utf-8", errors="ignore")]
        self.assertEqual(sorted(writers), ["wf_balance_20260927c_gerald_wolf.py"])


@unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                     and (ROOT / "mod-tools/profiles.json").is_file(),
                     "local candidate workspace required")
class CandidateTests(unittest.TestCase):
    ACTION_TABLE = "master/skill/action_skill.orderedmap"
    TEXT_TABLE = "master/character/character_text.orderedmap"
    SERVER = "cdndata/character_text.json"

    def test_candidate_splices_only_the_leader_panel_and_skill_text_keys_dry(self):
        import wf_mod_tool as C
        import wf_share_update_codec as X
        from wf_character_revision import RevisionCandidate
        inputs, _ = load()
        out = M.revise(reader(deepcopy(inputs)))
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        current = version(json.loads(before)["package_version"])
        mine = M.PACKAGE_VERSION[M.PACKAGES[0]]
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                      snapshot_key="revision_20260927c_growth", package_version=mine,
                                      reviewed_input_drift=M.REVIEWED_DRIFT,
                                      baseline_factory=lambda *a, **k: None)
        old_table = X.unpack(candidate.read("common", LEADER_TABLE))
        old_cas = X.unpack(candidate.read("common", CAS_TABLE))
        old_text = X.unpack(candidate.read("common", self.TEXT_TABLE))
        old_action = X.unpack(candidate.read("common", self.ACTION_TABLE))
        cand = X.csv_read(old_table[M.CID])
        state = out if cand == out["leader"][M.CID] else inputs
        if state is out:
            self.assertGreaterEqual(current, version(mine))          # 已回写：候选 = 本轮输出
        else:
            self.assertEqual(cand, inputs["leader"][M.CID])          # 暂存前：候选 = live 输入
            self.assertGreater(version(mine), current)
        for key in (M.CAS_A1, M.CAS_FLAG):
            self.assertEqual(X.csv_read(old_cas[key]), state["cas"][key], key)
        self.assertEqual(X.csv_read(old_text[M.CID]), state["text"][M.CID])
        self.assertEqual(json.dumps(C.decode_action_skill_row(old_action[M.CODE]), ensure_ascii=False),
                         json.dumps(state["action"][M.CODE], ensure_ascii=False))
        candidate.splice(LEADER_TABLE, out["leader"])
        candidate.splice(CAS_TABLE, out["cas"])
        candidate.splice(self.TEXT_TABLE, out["text"])
        candidate.splice(self.ACTION_TABLE, {M.CODE: C.encode_action_skill_row(out["action"][M.CODE])},
                         codec="action_nested")
        candidate.server_character_row(self.SERVER, out["server_text"][M.CID])
        new_table = X.unpack(candidate.read("common", LEADER_TABLE))
        self.assertEqual(X.csv_read(new_table[M.CID]), out["leader"][M.CID])
        self.assertEqual({k: v for k, v in old_table.items() if k != M.CID},
                         {k: v for k, v in new_table.items() if k != M.CID})
        new_cas = X.unpack(candidate.read("common", CAS_TABLE))
        for key in (M.CAS_A1, M.CAS_FLAG):
            self.assertEqual(X.csv_read(new_cas[key]), out["cas"][key], key)
        self.assertEqual({k: v for k, v in old_cas.items() if k not in (M.CAS_A1, M.CAS_FLAG)},
                         {k: v for k, v in new_cas.items() if k not in (M.CAS_A1, M.CAS_FLAG)})
        new_text = X.unpack(candidate.read("common", self.TEXT_TABLE))
        self.assertEqual(X.csv_read(new_text[M.CID]), out["text"][M.CID])
        self.assertEqual({k: v for k, v in old_text.items() if k != M.CID},
                         {k: v for k, v in new_text.items() if k != M.CID})
        server = json.loads(candidate.read("server", self.SERVER))[M.CID]
        self.assertEqual(server, out["server_text"][M.CID])
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertEqual(sorted((f["root"], f["logical_path"]) for f in evidence["changed_files"]),
                         sorted([("common", LEADER_TABLE), ("common", CAS_TABLE), ("common", self.TEXT_TABLE),
                                 ("common", self.ACTION_TABLE), ("server", self.SERVER)]))
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
