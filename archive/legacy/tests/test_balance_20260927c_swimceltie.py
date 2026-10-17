# -*- coding: utf-8 -*-
"""希尔媞「千刃共振」149996 灰服版 · 2026-09-27 平衡第三轮修订模块回归。

fixture（``fixtures/balance_20260927c_swimceltie.json``）= live 1.4.1054（gray3 导入后）只读快照，键 = BEFORE；
``_leader_precedents`` 另存 4 条官方队长行（只作新队长行的形状先例核对）。逐项断言：能力4 眩晕积蓄 25%×101 →
10%×10、能力2 三行 12.5%×101 → 10%×10、队长 #0/#1 12.5% → 10%、队长新增 #5–#7（= 队长 c0 + 能力2 改前行[5:]，
10%、限 101）、旋风 629 p13 13/24 → 1/24（每次 13 → 1）；未改格/行逐字保留、BEFORE 漂移拒绝、不改输入、对自身输出
重跑拒绝、合法性门禁与 DSL 四道门禁为空、AMF3 往返；第二批泳装模块与 gray3 不能在本轮之后重放。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_gray3 as G  # noqa: E402
import wf_balance_20260927b_swimceltie as B2  # noqa: E402
import wf_balance_20260927c_swimceltie as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402
import wf_describe  # noqa: E402
import wf_dsl  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parent / "fixtures/balance_20260927c_swimceltie.json"
FX = json.loads(FIXTURE.read_text(encoding="utf-8"))


def load() -> dict:
    return {(kind, key): deepcopy(value) for kind, key, value in FX["reads"]}


def reader(data: dict, extra_cas: dict | None = None):
    extra_cas = extra_cas or {}

    def read(kind, key):
        if kind == "cas" and key in extra_cas:
            return deepcopy(extra_cas[key])
        return data[kind, key]                    # 缺键 ⇒ KeyError，同 live（覆盖文案键不存在）
    return read


def diff_cells(a, b):
    return {i: (x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y}


class ReviseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.out = M.revise(reader(deepcopy(cls.data)))

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    # ------------------------------------------------------------ 基线与接口

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(set(self.data), set(M.BEFORE))
        for key, want in M.BEFORE.items():
            self.assertEqual(M.digest(self.data[key]), want, key)
        self.assertEqual(FX["live_tail"], "1.4.1054")

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), ("149996", "wind_spgirl_swim"))
        self.assertEqual((M.PACKAGES, M.PACKAGE_VERSION, M.CAPABILITIES, M.REVIEWED_DRIFT), ([], {}, [], {}))
        self.assertIs(self.out["notes"]["runtime_verified"], False)
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {M.A2, M.A4})               # 能力6（629 行）只读
        self.assertEqual(set(out["leader"]), {M.CID})
        self.assertEqual(set(out["dsl"]), {M.WHIRLWIND_PROGRAM})
        for kind in ("cas", "text", "table", "action", "server_text", "new_programs"):
            self.assertFalse(out[kind], kind)                             # auto 面板、技能文案都不含这些数值
        for key in list(out["ability"]) + list(out["leader"]):
            self.assertTrue(key.startswith(M.CID), key)                   # BarePlan 命名空间断言

    # ------------------------------------------------------------ 表行

    def test_ability4_stun_accumulation_is_capped_at_100(self):
        old, new = self.live("ability", M.A4), self.out["ability"][M.A4]
        self.assertEqual((len(old), len(new)), (1, 1))
        self.assertEqual(diff_cells(old[0], new[0]),
                         {34: ("101", "10"), 51: ("25000", "10000"), 52: ("25000", "10000")})
        row = new[0]
        self.assertEqual((row[27], row[30], row[47], row[48], row[1]), ("12", "7700000", "51", "0", "true"))
        self.assertEqual(int(row[52]) * int(row[34]), 100_000)           # 合计 100% = 自身上限
        self.assertNotEqual(row[47], "33")                               # 不是第二批的直击方案

    def test_ability2_team_growth_is_capped_at_ten_steps(self):
        old, new = self.live("ability", M.A2), self.out["ability"][M.A2]
        self.assertEqual((len(old), len(new)), (3, 3))
        for i, (a, b) in enumerate(zip(old, new)):
            self.assertEqual(diff_cells(a, b), {34: ("101", "10"), 51: ("12500", "10000"),
                                                52: ("12500", "10000")}, i)
            self.assertEqual((b[47], b[48], b[49], b[27], b[30]),
                             (("32", "33", "34")[i], "5", "Green", "12", "7700000"))
            self.assertEqual(int(b[52]) * int(b[34]), 100_000)          # 各合计 +100%

    def test_leader_self_rows_slow_to_four_fifths_and_others_are_kept(self):
        old, new = self.live("leader", M.CID), self.out["leader"][M.CID]
        self.assertEqual((len(old), len(new)), (5, 8))
        for i in (0, 1):
            self.assertEqual(diff_cells(old[i], new[i]), {49: ("12500", "10000"), 50: ("12500", "10000")}, i)
            self.assertEqual((new[i][32], new[i][46], new[i][4]), ("101", "0", "0"))   # 限 101 保留、自身、无前置
        for i in (2, 3, 4):
            self.assertEqual(new[i], old[i], i)                          # 充能/加槽不动

    def test_added_leader_rows_are_the_uncapped_part_of_ability2(self):
        ability2 = self.live("ability", M.A2)
        new = self.out["leader"][M.CID]
        for li, ai in M.LEADER_ADDED.items():
            row, src = new[li], ability2[ai]
            self.assertEqual(len(row), M.LEADER_NCOLS)
            want = [M.LEADER_C0, "0", ""] + src[5:]
            self.assertEqual(diff_cells(want, row), {49: ("12500", "10000"), 50: ("12500", "10000")}, li)
            for col in range(5, M.ABILITY_NCOLS):                        # 列号能力 c≥5 → 队长 c−2
                if col not in (51, 52):
                    self.assertEqual(row[col - 2], src[col], (li, col))
            self.assertEqual((row[25], row[28], row[32], row[45], row[46], row[47], row[4]),
                             ("12", "7700000", "101", src[47], "5", "Green", "0"))
        self.assertEqual({r[0] for r in new}, {M.LEADER_C0})
        # 与 #0/#1 不合并：同触发同 kind，但目标不同（自身 vs 风队）
        self.assertEqual([(new[i][45], new[i][46]) for i in (0, 1, 5, 6)],
                         [("32", "0"), ("33", "0"), ("32", "5"), ("33", "5")])

    def test_values_are_four_fifths_and_multiples_of_five_percent(self):
        num, den = M.FACTOR
        self.assertEqual((num, den), (4, 5))
        self.assertEqual(12500 * num // den, 10000)
        leader = self.out["leader"][M.CID]
        for i in (0, 1, 5, 6, 7):
            self.assertEqual((leader[i][49], leader[i][50]), ("10000", "10000"), i)
        for rows in self.out["ability"].values():
            for row in rows:
                self.assertEqual(int(row[51]) % 5000, 0)
                self.assertEqual(row[34], "10")

    def test_describe_after(self):
        got = {f"ability:{k}": wf_describe.describe_rows(v, "ability") for k, v in self.out["ability"].items()}
        got[f"leader_ability:{M.CID}"] = [wf_describe.describe_line(r, "leader_ability")
                                          for r in self.out["leader"][M.CID]]
        self.assertEqual(got, M.DESCRIBE_AFTER)
        self.assertEqual(self.out["notes"]["describe_after"], M.DESCRIBE_AFTER)

    def test_leader_shape_precedents(self):
        ctx = FX["_leader_precedents"]
        shape = {k: (r[25], r[45], r[46], r[47], r[3]) for k, r in ctx.items()}
        self.assertEqual(shape, {"leader:341001#2": ("12", "32", "5", "Green", "0"),
                                 "leader:241004#1": ("12", "32", "5", "Green", "0"),
                                 "leader:341005#2": ("0", "33", "5", "Green", "0"),
                                 "leader:333001#1": ("12", "34", "5", "Yellow", "0")})
        live_leader = self.live("leader", M.CID)
        self.assertEqual((live_leader[1][25], live_leader[1][45]), ("12", "33"))   # trigger 12 + kind 33 已上线

    @unittest.skipUnless((ROOT / ".cdn/cn").is_dir() and (ROOT / "mod-tools/profiles.json").is_file(),
                         "需要 .cdn/cn 官方基线")
    def test_leader_precedents_equal_the_official_baseline(self):
        import wf_mod_tool as core
        from wf_enhancement_policy import OfficialBaseline
        baseline = OfficialBaseline(ROOT / ".cdn/cn", cache_dir=ROOT / "mod-tools/work/official-baseline",
                                    write_cache=False)
        digest = core.sha1_path("master/ability/leader_ability.orderedmap")
        rows = core.read_orderedmap_file_from_bytes(baseline.get("common", digest[:2] + "/" + digest[2:]))
        for name, row in FX["_leader_precedents"].items():
            key, index = name.split(":")[1].split("#")
            self.assertEqual(core.read_csv_lines(rows[key])[int(index)], row, name)

    # ------------------------------------------------------------ 旋风 629

    def test_whirlwind_row_is_fast_ct_so_cap_is_one(self):
        rows = self.live("ability", M.A6)
        self.assertEqual(M.whirlwind_row_guard(rows), 60)
        row = rows[M.A6_WHIRLWIND_ROW]
        self.assertEqual((row[6], row[27], row[28], row[35], row[47], row[70], row[71]),
                         ("202", "23", "0", "60", "629", M.WHIRLWIND_KEY, M.WHIRLWIND_PROGRAM))
        slow = deepcopy(rows)
        slow[M.A6_WHIRLWIND_ROW][35] = "240"
        with self.assertRaises(ValueError):
            M.whirlwind_row_guard(slow)

    def test_whirlwind_detoughness_13_to_1_only_p13_changes(self):
        before, after = self.live("dsl", M.WHIRLWIND_PROGRAM), self.out["dsl"][M.WHIRLWIND_PROGRAM]
        self.assertEqual((M.detoughness(before), M.detoughness(after)), (13.0, 1.0))
        area, attack = M.whirlwind_parts(after)
        self.assertEqual(area[14], ["CalculatedUsingMaxNumOfHits", 24])
        self.assertEqual(attack[13], [{"min": 1 / 24, "max": 1 / 24}])
        self.assertEqual(24 * attack[13][0]["max"], 1.0)
        restored = deepcopy(after)
        M.whirlwind_parts(restored)[1][13] = [{"min": 13 / 24, "max": 13 / 24}]
        self.assertEqual(restored, before)                              # 只动了 p13
        _, old_attack = M.whirlwind_parts(before)
        self.assertEqual((attack[6], attack[14], attack[8]), (old_attack[6], old_attack[14], False))
        self.assertEqual(self.out["notes"]["whirlwind"]["detoughness"], [13.0, 1.0])

    def test_dsl_roundtrip_and_four_gates(self):
        tree = self.out["dsl"][M.WHIRLWIND_PROGRAM]
        self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)
        encode_tree(tree)                                                # 同暂存脚本：往返不一致会抛
        self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [])
        self.assertEqual(L.action_dsl_subject_binding_problems(tree), [])
        self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [])
        self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [])
        self.assertEqual(M.dsl_problems(tree), [])

    # ------------------------------------------------------------ 门禁

    def test_native_legality_gates_are_empty(self):
        for key, rows in self.out["ability"].items():
            for row in rows:
                self.assertEqual(L.client_legality_problems("ability", row), [], key)
                self.assertEqual(L.declared_block_field_problems("ability", row), [], key)
                self.assertEqual(L.invoke_skill_string_problems(row, set(), kind="ability"), [], key)
                self.assertEqual(L.ability_element_column_problems("ability", row, M.ELEMENT), [], key)
                self.assertEqual(L.required_client_capabilities("ability", row), [], key)
        for row in self.out["leader"][M.CID]:
            self.assertEqual(L.client_legality_problems("leader_ability", row), [])
            self.assertEqual(L.declared_block_field_problems("leader_ability", row), [])
            self.assertEqual(L.invoke_skill_string_problems(row, set(), kind="leader_ability"), [])
            self.assertEqual(L.ability_element_column_problems("leader_ability", row, M.ELEMENT), [])
            self.assertEqual(L.required_client_capabilities("leader_ability", row), [])
            self.assertEqual(M.row_gate_problems("leader_ability", row), [])

    # ------------------------------------------------------------ fail closed

    def test_panel_override_appearing_is_rejected(self):
        for key in ("desc_override_wind_spgirl_swim_2", "desc_override_wind_spgirl_swim_leader"):
            with self.assertRaisesRegex(ValueError, "panel override keys now exist"):
                M.revise(reader(deepcopy(self.data), {key: [["每达到77连击…"]]}))

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.data)
        out = M.revise(reader(data))
        self.assertEqual(data, self.data)
        out["ability"][M.A2][0][0] = "mutated"
        out["leader"][M.CID][5][0] = "mutated"
        M.whirlwind_parts(out["dsl"][M.WHIRLWIND_PROGRAM])[1][13] = "mutated"
        self.assertEqual(data, self.data)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.data)
            if kind == "dsl":
                M.whirlwind_parts(data[kind, key])[1][13] = [{"min": 0.5, "max": 0.5}]
            else:
                data[kind, key][0][0] += "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline", msg=(kind, key)):
                M.revise(reader(data))

    def test_rerun_on_own_output_is_rejected(self):
        data = deepcopy(self.data)
        for key, rows in self.out["ability"].items():
            data["ability", key] = deepcopy(rows)
        data["leader", M.CID] = deepcopy(self.out["leader"][M.CID])
        data["dsl", M.WHIRLWIND_PROGRAM] = deepcopy(self.out["dsl"][M.WHIRLWIND_PROGRAM])
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(data))
        # 各变换对自身产物也拒绝（不会叠加两次）
        with self.assertRaises(ValueError):
            M.ability2_rows(self.out["ability"][M.A2])
        with self.assertRaises(ValueError):
            M.ability4_rows(self.out["ability"][M.A4])
        with self.assertRaises(ValueError):
            M.leader_rows(self.out["leader"][M.CID], self.live("ability", M.A2))
        with self.assertRaises(ValueError):
            M.whirlwind_tree(self.out["dsl"][M.WHIRLWIND_PROGRAM])

    def test_unreviewed_shapes_are_rejected(self):
        for index, col, value in ((0, 34, "(None)"), (1, 49, "Red"), (2, 51, "15000")):
            rows = self.live("ability", M.A2)
            rows[index][col] = value
            with self.assertRaises(ValueError, msg=(index, col)):
                M.ability2_rows(rows)
        leader = self.live("leader", M.CID)
        leader[0][4] = "2"                                              # 自身成长行带了前置
        with self.assertRaises(ValueError):
            M.leader_rows(leader, self.live("ability", M.A2))
        with self.assertRaises(ValueError):
            M.leader_growth_row(self.live("ability", M.A4)[0])           # 不是能力2 的行
        tree = self.live("dsl", M.WHIRLWIND_PROGRAM)
        M.whirlwind_parts(tree)[0][14] = ["CalculatedUsingMaxNumOfHits", 30]
        with self.assertRaises(ValueError):
            M.whirlwind_tree(tree)


class NoReplayTest(unittest.TestCase):
    """第二批泳装模块 / gray3 不能在本轮之后重放。"""

    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.out = M.revise(reader(deepcopy(cls.data)))

    def test_batch2_swimceltie_matches_the_imported_row_hazard(self):
        # 灰版 1499964 就是第二批改前那一行：第二批模块此刻仍可应用 ⇒ 暂存计划里不得出现它
        self.assertEqual(B2.BEFORE[("ability", B2.ABILITY_KEY)], M.BEFORE[("ability", M.A4)])
        b2_out = B2.revise(reader(deepcopy(self.data)))
        self.assertEqual(b2_out["ability"][M.A4][0][47], "33")          # 第二批 = 自身直击 +20%×5
        self.assertEqual(self.out["ability"][M.A4][0][47], "51")         # 本轮 = 眩晕积蓄 10%×10
        self.assertIn("no_replay_batch2", self.out["notes"])

    def test_batch2_swimceltie_fails_closed_after_this_round(self):
        data = deepcopy(self.data)
        data["ability", M.A4] = deepcopy(self.out["ability"][M.A4])
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            B2.revise(reader(data))

    def test_gray3_is_already_closed_on_this_live(self):
        before = G.BEFORE_BY_CID[M.CID]
        stale = [key for key in M.BEFORE if key in before and before[key] != M.BEFORE[key]]
        self.assertIn(("dsl", M.WHIRLWIND_PROGRAM), stale)               # 导入前 live 没有旋风程序
        self.assertIn(("ability", M.A2), stale)


if __name__ == "__main__":
    unittest.main()
