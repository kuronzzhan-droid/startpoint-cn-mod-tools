# -*- coding: utf-8 -*-
"""GBF 双人 2026-09-27 平衡调整第二批：索利兹 129986 / 冈达葛萨 129987。

fixture = live 输入快照（``fixtures/balance_20260927b_gbf.json``，stage_batch.make_read(live_only=True)），
驱动两个 UNITS 的 ``revise()``：每处改动前后值、未改行/未改节点逐字保留、BEFORE 漂移拒绝、不改输入、
对自身输出重跑拒绝、合法性门禁为空、DSL AMF3 往返 + 四道门禁、面板规则、生成器输出 == revise()、
设计镜像已同步、候选可干跑拼接（后三类需要 .cdn / live store / 候选工作区，缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_gbf as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402

FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_gbf.json"
TABLE = {"ability": "ability", "leader": "leader_ability"}
LEADER_FORBIDDEN = {"422", "724", "713"}           # 队长表写这三个 kind = C7050
SORIZ, GHAND = M.UNITS


def load():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return data["inputs"], data["donors"]


def reader(inputs):
    def read(kind, key):
        return inputs[kind].get(key)
    return read


def cna(tree) -> list[list]:
    return M._commands(tree, "CreateNormalAttack")


def baseline_available() -> bool:
    profile = core.resolve_profile()
    return (profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()
            and (ROOT / M.SORIZ_DESIGN_REL).is_file() and (ROOT / M.GHAND_DESIGN_REL).is_file())


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.donors = load()
        cls.pristine = deepcopy(cls.inputs)
        cls.soriz = M.revise_soriz(reader(deepcopy(cls.inputs)))
        cls.ghand = M.revise_ghandagoza(reader(deepcopy(cls.inputs)))

    def old(self, kind, key):
        return self.inputs[kind][key]


class ContractTests(Base):
    def test_fixture_is_the_reviewed_baseline(self):
        before = {**M.SORIZ_BEFORE, **M.GHAND_BEFORE}
        for (kind, key), want in before.items():
            self.assertEqual(want, M.digest(self.inputs[kind][key]), (kind, key))
        self.assertEqual({(kind, key) for kind, keys in self.inputs.items() for key in keys}, set(before))
        self.assertEqual(17, len(before))         # 12 项改写输入 + 5 条只读的 629 string_id

    def test_units_export_the_module_contract(self):
        self.assertEqual([("129986", "soriz"), ("129987", "ghandagoza")],
                         [(u["CID"], u["CODE"]) for u in M.UNITS])
        self.assertEqual(["gbf-soriz-20260919"], SORIZ["PACKAGES"])
        self.assertEqual(["gbf-ghandagoza-20260919"], GHAND["PACKAGES"])
        self.assertEqual({"gbf-soriz-20260919": "1.0.1"}, SORIZ["PACKAGE_VERSION"])   # 候选现值 1.0.0
        self.assertEqual({"gbf-ghandagoza-20260919": "1.0.1"}, GHAND["PACKAGE_VERSION"])
        for unit in M.UNITS:
            self.assertEqual([], unit["CAPABILITIES"])
            self.assertEqual({}, unit["REVIEWED_DRIFT"])
            self.assertTrue(callable(unit["revise"]))
        self.assertIs(SORIZ["revise"], M.revise_soriz)
        self.assertIs(GHAND["revise"], M.revise_ghandagoza)

    def test_only_changed_keys_are_returned(self):
        s, g = self.soriz, self.ghand
        self.assertEqual({"1299863"}, set(s["ability"]))
        self.assertEqual({"129986"}, set(s["leader"]))
        self.assertEqual({M.CAS_SORIZ_LEADER, M.CAS_SORIZ_3}, set(s["cas"]))
        self.assertEqual(set(M.ASSISTS.values()) | set(M.PF_PROGRAMS.values()), set(s["dsl"]))
        self.assertEqual({"1299874"}, set(g["ability"]))
        self.assertEqual({M.CAS_GHAND_4}, set(g["cas"]))
        for out in (s, g):
            for kind in ("text", "table", "action", "server_text"):
                self.assertEqual({}, out[kind], kind)
            self.assertEqual([], out["new_programs"])        # 援护/PF 树都已在候选 manifest 里
            self.assertFalse(out["notes"]["runtime_verified"])
            json.dumps(out["notes"], ensure_ascii=False)
        self.assertEqual({}, g["leader"])
        self.assertEqual({}, g["dsl"])
        for unit, out in ((SORIZ, s), (GHAND, g)):            # RevisionCandidate 命名空间
            for key in out["cas"]:
                self.assertTrue(key.startswith("desc_override_" + unit["CODE"]), key)
            for key in (*out["ability"], *out["leader"]):
                self.assertTrue(key.startswith(unit["CID"]), key)

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.inputs)
        out = M.revise_soriz(reader(data))
        M.revise_ghandagoza(reader(data))
        self.assertEqual(self.pristine, data)
        out["leader"]["129986"][0][0] = "mutated"
        out["ability"]["1299863"][1][113] = "mutated"
        next(iter(out["dsl"].values()))[10] = 99
        self.assertEqual(self.pristine, data)

    def test_baseline_drift_is_rejected(self):
        for unit in M.UNITS:
            for kind, key in unit["BEFORE"]:
                drifted = deepcopy(self.inputs)
                value = drifted[kind][key]
                if kind == "dsl":
                    value[10] = 4
                elif kind == "cas":
                    value[0][0] += "。"
                else:
                    value[-1][-1] += "x"
                with self.assertRaisesRegex(M.GbfBalanceError, "unreviewed live baseline"):
                    unit["revise"](reader(drifted))
                missing = deepcopy(self.inputs)
                missing[kind][key] = None
                with self.assertRaises(ValueError):
                    unit["revise"](reader(missing))

    def test_revise_rejects_its_own_output(self):
        for unit, out in ((SORIZ, self.soriz), (GHAND, self.ghand)):
            live = deepcopy(self.inputs)
            for kind in ("ability", "leader", "cas", "dsl"):
                live[kind].update(deepcopy(out[kind]))
            with self.assertRaisesRegex(M.GbfBalanceError, "unreviewed live baseline"):
                unit["revise"](reader(live))
        # 纯函数层面同样拒绝二次施加（BEFORE 之外的第二道锁）。
        s, g = self.soriz, self.ghand
        with self.assertRaises(M.GbfBalanceError):
            M.soriz_ability3(s["ability"]["1299863"])
        with self.assertRaises(M.GbfBalanceError):
            M.soriz_leader(s["leader"]["129986"], self.old("ability", "1299863"))
        with self.assertRaises(M.GbfBalanceError):
            M.soriz_leader(self.old("leader", "129986"), s["ability"]["1299863"])
        with self.assertRaises(M.GbfBalanceError):
            M.soriz_a3_text(s["cas"][M.CAS_SORIZ_3])
        with self.assertRaises(M.GbfBalanceError):
            M.soriz_leader_text(s["cas"][M.CAS_SORIZ_LEADER])
        for name, path in M.ASSISTS.items():
            with self.assertRaisesRegex(M.GbfBalanceError, "p13 preimage"):
                M.revise_assist(s["dsl"][path], name)
        for level, path in M.PF_PROGRAMS.items():
            with self.assertRaisesRegex(M.GbfBalanceError, "p13 preimage"):
                M.revise_pf(s["dsl"][path], level)
        with self.assertRaises(M.GbfBalanceError):
            M.ghand_ability4(g["ability"]["1299874"])
        with self.assertRaises(M.GbfBalanceError):
            M.ghand_text(g["cas"][M.CAS_GHAND_4])


class SorizRowTests(Base):
    def test_ability3_changes_only_the_three_crows_rows(self):
        old, new = self.old("ability", "1299863"), self.soriz["ability"]["1299863"]
        self.assertEqual(11, len(new))
        diff = {i: {c: (a[c], b[c]) for c in range(126) if a[c] != b[c]}
                for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual({
            1: {102: ("(None)", "10"), 113: ("100000", "15000"), 114: ("100000", "15000")},
            2: {102: ("(None)", "10"), 113: ("100000", "10000"), 114: ("100000", "10000")},
            3: {102: ("(None)", "10"), 113: ("3000", "1000"), 114: ("3000", "1000")},
        }, diff)
        self.assertEqual({"false"}, {r[1] for r in new})          # 整键仍主位限定
        for i in (1, 2, 3):
            row = new[i]
            self.assertEqual(("1", "134", M.CROWS, "10"), (row[5], row[97], row[104], row[102]))
        self.assertEqual(["0", "23", "413"], [new[i][109] for i in (1, 2, 3)])

    def test_leader_keeps_nine_rows_and_appends_the_moved_growth(self):
        old, new = self.old("leader", "129986"), self.soriz["leader"]["129986"]
        ability = self.old("ability", "1299863")
        self.assertEqual((9, 12), (len(old), len(new)))
        self.assertEqual(old, new[:9])
        for n, (index, kind, target, legacy, _capped, per_layer) in enumerate(M.CROWS_ROWS):
            row = new[9 + n]
            self.assertEqual(124, len(row))
            # 口径 A3：行 = [队长 c0, '0', ''] + 能力行[5:]，只改强度 c111/c112。
            expected = ["soriz_leader", "0", ""] + ability[index][5:]
            self.assertEqual(legacy, expected[111])
            self.assertEqual({111: (legacy, per_layer), 112: (legacy, per_layer)},
                             {c: (expected[c], row[c]) for c in range(124) if expected[c] != row[c]})
            self.assertEqual(("1", "134", "100000", "(None)", M.CROWS, kind, target),
                             (row[3], row[95], row[98], row[100], row[102], row[107], row[108]))
        self.assertEqual([("0", "20000"), ("23", "20000"), ("413", "500")],
                         [(r[107], r[111]) for r in new[9:]])
        self.assertFalse([r for r in new if r[45] in LEADER_FORBIDDEN or r[107] in LEADER_FORBIDDEN])

    def test_growth_is_one_fifth_and_capped_side_is_bounded(self):
        for _i, _k, _t, legacy, capped, per_layer in M.CROWS_ROWS:
            ratio = int(per_layer) / int(legacy)
            self.assertLessEqual(ratio, 0.2)
            self.assertGreater(ratio, 0.1)
            self.assertLessEqual(int(capped) * int(M.CROWS_CAP), 150000)   # 封顶后 ≤150%
        self.assertEqual("500", M.CROWS_ROWS[2][5])                        # 复核 C09：3%/5 取 0.5%

    def test_moved_leader_rows_have_leader_table_precedent(self):
        """口径 A4：进队长表的触发/kind 须有官方或 live 自制先例（零先例 = 角色页 C7050）。"""
        precedent = {(r[95], r[107]) for rows in self.donors.values() for r in rows if r[3] == "1"}
        for row in self.soriz["leader"]["129986"][9:]:
            self.assertIn((row[95], row[107]), precedent)
        inaho = self.donors["leader:139995"]
        self.assertEqual(("134", "23", ""), (inaho[4][95], inaho[4][107], inaho[4][108]))
        self.assertEqual(("134", "413", ""), (inaho[9][95], inaho[9][107], inaho[9][108]))
        self.assertEqual(("134", "0", "0"), tuple(self.donors["leader:161063"][2][i] for i in (95, 107, 108)))

    def test_assist_invoke_rows_are_unchanged_and_slow_enough(self):
        rows = self.soriz["ability"]["1299863"]
        self.assertEqual(self.old("ability", "1299863")[4:], rows[4:])
        ct = M._check_assist_rows(rows)
        self.assertEqual(15.0, ct["soriz_assist_eugen"]["cooltime_seconds"])
        self.assertEqual(15.0, ct["soriz_assist_jin"]["cooltime_seconds"])
        self.assertEqual(("187", M.DUO, "2", M.DUO), (rows[6][13], rows[6][19], rows[6][39], rows[6][45]))
        broken = deepcopy(rows)
        broken[4][35] = "120"                                              # CT 2 秒 ⇒ 口径要求 ≤1，须重审
        with self.assertRaisesRegex(M.GbfBalanceError, "assist gate drift"):
            M._check_assist_rows(broken)
        broken = deepcopy(rows)
        broken[6][39] = "(None)"                                           # 不再消耗合击预备
        with self.assertRaises(M.GbfBalanceError):
            M._check_assist_rows(broken)

    def test_row_locators_are_content_based(self):
        rows = deepcopy(self.old("ability", "1299863"))
        swapped = rows[:1] + [rows[2], rows[1]] + rows[3:]
        with self.assertRaises(M.GbfBalanceError):
            M.soriz_ability3(swapped)
        drift = deepcopy(rows)
        drift[3][113] = drift[3][114] = "3500"
        with self.assertRaises(M.GbfBalanceError):
            M.soriz_ability3(drift)
        leader = deepcopy(self.old("leader", "129986"))
        merged = leader + [M.leader_from_ability(rows[1], "soriz_leader")]
        with self.assertRaisesRegex(M.GbfBalanceError, "leader 129986: expected 9"):
            M.soriz_leader(merged, rows)

    def test_every_returned_row_passes_client_gates(self):
        strings = {key for key in M.SORIZ_INVOKE_STRINGS} | set(self.soriz["cas"])
        for kind, table in (("ability", self.soriz["ability"]), ("leader", self.soriz["leader"]),
                            ("ability", self.ghand["ability"])):
            for key, rows in table.items():
                for i, row in enumerate(rows):
                    label = f"{kind}:{key}#{i}"
                    self.assertEqual([], L.client_legality_problems(TABLE[kind], row), label)
                    self.assertEqual([], L.declared_block_field_problems(TABLE[kind], row), label)
                    self.assertEqual([], L.invoke_skill_string_problems(row, strings, TABLE[kind]), label)
                    self.assertEqual([], L.ability_element_column_problems(TABLE[kind], row, 1), label)
                    self.assertEqual({}, KL.row_problems(TABLE[kind], row, 1), label)
                    # 候选已声明 kyubi-fever-ratio-v1（能力3#8 的 724 既有行）；本批不新增 capability。
                    self.assertLessEqual(set(L.required_client_capabilities(TABLE[kind], row)),
                                         {"kyubi-fever-ratio-v1"}, label)
        changed = [self.soriz["ability"]["1299863"][i] for i in (1, 2, 3)]
        changed += [("leader", row) for row in self.soriz["leader"]["129986"][9:]]
        changed += [self.ghand["ability"]["1299874"][0]]
        for item in changed:
            kind, row = item if isinstance(item, tuple) else ("ability", item)
            self.assertEqual([], L.required_client_capabilities(TABLE[kind], row))
        invoke = self.soriz["ability"]["1299863"][4]
        self.assertTrue(L.invoke_skill_string_problems(invoke, set(), "ability"))   # 门禁确实在查


class SorizPanelTests(Base):
    def test_leader_panel_inserts_only_the_growth_line(self):
        old = self.old("cas", M.CAS_SORIZ_LEADER)[0][0].split("\n")
        rows = self.soriz["cas"][M.CAS_SORIZ_LEADER]
        self.assertEqual((1, 1), (len(rows), len(rows[0])))
        new = rows[0][0].split("\n")
        self.assertEqual(old[:1] + [M.SORIZ_LEADER_NEW_LINE] + old[1:], new)
        self.assertEqual("每层「三羽乌」使自身攻击力+20%、强化弹射伤害+20%、强化弹射伤害额外+0.5%（独立乘区）。",
                         new[1])
        self.assertFalse([line for line in new if line.startswith(M.MAIN_ICON)])   # 队长栏不画 Ⓜ

    def test_ability3_panel_splits_the_first_line_and_marks_every_line_main(self):
        old = self.old("cas", M.CAS_SORIZ_3)[0][0].split("\n")
        new = self.soriz["cas"][M.CAS_SORIZ_3][0][0].split("\n")
        self.assertEqual(5, len(new))
        for line in new:
            self.assertTrue(line.startswith(M.MAIN_ICON), line)
            self.assertEqual(1, line.count("<icon id='main'>"))
        bare = [line[len(M.MAIN_ICON):] for line in new]
        self.assertEqual(old[1:], bare[2:])
        self.assertEqual("进入FEVER时获得1层「三羽乌」，最多99层。", bare[0])
        self.assertEqual("每层「三羽乌」使自身攻击力+15%、强化弹射伤害+10%、强化弹射伤害额外+1%（独立乘区），"
                         "最多计10层。", bare[1])
        self.assertEqual(old[0], bare[0] + bare[1].replace("+15%", "+100%").replace("+10%", "+100%")
                         .replace("+1%", "+3%").replace("，最多计10层。", "。"))

    def test_panel_texts_obey_the_batch_rules(self):
        for key, rows in (*self.soriz["cas"].items(), *self.ghand["cas"].items()):
            text = rows[0][0]
            self.assertEqual([], KL.panel_problems(text), key)
            self.assertNotIn("／", text, key)
            self.assertNotIn("Ⓜ", text, key)
            for word in ("自身为队长时", "觉醒后", "生命值100%以下", "无上限", "无限叠加", "不设上限", "可无限"):
                self.assertNotIn(word, text, key)


class SorizDslTests(Base):
    def test_assist_trees_change_only_p13_from_30_to_3(self):
        for name, path in M.ASSISTS.items():
            old, new = self.old("dsl", path), self.soriz["dsl"][path]
            attacks = cna(new)
            self.assertEqual(1, len(attacks), name)
            self.assertEqual([{"min": 30, "max": 30}], cna(old)[0][13], name)
            self.assertEqual([{"min": 3, "max": 3}], attacks[0][13], name)
            restored = deepcopy(new)
            cna(restored)[0][13] = [{"min": 30, "max": 30}]
            self.assertEqual(old, restored, name)                         # 其余节点逐字保留
            self.assertEqual(3, new[10], name)                            # 伤害归属仍是强化弹射

    def test_fever_special_pf_reaches_the_per_level_caps_exactly(self):
        for level, path in M.PF_PROGRAMS.items():
            old, new = self.old("dsl", path), self.soriz["dsl"][path]
            fever_old, normal_old = M._fever_node(old, level)[1:3]
            fever_new, normal_new = M._fever_node(new, level)[1:3]
            self.assertEqual({1: 60, 2: 60, 3: 75}[level], M.pf_toughness_total(fever_old))
            self.assertEqual(M.PF_CAP[level], M.pf_toughness_total(fever_new))
            self.assertEqual({1: 15, 2: 20, 3: 25}[level], M.PF_CAP[level])
            self.assertEqual(normal_old, normal_new)                      # 官方 special 原树副本不动
            self.assertEqual(M.PF_CAP[level], M.pf_toughness_total(normal_new))
            seg, fin = M.PF_TOUGHNESS[level][1]
            areas = M._commands(fever_new, "CreateHitArea")
            self.assertEqual([11, 1], [a[14][1] for a in areas])
            self.assertEqual([[{"min": seg, "max": seg}], [{"min": fin, "max": fin}]],
                             [cna(a)[0][13] for a in areas])
            restored = deepcopy(new)
            old_seg, old_fin = M.PF_TOUGHNESS[level][0]
            fever_areas = M._commands(M._fever_node(restored, level)[1], "CreateHitArea")
            cna(fever_areas[0])[0][13] = [{"min": old_seg, "max": old_seg}]
            cna(fever_areas[1])[0][13] = [{"min": old_fin, "max": old_fin}]
            self.assertEqual(old, restored, f"lv{level}")               # 只动了两格 p13
            multipliers = [cna(a)[0][6] for a in areas]
            self.assertEqual([cna(a)[0][6] for a in M._commands(M._fever_node(old, level)[1], "CreateHitArea")],
                             multipliers)                                 # 倍率不动

    def test_dsl_gates_and_amf3_roundtrip(self):
        # 形状/表达式/作用域门（签名表见 wf_dsl_sig）：只要求「不比 live 改前多出问题」。延迟导入，
        # 免得别的单元并行改 hibiki kit 时连带整份测试导入失败。
        from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems
        for path, tree in self.soriz["dsl"].items():
            self.assertEqual([], M.dsl_problems(tree, 1), path)
            self.assertEqual([], L.action_dsl_element_problems(tree, 1), path)
            self.assertEqual([], L.action_dsl_subject_binding_problems(tree), path)
            self.assertEqual([], L.action_dsl_lookup_scope_problems(tree), path)
            self.assertEqual([], L.action_dsl_hit_area_target_problems(tree), path)
            self.assertEqual(tree, wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], path)
            encode_tree(tree)
            old_problems = kit_dsl_problems(self.old("dsl", path), element=None)
            self.assertEqual(old_problems, kit_dsl_problems(tree, element=None), path)   # 不新增形状/作用域问题

    def test_p13_keeps_the_slv_shape(self):
        """F1034：SLv 参数位写成裸数值会让技能页崩；p13 必须仍是 [{min,max}]。"""
        for path, tree in self.soriz["dsl"].items():
            for attack in cna(tree):
                cell = attack[13]
                self.assertIsInstance(cell, list, path)
                self.assertEqual(1, len(cell), path)
                self.assertEqual({"min", "max"}, set(cell[0]), path)


class GhandagozaTests(Base):
    def test_ability4_stun_accumulation_drops_to_fifty_percent(self):
        old, new = self.old("ability", "1299874"), self.ghand["ability"]["1299874"]
        self.assertEqual(3, len(new))
        diff = {i: {c: (a[c], b[c]) for c in range(126) if a[c] != b[c]}
                for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual({0: {51: ("300000", "50000"), 52: ("300000", "50000")}}, diff)
        self.assertEqual(("51", "5", "Blue"), tuple(new[0][47:50]))
        self.assertLessEqual(int(new[0][52]), 50000)                      # 口径 B4：全队 ≤50%
        self.assertEqual(["53", "118"], [new[1][47], new[2][47]])
        self.assertEqual({"true"}, {r[1] for r in new})

    def test_ability4_panel_changes_only_the_number(self):
        old = self.old("cas", M.CAS_GHAND_4)[0][0].split("\n")
        new = self.ghand["cas"][M.CAS_GHAND_4][0][0].split("\n")
        self.assertEqual(["水属性角色的气绝蓄积＋50%"] + old[1:], new)
        self.assertEqual(old[0].replace("300", "50"), new[0])
        self.assertFalse([line for line in new if "<icon id='main'>" in line])   # 非主位槽


@unittest.skipUnless(baseline_available(), "需要 .cdn/cn 官方基线、live store 与设计镜像")
class GeneratorSyncTests(Base):
    """生成器（wf_gbf_kit_soriz / wf_gbf_kit_ghandagoza + 设计镜像）重跑 == revise() 输出。"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        import wf_gbf_duo as G
        import wf_seasonal7_build as B
        cls.ctx_s = B.KitContext(G.context("soriz"))
        cls.ctx_g = B.KitContext(G.context("ghandagoza"))

    def test_soriz_rows_equal_revise_output_and_match_the_design(self):
        # 生成器已同步到第三轮（wf_balance_20260927c_soriz）：队长 #9-#11 每层强度按 c 回调，设计镜像按 c 重算
        # （c 的镜像函数接受第二批/第三轮两种磁盘形态）。期望 = 第二批输出 + 第三轮覆盖；能力3 不变。
        import wf_gbf_kit_soriz as KIT
        import wf_balance_20260927c_soriz as C3
        design = C3.soriz_mirror(KIT.load_design(self.ctx_s.root))
        leader, ability, composer = KIT.build_rows(self.ctx_s, design)
        self.assertEqual(C3.soriz_leader(self.soriz["leader"]["129986"], self.soriz["ability"]["1299863"]), leader)
        self.assertEqual(self.soriz["ability"]["1299863"], ability["1299863"])
        self.assertEqual([], KIT.design_drift(composer, design))
        self.assertEqual(sorted(KIT.CAPABILITIES),
                         sorted({c for r in composer.records for c in r["capabilities"]}
                                | {"panel-description-override-v2"}))
        self.assertEqual([(ck, legacy, capped) for ck, _n, legacy, capped, _per_layer in KIT.CROWS_GROWTH],
                         [(int(k), int(o), int(n)) for _i, k, _t, o, n, _p in M.CROWS_ROWS])
        self.assertEqual([per_layer for *_rest, per_layer in KIT.CROWS_GROWTH], [g[5] for g in C3.GROWTH])
        self.assertEqual(int(M.CROWS_CAP), KIT.CROWS_CAP)

    def test_soriz_programs_equal_revise_output(self):
        import wf_gbf_kit_soriz as KIT
        programs = KIT.build_programs(self.ctx_s)
        for path, tree in self.soriz["dsl"].items():
            self.assertEqual(tree, programs[path], path)
        self.assertEqual(M.ASSIST_TOUGHNESS[1], KIT.ASSIST_TOUGHNESS)
        self.assertEqual({lv: new for lv, (_old, new) in M.PF_TOUGHNESS.items()}, KIT.PF_FEVER_TOUGHNESS)
        # 技能本体的 p13 仍是官方 donor 的 30（口径：单段 30 ≤30 保留）。
        skill = programs[KIT.SKILL_PATH.format(KIT.CODE, "1")]
        self.assertEqual([[{"min": 30, "max": 30}]], [a[13] for a in cna(skill)])

    def test_soriz_panel_strings_equal_revise_output(self):
        import wf_gbf_kit_soriz as KIT
        import wf_balance_20260927c_soriz as C3
        strings = KIT.cas_rows(C3.soriz_mirror(KIT.load_design(self.ctx_s.root)))
        expected = deepcopy(self.soriz["cas"])
        expected[C3.CAS_LEADER] = C3.soriz_leader_text(expected[C3.CAS_LEADER])   # 第三轮只改队长面板（数字 + 面板口径 A/B/D）
        for key, rows in expected.items():
            self.assertEqual(rows, strings[key], key)

    def test_ghandagoza_rows_and_panel_equal_revise_output(self):
        import wf_gbf_kit_ghandagoza as KG
        design = KG.load_design(self.ctx_g)
        _leader, abilities, _evidence = KG.build_tables(self.ctx_g, design)
        self.assertEqual(self.ghand["ability"]["1299874"], abilities["1299874"])
        texts = {r["key"]: r["text"] for r in design["plan"]["texts"]["custom_ability_string"]["rows"]}
        expected = self.ghand["cas"][M.CAS_GHAND_4]
        import wf_balance_20260927c_panels as P3
        if P3.MODULE_TAG in design:     # 第三轮面板合并（wf_balance_20260927c_panels）已同步设计镜像：两行并一行、去「的」
            panel = P3.PANELS_BY_CAS[M.CAS_GHAND_4]
            self.assertEqual(expected, [["\n".join(panel["before"])]])
            expected = [["\n".join(panel["after"])]]
        self.assertEqual(expected, [[texts[M.CAS_GHAND_4]]])


class MirrorTests(unittest.TestCase):
    PATHS = (ROOT / M.SORIZ_DESIGN_REL, ROOT / M.GHAND_DESIGN_REL)

    def setUp(self):
        if not all(path.is_file() for path in self.PATHS):
            self.skipTest("midautumn design mirrors missing")
        self.docs = [json.loads(path.read_text(encoding="utf-8")) for path in self.PATHS]

    def test_mirrors_are_already_synced(self):
        import wf_balance_20260927c_soriz as C3
        soriz, ghand = self.docs
        # 第三轮镜像已同步时，本批镜像函数会把队长 #9-#11 改回第二批值 ⇒ 只允许 soriz 镜像报差，一致性由 c 测试接管。
        expected = [M.SORIZ_DESIGN_REL.as_posix()] if C3.MIRROR_TAG in soriz else []
        self.assertEqual(expected, M.sync_mirrors(ROOT, write=False))
        self.assertEqual(12, len(soriz["plan"]["leader_ability"]["rows"]))
        self.assertIn(M.MIRROR_TAG, soriz)
        self.assertIn(M.MIRROR_TAG, ghand)

    def test_mirror_update_is_idempotent_and_pure(self):
        before = deepcopy(self.docs)
        once = M.mirror_updates(*self.docs)
        self.assertEqual(before, self.docs)
        self.assertEqual(once, M.mirror_updates(*once))


class CandidateDryRunTests(Base):
    """候选工作区无漂移（REVIEWED_DRIFT={}）且能干跑拼接；回写后改为核对候选 == 本次输出。"""

    def _check(self, unit, out):
        workspace = ROOT / "work/character_packs" / unit["PACKAGES"][0]
        manifest = workspace / "package/manifest.json"
        if not manifest.is_file() or not (ROOT / "mod-tools/profiles.json").is_file():
            self.skipTest("local candidate workspace required")
        from wf_character_revision import RevisionCandidate
        import wf_share_update_codec as X
        import zlib
        before = manifest.read_bytes()
        current = json.loads(before)["package_version"]
        version = unit["PACKAGE_VERSION"][unit["PACKAGES"][0]]
        if unit is SORIZ:
            # 第三轮（wf_balance_20260927c_soriz）回写后：候选现值 = c 版本，内容 = 第二批输出 + 第三轮覆盖。
            import wf_balance_20260927c_soriz as C3
            if current == C3.PACKAGE_VERSION[unit["PACKAGES"][0]]:
                version = current
                out = deepcopy(out)
                out["leader"]["129986"] = C3.soriz_leader(out["leader"]["129986"], out["ability"]["1299863"])
                out["cas"][C3.CAS_LEADER] = C3.soriz_leader_text(out["cas"][C3.CAS_LEADER])
        if unit is GHAND:
            # 第三轮面板合并（wf_balance_20260927c_panels）回写后：候选再升一版，能力4 面板 = 合并稿，能力4 行不变。
            import wf_balance_20260927c_panels as P3
            if P3.staged_version(json.loads(before), unit["PACKAGES"][0]) == current:
                version = current
                out = deepcopy(out)
                out["cas"][M.CAS_GHAND_4] = [["\n".join(P3.PANELS_BY_CAS[M.CAS_GHAND_4]["after"])]]
        self.assertGreaterEqual(tuple(map(int, version.split("."))), tuple(map(int, current.split("."))))
        kwargs = dict(character_id=unit["CID"], code_name=unit["CODE"], snapshot_key="revision_20260927b",
                      package_version=version, baseline_factory=lambda *a, **k: None)
        candidate = RevisionCandidate(ROOT, workspace, reviewed_input_drift=unit["REVIEWED_DRIFT"], **kwargs)
        if json.loads(before).get("snapshot", {}).get("revision_20260927b") is not None:
            self.assertEqual(version, current)                            # 已回写：候选 == 本次输出
            for kind, logical in (("ability", "master/ability/ability.orderedmap"),
                                  ("leader", "master/ability/leader_ability.orderedmap"),
                                  ("cas", "master/string/custom_ability_string.orderedmap")):
                table = X.unpack(candidate.read("common", logical))
                for key, rows in out[kind].items():
                    self.assertEqual(rows, X.csv_read(table[key]), f"{kind}:{key}")
            for program, tree in out["dsl"].items():
                raw = candidate.read("common", wf_dsl.dsl_logical(program))
                self.assertEqual(tree, wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"], program)
            return
        for kind, logical in (("ability", "master/ability/ability.orderedmap"),
                              ("leader", "master/ability/leader_ability.orderedmap"),
                              ("cas", "master/string/custom_ability_string.orderedmap")):
            if out[kind]:
                candidate.splice(logical, out[kind])
        for program, tree in out["dsl"].items():
            candidate.emit("common", wf_dsl.dsl_logical(program), encode_tree(tree))
        evidence = candidate.finish({"dry_run": True}, apply=False)
        self.assertFalse(evidence["applied"])
        self.assertFalse(evidence["writes_live"])
        expected = sum(1 for kind in ("ability", "leader", "cas") if out[kind]) + len(out["dsl"])
        self.assertEqual(expected, len(evidence["changed_files"]))
        self.assertEqual(before, manifest.read_bytes())

    def test_soriz_candidate(self):
        self._check(SORIZ, self.soriz)

    def test_ghandagoza_candidate(self):
        self._check(GHAND, self.ghand)


if __name__ == "__main__":
    unittest.main()
