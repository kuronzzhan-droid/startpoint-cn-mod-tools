# -*- coding: utf-8 -*-
"""杰拉尔 129992 / 见岛勇希(泳装) 129991 2026-09-27 平衡批次：能力伤害攻击倍率 ×0.8。

fixture = live 输入快照（``fixtures/balance_20260927_waterab.json``），驱动 ``UNITS[*].revise()``：
每处改动、未改行逐字保留、BEFORE 漂移拒绝、不改输入、合法性门禁为空、能力伤害来源全量核对，
以及生成器（``wf_water_balance_20260924`` 与在其上调用 ``yuki_rows`` 的 ``wf_seasonal7_kit_yuki``）
产物 == revise()。勇希 kit 的改版方案锁定行在 gitignored work/ 下，缺时只跳过那一条。
"""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927_waterab as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_dsl  # noqa: E402
import wf_gerald_resonance as GR  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_kit_yuki as K  # noqa: E402
import wf_water_balance_20260924 as W  # noqa: E402
from wf_battle_rules import DAMAGE_CAP  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927_waterab.json"
W_FIXTURE = Path(__file__).parent / "fixtures/water_balance_20260924.json"
GERALD, YUKI = M.UNITS
KINDS = ("ability", "leader", "cas", "text", "table", "action", "dsl", "server_text")


def load_fixture() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


def reader(data: dict):
    def read(kind, key):
        return data[kind][key]
    return read


def diff_cells(old: list[str], new: list[str]) -> list[int]:
    return [i for i, (a, b) in enumerate(zip(old, new)) if a != b]


class ContractTests(unittest.TestCase):
    def test_fixture_is_the_reviewed_baseline(self):
        live = load_fixture()
        for unit in M.UNITS:
            for (kind, key), want in unit["BEFORE"].items():
                self.assertEqual(M.digest(live[kind][key]), want, f"{unit['CID']} {kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in live.items() for key in keys}, set(M.BEFORE))
        self.assertFalse(set(GERALD["BEFORE"]) & set(YUKI["BEFORE"]))

    def test_units_exports(self):
        self.assertEqual([(u["CID"], u["CODE"]) for u in M.UNITS],
                         [("129992", "unicorn_lancer_rose"), ("129991", "psychic_yuki_swim")])
        self.assertEqual(GERALD["PACKAGES"], ["unicorn_lancer_rose"])
        self.assertEqual(GERALD["PACKAGE_VERSION"], {"unicorn_lancer_rose": "0.1.14"})   # 现值 0.1.13
        self.assertEqual(GERALD["CAPABILITIES"], [DAMAGE_CAP])     # 追击 DSL 根头 102（候选已声明）
        self.assertEqual(YUKI["PACKAGES"], ["s7-yuki"])
        self.assertEqual(YUKI["PACKAGE_VERSION"], {"s7-yuki": "1.0.6"})   # 现值 0.2.0、历史最高 1.0.5
        self.assertEqual(YUKI["CAPABILITIES"], [])
        for unit in M.UNITS:
            self.assertEqual(unit["REVIEWED_DRIFT"], {})
            self.assertTrue(callable(unit["revise"]))
            self.assertEqual(set(unit["PACKAGE_VERSION"]), set(unit["PACKAGES"]))

    def test_generator_constants_are_the_revision(self):
        self.assertEqual(W.STRIKE_MULTIPLIER, M.STRIKE_NEW)
        self.assertEqual(W.STRIKE_TEXT, M.STRIKE_TEXT_NEW)
        self.assertEqual(M.STRIKE_TEXT_NEW, "对距离最近的敌人造成36倍水属性能力伤害，威力随连击数提升")
        self.assertEqual((W.STRIKE_KEY, W.STRIKE_PROGRAM), (M.STRIKE_KEY, M.STRIKE_PROGRAM))


class GeraldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise_gerald(reader(deepcopy(cls.live)))

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {"1299923", "1299925"})
        self.assertEqual(set(out["cas"]), {M.STRIKE_KEY})
        self.assertEqual(set(out["dsl"]), {M.STRIKE_PROGRAM})
        for kind in ("leader", "text", "table", "action", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])               # 追击程序已在候选 manifest 里
        json.dumps(out["notes"], ensure_ascii=False)
        self.assertTrue(M.STRIKE_KEY.startswith("change_skill_" + M.GERALD_CODE))
        for key in out["ability"]:
            self.assertTrue(key.startswith(M.GERALD_CID))

    def test_ability3_row3_nearest_strike_10x_to_8x(self):
        old, new = self.live["ability"]["1299923"], self.out["ability"]["1299923"]
        self.assertEqual(len(old), len(new))
        self.assertEqual([i for i, (a, b) in enumerate(zip(old, new)) if a != b], [2])
        self.assertEqual(diff_cells(old[2], new[2]), [51, 52])
        self.assertEqual((old[2][47], old[2][51], old[2][52]), ("353", "1000000", "1000000"))
        self.assertEqual((new[2][51], new[2][52]), ("800000", "800000"))
        self.assertEqual(D.describe_line(new[2], "ability"),
                         "技能发动≥1 → 对最近的敌人 能力伤害·依攻击水 800%(8倍)")

    def test_ability5_row1_all_enemies_15x_to_12x(self):
        old, new = self.live["ability"]["1299925"], self.out["ability"]["1299925"]
        self.assertEqual([i for i, (a, b) in enumerate(zip(old, new)) if a != b], [0])
        self.assertEqual(diff_cells(old[0], new[0]), [51, 52])
        self.assertEqual((old[0][47], old[0][51]), ("252", "1500000"))
        self.assertEqual((new[0][51], new[0][52]), ("1200000", "1200000"))
        self.assertEqual(new[0][35], "60")                       # CT 1 秒不动
        self.assertEqual(D.describe_line(new[0], "ability"),
                         "水·编成≥6 时: 技能Hit≥1(CT1秒) → 对全体敌人 能力伤害·依攻击水 1200%(12倍)")
        self.assertEqual(new[1:], old[1:])                       # 694 / 695 独立乘区 buff 不动

    def test_strike_tree_only_the_per_hit_multiplier_changes(self):
        old = self.live["dsl"][M.STRIKE_PROGRAM]
        new = self.out["dsl"][M.STRIKE_PROGRAM]
        self.assertEqual(new[10], 102)                            # 仍按能力伤害结算
        hits = list(wf_dsl.iter_dsl_commands(new, "CreateNormalAttack"))
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0][6], [{"min": 36, "max": 36}])
        restored = deepcopy(new)
        next(wf_dsl.iter_dsl_commands(restored, "CreateNormalAttack"))[6] = [{"min": 45, "max": 45}]
        self.assertEqual(restored, old)

    def test_strike_text(self):
        self.assertEqual(self.live["cas"][M.STRIKE_KEY], [[M.STRIKE_TEXT_OLD]])
        self.assertEqual(self.out["cas"][M.STRIKE_KEY],
                         [["对距离最近的敌人造成36倍水属性能力伤害，威力随连击数提升"]])
        text = self.out["cas"][M.STRIKE_KEY][0][0]
        self.assertEqual([w for w in KL.FORBIDDEN_PANEL_WORDS if w in text], [])
        self.assertNotIn("／", text)
        self.assertEqual(L.required_client_capabilities("custom_ability_string", [M.STRIKE_KEY]), [])

    def test_multipliers_are_exactly_point_eight(self):
        for key, index in M.GERALD_ROWS:
            old, new = self.live["ability"][key][index], self.out["ability"][key][index]
            for col in (51, 52):
                self.assertEqual(int(new[col]) * 5, int(old[col]) * 4)
        self.assertEqual(M.STRIKE_NEW * 5, M.STRIKE_OLD * 4)

    def test_buffs_and_other_keys_untouched(self):
        for key in ("1299921", "1299922", "1299924", "1299926"):
            self.assertNotIn(key, self.out["ability"])
        # 能力伤害加成 buff（388 / 695）仍是原值
        self.assertEqual(self.live["ability"]["1299923"][3][47:53], self.out["ability"]["1299923"][3][47:53])
        self.assertEqual(self.out["ability"]["1299925"][2][47], "695")
        self.assertEqual(self.out["ability"]["1299925"][2][51:53], ["20000", "20000"])

    def test_legality_gates_are_empty(self):
        cas_keys = {M.STRIKE_KEY}
        for key, rows in self.out["ability"].items():
            for index, row in enumerate(rows):
                label = f"ability:{key}#{index}"
                self.assertEqual(L.client_legality_problems("ability", row), [], label)
                self.assertEqual(L.declared_block_field_problems("ability", row), [], label)
                self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, "ability"), [], label)
                self.assertEqual(L.ability_element_column_problems("ability", row, M.WATER_ELEMENT), [], label)
                self.assertEqual(L.required_client_capabilities("ability", row), [], label)
        invoke = self.live["ability"]["1299921"][0]              # 629 行引用的文案键仍在本批 cas 里
        self.assertEqual(L.invoke_skill_string_problems(invoke, set(self.out["cas"]), "ability"), [])
        self.assertEqual(invoke[70:72], [M.STRIKE_KEY, M.STRIKE_PROGRAM])
        tree = self.out["dsl"][M.STRIKE_PROGRAM]
        encode_tree(tree)                                         # AMF3 往返一致
        self.assertEqual(M.dsl_problems(tree), [])
        self.assertEqual(L.action_dsl_element_problems(tree, M.WATER_ELEMENT), [])
        self.assertEqual(L.action_dsl_subject_binding_problems(tree), [])
        self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [])
        self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [])

    def test_audit_lists_every_ability_damage_source(self):
        audit = self.out["notes"]["audit"]
        self.assertEqual(audit["rows"], [{"key": "1299923", "row": 3, "kind": "353"},
                                         {"key": "1299925", "row": 1, "kind": "252"}])
        self.assertEqual(audit["invokes"], [{"key": "1299921", "row": 1, "string": M.STRIKE_KEY,
                                             "program": M.STRIKE_PROGRAM}])
        self.assertEqual(audit["dsl"]["invoke"][M.STRIKE_PROGRAM]["ability_damage_commands"], 1)
        for group in ("skill", "power_flip"):
            self.assertEqual(len(audit["dsl"][group]), 2 if group == "skill" else 3)
            for program, info in audit["dsl"][group].items():
                self.assertEqual((info["buffTargetAs"], info["hit_area_p24"], info["ability_damage_commands"]),
                                 (0, [0], 0), program)
                self.assertGreater(info["damage_commands"], 0, program)


class YukiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise_yuki(reader(deepcopy(cls.live)))

    def test_only_ability2_is_returned(self):
        self.assertEqual(set(self.out["ability"]), {"1299912"})
        for kind in ("leader", "cas", "text", "table", "action", "dsl", "server_text"):
            self.assertEqual(self.out[kind], {}, kind)
        self.assertEqual(self.out["new_programs"], [])
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_ability2_row3_all_enemies_10x_to_8x(self):
        old, new = self.live["ability"]["1299912"], self.out["ability"]["1299912"]
        self.assertEqual(new[:2], old[:2])                        # 连击+10 / 除自身水技能槽 5% 不动
        self.assertEqual(diff_cells(old[2], new[2]), [51, 52])
        self.assertEqual((old[2][47], old[2][30], old[2][51]), ("252", "7500000", "1000000"))
        self.assertEqual((new[2][51], new[2][52]), ("800000", "800000"))
        self.assertEqual(D.describe_line(new[2], "ability"),
                         "水·编成≥6 时: 连击≥75 → 对全体敌人 能力伤害·依攻击水 800%(8倍)")

    def test_legality_gates_are_empty(self):
        for index, row in enumerate(self.out["ability"]["1299912"]):
            label = f"ability:1299912#{index}"
            self.assertEqual(L.client_legality_problems("ability", row), [], label)
            self.assertEqual(L.declared_block_field_problems("ability", row), [], label)
            self.assertEqual(L.invoke_skill_string_problems(row, set(), "ability"), [], label)
            self.assertEqual(L.ability_element_column_problems("ability", row, M.WATER_ELEMENT), [], label)
            self.assertEqual(L.required_client_capabilities("ability", row), [], label)

    def test_audit_lists_every_ability_damage_source(self):
        audit = self.out["notes"]["audit"]
        self.assertEqual(audit["rows"], [{"key": "1299912", "row": 3, "kind": "252"}])
        self.assertEqual(audit["invokes"], [])
        for program, info in audit["dsl"]["skill"].items():
            self.assertEqual((info["buffTargetAs"], info["hit_area_p24"], info["ability_damage_commands"]),
                             (0, [0], 0), program)


class FailClosedTests(unittest.TestCase):
    def test_input_is_not_mutated_and_output_is_detached(self):
        live = load_fixture()
        for unit in M.UNITS:
            data = deepcopy(live)
            out = unit["revise"](reader(data))
            self.assertEqual(data, live)
            for rows in out["ability"].values():
                rows[0][51] = "mutated"
            self.assertEqual(data, live)

    def test_baseline_drift_is_rejected(self):
        live = load_fixture()
        for unit, (kind, key) in ((GERALD, ("ability", "1299923")), (GERALD, ("dsl", M.GERALD_PF["2"])),
                                  (GERALD, ("leader", "129992")), (YUKI, ("ability", "1299912")),
                                  (YUKI, ("dsl", M.YUKI_SKILLS["1"]))):
            data = deepcopy(live)
            value = data[kind][key]
            if kind == "dsl":
                value[10] = 2
            else:
                value[0][51] = "999999"
            with self.assertRaisesRegex(M.WaterAbilityBalanceError, "live drift"):
                unit["revise"](reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        live = load_fixture()
        for unit in M.UNITS:
            out = unit["revise"](reader(deepcopy(live)))
            data = deepcopy(live)
            for kind in ("ability", "cas", "dsl"):
                data[kind].update(deepcopy(out[kind]))
            with self.assertRaises(M.WaterAbilityBalanceError):
                unit["revise"](reader(data))
            inputs = {("ability", k): v for k, v in out["ability"].items()}
            edits = M.GERALD_ROWS if unit is GERALD else M.YUKI_ROWS
            news = M.GERALD_NEW if unit is GERALD else M.YUKI_NEW
            with self.assertRaisesRegex(M.WaterAbilityBalanceError, "unexpected preimage"):
                M.scale_rows(inputs, edits, news)            # 不会再 ×0.8 一次
        gerald = M.revise_gerald(reader(deepcopy(live)))
        with self.assertRaises(M.WaterAbilityBalanceError):
            M.strike_tree(gerald["dsl"][M.STRIKE_PROGRAM])
        with self.assertRaises(M.WaterAbilityBalanceError):
            M.strike_text(gerald["cas"][M.STRIKE_KEY])

    def _inputs(self, unit):
        live = load_fixture()
        return {(kind, key): deepcopy(live[kind][key]) for kind, key in unit["BEFORE"]}

    def _audit(self, unit, inputs):
        if unit is GERALD:
            return M.audit(inputs, M.GERALD_CID, M.GERALD_ABILITY, row_sites=set(M.GERALD_ROWS),
                           invoke_programs={(M.GERALD_ABILITY[1], 0): (M.STRIKE_KEY, M.STRIKE_PROGRAM)},
                           pf_programs=M.GERALD_PF, skill_programs=M.GERALD_SKILLS)
        return M.audit(inputs, M.YUKI_CID, M.YUKI_ABILITY, row_sites=set(M.YUKI_ROWS), invoke_programs={},
                       pf_programs={}, skill_programs=M.YUKI_SKILLS)

    def test_audit_rejects_unreviewed_ability_damage_sources(self):
        """绕过 BEFORE：任何未审查的能力伤害来源（行 / 技能段 / PF 段 / 629 程序）都拒绝。"""
        self._audit(GERALD, self._inputs(GERALD))
        self._audit(YUKI, self._inputs(YUKI))
        cases = []
        inputs = self._inputs(YUKI)                               # 技能 DSL 根头改成能力归属
        inputs["dsl", M.YUKI_SKILLS["2"]][10] = 2
        cases.append((YUKI, inputs))
        inputs = self._inputs(GERALD)                             # 某判定区 p24 改成 102
        next(wf_dsl.iter_dsl_commands(inputs["dsl", M.GERALD_SKILLS["1"]], "CreateHitArea"))[24] = 102
        cases.append((GERALD, inputs))
        inputs = self._inputs(GERALD)                             # PF 覆盖段改成能力归属
        inputs["dsl", M.GERALD_PF["3"]][10] = 102
        cases.append((GERALD, inputs))
        inputs = self._inputs(YUKI)                               # 多出一条 kind252 行
        extra = deepcopy(inputs["ability", "1299912"][2])
        inputs["ability", "1299916"].append(extra)
        cases.append((YUKI, inputs))
        inputs = self._inputs(GERALD)                             # 629 改指其他程序
        inputs["ability", "1299921"][0][71] = "battle/action/skill/action/ability_skill/x$x"
        cases.append((GERALD, inputs))
        inputs = self._inputs(GERALD)                             # 722 覆盖档位变了
        inputs["leader", "129992"][9][81] = "1,2"
        cases.append((GERALD, inputs))
        for unit, broken in cases:
            with self.assertRaises(M.WaterAbilityBalanceError):
                self._audit(unit, broken)

    def test_row_locator_is_content_based(self):
        inputs = self._inputs(GERALD)
        inputs["ability", "1299923"][2][28] = "0"                 # 不再是「水属性角色发动技能」
        with self.assertRaisesRegex(M.WaterAbilityBalanceError, "unexpected preimage"):
            M.scale_rows(inputs, M.GERALD_ROWS, M.GERALD_NEW)
        with self.assertRaises(M.WaterAbilityBalanceError):
            M.scaled("1000001")
        with self.assertRaises(M.WaterAbilityBalanceError):
            M.scaled("0")


class GeneratorSyncTests(unittest.TestCase):
    """重跑生成器不能把本次改动回退：产物 == revise()，或对新值 fail closed。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.gerald = M.revise_gerald(reader(deepcopy(cls.live)))
        cls.yuki = M.revise_yuki(reader(deepcopy(cls.live)))
        cls.pre = json.loads(W_FIXTURE.read_bytes())["rows"]     # 0924 修订前的已审查输入

    def test_water_balance_generator_rows_equal_revise(self):
        self.assertEqual(W.gerald_rows("1299925", self.pre["1299925"]), self.gerald["ability"]["1299925"])
        self.assertEqual(W.yuki_rows(self.pre["1299912"]), self.yuki["ability"]["1299912"])
        # 本批未改的键，生成器产物仍 == live（改动不外溢）
        for key in ("1299921", "1299922"):
            self.assertEqual(W.gerald_rows(key, self.pre[key]), self.live["ability"][key], key)

    def test_water_balance_generator_strike_equals_revise(self):
        self.assertEqual(W.strike_tree(), self.gerald["dsl"][M.STRIKE_PROGRAM])
        self.assertEqual([[W.STRIKE_TEXT]], self.gerald["cas"][M.STRIKE_KEY])

    def test_water_balance_generator_refuses_the_revised_state(self):
        """apply_candidate 重跑面对已改的候选：基线哈希拒绝，而不是再写一遍旧值。"""
        with self.assertRaisesRegex(ValueError, "unreviewed balance baseline"):
            W.gerald_rows("1299925", self.gerald["ability"]["1299925"])
        with self.assertRaisesRegex(ValueError, "unreviewed balance baseline"):
            W.yuki_rows(self.yuki["ability"]["1299912"])

    def test_yuki_kit_applies_yuki_rows_after_the_locked_rows(self):
        src = inspect.getsource(K.build)
        self.assertIn("from wf_water_balance_20260924 import yuki_rows", src)
        self.assertIn('abilities[f"{CID}2"] = yuki_rows(abilities[f"{CID}2"])', src)
        self.assertIn('locked[f"{CID}2"] = yuki_rows(locked[f"{CID}2"])', src)

    @unittest.skipUnless((ROOT / K.REVISION_REL).is_file() and (ROOT / K.REVISION5_REL).is_file(),
                         "seasonal7 yuki revision plan (gitignored work/) absent")
    def test_yuki_kit_chain_from_plan_matches_revise(self):
        revision = json.loads((ROOT / K.REVISION_REL).read_text(encoding="utf-8"))
        revision5 = json.loads((ROOT / K.REVISION5_REL).read_text(encoding="utf-8"))
        locked = K._locked_rows(revision, revision5)
        self.assertEqual(locked["1299912"], self.pre["1299912"])
        self.assertEqual(W.yuki_rows(locked["1299912"]), self.yuki["ability"]["1299912"])

    def test_historic_gerald_resonance_gate_fails_closed(self):
        """wf_gerald_resonance 的 1299925 哈希闸门对新倍率拒绝（不会把 15 倍写回）。"""
        with self.assertRaises(ValueError):
            GR.revise_ability("1299925", core.write_csv_lines(self.gerald["ability"]["1299925"]))
        two_rows = [self.gerald["ability"]["1299925"][0], self.gerald["ability"]["1299925"][1]]
        with self.assertRaises(ValueError):
            GR.revise_ability("1299925", core.write_csv_lines(two_rows))


if __name__ == "__main__":
    unittest.main()
