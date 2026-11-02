"""Online builder regression cases; shared fixtures live in rogue_chain_support."""
from __future__ import annotations

from rogue_chain_support import *  # noqa: F403

class StandardBossHpCase(unittest.TestCase):
    """standard_boss 数值不在 master 行，但其 `.esdl` 的 forms 可按客户端公式审计。"""

    def test_health_termination_forms_are_summed_once(self):
        # StandardEnemySource.as:523-538：只累加 Health(index 0 / packed T1)，
        # Defeat(index 1 / packed T2) 不代表一条额外血条，不能混进基数。
        tree = {"au": [
            {"d": ["T1", 100.0]},
            {"d": ["T2", 99, "phase"]},
            {"d": ["T1", 35.5]},
        ]}
        got = rb.standard_enemy_hp_base(tree)
        self.assertEqual(got["form_count"], 3)
        self.assertEqual(got["health_terms"], (100.0, 35.5))
        self.assertEqual(got["base_hp"], 135.5)

    def test_unknown_or_malformed_termination_fails_closed(self):
        for tree in ({}, {"au": []}, {"au": [{"d": ["T9", 100]}]},
                     {"au": [{"d": ["T1", float("nan")]}]}):
            with self.assertRaises(ValueError, msg=tree):
                rb.standard_enemy_hp_base(tree)

    @staticmethod
    def _damage_check_tree() -> dict:
        return {"au": [{
            "d": ["T1", 65_000_000.0],
            "g": [
                {
                    "a": 170,
                    "b": ["T2", ["T1", ["T1", [171]]]],
                    "c": ["T2", ["T1", ["T1", [170]]]],
                    "d": ["T1", ["T1", 600]],
                    "e": 0,  # animation index; must not filter out the trial
                    "m": ["T2", {"a": 1.5, "d": True, "g": [335]}],
                },
                {
                    # A real non-damage trial uses a different Trial tag.
                    "a": 28,
                    "b": ["T2", ["T1", ["T1", [29]]]],
                    "c": ["T2", ["T1", ["T1", [28]]]],
                    "d": ["T1", ["T1", 845]],
                    "e": 17,
                    "m": ["T3", {
                        "h": ["T6", [["T2", "damage_check_a"]]],
                        "d": True,
                        "g": [93],
                    }],
                },
            ],
        }]}

    def test_damage_check_scales_percentage_but_not_other_t2_states(self):
        source = self._damage_check_tree()
        scaled = rb.scale_standard_enemy_hp_tree(source, 10.0)

        records = rb.standard_damage_check_records(scaled)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["state_id"], 170)
        self.assertEqual(records[0]["duration_frames"], 600.0)
        self.assertAlmostEqual(records[0]["percentage"], 0.15)
        self.assertEqual(scaled["au"][0]["g"][1], source["au"][0]["g"][1])

        contract = rb.standard_damage_check_contract(
            source, scaled, runtime_hp_scale=1.0)
        self.assertEqual(contract["occurrence_count"], 1)
        receipt = contract["checks"][0]
        self.assertEqual(receipt["source_absolute_threshold_hp"], 975_000.0)
        self.assertEqual(receipt["final_absolute_threshold_hp"], 975_000.0)
        self.assertEqual(receipt["duration_frames"], 600.0)
        self.assertFalse(contract["runtime_simulated"])
        self.assertFalse(contract["gameplay_verified"])

    def test_malformed_real_damage_check_fails_closed(self):
        tree = self._damage_check_tree()
        del tree["au"][0]["g"][0]["m"][1]["a"]
        with self.assertRaisesRegex(ValueError, "DamageCheck payload 非法"):
            rb.standard_damage_check_records(tree)

    def test_script_damage_threshold_is_not_silently_skipped(self):
        tree = self._damage_check_tree()
        tree["au"][0]["g"][0]["m"][1]["h"] = ["T6", [["T2", "damage_check_a"]]]
        original = copy.deepcopy(tree)
        with self.assertRaisesRegex(ValueError, "script 门槛缺独立 HP 依赖证明"):
            rb.scale_standard_enemy_hp_tree(tree, 10)
        self.assertEqual(tree, original)

    def test_dynamic_damage_trial_window_requires_independent_evidence(self):
        tree = self._damage_check_tree()
        tree["au"][0]["g"][0]["d"] = ["T6", [["T2", "trial_duration"]]]
        original = copy.deepcopy(tree)
        with self.assertRaisesRegex(ValueError, "DamageCheck 百分比/窗口/state id 非法"):
            rb.scale_standard_enemy_hp_tree(tree, 10)
        self.assertEqual(tree, original)

    def test_live_epuration_red_trials_keep_absolute_damage_thresholds(self):
        try:
            sb = q.load_table(rb.STANDARD_BOSS)
            evidence = rb.standard_boss_hp_evidence(
                "epuration_boss_dragon_main", 80, sb)
            source = rb._read_standard_enemy_dsl(evidence["logical"])
        except FileNotFoundError:
            self.skipTest("store 不可用")

        scaled = rb.scale_standard_enemy_hp_tree(source, 10.0)
        source_checks = rb.standard_damage_check_records(source)
        final_checks = rb.standard_damage_check_records(scaled)
        self.assertEqual(
            [check["percentage"] for check in source_checks], [1.5, 60.0])
        self.assertEqual(
            [check["percentage"] for check in final_checks], [0.15, 6.0])
        self.assertEqual(
            [check["duration_frames"] for check in final_checks], [600.0, 600.0])

        contract = rb.standard_damage_check_contract(
            source, scaled, runtime_hp_scale=1.0)
        self.assertEqual(contract["occurrence_count"], 2)
        self.assertEqual(
            [check["source_absolute_threshold_hp"]
             for check in contract["checks"]], [675_000.0, 27_000_000.0])
        self.assertEqual(
            [check["final_absolute_threshold_hp"]
             for check in contract["checks"]], [675_000.0, 27_000_000.0])
        self.assertTrue(contract["topology_preserved"])
        self.assertFalse(contract["runtime_simulated"])
        self.assertFalse(contract["gameplay_verified"])

    def test_live_chapter12_resource_decodes_to_700m(self):
        try:
            sb = q.load_table(rb.STANDARD_BOSS)
            got = rb.standard_boss_hp_evidence("chapter12_boss_story", 80, sb)
        except FileNotFoundError:
            self.skipTest("store 不可用")
        self.assertEqual(got["selected_level"], 80)
        self.assertTrue(got["logical"].endswith("chapter12_boss_main.esdl.amf3.deflate"))
        self.assertEqual(got["base_hp"], 700_000_000.0)
        self.assertEqual(got["health_terms"], (700_000_000.0,))

    def test_zone_pick_uses_single_battle_side_of_each_boss_slot(self):
        """rush event 是单人战：c24/28/32 与 c26/30/34 是镜像，不是两只。"""
        try:
            chapter, _ = rb._zone_pick("main_12_10_01")
            anv3, _ = rb._zone_pick("anv3")
        except FileNotFoundError:
            self.skipTest("store 不可用")
        self.assertEqual(chapter, ["chapter12_boss_story"])
        # anv3 的 single/multi 镜像代号不同；按字符串去重仍会误算成两只。
        self.assertEqual(anv3, ["anv3_big_boss_single"])

        with self.subTest("terrain inactive zone rows are ignored"):
            active = wave(bosses=("active",)).split(",")
            inactive = wave(bosses=("inactive",)).split(",")
            inactive[23] = "0"
            slots = rbb.active_boss_slots(
                "f",
                {"f": "f,terrain/path,z"},
                {"z": {"0": ",".join(active), "1": ",".join(inactive)}},
                terrain_loader=lambda _logical: {
                    "layers": [{"type": "objectgroup", "name": "0", "objects": []}]
                },
            )
            self.assertEqual(
                [(slot.layer, slot.single.kind, slot.single.code) for slot in slots],
                [("0", 1, "active")],
            )

        with self.subTest("live treasure cave only activates terrain layer zero"):
            try:
                fd = q.load_table(rb.FIELD_DATA_T)
                zone = q.load_table(rb.ZONE_T)
                caps = rbb.load_terrain_layer_caps(
                    "treasure_cave_area", fd, zone, rbb.load_store_terrain)
                slots = rbb.active_boss_slots(
                    "treasure_cave_area", fd, zone, rbb.load_store_terrain)
            except FileNotFoundError:
                self.skipTest("store 不可用")
            self.assertEqual(tuple(cap.layer for cap in caps), ("0",))
            self.assertEqual(slots, ())

    def test_floor_native_hp_keeps_two_real_instances_with_the_same_code(self):
        """跨 wave/不同实体槽若真的重复同代号，仍须逐实体累加。"""
        try:
            got = rb.floor_native_hp(
                ["chapter12_boss_story", "chapter12_boss_story"], 80,
                q.load_table(rb.STANDARD_BOSS))
        except FileNotFoundError:
            self.skipTest("store 不可用")
        self.assertEqual(len(got["components"]), 2)
        self.assertEqual(got["native_hp"], 770_000_000.0)

        with self.subTest("Orochi expands one parent plus eight ordered head instances"):
            try:
                catalog = rb.build_native_bundle_catalog(enemy_level=100)
                tables = {
                    "orochi": q.load_table(rbb.TABLE_LOGICALS["orochi"]),
                    "general_boss": q.load_table(rb.GENERAL_BOSS),
                    "general_boss_variable": q.load_table(
                        "master/battle/boss/general_boss_variable.orderedmap"),
                    "boss_level": q.load_table(
                        "master/battle/boss/boss_level.orderedmap"),
                }
            except FileNotFoundError:
                self.skipTest("store 不可用")
            family_id = next(
                family_id for family_id, name in catalog.family_names.items()
                if name == "八岐大蛇")
            discovered = [
                bundle for variant_id in catalog.discovered_variants[family_id]
                for bundle in catalog.discovered_bundles[variant_id]
            ]
            bundles = {}
            for bundle in discovered:
                bundles.setdefault(bundle.variant_name, bundle)
            expanded_by_variant = {}
            for variant in ("single", "multi", "multi_plus"):
                expanded = rb.expand_bundle_hp_members(
                    bundles[variant], 100, tables)
                self.assertTrue(expanded.ok, (variant, expanded))
                expanded_by_variant[variant] = expanded
                self.assertEqual(len(expanded.members), 9)
                self.assertEqual(expanded.members[0].role, "parent")
                self.assertEqual(
                    [member.ordinal for member in expanded.members[1:]],
                    list(range(1, 9)))
                self.assertAlmostEqual(
                    expanded.total_hp,
                    math.fsum(member.raw_hp for member in expanded.members),
                    places=5,
                )
                self.assertEqual(expanded.selected_parent_level, 100)

            for level in (79, 80, 90, 99, 100):
                expanded = rb.expand_bundle_hp_members(
                    bundles["single"], level, tables)
                self.assertTrue(expanded.ok, (level, expanded))
                self.assertEqual(expanded.selected_parent_level, 100)
            rejected = rb.expand_bundle_hp_members(
                bundles["single"], 101, tables)
            self.assertFalse(rejected.ok)
            self.assertEqual(rejected.reason, "SPECIAL_HP_CHANNEL_UNSUPPORTED")

        with self.subTest("duplicate head code is accumulated by occurrence"):
            duplicate_tables = copy.deepcopy(tables)
            parent = "orochi_all_head_single"
            row = rb.cells(duplicate_tables["orochi"][parent]["100"])
            heads = row[24].split(",")
            heads[-1] = heads[1]
            row[24] = ",".join(heads)
            duplicate_tables["orochi"][parent]["100"] = rb.join(row, False)
            expanded = rb.expand_bundle_hp_members(
                bundles["single"], 100, duplicate_tables)
            self.assertTrue(expanded.ok, expanded)
            self.assertEqual(
                [member.code for member in expanded.members].count(
                    "orochi_recovery_head_single"), 2)
            original = expanded_by_variant["single"]
            expected_duplicate = (
                original.total_hp
                - original.members[-1].raw_hp
                + original.members[2].raw_hp
            )
            self.assertAlmostEqual(
                expanded.total_hp, expected_duplicate, places=5
            )

        with self.subTest("one malformed head rejects the whole special HP channel"):
            malformed = copy.deepcopy(tables)
            malformed["boss_level"]["orochi_beam_head_single"] = \
                BossLevelHpScalingCase._boss_level(10, kind="1")
            expanded = rb.expand_bundle_hp_members(
                bundles["single"], 100, malformed)
            self.assertFalse(expanded.ok)
            self.assertEqual(expanded.reason, "SPECIAL_HP_CHANNEL_UNSUPPORTED")
            self.assertEqual(expanded.members, ())
            self.assertIsNone(expanded.total_hp)

        with self.subTest("unknown Hit curve is not silently replaced by proxy HP"):
            unknown = copy.deepcopy(tables)
            leaf = rb.cells(unknown["boss_level"]["orochi_beam_head_single"])
            leaf[4] = "hit_hp_unknown_task4_fixture"
            unknown["boss_level"]["orochi_beam_head_single"] = rb.join(leaf, False)
            expanded = rb.expand_bundle_hp_members(
                bundles["single"], 100, unknown)
            self.assertFalse(expanded.ok)
            self.assertEqual(expanded.reason, "SPECIAL_HP_CHANNEL_UNSUPPORTED")
            self.assertIn("curve", expanded.detail.lower())

    def test_training_dummy_proxy_family_is_not_a_tower_candidate(self):
        """practice_waraboss_tough* 是无攻击行为的练习木桩，代理榜首不能入塔。"""
        self.assertFalse(rb._pool_safe(["practice_waraboss_tough"]))
        self.assertFalse(rb._pool_safe(["practice_waraboss_tough_attack_funnel_colorless"]))
        self.assertTrue(rb._pool_safe(["guardian_totem_single"]))
