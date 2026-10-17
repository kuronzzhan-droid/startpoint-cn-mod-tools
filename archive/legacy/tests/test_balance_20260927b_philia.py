"""菲莉亚 159996 · 2026-09-27 平衡第二批（无上限成长 + Down）的修订模块回归。

fixture = live 1.4.1049（= s7-philia 1.0.11）只读快照；逐项断言改动前后值、未改行/节点逐字保留、
BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、合法性与 DSL 门禁为空、削韧合计，以及生成器
（wf_seasonal7_kit_philia → 0917 wf_seasonal_pf_revision → 本批）重跑与 revise() 一致；
一次性候选（随机 PF / 风刃 / 去浮游）对本批输出重跑不回退。
"""
from __future__ import annotations

import inspect
import json
import sys
import unittest
from copy import deepcopy
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.
pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_philia as M  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_describe  # noqa: E402
import wf_philia_no_flying_revision as NF  # noqa: E402
import wf_seasonal7_kit_philia as K  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402
from wf_philia_random_pf import revise_pf as random_pf  # noqa: E402
from wf_philia_wind_revision import revise_pf as wind_pf, revise_skill as wind_skill  # noqa: E402

HERE = Path(__file__).resolve().parent
FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_philia.json'
ROOT = HERE.parents[1]
WORKSPACE = ROOT / "work/character_packs/s7-philia"
SKILLS = tuple(M.SKILL_PROGRAMS.values())
PFS = tuple(M.PF_PROGRAMS.values())
MANIFEST_CAPS = {"kyubi-fever-ratio-v1"}


def load():
    fx = json.loads(FIXTURE.read_bytes())
    return {(kind, tuple(key) if isinstance(key, list) else key): value for kind, key, value in fx["reads"]}


def reader(data):
    return lambda kind, key: data[kind, key]


def _p13_restored(tree, attacks_of, values):
    out = deepcopy(tree)
    for group, value in zip(attacks_of(out), values):
        for attack in group:
            attack[13] = M.slv(value)
    return out


class ReviseTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()
        cls.out = M.revise(reader(cls.data))

    def live(self, kind, key):
        return deepcopy(self.data[kind, key])

    def assertOnly(self, before, after, cells):
        restored = deepcopy(after)
        for col, value in cells.items():
            restored[col] = value
        self.assertEqual(before, restored)

    # ---------------------------------------------------------------- 队长
    def test_leader_per_pf_rows_slowed_and_merged(self):
        before, after = self.live("leader", M.CID), self.out["leader"][M.CID]
        self.assertEqual((6, 8), (len(before), len(after)))
        self.assertEqual(["25000", "25000"], before[1][49:51])
        self.assertEqual(["2500", "2500"], after[1][49:51])                # 每次 PF 光队攻 25% → 2.5%（1/10）
        self.assertOnly(before[1], after[1], {49: "25000", 50: "25000"})
        self.assertEqual(["50000", "50000"], before[3][49:51])
        self.assertEqual(["7000", "7000"], after[3][49:51])                # 5%（1/10）+ 并入 2%（1/5 ÷ 5）
        self.assertOnly(before[3], after[3], {49: "50000", 50: "50000"})
        self.assertEqual(7000, 50000 // 10 + 50000 // 5 // 5)
        self.assertEqual([before[i] for i in (0, 2, 4, 5)], [after[i] for i in (0, 2, 4, 5)])
        self.assertEqual(["(None)", "(None)"], [after[1][32], after[3][32]])   # 队长侧仍不限次

    def test_moved_rows_are_ability_rows_shifted_by_two(self):
        third, after = self.live("ability", M.THIRD_KEY), self.out["leader"][M.CID]
        cast, five = after[6], after[7]
        expect = [M.CODE, "0", ""] + deepcopy(third[4][5:])
        expect[49] = expect[50] = "20000"                                  # 施放 100% × 1/5
        self.assertEqual(expect, cast)
        expect = [M.CODE, "0", ""] + deepcopy(third[5][5:])
        expect[46] = "0"                                                   # 队长（2）→ 自身（0）
        expect[49] = expect[50] = "10000"                                  # 每 5 次 PF 50% × 1/5
        self.assertEqual(expect, five)
        self.assertEqual(("23", "0", "32", "5", "White", "(None)", "0"),
                         (cast[25], cast[26], cast[45], cast[46], cast[47], cast[32], cast[33]))
        self.assertEqual(("2", "", "500000", "32", "0", "(None)", "0"),
                         (five[25], five[26], five[28], five[45], five[46], five[32], five[33]))
        described = wf_describe.describe_rows(after, "leader_ability")
        self.assertEqual("光·编成≥6 时: 技能发动≥1 → 赋予全队(光) 攻击力 20%", described[6])
        self.assertEqual("光·编成≥6 时: 强化弹射≥5 → 自身 攻击力 10%", described[7])
        self.assertEqual("光·编成≥6 时: 强化弹射≥1 → 自身 强化弹射伤害 7%", described[3])

    # ---------------------------------------------------------------- 能力 3
    def test_ability3_rows_capped(self):
        before, after = self.live("ability", M.THIRD_KEY), self.out["ability"][M.THIRD_KEY]
        self.assertEqual(7, len(after))
        self.assertEqual(before[:4], after[:4])
        for i, old in ((4, "100000"), (5, "50000")):
            self.assertEqual(("(None)", old, old), (before[i][34], before[i][51], before[i][52]))
            self.assertEqual(("8", "10000", "10000"), (after[i][34], after[i][51], after[i][52]))
            self.assertOnly(before[i], after[i], {34: "(None)", 51: old, 52: old})
        self.assertEqual("2", after[5][48])                                # 仍喂队长
        self.assertTrue(all(r[1] == "false" for r in after))               # 整键仍是主位限制
        described = wf_describe.describe_rows(after, "ability")
        self.assertEqual("光·编成≥6 时: 技能发动≥1(限8次) → 赋予全队(光) 攻击力 10%", described[4])
        self.assertEqual("光·编成≥6 时: 强化弹射≥5(限8次) → 赋予队长 攻击力 10%", described[5])

    def test_ability3_pf_row_becomes_stock_holding_bonus(self):
        before, after = self.live("ability", M.THIRD_KEY), self.out["ability"][M.THIRD_KEY]
        row = after[6]
        head = before[6][:27]
        head[5] = "1"                                                      # 瞬发 → 持续
        self.assertEqual(head, row[:27])                                   # 同键头部 + 光共鸣前置原样
        self.assertEqual([""] * (85 - 27), row[27:85])                     # 瞬发块清空
        self.assertEqual({c: v for c, v in enumerate(row) if v}, {c: v for c, v in M.THIRD_STOCK_PF_DAMAGE.items()})
        self.assertEqual(("1", "(None)", "194", "1", "15999601", "23", "", "50000"),
                         (row[5], row[85], row[97], row[102], row[104], row[109], row[110], row[113]))
        self.assertEqual("光·编成≥6 时: 持续·状态计数固有≥1(限1次)[固有15999601] → 自身 强化弹射伤害 50%",
                         wf_describe.describe_rows(after, "ability")[6])
        import wf_philia_combo_stock as stock
        self.assertEqual(str(stock.UID), M.STOCK_UID)

    def test_after_fingerprints(self):
        leader, third = self.out["leader"][M.CID], self.out["ability"][M.THIRD_KEY]
        for row, cells in ((leader[1], M.LEADER_PF_ATTACK_AFTER), (leader[3], M.LEADER_PF_DAMAGE_AFTER),
                           (leader[6], M.MOVED_CAST_ATTACK), (leader[7], M.MOVED_FIVE_PF_ATTACK)):
            self.assertTrue(M._matches(row, M.LEADER_NCOLS, cells))
        for row, cells in ((third[4], M.THIRD_CAST_ATTACK_AFTER), (third[5], M.THIRD_LEADER_ATTACK_AFTER),
                           (third[6], M.THIRD_STOCK_PF_DAMAGE)):
            self.assertTrue(M._matches(row, M.ABILITY_NCOLS, cells))
        self.assertEqual(M.LEADER_ROWS_AFTER, len(leader))
        # 放缓倍率表与落值一致（口径 A2：≥30 次 1/10，≤15 次 1/5）
        self.assertEqual({k: v[3] for k, v in M.SLOWDOWN.items()},
                         {k: v[2] // (10 if v[1] == "1/10" else 5) // (5 if k.startswith("ability3#6") else 1)
                          for k, v in M.SLOWDOWN.items()})
        self.assertEqual(int(leader[3][49]), M.SLOWDOWN["leader#3 每次PF 自身PF伤"][3]
                         + M.SLOWDOWN["ability3#6→leader#3 每5次PF 自身PF伤"][3])

    def test_official_shape_precedent_for_stock_row(self):
        """官方 1211771#1：持续 194 → 23（PF 伤害），c102=1、c110 空；块列位逐一相同。"""
        official = {5: "1", 85: "(None)", 97: "194", 98: "0", 100: "100000", 101: "100000", 102: "1",
                    108: "false", 109: "23", 110: ""}
        row = self.out["ability"][M.THIRD_KEY][6]
        self.assertEqual(official, {c: row[c] for c in official})

    def test_row_legality_and_capabilities(self):
        caps = set()
        for kind, rows in (("leader_ability", self.out["leader"][M.CID]),
                           ("ability", self.out["ability"][M.THIRD_KEY])):
            for row in rows:
                self.assertEqual([], L.client_legality_problems(kind, row))
                self.assertEqual([], L.declared_block_field_problems(kind, row))
                self.assertEqual([], L.invoke_skill_string_problems(row, set(), kind))
                self.assertEqual([], K.row_problems(kind, row))
                caps.update(L.required_client_capabilities(kind, row))
        self.assertLessEqual(caps, MANIFEST_CAPS)
        self.assertEqual([], M.CAPABILITIES)

    # ---------------------------------------------------------------- DSL
    def test_skill_rain_toughness_only(self):
        for program in SKILLS:
            before, after = self.live("dsl", program), self.out["dsl"][program]
            swords, rains = M.skill_attacks(after)
            self.assertEqual((10, 10), (len(swords), len(rains)))
            self.assertTrue(all(c[13] == M.slv(0.75) for c in swords))
            self.assertTrue(all(c[13] == M.slv(1.0) for c in rains))
            self.assertTrue(all(c[14] == M.slv(2.5) for c in rains))           # Fever 获得（p14）不动
            self.assertEqual([c[13] for c in M.skill_attacks(before)[1]], [M.slv(2.5)] * 10)
            self.assertEqual(before, _p13_restored(after, lambda t: M.skill_attacks(t)[1:], (2.5,)))
            self.assertEqual((57.5, 27.5), (M.toughness(before), M.toughness(after)))

    def test_pf_volley_toughness_zeroed_base_untouched(self):
        for level, program in M.PF_PROGRAMS.items():
            before, after = self.live("dsl", program), self.out["dsl"][program]
            base, swords, rains = M.pf_attacks(after)
            self.assertEqual((2, 180, 180), (len(base), len(swords), len(rains)))
            self.assertEqual(M.pf_attacks(before)[0], base)                    # special 底座两段爆炸不动
            self.assertTrue(all(c[13] == M.slv(0.0) for c in swords + rains))
            self.assertEqual({json.dumps(c[14]) for c in M.pf_attacks(before)[1] + M.pf_attacks(before)[2]},
                             {json.dumps(c[14]) for c in swords + rains})       # p14 不动
            self.assertEqual(before, _p13_restored(after, lambda t: M.pf_attacks(t)[1:], (0.75, 2.5)))
            self.assertEqual(M.PF_TOUGHNESS[level], (M.toughness(before), M.toughness(after)))
            self.assertEqual((15.0, 20.0, 25.0)[level - 1], M.toughness(after))

    def test_dsl_gates_are_clean(self):
        for program, tree in self.out["dsl"].items():
            encode_tree(tree)
            self.assertEqual([], M.dsl_problems(tree), program)
            self.assertEqual([], L.action_dsl_element_problems(tree, 4), program)
            self.assertEqual([], L.action_dsl_subject_binding_problems(tree), program)
            self.assertEqual([], L.action_dsl_lookup_scope_problems(tree), program)
            self.assertEqual([], L.action_dsl_hit_area_target_problems(tree), program)
            self.assertEqual([], K.dsl_gate_failures(K.dsl_gates(tree)), program)

    def test_inverse_restores_the_live_trees(self):
        for program in SKILLS + PFS:
            self.assertEqual(self.data["dsl", program], M.before_batch2(program, self.out["dsl"][program]))
            self.assertEqual(self.data["dsl", program], M.before_batch2(program, self.data["dsl", program]))
        with self.assertRaises(ValueError):
            M.before_batch2("battle/action/skill/action/rare5/other$other_1", self.out["dsl"][SKILLS[0]])

    # ---------------------------------------------------------------- 契约
    def test_only_changed_keys_are_returned(self):
        norm = lambda v: json.loads(json.dumps(v, ensure_ascii=False))
        seen = set()
        for kind in ("ability", "leader", "cas", "text", "action", "dsl", "server_text", "table"):
            for key, value in self.out[kind].items():
                self.assertIn((kind, key), self.data)
                self.assertNotEqual(norm(self.data[kind, key]), norm(value), (kind, key))
                seen.add((kind, key))
        self.assertEqual(set(M.BEFORE), seen)
        self.assertEqual([], self.out["new_programs"])
        self.assertFalse(self.out["notes"]["runtime_verified"])

    def test_baseline_drift_is_rejected_and_inputs_are_not_mutated(self):
        snapshot = deepcopy(self.data)
        M.revise(reader(self.data))
        self.assertEqual(snapshot, self.data)
        for (kind, key) in M.BEFORE:
            drifted = dict(self.data)
            value = deepcopy(drifted[kind, key])
            if kind == "dsl":
                value[1] = 3
            else:
                value[0][0] = value[0][0] + "x"
            drifted[kind, key] = value
            with self.assertRaisesRegex(ValueError, "drifted"):
                M.revise(reader(drifted))

    def test_rerun_on_own_output_is_rejected(self):
        staged = dict(self.data)
        for kind in ("ability", "leader", "dsl"):
            for key, value in self.out[kind].items():
                staged[kind, key] = value
        with self.assertRaisesRegex(ValueError, "drifted"):
            M.revise(reader(staged))
        with self.assertRaisesRegex(ValueError, "shape"):
            M.growth_rows(self.out["leader"][M.CID], self.live("ability", M.THIRD_KEY))
        with self.assertRaisesRegex(ValueError, "preimage"):
            M.growth_rows(self.live("leader", M.CID), self.out["ability"][M.THIRD_KEY])
        for program in SKILLS:
            with self.assertRaisesRegex(ValueError, "already revised"):
                M.skill_tree(self.out["dsl"][program])
        for program in PFS:
            with self.assertRaisesRegex(ValueError, "already revised"):
                M.pf_tree(self.out["dsl"][program])

    def test_unreviewed_shapes_are_rejected(self):
        third = self.live("ability", M.THIRD_KEY)
        third[6][35] = "600"                                               # 有人先给每 5 次 PF 行加了 CT
        with self.assertRaisesRegex(ValueError, "preimage"):
            M.growth_rows(self.live("leader", M.CID), third)
        leader = self.live("leader", M.CID)
        leader[3][32] = "10"
        with self.assertRaisesRegex(ValueError, "preimage"):
            M.growth_rows(leader, self.live("ability", M.THIRD_KEY))
        with self.assertRaisesRegex(ValueError, "shape"):
            M.growth_rows(self.live("leader", M.CID), self.live("ability", M.THIRD_KEY)[:5])
        tree = self.live("dsl", SKILLS[0])
        M.skill_attacks(tree)[1][0][13] = M.slv(2.0)
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            M.skill_tree(tree)
        pf = self.live("dsl", PFS[0])
        M.pf_attacks(pf)[1][0][13] = M.slv(0.5)
        with self.assertRaisesRegex(ValueError, "unreviewed"):
            M.pf_tree(pf)


class OneShotCandidatesDoNotRevert(unittest.TestCase):
    """此前的一次性候选脚本只改倍率 / 朝向 / 浮游，对本批输出重跑必须原样返回（不碰 p13）。"""

    @classmethod
    def setUpClass(cls):
        cls.out = M.revise(reader(load()))

    def test_skill_one_shots(self):
        for program in SKILLS:
            tree = self.out["dsl"][program]
            self.assertEqual(tree, wind_skill(tree))                           # wf_skill_feel / wf_philia_wind
            self.assertEqual(tree, NF.strip_flying(tree, expected=None))       # wf_philia_no_flying_revision

    def test_pf_one_shots(self):
        for program in PFS:
            tree = self.out["dsl"][program]
            self.assertEqual(tree, random_pf(tree))                            # wf_regis_philia_pf_candidate
            self.assertEqual(tree, wind_pf(tree))                              # wf_philia_wind_candidate
            self.assertEqual(tree, NF.strip_flying(tree, expected=None))

    def test_0917_row_candidate_refuses_the_revised_rows(self):
        import wf_seasonal_pf_revision as P
        with self.assertRaisesRegex(ValueError, "reviewed ability-3 rows changed"):
            P.revise_rows("philia", self.out["ability"][M.THIRD_KEY])


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

    def test_kit_build_applies_batch2_in_order(self):
        src = inspect.getsource(K.build)
        order = ["nofly_rows.ability4_rows(", "pf_revision.revise_rows('philia'", "balance_b.growth_rows(",
                 "_write_checked_flat(ctx, ABILITY, ability_rows)",
                 "_write_checked_flat(ctx, LEADER, {spec.cid_s: leader_rows})"]
        self.assertEqual(sorted(src.index(s) for s in order), [src.index(s) for s in order])
        self.assertLess(src.index("build_skill_tree(ctx, level"), src.index("balance_b.skill_tree(tree)"))
        self.assertLess(src.index("balance_b.skill_tree(tree)"), src.index("ctx.write_dsl(ctx.program_path(level)"))
        self.assertLess(src.index("tree = random_pf(tree)"), src.index("balance_b.pf_tree(tree)"))
        self.assertLess(src.index("balance_b.pf_tree(tree)"), src.index("ctx.write_dsl(PF_PROGRAMS[level - 1]"))

    @unittest.skipUnless(_design_available(), "design / official baseline / live store unavailable")
    def test_kit_rows_chain_matches_revise(self):
        from test_seasonal7_kit_philia import ReadOnlyCtx
        import wf_philia_combo_stock as stock
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
        third = P.revise_rows("philia", ability[M.THIRD_KEY])
        self.assertEqual(self.data["leader", M.CID], leader)                  # 本批输入 == kit 此前产物
        self.assertEqual(self.data["ability", M.THIRD_KEY], third)
        leader, third = M.growth_rows(leader, third)
        self.assertEqual(self.out["leader"][M.CID], leader)
        self.assertEqual(self.out["ability"][M.THIRD_KEY], third)

    @unittest.skipUnless(_design_available() and (WORKSPACE / "evidence/effect-families.json").is_file(),
                         "design / official baseline / package evidence unavailable")
    def test_kit_trees_match_revise(self):
        from test_seasonal7_kit_philia import ReadOnlyCtx
        ctx = ReadOnlyCtx()
        design, plan = K.load_design(ROOT), K.load_revision(ROOT)
        registry = json.loads((WORKSPACE / "evidence/effect-families.json").read_text(encoding="utf-8"))
        families = [registry[f"battle/effect/skill_unique/{K.CODE}/{sub}"] for sub in ("sword", "rain", "heal")]
        hashes = K.design_source_hashes(design)
        for level in ("1", "2"):
            tree, _ = K.build_skill_tree(ctx, level, K.SKILL_PARAMS[level], families, hashes)
            self.assertEqual(self.data["dsl", M.SKILL_PROGRAMS[level]], tree)
            self.assertEqual(self.out["dsl"][M.SKILL_PROGRAMS[level]], M.skill_tree(tree))
        donor = K._source_tree(ctx, f"{K.SKILL_SRC}wind_oracle_1anv$wind_oracle_1anv_2",
                               hashes[f"{K.SKILL_SRC}wind_oracle_1anv$wind_oracle_1anv_2"])
        rain_donor = K.find_one(
            K._source_tree(ctx, f"{K.SKILL_SRC}wind_oracle_meteor23$wind_oracle_meteor23_2",
                           hashes[f"{K.SKILL_SRC}wind_oracle_meteor23$wind_oracle_meteor23_2"])[11][1],
            K.is_cmd("CreateReferencePoint"), "meteor23 rain donor")
        special = K.special_source_hashes(plan)
        for level in (1, 2, 3):
            tree, _ = K.build_pf_tree(ctx, level, donor, rain_donor, families, special)
            volley = random_pf(tree)
            self.assertEqual(self.data["dsl", M.PF_PROGRAMS[level]], volley)
            self.assertEqual(self.out["dsl"][M.PF_PROGRAMS[level]], M.pf_tree(volley))


if __name__ == "__main__":
    unittest.main()
