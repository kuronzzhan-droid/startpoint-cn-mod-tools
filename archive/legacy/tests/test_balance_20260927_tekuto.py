# -*- coding: utf-8 -*-
"""特克托 139993 ``super_robot_tailcoat`` 2026-09-27 平衡批次：能力6 技能槽充能 20%→10%。

fixture = live 输入快照（``fixtures/balance_20260927_tekuto.json``），驱动 ``revise()``：
改动两格、其余 124 列逐字保留、BEFORE 漂移拒绝、不改输入、合法性门禁为空、生成器一致。
生成器一致性需要 work/ 下的 seasonal7 设计稿与改版 plan（gitignore，缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927_tekuto as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_seasonal7_kit_tekuto as K  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927_tekuto.json"
DESIGN = ROOT / K.DESIGN_REL
PLAN = ROOT / K.REVISION_REL


def load_fixture() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


def reader(data: dict):
    def read(kind, key):
        return data[kind][key]
    return read


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old = cls.live["ability"][M.ABILITY_KEY]
        cls.new = cls.out["ability"][M.ABILITY_KEY]

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         set(M.BEFORE))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (K.CID, K.CODE))
        self.assertEqual(M.ABILITY_KEY, "1399936")
        self.assertEqual(M.PACKAGES, ["s7-tekuto"])
        self.assertEqual(M.PACKAGE_VERSION, {"s7-tekuto": "1.0.8"})   # 现值 1.0.0、历史最高 1.0.7
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertEqual(M.ELEMENT, K.ELEMENT)

    def test_only_the_ability6_key_is_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {M.ABILITY_KEY})
        for kind in ("leader", "cas", "text", "table", "action", "dsl", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)

    def test_only_c51_c52_change_to_5000_10000(self):
        self.assertEqual((len(self.old), len(self.new)), (1, 1))
        old, new = self.old[0], self.new[0]
        self.assertEqual((len(old), len(new)), (126, 126))
        self.assertEqual((old[51], old[52]), ("10000", "20000"))
        self.assertEqual((new[51], new[52]), ("5000", "10000"))
        self.assertEqual([i for i in range(126) if old[i] != new[i]], [51, 52])

    def test_growth_ratio_and_content_are_preserved(self):
        row = self.new[0]
        self.assertEqual(int(row[52]), 2 * int(row[51]))                 # 1:2 成长
        self.assertEqual(int(row[52]) / 100000, 0.10)                    # 满级 10%（100000 = 100%）
        self.assertEqual((row[0], row[1], row[2]), ("super_robot_tailcoat_6", "true", "special"))
        self.assertEqual((row[5], row[27]), ("0", "0"))                   # 瞬发、无触发（开场常驻）
        self.assertEqual((row[47], row[48], row[49]), ("35", "5", "Yellow"))

    def test_auto_panel_renders_the_new_range(self):
        self.assertEqual(D.describe_line(self.old[0], "ability"), "赋予全队(雷) 技能槽充能 10%→20%")
        self.assertEqual(D.describe_line(self.new[0], "ability"), "赋予全队(雷) 技能槽充能 5%→10%")

    def test_native_legality_gates_are_empty(self):
        for index, row in enumerate(self.new):
            label = f"ability:{M.ABILITY_KEY}#{index}"
            self.assertEqual(L.client_legality_problems("ability", row), [], label)
            self.assertEqual(L.declared_block_field_problems("ability", row), [], label)
            self.assertEqual(L.invoke_skill_string_problems(row, set(), kind="ability"), [], label)
            self.assertEqual(L.ability_element_column_problems("ability", row, M.ELEMENT), [], label)
            self.assertEqual(L.required_client_capabilities("ability", row), M.CAPABILITIES, label)

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["ability"][M.ABILITY_KEY][0][51] = "mutated"
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for mutate in (lambda r: r[0].__setitem__(52, "30000"),
                       lambda r: r[0].__setitem__(49, "Red"),
                       lambda r: r.append(list(r[0]))):
            data = deepcopy(self.live)
            mutate(data["ability"][M.ABILITY_KEY])
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        """重跑在已改的 live 上必须拒绝（fail closed），而不是再减半一次。"""
        data = deepcopy(self.live)
        data["ability"].update(deepcopy(self.out["ability"]))
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.ability6_rows(self.new)

    def test_row_locator_is_content_based(self):
        """绕过 BEFORE 直接调纯函数：行形状不对也要拒绝。"""
        for mutate in (lambda r: r[0].__setitem__(48, "0"),          # 目标变成自身
                       lambda r: r[0].__setitem__(80, "x"),          # 多出非空列
                       lambda r: r[0].pop(),                         # 列宽不对
                       lambda r: r.append(list(r[0]))):              # 多一条记录
            rows = deepcopy(self.old)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.ability6_rows(rows)
        with self.assertRaises(ValueError):
            M.ability6_rows([])


@unittest.skipUnless(DESIGN.is_file() and PLAN.is_file(), "seasonal7 design/revision json not present")
class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_seasonal7_kit_tekuto 重跑不能把 1399936 回退到 10000/20000。"""

    @classmethod
    def setUpClass(cls):
        cls.out = M.revise(reader(load_fixture()))
        cls.plan = K.load_revision_plan(ROOT)
        design = json.loads(DESIGN.read_text(encoding="utf-8"))
        cls.pre = {}
        for slot in range(1, 7):                  # 同 test_seasonal7_kit_tekuto._design_ability_rows
            key = design["ability_keys"][f"slot{slot}"]["key"]
            cls.pre[key] = [list(rec["row"]) for rec in design["abilities"][f"slot{slot}"]]

    def test_plan_copies_ability6_verbatim(self):
        self.assertEqual(self.plan["ability"]["keys"][M.ABILITY_KEY].get("op"), "no_change")
        self.assertNotIn(M.ABILITY_KEY, (K.REV3_MOVED_ABILITY_KEY, K.REV5_ABILITY_KEY))

    def test_design_row_is_the_pre_revision_live_row(self):
        self.assertEqual(self.pre[M.ABILITY_KEY], load_fixture()["ability"][M.ABILITY_KEY])

    def test_generator_rows_equal_revise_output(self):
        current = deepcopy(self.pre)
        current[M.ABILITY_KEY] = deepcopy(self.out["ability"][M.ABILITY_KEY])   # 候选回写后的包内行
        built, trace = K.revision_ability_rows(self.plan, current)
        self.assertEqual(built[M.ABILITY_KEY], self.out["ability"][M.ABILITY_KEY])
        self.assertIn({"key": M.ABILITY_KEY, "op": "no_change", "records": 1}, trace)
        # 其余 5 键与改前输入跑出来的结果一致：本次改动不外溢
        before, _ = K.revision_ability_rows(self.plan, deepcopy(self.pre))
        self.assertEqual({k: v for k, v in built.items() if k != M.ABILITY_KEY},
                         {k: v for k, v in before.items() if k != M.ABILITY_KEY})
        self.assertEqual(before[M.ABILITY_KEY], self.pre[M.ABILITY_KEY])


if __name__ == "__main__":
    unittest.main()
