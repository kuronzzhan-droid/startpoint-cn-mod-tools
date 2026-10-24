# -*- coding: utf-8 -*-
"""丝缇涅尔·中秋 159995 ``still_obstinator_moon`` 2026-09-27 平衡批次：友技回槽 10%→5%（作者追加：不加 CT）。

fixture = live 输入快照（``fixtures/balance_20260927_stinel.json``），驱动 ``revise()``：
只改两格且 CT 仍为 0、其余行逐字保留、面板与数据一致、BEFORE 漂移拒绝、不改输入、
合法性门禁为空、生成器一致、设计镜像已同步。
生成器装配对比需要 ``.cdn/cn`` 官方基线与 live store（缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927_stinel as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_midautumn_kit_stinel as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927_stinel.json'
#: 候选 ma-stinel manifest 现有的 required_capabilities（改后不新增）。
CANDIDATE_CAPABILITIES = {"kyubi-fever-ratio-v1", "panel-description-override-v2"}


def load_fixture() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


def reader(data: dict):
    def read(kind, key):
        return data[kind][key]
    return read


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


def _kit_ctx():
    import wf_midautumn_common as MC
    import wf_midautumn_specs as MS
    import wf_seasonal7_build as B
    return B.KitContext(MC.MAPack(MS.get_spec("stinel"), record_sources=False))


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
        self.assertEqual((M.CID, M.CODE), (str(K.CID), K.CODE))
        self.assertEqual(M.ABILITY_KEY, K.ABILITY_KEYS[2])
        self.assertEqual(M.CAS_SLOT3, K.SLOT3_OVERRIDE)
        self.assertEqual(M.PACKAGES, ["ma-stinel"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-stinel": "1.0.1"})   # 候选现值 1.0.0，只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertEqual((M.ELEMENT, M.MAIN_ICON), (K.ELEMENT, K.MAIN_ICON))

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {M.ABILITY_KEY})
        self.assertEqual(set(out["cas"]), {M.CAS_SLOT3})
        for kind in ("leader", "text", "table", "action", "dsl", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)
        for key in out["cas"]:   # RevisionCandidate 命名空间
            self.assertTrue(key.startswith("desc_override_" + M.CODE), key)

    def test_only_two_cells_of_row3_change(self):
        self.assertEqual((len(self.old), len(self.new)), (6, 6))
        self.assertEqual([i for i in range(6) if self.old[i] != self.new[i]], [3])
        old, new = self.old[3], self.new[3]
        self.assertEqual((len(old), len(new)), (126, 126))
        self.assertEqual([i for i in range(126) if old[i] != new[i]], [51, 52])
        self.assertEqual((old[35], old[51], old[52]), ("0", "10000", "10000"))
        self.assertEqual((new[35], new[51], new[52]), ("0", "5000", "5000"))

    def test_row3_is_the_peer_skill_gauge_row(self):
        row = self.new[3]
        self.assertEqual(row[1], "false")                                   # 整键主位
        self.assertEqual((row[6], row[9], row[11]), ("2", "600000", "White"))   # 光共鸣
        self.assertEqual((row[27], row[28], row[29]), ("23", "6", "White"))     # 除自身外的光角色施技
        self.assertEqual((row[47], row[48]), ("211", "0"))                  # 自身技能槽
        self.assertEqual(int(row[51]) / 100000, 0.05)                       # 5%
        self.assertEqual(row[35], "0")                                      # 不加 CT（作者追加）
        self.assertEqual(row[34], "(None)")                                 # 不限次

    def test_same_trigger_combo_row_keeps_no_ct(self):
        combo, gauge = self.new[4], self.new[3]
        self.assertEqual(combo, self.old[4])
        self.assertEqual((combo[47], combo[51], combo[52]), ("226", "5000000", "5000000"))  # 连击 50
        self.assertEqual(combo[35], "0")
        for col in (6, 9, 10, 11, 27, 28, 29, 30, 31, 34):
            self.assertEqual(combo[col], gauge[col], col)

    def test_auto_describe_renders_the_new_row(self):
        self.assertEqual(D.describe_line(self.old[3], "ability"),
                         "光·编成≥6 时: 技能发动≥1 → 自身 技能槽 10%")
        self.assertEqual(D.describe_line(self.new[3], "ability"),
                         "光·编成≥6 时: 技能发动≥1 → 自身 技能槽 5%")
        self.assertEqual(D.describe_line(self.new[4], "ability"),
                         "光·编成≥6 时: 技能发动≥1 → 自身 追加连击 50")

    def test_panel_changes_only_line3(self):
        old = self.live["cas"][M.CAS_SLOT3][0][0].split("\n")
        rows = self.out["cas"][M.CAS_SLOT3]
        self.assertEqual((len(rows), len(rows[0])), (1, 1))
        new = rows[0][0].split("\n")
        self.assertEqual(len(new), 4)
        self.assertEqual(new[2], " <icon id='main'>  光属性共鸣时：除自身外的光属性角色发动技能时，"
                                 "自身技能槽＋5%、连击＋50")
        self.assertEqual(new[:2] + new[3:], old[:2] + old[3:])
        self.assertEqual(old[2], M.OLD_PANEL_LINE)

    def test_panel_agrees_with_the_data(self):
        """面板数字从数据反推：技能槽 5%、连击 50；两条都无 CT，面板也不写 CT。"""
        line = self.out["cas"][M.CAS_SLOT3][0][0].split("\n")[2]
        gauge, combo = self.new[3], self.new[4]
        pct = int(gauge[51]) // 1000
        combo_n = int(combo[51]) // 100000
        self.assertEqual((gauge[35], combo[35]), ("0", "0"))
        self.assertTrue(line.endswith(f"自身技能槽＋{pct}%、连击＋{combo_n}"), line)
        self.assertNotIn("CT", line)

    def test_panel_texts_obey_the_project_rules(self):
        text = self.out["cas"][M.CAS_SLOT3][0][0]
        self.assertNotIn("／", text)
        for line in text.split("\n"):
            self.assertTrue(line.startswith(M.MAIN_ICON), line)   # 主位限制槽每行带 Ⓜ
            self.assertEqual(KL.panel_problems(line.replace(M.MAIN_ICON, "")), [], line)
            self.assertTrue(line.replace(M.MAIN_ICON, "").startswith("光属性共鸣时："), line)
        self.assertEqual(L.panel_override_capability(M.CAS_SLOT3), "panel-description-override-v2")

    def test_native_legality_gates_are_empty(self):
        cas_keys = set(K.CAS_TEXTS)
        for index, row in enumerate(self.new):
            label = f"ability:{M.ABILITY_KEY}#{index}"
            self.assertEqual(L.client_legality_problems("ability", row), [], label)
            self.assertEqual(L.declared_block_field_problems("ability", row), [], label)
            self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, kind="ability"), [], label)
            self.assertEqual(L.ability_element_column_problems("ability", row, M.ELEMENT), [], label)
            self.assertEqual(KL.row_problems("ability", row, K.ELEMENT), {}, label)
            self.assertLessEqual(set(L.required_client_capabilities("ability", row)),
                                 CANDIDATE_CAPABILITIES, label)
        self.assertEqual(L.required_client_capabilities("ability", self.new[3]), [])

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["ability"][M.ABILITY_KEY][3][51] = "mutated"
        out["ability"][M.ABILITY_KEY][0][0] = "mutated"
        out["cas"][M.CAS_SLOT3][0][0] = "mutated"
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.live)
            if kind == "cas":
                data[kind][key][0][0] += "。"
            else:
                data[kind][key][3][35] = "60"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))
            data = deepcopy(self.live)
            data[kind][key] = data[kind][key] + [list(data[kind][key][0])]
            with self.assertRaises(ValueError):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        """重跑在已改的 live 上必须拒绝（fail closed），而不是再减半一次。"""
        data = deepcopy(self.live)
        for kind in ("ability", "cas"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.ability3_rows(self.new)
        with self.assertRaises(ValueError):
            M.ability3_text(self.out["cas"][M.CAS_SLOT3])

    def test_row_locator_is_content_based(self):
        """绕过 BEFORE 直接调纯函数：目标行/连击行形状不对也要拒绝。"""
        mutations = (
            lambda r: r.__setitem__(slice(3, 5), [r[4], r[3]]),     # 目标行不在 #3
            lambda r: r[3].__setitem__(28, "7"),                    # 全队合计（含自身）
            lambda r: r[3].__setitem__(52, "20000"),                # 数值漂移
            lambda r: r[3].__setitem__(80, "x"),                    # 多出非空列
            lambda r: r[4].__setitem__(35, "120"),                  # 连击行已带 CT
            lambda r: r[4].__setitem__(51, "2500000"),              # 连击行漂移
            lambda r: r[0].pop(),                                   # 列宽不对
            lambda r: r.pop(),                                      # 记录条数不对
        )
        for n, mutate in enumerate(mutations):
            rows = deepcopy(self.old)
            mutate(rows)
            with self.assertRaises(ValueError, msg=str(n)):
                M.ability3_rows(rows)
        text = deepcopy(self.live["cas"][M.CAS_SLOT3])
        text[0][0] = text[0][0].replace(M.MAIN_ICON + "光属性共鸣时：光属性角色发动技能时", "光属性共鸣时：光属性角色发动技能时")
        with self.assertRaises(ValueError):
            M.ability3_text(text)


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_stinel 重跑不能把 10%/旧面板带回来，也不能从 donor 带进 CT。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_panel_constants_equal_revise_output(self):
        self.assertEqual([[K.CAS_TEXTS[K.SLOT3_OVERRIDE]]], self.out["cas"][M.CAS_SLOT3])
        self.assertEqual(K.MAIN_ICON + K.PANEL_SLOT3[M.PANEL_LINE], M.NEW_PANEL_LINE)

    def test_plan_cells_carry_the_new_values(self):
        records = {tag: (donor, source, cells, expect) for tag, donor, source, cells, expect in K.ABILITY[3][2]}
        _donor, _src, gauge, expect = records["友技回槽"]
        self.assertEqual((gauge[35], gauge[51], gauge[52]), ("0", "5000", "5000"))
        self.assertEqual(gauge[28], "6")
        self.assertEqual(expect, "光·编成≥6 时: 技能发动≥1 → 自身 技能槽 5%")
        _donor, _src, combo, expect = records["友技连击"]
        self.assertEqual(combo[35], "0")                     # 同触发的连击行不加 CT
        self.assertEqual(expect, "光·编成≥6 时: 技能发动≥1 → 自身 追加连击 50")
        self.assertEqual([tag for tag, *_ in K.ABILITY[3][2]].index("友技回槽"), M.ROW)

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_slot3_rows_equal_revise_output(self):
        """只走槽 3 的装配路径（同 build_ability_rows 的 plan 拼法），不受其他槽 donor 影响。"""
        ctx = _kit_ctx()
        unisonable, statue_group, records = K.ABILITY[3]
        rows = []
        for index, (tag, donor, source, cells, expect) in enumerate(records):
            plan = {0: f"{K.CODE}_3", 1: unisonable, 2: statue_group, **cells}
            row, _ev = KL.build_row(ctx, "ability", donor, plan, source=source, element=K.ELEMENT,
                                    expect_describe=expect, label=f"{M.ABILITY_KEY}#{index}({tag})")
            rows.append(row)
        self.assertEqual(rows, self.out["ability"][M.ABILITY_KEY])

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_full_generator_build_equals_revise_output(self):
        rows_by_key, evidence = K.build_ability_rows(_kit_ctx())
        self.assertEqual(rows_by_key[M.ABILITY_KEY], self.out["ability"][M.ABILITY_KEY])
        described = [ev["describe"] for ev in evidence if ev["key"] == M.ABILITY_KEY]
        self.assertEqual(described[M.ROW], "光·编成≥6 时: 技能发动≥1 → 自身 技能槽 5%")


class MirrorTests(unittest.TestCase):
    PATHS = (ROOT / M.DESIGN_REL, ROOT / M.PANEL_REL)

    def setUp(self):
        if not all(path.is_file() for path in self.PATHS):
            self.skipTest("midautumn design mirrors missing")
        self.docs = [json.loads(path.read_text(encoding="utf-8")) for path in self.PATHS]

    def test_mirrors_are_already_synced(self):
        self.assertEqual(M.sync_mirrors(ROOT, write=False), [])
        design, panel = self.docs
        block = design["rework1"][M.MIRROR_TAG]
        self.assertEqual(block["panel"][M.CAS_SLOT3], K.PANEL_SLOT3[M.PANEL_LINE])
        self.assertEqual(design["rework1"]["calibration"]["self_axis"]["技能槽"], M.SELF_AXIS_GAUGE)
        three = next(entry for entry in panel["abilities"] if entry["index"] == 3)
        self.assertEqual([line["text"] for line in three["lines"]], list(K.PANEL_SLOT3))
        self.assertEqual(three["lines"][M.PANEL_LINE]["status"], "changed")
        self.assertEqual(panel["notes"][-1], M.MIRROR_NOTE)

    def test_mirror_update_is_idempotent_and_pure(self):
        before = deepcopy(self.docs)
        once = M.mirror_updates(*self.docs)
        self.assertEqual(self.docs, before)
        self.assertEqual(M.mirror_updates(*once), once)


if __name__ == "__main__":
    unittest.main()
