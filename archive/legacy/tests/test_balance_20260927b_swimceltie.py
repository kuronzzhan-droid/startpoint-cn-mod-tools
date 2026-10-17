# -*- coding: utf-8 -*-
"""希尔媞「千刃共振」149996 ``wind_spgirl_swim`` 2026-09-27 平衡第二批（删眩晕蓄积成长）。

fixture（``fixtures/balance_20260927b_swimceltie.json``）= revise() 的 live 输入快照（1.4.1049 只读），
另存同角色直击相关行（只作总量核对）与官方先例 brown_fighter 1210011（需要 ``.cdn/cn`` 时与官方基线逐字比对）。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_swimceltie as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_swimceltie.json"
DATA = json.loads(FIXTURE.read_text(encoding="utf-8"))


def load_fixture() -> dict:
    return {kind: value for kind, value in deepcopy(DATA).items() if not kind.startswith("_")}


def reader(data: dict, cas: dict | None = None):
    cas = cas or {}

    def read(kind, key):
        if kind == "cas":
            return cas[key]            # 无覆盖键 ⇒ KeyError，同 live
        return data[kind][key]
    return read


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys}, set(M.BEFORE))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), ("149996", "wind_spgirl_swim"))
        self.assertEqual((M.PACKAGES, M.PACKAGE_VERSION, M.CAPABILITIES, M.REVIEWED_DRIFT), ([], {}, [], {}))
        self.assertFalse(self.out["notes"]["runtime_verified"])
        json.dumps(self.out["notes"], ensure_ascii=False)

    def test_only_the_ability4_key_is_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {M.ABILITY_KEY})
        for kind in ("leader", "cas", "text", "table", "action", "dsl", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        self.assertTrue(M.ABILITY_KEY.startswith(M.CID))           # BarePlan 命名空间断言

    def test_ability4_before_and_after(self):
        old, new = self.live["ability"][M.ABILITY_KEY], self.out["ability"][M.ABILITY_KEY]
        self.assertEqual((len(old), len(new)), (1, 1))
        old, new = old[0], new[0]
        self.assertEqual((old[27], old[30], old[34], old[47], old[48], old[51], old[52]),
                         ("12", "7700000", "101", "51", "0", "25000", "25000"))
        self.assertEqual((new[27], new[30], new[34], new[47], new[48], new[51], new[52]),
                         ("12", "7700000", "5", "33", "0", "20000", "20000"))
        changed = {c for c, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(changed, {34, 47, 51, 52})                  # 其余列逐字保留
        self.assertEqual((new[1], new[2], new[35], new[49]), ("true", "attack_common", "0", ""))
        self.assertEqual(int(new[51]) * int(new[34]), 100_000)       # 合计 +100%
        self.assertEqual(wf_describe.describe_rows([new], "ability")[0], "连击≥77(限5次) → 自身 Direct伤害 20%")

    def test_no_down_accumulation_left_in_ability4(self):
        new = self.out["ability"][M.ABILITY_KEY][0]
        self.assertNotIn(new[47], ("22", "51", "183", "241"))
        self.assertNotIn(new[109], ("19", "120"))

    def test_precedent_shape_matches_the_fixture_snapshot(self):
        row = DATA["_official_precedent"]["ability:1210011"][M.PRECEDENT["row"]]
        for col, value in M.PRECEDENT["cells"].items():
            self.assertEqual(row[col], value, col)
        new = self.out["ability"][M.ABILITY_KEY][0]
        for col in (2, 27, 47, 48):                                  # 同触发族、同内容、同目标、同图标组
            self.assertEqual(new[col], row[col], col)
        self.assertLessEqual(int(new[51]) * int(new[34]), int(row[52]) * int(row[34]))   # ≤ 官方 +120%

    @unittest.skipUnless((ROOT / ".cdn/cn").is_dir() and (ROOT / "mod-tools/profiles.json").is_file(),
                         "需要 .cdn/cn 官方基线")
    def test_precedent_snapshot_equals_the_official_baseline(self):
        import wf_mod_tool as core
        from wf_enhancement_policy import OfficialBaseline
        baseline = OfficialBaseline(ROOT / ".cdn/cn", cache_dir=ROOT / "mod-tools/work/official-baseline",
                                    write_cache=False)
        logical = "master/ability/ability.orderedmap"
        digest = core.sha1_path(logical)
        rows = core.read_orderedmap_file_from_bytes(baseline.get("common", digest[:2] + "/" + digest[2:]))
        self.assertEqual(core.read_csv_lines(rows[M.PRECEDENT["key"]]),
                         DATA["_official_precedent"]["ability:1210011"])

    def test_direct_attack_totals_are_documented_and_untouched_rows_unchanged(self):
        peer = DATA["_live_context"]["ability:1499962"][M.PEER_DIRECT["row"]]
        for col, value in M.PEER_DIRECT["cells"].items():
            self.assertEqual(peer[col], value, col)
        leader = DATA["_live_context"]["leader:149996"]
        self.assertEqual([(r[45], r[46], r[32], r[49]) for r in leader],
                         [("32", "0", "101", "12500"), ("33", "0", "101", "12500"),
                          ("32", "5", "101", "12500"), ("33", "5", "101", "12500")])
        self.assertIn("direct_total", self.out["notes"])
        self.assertIn("flag_for_author", self.out["notes"])

    def test_native_legality_gates_are_empty(self):
        row = self.out["ability"][M.ABILITY_KEY][0]
        self.assertEqual(L.client_legality_problems("ability", row), [])
        self.assertEqual(L.declared_block_field_problems("ability", row), [])
        self.assertEqual(L.invoke_skill_string_problems(row, set(), kind="ability"), [])
        self.assertEqual(L.ability_element_column_problems("ability", row, M.ELEMENT), [])
        self.assertEqual(L.required_client_capabilities("ability", row), [])
        self.assertEqual(M.row_gate_problems(row), [])

    def test_panel_is_auto_generated_and_existing_override_is_rejected(self):
        """没有覆盖键 ⇒ 客户端按新行自动出文；若日后出现覆盖键，本模块必须拒绝（需同步文案）。"""
        with self.assertRaisesRegex(ValueError, "panel override keys now exist"):
            M.revise(reader(deepcopy(self.live), {M.PANEL_OVERRIDE_KEYS[4]: [["每达到77连击…眩晕…"]]}))
        self.assertEqual(M.PANEL_OVERRIDE_KEYS[4], "desc_override_wind_spgirl_swim_4")

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["ability"][M.ABILITY_KEY][0][0] = "mutated"
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.live)
            data[kind][key][0][51] = "30000"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))
            data = deepcopy(self.live)
            data[kind][key] = data[kind][key] + deepcopy(data[kind][key])
            with self.assertRaises(ValueError):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        data["ability"].update(deepcopy(self.out["ability"]))
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.ability4_rows(self.out["ability"][M.ABILITY_KEY])

    def test_row_locator_is_content_based(self):
        rows = deepcopy(self.live["ability"][M.ABILITY_KEY])
        rows[0][35] = "600"                                          # 带 CT 的同形行不是审过的那一行
        with self.assertRaises(ValueError):
            M.ability4_rows(rows)
        rows = deepcopy(self.live["ability"][M.ABILITY_KEY])
        rows[0][49] = "Green"
        with self.assertRaises(ValueError):
            M.ability4_rows(rows)


class GeneratorTests(unittest.TestCase):
    def test_locator_generator_does_not_build_this_character(self):
        """locator 登记的 wf_campus_celtie_data.py 只构建 149989；不会重写 1499964。"""
        import wf_campus_celtie_common as C
        self.assertEqual(C.CID, "149989")
        source = (Path(__file__).resolve().parents[1] / "wf_campus_celtie_data.py").read_text(encoding="utf-8")
        self.assertNotIn(M.ABILITY_KEY, source)
        self.assertNotIn(M.CODE, source)


if __name__ == "__main__":
    unittest.main()
