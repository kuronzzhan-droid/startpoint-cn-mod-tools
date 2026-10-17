# -*- coding: utf-8 -*-
"""特克托 139993 ``super_robot_tailcoat`` 2026-09-27 平衡第二批：无上限成长 + Down。

fixture = live 输入快照（``fixtures/balance_20260927b_tekuto.json``，BEFORE = make_read 返回值的摘要），
驱动 ``revise()``：每处改动的前后值、未改行/未改树节点逐字保留、BEFORE 漂移拒绝、不改输入、
对自身输出重跑拒绝、合法性门禁为空、DSL AMF3 往返 + 四道门禁、生成器输出 == revise() 输出。
生成器一致性需要 work/ 下的 seasonal7 设计稿与改版 plan（gitignore，缺时跳过）。
"""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_tekuto as M  # noqa: E402
import wf_balance_20260927c_tekuto as C3  # noqa: E402  第三批（叠在本批之上）
import wf_client_legality as L  # noqa: E402
import wf_describe as D  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402
import wf_seasonal7_kit_tekuto as K  # noqa: E402
import wf_tekuto_low_hp as LOW_HP  # noqa: E402
import wf_tekuto_no_endlag_revision as NE  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_tekuto.json'
DESIGN = ROOT / K.DESIGN_REL
PLAN = ROOT / K.REVISION_REL
MANIFEST = ROOT / "work/character_packs/s7-tekuto/package/manifest.json"


def load_fixture() -> dict:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {kind: value for kind, value in data.items() if not kind.startswith("_")}


def reader(data: dict):
    def read(kind, key):
        value = data[kind][key]
        if kind == "action":                         # contract：list[(inner_key, fields)]
            return [(inner, fields) for inner, fields in value]
        return value
    return read


def diff_paths(a, b, path="$", out=None) -> list[str]:
    """两棵 JSON 形树的逐叶差异路径（类型或值不同都算）。"""
    out = [] if out is None else out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)):
            diff_paths(x, y, f"{path}[{i}]", out)
    elif isinstance(a, dict) and isinstance(b, dict) and a.keys() == b.keys():
        for k in a:
            diff_paths(a[k], b[k], f"{path}.{k}", out)
    elif type(a) is not type(b) or a != b:
        out.append(path)
    return out


class ReviseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.old_leader = cls.live["leader"][M.LEADER_KEY]
        cls.new_leader = cls.out["leader"][M.LEADER_KEY]
        cls.old_ab2 = cls.live["ability"][M.ABILITY2_KEY]
        cls.new_ab2 = cls.out["ability"][M.ABILITY2_KEY]

    # ------------------------------------------------------------ 契约

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(M.digest(self.live[kind][key]), want, f"{kind}:{key}")
        self.assertEqual({(kind, key) for kind, keys in self.live.items() for key in keys},
                         set(M.BEFORE))

    def test_module_contract_exports(self):
        self.assertEqual((M.CID, M.CODE, M.ELEMENT), (K.CID, K.CODE, K.ELEMENT))
        self.assertEqual((M.UID_ENGINE, M.UID_CANNON), (K.UID_ENGINE, K.UID_CANNON))
        self.assertEqual(M.PACKAGES, ["s7-tekuto"])
        self.assertEqual(M.PACKAGE_VERSION, {"s7-tekuto": "1.0.9"})   # 候选现值 1.0.8，只升不降
        self.assertEqual(M.CAPABILITIES, [])
        self.assertEqual(M.REVIEWED_DRIFT, {})
        self.assertEqual(M.PROGRAMS, {lv: f"battle/action/skill/action/rare5/{K.CODE}${K.CODE}_{lv}"
                                      for lv in ("1", "2")})

    def test_only_changed_keys_are_returned(self):
        out = self.out
        self.assertEqual(set(out["ability"]), {M.ABILITY2_KEY})
        self.assertEqual(set(out["leader"]), {M.LEADER_KEY})
        self.assertEqual(set(out["dsl"]), set(M.PROGRAMS.values()))
        self.assertEqual(set(out["action"]), {M.CODE})
        self.assertEqual(set(out["text"]), {M.CID})
        self.assertEqual(set(out["server_text"]), {M.CID})
        for kind in ("cas", "table"):
            self.assertEqual(out[kind], {}, kind)
        self.assertEqual(out["new_programs"], [])        # 候选 manifest 已认领两档技能树
        json.dumps(out["notes"], ensure_ascii=False)

    # ------------------------------------------------------------ 队长

    def test_leader_growth_rows_slow_down_in_place(self):
        self.assertEqual((len(self.old_leader), len(self.new_leader)), (10, 12))
        want = {0: ((111, 112), "100000", "10000"), 1: ((111, 112), "200000", "20000"),
                2: ((111, 112), "5000", "500"), 8: ((49, 50), "100000", "10000")}
        for index, (cols, old, new) in want.items():
            before, after = self.old_leader[index], self.new_leader[index]
            self.assertEqual([i for i in range(124) if before[i] != after[i]], list(cols), index)
            self.assertEqual([before[c] for c in cols], [old, old], index)
            self.assertEqual([after[c] for c in cols], [new, new], index)

    def test_slow_down_ratio_follows_the_3_minute_frequency(self):
        """口径 A2（按实际次数、不按事件名称）：特克托当队长时引擎层数 3 分钟约 40–55 层（半血 60–80，
        设计稿保守估计也有 20–25 / 半血 35–45）⇒ ≥30 ⇒ 逐层行 ×1/10；半血持重炮每 120 帧一跳 20–60 次 ⇒ 1/10。"""
        self.assertEqual(M.ENGINE_LAYER_SLOWDOWN, 10)
        for index in (0, 1, 2):
            self.assertEqual(int(self.old_leader[index][111]), 10 * int(self.new_leader[index][111]))
        self.assertEqual(int(self.old_leader[8][49]), 10 * int(self.new_leader[8][49]))
        self.assertEqual(self.new_leader[8][25], "77")                       # 时间触发
        self.assertEqual(self.new_leader[8][28], "12000000")                 # 每 120 帧
        for moved, source in zip(self.new_leader[10:], self.old_ab2):
            self.assertEqual(int(source[113]), 10 * int(moved[111]))         # 50% → 5%
        notes = self.out["notes"]["frequency"]
        self.assertIn("≥30 ⇒ ×1/10", notes["engine_layers_3min"])
        self.assertIn("1/5", notes["deviation_from_design"])            # 写明与设计稿的偏离与回退值

    def test_charge_and_gauge_rows_are_untouched(self):
        """口径 A6：引擎每层的充能（during 3）/ 技能槽上限（during 124）与其余充能行原样保留。"""
        for index in (3, 4, 5, 6, 7, 9):
            self.assertEqual(self.new_leader[index], self.old_leader[index], index)
        self.assertEqual([(self.new_leader[i][107], self.new_leader[i][111]) for i in (3, 4)],
                         [("3", "5000"), ("124", "5000")])
        self.assertEqual(self.new_leader[7][45], "35")

    def test_ability2_growth_moves_to_the_leader_with_the_column_shift(self):
        """口径 A3：行 = [c0,'0',''] + 能力行[5:]（能力 c≥5 → 队长 c−2），强度 1/10，其余逐格同。"""
        for moved, source in zip(self.new_leader[10:], self.old_ab2):
            self.assertEqual(len(moved), 124)
            self.assertEqual(moved[:3], [M.CODE, "0", ""])
            for col in range(5, 126):
                if col - 2 in (111, 112):
                    continue
                self.assertEqual(moved[col - 2], source[col], f"ability c{col} -> leader c{col - 2}")
            self.assertEqual([moved[111], moved[112]], ["5000", "5000"])
            self.assertEqual([moved[3], moved[95], moved[100], moved[102], moved[108]],
                             ["1", "134", "(None)", M.UID_ENGINE, "0"])
        self.assertEqual([r[107] for r in self.new_leader[10:]], ["0", "2"])
        # 不合并：队长 #0/#1 是全队(雷)＋雷共鸣前置，新行是自身、无前置
        for old_row, new_row in zip(self.new_leader[:2], self.new_leader[10:]):
            self.assertEqual(old_row[107], new_row[107])
            self.assertNotEqual((old_row[4], old_row[108]), (new_row[4], new_row[108]))

    def test_leader_panel_renders_the_new_values(self):
        lines = D.describe_rows(self.new_leader, "leader_ability")
        self.assertEqual(lines[0], "雷·编成≥6 时: 持续·状态累积计数固有≥1[固有13999301] → 赋予全队(雷) 攻击力 10%")
        self.assertEqual(lines[1], "雷·编成≥6 时: 持续·状态累积计数固有≥1[固有13999301] → 赋予全队(雷) 技能伤害 20%")
        self.assertEqual(lines[2], "雷·编成≥6 时: 持续·状态累积计数固有≥1[固有13999301] → 自身 独立乘区技能伤害 0.5%")
        self.assertTrue(lines[8].endswith("Elapsed时间≥120 → 自身 技能伤害 10%"), lines[8])
        self.assertEqual(lines[10:], ["持续·状态累积计数固有≥1[固有13999301] → 自身 攻击力 5%",
                                      "持续·状态累积计数固有≥1[固有13999301] → 自身 技能伤害 5%"])
        for line in lines:                                   # 无上限成长写到效果为止
            for word in ("无上限", "可无限", "上限"):
                self.assertNotIn(word, line)

    # ------------------------------------------------------------ 能力2

    def test_ability2_is_capped_at_ten_stacks(self):
        self.assertEqual((len(self.old_ab2), len(self.new_ab2)), (2, 2))
        for old, new, strength in zip(self.old_ab2, self.new_ab2, ("16000", "15000")):
            self.assertEqual([i for i in range(126) if old[i] != new[i]], [102, 113, 114])
            self.assertEqual([old[102], old[113], old[114]], ["(None)", "50000", "50000"])
            self.assertEqual([new[102], new[113], new[114]], ["10", strength, strength])
            self.assertEqual((new[1], new[5], new[6], new[97], new[104], new[110]),
                             ("true", "1", "0", "134", M.UID_ENGINE, "0"))
        # 满层 = 官方自身攻持续 160% / 自身技伤 150%
        self.assertEqual([int(r[102]) * int(r[113]) for r in self.new_ab2], [160000, 150000])
        self.assertEqual([D.describe_line(r, "ability") for r in self.new_ab2],
                         ["持续·状态累积计数固有≥1(限10次)[固有13999301] → 自身 攻击力 16%",
                          "持续·状态累积计数固有≥1(限10次)[固有13999301] → 自身 技能伤害 15%"])

    def test_native_legality_gates_are_empty(self):
        for kind, rows in (("leader_ability", self.new_leader), ("ability", self.new_ab2)):
            for index, row in enumerate(rows):
                label = f"{kind}#{index}"
                self.assertEqual(L.client_legality_problems(kind, row), [], label)
                self.assertEqual(L.declared_block_field_problems(kind, row), [], label)
                self.assertEqual(L.invoke_skill_string_problems(row, set(), kind=kind), [], label)
                self.assertEqual(L.ability_element_column_problems(kind, row, M.ELEMENT), [], label)
                self.assertEqual(L.required_client_capabilities(kind, row), M.CAPABILITIES, label)

    # ------------------------------------------------------------ 技能 DSL

    def test_dsl_changes_only_the_bind_cap_and_the_beam_p13(self):
        for level, program in M.PROGRAMS.items():
            before, after = self.live["dsl"][program], self.out["dsl"][program]
            paths = diff_paths(before, after)
            binds = [p for p in paths if p.endswith("[5]")]
            breaks = [p for p in paths if not p.endswith("[5]")]
            self.assertEqual(len(binds), 11, level)
            self.assertEqual(len(breaks), 18, level)                       # 9 个 p13 × {min,max}
            self.assertTrue(all(p.endswith(("[13][0].min", "[13][0].max")) for p in breaks), breaks)
            self.assertEqual(list(wf_dsl.iter_dsl_commands(after, "BindConditionAccumulationVariable")),
                             [M.BIND_AFTER] * 11)
            self.assertEqual(M.BIND_AFTER[:5], M.BIND_BEFORE[:5])
            self.assertEqual((M.BIND_BEFORE[5], M.BIND_AFTER[5]), (99, 10))
        self.assertEqual(diff_paths(*[self.live["dsl"][p] for p in M.PROGRAMS.values()]),
                         diff_paths(*[self.out["dsl"][p] for p in M.PROGRAMS.values()]))

    def test_beam_attacks_and_kept_attacks(self):
        for program in M.PROGRAMS.values():
            tree = self.out["dsl"][program]
            areas = M.hit_areas(tree)
            beams = [(a, g) for a, g in areas if M._is_beam(a, g)]
            self.assertEqual(sorted(g for _a, g in beams), [False] * 4 + [True] * 5)
            for area, _gated in beams:
                attacks = M._direct_attacks(area[23])
                self.assertEqual([a[13] for a in attacks], [[{"min": 0.3, "max": 0.3}]])
                self.assertEqual([a[14] for a in attacks], [[{"min": 0.6, "max": 0.6}]])  # Fever 不动
            kept = sorted(json.dumps(a[13]) for area, gated in areas if not M._is_beam(area, gated)
                          for a in M._direct_attacks(area[23]))
            self.assertEqual(kept, sorted(json.dumps(v) for v in M.KEPT_BREAKS.values()))
            # 倍率（p6）一格不动
            before = [a[6] for a in wf_dsl.iter_dsl_commands(self.live["dsl"][program], "CreateNormalAttack")]
            after = [a[6] for a in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")]
            self.assertEqual(before, after)

    def test_down_total_is_within_the_cap(self):
        """口径 B1：技能每次施放单目标总削韧 ≤30；按 live 树重算 36/66 → 19.2/28.2。"""
        for program in M.PROGRAMS.values():
            before = M.down_census(self.live["dsl"][program])
            after = M.down_census(self.out["dsl"][program])
            self.assertEqual(before, {"ungated": 36.0, "gated": 30.0})
            self.assertEqual(after, {"ungated": 19.2, "gated": 9.0})
            self.assertLessEqual(after["ungated"] + after["gated"], 30)

    def test_engine_cap_bounds_the_growth_at_ten_stacks(self):
        """vlv 成长只读 var[1]；Bind 上限 10 ⇒ 满打倍率的层数增量 = 10 × Σ(vlv.max × 段数)。"""
        for program in M.PROGRAMS.values():
            tree = self.out["dsl"][program]
            for bind in wf_dsl.iter_dsl_commands(tree, "BindConditionAccumulationVariable"):
                self.assertEqual((bind[1], bind[2], bind[3], bind[4], bind[5]),
                                 (-17, 1, ["DCUnique", int(M.UID_ENGINE)], 1, 10))
            vids = {v["vid"] for a in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")
                    for term in a[6] for v in term.get("vlv", [])}
            self.assertEqual(vids, {1})

    def test_dsl_roundtrip_and_native_gates(self):
        import zlib
        from wf_character_revision import encode_tree
        for level, program in M.PROGRAMS.items():
            tree = self.out["dsl"][program]
            self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree, level)
            # 暂存脚本落盘用的编码（裸 deflate）同样往返一致
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))["tree"], tree, level)
            self.assertEqual(L.action_dsl_element_problems(tree, M.ELEMENT), [], level)
            self.assertEqual(L.action_dsl_subject_binding_problems(tree), [], level)
            self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [], level)
            self.assertEqual(L.action_dsl_hit_area_target_problems(tree), [], level)
            self.assertEqual(M.dsl_problems(tree), [], level)
            self.assertEqual(K.dsl_quick_problems(tree), [], level)

    # ------------------------------------------------------------ 文案

    def test_skill_description_writes_the_cap_in_all_five_places(self):
        self.assertEqual(M.NEW_DESC, M.OLD_DESC.replace("威力随其层数提升", "威力随其层数提升（最多10层）"))
        for (inner, old), (inner2, new) in zip(self.live["action"][M.CODE], self.out["action"][M.CODE]):
            self.assertEqual(inner, inner2)
            self.assertEqual([i for i in range(len(old)) if old[i] != new[i]], [1])
            self.assertEqual((old[1], new[1]), (M.OLD_DESC, M.NEW_DESC))
        for kind in ("text", "server_text"):
            old, new = self.live[kind][M.CID][0], self.out[kind][M.CID][0]
            self.assertEqual([i for i in range(12) if old[i] != new[i]], [5, 7], kind)
            self.assertEqual([new[5], new[7]], [M.NEW_DESC] * 2, kind)
        self.assertEqual(KL.panel_problems(M.NEW_DESC), [])
        self.assertEqual(NE.text_problems("skill", M.NEW_DESC), [])
        self.assertEqual(M.NEW_DESC.count("最多"), 1)

    # ------------------------------------------------------------ fail closed

    def test_input_is_not_mutated_and_output_is_detached(self):
        data = deepcopy(self.live)
        out = M.revise(reader(data))
        self.assertEqual(data, self.live)
        out["leader"][M.LEADER_KEY][0][111] = "mutated"
        next(iter(out["dsl"].values()))[11] = "mutated"
        self.assertEqual(data, self.live)

    def test_baseline_drift_is_rejected(self):
        program = M.PROGRAMS["1"]
        for kind, key, mutate in (
                ("leader", M.LEADER_KEY, lambda v: v[0].__setitem__(111, "90000")),
                ("leader", M.LEADER_KEY, lambda v: v.pop()),
                ("ability", M.ABILITY2_KEY, lambda v: v[1].__setitem__(102, "5")),
                ("dsl", program, lambda v: v.__setitem__(10, 4)),
                ("action", M.CODE, lambda v: v[0][1].__setitem__(4, "600")),
                ("text", M.CID, lambda v: v[0].__setitem__(0, "X")),
                ("server_text", M.CID, lambda v: v[0].__setitem__(7, "X"))):
            data = deepcopy(self.live)
            mutate(data[kind][key])
            with self.assertRaisesRegex(ValueError, "unreviewed live baseline", msg=f"{kind}:{key}"):
                M.revise(reader(data))

    def test_revise_is_not_reapplicable_to_its_own_output(self):
        data = deepcopy(self.live)
        for kind in ("leader", "ability", "dsl", "text", "server_text"):
            data[kind].update(deepcopy(self.out[kind]))
        data["action"][M.CODE] = [[inner, fields] for inner, fields in self.out["action"][M.CODE]]
        with self.assertRaises(ValueError):
            M.revise(reader(data))
        with self.assertRaises(ValueError):
            M.ability2_rows(self.new_ab2)
        with self.assertRaises(ValueError):
            M.leader_rows(self.new_leader[:10], self.old_ab2)
        for program in M.PROGRAMS.values():
            with self.assertRaises(ValueError):
                M.revise_tree(self.out["dsl"][program], "x")
        with self.assertRaises(ValueError):
            M.revise_texts(self.out["action"][M.CODE], deepcopy(self.out["text"][M.CID]),
                           deepcopy(self.out["server_text"][M.CID]))

    def test_row_locators_are_content_based(self):
        """绕过 BEFORE 直接调纯函数：行形状不对也要拒绝。"""
        for mutate in (lambda r: r[0].__setitem__(110, "5"),          # 目标变全队
                       lambda r: r[1].__setitem__(80, "x"),           # 多出非空列
                       lambda r: r.append(list(r[0])),                # 多一条记录
                       lambda r: r.reverse()):                        # 行序变了
            rows = deepcopy(self.old_ab2)
            mutate(rows)
            with self.assertRaises(ValueError):
                M.ability2_rows(rows)
        for index, col, value in ((3, 111, "6000"), (8, 49, "90000"), (0, 108, "0"), (4, 107, "3")):
            rows = deepcopy(self.old_leader)
            rows[index][col] = value
            with self.assertRaises(ValueError):
                M.leader_rows(rows, self.old_ab2)
        tree = deepcopy(self.live["dsl"][M.PROGRAMS["2"]])
        next(wf_dsl.iter_dsl_commands(tree, "BindConditionAccumulationVariable"))[5] = 50
        with self.assertRaises(ValueError):
            M.revise_tree(tree, "2")
        tree = deepcopy(self.live["dsl"][M.PROGRAMS["2"]])
        beam = next(a for a, g in M.hit_areas(tree) if M._is_beam(a, g))
        M._direct_attacks(beam[23])[0][13] = [{"min": 2, "max": 2}]
        with self.assertRaises(ValueError):
            M.revise_tree(tree, "2")


def fake_families():
    """与 clone_effect_family 返回形状一致（同 test_seasonal7_kit_tekuto.fake_families）。"""
    out = []
    for src_dir, sub, fx in K.FAMILIES:
        out.append({"src_dir": src_dir, "dst_dir": f"battle/effect/skill_unique/{K.CODE}/{sub}",
                    "donor": src_dir.rsplit("/", 1)[-1], "dst_name": sub, "copied_bases": sorted(fx)})
    return out


@unittest.skipUnless(DESIGN.is_file() and PLAN.is_file(), "seasonal7 design/revision json not present")
class GeneratorSyncTests(unittest.TestCase):
    """生成器 wf_seasonal7_kit_tekuto（+ wf_tekuto_low_hp / wf_tekuto_fast_release）重跑 == revise() 输出。

    第三批（wf_balance_20260927c_tekuto）在第六轮之后叠第七轮 apply_balance_c / balance_c_skill_tree 与新文案；
    这里只核对到第六轮为止的同一串，全链一致性（含 TEXTS）由 test_balance_20260927c_tekuto 断言。"""

    @classmethod
    def setUpClass(cls):
        cls.live = load_fixture()
        cls.out = M.revise(reader(deepcopy(cls.live)))
        cls.plan = K.load_revision_plan(ROOT)
        design = json.loads(DESIGN.read_text(encoding="utf-8"))
        cls.pre = {}
        for slot in range(1, 7):                  # 同 test_seasonal7_kit_tekuto._design_ability_rows
            key = design["ability_keys"][f"slot{slot}"]["key"]
            cls.pre[key] = [list(rec["row"]) for rec in design["abilities"][f"slot{slot}"]]

    def _generator_rows(self, current):
        ability, _trace = K.revision_ability_rows(self.plan, deepcopy(current))
        leader = K.revision_leader_rows(self.plan)
        leader, ability[f"{K.CID}3"] = LOW_HP.revise_rows(leader, ability[f"{K.CID}3"])
        leader, ability[K.REV5_ABILITY_KEY], trace = K.apply_balance_b(leader, ability[K.REV5_ABILITY_KEY])
        return leader, ability, trace

    def test_generator_rows_equal_revise_output(self):
        leader, ability, trace = self._generator_rows(self.pre)
        self.assertEqual(leader, self.out["leader"][M.LEADER_KEY])
        self.assertEqual(ability[M.ABILITY2_KEY], self.out["ability"][M.ABILITY2_KEY])
        self.assertEqual(len(trace), 6)

    def test_rerun_after_candidate_write_back_is_stable(self):
        """候选回写后包内能力2 是第二批封顶行：apply_rev5_ability2 认得它，重跑结果不变、不叠改。"""
        current = deepcopy(self.pre)
        current[M.ABILITY2_KEY] = deepcopy(self.out["ability"][M.ABILITY2_KEY])
        leader, ability, _trace = self._generator_rows(current)
        self.assertEqual(leader, self.out["leader"][M.LEADER_KEY])
        self.assertEqual(ability[M.ABILITY2_KEY], self.out["ability"][M.ABILITY2_KEY])
        before, _ = K.revision_ability_rows(self.plan, deepcopy(self.pre))
        after, _ = K.revision_ability_rows(self.plan, current)
        self.assertEqual(before, after)                     # 第五轮形态，第二批只在 build 末尾叠一次

    def test_generator_rejects_a_drifted_balance_b_input(self):
        leader = K.revision_leader_rows(self.plan)
        ability, _ = K.revision_ability_rows(self.plan, deepcopy(self.pre))
        leader, _third = LOW_HP.revise_rows(leader, ability[f"{K.CID}3"])
        broken = deepcopy(leader)
        broken[0][111] = broken[0][112] = "10000"            # 已经放缓过一次
        with self.assertRaises(K.KitError):
            K.apply_balance_b(broken, ability[K.REV5_ABILITY_KEY])
        with self.assertRaises(K.KitError):
            K.balance_b_ability2_rows(self.out["ability"][M.ABILITY2_KEY])

    def test_generator_trees_equal_revise_output(self):
        from wf_tekuto_fast_release import final_tree
        for level, program in M.PROGRAMS.items():
            tree = K.donor_tree(level, self.plan)
            for fam in fake_families():
                tree, _info = C.rewrite_effect_refs(tree, fam)
            probs, _facts = K.revision_tree_problems(tree, level, self.plan)
            self.assertEqual(probs, [], level)
            tree = final_tree(LOW_HP.revise_skill(tree))
            self.assertEqual(tree, self.out["dsl"][program], level)
        self.assertEqual((K.ENGINE_CAP, K.BEAM_BREAK), (M.BIND_AFTER[5], M.BEAM_BREAK_AFTER[0]["max"]))
        self.assertEqual((K.ENGINE_CAP_BEFORE_BALANCE_B, K.BEAM_BREAK_BEFORE_BALANCE_B),
                         (M.BIND_BEFORE[5], M.BEAM_BREAK_BEFORE[0]["max"]))

    def test_generator_texts_equal_revise_output(self):
        # 第三批落表入口是 _DESC_BALANCE_C（== 本批文案：强化后效果只写在强化条目，技能说明不重复），
        # TEXTS 的一致性移交 c 测试；本批的文案常量仍钉在 _DESC_BALANCE_B。
        self.assertEqual(K._DESC_BALANCE_B, M.NEW_DESC)
        for level in ("1", "2"):
            self.assertEqual(K.TEXTS[f"desc{level}"], C3.NEW_DESC)
        self.assertEqual(C3.OLD_DESC, M.NEW_DESC)
        self.assertEqual(K._DESC_NO_ENDLAG, M.OLD_DESC)


@unittest.skipUnless((ROOT / ".cdn" / "cn").is_dir(), "需要 .cdn/cn 官方基线")
class PrecedentTests(unittest.TestCase):
    """新进队长表的两行：during 134（按层数）→ 自身攻击力 / 自身技能伤害，官方队长表都有先例。"""

    @classmethod
    def setUpClass(cls):
        import wf_mod_tool as core
        from wf_enhancement_policy import OfficialBaseline
        baseline = OfficialBaseline(ROOT / ".cdn/cn", cache_dir=ROOT / "mod-tools/work/official-baseline",
                                    write_cache=False)
        hashed = core.sha1_path(K.LEADER)
        raw = baseline.get("common", hashed[:2] + "/" + hashed[2:])
        if raw is None:
            raise unittest.SkipTest("official leader_ability absent")
        cls.rows = [row for text in core.read_orderedmap_file_from_bytes(raw).values()
                    for row in core.read_csv_lines(text)]

    def test_leader_during_134_self_attack_and_skill_damage_have_official_precedent(self):
        during = [r for r in self.rows if r[3] == "1" and r[95] == "134"]
        self.assertGreaterEqual(len(during), 5)
        kinds = {(r[107], r[108]) for r in during}
        self.assertIn(("0", "0"), kinds)             # 自身攻击力（官方 161063#2）
        self.assertIn(("2", "0"), kinds)             # 自身技能伤害（官方 161063#3）
        # 官方 during 134 都带数字上限；本批队长两行保持 (None)（口径：无上限成长留在队长）——
        # 队长 during 134 + (None) 的 live 自制先例就是改前的队长 #0–#4（在线）。
        self.assertTrue(all(r[100] not in ("", "(None)") for r in during))


@unittest.skipUnless(MANIFEST.is_file(), "candidate workspace s7-tekuto not present")
class CandidateTests(unittest.TestCase):
    def test_package_version_only_goes_up(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        current = manifest["package_version"]
        as_tuple = lambda v: tuple(int(x) for x in v.split("."))        # noqa: E731
        # 第三批（wf_balance_20260927c_tekuto）在本批之上再升一号：回写后候选现值是其中较新的那个
        latest = max(as_tuple(M.PACKAGE_VERSION["s7-tekuto"]), as_tuple(C3.PACKAGE_VERSION["s7-tekuto"]))
        self.assertGreaterEqual(latest, as_tuple(current))
        self.assertGreater(as_tuple(M.PACKAGE_VERSION["s7-tekuto"]), (1, 0, 8))
        if manifest.get("snapshot", {}).get("revision_20260927b") is not None:
            # 已回写：候选现值 == 本模块版本（或已被第三批覆盖成第三批版本）
            self.assertIn(current, (M.PACKAGE_VERSION["s7-tekuto"], C3.PACKAGE_VERSION["s7-tekuto"]))


if __name__ == "__main__":
    unittest.main()
