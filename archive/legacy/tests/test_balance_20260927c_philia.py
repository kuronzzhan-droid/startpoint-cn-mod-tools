# -*- coding: utf-8 -*-
"""菲莉亚 159996 · 2026-09-27 平衡第三轮（成长复核）修订模块回归。

fixture = live 1.4.1053 只读快照（= 第二批产物，与候选 s7-philia 1.0.12 逐字相同）。逐项断言：队长四行 c49/c50
改到表值（20% / 40% / 80% / 35%）且按口径取整、其余格与其余 4 行逐字保留、能力 3 封顶版不动（D4）、
BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、合法性门禁为空，以及生成器链
「kit 回放 → 0917 → 第二批 → 第三轮」== revise()。
"""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_philia as B  # noqa: E402
import wf_balance_20260927c_philia as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_seasonal7_kit_philia as K  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FIXTURE = HERE / "fixtures/balance_20260927c_philia.json"
FIXTURE_B = HERE / "fixtures/balance_20260927b_philia.json"
MANIFEST_CAPS = {"kyubi-fever-ratio-v1"}


def _load(path):
    fx = json.loads(path.read_bytes())
    return {(kind, tuple(key) if isinstance(key, list) else key): value for kind, key, value in fx["reads"]}


def load():
    return _load(FIXTURE)


def reader(data):
    return lambda kind, key: data[kind, key]


def diff_cells(a, b):
    return {i: (x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y}


class ReviseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.out = M.revise(reader(cls.data))

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(set(self.data), set(M.BEFORE))
        for key, want in M.BEFORE.items():
            self.assertEqual(M.digest(self.data[key]), want, key)

    def test_input_is_the_batch2_output(self):
        b_data = _load(FIXTURE_B)
        b_out = B.revise(reader(b_data))
        self.assertEqual(b_out["leader"][M.CID], self.data["leader", M.CID])

    def test_only_the_four_growth_rows_change(self):
        before, after = self.live("leader", M.CID), self.out["leader"][M.CID]
        self.assertEqual((8, 8), (len(before), len(after)))
        want = {1: ("2500", "20000"), 3: ("7000", "40000"), 6: ("20000", "80000"), 7: ("10000", "35000")}
        for i, (old, new) in enumerate(zip(before, after)):
            expect = {49: want[i], 50: want[i]} if i in want else {}
            self.assertEqual(diff_cells(old, new), expect, i)
        for i in want:                                                  # 触发 / 目标 / 光共鸣前置 / 不限次不变
            self.assertTrue(M.B._matches(after[i], M.LEADER_NCOLS, M.C_AFTER[i]), i)
            self.assertEqual((after[i][4], after[i][7], after[i][9], after[i][32]), ("2", "600000", "White", "(None)"))

    def test_values_follow_the_rounding_rules(self):
        after = self.out["leader"][M.CID]
        for i, (_label, orig, b2, _tier, new) in M.GROWTH.items():
            self.assertEqual(int(after[i][49]), new * 1000, i)
            self.assertEqual(int(after[i][49]) % 5000, 0, i)           # 5 的倍数
            self.assertGreaterEqual(new, orig * 2 / 3 - 1e-9, i)        # 不低于 2/3 下限
            self.assertLessEqual(new, orig * 4 / 5 + 1e-9, i)           # 不高于 4/5
            self.assertGreater(new, b2, i)
        self.assertEqual(20, 25 * 4 // 5)                               # L#1：D1 取 20%（2/3 = 16.7 向上取 5 的倍数）
        self.assertEqual(40, round((50 * 2 / 3 + 10 * 7 / 10) / 5) * 5)  # L#3：自身 2/3 + 并入 7/10
        self.assertEqual((80, 35), (100 * 4 // 5, 50 * 7 // 10))        # L#6 4/5、L#7 7/10

    def test_describe_after(self):
        rows = self.out["leader"][M.CID]
        self.assertEqual({i: D.describe_line(rows[i], "leader_ability") for i in M.DESCRIBE_AFTER}, M.DESCRIBE_AFTER)
        self.assertEqual(self.out["notes"]["describe_after"],
                         {f"leader_ability:{M.CID}#{i}": d for i, d in M.DESCRIBE_AFTER.items()})

    def test_row_legality_and_capabilities(self):
        caps = set()
        for row in self.out["leader"][M.CID]:
            self.assertEqual([], L.client_legality_problems("leader_ability", row))
            self.assertEqual([], L.declared_block_field_problems("leader_ability", row))
            self.assertEqual([], L.invoke_skill_string_problems(row, set(), "leader_ability"))
            self.assertEqual([], K.row_problems("leader_ability", row))
            caps.update(L.required_client_capabilities("leader_ability", row))
        self.assertLessEqual(caps, MANIFEST_CAPS)
        self.assertEqual([], M.CAPABILITIES)

    def test_only_changed_keys_are_returned(self):
        self.assertEqual(set(self.out["leader"]), {M.CID})
        for kind in ("ability", "cas", "text", "table", "action", "dsl", "server_text", "new_programs"):
            self.assertFalse(self.out[kind], kind)                      # 能力 3 封顶版（D4）/ DSL / 文案都不动
        self.assertEqual((M.PACKAGES, M.PACKAGE_VERSION, M.CAPABILITIES, M.REVIEWED_DRIFT),
                         (["s7-philia"], {"s7-philia": "1.0.13"}, [], {}))
        self.assertEqual((M.CID, M.CODE), (B.CID, B.CODE))
        self.assertIs(self.out["notes"]["runtime_verified"], False)
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_baseline_drift_is_rejected_and_inputs_are_not_mutated(self):
        snapshot = deepcopy(self.data)
        M.revise(reader(self.data))
        self.assertEqual(snapshot, self.data)
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.data)
            drifted[kind, key][0][0] += "x"
            with self.assertRaisesRegex(ValueError, "drifted"):
                M.revise(reader(drifted))

    def test_rerun_on_own_output_is_rejected_but_transform_is_idempotent(self):
        staged = dict(self.data)
        staged["leader", M.CID] = self.out["leader"][M.CID]
        with self.assertRaisesRegex(ValueError, "drifted"):
            M.revise(reader(staged))
        self.assertEqual(M.growth_rows(self.out["leader"][M.CID]), self.out["leader"][M.CID])

    def test_unreviewed_shapes_are_rejected(self):
        for index, col, value in ((1, 49, "3000"), (3, 50, "6000"), (6, 25, "2"), (7, 46, "2")):
            rows = self.live("leader", M.CID)
            rows[index][col] = value
            with self.assertRaisesRegex(ValueError, "preimage", msg=(index, col)):
                M.growth_rows(rows)
        with self.assertRaisesRegex(ValueError, "shape"):
            M.growth_rows(self.live("leader", M.CID)[:6])                # 第二批之前的 6 行形态
        b_data = _load(FIXTURE_B)
        with self.assertRaisesRegex(ValueError, "shape"):
            M.growth_rows(b_data["leader", M.CID])


class DonorPinTest(unittest.TestCase):
    """澄波响 kit 队长 L0 以 live 菲莉亚队长 #3 为 donor 且钉住其全部非空列：本轮改的 c49/c50 带不进去。"""

    def test_hibiki_l0_pins_the_changed_cells(self):
        import wf_midautumn_kit_hibiki as H
        import wf_midautumn_kitlib as KL
        data = load()
        old = data["leader", M.CID][3]
        new = M.revise(reader(data))["leader"][M.CID][3]
        changed = set(diff_cells(old, new))
        self.assertEqual(changed, {49, 50})
        entries = [e for e in H.LEADER if e[0] == f"{M.CID}#3"]
        self.assertTrue(entries)
        for _addr, source, cells, _expect in entries:
            self.assertEqual(source, "live")
            self.assertLessEqual(changed, {int(c) for c in cells})
            self.assertEqual(KL.apply_cells(old, cells, M.LEADER_NCOLS), KL.apply_cells(new, cells, M.LEADER_NCOLS))
        refs = {f"{M.CID}#{i}" for i in M.C_VALUES} | {f"{M.CID}#L{i + 1}" for i in M.C_VALUES}
        hits = {}
        for path in (ROOT / "mod-tools").glob("*.py"):
            if path.name.startswith("wf_balance_20260927") or path.name == "wf_midautumn_kit_hibiki.py":
                continue
            text = path.read_text(encoding="utf-8")
            found = sorted(r for r in refs if any(f"{r}{end}" in text for end in ('"', "'", ",", " ", ")")))
            if found:
                hits[path.name] = found
        self.assertEqual(hits, {})


def _design_available() -> bool:
    try:
        from test_seasonal7_kit_philia import _live_available
        return _live_available() and (ROOT / K.REVISION_REL).is_file()
    except Exception:
        return False


class GeneratorConsistencyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.out = M.revise(reader(cls.data))

    def test_kit_build_applies_round3_after_batch2(self):
        src = inspect.getsource(K.build)
        order = ["balance_b.growth_rows(", "balance_c.growth_rows(leader_rows)",
                 "_write_checked_flat(ctx, LEADER, {spec.cid_s: leader_rows})"]
        self.assertEqual(sorted(src.index(s) for s in order), [src.index(s) for s in order])
        self.assertIn("import wf_balance_20260927c_philia as balance_c", src)
        self.assertIn("wf_balance_20260927c_philia", K.__doc__)

    def test_batch2_output_then_round3_equals_revise(self):
        b_out = B.revise(reader(_load(FIXTURE_B)))
        self.assertEqual(M.growth_rows(b_out["leader"][M.CID]), self.out["leader"][M.CID])

    @unittest.skipUnless(_design_available(), "design / official baseline / live store unavailable")
    def test_kit_rows_chain_matches_revise(self):
        from test_seasonal7_kit_philia import ReadOnlyCtx
        import wf_philia_combo_stock as stock
        import wf_philia_no_flying_revision as NF
        import wf_seasonal_pf_revision as P
        ctx = ReadOnlyCtx()
        design, plan, cache = K.load_design(ROOT), K.load_revision(ROOT), {}
        leader, _ = K.revise_leader(ctx, K.derive_rows(ctx, design["leader"], "leader_ability", "leader", cache)[0],
                                    plan, cache)
        base = {design["ability_keys"][slot]: K.derive_rows(ctx, entries, "ability", slot, cache)[0]
                for slot, entries in design["abilities"].items()}
        ability, _ = K.revise_abilities(ctx, base, plan, cache)
        ability[M.CID + "1"], ability[M.CID + "4"] = stock.revise_abilities(ability[M.CID + "1"], ability[M.CID + "4"])
        ability[M.CID + "4"] = NF.ability4_rows(ability[M.CID + "4"])
        third = P.revise_rows("philia", ability[B.THIRD_KEY])
        leader, third = B.growth_rows(leader, third)
        self.assertEqual(self.data["leader", M.CID], leader)            # 本轮输入 == kit 第二批产物
        leader = M.growth_rows(leader)
        self.assertEqual(self.out["leader"][M.CID], leader)


if __name__ == "__main__":
    unittest.main()
