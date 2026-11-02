"""Online builder regression cases; shared fixtures live in rogue_chain_support."""
from __future__ import annotations

from rogue_chain_support import *  # noqa: F403
import test_rogue_chain_gate_07 as _phase_cases
import test_rogue_chain_gate_03 as _hp_cases

class CasterCarrierGateCase(unittest.TestCase):
    """「深渊法阵」载体门禁:成对/分阶段层拒发(2026-07-30 玩家第10战打不死)。"""

    ZONE = _phase_cases.PhaseLinkedBossCase.ZONE
    FD = _phase_cases.PhaseLinkedBossCase.FD
    # 合成的代号引用名单:显式传进去,门禁就完全不碰 store —— 保持用例密闭,
    # 让没有数据包的环境(CI / 上游 fork / 别人的克隆)也能跑。
    REFS = {"hard": frozenset({"shared_boss"}), "soft": frozenset({"watched_boss"}),
            "degraded": False}

    def test_plain_field_allowed(self):
        why = rb.caster_carrier_block("f_single", ["lone_boss"],
                                      self.FD, self.ZONE, frozenset(), refs=self.REFS)
        self.assertIsNone(why)

    def test_multi_entity_zone_blocked(self):
        why = rb.caster_carrier_block("f_pair", ["form1", "form2"],
                                      self.FD, self.ZONE, frozenset(), refs=self.REFS)
        self.assertIsNotNone(why)
        self.assertIn("boss 实体", why)

    def test_phase_linked_boss_blocked_even_when_alone(self):
        """索拉斯型:这层只摆了一只,但它的转场按代号找同伴,克隆即断链。"""
        why = rb.caster_carrier_block("f_ph1", ["lich"],
                                      self.FD, self.ZONE, frozenset({"lich", "owl"}),
                                      refs=self.REFS)
        self.assertIsNotNone(why)
        self.assertIn("分阶段", why)

    def test_unknown_field_falls_back_to_boss_check(self):
        self.assertIsNone(rb.caster_carrier_block("f_ghost", ["lone_boss"],
                                                  self.FD, self.ZONE, frozenset(),
                                                  refs=self.REFS))
        self.assertIsNotNone(rb.caster_carrier_block("f_ghost", ["lich"],
                                                     self.FD, self.ZONE,
                                                     frozenset({"lich"}), refs=self.REFS))

    def test_hard_code_reference_blocked(self):
        """damage_share/enemy_watch partner 型:随从按代号认爹,克隆改名即断链
        (2026-08-03 玩家实锤:背鳍三兄弟 / 旋风巨土俑「血量下不去」)。"""
        why = rb.caster_carrier_block("f_single", ["shared_boss"],
                                      self.FD, self.ZONE, frozenset(), refs=self.REFS)
        self.assertIsNotNone(why)
        self.assertIn("按代号引用", why)

        with self.subTest("the same hard set is the single identity-lock source"):
            reason = rb.identity_locked_boss_reason(
                ["shared_boss"], code_references=self.REFS)
            self.assertIsNotNone(reason)
            self.assertIn("identity-locked", reason)
            self.assertIn("shared_boss", reason)
            self.assertIsNone(rb.identity_locked_boss_reason(
                ["watched_boss"], code_references=self.REFS))
            self.assertIsNone(rb.identity_locked_mix_reason(
                ["shared_boss"], "native_field", "native_field",
                code_references=self.REFS))
            foreign = rb.identity_locked_mix_reason(
                ["shared_boss"], "native_field", "foreign_field",
                code_references=self.REFS)
            self.assertIsNotNone(foreign)
            self.assertIn("native_field", foreign)
            self.assertIn("foreign_field", foreign)

        with self.subTest("current store keeps shark native action and damage-share links"):
            try:
                refs = rb.code_referenced_bosses()
                gb = q.load_table(rb.GENERAL_BOSS)
                gf = q.load_table(rb.GENERAL_FUNNEL)
            except FileNotFoundError:
                return
            if refs.get("degraded") or "shark" not in gb:
                return
            self.assertIn("shark", refs["hard"])
            self.assertIn("shark", refs["damage_share"])
            self.assertTrue(any(
                code.startswith("haniwa_great_wind") for code in refs["hard"]))
            if "spirit_beast_fire" in gb:
                self.assertIn("spirit_beast_fire", refs["enemy_watch_partner"])
                self.assertNotIn("spirit_beast_fire", refs["damage_share"])
                self.assertIsNone(rb.identity_clone_locked_boss_reason(
                    ["spirit_beast_fire"], code_references=refs))
            selected = rb.select_surjective_level(gb["shark"], 100)
            self.assertIsNotNone(selected)
            shark_row = rb.cells(gb["shark"][str(selected)])
            self.assertIn(
                "battle/action/enemy/action/boss_shark/boss_shark$ea1",
                shark_row[109:161])
            for fin in ("shark_blue", "shark_red", "shark_brown"):
                self.assertIn(fin, gf)
                self.assertTrue(any(
                    len(cells := rb.cells(leaf)) > rb.FUNNEL_DMGSHARE_COL
                    and cells[rb.FUNNEL_DMGSHARE_COL] == "shark"
                    for leaf in rb._leaf_rows(gf[fin])), fin)

    def test_soft_code_reference_allowed_because_watch_is_cloned(self):
        """只有 enemy_watch 自身条目的:make_caster_boss 会把 self 侧一并克隆,放行。"""
        why = rb.caster_carrier_block("f_single", ["watched_boss"],
                                      self.FD, self.ZONE, frozenset(), refs=self.REFS)
        self.assertIsNone(why)

    def test_partner_only_reference_is_alias_closed_but_still_not_relocatable(self):
        refs = {
            "hard": frozenset({"partner", "shared", "phase"}),
            "soft": frozenset(),
            "damage_share": frozenset({"shared"}),
            "enemy_watch_partner": frozenset({"partner"}),
            "boss_alive": frozenset({"phase"}),
            "degraded": False,
        }
        self.assertIsNone(rb.identity_clone_locked_boss_reason(
            ["partner"], code_references=refs))
        self.assertIsNone(rb.caster_carrier_block(
            "f_single", ["partner"], self.FD, self.ZONE,
            frozenset(), refs=refs))
        self.assertIn("damage_share", rb.identity_clone_locked_boss_reason(
            ["shared"], code_references=refs))
        self.assertIn("BossAlive", rb.identity_clone_locked_boss_reason(
            ["phase"], code_references=refs))
        # Adding a partner alias closes an in-place rename, not a terrain move:
        # the watcher/funnel entities still live in the native field.
        self.assertIsNotNone(rb.identity_locked_mix_reason(
            ["partner"], "native", "foreign", code_references=refs))

    def test_enemy_watch_partner_alias_is_additive_auditable_and_purgeable(self):
        leaf = "watch-row"
        ew = {
            "1": {
                "self_boss": {"routine": {"1": {
                    "source": {"routine": leaf}}}},
            },
            "2": {
                "funnel": {"routine": {"1": {
                    "source": {"routine": leaf}}}},
            },
        }
        before = copy.deepcopy(ew)
        self.assertEqual(rb.clone_enemy_watch_partner_aliases(
            ew, "source", "mod_rogue_boss8"), 2)
        self.assertEqual(rb.enemy_watch_partner_reference_count(
            ew, "source"), 2)
        self.assertEqual(rb.enemy_watch_partner_reference_count(
            ew, "mod_rogue_boss8"), 2)
        self.assertIsNone(rb.enemy_watch_partner_alias_error(
            ew, "source", "mod_rogue_boss8"))
        self.assertEqual(
            ew["1"]["self_boss"]["routine"]["1"]["source"],
            before["1"]["self_boss"]["routine"]["1"]["source"])
        self.assertEqual(rb.purge_enemy_watch_partner_aliases(ew), 2)
        self.assertEqual(rb.enemy_watch_partner_reference_count(
            ew, "mod_rogue_boss8"), 0)
        self.assertEqual(rb.enemy_watch_partner_reference_count(
            ew, "source"), 2)

        with self.subTest("target conflict is transactional"):
            conflict = copy.deepcopy(before)
            branch = conflict["1"]["self_boss"]["routine"]["1"]
            branch["mod_rogue_boss8"] = {"routine": "different"}
            snapshot = copy.deepcopy(conflict)
            with self.assertRaisesRegex(ValueError, "alias conflict"):
                rb.clone_enemy_watch_partner_aliases(
                    conflict, "source", "mod_rogue_boss8")
            self.assertEqual(conflict, snapshot)

    def test_degraded_refs_block_everything(self):
        """引用名单没扫全就一律拒发——名单只会偏小=漏拦,漏拦的代价是线上打不死。"""
        degraded = dict(self.REFS, degraded=True)
        why = rb.caster_carrier_block("f_single", ["lone_boss"],
                                      self.FD, self.ZONE, frozenset(), refs=degraded)
        self.assertIsNotNone(why)
        self.assertIn("降级", why)
        identity = rb.identity_locked_boss_reason(
            ["lone_boss"], code_references=degraded)
        self.assertIsNotNone(identity)
        self.assertIn("identity-locked", identity)
        self.assertIn("扫描降级", identity)


class ZoneBossSlotsCase(unittest.TestCase):
    def test_counts_entities_not_columns(self):
        zn = {"0": wave_pair(bosses=("a", "b"))}
        self.assertEqual(rb.zone_boss_slots(zn), [{"a"}, {"b"}])

        with self.subTest("terrain BOSS_GROUP objects are not a client capability"):
            caps = rbb.load_terrain_layer_caps(
                "f", {"f": "f,terrain/path,z"}, {"z": zn},
                terrain_loader=lambda _logical: {
                    "layers": [{
                        "type": "objectgroup", "name": "0",
                        "objects": [{"type": "BOSS_GROUP", "name": "fake"}],
                    }]
                })
            self.assertEqual(caps[0].boss_groups, ())

        with self.subTest("unsupported c22 topology fails closed"):
            row = wave_pair(bosses=("a", "b")).split(",")
            row[22] = "2"
            slots = rbb.active_boss_slots(
                "f", {"f": "f,terrain/path,z"}, {"z": {"0": ",".join(row)}},
                terrain_loader=lambda _logical: {
                    "layers": [{"type": "objectgroup", "name": "0", "objects": []}]
                })
            source = rbb.NativeBossBundle(
                "f", "f", "v", "v", "f", "z", "terrain/path", ("0",),
                slots, None, "", "test",
                terrain_caps=(rbb.TerrainLayerCaps(
                    "0", (1, 2), (2,), (), (), ()),))
            result = rbb.terrain_compatibility(
                source, source,
                rbb.BossTerrainRequirements(layers=(
                    rbb.LayerTerrainRequirements("0"),)))
            self.assertFalse(result.ok)
            self.assertEqual(result.reason, "BOSS_GROUP_MISMATCH")

    def test_single_multi_variants_are_one_entity(self):
        wc = wave_pair(bosses=("x_single",)).split(",")
        wc[26] = "x_multi"                      # 官方 78 处这样写
        zn = {"0": ",".join(wc)}
        self.assertEqual(rb.zone_boss_slots(zn), [{"x_single", "x_multi"}])

        with self.subTest("complete slot retains both BossKind/code pairs"):
            wc[22] = "7"
            wc[23], wc[25] = "1", "0"
            slots = rbb.active_boss_slots(
                "f",
                {"f": "f,terrain/path,z"},
                {"z": {"0": ",".join(wc)}},
                terrain_loader=lambda _logical: {
                    "layers": [{
                        "type": "objectgroup",
                        "name": "0",
                        "objects": [
                            {"type": "FUNNEL_SPAWN3", "name": ""},
                            {"type": "FUNNEL_SPAWN3", "name": ""},
                            {"type": "CUSTOM_POSITION", "name": "p0"},
                            {"type": "BOSS_GROUP", "name": "pack"},
                        ],
                    }]
                },
            )
            self.assertEqual(len(slots), 1)
            self.assertEqual(slots[0].boss_group_kind, 7)
            self.assertEqual(slots[0].single, rbb.BossRef(1, "x_single"))
            self.assertEqual(slots[0].multi, rbb.BossRef(0, "x_multi"))
            caps = rbb.load_terrain_layer_caps(
                "f", {"f": "f,terrain/path,z"}, {"z": {"0": ",".join(wc)}},
                terrain_loader=lambda _logical: {
                    "layers": [{
                        "type": "objectgroup", "name": "0",
                        "objects": [
                            {"type": "FUNNEL_SPAWN3", "name": ""},
                            {"type": "FUNNEL_SPAWN3", "name": ""},
                            {"type": "CUSTOM_POSITION", "name": "p0"},
                            {"type": "BOSS_GROUP", "name": "pack"},
                        ],
                    }]
                },
            )
            self.assertEqual(caps[0].funnel_groups, (("3", 2),))
            self.assertEqual(caps[0].custom_positions, (("p0", 1),))
            self.assertEqual(caps[0].boss_slots, (1,))

        with self.subTest("duplicate CUSTOM_POSITION names retain exact counts"):
            caps = rbb.load_terrain_layer_caps(
                "f", {"f": "f,terrain/path,z"}, {"z": {"0": ",".join(wc)}},
                terrain_loader=lambda _logical: {
                    "layers": [{
                        "type": "objectgroup", "name": "0",
                        "objects": [
                            {"type": "CUSTOM_POSITION", "name": "same"},
                            {"type": "CUSTOM_POSITION", "name": "same"},
                        ],
                    }]
                },
            )
            self.assertEqual(caps[0].custom_positions, (("same", 2),))

        with self.subTest("non-empty code without BossKind fails closed"):
            malformed = wc.copy()
            malformed[25] = ""
            with self.assertRaisesRegex(rbb.TerrainGateError, "BossKind"):
                rbb.active_boss_slots(
                    "f", {"f": "f,terrain/path,z"},
                    {"z": {"0": ",".join(malformed)}},
                    terrain_loader=lambda _logical: {
                        "layers": [{"type": "objectgroup", "name": "0", "objects": []}]
                    },
                )
            self.assertEqual(rb.zone_boss_slots({"0": ",".join(malformed)}), [])

    def test_nested_wave_skipped(self):
        self.assertEqual(rb.zone_boss_slots({"0": {"weird": "nested"}}), [])

    def test_non_dict_zone_empty(self):
        self.assertEqual(rb.zone_boss_slots("not-a-zone"), [])


class AtkCurseTierCase(unittest.TestCase):
    def test_hell_tier_matches_the_agreed_numbers(self):
        """烈狱攻击曲线、词条三级台阶与分布闸使用 2026-08-05 定档。"""
        self.assertEqual(rb.DIFF_PRESETS["hell"][2:4], (1.1, 1.1))
        self.assertEqual(rb.ATK_CURSE_TIERS["嗜血狂潮"], (1.05, 1.10, 1.15))
        self.assertEqual(rb.ATK_CURSE_TIERS["深渊逆鳞"], (1.10, 1.20, 1.30))
        self.assertEqual(rb.ATK_CURSE_TIERS["玻璃深渊"], (1.20, 1.30, 1.40))
        self.assertEqual(rb.BAND_TARGET, {"median": 1.1, "p90": 1.35, "max": 1.5})

    def test_tiers_are_a_monotone_ladder(self):
        """阶梯本身就是降档闸的台阶,不单调就降不下去。"""
        for name, tiers in rb.ATK_CURSE_TIERS.items():
            self.assertEqual(len(tiers), 3, name)
            self.assertLess(tiers[0], tiers[1], name)
            self.assertLess(tiers[1], tiers[2], name)
            self.assertGreater(tiers[0], 1.0, name)

    def test_text_always_matches_the_number(self):
        """落表值与文案同源 —— 降档后 desc 写 ×1.4 就必须真的是 ×1.4。"""
        for name in rb.ATK_CURSE_TIERS:
            for t in range(3):
                e = rb.atk_curse_entry(name, t)
                self.assertIn(f"敌攻×{e['atk']}", e["text"], (name, t))
                self.assertEqual(e["atk_tier"], t)


class DowngradeAtkCurseCase(unittest.TestCase):
    def _hell_floor(self, name):
        e = rb.atk_curse_entry(name, 2, weak=1)
        return rb.apply_picks({}, [e, {"name": "深渊重甲", "tp": 9, "text": "韧性×9"}],
                              "绞肉机")

    def test_每次调用都严格下降并最终摘除(self):
        for name in rb.ATK_CURSE_TIERS:
            curse = self._hell_floor(name)
            seen = [curse["atk"]]
            while rb.downgrade_atk_curse(curse) is not None:
                self.assertLess(curse["atk"], seen[-1], (name, seen))
                seen.append(curse["atk"])
            self.assertEqual(curse["atk"], 1.0, name)     # 收敛到无攻击诅咒
            self.assertLessEqual(len(seen), 5, name)      # 2→1→0→摘,最多 4 步

    def test_desc_follows_the_downgrade(self):
        curse = self._hell_floor("玻璃深渊")
        self.assertIn("敌攻×1.4", curse["desc"])
        rb.downgrade_atk_curse(curse)
        self.assertIn("敌攻×1.3", curse["desc"])
        self.assertNotIn("敌攻×1.4", curse["desc"])

    def test_removal_drops_the_combo_label(self):
        """【绞肉机】的承诺(血厚攻高)没了就别再挂这个名,别骗玩家。"""
        curse = self._hell_floor("嗜血狂潮")
        for _ in range(3):
            rb.downgrade_atk_curse(curse)
        self.assertNotIn("绞肉机", curse["desc"])
        self.assertIsNone(curse["combo"])

    def test_no_atk_curse_returns_none(self):
        curse = rb.apply_picks({}, [{"name": "深渊重甲", "tp": 9, "text": "韧性×9"}])
        self.assertIsNone(rb.downgrade_atk_curse(curse))

    def test_other_effects_survive_the_downgrade(self):
        """降的是攻击项,韧性/词条槽不该被顺手抹掉。"""
        curse = self._hell_floor("深渊逆鳞")
        rb.downgrade_atk_curse(curse)
        self.assertEqual(curse["tp"], 9)
        self.assertTrue(any(k == "1" for k, _v in curse["conds"]))

    def test_fixed_seed_removal_preserves_the_floor_hp_multiplier(self):
        """2026-08-05 实测陷阱:第12战血肉高墙叠玻璃深渊,摘攻击不能把血量翻倍。"""
        import random as _r
        for name in ("玻璃深渊", "嗜血狂潮", "深渊逆鳞"):
            curse = rb.abyss_curses(
                12, 30, _r.Random(20260805), "hell",
                caps={"boss": True, "element": False},
                forced={"curses": [name, "血肉高墙"]})
            hp_before = curse["hp"]
            while rb.downgrade_atk_curse(curse) is not None:
                self.assertEqual(curse["hp"], hp_before, name)
            self.assertEqual(curse["atk"], 1.0, name)

    def test_hp_audit_is_identical_before_and_after_attack_component_removal(self):
        """任务 C 不能再用目标反解绕空任务 A：摘攻击后最终 HP/DPS 必须逐项不变。"""
        curse = rb.apply_picks({}, [
            rb.atk_curse_entry("玻璃深渊", 2),
            {"name": "血肉高墙", "hp": 2.5, "text": "敌血×2.5"},
        ])
        native = {
            "native_hp": 125_000_000.0, "verified": True,
            "components": [
                {"code": "boss_a", "kind": "general",
                 "native_hp": 125_000_000.0},
            ],
        }
        general_boss = {"boss_a": {"100": "general@100"}}
        boss_level = {
            "boss_a": _hp_cases.BossLevelHpScalingCasePart1._boss_level(10_000, 1.0),
        }

        def audit():
            return rb.general_hp_scale_plan(
                ["boss_a"], native, general_boss, boss_level, 100,
                target_hp=22_500_000_000.0, curse_hp=curse["hp"],
                code_references=_hp_cases.BossLevelHpScalingCasePart1.SAFE_REFS)

        before = audit()
        while rb.downgrade_atk_curse(curse) is not None:
            pass
        after = audit()
        self.assertEqual(curse["atk"], 1.0)
        for key in ("curse_hp", "c86", "baseline_true_hp", "true_hp",
                    "baseline_leaves", "final_leaves"):
            self.assertEqual(before[key], after[key], key)


class SolveAtkCase(unittest.TestCase):
    def _rec(self, **kw):
        base = {"r": 30, "ba": 1.0, "curse": {"atk": 1.0}, "st_mult": 1.0,
                "no_base": False, "anchor": None}
        base.update(kw)
        return base

    def test_combo_cap_binds_on_base_times_curse(self):
        """solve_atk 只报告真实乘积，显式降档由 enforce_atk_band 负责。"""
        rec = self._rec(ba=3.0, curse={"atk": 2.2})
        self.assertAlmostEqual(rb.solve_atk(rec, 1.0, 1.0), 6.6)

    def test_nobase_floor_is_capped_harder(self):
        rec = self._rec(ba=3.0, curse={"atk": 1.0}, no_base=True)
        self.assertAlmostEqual(rb.solve_atk(rec, 1.0, 1.0), 3.0)

    def test_true_damage_cap_catches_the_invisible_spike(self):
        """青之女王:col 只有 1.90 却是全塔每跳最疼的一层(原生 atk ≈ 中位 3 倍)。"""
        rec = self._rec(ba=1.9, anchor=(3.0, 1.0))       # 原生是中位的 3 倍
        got = rb.solve_atk(rec, 1.0, 1.0)
        self.assertAlmostEqual(got, 1.9)

    def test_ceiling_is_the_last_backstop(self):
        rec = self._rec(ba=100.0, st_mult=100.0)
        self.assertEqual(rb.solve_atk(rec, 1.0, 1.0), 100.0)

    def test_scale_is_applied_to_the_curve(self):
        rec = self._rec(ba=1.0)
        self.assertAlmostEqual(rb.solve_atk(rec, 1.0, 1.0, scale=0.5), 0.5)


class AtkBandCase(unittest.TestCase):
    def _tower(self, cols, n=30):
        """构造中后段 col = cols 的假塔(每层都带一个顶格玻璃深渊可供降档)。"""
        recs = []
        for i, col in enumerate(cols):
            curse = rb.apply_picks({}, [rb.atk_curse_entry("玻璃深渊", 2)])
            recs.append({"r": n - len(cols) + 1 + i,
                         "ba": col / rb.ATK_CURSE_TIERS["玻璃深渊"][2],
                         "curse": curse, "st_mult": 1.0, "no_base": False,
                         "anchor": None})
        return recs

    def test_band_violation_reports_the_worst_metric_first(self):
        self.assertIsNone(rb.band_violation([1.0, 1.1, 1.35]))
        self.assertEqual(rb.band_violation([1.0, 1.0, 99.0])[0], "max")
        self.assertEqual(rb.band_violation([9.0] * 10)[0], "max")

    def test_p90_uses_nearest_rank(self):
        cols = [1.0] * 18 + [1.34, 1.5]           # n=20 → P90 = 第 18 小
        self.assertIsNone(rb.band_violation(cols))

    def test_enforce_converges_into_the_band(self):
        recs = []
        for r in range(1, 32):
            for name in rb.ATK_CURSE_TIERS:
                for tier in range(3):
                    recs.append({
                        "r": r, "ba": 1.0,
                        "curse": rb.apply_picks({}, [rb.atk_curse_entry(name, tier)]),
                        "st_mult": 9.0, "no_base": False, "anchor": None,
                    })
        _scale, log = rb.enforce_atk_band(recs, 1.1, 1.0, 31)
        self.assertIsNone(rb.band_violation([r["atk"] for r in recs]))
        self.assertTrue(all(r["atk"] <= 1.5 + 1e-9 for r in recs))
        self.assertFalse(any("单层夹到" in line for line in log), log)

    def test_enforce_prefers_downgrade_over_hard_clamp(self):
        """闸门是"降档"不是"闷头夹":有诅咒可降就别直接砍数值。"""
        recs = self._tower([4.0] * 20)
        _scale, log = rb.enforce_atk_band(recs, 1.0, 1.0, 30)
        self.assertTrue(log)
        self.assertTrue(any("×1.4→×1.3" in ln for ln in log), log[:3])
        self.assertFalse(any("单层夹到" in ln for ln in log), log[:3])

    def test_curve_scale_kicks_in_when_no_curse_left(self):
        """中后段已无攻击诅咒可降 = 基础曲线本身太热,全塔等比缩放。"""
        recs = []
        for i in range(20):
            recs.append({"r": 11 + i, "ba": 5.0, "curse": rb.apply_picks({}, []),
                         "st_mult": 1.0, "no_base": False, "anchor": None})
        scale, log = rb.enforce_atk_band(recs, 1.0, 1.0, 30)
        self.assertEqual(scale, 1.0)
        self.assertIsNone(rb.band_violation([r["atk"] for r in recs]))
        self.assertTrue(any("攻击来源" in ln for ln in log))

    def test_early_floors_are_out_of_scope(self):
        """硬上限覆盖浅层；攻击来源超标时也必须显式降档并留痕。"""
        recs = [{"r": 1, "ba": 5.0, "curse": rb.apply_picks({}, []), "st_mult": 1.0,
                 "no_base": False, "anchor": None}]
        _scale, log = rb.enforce_atk_band(recs, 1.0, 1.0, 30)
        self.assertLessEqual(recs[0]["atk"], rb.BAND_TARGET["max"])
        self.assertTrue(any("攻击来源" in line for line in log), log)


class NoBaseFloorCase(unittest.TestCase):
    def test_nobase_floor_never_gets_an_atk_curse(self):
        """standard 表 boss 归一化返回 1.0,拿到裸曲线值,原生数值不在审计视野内。
        第15/18/26/29/30 战都是这种,还叠了攻击诅咒 —— 直接从池子里摘掉。"""
        import random as _r
        for seed in range(40):
            out = rb.abyss_curses(29, 30, _r.Random(seed), "hell",
                                  caps={"boss": True}, no_base=True)
            names = [c["name"] for c in out["picks"]]
            self.assertFalse(set(names) & set(rb.ATK_CURSE_TIERS), (seed, names))
            self.assertEqual(out["atk"], 1.0, seed)

    def test_normal_floor_still_gets_them(self):
        import random as _r
        hit = 0
        for seed in range(40):
            out = rb.abyss_curses(29, 30, _r.Random(seed), "hell", caps={"boss": True})
            hit += bool(set(c["name"] for c in out["picks"]) & set(rb.ATK_CURSE_TIERS))
        self.assertGreater(hit, 0, "有基数的层不该被一起误伤")


class LevelRampCase(unittest.TestCase):
    def test_ramp_is_monotone_and_tops_out_at_100(self):
        self.assertEqual(list(rb.LEVEL_RAMP), sorted(rb.LEVEL_RAMP))
        self.assertEqual(rb.LEVEL_RAMP[-1], 100)
        self.assertLess(rb.LEVEL_RAMP[0], 100)

    def test_funnel_column_is_downgraded(self):
        """炮台弹幕同吃 boss 倍率,玩家会把它算进"boss 伤害"。"""
        self.assertLess(rb.FUNNEL_ATK_SCALE, 1.0)
        self.assertGreater(rb.FUNNEL_ATK_SCALE, 0.0)
