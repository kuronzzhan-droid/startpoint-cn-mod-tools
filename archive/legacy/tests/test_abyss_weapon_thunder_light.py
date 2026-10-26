# -*- coding: utf-8 -*-
"""深渊·轰电战锤 8000106 / 深渊·辉环法器 8000110 重做(作者 2026-09-28)的聚焦测试。

合成捐赠行(test_rogue_rewards 的夹具),不读 live store。覆盖:
持续行发射与拆分、253 time=(None)、629 文案键/程序登记、DSL 的元素与命中特效安全、
「本体 + 强化 120」合计 = 作者给的游戏内满级数值、强化弹射命中类触发的自我连锁门禁、
wfx 能力闸门对 DSL 段覆盖的判定、旧入口 --write 的失败关闭。
"""
from __future__ import annotations

import contextlib
import dataclasses
import importlib.util
import io
import sys
import unittest
import zlib
from pathlib import Path
from unittest import mock

pass  # Imports resolve from this checkout/package, not external source copies.
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_abyss_weapon_programs as programs  # noqa: E402
import wf_abyss_weapon_split as split  # noqa: E402
import wf_battle_rules as BR  # noqa: E402
import wf_client_legality as legality  # noqa: E402
import wf_describe  # noqa: E402
import wf_dsl  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_rogue_rewards as rewards  # noqa: E402
import wfx_gate  # noqa: E402
from test_rogue_rewards import (  # noqa: E402
    fake_master_tables, fake_server_mirrors, fake_templates, templates_for_spec,
)

ROOT = Path(__file__).resolve().parents[2]
CODEX_SPLITTER = (
    ROOT / ".worktrees/abyss-weapon-awakening/mod-tools/wf_abyss_weapon_awakening.py"
)

#: 每槽「本体 + 强化 120 级行」的强度合计(100000 = 100% / 1 倍 / 1 次);None = 无强度的 629 行。
FULL_LEVEL_TOTALS = {
    "8000106": [300000, 300000, 500000, None],          # 强弹 +300% / 攻击 +300% / 5 倍 / 立即 PF
    "8000110": [2250000, 37500, 50000, 250000, 250000],  # 203 / 206 现值;245 50%;Fever 攻击/直击 250%
}
#: 其中作者 2026-09-28 终版**指定了数值**的槽(1 起)。8000110 槽 1/2(203 / 206)作者要求「不变」,
#: 上表对应数字是现值,不是作者给的数:203 强度合计 2250000,但客户端 CoffinBaseCountDown
#: 走 AbilityPowerValue.resolveInt(Decimal 四舍五入)逐行取整 = 本体 11 + 强化 11 = 游戏内 −22 次,
#: 不是作者口头的「−15」(对半拆 750000+750000 = 8+8 = −16,对半拆凑不出 −15),待作者确认。
AUTHOR_SPECIFIED_SLOTS = {"8000106": (1, 2, 3, 4), "8000110": (3, 4, 5)}
UNCHANGED_SLOTS = {"8000110": (1, 2)}


def resolve_int(strength: int) -> int:
    """AbilityPowerValue.resolveInt:强度 /100000 后 Decimal_Impl_.round(一半向上)。"""
    return (strength * 2 + 100000) // 200000


@contextlib.contextmanager
def no_bytecode():
    """加载 Codex 只读工作树的模块时不写 __pycache__(.worktrees 下一律不改)。"""
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        yield
    finally:
        sys.dont_write_bytecode = previous


def spec_of(weapon_id: str) -> rewards.WeaponSpec:
    return next(spec for spec in rewards.WEAPONS if spec.id == weapon_id)


def built_rows(weapon_id: str) -> list[list[str]]:
    spec = spec_of(weapon_id)
    return core.read_csv_lines(rewards.build_soul_leaf(templates_for_spec(spec), spec))


def split_rows(weapon_id: str) -> tuple[list[list[str]], list[list[str]]]:
    spec = spec_of(weapon_id)
    full = rewards.build_soul_leaf(templates_for_spec(spec), spec)
    base, wab = split.split_soul_leaf(full, spec)
    return core.read_csv_lines(base), core.read_csv_lines(wab)


def commands(node, name: str):
    if isinstance(node, list):
        if len(node) >= 2 and node[0] == "Command" and isinstance(node[1], list) \
                and node[1] and node[1][0] == name:
            yield node[1]
        for child in node:
            yield from commands(child, name)


class ColumnContractTests(unittest.TestCase):
    def test_content_columns_match_describe_layout_and_client_parsers(self):
        blocks = wf_describe.layout("ability_soul")["blocks"]
        offsets = {
            field: int(offset)
            for offset, field, _label in wf_describe.enum_map()["block_fields"]["during_content"]
        }
        # AbilitySoulValues.parseAt106/107/108/110(power1=c110, first_max=c111)
        self.assertEqual(106, int(blocks["during_content"]))
        self.assertEqual(
            (106, 106 + offsets["target"], 106 + offsets["target.character_groups"],
             (106 + offsets["strength.power1"], 106 + offsets["strength.first_max"])),
            rewards.SOUL_DURING_CONTENT,
        )
        self.assertEqual((44, 45, 46, (48, 49)), rewards.SOUL_INSTANT_CONTENT)
        self.assertEqual(44, int(blocks["instant_content"]))
        self.assertEqual(82, int(blocks["during_accumulation_trigger"]))
        self.assertEqual(range(24, 82), rewards.SOUL_INSTANT_COLUMNS)
        self.assertEqual(range(82, 120), rewards.SOUL_DURING_COLUMNS)
        # EquipmentEnhancementAbilityValues:强化表 = 魂珠表 c2 起右移 3 列
        wab_blocks = wf_describe.layout("equipment_enhancement_ability")["blocks"]
        for name, column in blocks.items():
            self.assertEqual(column + 3, wab_blocks[name], name)
        self.assertEqual(113, split.wab_column(110))
        self.assertEqual(51, split.wab_column(48))


class DuringRowTests(unittest.TestCase):
    def test_fever_rows_are_emitted_into_the_during_block(self):
        rows = built_rows("8000110")
        self.assertEqual(5, len(rows))
        for row, kind in zip(rows[3:], ("0", "1")):
            with self.subTest(kind=kind):
                self.assertEqual("1", row[2])
                self.assertEqual(
                    (kind, "5", "(None)", "250000", "250000"),
                    (row[106], row[107], row[108], row[110], row[111]),
                )
                self.assertEqual("4", row[94])           # during_trigger Fever
                self.assertEqual("(None)", row[82])
                self.assertEqual("false", row[105])
                self.assertEqual([""] * 58, row[24:82], "持续行不带瞬发块")
                gates = [row[i:i + 7] for i in (3, 10, 17) if row[i] == "2"]
                self.assertEqual([["2", "", "", "600000", "600000", "White", ""]], gates)
                self.assertEqual([], legality.client_legality_problems("ability_soul", row))
        # 槽 1-3(203/206/245)仍是瞬发行、位置不变
        self.assertEqual(["203", "206", "245"], [row[44] for row in rows[:3]])
        self.assertEqual(["0", "0", "0"], [row[2] for row in rows[:3]])

    def test_during_rows_refuse_instant_block_overrides_and_instant_donors(self):
        spec = spec_of("8000110")
        templates = templates_for_spec(spec)
        fever = spec.effects[3]
        with_init = dataclasses.replace(fever, overrides=rewards._INIT)
        with self.assertRaisesRegex(ValueError, "c24"):
            rewards.build_soul_leaf(
                templates, dataclasses.replace(spec, effects=(with_init,)))
        instant_donor = dataclasses.replace(
            spec.effects[2], during=True)          # 5040019#2 是瞬发行
        with self.assertRaisesRegex(ValueError, "不是持续行"):
            rewards.build_soul_leaf(
                templates, dataclasses.replace(spec, effects=(instant_donor,)))
        instant_poking_during = dataclasses.replace(
            spec.effects[2], overrides=rewards._INIT + ((110, "1"),))
        with self.assertRaisesRegex(ValueError, "c110"):
            rewards.build_soul_leaf(
                templates, dataclasses.replace(spec, effects=(instant_poking_during,)))

    def test_during_rows_split_into_c110_base_and_c113_c114_enhancement(self):
        base, wab = split_rows("8000110")
        self.assertEqual(["125000", "125000"], base[3][110:112])
        self.assertEqual(["125000", "125000"], base[4][110:112])
        self.assertEqual(["0", "1", "2", "3", "4"], [row[0] for row in wab])
        for row, kind in zip(wab[3:], ("0", "1")):
            with self.subTest(kind=kind):
                self.assertEqual(126, len(row))
                self.assertEqual(["1", "120", "0", "0", "1"], row[1:6])
                self.assertEqual((kind, "5", "(None)"), (row[109], row[110], row[111]))
                self.assertEqual(("0", "125000"), (row[113], row[114]))
                self.assertEqual("4", row[97])
        for index, row in enumerate(wab):
            with self.subTest(wab=index):
                self.assertEqual(
                    [], legality.client_legality_problems("equipment_enhancement_ability", row))
        for index, row in enumerate(base):
            with self.subTest(base=index):
                self.assertEqual([], legality.client_legality_problems("ability_soul", row))

    def test_instant_split_matches_codex_awakening_splitter(self):
        if not CODEX_SPLITTER.is_file():
            self.skipTest("Codex awakening worktree not present")
        module_spec = importlib.util.spec_from_file_location(
            "wf_abyss_weapon_awakening_probe", CODEX_SPLITTER)
        codex = importlib.util.module_from_spec(module_spec)
        # dataclass 解析注解需要模块已登记在 sys.modules;不写字节码缓存(不碰 .worktrees)
        with mock.patch.dict(sys.modules, {module_spec.name: codex}), no_bytecode():
            module_spec.loader.exec_module(codex)
        templates = fake_templates()
        for spec in rewards.WEAPONS:
            if any(effect.during for effect in spec.effects):
                continue
            with self.subTest(weapon=spec.id):
                full = rewards.build_soul_leaf(templates, spec)
                self.assertEqual(codex.split_current_soul(full, spec),
                                 split.split_soul_leaf(full, spec))


class HammerRowTests(unittest.TestCase):
    def test_pf_damage_and_party_attack_rows(self):
        rows = built_rows("8000106")
        self.assertEqual(["55", "32", "253", "629"], [row[44] for row in rows])
        self.assertEqual(["300000", "300000"], rows[0][48:50])
        self.assertEqual(["5", "(None)", "300000"], [rows[1][45], rows[1][46], rows[1][48]])
        for row in rows:
            gates = [row[i:i + 7] for i in (3, 10, 17) if row[i] == "2"]
            self.assertEqual([["2", "", "", "600000", "600000", "Yellow", ""]], gates)

    def test_powerflip_row_hits_all_enemies_with_thunder_damage(self):
        row = built_rows("8000106")[2]
        self.assertEqual(
            {24: "2", 25: "", 26: "", 27: "100000", 28: "100000", 31: "(None)", 32: "0",
             44: "253", 45: "0", 46: "", 48: "500000", 49: "500000", 66: "(None)"},
            {col: row[col] for col in (24, 25, 26, 27, 28, 31, 32, 44, 45, 46, 48, 49, 66)},
        )
        base, wab = split_rows("8000106")
        self.assertEqual(["250000", "250000", "(None)"], [base[2][48], base[2][49], base[2][66]])
        self.assertEqual(["253", "0", "250000", "(None)"],
                         [wab[2][47], wab[2][51], wab[2][52], wab[2][69]])

    def test_skill_invoke_row_uses_the_registered_string_and_program(self):
        row = built_rows("8000106")[3]
        self.assertEqual(
            ["23", "0", "", "629", "", "", "", ""],
            [row[24], row[25], row[26], row[44], row[45], row[46], row[48], row[49]],
        )
        self.assertEqual(programs.THUNDER_HAMMER_PF_STRING, row[67])
        self.assertEqual(programs.THUNDER_HAMMER_PF_PROGRAM, row[68])
        self.assertEqual("立即获得强化弹射效果", programs.INVOKE_STRINGS[row[67]])
        self.assertEqual([], legality.invoke_skill_string_problems(
            row, frozenset(programs.INVOKE_STRINGS), "ability_soul"))
        self.assertTrue(legality.invoke_skill_string_problems(row, frozenset(), "ability_soul"))
        # 629 无强度:只留在本体,不出强化行
        base, wab = split_rows("8000106")
        self.assertEqual(row, base[3])
        self.assertEqual(["0", "1", "2"], [r[0] for r in wab])

    def test_builder_refuses_unregistered_string_and_pf_hit_triggers(self):
        spec = spec_of("8000106")
        templates = templates_for_spec(spec)
        with mock.patch.dict(programs.INVOKE_STRINGS, clear=True):
            with self.assertRaisesRegex(ValueError, "C8601"):
                rewards.build_soul_leaf(templates, spec)
        invoke = spec.effects[3]
        # 根头 133 = PF Lv3:LvAny 183、Lv3 专属 182、PowerFlipHitLv1/2/3High 15/16/17 都会被自己的命中驱动
        for trigger in ("183", "182", "17", "16", "15"):
            with self.subTest(trigger=trigger):
                on_pf_hit = dataclasses.replace(
                    invoke,
                    overrides=rewards._trig(trigger, puller="0") + invoke.overrides[-2:],
                )
                with self.assertRaisesRegex(ValueError, "连锁"):
                    rewards.build_soul_leaf(
                        templates, dataclasses.replace(spec, effects=(on_pf_hit,)))

    def test_cursed_weapon_pf_echo_gate_agrees(self):
        import wf_cursed_weapons as cursed
        row = built_rows("8000106")[3]
        dsl = programs.build_programs()
        self.assertEqual([], cursed.pf_echo_trigger_problems(cursed.SOUL_T, row, dsl))
        for trigger in ("183", "182", "17"):
            with self.subTest(trigger=trigger):
                echo = list(row)
                echo[24], echo[25] = trigger, ""
                self.assertTrue(cursed.pf_echo_trigger_problems(cursed.SOUL_T, echo, dsl))
        # 180/181 是 Lv1/Lv2 专属计数,Lv3 命中不驱动
        for trigger in ("180", "181"):
            with self.subTest(trigger=trigger):
                other = list(row)
                other[24], other[25] = trigger, ""
                self.assertEqual([], cursed.pf_echo_trigger_problems(cursed.SOUL_T, other, dsl))


class PfHitSelfChainTests(unittest.TestCase):
    """wf_battle_rules.PF_SEGMENT_HIT_TRIGGERS:段覆盖 → 被驱动的瞬发触发,按等级精确。"""

    def test_levels_map_to_their_own_counters(self):
        self.assertEqual(frozenset({"183", "180", "15"}), BR.PF_SEGMENT_HIT_TRIGGERS[131])
        self.assertEqual(frozenset({"183", "181", "15", "16"}), BR.PF_SEGMENT_HIT_TRIGGERS[132])
        self.assertEqual(frozenset({"183", "182", "15", "16", "17"}),
                         BR.PF_SEGMENT_HIT_TRIGGERS[133])
        self.assertEqual(BR.PF_SEGMENT_HIT_TRIGGERS[133],
                         BR.pf_hit_triggers_driven_by(programs.build_thunder_hammer_pf_tree()))

    def test_hit_area_overrides_count_and_non_pf_overrides_do_not(self):
        tree = programs.build_thunder_hammer_pf_tree()
        tree[10] = 0
        areas = list(commands(tree, "CreateHitArea"))
        self.assertEqual([0, 0], [area[24] for area in areas])   # buffTargetAs = 命令名后第 23 参
        self.assertEqual(frozenset(), BR.pf_hit_triggers_driven_by(tree))
        self.assertEqual([], BR.dsl_capabilities(tree))
        areas[1][24] = 132
        self.assertEqual([132], BR.dsl_segment_overrides(tree))
        self.assertEqual(BR.PF_SEGMENT_HIT_TRIGGERS[132], BR.pf_hit_triggers_driven_by(tree))
        areas[1][24] = 101                                         # 技能段覆盖:要补丁,但不是 PF 命中
        self.assertEqual(["damage-type-rules-v1"], BR.dsl_capabilities(tree))
        self.assertEqual(frozenset(), BR.pf_hit_triggers_driven_by(tree))


class CapabilityGateTests(unittest.TestCase):
    """wfx_gate 的 DSL 扫描要看段覆盖:没有 damage-type-rules-v1 的收方 = 伤害归属静默丢失。"""

    def setUp(self):
        from wf_character_revision import encode_tree
        self.tree = programs.build_thunder_hammer_pf_tree()
        self.data = encode_tree(self.tree)
        self.rel = "84/4b9a-probe"
        self.without = wfx_gate.ClientProfile("probe-without", frozenset())
        self.with_cap = wfx_gate.ClientProfile("probe-with", frozenset({"damage-type-rules-v1"}))

    def test_check_registers_semantic_requirement_for_segment_override(self):
        report = wfx_gate.check({}, {"thunder": self.tree}, [], self.without)
        self.assertFalse(report.ok)
        self.assertEqual(["damage-type-rules-v1"], report.required_capabilities())
        self.assertTrue(any("damage-type-rules-v1" in p and "会静默失效" in p for p in report.problems),
                        report.problems)
        self.assertTrue(wfx_gate.check({}, {"thunder": self.tree}, [], self.with_cap).ok)

    def test_check_publish_parses_dsl_without_wfx_content(self):
        # store=None ⇒ 没有 wfx 索引,DSL 字节里也没有 "wfx":旧扫描会整棵跳过
        self.assertNotIn(b"wfx", zlib.decompress(self.data, -15))
        report = wfx_gate.check_publish([(self.rel, self.data)], None, self.without)
        self.assertEqual(["damage-type-rules-v1"], report.required_capabilities())
        self.assertFalse(report.ok)
        self.assertTrue(wfx_gate.check_publish([(self.rel, self.data)], None, self.with_cap).ok)

    def test_plain_dsl_needs_nothing(self):
        plain = programs.build_thunder_hammer_pf_tree()
        plain[10] = 0
        self.assertTrue(wfx_gate.check({}, {"plain": plain}, [], self.without).ok)


class LegacyEntryTests(unittest.TestCase):
    """旧入口 wf_rogue_rewards --write/--publish 失败关闭。"""

    def test_blockers_name_the_629_row_and_the_live_awakening(self):
        problems = rewards.legacy_write_blockers(set())
        self.assertEqual(1, len(problems), problems)
        self.assertIn("8000106 槽4 629", problems[0])
        self.assertIn("C8601", problems[0])
        problems = rewards.legacy_write_blockers({"8000101", "9999999"})
        self.assertEqual(2, len(problems), problems)
        self.assertIn("觉醒拆分已上线", problems[1])
        without_629 = tuple(
            dataclasses.replace(spec, effects=tuple(e for e in spec.effects if e.effect_kind != "629"))
            for spec in rewards.WEAPONS
        )
        with mock.patch.object(rewards, "WEAPONS", without_629):
            self.assertEqual([], rewards.legacy_write_blockers({"9999999"}))

    def test_blockers_read_the_enhancement_table_when_not_given(self):
        with mock.patch.object(rewards.q, "load_table", return_value={"8000110": "x"}) as load:
            problems = rewards.legacy_write_blockers()
        load.assert_called_once_with(rewards.ENHANCEMENT_ABILITY_T)
        self.assertTrue(any("觉醒拆分已上线" in p for p in problems))
        with mock.patch.object(rewards.q, "load_table", side_effect=FileNotFoundError("none")):
            self.assertEqual(1, len(rewards.legacy_write_blockers()))

    def test_write_is_refused_before_any_table_json_or_asset_write(self):
        tables = fake_master_tables(placeholders=True)
        mirrors = fake_server_mirrors()
        stored = {
            rewards.ITEM_T: tables.items,
            rewards.EQUIP_T: tables.equipment,
            rewards.EQUIP_STATUS_T: tables.equipment_status,
            rewards.SOUL_T: tables.ability_soul,
            rewards.RUSH_EVENT_T: tables.rush_event,
            rewards.ENHANCEMENT_ABILITY_T: {"8000101": "awakened"},
        }
        stored_json = {
            "equipment_max_level.json": mirrors.equipment_max_level,
            "equipment_element.json": mirrors.equipment_element,
            "equipment_lookup.json": mirrors.equipment_lookup,
            "equipment_ids.json": mirrors.equipment_ids,
            "item_ids.json": mirrors.item_ids,
        }
        profile = core.VersionProfile(id="cn", label="CN", store=Path("cn-store"), fallback=None)
        errors = io.StringIO()
        with (
            mock.patch.object(rewards, "require_cn_profile", return_value=profile),
            mock.patch.object(rewards.q, "load_table", side_effect=lambda lg: stored[lg]),
            mock.patch.object(rewards.q, "save_table") as save_table,
            mock.patch.object(rewards, "load_json", side_effect=lambda name: stored_json[name]),
            mock.patch.object(rewards, "save_json") as save_json,
            mock.patch.object(rewards, "validate_source_assets",
                              return_value={spec.image_slug: Path(f"{spec.image_slug}.png")
                                            for spec in rewards.WEAPONS}),
            mock.patch.object(rewards, "install_source_assets") as install,
            mock.patch.object(rewards, "_print_asset_validation"),
            mock.patch.object(rewards, "_print_plan"),
            mock.patch.object(rewards.subprocess, "run") as publish,
            mock.patch.object(sys, "argv", ["wf_rogue_rewards.py", "--write"]),
            contextlib.redirect_stderr(errors),
        ):
            result = rewards.main()
        self.assertEqual(1, result)
        save_table.assert_not_called()
        save_json.assert_not_called()
        install.assert_not_called()
        publish.assert_not_called()
        self.assertIn("失败关闭", errors.getvalue())
        self.assertIn("629", errors.getvalue())
        self.assertIn("觉醒拆分已上线", errors.getvalue())


class ProgramSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tree = programs.build_thunder_hammer_pf_tree()

    def test_program_path_and_encoding_round_trip(self):
        from wf_character_revision import encode_tree
        self.assertEqual({programs.THUNDER_HAMMER_PF_PROGRAM}, set(programs.build_programs()))
        logical = wf_dsl.dsl_logical(programs.THUNDER_HAMMER_PF_PROGRAM)
        self.assertEqual(
            "battle/action/skill/action/ability_skill/abyss_weapon$abyss_thunder_hammer_pf"
            ".action.dsl.amf3.deflate", logical)
        data = encode_tree(self.tree)
        self.assertEqual(self.tree, wf_dsl.parse_dsl(zlib.decompress(data, -15))["tree"])

    def test_explicit_thunder_element_and_colorless_safe_hit_effect(self):
        import wf_cursed_weapons as cursed
        attacks = list(commands(self.tree, "CreateNormalAttack"))
        self.assertEqual(2, len(attacks))
        self.assertEqual([3, 3], [cna[2] for cna in attacks])          # 1-based 雷 = 内部 2 + 1
        self.assertEqual([["Explosion"]] * 2, [cna[15] for cna in attacks])
        self.assertEqual([], cursed.colorless_hit_effect_problems(self.tree))
        self.assertEqual([], legality.action_dsl_element_problems(self.tree, 2))
        # 反向对照:169988 原树的「继承属性 + Fine」在装备主体上会 C10013
        inherited = programs.build_thunder_hammer_pf_tree()
        for cna in commands(inherited, "CreateNormalAttack"):
            cna[2], cna[15] = 255, ["Fine"]
        self.assertTrue(cursed.colorless_hit_effect_problems(inherited))

    def test_structure_gates_and_capabilities(self):
        import wf_cursed_weapons as cursed
        import wf_midautumn_kit_hibiki as hibiki
        self.assertEqual([], cursed.dsl_signature_problems(self.tree))
        self.assertEqual([], hibiki.dsl_problems(self.tree, element=2))
        self.assertEqual([], legality.action_dsl_subject_binding_problems(self.tree))
        self.assertEqual([], legality.action_dsl_lookup_scope_problems(self.tree))
        self.assertEqual(133, programs.PF3_BUFF_TARGET_AS)
        self.assertEqual(programs.PF3_BUFF_TARGET_AS, self.tree[10])
        self.assertIn(self.tree[10], programs.PF_SEGMENT_HIT_TRIGGERS)
        self.assertEqual(["damage-type-rules-v1"], cursed.dsl_capabilities(self.tree))
        for name in ("SetPowerFilpSuppress", "NotifyPowerflipEnd", "RemoveEvent"):
            self.assertEqual([], list(commands(self.tree, name)), name)

    def test_payload_is_three_by_19_2_plus_one_by_43_2_at_the_ball(self):
        areas = list(commands(self.tree, "CreateHitArea"))
        self.assertEqual([["CalculatedUsingMaxNumOfHits", 3], ["CalculatedUsingMaxNumOfHits", 1]],
                         [area[14] for area in areas])
        attacks = list(commands(self.tree, "CreateNormalAttack"))
        self.assertEqual([19.2, 43.2], [cna[6][0]["min"] for cna in attacks])
        self.assertEqual([19.2, 43.2], [cna[6][0]["max"] for cna in attacks])
        self.assertEqual([0.25, 0.25], [cna[13][0]["min"] for cna in attacks])
        reference = next(commands(self.tree, "CreateReferencePoint"))
        self.assertEqual((-18, ["AB"]), (reference[1], reference[2]))   # -18 = 球


class AuthorTotalTests(unittest.TestCase):
    def test_body_plus_level_120_equals_full_level_totals(self):
        for weapon_id, expected in FULL_LEVEL_TOTALS.items():
            with self.subTest(weapon=weapon_id):
                spec = spec_of(weapon_id)
                full = rewards.build_soul_leaf(templates_for_spec(spec), spec)
                base, wab = split.split_soul_leaf(full, spec)
                self.assertEqual(expected, split.full_level_totals(base, wab, spec))
        # 作者指定槽 + 不变槽 = 全部槽,不重叠
        for weapon_id, totals in FULL_LEVEL_TOTALS.items():
            specified = set(AUTHOR_SPECIFIED_SLOTS[weapon_id])
            unchanged = set(UNCHANGED_SLOTS.get(weapon_id, ()))
            self.assertEqual(set(range(1, len(totals) + 1)), specified | unchanged)
            self.assertFalse(specified & unchanged)

    def test_unchanged_slots_keep_their_pre_rework_specs(self):
        spec = spec_of("8000110")
        self.assertEqual(
            [("5050017", 2, "203", 1500000), ("4080015", 1, "206", 25000)],
            [(e.template_id, e.donor_line, e.effect_kind, e.strength) for e in spec.effects[:2]],
        )
        for effect in spec.effects[:2]:
            key = (effect.template_id, effect.donor_line, effect.effect_kind)
            self.assertIsNone(rewards.EFFECT_STRENGTH_RULES[key].uplift)   # 仍按 ×3/2

    def test_revival_count_is_minus_22_in_game_not_15(self):
        """203 游戏内按行 resolveInt:1125000 → 11,本体 + 强化 120 级 = 22 次(不是「−15」)。"""
        base, wab = split_rows("8000110")
        self.assertEqual("203", base[0][44])
        body, enhancement = int(base[0][49]), int(wab[0][52])
        self.assertEqual((1125000, 1125000), (body, enhancement))
        self.assertEqual(22, resolve_int(body) + resolve_int(enhancement))
        self.assertEqual((11, 8, 7), (resolve_int(1125000), resolve_int(750000), resolve_int(700000)))
        # 对半拆两行取整相同 ⇒ 游戏内合计恒为偶数,凑不出 15(750000+750000 = 8+8 = 16)
        self.assertEqual(16, 2 * resolve_int(750000))
        self.assertEqual(15, resolve_int(700000) + resolve_int(800000))

    def test_body_and_enhancement_are_even_halves(self):
        expected_halves = {
            "8000106": [("150000", "150000"), ("150000", "150000"), ("250000", "250000")],
            "8000110": [("1125000", "1125000"), ("18750", "18750"), ("25000", "25000"),
                        ("125000", "125000"), ("125000", "125000")],
        }
        for weapon_id, halves in expected_halves.items():
            with self.subTest(weapon=weapon_id):
                base, wab = split_rows(weapon_id)
                actual = []
                for row in wab:
                    low, high = split.strength_columns(base[int(row[0])])
                    enhancement = row[split.wab_column(high)]
                    self.assertEqual("0", row[split.wab_column(low)])
                    self.assertEqual(base[int(row[0])][low], base[int(row[0])][high])
                    actual.append((base[int(row[0])][low], enhancement))
                self.assertEqual(halves, actual)

    def test_exact_total_rules_are_confined_to_the_reworked_weapons(self):
        exact = {key for key, rule in rewards.EFFECT_STRENGTH_RULES.items()
                 if rule.uplift == (1, 1)}
        self.assertEqual({("5070040", 1, "253"), ("5040019", 2, "245"),
                          ("5030030", 0, "0"), ("5040033", 0, "1")}, exact)
        users = {
            spec.id
            for spec in rewards.WEAPONS for effect in spec.effects
            if (effect.template_id, effect.donor_line, effect.effect_kind) in exact
        }
        self.assertEqual({"8000106", "8000110"}, users)


if __name__ == "__main__":
    unittest.main()
