"""Repository reward regressions with shared synthetic fixtures."""
from __future__ import annotations

from rogue_rewards_support import *  # noqa: F403

@unittest.skipUnless(not MISSING_API, "canonical builder API is not implemented yet")
class TestWeaponContract(unittest.TestCase):
    def test_all_canonical_fields_are_fixed(self):
        actual_metadata = [
            (spec.id, spec.name, spec.donor, spec.element, spec.group,
             f"{rewards.IMAGE_PREFIX}/{spec.image_slug}", spec.status_multiplier)
            for spec in rewards.WEAPONS
        ]
        self.assertEqual(EXPECTED_WEAPON_METADATA, actual_metadata)

        actual_effect_rows = {
            spec.id: tuple(
                (effect.template_id, effect.donor_line, effect.effect_kind, effect.strength)
                for effect in spec.effects
            )
            for spec in rewards.WEAPONS
        }
        expected_effect_rows = {
            weapon_id: tuple(row[:4] for row in rows)
            for weapon_id, rows in EXPECTED_EFFECT_ROWS.items()
        }
        self.assertEqual(expected_effect_rows, actual_effect_rows)

    def test_specs_and_strength_rules_are_immutable_and_complete(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            rewards.WEAPONS[0].name = "changed"
        with self.assertRaises(dataclasses.FrozenInstanceError):
            rewards.WEAPONS[0].effects[0].strength = 1

        expected_rule_keys = {
            (template_id, donor_line, effect_kind)
            for expected_rows in EXPECTED_EFFECT_ROWS.values()
            for template_id, donor_line, effect_kind, _old, _new in expected_rows
        }
        self.assertEqual(75, sum(map(len, EXPECTED_EFFECT_ROWS.values())))
        self.assertEqual(48, len(expected_rule_keys))
        self.assertEqual(expected_rule_keys, set(rewards.EFFECT_STRENGTH_RULES))
        with self.assertRaises(TypeError):
            rewards.EFFECT_STRENGTH_RULES[("x", 0, "0")] = object()

        templates = fake_templates()
        for spec in rewards.WEAPONS:
            with self.subTest(weapon=spec.id):
                rows = core.read_csv_lines(
                    rewards.build_soul_leaf(templates, spec, validate=False)
                )
                expected_rows = EXPECTED_EFFECT_ROWS[spec.id]
                expected_strengths = [expected[4] for expected in expected_rows]
                self.assertEqual(
                    expected_strengths, [strength_cells(row)[0] for row in rows]
                )
                self.assertEqual(
                    [strength_cells(row)[0] for row in rows],
                    [strength_cells(row)[1] for row in rows],
                )
                expected_durations = []
                for slot, (expected, effect) in enumerate(
                    zip(expected_rows, spec.effects), start=1,
                ):
                    template_id, donor_line = expected[:2]
                    if effect.during:
                        # 持续行不带瞬发块:c54/c55 维持捐赠行的空值
                        expected_durations.append(("", ""))
                        continue
                    expected_durations.append(EXPECTED_DURATION_OVERRIDES.get(
                        (spec.id, slot),
                        (
                            donor_duration_sentinel(template_id, donor_line, 54),
                            donor_duration_sentinel(template_id, donor_line, 55),
                        ),
                    ))
                self.assertEqual(
                    expected_durations,
                    [(row[54], row[55]) for row in rows],
                    "c54/c55 must preserve each donor sentinel except the three audited overrides",
                )

        legacy_effect = rewards.EffectSpec("3020006", "32", 1_200_000)
        legacy_spec = dataclasses.replace(rewards.WEAPONS[0], effects=(legacy_effect,))
        with self.assertRaisesRegex(ValueError, "no audited strength rule"):
            rewards.resolve_effect_strength(legacy_spec, legacy_effect)

        max_gauge_spec = next(spec for spec in rewards.WEAPONS if spec.id == "8000110")
        # 2026-09-28:245 改为 ×1 满额规则(作者给的是合计 +50%),上限 100% 照旧。
        max_gauge_probe = dataclasses.replace(
            max_gauge_spec.effects[2], strength=120000
        )
        resolution = rewards.resolve_effect_strength(max_gauge_spec, max_gauge_probe)
        self.assertEqual((100000, 120000, True), (
            resolution.value, resolution.raw_scaled, resolution.capped,
        ))

        inherited_effect = dataclasses.replace(rewards.WEAPONS[0].effects[0], strength=None)
        inherited_spec = dataclasses.replace(rewards.WEAPONS[0], effects=(inherited_effect,))
        inherited_row = core.read_csv_lines(rewards.build_soul_leaf(
            templates_for_spec(inherited_spec), inherited_spec, validate=False,
        ))[0]
        self.assertEqual(["100", "200"], inherited_row[48:50])


@unittest.skipUnless(not MISSING_API, "canonical builder API is not implemented yet")
class TestEquipmentGeneration(unittest.TestCase):
    def test_canonical_columns_match_verified_cn_schema(self):
        donor = [f"donor-{index}" for index in range(16)]
        leaf = rewards.build_equipment_leaf(core.write_csv_lines([donor]), rewards.WEAPONS[0])
        rows = core.read_csv_lines(leaf)

        self.assertEqual(1, len(rows))
        row = rows[0]
        self.assertEqual(16, len(row))
        self.assertEqual("mod_abyss_8000101", row[0])
        # 2026-08-05:编成选装备页按 rarity↓ / numeric id↑ 排序
        # (EquipmentSelectThumbnailListRepository.sortByRarity:81-88)。保留高 ID 的
        # 方案 1 不改 APK,因此这里只锁定「深渊·」检索前缀与稳定 ID,不声明置顶。
        self.assertEqual("深渊·灰烬巨剑", row[1])
        self.assertEqual(donor[2:6], row[2:6])
        self.assertEqual("item/equipment/mod/abyss/fire_01", row[6])
        self.assertEqual(rewards.MODE_DESCRIPTION, row[7])
        self.assertEqual("5", row[8])
        self.assertEqual("true", row[9])
        self.assertEqual("8000101", row[10])
        self.assertEqual("5", row[11])
        self.assertEqual(donor[12:16], row[12:16])

    def test_equipment_leaf_preserves_string_or_bytes_type(self):
        donor_text = core.write_csv_lines([[f"donor-{index}" for index in range(16)]])
        for template_leaf in (donor_text, donor_text.encode("utf-8")):
            with self.subTest(leaf_type=type(template_leaf).__name__):
                result = rewards.build_equipment_leaf(template_leaf, rewards.WEAPONS[0])
                self.assertIs(type(template_leaf), type(result))

    def test_equipment_status_scales_every_effective_level_with_ceiling(self):
        cases = (
            (
                rewards.WEAPONS[0],
                {"1": "334,147", "5": "500,220"},
                {
                    "1": "501,221", "2": "564,249", "3": "626,276",
                    "4": "689,303", "5": "750,330",
                },
            ),
            (
                rewards.WEAPONS[1],
                {"1": "330,148", "5": "495,221"},
                {
                    "1": "495,222", "2": "558,251", "3": "620,278",
                    "4": "681,305", "5": "743,332",
                },
            ),
            (
                rewards.WEAPONS[-1],
                {"1": "544,85", "5": "815,127"},
                {
                    "1": "816,128", "2": "918,144", "3": "1020,159",
                    "4": "1122,176", "5": "1223,191",
                },
            ),
        )
        for spec, donor_levels, expected in cases:
            with self.subTest(weapon=spec.id):
                status_table = {spec.donor: donor_levels}
                result = rewards.build_equipment_status(status_table, spec)
                self.assertEqual(expected, result)
                self.assertEqual(donor_levels, status_table[spec.donor])

        doubled = dataclasses.replace(rewards.WEAPONS[0], status_multiplier=(2, 1))
        self.assertEqual(
            {
                "1": "668,294", "2": "752,332", "3": "834,368",
                "4": "918,404", "5": "1000,440",
            },
            rewards.build_equipment_status(
                {doubled.donor: {"1": "334,147", "5": "500,220"}}, doubled
            ),
        )

        descending = dataclasses.replace(rewards.WEAPONS[0], donor="descending")
        with self.assertRaisesRegex(ValueError, "monotonic"):
            rewards.build_equipment_status(
                {"descending": {"1": "500,220", "5": "334,147"}}, descending
            )


@unittest.skipUnless(not MISSING_API, "canonical builder API is not implemented yet")
class TestTokenGeneration(unittest.TestCase):
    def test_token_leaf_is_the_complete_canonical_template_clone(self):
        template = [f"template-{index}" for index in range(23)]
        template[1] = rewards.TOKEN_TEMPLATE
        template[2] = "激战代币"
        original = core.write_csv_lines([template])

        actual = rewards.build_token_leaf(original)

        expected = list(template)
        expected[0] = "rogue_event_item_99"
        expected[1] = rewards.TOKEN_ID
        expected[2] = "深渊代币"
        expected[5] = rewards.TOKEN_DESCRIPTION
        expected[19:22] = ["2000-01-01 00:00:00", "2099-12-31 23:59:59", "true"]
        self.assertEqual([expected], core.read_csv_lines(actual))
        self.assertIs(str, type(actual))

    def test_token_display_period_preserves_binary_leaf_and_unowned_columns(self):
        template = [f"template-{index}" for index in range(25)]
        template[19:22] = ["2025-01-01 12:00:00", "2025-12-31 11:59:59", "false"]
        original = core.write_csv_lines([template]).encode("utf-8")

        actual = rewards.build_token_leaf(original)

        self.assertIs(bytes, type(actual))
        row = core.read_csv_lines(actual.decode("utf-8"))[0]
        self.assertEqual(
            ["2000-01-01 00:00:00", "2099-12-31 23:59:59", "true"], row[19:22]
        )
        owned = {0, 1, 2, 5, 19, 20, 21}
        self.assertEqual(
            [value for index, value in enumerate(template) if index not in owned],
            [value for index, value in enumerate(row) if index not in owned],
        )

    def test_short_token_template_fails_with_a_validation_error(self):
        for width in (6, 19, 21):
            with self.subTest(width=width), self.assertRaisesRegex(ValueError, "22\\+"):
                rewards.build_token_leaf(core.write_csv_lines([[""] * width]))


@unittest.skipUnless(not MISSING_API, "canonical builder API is not implemented yet")
class TestSoulGeneration(unittest.TestCase):
    def test_fire_greatsword_uses_only_requested_template_lines(self):
        templates = fake_templates()
        donor_mismatch = core.read_csv_lines(templates["5050022"])[1]
        self.assertEqual(["32", "5050022#1"], [donor_mismatch[44], donor_mismatch[122]])

        leaf = rewards.build_soul_leaf(templates, rewards.WEAPONS[0])
        rows = core.read_csv_lines(leaf)
        self.assertEqual(6, len(rows))
        self.assertEqual(["51", "202", "32", "33", "32", "33"], [row[44] for row in rows])
        self.assertEqual(["5", "0", "5", "5", "8", "8"], [row[45] for row in rows])
        self.assertEqual(
            ["(None)", "", "(None)", "(None)", "", ""], [row[46] for row in rows]
        )
        self.assertEqual(
            ["225000", "75000", "300000", "300000", "300000", "300000"],
            [row[48] for row in rows],
        )
        self.assertEqual([row[48] for row in rows], [row[49] for row in rows])

    def test_fire_weapons_mirror_attack_and_direct_to_multiballs(self):
        """作者 2026-09-28:火深渊武器的攻击力/直击加成同值给协力球。

        协力球行必须是全队行的逐列镜像,只允许槽号 c0、target c45(5→8)、组 c46((None)→空)不同;
        target=8 Multiball 解析器(soul parseAt45,32/33 共用)不读 c46。先例:官方 soul 32/8
        4 行(4030008#0 等)c46 皆空;soul 无 33/8,33/8 先例在官方 ability 表(1110061#0 等)
        与自家诅咒武器。
        """
        templates = fake_templates()
        expected_kinds = {"8000101": ["32", "33"], "8000102": ["32"]}
        for spec in rewards.WEAPONS:
            rows = core.read_csv_lines(rewards.build_soul_leaf(templates, spec))
            multiball = [row for row in rows if row[45] == "8"]
            with self.subTest(weapon=spec.id):
                self.assertEqual(
                    expected_kinds.get(spec.id, []), [row[44] for row in multiball]
                )
                for row in multiball:
                    twins = [t for t in rows if t[44] == row[44] and t[45] == "5"]
                    self.assertEqual(1, len(twins))
                    diff = {
                        column for column, (a, b) in enumerate(zip(twins[0], row))
                        if a != b
                    }
                    self.assertEqual({0, 45, 46}, diff)
                    self.assertEqual(("(None)", ""), (twins[0][46], row[46]))
                    self.assertEqual(rows[-len(multiball):], multiball,
                                     "协力球行追加在末尾,旧槽号不动")

    def test_each_effect_uses_its_templates_first_line_and_fixed_columns(self):
        templates = fake_templates()
        for spec in rewards.WEAPONS:
            with self.subTest(weapon=spec.id):
                rows = core.read_csv_lines(rewards.build_soul_leaf(templates, spec))
                expected_rows = EXPECTED_EFFECT_ROWS[spec.id]
                self.assertEqual(len(expected_rows), len(rows))
                for slot, (row, effect, expected) in enumerate(
                    zip(rows, spec.effects, expected_rows), start=1,
                ):
                    template_id, donor_line, effect_kind, _old, uplift = expected
                    kind_col, target_col, group_col, (low, high) = (
                        rewards.SOUL_DURING_CONTENT if effect.during
                        else rewards.SOUL_INSTANT_CONTENT
                    )
                    self.assertEqual(123, len(row))
                    self.assertEqual(
                        [str(slot), "1", "1" if effect.during else "0"], row[:3]
                    )
                    self.assertEqual(f"{template_id}#{donor_line}", row[122])
                    self.assertEqual(effect_kind, row[kind_col])
                    donor_target = "5" if effect.during else "1"
                    self.assertEqual(
                        effect.target if effect.target is not None else donor_target,
                        row[target_col],
                    )
                    expected_group = (
                        spec.group if effect.target_groups is rewards.WEAPON_GROUP
                        else effect.target_groups if effect.target_groups is not None
                        else ""
                    )
                    self.assertEqual(expected_group, row[group_col])
                    self.assertEqual(uplift, row[low])
                    self.assertEqual(row[low], row[high])
                    expected_bool = EXPECTED_BY_EACH_TRIGGER_PULLER.get(
                        (spec.id, slot)
                    )
                    if expected_bool is not None:
                        self.assertEqual(expected_bool, row[69])
                if spec.id == "8000112":
                    self.assertEqual(
                        EXPECTED_5050022_OUTPUT_COLUMNS,
                        {
                            column: rows[3][column]
                            for column in EXPECTED_5050022_OUTPUT_COLUMNS
                        },
                        "5050022#1 must remain HpHigh + skill-triggered self damage",
                    )
                if spec.id == "8000113":
                    actual = tuple(
                        {column: row[column] for column in expected}
                        for row, expected in zip(
                            rows[:2], EXPECTED_CONQUEROR_SURVIVAL_COLUMNS,
                        )
                    )
                    self.assertEqual(EXPECTED_CONQUEROR_SURVIVAL_COLUMNS, actual)

    def test_universal_effects_use_none_sentinel_for_unfiltered_party_target(self):
        templates = fake_templates()
        expected_groups = {
            "8000113": ["(None)", "", "", "(None)"],
            "8000114": ["(None)", "(None)", "", "(None)", "(None)", ""],
            "8000115": ["", "", "(None)", "(None)", "", "(None)"],
        }
        for spec in rewards.WEAPONS[-3:]:
            with self.subTest(weapon=spec.id):
                rows = core.read_csv_lines(rewards.build_soul_leaf(templates, spec))
                self.assertEqual(expected_groups[spec.id], [row[46] for row in rows])


class TestMasterChanges(unittest.TestCase):
    def test_registers_same_id_ability_soul_items_for_every_weapon(self):
        tables = fake_master_tables()

        result = require_task2("build_master_changes")(tables)

        for spec in rewards.WEAPONS:
            with self.subTest(weapon=spec.id):
                self.assertIn(spec.id, result.items)
                donor = core.read_csv_lines(tables.items[spec.donor])[0]
                actual = core.read_csv_lines(result.items[spec.id])[0]
                expected = list(donor)
                expected[0] = f"mod_abyss_{spec.id}"
                expected[1] = spec.id
                expected[2] = f"{spec.name}魂珠"
                expected[3] = f"{rewards.IMAGE_PREFIX}/{spec.image_slug}"
                expected[12] = (
                    str(spec.element) if spec.element >= 0 else "0,3,2,1,4,5"
                )
                self.assertEqual(expected, actual)

    def test_first_run_materializes_exactly_fifteen_owned_rows_per_table(self):
        tables = fake_master_tables()
        result = require_task2("build_master_changes")(tables)
        generated = {spec.id for spec in rewards.WEAPONS}

        self.assertEqual(generated, generated.intersection(result.equipment))
        self.assertEqual(generated, generated.intersection(result.equipment_status))
        self.assertEqual(generated, generated.intersection(result.ability_soul))
        self.assertEqual(15, len(generated.intersection(result.equipment)))
        self.assertEqual(15, len(generated.intersection(result.equipment_status)))
        self.assertEqual(15, len(generated.intersection(result.ability_soul)))
        self.assertFalse(generated.intersection(tables.equipment))
        self.assertFalse(generated.intersection(tables.equipment_status))
        self.assertFalse(generated.intersection(tables.ability_soul))

    def test_second_run_is_byte_for_byte_idempotent(self):
        tables = fake_master_tables(placeholders=True, binary=True)
        builder = require_task2("build_master_changes")
        first = builder(tables)
        tables_type = require_task2("MasterTables")
        second = builder(tables_type(
            items=first.items,
            equipment=first.equipment,
            equipment_status=first.equipment_status,
            ability_soul=first.ability_soul,
            rush_event=first.rush_event,
        ))

        self.assertEqual(first, second)
        for spec in rewards.WEAPONS:
            self.assertIs(bytes, type(first.equipment[spec.id]))
            self.assertIs(bytes, type(first.ability_soul[spec.id]))
            self.assertEqual(first.equipment[spec.id], second.equipment[spec.id])
            self.assertEqual(first.ability_soul[spec.id], second.ability_soul[spec.id])
        self.assertEqual(first.items[rewards.TOKEN_ID], second.items[rewards.TOKEN_ID])
        self.assertEqual(first.rush_event["700099"], second.rush_event["700099"])

    def test_foreign_reserved_equipment_fails_without_mutating_any_table(self):
        tables = fake_master_tables(placeholders=True)
        spec = rewards.WEAPONS[0]
        foreign = [f"foreign-{index}" for index in range(16)]
        foreign[0] = "not_owned_by_abyss"
        tables.equipment[spec.id] = core.write_csv_lines([foreign])
        before = copy.deepcopy(tables)

        with self.assertRaisesRegex(ValueError, spec.id):
            require_task2("build_master_changes")(tables)

        self.assertEqual(before, tables)

    def test_foreign_reserved_ability_soul_item_fails_without_mutation(self):
        tables = fake_master_tables(placeholders=True)
        spec = rewards.WEAPONS[0]
        foreign = [f"foreign-item-{index}" for index in range(23)]
        foreign[0] = "not_owned_by_abyss"
        foreign[1] = spec.id
        tables.items[spec.id] = core.write_csv_lines([foreign])
        before = copy.deepcopy(tables)

        with self.assertRaisesRegex(ValueError, spec.id):
            require_task2("build_master_changes")(tables)

        self.assertEqual(before, tables)

    def test_orphan_soul_or_status_requires_an_owned_equipment_row(self):
        spec = rewards.WEAPONS[0]
        for field, occupant in (
            ("ability_soul", core.write_csv_lines([["foreign-soul"]])),
            ("equipment_status", {"foreign": "status"}),
        ):
            with self.subTest(field=field):
                tables = fake_master_tables()
                getattr(tables, field)[spec.id] = occupant
                before = copy.deepcopy(tables)

                with self.assertRaisesRegex(ValueError, spec.id):
                    require_task2("build_master_changes")(tables)

                self.assertEqual(before, tables)

    def test_recognized_placeholders_may_be_replaced(self):
        tables = fake_master_tables(placeholders=True)
        result = require_task2("build_master_changes")(tables)

        for spec in rewards.WEAPONS:
            row = core.read_csv_lines(result.equipment[spec.id])[0]
            self.assertEqual(f"mod_abyss_{spec.id}", row[0])
            self.assertEqual(spec.name, row[1])
            self.assertEqual(f"{rewards.IMAGE_PREFIX}/{spec.image_slug}", row[6])
            self.assertEqual(
                rewards.build_equipment_status(tables.equipment_status, spec),
                result.equipment_status[spec.id],
            )
            self.assertNotEqual(tables.ability_soul[spec.id], result.ability_soul[spec.id])

    def test_token_and_rush_event_are_complete_canonical_clones(self):
        tables = fake_master_tables()
        result = require_task2("build_master_changes")(tables)

        template = core.read_csv_lines(tables.items[rewards.TOKEN_TEMPLATE])[0]
        token = core.read_csv_lines(result.items[rewards.TOKEN_ID])[0]
        self.assertEqual("2370099", token[1])
        self.assertEqual("深渊代币", token[2])
        self.assertEqual(
            ["2000-01-01 00:00:00", "2099-12-31 23:59:59", "true"], token[19:22]
        )
        self.assertEqual(
            [value for index, value in enumerate(template)
             if index not in (0, 1, 2, 5, 19, 20, 21)],
            [value for index, value in enumerate(token)
             if index not in (0, 1, 2, 5, 19, 20, 21)],
        )

        before = core.read_csv_lines(tables.rush_event["700099"])[0]
        template_event = core.read_csv_lines(
            tables.rush_event[rogue_build.TEMPLATE_EVENT]
        )[0]
        after = core.read_csv_lines(result.rush_event["700099"])[0]
        expected = list(template_event)
        expected[0] = rogue_build.EVENT_STRING_ID
        expected[1] = rogue_build.EVENT_NAME
        expected[2] = ",".join(
            (
                rogue_build.START,
                rogue_build.END,
                rogue_build.RESULT_END,
                rogue_build.EXCHANGE_END,
            )
        )
        expected[3:5] = before[3:5]
        expected[10] = rewards.TOKEN_ID
        expected[15] = rogue_build.START
        expected[16] = rogue_build.END
        expected[17] = rogue_build.EXCHANGE_END
        self.assertEqual(expected, after)
        self.assertEqual(tables.rush_event["700001"], result.rush_event["700001"])

    def test_patch_rush_token_preserves_leaf_type(self):
        row = [f"rush-{index}" for index in range(18)]
        row[10] = rewards.TOKEN_TEMPLATE
        text = core.write_csv_lines([row])
        patcher = require_task2("patch_rush_token")

        for leaf in (text, text.encode("utf-8")):
            with self.subTest(leaf_type=type(leaf).__name__):
                result = patcher(leaf)
                self.assertIs(type(leaf), type(result))
                changed = core.read_csv_lines(result.decode("utf-8") if isinstance(result, bytes) else result)[0]
                self.assertEqual(rewards.TOKEN_ID, changed[10])
                self.assertEqual(row[:10] + row[11:], changed[:10] + changed[11:])


class TestServerMirrors(unittest.TestCase):
    def test_canonical_lookup_elements_and_donor_metadata_are_applied(self):
        mirrors = fake_server_mirrors()
        result = require_task2("apply_server_mirrors")(mirrors)

        self.assertEqual(
            [0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, -1, -1, -1],
            [result.equipment_element[spec.id] for spec in rewards.WEAPONS],
        )
        for spec in rewards.WEAPONS:
            donor = mirrors.equipment_lookup[spec.donor]
            self.assertEqual({
                "name": spec.name,
                "rarity": "5",
                "category": donor["category"],
            }, result.equipment_lookup[spec.id])
            self.assertEqual(
                mirrors.equipment_max_level[spec.donor],
                result.equipment_max_level[spec.id],
            )
        self.assertEqual(mirrors.equipment_lookup["42"], result.equipment_lookup["42"])

    def test_id_mirrors_are_sorted_unique_integer_arrays(self):
        result = require_task2("apply_server_mirrors")(fake_server_mirrors())

        self.assertEqual(sorted(set(result.equipment_ids)), result.equipment_ids)
        self.assertEqual(sorted(set(result.item_ids)), result.item_ids)
        self.assertTrue(all(isinstance(value, int) for value in result.equipment_ids))
        self.assertTrue(all(isinstance(value, int) for value in result.item_ids))
        self.assertEqual(
            {int(spec.id) for spec in rewards.WEAPONS},
            {int(spec.id) for spec in rewards.WEAPONS}.intersection(result.equipment_ids),
        )
        self.assertIn(int(rewards.TOKEN_ID), result.item_ids)

    def test_second_run_produces_identical_json_bytes(self):
        applier = require_task2("apply_server_mirrors")
        first = applier(fake_server_mirrors())
        second = applier(first)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            first_bytes = write_temp_mirrors(path, first)
            second_bytes = write_temp_mirrors(path, second)

        self.assertEqual(first, second)
        self.assertEqual(first_bytes, second_bytes)
