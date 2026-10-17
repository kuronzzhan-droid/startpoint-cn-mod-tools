# -*- coding: utf-8 -*-
"""罗尔夫「不落幕的安可」149986 ``black_wolf_knight_moon`` 2026-09-27 平衡第二批。

fixture = live 输入快照（``fixtures/balance_20260927b_rolfmoon.json``，本地链尾 1.4.1049），驱动 ``revise()``：
每处改动的前后值、未改行/未改节点逐字保留、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、
合法性门禁为空、DSL AMF3 往返与四道门禁、面板规则、生成器输出 == revise() 输出、设计镜像已同步。
生成器装配对比需要 ``.cdn/cn`` 官方基线与 live store（缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_rolfmoon as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kit_rolf as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_mod_tool as core  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/balance_20260927b_rolfmoon.json"
#: 候选 ma-rolf manifest 现有的 required_capabilities（改后不新增）。
CANDIDATE_CAPABILITIES = {"dash-parameter-v1", "panel-description-override-v2"}


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
    return B.KitContext(MC.MAPack(MS.get_spec("rolf"), record_sources=False))


def cell_diff(a: list[str], b: list[str]) -> dict[int, tuple[str, str]]:
    return {i: (x, y) for i, (x, y) in enumerate(zip(a, b)) if x != y}


def tree_diff(a, b, path=()) -> list[tuple]:
    """两棵 DSL 树逐节点比较，返回不同之处的路径（类型不同也算）。"""
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


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))

    def old(self, kind, key):
        return self.live[kind][key]

    # ------------------------------------------------------------ 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys}, set(M.BEFORE))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE), (str(K.CID), K.CODE))
        self.assertEqual(M.PACKAGES, ["ma-rolf"])
        self.assertEqual(M.PACKAGE_VERSION, {"ma-rolf": "1.0.1"})     # 候选现值 1.0.0，只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertEqual(M.ENCORE_PROGRAM, K.ENCORE_PROGRAM)
        self.assertEqual((M.CAS_LEADER, M.CAS_A3), (K.CAS_LEADER, K.CAS_ABILITY[3]))
        self.assertEqual((M.ELEMENT, M.MAIN_ICON), (K.ELEMENT, K.MAIN_ICON))
        self.assertEqual(M.CAS_KEYS, frozenset(K.CAS_TEXTS))

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {M.A3_KEY, M.A6_KEY})
        self.assertEqual(set(out["leader"]), {M.LEADER_KEY})
        self.assertEqual(set(out["cas"]), {M.CAS_LEADER, M.CAS_A3})
        self.assertEqual(set(out["dsl"]), {M.ENCORE_PROGRAM})
        for kind in ("text", "table", "action", "server_text"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])
        json.dumps(out["notes"], ensure_ascii=False)
        for key in out["cas"]:                                     # RevisionCandidate 命名空间
            self.assertTrue(key.startswith("desc_override_" + M.CODE), key)

    # ------------------------------------------------------------ 队长

    def test_leader_only_the_direct_growth_cells_change(self):
        old, new = self.old("leader", M.LEADER_KEY), self.out["leader"][M.LEADER_KEY]
        self.assertEqual((len(old), len(new)), (7, 7))                # 队长表不加行（C08）
        diffs = {i: cell_diff(a, b) for i, (a, b) in enumerate(zip(old, new)) if a != b}
        self.assertEqual(diffs, {3: {49: ("100000", "20000"), 50: ("100000", "20000")},
                                 4: {49: ("100000", "20000"), 50: ("100000", "20000")}})
        for row in new:
            self.assertEqual(len(row), 124)
            self.assertNotEqual(row[25], "246")                      # 零先例触发不进队长表
        self.assertEqual((new[3][45], new[4][45]), ("32", "33"))
        self.assertEqual((new[3][25], new[3][32], new[3][33]), ("20", "(None)", "0"))

    # ------------------------------------------------------------ 能力 3 / 6

    def test_ability3_growth_rows_become_capped_holding_rows(self):
        old, new = self.old("ability", M.A3_KEY), self.out["ability"][M.A3_KEY]
        self.assertEqual((len(old), len(new)), (6, 6))
        self.assertEqual([i for i in range(6) if old[i] != new[i]], [1, 2])
        for index, kind in ((1, "0"), (2, "1")):
            row = new[index]
            self.assertEqual({i: v for i, v in enumerate(row) if v},
                             {0: f"{M.CODE}_3", 1: "false", 2: "attack_common", 3: "0", 5: "1", 6: "0",
                              13: "0", 20: "0", 85: "(None)", 97: "214", 108: "false", 109: kind,
                              110: "0", 113: "100000", 114: "100000"})
            self.assertEqual((old[index][27], old[index][34], old[index][47]),
                             ("246", "(None)", "32" if index == 1 else "33"))
        self.assertEqual(new[4][35], "300")                          # 629 CT 5 秒不动
        self.assertEqual(len({(r[0], r[1], r[2]) for r in new}), 1)  # 整键主位仍一致

    def test_ability6_ic693_slows_and_the_246_rows_are_carried_behind_leader_gate(self):
        old, new = self.old("ability", M.A6_KEY), self.out["ability"][M.A6_KEY]
        self.assertEqual((len(old), len(new)), (5, 7))
        self.assertEqual(new[:3] + new[4:5], old[:3] + old[4:5])
        self.assertEqual(cell_diff(old[3], new[3]), {51: ("10000", "2000"), 52: ("10000", "2000")})
        old_a3 = self.old("ability", M.A3_KEY)
        for carrier, source in ((new[5], old_a3[1]), (new[6], old_a3[2])):
            self.assertEqual(cell_diff(source, carrier),
                             {0: (f"{M.CODE}_3", f"{M.CODE}_6"), 1: ("false", "true"),
                              2: ("attack_common", "special"), 6: ("0", "42"),
                              51: ("50000", "5000"), 52: ("50000", "5000")})
            self.assertEqual((carrier[27], carrier[32], carrier[34], carrier[35]),
                             ("246", "6000000", "(None)", "0"))
            self.assertEqual((carrier[13], carrier[20]), ("0", "0"))  # 原行无共鸣前置，承载行也不加
        self.assertEqual([r[47] for r in new[5:]], ["32", "33"])
        self.assertEqual(len({(r[0], r[1], r[2]) for r in new}), 1)

    def test_auto_describe_renders_the_new_rows(self):
        leader = self.out["leader"][M.LEADER_KEY]
        a3, a6 = self.out["ability"][M.A3_KEY], self.out["ability"][M.A6_KEY]
        self.assertEqual(D.describe_line(leader[3], "leader_ability"),
                         "风·编成≥6 时: 编成直接攻击≥100 → 赋予全队(风) 攻击力 20%")
        self.assertEqual(D.describe_line(leader[4], "leader_ability"),
                         "风·编成≥6 时: 编成直接攻击≥100 → 赋予全队(风) Direct伤害 20%")
        self.assertEqual(D.describe_line(a3[1], "ability"), "持续·状态Fixed速度↑ → 自身 攻击力 100%")
        self.assertEqual(D.describe_line(a3[2], "ability"), "持续·状态Fixed速度↑ → 自身 Direct伤害 100%")
        self.assertEqual(D.describe_line(a6[3], "ability"),
                         "队长 且 风·编成≥6 时: 编成直接攻击≥100 → 赋予全队(风) 独立乘区Direct伤害 2%")
        self.assertEqual(D.describe_line(a6[5], "ability"), "队长 时: 状态KeepFrameFixed速度↑≥1 → 自身 攻击力 5%")
        self.assertEqual(D.describe_line(a6[6], "ability"),
                         "队长 时: 状态KeepFrameFixed速度↑≥1 → 自身 Direct伤害 5%")

    # ------------------------------------------------------------ 面板

    def test_leader_panel_changes_line5_and_gains_the_keep_frame_line(self):
        old = self.old("cas", M.CAS_LEADER)[0][0].split("\n")
        rows = self.out["cas"][M.CAS_LEADER]
        self.assertEqual((len(rows), len(rows[0])), (1, 1))
        new = rows[0][0].split("\n")
        self.assertEqual(len(new), len(old) + 1)
        self.assertEqual(new[:4], old[:4])
        self.assertEqual(new[4], "风属性共鸣时：风属性角色每造成100次直接攻击，风属性角色攻击力＋20%、"
                                 "直击伤害＋20%，直击伤害额外乘区＋2%")
        self.assertEqual(new[5], "最大速度固定效果持续期间，每持续1秒，自身攻击力＋5%、直击伤害＋5%")
        self.assertEqual(new[6:], old[5:])

    def test_ability3_panel_changes_only_line2(self):
        old = self.old("cas", M.CAS_A3)[0][0].split("\n")
        new = self.out["cas"][M.CAS_A3][0][0].split("\n")
        self.assertEqual(len(new), 4)
        self.assertEqual(new[1], " <icon id='main'>  自身处于最大速度固定状态时：自身攻击力＋100%、直击伤害＋100%")
        self.assertEqual(new[:1] + new[2:], old[:1] + old[2:])

    def test_panel_agrees_with_the_data(self):
        """面板数字从数据反推（100000 = 100%）。"""
        leader = self.out["leader"][M.LEADER_KEY]
        a3, a6 = self.out["ability"][M.A3_KEY], self.out["ability"][M.A6_KEY]
        pct = lambda value: f"＋{int(value) // 1000}%"    # noqa: E731
        lines = self.out["cas"][M.CAS_LEADER][0][0].split("\n")
        self.assertIn(f"攻击力{pct(leader[3][49])}、直击伤害{pct(leader[4][49])}，"
                      f"直击伤害额外乘区{pct(a6[3][51])}", lines[4])
        self.assertIn(f"自身攻击力{pct(a6[5][51])}、直击伤害{pct(a6[6][51])}", lines[5])
        a3_line = self.out["cas"][M.CAS_A3][0][0].split("\n")[1]
        self.assertIn(f"自身攻击力{pct(a3[1][113])}、直击伤害{pct(a3[2][113])}", a3_line)

    def test_panel_texts_obey_the_project_rules(self):
        for key, rows in self.out["cas"].items():
            text = rows[0][0]
            self.assertNotIn("／", text)
            self.assertEqual(L.panel_override_capability(key), "panel-description-override-v2")
            for line in text.split("\n"):
                self.assertEqual(KL.panel_problems(line.replace(M.MAIN_ICON, "")), [], line)
                for word in ("可无限", "无上限", "自身为队长时", "生命值100%以下", "(None)"):
                    self.assertNotIn(word, line)
                self.assertEqual(line.startswith(M.MAIN_ICON), key == M.CAS_A3, line)
        self.assertEqual(M.panel_problems(self.out["cas"]), [])

    # ------------------------------------------------------------ 合法性

    def test_native_legality_gates_are_empty(self):
        cas_keys = set(K.CAS_TEXTS)
        for index, row in enumerate(self.out["leader"][M.LEADER_KEY]):
            label = f"leader#{index}"
            self.assertEqual(L.client_legality_problems("leader_ability", row), [], label)
            self.assertEqual(L.declared_block_field_problems("leader_ability", row), [], label)
            self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, "leader_ability"), [], label)
            self.assertEqual(KL.row_problems("leader_ability", row), {}, label)
        for key in (M.A3_KEY, M.A6_KEY):
            for index, row in enumerate(self.out["ability"][key]):
                label = f"ability:{key}#{index}"
                self.assertEqual(L.client_legality_problems("ability", row), [], label)
                self.assertEqual(L.declared_block_field_problems("ability", row), [], label)
                self.assertEqual(L.invoke_skill_string_problems(row, cas_keys, "ability"), [], label)
                self.assertEqual(L.ability_element_column_problems("ability", row, M.ELEMENT), [], label)
                self.assertEqual(KL.row_problems("ability", row, M.ELEMENT), {}, label)
                self.assertLessEqual(set(L.required_client_capabilities("ability", row)),
                                     CANDIDATE_CAPABILITIES, label)
        for row in self.out["ability"][M.A3_KEY][1:3] + self.out["ability"][M.A6_KEY][5:]:
            self.assertEqual(L.required_client_capabilities("ability", row), [])

    # ------------------------------------------------------------ DSL

    def test_encore_only_the_two_p13_nodes_change(self):
        old, new = self.old("dsl", M.ENCORE_PROGRAM), self.out["dsl"][M.ENCORE_PROGRAM]
        paths = tree_diff(old, new)
        self.assertEqual(len(paths), 4)                                # 两条 CNA × {min, max}
        attacks = list(wf_dsl.iter_dsl_commands(new, "CreateNormalAttack"))
        old_attacks = list(wf_dsl.iter_dsl_commands(old, "CreateNormalAttack"))
        self.assertEqual([a[13] for a in old_attacks], [[{"min": 10, "max": 10}], [{"min": 1, "max": 1}]])
        self.assertEqual([a[13] for a in attacks], [[{"min": 1.5, "max": 1.5}], [{"min": 0.1, "max": 0.1}]])
        for a, b in zip(old_attacks, attacks):
            self.assertEqual(a[:13] + a[14:], b[:13] + b[14:])
        for path in paths:
            self.assertIn(path[-1], ("min", "max"))

    def test_encore_detoughness_respects_the_629_cap(self):
        ct = int(self.out["ability"][M.A3_KEY][4][35])
        self.assertEqual(ct, 300)                                       # 5 秒 > 3 秒 ⇒ 上限 3
        notes = self.out["notes"]["encore_ct"]
        self.assertEqual(notes["cap_per_call"], 3)
        self.assertEqual(notes["per_call"], {"before": 20.0, "after": 2.5})
        tree = self.out["dsl"][M.ENCORE_PROGRAM]
        total = 0.0
        for area in wf_dsl.iter_dsl_commands(tree, "CreateHitArea"):
            hits = area[14][1]
            for attack in wf_dsl.iter_dsl_commands(area[23], "CreateNormalAttack"):
                total += attack[13][0]["max"] * hits
        self.assertAlmostEqual(total, 2.5)

    def test_encore_dsl_roundtrip_and_gates(self):
        tree = self.out["dsl"][M.ENCORE_PROGRAM]
        self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)
        self.assertTrue(encode_tree(tree))                              # 暂存脚本的编码路径（含往返断言）
        self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [])
        self.assertEqual(L.action_dsl_subject_binding_problems(tree), [])
        self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [])
        self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [])
        self.assertEqual(K.dsl_problems(tree), [])
        self.assertEqual(M.dsl_problems(tree), [])
        # F1034 / 构造名静默吞节点：官方参数形状签名逐参比对（借芙拉菲 kit 的签名门禁）
        import wf_midautumn_kit_fluffy as FK
        self.assertEqual(FK.signature_problems(tree), [])
        self.assertEqual(wf_dsl.player_side_dsl_problems(tree), [])

    # ------------------------------------------------------------ fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["leader"][M.LEADER_KEY][3][49] = "mutated"
        out["ability"][M.A6_KEY][5][51] = "mutated"
        out["ability"][M.A3_KEY][1][0] = "mutated"
        out["cas"][M.CAS_LEADER][0][0] = "mutated"
        next(iter(wf_dsl.iter_dsl_commands(out["dsl"][M.ENCORE_PROGRAM], "CreateNormalAttack")))[13] = "x"
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
        for kind in ("leader", "ability", "cas", "dsl"):
            data[kind].update(deepcopy(self.out[kind]))
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.leader_rows(self.out["leader"][M.LEADER_KEY])
        with self.assertRaises(ValueError):
            M.ability3_rows(self.out["ability"][M.A3_KEY])
        with self.assertRaises(ValueError):
            M.ability6_rows(self.out["ability"][M.A6_KEY], [])
        with self.assertRaises(ValueError):
            M.carrier_rows(self.out["ability"][M.A3_KEY])
        with self.assertRaises(ValueError):
            M.leader_text(self.out["cas"][M.CAS_LEADER])
        with self.assertRaises(ValueError):
            M.ability3_text(self.out["cas"][M.CAS_A3])
        with self.assertRaises(ValueError):
            M.encore_tree(self.out["dsl"][M.ENCORE_PROGRAM])

    def test_row_locators_are_content_based(self):
        """绕过 BEFORE 直接调纯函数：目标行形状不对也要拒绝。"""
        leader = self.old("leader", M.LEADER_KEY)
        for mutate in (lambda r: r[3].__setitem__(32, "10"), lambda r: r[4].__setitem__(46, "0"),
                       lambda r: r.__setitem__(slice(3, 5), [r[4], r[3]]), lambda r: r.pop()):
            rows = deepcopy(leader)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.leader_rows(rows)
        a3 = self.old("ability", M.A3_KEY)
        for mutate in (lambda r: r[1].__setitem__(34, "10"), lambda r: r[2].__setitem__(27, "235"),
                       lambda r: r[4].__setitem__(35, "120"), lambda r: r[1].__setitem__(80, "x")):
            rows = deepcopy(a3)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.ability3_rows(rows)
        a6 = self.old("ability", M.A6_KEY)
        for mutate in (lambda r: r[3].__setitem__(51, "20000"), lambda r: r[3].__setitem__(6, "0"),
                       lambda r: r.append(list(r[0]))):
            rows = deepcopy(a6)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.ability6_rows(rows, [])
        tree = deepcopy(self.old("dsl", M.ENCORE_PROGRAM))
        next(iter(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")))[13] = [{"min": 8, "max": 8}]
        with self.assertRaises(ValueError):
            M.encore_tree(tree)


def after_batch3(live: dict, out: dict) -> dict:
    """第三轮（wf_balance_20260927c_rolfmoon，以本模块输出为输入回调成长数值与队长面板）之后的终态：
    本模块输出 + 第三轮覆盖。生成器现在对齐这个终态（第三轮测试另行断言生成器 == 第三轮输出）。"""
    import wf_balance_20260927c_rolfmoon as C
    data = deepcopy(live)
    for kind in ("leader", "ability", "cas", "dsl"):
        data[kind].update(deepcopy(out[kind]))
    # 第三轮另读的只读键（面板合并：能力4 行与覆盖串，本批不碰）取第三轮 fixture。
    c_fixture = json.loads((FIXTURE.parent / "balance_20260927c_rolfmoon.json").read_text(encoding="utf-8"))
    for kind, key in C.BEFORE:
        data.setdefault(kind, {}).setdefault(key, deepcopy(c_fixture[kind][key]))
    batch3 = C.revise(reader(data))
    final = deepcopy(out)
    for kind in ("leader", "ability", "cas"):
        final[kind].update(batch3[kind])
    return final


class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_midautumn_kit_rolf 重跑不能把旧值带回来（第三轮后对齐「本模块输出 + 第三轮覆盖」）。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.final = after_batch3(cls.live, cls.out)

    def test_constants_mirror_the_module(self):
        self.assertEqual(K.BALANCE_B, {"direct_growth": M.DIRECT_GROWTH[1],
                                       "direct_growth_ic693": M.DIRECT_GROWTH_IC693[1],
                                       "keep_frame_growth": M.KEEP_FRAME_GROWTH[1],
                                       "hold_fixed_speed": M.HOLD_FIXED_SPEED})
        self.assertEqual(K.ENCORE_DETOUGHNESS_DONOR, {tag: old for tag, (old, _new) in M.ENCORE_DETOUGHNESS.items()})
        self.assertEqual(K.ENCORE_DETOUGHNESS, {tag: new for tag, (_old, new) in M.ENCORE_DETOUGHNESS.items()})
        self.assertEqual((K.LEADER_ROWS, K.ABILITY_RECORDS, len(K.PLAN[6])), (7, 21, 7))

    def test_panel_constants_equal_revise_output(self):
        self.assertEqual([[K.CAS_TEXTS[K.CAS_LEADER]]], self.final["cas"][M.CAS_LEADER])
        # 第三轮技能强化文案（wf_balance_20260927c_rolfmoon）以本模块的能力3 面板为输入拆行 ⇒ 生成器对齐终态。
        self.assertEqual([[K.CAS_TEXTS[K.CAS_ABILITY[3]]]], self.final["cas"][M.CAS_A3])
        import wf_balance_20260927c_rolfmoon as C
        self.assertEqual(C.ability3_text(self.out["cas"][M.CAS_A3]), self.final["cas"][M.CAS_A3])

    def test_expect_gate_matches_the_revised_rows(self):
        leader = self.final["leader"][M.LEADER_KEY]
        for index, row in enumerate(leader):
            self.assertEqual(D.describe_line(row, "leader_ability"), K.EXPECT[f"leader#{index}"], index)
        for key in (M.A3_KEY, M.A6_KEY):
            for index, row in enumerate(self.final["ability"][key]):
                self.assertEqual(D.describe_line(row, "ability"), K.EXPECT[f"{key}#{index}"], f"{key}#{index}")

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_rows_equal_revise_output(self):
        built = K.build_rows(_kit_ctx())
        self.assertEqual(built["leader"], self.final["leader"][M.LEADER_KEY])
        self.assertEqual(built["ability"][M.A3_KEY], self.out["ability"][M.A3_KEY])       # 第三轮不动能力3
        self.assertEqual(built["ability"][M.A6_KEY], self.final["ability"][M.A6_KEY])

    @unittest.skipUnless(_baseline_available(), "需要 .cdn/cn 官方基线与 live store")
    def test_generator_encore_tree_equals_revise_output(self):
        ctx = _kit_ctx()
        values = K.load_design(ctx.root)["plan_rework1"]["skills"]["values"]
        level = str(values["encore_level"])
        level_values = dict(values[level], hit_area_damage_kind=values["hit_area_damage_kind"])
        tree, gates = K.build_encore_tree(ctx, level, level_values, None)
        self.assertEqual(tree, self.out["dsl"][M.ENCORE_PROGRAM])
        self.assertEqual(gates["detoughness"]["per_cast"], 2.5)


class MirrorTests(unittest.TestCase):
    """第三轮起镜像同步移交 wf_balance_20260927c_rolfmoon（其测试断言「已同步」或「待 --write」两态）；
    本模块的 mirror_updates 只认第二批两行（镜像停在第二批时对第三轮生成器拒绝）。这里只核对第二批记录仍在镜像里。"""
    PATHS = (ROOT / M.DESIGN_REL, ROOT / M.PANEL_REL)

    def setUp(self):
        if not all(path.is_file() for path in self.PATHS):
            self.skipTest("midautumn design mirrors missing (work/ is gitignored)")
        self.docs = [json.loads(path.read_text(encoding="utf-8")) for path in self.PATHS]

    def test_batch2_record_stays_in_the_mirrors(self):
        design, panel = self.docs
        self.assertEqual(K.design_problems(design), [])
        self.assertEqual(design["plan_rework1"]["ability_records"], 21)
        self.assertEqual(design["plan_rework1"]["ability_rows_by_slot"]["6"], 7)
        block = design["rework1"][M.MIRROR_TAG]
        self.assertEqual(block["module"], "mod-tools/wf_balance_20260927b_rolfmoon.py")
        three = next(entry for entry in panel["abilities"] if entry["index"] == 3)
        self.assertEqual("\n".join(K.MAIN_ICON + line["text"] for line in three["lines"]), K.PANEL_ABILITY[3])
        self.assertIn(M.MIRROR_NOTE, panel["notes"])

    def test_batch2_mirror_update_cannot_restore_batch2_numbers(self):
        """本模块的镜像同步对第三轮生成器：镜像停在第二批时放不下第三轮队长行 ⇒ 拒绝；镜像已同步时队长行保持
        第三轮（不会改回第二批数值）。两种情况都不改输入。"""
        before = deepcopy(self.docs)
        try:
            _design, panel = M.mirror_updates(*self.docs)
        except ValueError:
            panel = None
        self.assertEqual(self.docs, before)
        if panel is not None:
            self.assertEqual("\n".join(line["text"] for line in panel["leader"]["lines"]), K.PANEL_LEADER)


if __name__ == "__main__":
    unittest.main()
