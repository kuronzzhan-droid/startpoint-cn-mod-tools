# -*- coding: utf-8 -*-
"""蕾贝卡 kit（169991 ``bearish_darkwitch_moon``）：设计稿自查 + 行装配 + DSL 门禁。

三组用例：

1. **纯静态**（不需要 live / 官方基线）：模块常量与设计稿 JSON 的互锁、裁决 §8 的设计自查
   （队长表禁 422/724/713、固有状态确实为零、c2 雕像组每键单值且落在 25 键内、面板禁词、
   donor 地址 1 基→0 基换算、两档数值的 0.8 比例与裁决 §2 的 36–50× 带）、以及本模块的
   DSL 小工具（``_remap_binding`` 的平移与拒绝、``_write_dsl_checked`` 的包装壳拦截、
   ``_assert_effects_are_shared`` 的角色专属特效拦截）。
2. **官方基线**（缺 ``.cdn/cn`` 或 live store 时跳过）：6+14 行逐行装配并与设计登记的
   ``desc_expected`` 逐字比对；两档技能树的装配与门禁（段数、两条抗性↓、强制付与、
   贯通/PF 帧数、绑定 id 重映射、特效来源）。
3. **已构建的 workspace**（``work/character_packs/ma-rebecca`` 未构建时跳过）：包内唯一的
   自有共享表键、认领、两棵 DSL 往返、语音路由、kit-report 的状态与面板。

不写 live store / ``assets/`` / ``.cdn``，不跑发布；官方基线只读。

**rework1（2026-09-21）** 额外钉住三条：技能树里 ``AddSkillPoint`` 必须一条不剩、
队友块里的条件治疗（``ConditionalsHealthPointRatioOf`` → ``CreateRatioHeal``）形状与两档比例、
词条 3 第 4 条是 ``(CT15秒)`` 而不是 ``(限5次)``。
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_client_legality as L  # noqa: E402
import wf_dsl  # noqa: E402
import wf_midautumn_common as MC  # noqa: E402
import wf_midautumn_kit_rebecca as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_build as B  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402

ROOT = core.project_root()
DESIGN = MS.load_design(ROOT, "rebecca")
WORKSPACE = ROOT / "work/character_packs/ma-rebecca"


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


_BASELINE = _baseline_available()
_CTX = None


def ctx():
    """只读上下文：``record_sources=False`` ⇒ 母本取数不写 workspace（框架 §10.2）。"""
    global _CTX
    if _CTX is None:
        _CTX = B.KitContext(MC.MAPack(MS.get_spec("rebecca"), record_sources=False))
    return _CTX


def _command(name, *args):
    return ["Command", [name, *args]]


# ---------------------------------------------------------------- 1. 纯静态

class ConstantTests(unittest.TestCase):
    def test_identity_matches_the_registry(self):
        spec = MS.get_spec("rebecca")
        self.assertEqual((spec.cid, spec.code), (K.CID, K.CODE))
        self.assertEqual((spec.template_id, spec.template_code), (K.TEMPLATE_ID, K.TEMPLATE_CODE))
        self.assertEqual(spec.element, K.ELEMENT)          # 5 = 暗；写 6(Colorless) 崩 C7050
        self.assertEqual(spec.pf_type, 3)
        self.assertEqual(spec.stance, "Supporter")
        self.assertIn(spec.stance, L.CHARACTER_STANCES)

    def test_the_only_self_owned_shared_key_is_the_voice_switch(self):
        keys = MS.get_spec("rebecca").extra_keys
        self.assertEqual(keys.get(KL.SWITCHED), (K.VOICE_KEY,))
        self.assertEqual(K.VOICE_KEY, f"{K.CODE}_voice_ready")
        # 裁决 §2「蕾贝卡：不做 722」＋ 偏离 D7「零固有状态」⇒ 这三张表一个键都不占
        for logical in (MS.UNIQUE_CONDITION_LOGICAL, KL.CAS,
                        "master/skill/power_flip_action.orderedmap"):
            self.assertFalse(keys.get(logical), logical)
        self.assertEqual(tuple(K.SPEC["required_capabilities"]), ())

    def test_ability_keys_are_the_six_slots(self):
        self.assertEqual(K.ABILITY_KEYS, tuple(f"{K.CID}{n}" for n in range(1, 7)))

    def test_parse_donor_handles_both_address_shapes_and_is_one_based(self):
        self.assertEqual(K._parse_donor("L:261083:1"), ("official", "L", "261083#0"))
        self.assertEqual(K._parse_donor("A:2610833:2"), ("official", "A", "2610833#1"))
        self.assertEqual(K._parse_donor("s:A:1599963:3"), ("live", "A", "1599963#2"))
        self.assertEqual(K._parse_donor("o:A:1110934:1"), ("official", "A", "1110934#0"))
        for bad in ("A:2610833:0", "x:A:2610833:1", "Z:2610833:1", "A:2610833", "A:1:2:3:4"):
            with self.assertRaises(K.KitError, msg=bad):
                K._parse_donor(bad)

    def test_skill_tiers_keep_the_designed_ratio_and_stay_in_band(self):
        tiers = K.SKILL_TIERS
        self.assertEqual(set(tiers), {"1", "2"})
        enhanced = tiers["2"]["cna"]["max"] * K.TOTAL_HITS
        base = tiers["1"]["cna"]["max"] * K.TOTAL_HITS
        self.assertEqual(enhanced, 40.0)                   # 裁决 §2：辅助技能 36–50×
        self.assertTrue(36 <= enhanced <= 50, enhanced)
        self.assertLess(base, enhanced)
        # 偏离 D9：未强化档 = 强化档 × 0.8（比例取自 ★3 母本自己的官方 _1/_2 比）
        for field in ("cna", "tolerance_self", "tolerance_all", "heal_ratio", "pf_value"):
            for edge in ("min", "max"):
                self.assertAlmostEqual(tiers["1"][field][edge], tiers["2"][field][edge] * 0.8,
                                       places=6, msg=f"{field}.{edge}")
        for field in ("frozen", "pf_frames", "piercing"):
            self.assertEqual(tiers["1"][field], round(tiers["2"][field] * 0.8), field)

    def test_tolerance_elements_and_hit_effect_are_the_safe_ones(self):
        self.assertEqual(K.TOLERANCE_ELEMENT_SELF, 255)    # 继承持有者，不是内部元素码
        self.assertEqual(K.TOLERANCE_ELEMENT_ALL, 254)     # 带抗性旗 boss 的白名单只放行 254
        self.assertNotIn(K.ELEMENT, (K.TOLERANCE_ELEMENT_SELF, K.TOLERANCE_ELEMENT_ALL))
        # 偏离 D10：AttackHitEffect 必须是官方枚举分支，不能是引用别人专属目录的 SpecifyHitEffectDirectly
        self.assertEqual(K.HIT_EFFECT, ["Fine"])
        self.assertNotEqual(K.HIT_EFFECT[0], "SpecifyHitEffectDirectly")

    def test_binding_ids_do_not_collide_with_the_spine(self):
        spine_used = {0, 1, K.SPINE_HIT_BINDING, K.SPINE_ALLY_BINDING}
        moved = {0 + K.BUFF_BINDING_SHIFT, 1 + K.BUFF_BINDING_SHIFT, 2 + K.BUFF_BINDING_SHIFT}
        self.assertFalse(spine_used & moved, f"{spine_used} ∩ {moved}")

    def test_shared_effect_is_not_under_any_character_directory(self):
        self.assertTrue(K.SHARED_EFFECT.startswith("battle/effect/skill_general/"))
        self.assertNotIn("skill_unique", K.SHARED_EFFECT)

    def test_rework1_heal_constants(self):
        # rework1：治疗基准恒为 2（按最大生命值，全库 172 例）、命中特效必须是官方枚举、
        # 阈值按百分数整数写（官方三例 40/50/50）、选择器 35 ＝ 除自身外队友（面板的「队友」）。
        self.assertEqual(K.HEAL_BASIS, 2)
        self.assertEqual(K.HEAL_HIT_EFFECT, ["GenericHealHitEffect"])
        self.assertNotIn("SpecifyHealEffectDirectly", K.HEAL_HIT_EFFECT)
        self.assertEqual(K.HEAL_HP_THRESHOLD, 40)
        self.assertEqual(K.SPINE_ALLY_SELECTOR, 35)
        self.assertTrue(K.HEAL_DONOR.endswith("psychic_teleport_playable_2"))
        # 觉醒档 ＝ 作者口径的「满级」35%，未觉醒档 28%
        self.assertEqual(K.SKILL_TIERS["2"]["heal_ratio"], {"min": 0.35, "max": 0.35})
        self.assertEqual(K.SKILL_TIERS["1"]["heal_ratio"], {"min": 0.28, "max": 0.28})
        for tier in K.SKILL_TIERS.values():
            self.assertNotIn("skill_point", tier, "rework1：技能不再给队友技能槽")

    def test_dsl_events_finds_the_wait_wrapper(self):
        tree = ["Block", [["Event", ["Wait", 300, "*", ["Block", []]]],
                          ["Command", ["AddCombo", []]]]]
        self.assertEqual([e[1] for e in K._dsl_events(tree, "Wait")], [300])
        self.assertEqual(K._dsl_events(tree, "Nope"), [])


@unittest.skipUnless(bool(DESIGN), "design/rebecca.json missing")
class DesignSelfCheckTests(unittest.TestCase):
    """裁决 §8：kit 实现前对设计稿的硬自查。"""

    def setUp(self):
        self.leader = DESIGN["plan"]["leader_ability"]["rows"]
        self.ability = DESIGN["plan"]["ability"]["keys"]

    def test_design_identity_matches_the_module(self):
        self.assertEqual(DESIGN.get("schema"), "ma-design/1")
        self.assertEqual(DESIGN.get("cid"), K.CID)
        self.assertEqual(DESIGN.get("code"), K.CODE)

    def test_leader_block_shape_and_no_patched_kinds(self):
        plan = DESIGN["plan"]["leader_ability"]
        self.assertEqual(str(plan["key"]), str(K.CID))
        self.assertEqual(int(plan["layout"]["ncols"]), KL.LEADER_NCOLS)
        self.assertEqual(len(self.leader), K.LEADER_ROW_COUNT)
        for entry in self.leader:
            for col in ("45", "107"):                      # 瞬发内容 / 持续内容 kind
                self.assertNotIn(entry["cells"].get(col), K.FORBIDDEN_LEADER_KINDS, entry["label"])
            self.assertEqual(entry["cells"]["0"], K.CODE, entry["label"])
            self.assertTrue(entry["donor"] and entry["desc_expected"], entry["label"])

    def test_leader_never_carries_a_629_pursuit_without_a_string_key(self):
        # 裁决 §8：629 必须配 custom_ability_string 字符串键；本角色一条都没有，所以也不许出现 629
        for entry in self.leader + [r for b in self.ability.values() for r in b["records"]]:
            self.assertNotIn("629", (entry["cells"].get("45"), entry["cells"].get("47")),
                             entry.get("label") or entry["donor"])

    def test_ability_has_six_keys_fourteen_records(self):
        self.assertEqual(tuple(sorted(self.ability)), tuple(sorted(K.ABILITY_KEYS)))
        self.assertEqual(int(DESIGN["plan"]["ability"]["layout"]["ncols"]), KL.ABILITY_NCOLS)
        total = sum(len(block["records"]) for block in self.ability.values())
        self.assertEqual(total, K.ABILITY_RECORD_COUNT)

    def test_no_unique_condition_is_planned(self):
        # 偏离 D7：零固有状态。真要加就必须是 8 位 ID 且上限不是 (None)——这里顺手把规则钉住。
        add = DESIGN["plan"]["unique_conditions"]["add"]
        self.assertEqual(add, [])
        for entry in add:                                   # 空列表；规则仍然写出来防以后回填时漏
            self.assertTrue(MS.unique_condition_ok(K.CID, entry["key"]))
            self.assertNotIn(entry["row"][4], ("", "(None)"))

    def test_statue_group_and_unisonable_are_single_valued_per_key(self):
        for name, block in self.ability.items():
            groups = {r["cells"]["2"] for r in block["records"]}
            self.assertEqual(len(groups), 1, f"{name} mixed statue groups {groups}")
            self.assertEqual(groups.pop(), block["statue_group_c2"], name)
            # c2 是玛纳板雕像图键：不在 25 键内 = 玛纳板整块 C8601
            self.assertIn(block["statue_group_c2"], L.ABILITY_STATUE_GROUPS, name)
            flags = {r["cells"]["1"] for r in block["records"]}
            self.assertEqual(len(flags), 1, f"{name} mixed unisonable flags {flags}")
            self.assertEqual(flags.pop(), block["unisonable_c1"], name)

    def test_statue_group_precedent_block_is_recorded(self):
        # 裁决 §8 要求核对过（三处官方零先例已登记为偏离 D11，不是静默降级）
        block = DESIGN["plan"]["ability"]["statue_group_precedent"]
        self.assertTrue(block["hit"])
        self.assertEqual(set(block["no_official_precedent"]),
                         {"power_flip×I718", "attack_black×I192", "attack_common×I491"})
        self.assertIn("D11", {d["id"] for d in DESIGN["deviations"]})

    def test_ability_records_carry_the_slot_code_in_c0(self):
        for slot, key_name in enumerate(K.ABILITY_KEYS, start=1):
            for record in self.ability[key_name]["records"]:
                self.assertEqual(record["cells"]["0"], f"{K.CODE}_{slot}", f"{key_name}#{record['index']}")

    def test_all_donor_addresses_parse(self):
        for entry in self.leader:
            self.assertEqual(K._parse_donor(entry["donor"])[1], "L", entry["label"])
        for block in self.ability.values():
            for record in block["records"]:
                self.assertEqual(K._parse_donor(record["donor"])[1], "A", record["donor"])

    def test_panel_texts_obey_the_batch_rules(self):
        for entry in self.leader:
            self.assertEqual(KL.panel_problems(entry["desc_expected"]), [], entry["label"])
        for block in self.ability.values():
            for record in block["records"]:
                self.assertEqual(KL.panel_problems(record["desc_expected"]), [], record["donor"])
        for field in ("title", "profile", "leader", "skill1", "skill2", "desc1", "desc2"):
            self.assertEqual(KL.panel_problems(DESIGN["texts"][field]), [], field)
        self.assertEqual(DESIGN["texts"]["desc1"], DESIGN["texts"]["desc2"])

    def test_skill_description_names_both_tolerances(self):
        # 裁决 §3：面板文案必须与真实机制一致——DSL 挂两条抗性↓，描述里两种都要写出来
        desc = DESIGN["texts"]["desc1"]
        self.assertIn("暗属性抗性降低", desc)
        self.assertIn("全属性抗性降低", desc)
        self.assertIn("无视弱体耐性", desc)                 # ＝ forceApply=true 的精确说法

    def test_energy_and_level_tiers_are_declared(self):
        energy = DESIGN["plan"]["skills"]["energy"]
        self.assertEqual([str(x) for x in energy["1"]], ["500", "500"])
        self.assertEqual([str(x) for x in energy["2"]], ["500", "450"])
        tiers = DESIGN["plan"]["skills"]["level_tiers"]
        for level in ("1", "2"):
            self.assertEqual(tiers[level]["cna"], K.SKILL_TIERS[level]["cna"], level)
            self.assertEqual(tiers[level]["frozen_frames"], K.SKILL_TIERS[level]["frozen"], level)
            self.assertEqual(tiers[level]["piercing_frames"], K.SKILL_TIERS[level]["piercing"], level)
            # rework1：治疗比例与阈值两边互锁（设计稿漂移当场红）
            self.assertEqual(tiers[level]["heal_ratio"], K.SKILL_TIERS[level]["heal_ratio"], level)
            self.assertEqual(tiers[level]["heal_hp_threshold"], K.HEAL_HP_THRESHOLD, level)
            self.assertNotIn("add_skill_point", tiers[level], level)
        self.assertEqual(tiers["shared"]["root_bta_tree10"], 0)   # 技能伤害归属，不写 3
        self.assertEqual(tiers["shared"]["heal_basis"], K.HEAL_BASIS)
        self.assertEqual(tiers["shared"]["heal_hit_effect"], K.HEAL_HIT_EFFECT)
        self.assertEqual(tiers["shared"]["heal_selector"], K.SPINE_ALLY_SELECTOR)
        self.assertEqual(tiers["shared"]["heal_wait_frames"], 0)  # 偏离 D13：donor 的 300 帧去掉

    def test_rework1_skill_description_swaps_the_skill_gauge_line_for_the_heal(self):
        for field in ("desc1", "desc2"):
            desc = DESIGN["texts"][field]
            self.assertNotIn("增加除自身外的队友的技能槽", desc, field)
            self.assertIn("回复生命值低于40%的队友最大生命值35%的生命值", desc, field)

    def test_rework1_ability3_record4_is_a_cooldown_not_a_count_limit(self):
        record = DESIGN["plan"]["ability"]["keys"]["1699913"]["records"][3]
        self.assertEqual(record["cells"]["34"], "(None)")   # 触发次数上限：撤掉「限 5 次」
        self.assertEqual(record["cells"]["35"], "900")      # 触发冷却：900 帧 = 15 秒
        self.assertEqual(record["desc_expected"],
                         "技能发动≥1(CT15秒) → 赋予除自身全员(暗) 技能槽 10%")

    def test_rework1_block_records_the_previous_values(self):
        block = DESIGN["rework1"]
        self.assertEqual({c["id"] for c in block["changes"]}, {"R1", "R2", "R3"})
        before = block["before_snapshot"]
        self.assertIn("增加除自身外的队友的技能槽", before["texts.desc1"])
        self.assertEqual(before["plan.ability.keys.1699913.records[3]"]["desc_expected"],
                         "技能发动≥1(限5次) → 赋予除自身全员(暗) 技能槽 10%")
        self.assertTrue(block["zero_precedent"])

    def test_effects_plan_clones_nothing(self):
        effects = DESIGN["plan"]["skills"]["effects"]
        self.assertEqual(effects["clone"], [])
        self.assertEqual([e["path"] for e in effects["reuse"]], [K.SHARED_EFFECT])

    def test_voice_route_matches_the_module(self):
        route = DESIGN["voice"]["route"]
        self.assertEqual(int(route["kind"]), K.VOICE_ROUTE["kind"])
        self.assertEqual(str(route["threshold"]), K.VOICE_ROUTE["threshold"])
        self.assertEqual(len(DESIGN["voice"]["lines"]), 22)
        for line in DESIGN["voice"]["lines"]:
            self.assertTrue(line.get("ja"), line)
            self.assertTrue(line.get("zh"), line)
            self.assertLessEqual(len(line["zh"]), 82, line)

    def test_deviations_are_registered_with_reasons(self):
        ids = [d["id"] for d in DESIGN["deviations"]]
        self.assertEqual(ids, sorted(ids, key=lambda s: int(s[1:])))
        # kit 阶段自查补登三条 + rework1 补登三条
        self.assertLessEqual({"D9", "D10", "D11", "D12", "D13", "D14"}, set(ids))
        for item in DESIGN["deviations"]:
            self.assertTrue(item.get("planned") and item.get("actual") and item.get("reason"), item)


class DslToolTests(unittest.TestCase):
    def test_remap_binding_shifts_every_lookup_slot(self):
        block = ["FindAllSubjects", 0, 97, [], [], [], [], [], ["DoNothing"],
                 ["Block", [_command("CreateCondition", 0, [["ACPiercing", [{"min": 60, "max": 60}]]]),
                            _command("FindAllSubjects", 1, 113, [6], [], [], [], [], ["DoNothing"],
                                     ["Block", [_command("DeleteCondition", 1, ["DCAll", 3])]])]]]
        K._remap_binding(["Block", [["Command", block]]], 4)
        self.assertEqual(block[1], 4)
        inner = list(wf_dsl.iter_dsl_commands(block, "CreateCondition"))
        self.assertEqual([c[1] for c in inner], [4])
        self.assertEqual([f[1] for f in wf_dsl.iter_dsl_commands(block, "FindAllSubjects")], [5])
        self.assertEqual([d[1] for d in wf_dsl.iter_dsl_commands(block, "DeleteCondition")], [5])
        self.assertEqual(block[3], [])                     # 选择器参数不是绑定位，不许被平移

    def test_remap_binding_refuses_commands_with_other_lookup_slots(self):
        # 记忆卡 wf-dsl-subject-lookup-map：CreateHitArea p1 / ShowEffect p2 等都要单独重映射，
        # 移植块里出现它们时必须报错而不是猜。
        block = ["FindAllSubjects", 0, 97, [], [], [], [], [], ["DoNothing"],
                 ["Block", [_command("ShowEffect", "x", ["SpecifyEffectDirectly", "a/b"], 0)]]]
        with self.assertRaises(K.KitError):
            K._remap_binding(["Block", [["Command", block]]], 4)

    def test_write_dsl_checked_rejects_the_wrapper_shape(self):
        # 记忆卡 wf-dsl-encode-wrapper-trap：喂 {tree, numbers} 包装壳 = 进战斗 F1034
        with self.assertRaises(K.KitError):
            K._write_dsl_checked(None, "x", {"tree": ["ActionDsl"], "numbers": []})
        with self.assertRaises(K.KitError):
            K._write_dsl_checked(None, "x", ["Block", []])

    def test_assert_effects_are_shared_rejects_character_owned_paths(self):
        good = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
                ["Block", [_command("ShowEffect", "x", ["ResolveByElement", K.SHARED_EFFECT, 255], 0)]]]
        K._assert_effects_are_shared(good, "1")
        bad = copy.deepcopy(good)
        bad[11][1][0][1][2] = ["SpecifyEffectDirectly", "battle/effect/skill_unique/blackflower_wiz/x"]
        with self.assertRaises(K.KitError):
            K._assert_effects_are_shared(bad, "1")
        donor_hit = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
                     ["Block", [_command("CreateNormalAttack", 2, 255, [], [], 13,
                                         [{"min": 5, "max": 5}], [{"min": 0, "max": 0}],
                                         False, False, False, False, False,
                                         [{"min": 2, "max": 2}], [{"min": 1, "max": 1}],
                                         ["SpecifyHitEffectDirectly", ["SpecifyEffectDirectly", "a/b"], False],
                                         True)]]]
        with self.assertRaises(K.KitError):
            K._assert_effects_are_shared(donor_hit, "2")

    def test_ban_forbidden_leader_kinds(self):
        row = [""] * KL.LEADER_NCOLS
        row[45], row[107] = "32", ""
        K._ban_forbidden_leader_kinds([row])
        for col, kind in ((45, "422"), (107, "724"), (45, "713")):
            bad = list(row)
            bad[col] = kind
            with self.assertRaises(K.KitError):
                K._ban_forbidden_leader_kinds([bad])


# ---------------------------------------------------------------- 2. 官方基线

@unittest.skipUnless(_BASELINE and bool(DESIGN), "needs the official .cdn/cn baseline + live store")
class RowAssemblyTests(unittest.TestCase):
    def test_leader_and_ability_rows_assemble_and_describe_as_designed(self):
        leader_rows, leader_evidence = K.build_leader_rows(ctx(), DESIGN)
        self.assertEqual(len(leader_rows), K.LEADER_ROW_COUNT)
        for row in leader_rows:
            self.assertEqual(row[0], K.CODE)
            self.assertEqual(len(row), KL.LEADER_NCOLS)
        ability_rows, ability_evidence = K.build_ability_rows(ctx(), DESIGN)
        self.assertEqual(sum(len(v) for v in ability_rows.values()), K.ABILITY_RECORD_COUNT)
        for slot, key_name in enumerate(K.ABILITY_KEYS, start=1):
            KL.check_ability_key(ability_rows[key_name], key_name, K.CODE, slot)
        # 本角色不依赖任何客户端补丁：20 行一个 capability 都不该要
        self.assertEqual(sorted({c for ev in leader_evidence + ability_evidence
                                 for c in ev["capabilities"]}), [])

    def test_pf_kind_rows_leave_the_target_column_empty(self):
        """PF 类 kind（55/200/248/28/718/226）官方口径 target 全空；写 5/7 会让面板说谎。"""
        leader_rows, _ = K.build_leader_rows(ctx(), DESIGN)
        for n, row in enumerate(leader_rows):
            if row[45] in ("55", "200", "248"):
                self.assertEqual(row[46], "", f"leader#{n}")
        ability_rows, _ = K.build_ability_rows(ctx(), DESIGN)
        for key_name, rows in ability_rows.items():
            for i, row in enumerate(rows):
                if row[47] in ("55", "200", "248", "28", "718", "226"):
                    self.assertEqual(row[48], "", f"{key_name}#{i}")

    def test_build_row_catches_a_describe_drift(self):
        entry = copy.deepcopy(DESIGN["plan"]["leader_ability"]["rows"][0])
        entry["desc_expected"] = "这不是面板会显示的文字"
        design = copy.deepcopy(DESIGN)
        design["plan"]["leader_ability"]["rows"] = [entry]
        with self.assertRaises(K.KitError):
            K.build_leader_rows(ctx(), design)

    def test_skill_trees_assemble_for_both_levels(self):
        for level in ("1", "2"):
            tier = K.SKILL_TIERS[level]
            tree, gates = K.build_skill_tree(ctx(), level)
            self.assertEqual(tree[0], "ActionDsl")
            self.assertEqual(tree[10], 0, "技能伤害归属：根头保持 0，不写 3")

            areas = list(wf_dsl.iter_dsl_commands(tree, "CreateHitArea"))
            self.assertEqual(len(areas), 1)
            area = areas[0]
            self.assertEqual(area[9], ["Circle", [{"min": K.HIT_RADIUS, "max": K.HIT_RADIUS}]])
            self.assertEqual(area[13], ["SpecifyHitAreaLifetimeDirectly", K.HIT_LIFETIME])
            self.assertEqual(area[14], ["SpecifyMinHitIntervalDirectly", K.MIN_HIT_INTERVAL])
            self.assertEqual(area[15], ["Some", [{"min": K.TOTAL_HITS, "max": K.TOTAL_HITS}]])

            cnas = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
            self.assertEqual(len(cnas), 1)
            self.assertEqual(cnas[0][1], K.SPINE_HIT_BINDING)
            self.assertEqual(cnas[0][2], 255)              # 继承持有者；写 5/6 会打成别的属性
            self.assertEqual(cnas[0][6], [dict(tier["cna"])])
            self.assertEqual(cnas[0][15], K.HIT_EFFECT)

            tol = K._cc_commands(tree, "ACToleranceOfElement")
            self.assertEqual(len(tol), 2)
            self.assertEqual([c[2][0][2] for c in tol],
                             [K.TOLERANCE_ELEMENT_SELF, K.TOLERANCE_ELEMENT_ALL])
            self.assertEqual([c[2][0][3] for c in tol],
                             [[dict(tier["tolerance_self"])], [dict(tier["tolerance_all"])]])
            self.assertEqual([c[12] for c in tol], [True, True])   # 第 12 位 = forceApply
            self.assertEqual([c[10] for c in tol], [3, 3])         # 付与对象种类：命中的敌人

            frozen = K._cc_commands(tree, "ACFrozen")
            self.assertEqual(len(frozen), 1)
            self.assertEqual(frozen[0][2][0][1], [{"min": tier["frozen"], "max": tier["frozen"]}])
            self.assertIs(frozen[0][12], False, "迟缓不开强制付与")

            pf = K._cc_commands(tree, "ACPowerFlipDamage")
            pierce = K._cc_commands(tree, "ACPiercing")
            self.assertEqual(len(pf), 1)
            self.assertEqual(len(pierce), 1)
            self.assertEqual(pf[0][2][0][1], [{"min": tier["pf_frames"], "max": tier["pf_frames"]}])
            self.assertEqual(pf[0][2][0][2], [dict(tier["pf_value"])])
            self.assertEqual(pierce[0][2][0][1], [{"min": tier["piercing"], "max": tier["piercing"]}])
            self.assertEqual([pf[0][10], pierce[0][10]], [2, 2])   # 配选择器 97，错配 = C16102

            finds = {f[2]: f[1] for f in wf_dsl.iter_dsl_commands(tree, "FindAllSubjects")}
            self.assertEqual(finds[K.SPINE_ALLY_SELECTOR], K.SPINE_ALLY_BINDING)
            self.assertEqual(finds[97], K.BUFF_BINDING_SHIFT)
            self.assertEqual(finds[113], K.BUFF_BINDING_SHIFT + 1)
            self.assertEqual(finds[145], K.BUFF_BINDING_SHIFT + 2)

            # rework1：技能不再给队友技能槽，队友块里只剩条件治疗
            self.assertEqual(list(wf_dsl.iter_dsl_commands(tree, "AddSkillPoint")), [])
            self.assertIsNone(gates["add_skill_point"])
            conds = list(wf_dsl.iter_dsl_commands(tree, "ConditionalsHealthPointRatioOf"))
            self.assertEqual(len(conds), 1)
            self.assertEqual(conds[0][1], K.SPINE_ALLY_BINDING)    # lookup 位＝所在 FindAllSubjects 绑定
            self.assertEqual(conds[0][2], K.HEAL_HP_THRESHOLD)
            # 空分支必须是 ["Block", []]；写 ["DoNothing"] ⇒ 进游戏 F1009
            self.assertEqual(conds[0][3], ["Block", []])
            heals = list(wf_dsl.iter_dsl_commands(tree, "CreateRatioHeal"))
            self.assertEqual(len(heals), 1)
            self.assertEqual(heals[0][1], K.SPINE_ALLY_BINDING)
            self.assertEqual(heals[0][2], K.HEAL_BASIS)
            self.assertEqual(heals[0][3], [dict(tier["heal_ratio"])])
            self.assertEqual(heals[0][6], K.HEAL_HIT_EFFECT)
            # 治疗只能长在 else 分支（＝HP 低于阈值）里，不能漏到 then 或块外
            self.assertEqual(list(wf_dsl.iter_dsl_commands(conds[0][4], "CreateRatioHeal")), heals)
            # 偏离 D13：donor 自带的 Event Wait 300 包装已去掉
            self.assertEqual(K._dsl_events(conds[0], "Wait"), [])
            self.assertEqual(gates["heal"]["ratio"], dict(tier["heal_ratio"]))
            self.assertEqual(gates["heal"]["selector"], K.SPINE_ALLY_SELECTOR)

            self.assertEqual(K._dsl_problems(tree, element=K.ELEMENT), [])
            self.assertEqual(gates["cna_total"], tier["cna"]["max"] * K.TOTAL_HITS)
            self.assertEqual(gates["bta_tree10"], 0)

    def test_skill_trees_only_reference_the_shared_effect(self):
        for level in ("1", "2"):
            tree, _ = K.build_skill_tree(ctx(), level)
            paths = [c[2][1] for c in wf_dsl.iter_dsl_commands(tree, "ShowEffect")]
            self.assertEqual(set(paths), {K.SHARED_EFFECT}, level)

    def test_enhanced_tier_is_strictly_stronger(self):
        base, _ = K.build_skill_tree(ctx(), "1")
        enhanced, _ = K.build_skill_tree(ctx(), "2")
        self.assertNotEqual(base, enhanced)
        b = list(wf_dsl.iter_dsl_commands(base, "CreateNormalAttack"))[0][6][0]["max"]
        e = list(wf_dsl.iter_dsl_commands(enhanced, "CreateNormalAttack"))[0][6][0]["max"]
        self.assertLess(b, e)

    def test_action_skill_rows_use_the_lineage_shape(self):
        rows = K._official_action_rows(ctx(), K.LINEAGE_CODE)
        self.assertEqual(sorted(rows), ["1", "2"])
        want = DESIGN["plan"]["skills"]["action_skill_row"]
        for level, cells in rows.items():
            self.assertEqual(cells[2], want["c2_motion"], level)
            self.assertEqual(cells[8], want["c8"], level)
            self.assertEqual(cells[10], want["c10"], level)


# ---------------------------------------------------------------- 3. 已构建的 workspace

@unittest.skipUnless((WORKSPACE / "evidence/kit-report.json").is_file(),
                     "workspace ma-rebecca has not been built yet")
class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = MC.MAPack(MS.get_spec("rebecca"), record_sources=False)
        cls.report = json.loads((WORKSPACE / "evidence/kit-report.json").read_text("utf-8"))
        cls.claims = json.loads((WORKSPACE / "evidence/table_claims.json").read_text("utf-8"))

    def claimed(self, logical: str) -> set[str]:
        return {key for entry in self.claims if entry["logical_path"] == logical
                for key in entry["outer_keys"]}

    def test_package_carries_the_single_self_owned_shared_key(self):
        switched = C.core.load_nested_table_bytes(
            self.pack.pkg_path("common", KL.SWITCHED).read_bytes(), KL.SWITCHED)
        self.assertIn(K.VOICE_KEY, switched.rows)
        self.assertEqual(self.claimed(MS.UNIQUE_CONDITION_LOGICAL), set())
        self.assertEqual(self.claimed(KL.CAS), set())

    def test_every_self_owned_key_is_claimed(self):
        self.assertIn(K.VOICE_KEY, self.claimed(KL.SWITCHED))
        self.assertEqual(self.claimed(KL.ABILITY), set(K.ABILITY_KEYS))
        self.assertEqual(self.claimed(KL.LEADER), {str(K.CID)})

    def test_package_ability_rows_match_the_design_describe(self):
        rows = self.pack.pkg_flat(KL.ABILITY)
        for slot, key_name in enumerate(K.ABILITY_KEYS, start=1):
            records = C.csv_split(rows[key_name])
            plan = DESIGN["plan"]["ability"]["keys"][key_name]["records"]
            self.assertEqual(len(records), len(plan), key_name)
            for record, entry in zip(records, plan):
                self.assertEqual(record[0], f"{K.CODE}_{slot}")
                self.assertEqual(KL.describe("ability", record), entry["desc_expected"])
                self.assertEqual(KL.row_problems("ability", record, K.ELEMENT), {})

    def test_package_leader_rows_match_the_design_describe(self):
        records = C.csv_split(self.pack.pkg_flat(KL.LEADER)[str(K.CID)])
        plan = DESIGN["plan"]["leader_ability"]["rows"]
        self.assertEqual(len(records), len(plan))
        for record, entry in zip(records, plan):
            self.assertEqual(KL.describe("leader_ability", record), entry["desc_expected"])
        K._ban_forbidden_leader_kinds(records)

    def test_written_dsl_round_trips_and_keeps_the_new_numbers(self):
        for level in ("1", "2"):
            program = f"battle/action/skill/action/rare5/{K.CODE}${K.CODE}_{level}"
            logical = wf_dsl.dsl_logical(program)
            tree = C.amf_parse(self.pack.pkg_path("common", logical).read_bytes())
            self.assertEqual(tree[0], "ActionDsl", logical)
            self.assertEqual(tree[10], 0, logical)
            cna = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
            self.assertEqual(len(cna), 1)
            self.assertEqual(cna[0][6], [dict(K.SKILL_TIERS[level]["cna"])])
            self.assertEqual(len(K._cc_commands(tree, "ACToleranceOfElement")), 2)
            pierce = K._cc_commands(tree, "ACPiercing")[0][2][0][1][0]
            self.assertEqual(pierce["max"], K.SKILL_TIERS[level]["piercing"])
            # rework1：落盘的树里确实没有 AddSkillPoint，条件治疗带着新比例
            self.assertEqual(list(wf_dsl.iter_dsl_commands(tree, "AddSkillPoint")), [], logical)
            heal = list(wf_dsl.iter_dsl_commands(tree, "CreateRatioHeal"))
            self.assertEqual(len(heal), 1, logical)
            self.assertEqual(heal[0][3], [dict(K.SKILL_TIERS[level]["heal_ratio"])], logical)

    def test_action_skill_energy_and_motion(self):
        inner = {lv: C.csv_split(v)[0] for lv, v in C.core.load_nested_table_bytes(
            self.pack.pkg_path("common", KL.ACTION).read_bytes(), KL.ACTION
        ).rows[K.CODE].text_rows().items()}
        energy = DESIGN["plan"]["skills"]["energy"]
        motion = DESIGN["plan"]["skills"]["action_skill_row"]["c2_motion"]
        for level in ("1", "2"):
            cells = inner[level]
            self.assertEqual(cells[2], motion, level)
            self.assertEqual([cells[4], cells[5]], [str(energy[level][0]), str(energy[level][1])], level)
            self.assertTrue(cells[7].endswith(f"{K.CODE}_{level}"), cells[7])

    def test_character_row_routes_the_voice(self):
        row = self.pack.pkg_character_row()
        self.assertEqual(row[9:17], KL.voice_route(K.CODE, K.VOICE_ROUTE))
        self.assertEqual(row[6], "3")
        self.assertEqual(row[26], "Supporter")
        self.assertEqual(row[27], str(K.CID))

    def test_report_status_and_gate(self):
        gate = self.report["kit_gate"]
        self.assertEqual(gate["rows"], K.LEADER_ROW_COUNT + K.ABILITY_RECORD_COUNT)
        self.assertEqual(gate["programs"], 2)
        expected = KL.READY if gate["pixel_present"] and not gate["pixel_missing"] else KL.DRAFT
        self.assertEqual(self.report["status"], expected)
        self.assertEqual(self.report["skill_multipliers"], {"1": 32.0, "2": 40.0})

    def test_report_panel_and_capabilities(self):
        self.assertEqual(self.report["cid"], K.CID)
        self.assertEqual(len(self.report["panel"]), K.ABILITY_RECORD_COUNT)
        for text in self.report["panel"]:
            self.assertEqual(KL.panel_problems(text), [], text)
        self.assertEqual(self.report["required_capabilities"], [])
        self.assertEqual(self.report["effect_families"], [])
        self.assertEqual(self.report["unique_condition"], {})

    def test_report_carries_every_design_deviation(self):
        self.assertEqual({d["id"] for d in self.report["deviations"]},
                         {d["id"] for d in DESIGN["deviations"]})

    def test_no_effect_family_was_cloned_into_the_package(self):
        root = self.pack.pkg_path("common", f"battle/effect/skill_unique/{K.CODE}")
        self.assertFalse(root.exists(), f"{root} —— 本角色零特效克隆（裁决 §4）")


if __name__ == "__main__":
    unittest.main()
