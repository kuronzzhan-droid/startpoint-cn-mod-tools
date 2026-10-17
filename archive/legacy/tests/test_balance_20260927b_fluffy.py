# -*- coding: utf-8 -*-
"""芙拉菲「圆月下的捣糕之约」149987 ``combat_animal_moon`` 2026-09-27 平衡第二批。

fixture = live 输入快照（``fixtures/balance_20260927b_fluffy.json``，本地链尾 1.4.1049），驱动 ``revise()``：
每处改动的前后值、未改行/未改节点逐字保留、充能行与 Lv3 CT 不动、BEFORE 漂移拒绝、不改输入、
对自身输出重跑拒绝、合法性门禁为空、DSL AMF3 往返与四道门禁、面板规则、生成器输出 == revise() 输出、
设计镜像已同步。生成器装配对比需要 ``.cdn/cn`` 官方基线与 live store（缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_fluffy as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kit_fluffy as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_fluffy.json"
#: 候选 ma-fluffy manifest 现有的 required_capabilities（改后不新增）。
CANDIDATE_CAPABILITIES = {"panel-description-override-v2", "dash-parameter-v1", "gauge-gain-rules-v1"}


def load_fixture() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


C_FIXTURE = Path(__file__).parent / "fixtures/balance_20260927c_fluffy.json"
#: 第三轮（``wf_balance_20260927c_fluffy``，成长复核）已把生成器的队长成长推进到 c 值：生成器一致性按
#: 「第二批输出 + 第三轮覆盖」核对（b → c 两种状态都接受；逐格断言与设计镜像同步由 c 测试接管）。
GENERATOR_AT_C = K.LEADER[4][2][49] != M.LEADER_CHANGES[4][1]


def batch3_output(out: dict) -> dict:
    """第二批输出里被第三轮改写的键换成第三轮输出（c fixture == 第二批输出，见 c 测试），其余原样。"""
    import wf_balance_20260927c_fluffy as C
    data = {k: v for k, v in json.loads(C_FIXTURE.read_text(encoding="utf-8")).items() if not k.startswith("_")}
    c_out = C.revise(lambda kind, key: data[kind][key])
    merged = deepcopy(out)
    for kind, table in c_out.items():
        if kind != "notes" and isinstance(table, dict):
            merged.setdefault(kind, {}).update(deepcopy(table))
    return merged


def generator_target(out: dict) -> dict:
    return batch3_output(out) if GENERATOR_AT_C else out


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
    return B.KitContext(MC.MAPack(MS.get_spec("fluffy"), record_sources=False))


def cell_diff(a: list[str], b: list[str]) -> dict[int, tuple[str, str]]:
    return {i: (x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y}


def tree_diff(a, b, path=()) -> list[tuple]:
    if type(a) is not type(b):
        return [path]
    if isinstance(a, list):
        if len(a) != len(b):
            return [path]
        return [p for i, (x, y) in enumerate(zip(a, b)) for p in tree_diff(x, y, path + (i,))]
    if isinstance(a, dict):
        if set(a) != set(b):
            return [path]
        return [p for k in a for p in tree_diff(a[k], b[k], path + (k,))]
    return [] if a == b else [path]


def p13s(tree) -> list[float]:
    return [cna[13][0]["max"] for cna in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")]


def per_cast(tree) -> float:
    """每次施放单目标削韧：精准连击 ×10、八连 ×1 各段、裂地 then/else 两副本只执行一条。"""
    values = p13s(tree)
    return round(values[0] * 10 + sum(values[1:9]) + values[9], 6)


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def old(self, kind, key):
        return self.live[kind][key]

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys}, set(M.BEFORE))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (str(K.CID), K.CODE))
        self.assertEqual(M.PACKAGES, ["ma-fluffy"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-fluffy": "1.0.1"})   # 候选现值 1.0.0，只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertEqual(M.INVOKE_PROGRAM, K.INVOKE_PROGRAM)
        self.assertEqual(M.CAS_LEADER, K.LEADER_OVERRIDE)
        self.assertEqual(M.CAS_KEYS, frozenset(K.CAS_TEXTS))
        self.assertEqual(M.SKILL_PROGRAMS, tuple(f"{K.PROGRAM_DIR}/{K.CODE}${K.CODE}_{lv}" for lv in "12"))

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(out["ability"], {})                           # 能力行本批不动（只读能力3 核 CT）
        self.assertEqual(set(out["leader"]), {M.LEADER_KEY})
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER})
        self.assertEqual(set(out["dsl"]), {*M.SKILL_PROGRAMS, M.INVOKE_PROGRAM})
        for kind in ("text", "table", "action", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)
        self.assertTrue(M.CAS_LEADER.startswith("desc_override_" + M.CODE))

    # ------------------------------------------------------------ 队长

    def test_leader_only_the_growth_cells_change(self):
        old, new = self.old("leader", M.LEADER_KEY), self.out["leader"][M.LEADER_KEY]
        self.assertEqual((len(old), len(new)), (13, 13))
        diffs = {i: cell_diff(a, b) for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(diffs, {
            4: {49: ("20000", "2000"), 50: ("20000", "2000")},
            5: {49: ("20000", "2000"), 50: ("20000", "2000")},
            9: {49: ("100000", "20000"), 50: ("100000", "20000")},
            12: {49: ("5000", "1000"), 50: ("5000", "1000")},
        })
        self.assertEqual([new[i][45] for i in (4, 5, 9, 12)], ["32", "34", "34", "694"])

    def test_charge_rows_and_the_lv3_cooltime_are_untouched(self):
        """口径 A.6：每 3 次 PF 的 35/245 属充能不动；作者：「每 5 次 Lv3 PF 免费发动技能」CT 不动。"""
        new = self.out["leader"][M.LEADER_KEY]
        self.assertEqual([(new[i][45], new[i][49]) for i in (10, 11)], [("35", "5000"), ("245", "5000")])
        self.assertEqual([(new[i][25], new[i][33], new[i][45]) for i in (7, 8)],
                         [("65", "360", "226"), ("65", "360", "629")])
        self.assertEqual(new[:4] + new[6:9] + new[10:12], self.old("leader", M.LEADER_KEY)[:4]
                         + self.old("leader", M.LEADER_KEY)[6:9] + self.old("leader", M.LEADER_KEY)[10:12])

    def test_auto_describe_renders_the_new_rows(self):
        new = self.out["leader"][M.LEADER_KEY]
        self.assertEqual(D.describe_line(new[4], "leader_ability"), "风·编成≥6 时: 强化弹射≥1 → 赋予全队(风) 攻击力 2%")
        self.assertEqual(D.describe_line(new[5], "leader_ability"), "风·编成≥6 时: 强化弹射≥1 → 赋予全队(风) 技能伤害 2%")
        self.assertEqual(D.describe_line(new[9], "leader_ability"), "风·编成≥6 时: 连击≥250 → 自身 技能伤害 20%")
        self.assertEqual(D.describe_line(new[12], "leader_ability"),
                         "风·编成≥6 时: 强化弹射≥3 → 赋予全队(风) 独立乘区技能伤害 1%")

    # ------------------------------------------------------------ 面板

    def test_panel_changes_only_the_three_growth_lines(self):
        old = self.old("cas", M.CAS_LEADER)[0][0].split("\n")
        rows = self.out["cas"][M.CAS_LEADER]
        self.assertEqual((len(rows), len(rows[0])), (1, 1))
        new = rows[0][0].split("\n")
        self.assertEqual(len(new), len(old))
        self.assertEqual([i for i in range(len(old)) if old[i] != new[i]], [2, 3, 5])
        self.assertEqual(new[2], "风属性共鸣时，每发动3次强化弹射，风属性角色技能充能速度＋5%、技能槽最大值＋5%、"
                                 "技能伤害额外乘区＋1%")
        self.assertEqual(new[3], "风属性共鸣时，每发动1次强化弹射，风属性角色攻击力＋2%、技能伤害＋2%、连击＋5")
        self.assertEqual(new[5], "风属性共鸣时，每达到250连击，自身技能伤害＋20%")
        self.assertIn("冷却时间：6秒", new[4])

    def test_panel_agrees_with_the_data(self):
        rows = self.out["leader"][M.LEADER_KEY]
        pct = lambda value: f"＋{int(value) // 1000}%"    # noqa: E731
        lines = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertIn(f"技能充能速度{pct(rows[10][49])}、技能槽最大值{pct(rows[11][49])}、"
                      f"技能伤害额外乘区{pct(rows[12][49])}", lines[2])
        self.assertIn(f"攻击力{pct(rows[4][49])}、技能伤害{pct(rows[5][49])}、连击＋{int(rows[6][49]) // 100000}",
                      lines[3])
        self.assertIn(f"自身技能伤害{pct(rows[9][49])}", lines[5])

    def test_panel_text_obeys_the_project_rules(self):
        text = self.out["cas"][M.CAS_LEADER][0][0]
        self.assertNotIn("／", text)
        self.assertEqual(M.panel_problems(text), [])
        self.assertEqual(L.panel_override_capability(M.CAS_LEADER), "panel-description-override-v2")
        for line in text.split("\n"):
            self.assertEqual(KL.panel_problems(line), [], line)
            self.assertFalse(line.startswith(K.MAIN_ICON), line)       # 队长面板不带主位图标
            for word in ("可无限", "无上限", "自身为队长时", "生命值100%以下", "(None)"):
                self.assertNotIn(word, line)

    # ------------------------------------------------------------ 合法性

    def test_native_legality_gates_are_empty(self):
        cas_keys = set(K.CAS_TEXTS)
        for index, row in enumerate(self.out["leader"][M.LEADER_KEY]):
            label = f"leader#{index}"
            self.assertEqual(L.client_legality_problems("leader_ability", row), [], label)
            self.assertEqual(L.declared_block_field_problems("leader_ability", row), [], label)
            self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, "leader_ability"), [], label)
            self.assertEqual(KL.row_problems("leader_ability", row), {}, label)
            self.assertLessEqual(set(L.required_client_capabilities("leader_ability", row)),
                                 CANDIDATE_CAPABILITIES, label)

    # ------------------------------------------------------------ DSL

    def test_skill_tiers_change_only_the_eight_pestle_p13(self):
        for program in M.SKILL_PROGRAMS:
            old, new = self.old("dsl", program), self.out["dsl"][program]
            self.assertEqual(len(tree_diff(old, new)), 16, program)     # 8 条 CNA × {min, max}
            self.assertEqual(p13s(old)[1:9], [6.25] * 8)
            self.assertEqual(p13s(new)[1:9], [1.5] * 8)
            self.assertEqual(p13s(new)[:1] + p13s(new)[9:], p13s(old)[:1] + p13s(old)[9:])
            self.assertEqual(per_cast(old), 65.0)
            self.assertEqual(per_cast(new), 27.0)                        # 口径 B.1：≤30
            for a, b in zip(wf_dsl.iter_dsl_commands(old, "CreateNormalAttack"),
                            wf_dsl.iter_dsl_commands(new, "CreateNormalAttack")):
                self.assertEqual(a[:13] + a[14:], b[:13] + b[14:])

    def test_invoke_tree_sets_every_p13_to_the_629_value(self):
        old, new = self.old("dsl", M.INVOKE_PROGRAM), self.out["dsl"][M.INVOKE_PROGRAM]
        self.assertEqual(len(tree_diff(old, new)), 22)                   # 11 条 CNA × {min, max}
        self.assertEqual(p13s(new), [0.15] * 11)
        self.assertEqual(per_cast(old), 65.0)
        self.assertEqual(per_cast(new), 2.85)                            # 口径 B.3：CT 6/12 秒 ⇒ ≤3
        self.assertEqual(self.out["notes"]["invoke_ct"],
                         {"leader_L8_frames": 360, "ability3_row2_frames": 720, "min_seconds": 6.0,
                          "cap_per_call": 3})
        # 629 树 = 技能档 2 ＋ p13 覆盖
        expected = deepcopy(self.out["dsl"][M.SKILL_PROGRAMS[1]])
        for cna in wf_dsl.iter_dsl_commands(expected, "CreateNormalAttack"):
            cna[13] = [{"min": 0.15, "max": 0.15}]
        self.assertEqual(new, expected)

    def test_dsl_roundtrip_and_gates(self):
        for program, tree in self.out["dsl"].items():
            self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree, program)
            self.assertTrue(encode_tree(tree))
            self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [], program)
            self.assertEqual(L.action_dsl_subject_binding_problems(tree), [], program)
            self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [], program)
            self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [], program)
            self.assertEqual(K.dsl_problems(tree, element=K.ELEMENT), [], program)
            self.assertEqual(K.roundtrip_problems(tree), [], program)

    # ------------------------------------------------------------ fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["leader"][M.LEADER_KEY][4][49] = "mutated"
        out["cas"][M.CAS_LEADER][0][0] = "mutated"
        for tree in out["dsl"].values():
            next(iter(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")))[13] = "x"
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        for kind, key in M.BEFORE:
            data = deepcopy(self.live)
            value = data[kind][key]
            if kind == "cas":
                value[0][0] += "。"
            elif kind == "dsl":
                value[10] = 3
            else:
                value[0][0] += "x"
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline"):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        for kind in ("leader", "cas", "dsl"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.leader_rows(self.out["leader"][M.LEADER_KEY])
        with self.assertRaises(ValueError):
            M.leader_text(self.out["cas"][M.CAS_LEADER])
        for tree in self.out["dsl"].values():
            with self.assertRaises(ValueError):
                M.skill_tree(tree)
            with self.assertRaises(ValueError):
                M.invoke_tree(tree)

    def test_row_locators_are_content_based(self):
        leader = self.old("leader", M.LEADER_KEY)
        for mutate in (lambda r: r[4].__setitem__(32, "10"),         # 成长行加了限次
                       lambda r: r[10].__setitem__(49, "1000"),       # 充能行被动过
                       lambda r: r[8].__setitem__(33, "1200"),        # Lv3 CT 被动过
                       lambda r: r.__setitem__(slice(4, 6), [r[5], r[4]]),
                       lambda r: r.pop()):
            rows = deepcopy(leader)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.leader_rows(rows)
        data = deepcopy(self.live)
        data["ability"][M.A3_KEY][2][35] = "120"                     # 能力3 629 CT 漂移
        with self.assertRaises(ValueError):
            M.revise(reader(data))                                    # 摘要先拒
        tree = deepcopy(self.old("dsl", M.SKILL_PROGRAMS[0]))
        list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))[3][13] = [{"min": 3, "max": 3}]
        with self.assertRaises(ValueError):
            M.skill_tree(tree)


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_fluffy 重跑不能把旧值带回来。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def test_constants_mirror_the_module(self):
        self.assertEqual(K.BALANCE_B["pf_growth"], M.LEADER_CHANGES[4][1])
        self.assertEqual(K.BALANCE_B["pf_growth"], M.LEADER_CHANGES[5][1])
        self.assertEqual(K.BALANCE_B["combo_growth"], M.LEADER_CHANGES[9][1])
        self.assertEqual(K.BALANCE_B["pf3_growth"], {"35": "5000", "245": "5000", "694": M.LEADER_CHANGES[12][1]})
        self.assertEqual((K.PESTLE_DETOUGHNESS_DONOR, K.PESTLE_DETOUGHNESS), M.PESTLE_P13)
        self.assertEqual(K.INVOKE_DETOUGHNESS, M.INVOKE_P13)
        self.assertEqual(K.CNA_DETOUGHNESS, M.CNA_P13)
        self.assertEqual((K.PF_LV3_COOLTIME, K.COMBO_INVOKE_COOLTIME), (M.LEADER_629_CT, M.ABILITY3_629_CT))
        self.assertEqual(K.LEADER_ROW_COUNT, 13)

    def test_panel_constant_equals_revise_output(self):
        target = generator_target(self.out)                    # 第三轮后 = 第二批输出 + 第三轮覆盖
        self.assertEqual([[K.CAS_TEXTS[K.LEADER_OVERRIDE]]], target["cas"][M.CAS_LEADER])

    def test_leader_plan_describes_the_revised_rows(self):
        for index, row in enumerate(generator_target(self.out)["leader"][M.LEADER_KEY]):
            self.assertEqual(D.describe_line(row, "leader_ability"), K.LEADER[index][3], index)

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_leader_rows_equal_revise_output(self):
        rows, _evidence = K.build_leader_rows(_kit_ctx())
        self.assertEqual(rows, generator_target(self.out)["leader"][M.LEADER_KEY])

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_trees_equal_revise_output(self):
        import test_midautumn_kit_fluffy as T
        ctx = _kit_ctx()
        trees = {}
        for level, program in zip("12", M.SKILL_PROGRAMS):
            trees[level], gates = K.build_skill_tree(ctx, level, T.fake_families())
            self.assertEqual(trees[level], self.out["dsl"][program], program)
            self.assertEqual(gates["detoughness"]["per_cast"], 27.0)
        invoke, gates = K.build_invoke_tree(trees["2"])
        self.assertEqual(invoke, self.out["dsl"][M.INVOKE_PROGRAM])
        self.assertEqual(gates["detoughness"]["per_call"], 2.85)


class MirrorTests(unittest.TestCase):
    PATHS = (ROOT / M.DESIGN_REL, ROOT / M.PANEL_REL)

    def setUp(self):
        if not all(path.is_file() for path in self.PATHS):
            self.skipTest("midautumn design mirrors missing (work/ is gitignored)")
        self.docs = [json.loads(path.read_text(encoding="utf-8")) for path in self.PATHS]

    @unittest.skipIf(GENERATOR_AT_C, "生成器已前进到第三轮：设计镜像同步由 test_balance_20260927c_fluffy.MirrorTests 接管")
    def test_mirrors_are_already_synced(self):
        self.assertEqual(M.sync_mirrors(ROOT, write=False), [])
        design, panel = self.docs
        rows = design["rework1"]["leader_ability"]["rows"]
        for index in M.MIRROR_ROWS:
            self.assertEqual(rows[index]["cells"], {str(c): v for c, v in K.LEADER[index][2].items()})
            self.assertEqual(rows[index]["desc_expected"], K.LEADER[index][3])
        self.assertEqual(design["rework1"]["leader_ability"]["row_count"], K.LEADER_ROW_COUNT)
        self.assertEqual(design["rework1"][M.MIRROR_TAG]["module"], "mod-tools/wf_balance_20260927b_fluffy.py")
        self.assertEqual([line["text"] for line in panel["leader"]["lines"]],
                         K.CAS_TEXTS[K.LEADER_OVERRIDE].split("\n"))
        self.assertEqual(panel["notes"][-1], M.MIRROR_NOTE)

    def test_mirror_update_is_idempotent_and_pure(self):
        before = deepcopy(self.docs)
        once = M.mirror_updates(*self.docs)
        self.assertEqual(self.docs, before)
        self.assertEqual(M.mirror_updates(*once), once)


if __name__ == "__main__":
    unittest.main()
