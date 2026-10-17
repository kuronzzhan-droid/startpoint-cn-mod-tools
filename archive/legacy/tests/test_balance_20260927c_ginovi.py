# -*- coding: utf-8 -*-
"""基诺维 169999 ``ginovi`` 2026-09-27 平衡第三轮（c，成长复核）：贯穿成长每跳 2.5% → 20%；
队长面板第 3 行按数据条件拆两行（口径 5 扩展，主会话追加 B；拆行依据 = 能力1 422 行 vs 队长 #5 疾走行）。

fixture = live 1.4.1053 输入快照（``fixtures/balance_20260927c_ginovi.json``，make_read(live_only=True)；
能力1 ``1699991`` 为拆行依据后补，1.4.1054 与 1.4.1053 逐字相同），
驱动 ``revise()``：每处改动前后值、未改行/未改面板行逐字保留、数值按「原值 × 2/3 向上取 5 的倍数」、
fixture 就是第二批输出（b → c 链）、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、合法性门禁、面板规则、
生成器输出 == revise() 输出（接管第二批测试的成长/面板一致性断言）、候选干跑。
**不跑** ``build_workspace.py build``/``kit-v3``（会写包）；队长行对比需要 live store 与 ``.cdn/cn``（缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_ginovi as B  # noqa: E402
import wf_balance_20260927c_ginovi as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
from wf_panel_merge_check import check as panel_merge_check  # noqa: E402  面板合并校验器（仓库内，硬依赖）

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_ginovi.json'
B_FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_ginovi.json'
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
BUILD_SCRIPT = WORKSPACE / "build_workspace.py"
CANDIDATE_CAPABILITIES = {"dash-parameter-v1", "panel-description-override-v2"}


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


def load_fixture() -> dict:
    return load(FIXTURE)


def reader(data: dict):
    def read(kind, key):
        return data[kind][key if isinstance(key, str) else "|".join(key)]
    return read


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


def load_generator():
    spec = importlib.util.spec_from_file_location("ginovi_build_workspace_c", BUILD_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old_leader = cls.live["leader"][M.LEADER]
        cls.new_leader = cls.out["leader"][M.LEADER]

    # ---------------------------------------------------------------- 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys}, set(M.BEFORE))

    def test_fixture_is_the_batch2_output(self):
        """b → c 链：本轮 live 输入 == 第二批模块对其快照的输出（1.4.1051 已发布；kit-v3 重建未改 live 行字节）。"""
        b_fixture = load(B_FIXTURE)
        b_out = B.revise(reader(b_fixture))
        self.assertEqual(self.old_leader, b_out["leader"][B.LEADER])
        self.assertEqual(self.live["cas"][M.CAS_LEADER], b_out["cas"][B.CAS_LEADER])
        for key in M.CAS_INVOKE:
            self.assertEqual(self.live["cas"][key], b_fixture["cas"][key], key)
        self.assertEqual((B.OLD_TICK, B.NEW_TICK), (M.ORIGINAL_TICK, M.OLD_TICK))
        self.assertEqual(B.NEW_PANEL_LINE, M.OLD_PANEL_LINE)
        self.assertEqual(B.PIERCING_ROWS, M.PIERCING_ROWS)

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), ("169999", "ginovi"))
        self.assertEqual(M.PACKAGES, ["ginovi"])
        self.assertEqual(M.PACKAGE_VERSION, {"ginovi": "0.3.2"})   # 候选现值 0.3.1，只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertEqual(M.ELEMENT, 5)
        self.assertFalse(self.out["notes"]["runtime_verified"])
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["leader"]), {M.LEADER})
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER, M.CAS_FLAG, M.CAS_A1})      # + 技能强化文案（R2）
        for kind in ("ability", "text", "table", "action", "dsl", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        self.assertTrue(M.CAS_LEADER.startswith("desc_override_" + M.CODE))
        self.assertTrue(M.CAS_A1.startswith("desc_override_" + M.CODE))
        self.assertTrue(M.CAS_FLAG.startswith("change_skill_" + M.CODE))

    # ---------------------------------------------------------------- 成长

    def test_leader_only_tick_cells_change(self):
        self.assertEqual((len(self.old_leader), len(self.new_leader)), (11, 11))
        changed = {(i, c): (a, b)
                   for i, (old, new) in enumerate(zip(self.old_leader, self.new_leader))
                   for c, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(changed, {(i, c): ("2500", "20000") for i in (6, 7, 8) for c in (49, 50)})
        self.assertTrue(all(len(r) == 124 for r in self.new_leader))

    def test_tick_rows_keep_trigger_gate_and_stay_unlimited(self):
        for index, kind in ((6, "32"), (7, "34"), (8, "388")):
            row = self.new_leader[index]
            with self.subTest(row=index):
                self.assertEqual((row[4], row[7], row[9]), ("2", "600000", "Black"))    # 暗共鸣
                self.assertEqual((row[25], row[26]), ("235", "0"))                      # 保持贯穿
                self.assertEqual((row[28], row[30]), ("100000", "9000000"))             # 每 90 帧一跳
                self.assertEqual((row[32], row[33]), ("(None)", "0"))                   # 仍不限次、无 CT
                self.assertEqual((row[45], row[46], row[47]), (kind, "5", "Black"))     # 暗队
                self.assertEqual(int(row[49]) / 1000, 20)                               # +20%

    def test_values_follow_the_two_thirds_floor(self):
        """25×2/3=16.7：15 实际 0.6 低于下限；不低于 2/3 的最小 5 的倍数是 20（D1：不用 17.5）。"""
        original, value = int(M.ORIGINAL_TICK), int(M.NEW_TICK)
        self.assertEqual(value % 5000, 0)
        self.assertGreaterEqual(Fraction(value, original), Fraction(2, 3))
        self.assertLess(value - 5000, original * Fraction(2, 3))
        self.assertEqual(value // 1000 * M.THREE_MIN_TICKS, 1680)               # 3 分钟 84 跳

    def test_auto_describe_readback(self):
        names = {6: "攻击力", 7: "技能伤害", 8: "能力伤害"}
        for index, name in names.items():
            self.assertEqual(D.describe_line(self.new_leader[index], "leader_ability"),
                             f"暗·编成≥6 时: 状态KeepFrame贯通≥1 → 赋予全队(暗) {name} 20%")

    def test_other_rows_are_byte_identical(self):
        for index in (0, 1, 2, 3, 4, 5, 9, 10):
            self.assertEqual(self.new_leader[index], self.old_leader[index], index)

    def test_panel_changes_only_the_piercing_and_split_lines(self):
        old = self.live["cas"][M.CAS_LEADER][0][0].split("\n")
        new = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual((len(old), len(new)), (6, 7))                      # 第 3 行拆两行
        self.assertEqual(new[:2], old[:2])
        self.assertEqual(old[2], "常态冲刺冷却时间延长，冲刺效果强化；暗属性共鸣时，弹射后冲刺冷却时间缩短（3秒）")
        self.assertEqual(new[2:4], ["常态冲刺冷却时间延长，冲刺效果强化", "暗属性共鸣时，弹射后冲刺冷却时间缩短（3秒）"])
        self.assertEqual("；".join(new[2:4]), old[2])                        # 只按「；」拆，文字逐字不改
        self.assertEqual(new[4], "暗属性共鸣时，自身每保持贯穿效果1.5秒，暗属性角色攻击力＋20%、技能伤害＋20%、能力伤害＋20%")
        self.assertEqual(old[3], M.OLD_PANEL_LINE)
        self.assertEqual(new[5:], old[4:])
        self.assertEqual((len(self.out["cas"][M.CAS_LEADER]), len(self.out["cas"][M.CAS_LEADER][0])), (1, 1))

    def test_panel_agrees_with_the_data(self):
        line = self.out["cas"][M.CAS_LEADER][0][0].split("\n")[M.PANEL_LINE]
        self.assertEqual(M.PANEL_LINE, 4)
        self.assertEqual(line.count("＋20%"), 3)
        self.assertEqual(M.panel_percent(line), int(self.new_leader[6][49]) / 1000)
        self.assertIn("1.5秒", line)
        self.assertEqual(int(self.new_leader[6][30]) // 100000, 90)

    def test_dash_line_is_split_by_data_condition(self):
        """口径 5 扩展（主会话追加 B）：前半行 = 能力1 #2–#7（422，前置 42 仅队长、无共鸣），后半行 = 队长 #5
        （暗共鸣 + 弹射 → 31 疾走 180 帧）⇒ 两种数据条件，拆两行；前半行无前缀，后半行保留「暗属性共鸣时，」。"""
        ability = self.live["ability"][M.DASH_ABILITY]
        self.assertEqual(M.split_basis_problems(ability, self.old_leader), [])
        self.assertEqual(M.split_basis_problems(ability, self.new_leader), [])     # 本轮只改 #6–#8 的 c49/c50
        self.assertEqual({i: ability[i][118] for i in M.DASH_PARAM_ROWS}, M.DASH_PARAM_ROWS)
        self.assertEqual({ability[i][109] for i in M.DASH_PARAM_ROWS}, {"422"})
        self.assertEqual({ability[i][6] for i in M.DASH_PARAM_ROWS}, {"42"})
        self.assertEqual((ability[7][97], ability[7][113]), ("34", "11667"))       # 疾走中冷却补偿，同样仅队长
        swift = self.old_leader[M.SWIFT_ROW]
        self.assertEqual((swift[4], swift[7], swift[9], swift[25], swift[45], swift[55]),
                         ("2", "600000", "Black", "6", "31", "18000000"))
        self.assertNotIn("共鸣", M.SPLIT_LINES[0])
        self.assertTrue(M.SPLIT_LINES[1].startswith("暗属性共鸣时，"))
        # 反例：前半行的数据带上共鸣 / 后半行失去共鸣 / 疾走改帧数 / 422 换 param ⇒ 依据失效（revise 拒绝）
        def resonant(rows):
            rows[3][6], rows[3][9], rows[3][11] = "2", "600000", "Black"
        for target, mutate in (("ability", resonant),
                               ("leader", lambda rows: rows[M.SWIFT_ROW].__setitem__(4, "0")),
                               ("leader", lambda rows: rows[M.SWIFT_ROW].__setitem__(55, "24000000")),
                               ("leader", lambda rows: rows[M.SWIFT_ROW].__setitem__(45, "32")),
                               ("ability", lambda rows: rows[6].__setitem__(113, "-50000")),
                               ("ability", lambda rows: rows[2].__setitem__(118, "2")),
                               ("ability", lambda rows: rows.pop())):
            a, l = deepcopy(ability), deepcopy(self.old_leader)
            mutate(a if target == "ability" else l)
            with self.subTest(target=target):
                self.assertTrue(M.split_basis_problems(a, l))

    def test_panel_merge_checker_accepts_the_registered_rewrite(self):
        """面板合并校验器（wf_panel_merge_check，硬依赖）：原文先按「数值同步 → 口径 5 拆行」显式规范化，再与输出比对
        （逐行 verbatim、行序不变、数值多重集合不变）；未登记拆行时校验器必须报错。"""
        old = self.live["cas"][M.CAS_LEADER][0][0].split("\n")
        numbers = old[:M.OLD_PANEL_LINE_INDEX] + [M.NEW_PANEL_LINE] + old[M.OLD_PANEL_LINE_INDEX + 1:]
        split = numbers[:M.PANEL_SPLIT_LINE] + list(M.SPLIT_LINES) + numbers[M.PANEL_SPLIT_LINE + 1:]
        out = self.out["cas"][M.CAS_LEADER][0][0]
        result = panel_merge_check("\n".join(split), out, prefix_drops=[])
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(set(result["columns"][0]["kinds"].values()), {"verbatim"})
        self.assertFalse(panel_merge_check("\n".join(numbers), out)["ok"])

    def test_panel_text_obeys_the_project_rules(self):
        text = self.out["cas"][M.CAS_LEADER][0][0]
        self.assertEqual(KL.panel_problems(text), [])
        for word in ("可无限", "无上限", "无限叠加", "不设上限", "自身为队长时", "生命值100%以下", "／",
                     "/", "共鸣时：", "共鸣时:", "、强化弹射伤害", "迟缓", "&", "＆"):
            self.assertNotIn(word, text, word)
        # 口径 5：每行只有一种数据条件（「；」不再把两种条件挤在一行）
        self.assertEqual([line for line in text.split("\n") if "；" in line and "共鸣时" in line.split("；", 1)[1]], [])
        self.assertEqual(L.required_client_capabilities("custom_ability_string", [M.CAS_LEADER, text]),
                         ["panel-description-override-v2"])

    def test_every_leader_row_passes_client_gates(self):
        cas_keys = {M.CAS_LEADER, *M.CAS_INVOKE}
        for index, row in enumerate(self.new_leader):
            with self.subTest(row=index):
                self.assertEqual(L.client_legality_problems("leader_ability", row), [])
                self.assertEqual(L.declared_block_field_problems("leader_ability", row), [])
                self.assertEqual(L.ability_element_column_problems("leader_ability", row, M.ELEMENT), [])
                self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, "leader_ability"), [])
                self.assertEqual(L.required_client_capabilities("leader_ability", row), [])
                self.assertEqual(M.leader_row_problems(row, cas_keys), [])

    # ---------------------------------------------------------------- fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        live = deepcopy(self.live)
        out = M.revise(reader(live))
        self.assertEqual(live, self.live)
        out["leader"][M.LEADER][6][49] = "x"
        out["cas"][M.CAS_LEADER][0][0] = "x"
        self.assertEqual(live, self.live)
        self.assertEqual(M.revise(reader(deepcopy(self.live)))["leader"], self.out["leader"])

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.live)
            drifted[kind][key][0][-1] = drifted[kind][key][0][-1] + "x"
            with self.subTest(kind=kind, key=key), self.assertRaisesRegex(M.GinoviBalanceError, "live drift"):
                M.revise(reader(drifted))
            missing = deepcopy(self.live)
            missing[kind][key] = None
            with self.assertRaises(M.GinoviBalanceError):
                M.revise(reader(missing))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        live = deepcopy(self.live)
        live["leader"].update(deepcopy(self.out["leader"]))
        live["cas"].update(deepcopy(self.out["cas"]))
        with self.assertRaisesRegex(M.GinoviBalanceError, "live drift"):
            M.revise(reader(live))
        with self.assertRaises(M.GinoviBalanceError):
            M.revise_leader(self.new_leader)
        with self.assertRaises(M.GinoviBalanceError):
            M.revise_panel(self.out["cas"][M.CAS_LEADER])

    def test_batch2_preimage_is_required(self):
        """第二批之前的 25%/面板不是本轮原像：跳过第二批直接套本轮必须拒绝。"""
        b_live = load(B_FIXTURE)
        with self.assertRaises(M.GinoviBalanceError):
            M.revise_leader(b_live["leader"][B.LEADER])
        with self.assertRaises(M.GinoviBalanceError):
            M.revise_panel(b_live["cas"][B.CAS_LEADER])

    def test_structure_guards(self):
        for mutate, pattern in ((lambda r: r[6].__setitem__(32, "10"), "235 piercing tick"),
                                (lambda r: r[7].__setitem__(4, "0"), "235 piercing tick"),
                                (lambda r: r[2].__setitem__(33, "600"), "629"),
                                (lambda r: r[0].__setitem__(45, "32"), "722"),
                                (lambda r: r.pop(), "expected")):
            rows = deepcopy(self.old_leader)
            mutate(rows)
            with self.assertRaisesRegex(M.GinoviBalanceError, pattern):
                M.revise_leader(rows)


class SkillEnhancementTextTests(unittest.TestCase):
    """作者「技能都强化效果只在队长技或者能力里面按照格式写,技能里面不要重复描述强化后的效果」（主会话口径 R1–R4）。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_flag_entry_is_qualitative_and_names_the_skill(self):
        old = self.live["cas"][M.CAS_FLAG][0][0]
        new = self.out["cas"][M.CAS_FLAG][0][0]
        self.assertEqual(old, M.OLD_FLAG_TEXT)
        self.assertEqual(new, "为『掠影协奏』追加「攻击力提升效果」「直接攻击分为多次」与「暗属性角色护盾提升＋最大速度固定效果」，"
                              "并对距离最近的敌人强制赋予不可消除的「死印」；首次发动时缔结血契，夺取全体参战成员的生命值"
                              "并为全体队员赋予护盾")
        self.assertEqual(M.flag_entry_problems(new), [])
        self.assertEqual(KL.panel_problems(new, skill_flag=True), [])
        self.assertTrue(KL.panel_problems(old, skill_flag=True))              # 旧文带数字
        self.assertFalse(any(ch.isdigit() for ch in new))
        # 内容不变：各效果名与血契后半句都在。
        for phrase in ("攻击力提升效果", "直接攻击", "护盾", "最大速度固定效果", "「死印」", "不可消除", "首次发动时缔结血契",
                       "夺取全体参战成员的生命值并为全体队员赋予护盾"):
            self.assertIn(phrase, new)

    def test_ability1_panel_line_is_the_same_entry(self):
        old = self.live["cas"][M.CAS_A1][0][0].split("\n")
        new = self.out["cas"][M.CAS_A1][0][0].split("\n")
        self.assertEqual((len(old), len(new)), (2, 2))
        self.assertEqual(new[0], old[0])
        self.assertEqual(new[1], "暗属性共鸣时，" + self.out["cas"][M.CAS_FLAG][0][0])
        for line in new:
            self.assertEqual(KL.panel_problems(line), [], line)
            self.assertNotIn("／", line)

    def test_basis_is_the_dark_resonance_536_row(self):
        rows = self.live["ability"][M.DASH_ABILITY]
        self.assertEqual(M.flag_basis_problems(rows), [])
        row = rows[M.FLAG_ROW]
        self.assertEqual((row[47], row[70], row[6], row[9], row[11]), ("536", M.CAS_FLAG, "2", "600000", "Black"))
        for mutate in (lambda r: r[M.FLAG_ROW].__setitem__(70, "x"), lambda r: r[M.FLAG_ROW].__setitem__(6, "0"),
                       lambda r: r[M.FLAG_ROW].__setitem__(47, "704")):
            data = deepcopy(rows)
            mutate(data)
            self.assertTrue(M.flag_basis_problems(data))

    def test_reapply_is_rejected(self):
        with self.assertRaises(M.GinoviBalanceError):
            M.revise_flag_texts(self.out["cas"][M.CAS_FLAG], self.live["cas"][M.CAS_A1])
        with self.assertRaises(M.GinoviBalanceError):
            M.revise_flag_texts(self.live["cas"][M.CAS_FLAG], self.out["cas"][M.CAS_A1])

    def test_skill_description_is_body_only(self):
        """R3：技能说明本来就只写本体（与强化条目不重叠），本轮不读不写。"""
        self.assertNotIn("text", self.out["notes"].get("changes", {}))
        self.assertEqual((self.out["action"], self.out["text"], self.out["server_text"]), ({}, {}, {}))


@unittest.skipUnless(BUILD_SCRIPT.is_file(), "需要基诺维生成器 build_workspace.py")
class GeneratorTests(unittest.TestCase):
    """生成器 build_workspace.py（kit-v3）重跑不能把 2.5% 带回来：纯函数输出 == revise() 输出。"""

    @classmethod
    def setUpClass(cls):
        cls.gen = load_generator()
        cls.out = M.revise(reader(load_fixture()))

    def test_generator_constants_equal_revise_output(self):
        gen = self.gen
        self.assertEqual(gen.PIERCING_BUFF, M.NEW_TICK)
        self.assertEqual(gen.PIERCING_TICK_FRAMES, M.TICK_FRAMES)
        self.assertEqual(gen.PIERCING_STACK_LIMIT, "(None)")
        # 第二批削韧常量不动
        self.assertEqual((gen.SKILL_AURA_DETOUGHNESS, gen.DASH_BLADE_DETOUGHNESS, gen.BLACKFEATHER_DETOUGHNESS),
                         (B.SKILL_SPEC[2], B.DASH_SPEC[2], B.PF_INVOKE_SPEC[1][2]))

    def test_generator_panel_equals_revise_output(self):
        text = "\n".join(self.gen.DESC_OVERRIDE_LINES[M.CAS_LEADER])
        self.assertEqual([[text]], self.out["cas"][M.CAS_LEADER])

    def test_generator_skill_flag_texts_equal_revise_output(self):
        """技能强化文案：生成器的条目常量与能力1 面板 == revise() 输出（write_custom_ability_strings 用这两处）。"""
        self.assertEqual([[self.gen.CHANGE_SKILL_TEXT]], self.out["cas"][M.CAS_FLAG])
        self.assertEqual([["\n".join(self.gen.DESC_OVERRIDE_LINES[M.CAS_A1])]], self.out["cas"][M.CAS_A1])
        self.assertEqual(self.gen.DESC_OVERRIDES[M.CAS_A1], self.out["cas"][M.CAS_A1][0][0])
        source = BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"change_skill_ginovi": CHANGE_SKILL_TEXT,', source)

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_leader_rows_equal_revise_output(self):
        """write_m3_leader_rows 的写表调用被拦截（不落影子表），只取它装配出的 11 行。"""
        gen = self.gen
        with mock.patch.object(gen.core, "write_table") as write_table:
            result = gen.write_m3_leader_rows()
        self.assertEqual(write_table.call_count, 1)
        self.assertEqual(Path(write_table.call_args[0][1]), Path(gen.SHADOW_STORE))
        self.assertEqual(result["rows"], self.out["leader"][M.LEADER])


@unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                     and (ROOT / "mod-tools/profiles.json").is_file(),
                     "local candidate workspace required")
class CandidateTests(unittest.TestCase):
    def test_candidate_accepts_the_revision_dry(self):
        import wf_share_update_codec as X
        from wf_character_revision import RevisionCandidate
        out = M.revise(reader(load_fixture()))
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        data = json.loads(before)
        self.assertEqual(set(data["required_capabilities"]), CANDIDATE_CAPABILITIES)
        version = tuple(map(int, M.PACKAGE_VERSION[M.PACKAGES[0]].split(".")))
        current = tuple(map(int, data["package_version"].split(".")))
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                      snapshot_key="revision_20260927c",
                                      package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                                      baseline_factory=lambda *a, **k: None, reviewed_input_drift=M.REVIEWED_DRIFT)
        if current >= version:
            # 主会话暂存回写后：候选 = live + 本修订。
            leader = X.unpack(candidate.read("common", "master/ability/leader_ability.orderedmap"))
            self.assertEqual(X.csv_read(leader[M.LEADER]), out["leader"][M.LEADER])
            cas = X.unpack(candidate.read("common", "master/string/custom_ability_string.orderedmap"))
            for key in out["cas"]:
                self.assertEqual(X.csv_read(cas[key]), out["cas"][key], key)
            self.assertEqual(before, manifest.read_bytes())
            return
        candidate.splice("master/ability/leader_ability.orderedmap", out["leader"])
        candidate.splice("master/string/custom_ability_string.orderedmap", out["cas"])
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertEqual(len(evidence["changed_files"]), 2)
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
