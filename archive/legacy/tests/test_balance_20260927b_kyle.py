# -*- coding: utf-8 -*-
"""凯尔 139990 ``kyle_moon`` 2026-09-27 平衡调整第二批（无上限成长 + Down）。

fixture = live 1.4.1049 输入快照（``fixtures/balance_20260927b_kyle.json``），驱动 ``revise()``：
每处改动的前后值、未改行/未改树节点逐字保留、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、
合法性门禁为空、DSL AMF3 往返与四道门禁、面板规则、生成器输出 == revise() 输出（需要 .cdn/cn 与
live store 的用 skipUnless）、与第一批输出首尾相接、设计镜像已同步。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927_kyle as M1  # noqa: E402
import wf_balance_20260927b_kyle as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kit_kyle as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_kit_philia as PH  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_kyle.json"
FIXTURE_BATCH1 = Path(__file__).parent / "fixtures/balance_20260927_kyle.json"
CANDIDATE = ROOT / "work/character_packs/ma-kyle"
TABLE_KIND = {"leader": "leader_ability", "ability": "ability"}


def load_fixture(path: Path = FIXTURE) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


def reader(data: dict):
    def read(kind, key):
        return data[kind][key]
    return read


def candidate_written_back() -> bool:
    """主会话暂存回写（snapshot revision_20260927b，package_version 升到模块版本）后为 True。"""
    manifest = json.loads((CANDIDATE / "package/manifest.json").read_text(encoding="utf-8"))
    return (manifest.get("snapshot", {}).get("revision_20260927b") is not None
            or manifest["package_version"] == M.PACKAGE_VERSION["ma-kyle"])


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


def _cna(tree) -> list[list]:
    return M.commands(tree, "CreateNormalAttack")


def _percent(value: str) -> float:
    return int(value) / 1000          # 100000 = 100%


def batch3_overlay(live: dict, out: dict) -> dict:
    """第二批输出 + 第三轮覆盖（wf_balance_20260927c_kyle：队长月牙/贯穿成长 4/5、队长面板、追击段数上限 99）。
    生成器现在产出的是两批依次施工后的结果（第三轮 BEFORE 锁定的正是第二批输出，见其 ChainTests），
    第二批的生成器一致性断言改比这份叠加结果；第三轮没碰的键仍直接等于第二批输出。"""
    import wf_balance_20260927c_kyle as M3
    live3 = deepcopy(live)
    for kind in ("leader", "ability", "cas", "dsl"):
        live3[kind].update(deepcopy(out[kind]))
    # 第三轮面板合并补读、第二批不涉及的键（desc_override_kyle_moon_3）取第三轮 fixture（= live）
    fixture3 = json.loads((Path(__file__).parent / "fixtures/balance_20260927c_kyle.json").read_text(encoding="utf-8"))
    for kind, key in M3.BEFORE:
        live3.setdefault(kind, {}).setdefault(key, deepcopy(fixture3[kind][key]))
    out3 = M3.revise(reader(live3))
    merged = deepcopy(out)
    for kind in ("leader", "ability", "cas", "dsl"):
        merged[kind].update(deepcopy(out3[kind]))
    return merged


def batch3_written_back() -> bool:
    """第三轮已由主会话回写候选（package_version 升到第三轮模块版本）。"""
    import wf_balance_20260927c_kyle as M3
    manifest = json.loads((CANDIDATE / "package/manifest.json").read_text(encoding="utf-8"))
    as_tuple = lambda v: tuple(int(x) for x in v.split("."))  # noqa: E731
    return as_tuple(manifest["package_version"]) >= as_tuple(M3.PACKAGE_VERSION["ma-kyle"])


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         set(M.BEFORE))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (str(K.CID), K.CODE))
        self.assertEqual(M.PACKAGES, ["ma-kyle"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-kyle": "1.0.3"})
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})

    @unittest.skipUnless((CANDIDATE / "package/manifest.json").is_file(), "candidate ma-kyle missing")
    def test_package_version_moves_forward(self):
        manifest = json.loads((CANDIDATE / "package/manifest.json").read_text(encoding="utf-8"))
        current = tuple(int(x) for x in manifest["package_version"].split("."))
        new = tuple(int(x) for x in M.PACKAGE_VERSION["ma-kyle"].split("."))
        if candidate_written_back():
            # 已回写：候选现值 == 本模块版本；第三轮（wf_balance_20260927c_kyle）回写后候选再升号 ⇒ ≤。
            self.assertIsNotNone(manifest["snapshot"].get("revision_20260927b"))
            self.assertLessEqual(new, current)
        else:
            self.assertGreater(new, current)
        self.assertTrue(set(M.CAPABILITIES) <= set(manifest["required_capabilities"]))

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["leader"]), {M.CID})
        self.assertEqual(set(out["ability"]), {M.ABILITY2})           # 1399903 只读核对，不返回
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER, M.CAS_ABILITY2})
        self.assertEqual(set(out["dsl"]), {M.PIERCE_PROGRAM, M.THUNDER_PROGRAM, *M.SKILL_PROGRAMS.values()})
        for kind in ("text", "table", "action", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)
        for key in out["cas"]:   # RevisionCandidate 命名空间
            self.assertTrue(key.startswith("desc_override_" + M.CODE), key)
        for kind in ("leader", "ability", "cas", "dsl"):
            for key, value in out[kind].items():
                self.assertNotEqual(value, self.live[kind][key], f"{kind}:{key} returned but unchanged")

    def test_charge_rows_are_not_touched(self):
        """口径 A6：kind 35 充能 / 245 槽上限不动 —— 能力5 不在输出里，队长 #4/#5 逐字不变。"""
        self.assertNotIn(f"{M.CID}5", self.out["ability"])
        old, new = self.live["leader"][M.CID], self.out["leader"][M.CID]
        self.assertEqual([r[45] for r in new[4:6]], ["245", "35"])
        self.assertEqual(new[4:6], old[4:6])
        self.assertEqual(new[8], old[8])                               # 722 特殊强化弹射


class LeaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old, cls.new = cls.live["leader"][M.CID], cls.out["leader"][M.CID]

    def test_row_count_and_width_are_kept(self):
        self.assertEqual((len(self.old), len(self.new)), (9, 9))
        self.assertTrue(all(len(r) == 124 for r in self.new))

    def test_every_edit_before_and_after(self):
        want = {0: (111, "12500", "1250"), 1: (111, "12500", "6250"), 2: (111, "25000", "7500"),
                3: (111, "25000", "2500"), 6: (49, "25000", "2500"), 7: (49, "5000", "500")}
        for index, (col, before, after) in want.items():
            self.assertEqual(self.old[index][col:col + 2], [before, before], f"leader#{index}")
            self.assertEqual(self.new[index][col:col + 2], [after, after], f"leader#{index}")
            diff = [c for c, (a, b) in enumerate(zip(self.old[index], self.new[index])) if a != b]
            self.assertEqual(diff, [col, col + 1], f"leader#{index} touched other cells")
        for index in (4, 5, 8):
            self.assertEqual(self.new[index], self.old[index], f"leader#{index}")

    def test_slowdown_is_one_tenth_plus_the_merged_ability_rows(self):
        ability = self.live["ability"][M.ABILITY2]
        for index in (0, 3):
            self.assertEqual(int(self.new[index][111]) * 10, int(self.old[index][111]))
        for index in (6, 7):
            self.assertEqual(int(self.new[index][49]) * 10, int(self.old[index][49]))
        # 合并：#1 ← 能力2#1（自身攻击），#2 ← 能力2#0（雷队直击），各 /10 相加
        self.assertEqual(int(self.new[1][111]), int(self.old[1][111]) // 10 + int(ability[1][113]) // 10)
        self.assertEqual(int(self.new[2][111]), int(self.old[2][111]) // 10 + int(ability[0][113]) // 10)

    def test_merged_ability_rows_share_trigger_kind_target_and_preconditions(self):
        ability = self.live["ability"][M.ABILITY2]
        for leader_index, ability_index in ((1, 1), (2, 0)):
            moved = M.moved_row(ability[ability_index])
            row = self.old[leader_index]
            self.assertEqual(len(moved), 124)
            self.assertEqual(moved[:111] + moved[113:], row[:111] + row[113:])

    def test_growth_rows_keep_their_trigger_and_unlimited_limit(self):
        for row in self.new[:4]:
            self.assertEqual((row[95], row[100], row[102]), ("134", "(None)", M.UID_CRESCENT))
        for row in self.new[6:8]:
            self.assertEqual((row[25], row[32], row[33]), ("51", "(None)", "0"))

    def test_rows_that_are_not_mergeable_are_rejected(self):
        ability = deepcopy(self.live["ability"][M.ABILITY2])
        ability[0][110] = "0"                  # 目标改成自身 ⇒ 与队长 #2（全队雷）不同目标
        with self.assertRaisesRegex(M.KyleBalanceError, "not mergeable"):
            M.leader_rows(self.old, ability)

    def test_row_locators_are_content_based(self):
        moved = deepcopy(self.old)
        moved[0], moved[1] = moved[1], moved[0]
        with self.assertRaises(M.KyleBalanceError):
            M.leader_rows(moved, self.live["ability"][M.ABILITY2])
        changed = deepcopy(self.old)
        changed[6][49] = changed[6][50] = "30000"
        with self.assertRaises(M.KyleBalanceError):
            M.leader_rows(changed, self.live["ability"][M.ABILITY2])


class AbilityTwoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old, cls.new = cls.live["ability"][M.ABILITY2], cls.out["ability"][M.ABILITY2]

    def test_capped_weak_version_before_and_after(self):
        want = {0: ("1", "5", "Yellow", "50000", "10000"), 1: ("0", "0", "", "50000", "16000")}
        for index, (kind, target, element, before, after) in want.items():
            old, new = self.old[index], self.new[index]
            self.assertEqual((new[97], new[109], new[110], new[111]), ("134", kind, target, element))
            self.assertEqual((old[102], new[102]), ("(None)", "10"))
            self.assertEqual(old[113:115], [before, before])
            self.assertEqual(new[113:115], [after, after])
            diff = [c for c, (a, b) in enumerate(zip(old, new)) if a != b]
            self.assertEqual(diff, [102, 113, 114], f"1399902#{index}")

    def test_full_stack_values_land_in_the_official_bands(self):
        """满 10 层：雷队直击 +100%（官方持续带 100–200%）、自身攻击 +160%（官方自身攻持续 160%）。"""
        self.assertEqual(int(self.new[0][113]) * int(self.new[0][102]), 100000)
        self.assertEqual(int(self.new[1][113]) * int(self.new[1][102]), 160000)

    def test_slot_stays_main_only_and_thunder_resonance_gated(self):
        for row in self.new:
            self.assertEqual((row[1], row[6], row[9], row[11]), ("false", "2", "600000", "Yellow"))


class PanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_leader_panel_text(self):
        old = self.live["cas"][M.CAS_LEADER][0][0].split("\n")
        new = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertEqual((len(old), len(new)), (6, 7))
        self.assertEqual(new[:3], old[:3])
        self.assertEqual(new[-1], old[-1])                          # 充能行（口径 A6）不动
        self.assertEqual(new[3], "雷属性共鸣时：自身“月牙”每上升1层，自身攻击力＋7.5%、直击伤害＋10%；"
                                 "除自身外雷属性角色攻击力＋1.25%、直击伤害＋7.5%")
        self.assertEqual(new[4], "雷属性共鸣时：自身“月牙”每上升1层，自身直击判定次数＋1（最多10层）")
        self.assertEqual(new[5], "雷属性共鸣时：自身每获得一次贯穿效果，雷属性角色攻击力＋2.5%、追击伤害＋0.5%")

    def test_leader_panel_numbers_equal_the_rows(self):
        rows = self.out["leader"][M.CID]
        share = {(r[107], r[108]): _percent(r[111]) for r in rows if r[95] == "134"}
        self_attack = share[("0", "5")] + share[("0", "0")]
        self_direct = share[("1", "5")] + share[("1", "0")]
        line = self.out["cas"][M.CAS_LEADER][0][0].split("\n")[3]
        self.assertIn(f"自身攻击力＋{self_attack:g}%", line)
        self.assertIn(f"直击伤害＋{self_direct:g}%", line)
        self.assertIn(f"除自身外雷属性角色攻击力＋{share[('0', '5')]:g}%", line)
        self.assertIn(f"直击伤害＋{share[('1', '5')]:g}%", line.split("；")[1])
        pierce = {r[45]: _percent(r[49]) for r in rows if r[25] == "51"}
        line = self.out["cas"][M.CAS_LEADER][0][0].split("\n")[5]
        self.assertIn(f"攻击力＋{pierce['32']:g}%", line)
        self.assertIn(f"追击伤害＋{pierce['53']:g}%", line)
        cap = self.out["dsl"][M.PIERCE_PROGRAM][11][1][0][1][5]
        self.assertIn(f"（最多{cap}层）", self.out["cas"][M.CAS_LEADER][0][0].split("\n")[4])

    def test_ability2_panel_text_equals_the_rows(self):
        text = self.out["cas"][M.CAS_ABILITY2][0][0]
        self.assertEqual(text, M.MAIN_ICON + "雷属性共鸣时：自身“月牙”每提升1层，自身攻击力＋16%、"
                                             "雷属性角色直击伤害＋10%（最多10层）")
        rows = self.out["ability"][M.ABILITY2]
        self.assertIn(f"攻击力＋{_percent(rows[1][113]):g}%", text)
        self.assertIn(f"直击伤害＋{_percent(rows[0][113]):g}%", text)
        self.assertIn(f"（最多{rows[0][102]}层）", text)

    def test_panel_texts_obey_the_project_rules(self):
        for key, rows in self.out["cas"].items():
            text = rows[0][0]
            self.assertNotIn("／", text)
            self.assertNotIn("Ⓜ", text)
            for line in text.split("\n"):
                self.assertEqual(KL.panel_problems(line.replace(M.MAIN_ICON, "")), [], f"{key}: {line}")
                # 主位限制槽（能力2 整键 c1=false）每行带图标；队长块不带
                self.assertEqual(line.startswith(M.MAIN_ICON), key == M.CAS_ABILITY2, line)
            for word in ("可无限", "无上限", "无限叠加", "不设上限", "自身为队长时", "觉醒后", "生命值100%以下"):
                self.assertNotIn(word, text)
            self.assertFalse(re.search(r"\d+(\.\d+)?%（觉醒", text))


class DslTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def old(self, program):
        return self.live["dsl"][program]

    def new(self, program):
        return self.out["dsl"][program]

    def test_pierce_growth_is_capped_at_ten_layers(self):
        old, new = self.old(M.PIERCE_PROGRAM), self.new(M.PIERCE_PROGRAM)
        self.assertEqual(old[11][1][0][1], ["BindConditionAccumulationVariable", -17, 1,
                                            ["DCUnique", int(M.UID_CRESCENT)], 1, 99])
        self.assertEqual(new[11][1][0][1], ["BindConditionAccumulationVariable", -17, 1,
                                            ["DCUnique", int(M.UID_CRESCENT)], 1, 10])
        # 段数 = 1 + vlv（每层 +1）不变；只改变量上限
        self.assertEqual(new[11][1][1][1][2][0][2], M.PIERCE_TIMES)
        reverted = deepcopy(new)
        reverted[11][1][0][1][5] = 99
        self.assertEqual(reverted, old)

    def test_thunder_detoughness_before_and_after(self):
        old, new = self.old(M.THUNDER_PROGRAM), self.new(M.THUNDER_PROGRAM)
        flag_old = M.commands(old, "ConditionalsChangeSkillFlag")[0]
        flag_new = M.commands(new, "ConditionalsChangeSkillFlag")[0]
        for slot, name, before, after in ((2, "boost", 3.6, 0.2), (3, "normal", 20, 1)):
            self.assertEqual(_cna(flag_old[slot])[0][13], [{"min": before, "max": before}], name)
            self.assertEqual(_cna(flag_new[slot])[0][13], [{"min": after, "max": after}], name)
            self.assertLessEqual(M.detoughness_per_cast(["Command", ["Probe", flag_new[slot]]]), 1.0 + 1e-9)
        self.assertEqual(M.detoughness_per_cast(old), 20.0)
        self.assertAlmostEqual(M.detoughness_per_cast(new), 1.0)
        reverted = deepcopy(new)
        flag = M.commands(reverted, "ConditionalsChangeSkillFlag")[0]
        _cna(flag[2])[0][13] = [{"min": 3.6, "max": 3.6}]
        _cna(flag[3])[0][13] = [{"min": 20, "max": 20}]
        self.assertEqual(reverted, old)

    def test_thunder_is_a_cooltime_three_second_invoke(self):
        """CT ≤3 秒的 629 每次 ≤1（口径 B3）—— 按 live 能力3 行核对 CT。"""
        checks = M.ability3_checks(self.live["ability"][M.ABILITY3])
        self.assertEqual(checks["thunder_cooltime_frames"], 180)
        self.assertLessEqual(checks["thunder_cooltime_frames"] / 60, 3)
        rows = deepcopy(self.live["ability"][M.ABILITY3])
        next(r for r in rows if r[70] == M.CAS_THUNDER)[35] = "240"
        with self.assertRaises(M.KyleBalanceError):
            M.ability3_checks(rows)
        rows = deepcopy(self.live["ability"][M.ABILITY3])
        next(r for r in rows if r[70] == M.CAS_PIERCE)[6] = "0"      # 段数 629 不再仅队长
        with self.assertRaises(M.KyleBalanceError):
            M.ability3_checks(rows)

    def test_skill_detoughness_before_and_after(self):
        for level, program in M.SKILL_PROGRAMS.items():
            old, new = self.old(program), self.new(program)
            self.assertEqual([a[13][0]["max"] for a in _cna(old)], [10, 1, 12], level)
            self.assertEqual([a[13] for a in _cna(new)],
                             [[{"min": 8, "max": 8}], [{"min": 1, "max": 1}], [{"min": 8, "max": 8}]], level)
            self.assertEqual([a[14] for a in _cna(new)], [a[14] for a in _cna(old)], "Fever 点不动")
            self.assertEqual(M.detoughness_per_cast(old), 36.0, level)
            self.assertEqual(M.detoughness_per_cast(new), 30.0, level)
            reverted = deepcopy(new)
            for attack, value in zip(_cna(reverted), (10, 1, 12)):
                attack[13] = [{"min": value, "max": value}]
            self.assertEqual(reverted, old, level)

    def test_command_counts_are_unchanged(self):
        for program, tree in self.out["dsl"].items():
            count = lambda t: sorted(body[0] for body in M.commands(t))  # noqa: E731
            self.assertEqual(count(tree), count(self.old(program)), program)

    def test_trees_pass_the_dsl_gates_and_roundtrip(self):
        for program, tree in self.out["dsl"].items():
            self.assertEqual(M.dsl_problems(tree), [], program)
            self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [], program)
            self.assertEqual(L.action_dsl_subject_binding_problems(tree), [], program)
            self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [], program)
            self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [], program)
            self.assertEqual(PH.signature_problems(tree), [], program)     # 参数个数 = 官方签名
            self.assertEqual(PH.expr_tag_problems(tree), [], program)      # 表达式外壳
            raw = encode_tree(tree)                                        # AMF3 往返不一致会抛
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], tree)
            self.assertEqual(K._dsl_problems(tree), [], program)           # 生成器落盘门禁（含方向/坐标系）

    def test_structure_guards_reject_their_own_output(self):
        with self.assertRaises(M.KyleBalanceError):
            M.pierce_tree(self.new(M.PIERCE_PROGRAM))
        with self.assertRaises(M.KyleBalanceError):
            M.thunder_tree(self.new(M.THUNDER_PROGRAM))
        for level, program in M.SKILL_PROGRAMS.items():
            with self.assertRaises(M.KyleBalanceError):
                M.skill_tree(self.new(program), level)

    def test_hit_count_drift_is_rejected(self):
        tree = deepcopy(self.old(M.THUNDER_PROGRAM))
        flag = M.commands(tree, "ConditionalsChangeSkillFlag")[0]
        M.commands(flag[2], "CreateHitArea")[0][15] = ["Some", [{"min": 6, "max": 6}]]
        M.commands(flag[2], "CreateHitArea")[0][14] = ["CalculatedUsingMaxNumOfHits", 6]
        with self.assertRaises(M.KyleBalanceError):
            M.thunder_tree(tree)
        tree = deepcopy(self.old(M.SKILL_PROGRAMS["1"]))
        M.commands(tree, "CreateHitArea")[1][14] = ["CalculatedUsingMaxNumOfHits", 20]
        with self.assertRaises(M.KyleBalanceError):
            M.skill_tree(tree, "1")


class GateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_native_legality_gates_are_empty(self):
        cas_keys = set(K.CAS_TEXTS)
        for kind in ("leader", "ability"):
            table = TABLE_KIND[kind]
            for key, rows in self.out[kind].items():
                for index, row in enumerate(rows):
                    label = f"{kind}:{key}#{index}"
                    self.assertEqual(L.client_legality_problems(table, row), [], label)
                    self.assertEqual(L.declared_block_field_problems(table, row), [], label)
                    self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, kind=table), [], label)
                    self.assertEqual(KL.row_problems(table, row, K.ELEMENT), {}, label)
                    self.assertEqual(M.row_problems(table, row), [], label)

    def test_changed_rows_render_the_baked_describe(self):
        # 队长 #0–#3/#6/#7 的 EXPECT 已随第三轮（wf_balance_20260927c_kyle）改为 4/5 值 ⇒ 比第二批 + 第三轮叠加结果
        leader = batch3_overlay(self.live, self.out)["leader"][M.CID]
        for index in (0, 1, 2, 3, 6, 7):
            self.assertEqual(KL.describe("leader_ability", leader[index]), K.EXPECT[f"leader#{index}"])
        for index, row in enumerate(self.out["ability"][M.ABILITY2]):
            self.assertEqual(KL.describe("ability", row), K.EXPECT[f"{M.ABILITY2}#{index}"])
            self.assertIn("(限10次)", K.EXPECT[f"{M.ABILITY2}#{index}"])

    def test_leader_table_keeps_to_vetted_kinds(self):
        """队长表不新增行、不引入零先例 kind（C7050）：kind 集合与输入相同。"""
        kinds = lambda rows: sorted((r[25], r[45], r[95], r[107]) for r in rows)  # noqa: E731
        self.assertEqual(kinds(self.out["leader"][M.CID]), kinds(self.live["leader"][M.CID]))
        K._ban_kinds("leader_ability", self.out["leader"][M.CID], "leader")
        K._ban_kinds("ability", self.out["ability"][M.ABILITY2], M.ABILITY2)


class SafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["leader"][M.CID][0][0] = "mutated"
        out["ability"][M.ABILITY2][0][0] = "mutated"
        M.commands(out["dsl"][M.PIERCE_PROGRAM])[0][1] = 0
        self.assertEqual(data, self.live)

    def test_revise_is_deterministic(self):
        self.assertEqual(M.revise(reader(deepcopy(self.live))), self.out)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.live)
            if kind == "cas":
                data[kind][key][0][0] += "。"
            elif kind == "dsl":
                data[kind][key][1] = 1
            else:
                data[kind][key][-1][1] = "drift"
            with self.assertRaisesRegex(M.KyleBalanceError, "unreviewed live baseline"):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        for kind in ("leader", "ability", "cas", "dsl"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaises(M.KyleBalanceError):
            M.revise(reader(data))
        with self.assertRaises(M.KyleBalanceError):
            M.leader_rows(self.out["leader"][M.CID], self.live["ability"][M.ABILITY2])
        with self.assertRaises(M.KyleBalanceError):
            M.ability2_rows(self.out["ability"][M.ABILITY2])
        with self.assertRaises(M.KyleBalanceError):
            M.leader_text(self.out["cas"][M.CAS_LEADER])
        with self.assertRaises(M.KyleBalanceError):
            M.ability2_text(self.out["cas"][M.CAS_ABILITY2])


class ChainTests(unittest.TestCase):
    """第二批必须排在第一批之后：第一批 revise() 的输出 == 第二批的 live 输入。"""

    def test_batch1_output_is_the_batch2_input(self):
        batch1 = M1.revise(reader(load_fixture(FIXTURE_BATCH1)))
        live = load_fixture()
        self.assertEqual(batch1["leader"][M.CID], live["leader"][M.CID])
        self.assertEqual(batch1["cas"][M.CAS_LEADER], live["cas"][M.CAS_LEADER])

    @unittest.skipUnless((CANDIDATE / "package/manifest.json").is_file(), "candidate ma-kyle missing")
    def test_candidate_equals_the_live_inputs(self):
        """回写前：候选 == 第二批 live 输入；回写后：候选 == live 输入 + 本批 revise() 输出
        （本批只读核对、不返回的键仍等于输入）。"""
        import wf_share_update_codec as X
        root = CANDIDATE / "package/roots/common"
        live = load_fixture()
        if candidate_written_back():
            out = M.revise(reader(deepcopy(live)))
            if batch3_written_back():                      # 第三轮回写后：再叠加第三轮输出
                # 第三轮 BEFORE 里点名的键（如 desc_override_kyle_moon_1/_3/_6、change_skill_kyle_moon）
                # 本来就已在 live（第三轮只读核对，不是本批新增），只是第二批 fixture 没收录；
                # 补进 live 后续等式判定才成立，取值与 wf_balance_20260927c_kyle.BEFORE 锁的哈希对应的快照一致。
                import wf_balance_20260927c_kyle as M3
                fixture3 = json.loads((Path(__file__).parent /
                                       "fixtures/balance_20260927c_kyle.json").read_text(encoding="utf-8"))
                for kind, key in M3.BEFORE:
                    live.setdefault(kind, {}).setdefault(key, deepcopy(fixture3[kind][key]))
                out = batch3_overlay(live, out)
            for kind in ("leader", "ability", "cas", "dsl"):
                self.assertLessEqual(set(out[kind]), set(live[kind]), kind)
                live[kind].update(deepcopy(out[kind]))
        tables = {"leader": "master/ability/leader_ability.orderedmap",
                  "ability": "master/ability/ability.orderedmap",
                  "cas": "master/string/custom_ability_string.orderedmap"}
        for kind, logical in tables.items():
            rows = X.unpack((root / logical).read_bytes())
            for key, value in live[kind].items():
                self.assertEqual(X.csv_read(rows[key]), value, f"{kind}:{key}")
        for program, tree in live["dsl"].items():
            raw = (root / wf_dsl.dsl_logical(program)).read_bytes()
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], tree, program)


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_kyle 重跑不能回退本次改动。

    2026-09-27 第三轮（wf_balance_20260927c_kyle）改了同一生成器（队长月牙/贯穿成长数值、队长面板、
    PIERCE_VAR_CEIL）：这几处改比「第二批输出 + 第三轮覆盖」（:func:`batch3_overlay`）；其余仍直接比第二批输出。
    """

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.out3 = batch3_overlay(cls.live, cls.out)

    def test_panel_constants_equal_revise_output(self):
        self.assertEqual([[K.PANEL_LEADER]], self.out3["cas"][M.CAS_LEADER])
        # 第三轮（C 节）把能力2 面板的「雷属性共鸣时：」省略了（数值仍是第二批的）⇒ 比叠加结果
        self.assertEqual([[K.PANEL_ABILITY[2]]], self.out3["cas"][M.CAS_ABILITY2])
        self.assertEqual(K.CAS_TEXTS[M.CAS_LEADER], K.PANEL_LEADER)
        self.assertEqual(K.CAS_TEXTS[M.CAS_ABILITY2], K.PANEL_ABILITY[2])

    def test_plan_constants_equal_revise_output(self):
        leader = self.out3["leader"][M.CID]
        for index, (_addr, _src, cells, _e) in enumerate(K.LEADER[:4]):
            self.assertEqual([cells[111], cells[112]], leader[index][111:113], f"leader#{index}")
        self.assertEqual(dict(K.PIERCING_GROWTH), {r[45]: r[49] for r in leader if r[25] == "51"})
        for index, (_addr, _src, cells, _e) in enumerate(K.PLAN[2]):
            row = self.out["ability"][M.ABILITY2][index]
            self.assertEqual((cells[102], cells[113], cells[114]), (row[102], row[113], row[114]))
        self.assertEqual(K.PIERCE_VAR_CEIL, self.out3["dsl"][M.PIERCE_PROGRAM][11][1][0][1][5])
        self.assertEqual([K.CNA_SHAPE[i]["p12"] for i in (0, 1, 2)],
                         [a[13][0]["max"] for a in _cna(self.out["dsl"][M.SKILL_PROGRAMS["1"]])])
        flag = M.commands(self.out["dsl"][M.THUNDER_PROGRAM], "ConditionalsChangeSkillFlag")[0]
        self.assertEqual(_cna(flag[2])[0][13], [{"min": K.THUNDER_DETOUGHNESS_BOOST,
                                                 "max": K.THUNDER_DETOUGHNESS_BOOST}])
        self.assertEqual(_cna(flag[3])[0][13], [{"min": K.THUNDER_DETOUGHNESS_NORMAL,
                                                 "max": K.THUNDER_DETOUGHNESS_NORMAL}])

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_rows_and_trees_equal_revise_output(self):
        import wf_midautumn_common as MC
        import wf_midautumn_specs as MS
        import wf_seasonal7_build as B
        pass  # Imports resolve from this checkout/package, not external source copies.
        import test_midautumn_kit_kyle as T   # 只借用 fake_family 三件（与 kit 测试同一口径）
        ctx = B.KitContext(MC.MAPack(MS.get_spec("kyle"), record_sources=False))
        built = K.build_rows(ctx)
        self.assertEqual(built["leader"], self.out3["leader"][M.CID])
        self.assertEqual(built["ability"][M.ABILITY2], self.out["ability"][M.ABILITY2])
        self.assertEqual(built["ability"][M.ABILITY3], self.live["ability"][M.ABILITY3])
        blade, bolt, trail = T.blade_family(), T.bolt_family(), T.trail_family()
        donor = ctx.template_dsl(f"battle/action/skill/action/rare5/{K.TEMPLATE_CODE}${K.TEMPLATE_CODE}_1")
        pierce, _ = K.build_pierce_tree(ctx, donor)
        self.assertEqual(pierce, self.out3["dsl"][M.PIERCE_PROGRAM])
        thunder, _ = K.build_thunder_tree(ctx, donor, bolt)
        self.assertEqual(thunder, self.out["dsl"][M.THUNDER_PROGRAM])
        for level, program in M.SKILL_PROGRAMS.items():
            raw = ctx.template_dsl(f"battle/action/skill/action/rare5/{K.TEMPLATE_CODE}${K.TEMPLATE_CODE}_{level}")
            tree, _ = K.mutate_tree(ctx, raw, level)
            tree, _ = ctx.rewrite_effect_refs(tree, blade)
            tree, _ = ctx.rewrite_effect_refs(tree, trail)
            self.assertEqual(tree, self.out["dsl"][program], level)


class MirrorTests(unittest.TestCase):
    PATHS = (ROOT / M.DESIGN_REL, ROOT / M.PANEL_REL)

    def setUp(self):
        if not all(path.is_file() for path in self.PATHS):
            self.skipTest("midautumn design mirrors missing")
        self.docs = [json.loads(path.read_text(encoding="utf-8")) for path in self.PATHS]
        # 第三轮（wf_balance_20260927c_kyle）改了同一生成器的队长面板 / 段数上限；镜像由主会话 --write 落盘，
        # 落盘前在内存里补上（第三轮 mirror_updates 幂等，已落盘时为恒等），再核对本批 / 第一批同步仍是恒等。
        import wf_balance_20260927c_kyle as M3
        self.docs = list(M3.mirror_updates(*self.docs))

    def test_mirrors_are_already_synced(self):
        self.assertEqual(M.mirror_updates(*self.docs), tuple(self.docs))
        deviations = json.loads((ROOT / M1.DEVIATIONS_REL).read_text(encoding="utf-8"))
        self.assertEqual(M1.mirror_updates(*self.docs, deviations), (*self.docs, deviations))   # 第一批仍是恒等
        design, panel = self.docs
        self.assertEqual(K._design_problems(design), [])
        self.assertEqual([line["text"] for line in panel["leader"]["lines"]], K.PANEL_LEADER.split("\n"))
        two = next(entry for entry in panel["abilities"] if entry["index"] == 2)
        # 第三轮（C 节）省略了本行的「雷属性共鸣时：」，其余与第二批逐字相同
        self.assertEqual([line["text"] for line in two["lines"]],
                         [M.NEW_ABILITY2_TEXT.replace(M.MAIN_ICON, "").replace("雷属性共鸣时：", "", 1)])
        block = design["plan"]["rework1"][M.MIRROR_KEY]
        self.assertEqual(block["crescent_ability_limit"], 10)
        self.assertEqual(block["skill_detoughness"]["total"], [36, 30])
        self.assertEqual(panel[M.MIRROR_KEY]["note"], M.MIRROR_NOTE)

    def test_mirror_update_is_idempotent_and_pure(self):
        before = deepcopy(self.docs)
        once = M.mirror_updates(*self.docs)
        self.assertEqual(self.docs, before)
        self.assertEqual(M.mirror_updates(*once), once)


if __name__ == "__main__":
    unittest.main()
