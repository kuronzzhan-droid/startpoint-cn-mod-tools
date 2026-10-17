# -*- coding: utf-8 -*-
"""芙拉菲「圆月下的捣糕之约」149987 ``combat_animal_moon`` 2026-09-27 平衡第三轮（c，成长复核）。

fixture = live 输入快照（``fixtures/balance_20260927c_fluffy.json``，make_read(live_only=True)，本地链尾 1.4.1053），
驱动 ``revise()``：每处改动的前后值、未改行/未改面板行逐字保留、数值按「原值 × 档位系数、取 5 的倍数」、
fixture 就是第二批输出（b → c 链）、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、合法性门禁为空、
面板规则、生成器输出 == revise() 输出（接管第二批测试的生成器一致性断言）、设计镜像已同步、候选干跑。
生成器装配对比需要 ``.cdn/cn`` 官方基线与 live store（缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_fluffy as B  # noqa: E402
import wf_balance_20260927c_fluffy as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_midautumn_kit_fluffy as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927c_fluffy.json"
B_FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_fluffy.json"
WORKSPACE = ROOT / "work/character_packs" / M.PACKAGES[0]
#: 候选 ma-fluffy manifest 现有的 required_capabilities（改后不新增）。
CANDIDATE_CAPABILITIES = {"panel-description-override-v2", "dash-parameter-v1", "gauge-gain-rules-v1"}


def load(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


def load_fixture() -> dict:
    return load(FIXTURE)


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
    import wf_seasonal7_build as BLD
    return BLD.KitContext(MC.MAPack(MS.get_spec("fluffy"), record_sources=False))


def cell_diff(a: list[str], b: list[str]) -> dict[int, tuple[str, str]]:
    return {i: (x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y}


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old_leader = cls.live["leader"][M.LEADER_KEY]
        cls.new_leader = cls.out["leader"][M.LEADER_KEY]

    # ------------------------------------------------------------ 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys}, set(M.BEFORE))

    def test_fixture_is_the_batch2_output(self):
        """b → c 链：本轮的 live 输入 == 第二批模块对其快照的输出（1.4.1051 已发布、此后未再动）。"""
        b_out = B.revise(reader(load(B_FIXTURE)))
        self.assertEqual(self.old_leader, b_out["leader"][B.LEADER_KEY])
        self.assertEqual(self.live["cas"][M.CAS_LEADER], b_out["cas"][B.CAS_LEADER])
        self.assertEqual({i: (old, b_new) for i, (old, b_new) in B.LEADER_CHANGES.items()},
                         {i: (M.ORIGINAL[i], old) for i, (old, _new) in M.LEADER_CHANGES.items()})

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (str(K.CID), K.CODE))
        self.assertEqual(M.PACKAGES, ["ma-fluffy"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-fluffy": "1.0.2"})   # 候选现值 1.0.1，只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertEqual(M.CAS_LEADER, K.LEADER_OVERRIDE)
        self.assertEqual((M.INVOKE_KEY, M.INVOKE_PROGRAM), (K.INVOKE_STRING, K.INVOKE_PROGRAM))

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["leader"]), {M.LEADER_KEY})
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER, M.CAS_A3})          # 能力3 = 技能强化文案（R2）
        for kind in ("ability", "text", "table", "action", "dsl", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)
        self.assertFalse(out["notes"]["runtime_verified"])
        self.assertTrue(M.CAS_LEADER.startswith("desc_override_" + M.CODE))

    # ------------------------------------------------------------ 队长

    def test_leader_only_the_growth_cells_change(self):
        old, new = self.old_leader, self.new_leader
        self.assertEqual((len(old), len(new)), (13, 13))
        diffs = {i: cell_diff(a, b) for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(diffs, {
            4: {49: ("2000", "15000"), 50: ("2000", "15000")},
            5: {49: ("2000", "15000"), 50: ("2000", "15000")},
            9: {49: ("20000", "70000"), 50: ("20000", "70000")},
            12: {49: ("1000", "4000"), 50: ("1000", "4000")},
        })
        self.assertEqual([new[i][45] for i in (4, 5, 9, 12)], ["32", "34", "34", "694"])
        for i in (0, 1, 2, 3, 6, 7, 8, 10, 11):
            self.assertEqual(new[i], old[i], i)

    def test_growth_rows_stay_unlimited_and_resonance_gated(self):
        for i in (4, 5, 9, 12):
            row = self.new_leader[i]
            self.assertEqual((row[4], row[7], row[9]), ("2", "600000", "Green"), i)   # 风共鸣（不新增前置，D3）
            self.assertEqual((row[32], row[33]), ("(None)", "0"), i)                  # 仍不限次、无 CT

    def test_values_follow_the_tier_and_rounding_rules(self):
        """原值 × 档位（4/5 或 7/10，2/3 为下限）；≥10% 取 5 的倍数，<10% 取整数（D2）。"""
        for i, (_old, new) in M.LEADER_CHANGES.items():
            original, value = int(M.ORIGINAL[i]), int(new)
            ratio = Fraction(value, original)
            self.assertGreaterEqual(ratio, Fraction(2, 3), i)
            self.assertLessEqual(ratio, Fraction(4, 5), i)
            if original >= 10000 * 2:                      # 原值 ≥20%：5 的倍数（千 = 1% ⇒ 5000）
                self.assertEqual(value % 5000, 0, i)
            else:
                self.assertEqual(value % 1000, 0, i)
            nominal = original * Fraction(*map(int, M.FACTOR[i].split("/")))
            self.assertLessEqual(abs(value - nominal), 2500, i)   # 就近取整，误差不超过半档
        self.assertEqual({i: new for i, (_o, new) in M.LEADER_CHANGES.items()},
                         {4: "15000", 5: "15000", 9: "70000", 12: "4000"})

    def test_three_minute_totals_match_the_table(self):
        totals = {i: int(new) // 1000 * M.THREE_MIN_EVENTS[i] for i, (_o, new) in M.LEADER_CHANGES.items()}
        self.assertEqual(totals, {4: 525, 5: 525, 9: 1400, 12: 48})

    def test_charge_rows_and_the_lv3_cooltime_are_untouched(self):
        new = self.new_leader
        self.assertEqual([(new[i][45], new[i][49]) for i in (10, 11)], [("35", "5000"), ("245", "5000")])
        self.assertEqual([(new[i][25], new[i][33], new[i][45]) for i in (7, 8)],
                         [("65", "360", "226"), ("65", "360", "629")])

    def test_auto_describe_renders_the_new_rows(self):
        new = self.new_leader
        self.assertEqual(D.describe_line(new[4], "leader_ability"), "风·编成≥6 时: 强化弹射≥1 → 赋予全队(风) 攻击力 15%")
        self.assertEqual(D.describe_line(new[5], "leader_ability"), "风·编成≥6 时: 强化弹射≥1 → 赋予全队(风) 技能伤害 15%")
        self.assertEqual(D.describe_line(new[9], "leader_ability"), "风·编成≥6 时: 连击≥250 → 自身 技能伤害 70%")
        self.assertEqual(D.describe_line(new[12], "leader_ability"),
                         "风·编成≥6 时: 强化弹射≥3 → 赋予全队(风) 独立乘区技能伤害 4%")

    # ------------------------------------------------------------ 面板

    def test_panel_changes_only_the_three_growth_lines(self):
        old = self.live["cas"][M.CAS_LEADER][0][0].split("\n")
        rows = self.out["cas"][M.CAS_LEADER]
        self.assertEqual((len(rows), len(rows[0])), (1, 1))
        new = rows[0][0].split("\n")
        self.assertEqual(len(new), len(old))
        self.assertEqual([i for i in range(len(old)) if old[i] != new[i]], [2, 3, 5])
        self.assertEqual(new[2], "风属性共鸣时，每发动3次强化弹射，风属性角色技能充能速度＋5%、技能槽最大值＋5%、"
                                 "技能伤害额外乘区＋4%")
        self.assertEqual(new[3], "风属性共鸣时，每发动1次强化弹射，风属性角色攻击力＋15%、技能伤害＋15%、连击＋5")
        self.assertEqual(new[5], "风属性共鸣时，每达到250连击，自身技能伤害＋70%")
        self.assertIn("冷却时间：6秒", new[4])

    def test_panel_agrees_with_the_data(self):
        rows = self.new_leader
        pct = lambda value: f"＋{int(value) // 1000}%"    # noqa: E731
        lines = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertIn(f"技能充能速度{pct(rows[10][49])}、技能槽最大值{pct(rows[11][49])}、"
                      f"技能伤害额外乘区{pct(rows[12][49])}", lines[2])
        self.assertIn(f"攻击力{pct(rows[4][49])}、技能伤害{pct(rows[5][49])}、连击＋{int(rows[6][49]) // 100000}",
                      lines[3])
        self.assertIn(f"自身技能伤害{pct(rows[9][49])}", lines[5])

    def test_panel_text_obeys_the_project_rules(self):
        text = self.out["cas"][M.CAS_LEADER][0][0]
        self.assertEqual(M.panel_problems(text), [])
        self.assertEqual(L.panel_override_capability(M.CAS_LEADER), "panel-description-override-v2")
        for line in text.split("\n"):
            self.assertEqual(KL.panel_problems(line), [], line)
            self.assertFalse(line.startswith(K.MAIN_ICON), line)
            for word in ("可无限", "无上限", "自身为队长时", "生命值100%以下", "(None)", "／"):
                self.assertNotIn(word, line)

    # ------------------------------------------------------------ 合法性

    def test_native_legality_gates_are_empty(self):
        cas_keys = set(K.CAS_TEXTS)
        for index, row in enumerate(self.new_leader):
            label = f"leader#{index}"
            self.assertEqual(L.client_legality_problems("leader_ability", row), [], label)
            self.assertEqual(L.declared_block_field_problems("leader_ability", row), [], label)
            self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, "leader_ability"), [], label)
            self.assertEqual(M.row_problems(row, {M.CAS_LEADER, M.INVOKE_KEY}), [], label)
            self.assertEqual(KL.row_problems("leader_ability", row), {}, label)
            self.assertLessEqual(set(L.required_client_capabilities("leader_ability", row)),
                                 CANDIDATE_CAPABILITIES, label)

    # ------------------------------------------------------------ fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["leader"][M.LEADER_KEY][4][49] = "mutated"
        out["cas"][M.CAS_LEADER][0][0] = "mutated"
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.live)
            data[kind][key][0][0] += "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        for kind in ("leader", "cas"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.leader_rows(self.new_leader)
        with self.assertRaises(ValueError):
            M.leader_text(self.out["cas"][M.CAS_LEADER])

    def test_batch2_preimage_is_required(self):
        """第二批之前的原值（20%/100%/5%）不是本轮的原像：跳过第二批直接套本轮必须拒绝。"""
        b_live = load(B_FIXTURE)
        with self.assertRaises(ValueError):
            M.leader_rows(b_live["leader"][B.LEADER_KEY])
        with self.assertRaises(ValueError):
            M.leader_text(b_live["cas"][B.CAS_LEADER])

    def test_row_locators_are_content_based(self):
        for mutate in (lambda r: r[4].__setitem__(32, "10"),         # 成长行加了限次
                       lambda r: r[10].__setitem__(49, "1000"),       # 充能行被动过
                       lambda r: r[8].__setitem__(33, "1200"),        # Lv3 CT 被动过
                       lambda r: r[9].__setitem__(4, "0"),            # 共鸣门被摘
                       lambda r: r.__setitem__(slice(4, 6), [r[5], r[4]]),
                       lambda r: r.pop()):
            rows = deepcopy(self.old_leader)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.leader_rows(rows)
        text = deepcopy(self.live["cas"][M.CAS_LEADER])
        text[0][0] = text[0][0].replace("冷却时间：6秒", "冷却时间：5秒")
        with self.assertRaises(ValueError):
            M.leader_text(text)


class SkillEnhancementTextTests(unittest.TestCase):
    """作者「技能都强化效果只在队长技或者能力里面按照格式写,技能里面不要重复描述强化后的效果」（主会话口径 R1–R4）。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_ability3_flag_line_is_the_entry_without_numbers(self):
        old = self.live["cas"][M.CAS_A3][0][0].split("\n")
        new = self.out["cas"][M.CAS_A3][0][0].split("\n")
        self.assertEqual(len(old), len(new))
        self.assertEqual([i for i in range(len(old)) if old[i] != new[i]], [4])
        self.assertEqual(old[4], K.MAIN_ICON + "风属性共鸣时，强化『玉杵捣月·桂风连打』的连击效果，技能命中每次连击＋55")
        self.assertEqual(new[4], K.MAIN_ICON + "风属性共鸣时，强化『玉杵捣月·桂风连打』的连击效果，技能命中时追加连击")
        self.assertEqual(new[4], K.MAIN_ICON + "风属性共鸣时，" + self.live["cas"][M.CAS_FLAG2][0][0])
        body = new[4].removeprefix(K.MAIN_ICON + "风属性共鸣时，")
        self.assertEqual(KL.panel_problems(body, skill_flag=True), [])
        self.assertTrue(all(line.startswith(K.MAIN_ICON) for line in new))
        for line in new:
            self.assertEqual(KL.panel_problems(line.replace(K.MAIN_ICON, "")), [], line)

    def test_basis_is_the_wind_resonance_704_row(self):
        a3 = self.live["ability"][M.A3_KEY]
        self.assertEqual(M.flag_basis_problems(a3, self.live["cas"][M.CAS_FLAG2]), [])
        row = a3[M.FLAG2_ROW]
        self.assertEqual((row[47], row[70], row[1], row[6], row[9], row[11]),
                         ("704", M.CAS_FLAG2, "false", "2", "600000", "Green"))
        self.assertEqual(D.describe_line(row, "ability"), f"风·编成≥6 时: 自身 切换技能Flag2[{M.CAS_FLAG2}]")
        for mutate in (lambda r: r[M.FLAG2_ROW].__setitem__(70, "x"), lambda r: r[M.FLAG2_ROW].__setitem__(6, "0"),
                       lambda r: r[M.FLAG2_ROW].__setitem__(1, "true")):
            rows = deepcopy(a3)
            mutate(rows)
            self.assertTrue(M.flag_basis_problems(rows, self.live["cas"][M.CAS_FLAG2]))
        self.assertTrue(M.flag_basis_problems(a3, [["强化『玉杵捣月·桂风连打』的连击效果，技能命中每次连击＋55"]]))

    def test_reapply_is_rejected(self):
        with self.assertRaises(ValueError):
            M.ability3_text(self.out["cas"][M.CAS_A3])

    def test_generator_panel_equals_revise_output(self):
        self.assertEqual([[K.CAS_TEXTS[K.SLOT_OVERRIDE[3]]]], self.out["cas"][M.CAS_A3])
        self.assertEqual(K.CAS_TEXTS[K.CAS_FLAG2], self.live["cas"][M.CAS_FLAG2][0][0])   # 条目原文不改


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_fluffy 重跑不能把第二批的 2%/20%/1% 带回来（接管 b 测试的生成器一致性断言）。"""

    @classmethod
    def setUpClass(cls):
        cls.out = M.revise(reader(load_fixture()))

    def test_constants_mirror_the_module(self):
        self.assertEqual(K.BALANCE_C["pf_growth"], M.LEADER_CHANGES[4][1])
        self.assertEqual(K.BALANCE_C["pf_growth"], M.LEADER_CHANGES[5][1])
        self.assertEqual(K.BALANCE_C["combo_growth"], M.LEADER_CHANGES[9][1])
        self.assertEqual(K.BALANCE_C["pf3_growth"], {"35": "5000", "245": "5000", "694": M.LEADER_CHANGES[12][1]})
        # 第二批历史值原样保留，且正是本轮的原像
        self.assertEqual((K.BALANCE_B["pf_growth"], K.BALANCE_B["combo_growth"], K.BALANCE_B["pf3_growth"]["694"]),
                         (M.LEADER_CHANGES[4][0], M.LEADER_CHANGES[9][0], M.LEADER_CHANGES[12][0]))
        # 第二批削韧不动
        self.assertEqual((K.PESTLE_DETOUGHNESS, K.INVOKE_DETOUGHNESS), (B.PESTLE_P13[1], B.INVOKE_P13))

    def test_panel_constant_equals_revise_output(self):
        self.assertEqual([[K.CAS_TEXTS[K.LEADER_OVERRIDE]]], self.out["cas"][M.CAS_LEADER])

    def test_leader_plan_describes_the_revised_rows(self):
        self.assertEqual(len(K.LEADER), M.LEADER_ROWS)
        for index, row in enumerate(self.out["leader"][M.LEADER_KEY]):
            self.assertEqual(D.describe_line(row, "leader_ability"), K.LEADER[index][3], index)
        for index, (_old, new) in M.LEADER_CHANGES.items():
            self.assertEqual((K.LEADER[index][2][49], K.LEADER[index][2][50]), (new, new), index)

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_leader_rows_equal_revise_output(self):
        rows, _evidence = K.build_leader_rows(_kit_ctx())
        self.assertEqual(rows, self.out["leader"][M.LEADER_KEY])


class MirrorTests(unittest.TestCase):
    PATHS = (ROOT / M.DESIGN_REL, ROOT / M.PANEL_REL)

    def setUp(self):
        if not all(path.is_file() for path in self.PATHS):
            self.skipTest("midautumn design mirrors missing (work/ is gitignored)")
        self.docs = [json.loads(path.read_text(encoding="utf-8")) for path in self.PATHS]

    def test_mirrors_are_already_synced(self):
        self.assertEqual(M.sync_mirrors(ROOT, write=False), [])
        design, panel = self.docs
        rows = design["rework1"]["leader_ability"]["rows"]
        for index in M.MIRROR_ROWS:
            self.assertEqual(rows[index]["cells"], {str(c): v for c, v in K.LEADER[index][2].items()})
            self.assertEqual(rows[index]["desc_expected"], K.LEADER[index][3])
        self.assertEqual(design["rework1"][M.MIRROR_TAG]["module"], "mod-tools/wf_balance_20260927c_fluffy.py")
        self.assertIn(B.MIRROR_TAG, design["rework1"])                 # 第二批记录留作历史
        self.assertEqual([line["text"] for line in panel["leader"]["lines"]],
                         K.CAS_TEXTS[K.LEADER_OVERRIDE].split("\n"))
        self.assertEqual(panel["notes"][-1], M.MIRROR_NOTE)
        self.assertIn(B.MIRROR_NOTE, panel["notes"])

    def test_mirror_update_is_idempotent_and_pure(self):
        before = deepcopy(self.docs)
        once = M.mirror_updates(*self.docs)
        self.assertEqual(self.docs, before)
        self.assertEqual(M.mirror_updates(*once), once)


@unittest.skipUnless((WORKSPACE / "package/manifest.json").is_file()
                     and (ROOT / "mod-tools/profiles.json").is_file(), "local candidate workspace required")
class CandidateTests(unittest.TestCase):
    def test_candidate_accepts_the_revision_dry(self):
        """候选与 live 逐字相同（REVIEWED_DRIFT 为空）；dry-run 回写不落盘。回写后改为逐项比对。"""
        import wf_share_update_codec as X
        from wf_character_revision import RevisionCandidate
        out = M.revise(reader(load_fixture()))
        manifest = WORKSPACE / "package/manifest.json"
        before = manifest.read_bytes()
        current = json.loads(before)
        self.assertLessEqual(set(current["required_capabilities"]), CANDIDATE_CAPABILITIES)
        version = tuple(map(int, M.PACKAGE_VERSION[M.PACKAGES[0]].split(".")))
        have = tuple(map(int, current["package_version"].split(".")))
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                      snapshot_key="revision_20260927c", package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                                      baseline_factory=lambda *a, **k: None, reviewed_input_drift=M.REVIEWED_DRIFT)
        if have >= version:
            # 主会话暂存回写后：候选 = 本轮输出。
            for logical, table in (("master/ability/leader_ability.orderedmap", out["leader"]),
                                   ("master/string/custom_ability_string.orderedmap", out["cas"])):
                rows = X.unpack(candidate.read("common", logical))
                for key, value in table.items():
                    self.assertEqual(X.csv_read(rows[key]), value, key)
            return
        candidate.splice("master/ability/leader_ability.orderedmap", out["leader"])
        candidate.splice("master/string/custom_ability_string.orderedmap", out["cas"])
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertEqual(len(evidence["changed_files"]), 2)
        self.assertEqual(before, manifest.read_bytes())


if __name__ == "__main__":
    unittest.main()
