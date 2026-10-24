# -*- coding: utf-8 -*-
"""丝缇涅尔 kit（159995 ``still_obstinator_moon``）rework1：行计划自查 + 行装配 + 技能/PF 树门禁。

三组用例：

1. **纯静态**（不需要 live / 官方基线）：模块常量与 ``design/stinel.json`` 的 ``rework1`` 段互锁、
   裁决 §8 的自查（队长表禁 422/724/713、零固有状态、c1/c2 每键单值、面板禁词、
   536/722/desc_override 四个 string 键都已声明），以及纯树变换小工具
   （``_write_dsl_checked`` 的包装壳拦截、``retune_presentation``/``boost_alv`` 的母本漂移断言）。
2. **官方基线**（缺 ``.cdn/cn`` 或 live store 时跳过）：9+16 行逐行装配并与计划登记的
   ``wf_describe`` 回读逐字比对；两棵技能树与三棵 722 树的嫁接、主体重映射与四道门。
3. **已构建的 workspace**（``work/character_packs/ma-stinel`` 不存在时跳过）：包内自有键、
   认领、kit-report、技能能量、语音路由、特效族、``power_flip_action``。

不写 live store / ``assets/`` / ``.cdn``，不跑发布；官方基线只读。
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
import wf_midautumn_kit_stinel as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_build as B  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402

ROOT = core.project_root()
DESIGN = MS.load_design(ROOT, "stinel")
WORKSPACE = ROOT / "work/character_packs/ma-stinel"


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


_BASELINE = _baseline_available()
_CTX = None


def ctx():
    """只读上下文：``record_sources=False`` ⇒ 母本取数不写 workspace（框架 §10.2）。"""
    global _CTX
    if _CTX is None:
        _CTX = B.KitContext(MC.MAPack(MS.get_spec("stinel"), record_sources=False))
    return _CTX


def fake_family() -> dict:
    """``clone_effect_family`` 结果的只读替身（测树装配时不往包里写特效）。"""
    return {"src_dir": K.FX_SRC_DIR, "dst_dir": K.FX_DST_DIR, "donor": K.TEMPLATE_CODE,
            "dst_name": K.FX_SUBDIR, "copied_bases": [K.FX_FUNNEL, K.FX_EXPLOSION]}


def graft_parts():
    return K.pick_graft_blocks(ctx().template_dsl(K.GRAFT_PROGRAM.format(lv="2")))


# ---------------------------------------------------------------- 1. 纯静态

class ConstantTests(unittest.TestCase):
    def test_identity_matches_the_registry(self):
        spec = MS.get_spec("stinel")
        self.assertEqual((spec.cid, spec.code), (K.CID, K.CODE))
        self.assertEqual((spec.template_id, spec.template_code), (K.TEMPLATE_ID, K.TEMPLATE_CODE))
        self.assertEqual(spec.element, K.ELEMENT)
        self.assertEqual(spec.pf_type, K.PF_TYPE)
        self.assertEqual(spec.stance, K.STANCE)

    def test_ability_keys_are_the_six_slots(self):
        self.assertEqual(K.ABILITY_KEYS, tuple(f"{K.CID}{n}" for n in range(1, 7)))
        self.assertEqual(sorted(K.ABILITY), [1, 2, 3, 4, 5, 6])

    def test_row_counts_match_the_plan(self):
        self.assertEqual(len(K.LEADER), K.LEADER_ROWS)
        self.assertEqual(sum(len(records) for _, _, records in K.ABILITY.values()),
                         K.ABILITY_RECORDS)

    def test_spec_declares_every_self_owned_key(self):
        declared = K.SPEC["extra_keys"]
        self.assertEqual(sorted(declared[KL.CAS]), sorted(K.CAS_TEXTS))
        self.assertEqual(declared[KL.SWITCHED], (K.VOICE_KEY,))
        self.assertEqual(declared[K.PFA], (K.PF_KEY,))
        self.assertIn("panel-description-override-v2", K.SPEC["required_capabilities"])

    def test_string_keys_are_self_consistent(self):
        self.assertEqual(K.PF_STRING, f"override_string_{K.PF_KEY}")
        self.assertEqual(K.LEADER_OVERRIDE, f"desc_override_{K.CODE}")
        self.assertEqual(K.SLOT3_OVERRIDE, f"desc_override_{K.CODE}_3")
        # 722 的 override_string_* 不需要 APK 补丁；desc_override_* 需要 v2
        self.assertIsNone(L.panel_override_capability(K.PF_STRING))
        for key in (K.LEADER_OVERRIDE, K.SLOT3_OVERRIDE):
            self.assertEqual(L.panel_override_capability(key), "panel-description-override-v2")

    def test_effect_family_naming(self):
        self.assertEqual(K.FX_SRC_DIR, f"battle/effect/skill_unique/{K.TEMPLATE_CODE}")
        self.assertEqual(K.FX_DST_DIR, f"battle/effect/skill_unique/{K.CODE}/{K.FX_SUBDIR}")
        self.assertTrue(K.FX_FUNNEL.startswith(K.TEMPLATE_CODE))
        self.assertTrue(K.FX_EXPLOSION.startswith(K.TEMPLATE_CODE))

    def test_pf_programs_live_under_the_override_namespace(self):
        self.assertEqual(len(K.PF_PROGRAMS), 3)
        for n, program in enumerate(K.PF_PROGRAMS, start=1):
            self.assertEqual(program,
                             f"battle/action/power_flip/action/override/"
                             f"{K.PF_KEY}${K.PF_KEY}_lv{n}")
        self.assertEqual(sorted(K.SPECIAL_SHA), [1, 2, 3])
        self.assertEqual(sorted(K.PF_PIERCE_FRAMES), [1, 2, 3])

    def test_subject_remap_offsets_the_graft_by_four(self):
        self.assertEqual(K.SUBJECT_BASE, 4)
        self.assertEqual(K.SUBJECT_REMAP, {n: n + 4 for n in range(5)})

    def test_light_values_differ_between_the_two_lamps(self):
        """A/B 两盏灯的数值与时长都必须不同，否则 gid 相同会互相覆盖（设计 §6.2 风险 R1）。"""
        for level, pair in K.LIGHT_VALUES.items():
            self.assertNotEqual(pair["a"][0], pair["b"][0], level)
            self.assertNotEqual(pair["a"][1], pair["b"][1], level)

    def test_alv_boost_lands_on_eighty(self):
        """作者「强化技能威力为 80」＝ 母本满级 43 + alv 37。"""
        self.assertEqual(43.0 + K.SKILL_ALV_BOOST, 80.0)
        self.assertEqual(K.TEMPLATE_ALV, (3.5, 7))

    def test_presentation_constants_follow_research_card_c(self):
        self.assertEqual(K.STOP_BALL_TEMPLATE[1:3], [90, ["Stop"]])
        self.assertEqual(K.STOP_BALL_DONOR[1:3], [30, ["RestoreToSpeedBeforeActionExecution"]])
        self.assertEqual(K.STOP_BALL_DONOR[0], -18)
        self.assertEqual((K.HIT_AREA_TEMPLATE_RADIUS, K.HIT_AREA_RADIUS), (150, 250))
        self.assertEqual(K.FUNNEL_SCALE, 1.5)

    def test_voice_route_is_change_skill_flag(self):
        self.assertEqual(K.VOICE_ROUTE, {"kind": 3})
        self.assertEqual(K.VOICE_KEY, KL.switch_key(K.CODE))

    def test_write_dsl_checked_rejects_the_wrapper_shape(self):
        """``encode_amf3`` 只吃裸树；喂 ``{tree, numbers}`` 包装壳＝进战斗 F1034。"""
        with self.assertRaises(K.KitError):
            K._write_dsl_checked(None, "x", {"tree": ["ActionDsl"], "numbers": []})

    def test_leader_plan_carries_no_patched_kinds(self):
        """422/724/713 写进队长表 = C7050（裁决 §2/§8）。"""
        for tag, _donor, _src, cells, _desc in K.LEADER:
            for col in (45, 107):
                self.assertNotIn(str(cells.get(col, "")), K.FORBIDDEN_LEADER_KINDS, tag)

    def test_fever_kind_lives_in_the_ability_table_only(self):
        fever = [cells for _tag, _d, _s, cells, desc in K.ABILITY[3][2] if "Fever" in desc]
        self.assertEqual(len(fever), 1)

    def test_main_position_slots_match_the_panel(self):
        for slot, (unisonable, _sg, _records) in K.ABILITY.items():
            self.assertEqual(unisonable, "false" if slot in (3, 6) else "true", slot)

    def test_panel_texts_obey_the_batch_rules(self):
        for text in K.PANEL_LEADER + K.PANEL_SLOT3:
            self.assertEqual(KL.panel_problems(text), [], text)
        # 536 条目不写数字与时间（裁决 §3）
        self.assertEqual(KL.panel_problems(K.CAS_TEXTS[K.CAS_CHANGE_SKILL], skill_flag=True), [])

    def test_slot3_override_carries_the_main_icon_on_every_line(self):
        lines = K.CAS_TEXTS[K.SLOT3_OVERRIDE].split("\n")
        self.assertEqual(len(lines), len(K.PANEL_SLOT3))
        for line in lines:
            self.assertTrue(line.startswith(K.MAIN_ICON), line)

    def test_leader_override_line_count_matches_the_panel(self):
        self.assertEqual(K.CAS_TEXTS[K.LEADER_OVERRIDE].split("\n"), list(K.PANEL_LEADER))

    def test_deviations_are_registered_with_reasons(self):
        self.assertGreaterEqual(len(K.DEVIATIONS), 9)
        for entry in K.DEVIATIONS:
            for field in ("id", "want", "got", "why"):
                self.assertTrue(entry.get(field), entry)


class DesignSelfCheckTests(unittest.TestCase):
    """设计稿 ``rework1`` 段与模块常量的互锁（``plan`` 块是上一轮的历史，不参与）。"""

    def setUp(self):
        if not DESIGN:
            self.skipTest("design/stinel.json missing")
        self.rework = DESIGN.get("rework1") or {}
        if not self.rework:
            self.skipTest("design/stinel.json has no rework1 block")

    def test_design_identity_matches_the_module(self):
        self.assertEqual(DESIGN["schema"], "ma-design/1")
        self.assertEqual(DESIGN["cid"], K.CID)
        self.assertEqual(DESIGN["code"], K.CODE)

    def test_history_block_is_preserved(self):
        self.assertIn("plan", DESIGN)
        self.assertTrue(self.rework.get("history_note"))

    def test_row_counts_agree_with_the_module(self):
        self.assertEqual(self.rework["leader_ability"]["rows"], K.LEADER_ROWS)
        self.assertEqual(self.rework["leader_ability"]["panel_rows"], len(K.PANEL_LEADER))
        self.assertEqual(self.rework["ability"]["records"], K.ABILITY_RECORDS)
        self.assertEqual({key: len(records) for key, (_u, _s, records)
                          in zip(K.ABILITY_KEYS, K.ABILITY.values())},
                         {k: v for k, v in self.rework["ability"]["keys"].items()})

    def test_no_unique_condition_is_added(self):
        self.assertEqual(self.rework["unique_conditions"]["add"], [])

    def test_energy_agrees_with_the_module(self):
        energy = self.rework["texts"]["action_skill_energy"]
        for level in ("level_1", "level_2"):
            self.assertEqual([str(v) for v in energy[level]], list(K.ENERGY), level)

    def test_pf_override_agrees_with_the_module(self):
        pf = self.rework["skills"]["pf_override"]
        self.assertEqual(pf["power_flip_action"]["key"], K.PF_KEY)
        self.assertEqual(pf["power_flip_action"]["value"], list(K.PF_PROGRAMS))
        self.assertEqual(float(pf["scale_scalar"]), K.PF_SCALE)
        self.assertEqual({int(k): v for k, v in pf["pierce_frames"].items()}, K.PF_PIERCE_FRAMES)

    def test_string_keys_agree_with_the_module(self):
        self.assertEqual(sorted(self.rework["texts"]["custom_ability_string"]),
                         sorted(K.CAS_TEXTS))

    def test_deviation_ids_agree_with_the_module(self):
        self.assertEqual([e["id"] for e in self.rework["deviations_new"]],
                         [e["id"] for e in K.DEVIATIONS])

    def test_voice_block_is_complete(self):
        route = DESIGN.get("voice", {}).get("route")
        self.assertEqual(int(route["kind"]), K.VOICE_ROUTE["kind"])


# ---------------------------------------------------------------- 2. 官方基线

@unittest.skipUnless(_BASELINE, "official baseline / live store not available")
class RowAssemblyTests(unittest.TestCase):
    def test_leader_rows_assemble_and_describe_as_planned(self):
        rows, evidence = K.build_leader_rows(ctx())
        self.assertEqual(len(rows), K.LEADER_ROWS)
        for row, (tag, _d, _s, _c, expect) in zip(rows, K.LEADER):
            self.assertEqual(row[0], K.CODE, tag)
            self.assertEqual(len(row), KL.LEADER_NCOLS, tag)
        self.assertEqual([ev["describe"] for ev in evidence],
                         [entry[4] for entry in K.LEADER])

    def test_every_leader_row_carries_the_light_resonance_gate(self):
        """作者补充 09-21 00:5x「都是属性共鸣」⇒ 9 行全挂光编成≥6 前置（偏离 D-2）。"""
        rows, _ = K.build_leader_rows(ctx())
        for n, row in enumerate(rows):
            self.assertEqual((row[4], row[7], row[8], row[9]),
                             ("2", "600000", "600000", "White"), f"leader#{n}")

    def test_pf_override_row_points_at_the_three_programs(self):
        rows, _ = K.build_leader_rows(ctx())
        pf = rows[0]
        self.assertEqual(pf[45], "722")
        self.assertEqual(pf[80], K.PF_KEY)
        self.assertEqual(pf[81], "1,2,3")
        self.assertEqual(pf[82], K.PF_STRING)

    def test_timed_attack_row_uses_condition_attack_point(self):
        """kind 0 ConditionAttackPoint（带帧数的状态）≠ kind 32 AttackPoint（常驻定值）。"""
        rows, _ = K.build_leader_rows(ctx())
        timed = rows[7]
        self.assertEqual(timed[25], "15")            # PowerFlipHitLv1High
        self.assertEqual(timed[45], "0")             # ConditionAttackPoint
        self.assertEqual((timed[55], timed[56]), ("48000000", "48000000"))   # 480 帧 = 8 秒
        self.assertEqual(timed[59], "(None)")        # 可叠加，无累积上限
        self.assertEqual(rows[3][45], "32")          # 常驻攻击那行仍是 32

    def test_combo_snowball_row_caps_at_five(self):
        rows, _ = K.build_leader_rows(ctx())
        snowball = rows[6]
        self.assertEqual(snowball[25], "12")                          # Combo
        self.assertEqual((snowball[28], snowball[29]), ("25000000",) * 2)   # 250 连击
        self.assertEqual(snowball[32], "5")                           # 最多 +500%

    def test_ability_rows_assemble_and_describe_as_planned(self):
        rows_by_key, evidence = K.build_ability_rows(ctx())
        self.assertEqual(sorted(rows_by_key), sorted(K.ABILITY_KEYS))
        self.assertEqual(sum(len(v) for v in rows_by_key.values()), K.ABILITY_RECORDS)
        self.assertEqual([ev["describe"] for ev in evidence],
                         [entry[4] for slot in sorted(K.ABILITY)
                          for entry in K.ABILITY[slot][2]])

    def test_slot3_splits_the_one_sentence_into_two_rows(self):
        """「自身每获得一个效果 → 连击＋50、技伤＋50% 最多 350%」＝ 瞬发 29 + 持续 37（偏离 D-5）。"""
        rows = K.build_ability_rows(ctx())[0][K.ABILITY_KEYS[2]]
        combo, during = rows[1], rows[2]
        self.assertEqual(combo[27], "29")            # instant ConditionBuff
        self.assertEqual(combo[47], "226")           # AddCombo
        self.assertEqual(combo[34], "7")             # 限 7 次 ＝ 合计 +350 连击
        self.assertEqual(during[97], "37")           # during ConditionCountBuff
        self.assertEqual(during[102], "7")           # 七层 ＝ 最多 +350%
        self.assertEqual(during[109], "2")           # during_content 技能伤害
        self.assertEqual((during[113], during[114]), ("50000", "50000"))

    def test_slot3_peer_skill_rows_share_the_trigger(self):
        rows = K.build_ability_rows(ctx())[0][K.ABILITY_KEYS[2]]
        for col in (27, 28, 29, 30, 31):
            self.assertEqual(rows[3][col], rows[4][col], col)
        self.assertEqual(rows[3][28], "6")           # 除自身合计

    def test_slot6_carries_the_main_position_restriction(self):
        rows_by_key = K.build_ability_rows(ctx())[0]
        for slot in (3, 6):
            for row in rows_by_key[K.ABILITY_KEYS[slot - 1]]:
                self.assertEqual(row[1], "false", slot)

    def test_values_are_flattened_to_the_max_level(self):
        """作者总口径「全部按照满级的描述」⇒ c51 == c52（有强度的行）。"""
        for rows in K.build_ability_rows(ctx())[0].values():
            for row in rows:
                if row[51] or row[52]:
                    self.assertEqual(row[51], row[52], row[:3])

    def test_only_the_fever_row_needs_a_client_capability(self):
        _, evidence = K.build_ability_rows(ctx())
        needed = {ev["label"]: ev["capabilities"] for ev in evidence if ev["capabilities"]}
        self.assertEqual(list(needed.values()), [["kyubi-fever-ratio-v1"]])

    def test_row_assembly_rejects_a_tampered_plan_row(self):
        tag, donor, source, cells, expect = K.LEADER[2]
        broken = dict(cells) | {49: "999999"}
        with self.assertRaises(K.KitError):
            KL.build_row(ctx(), "leader_ability", donor, broken, source=source,
                         expect_describe=expect, label=tag)


@unittest.skipUnless(_BASELINE, "official baseline / live store not available")
class SkillTreeTests(unittest.TestCase):
    def test_both_levels_assemble_and_pass_the_gates(self):
        for level in ("1", "2"):
            tree, gates = K.build_skill_tree(ctx(), level, fake_family())
            self.assertEqual(tree[0], "ActionDsl", level)
            self.assertEqual(tree[10], 0, level)          # 自动档＝技能伤害归属
            self.assertEqual(gates["grafted"], 3, level)
            self.assertEqual(K._dsl_problems(tree, element=K.ELEMENT), [], level)

    def test_presentation_retune_lands(self):
        for level in ("1", "2"):
            tree, gates = K.build_skill_tree(ctx(), level, fake_family())
            stops = list(wf_dsl.iter_dsl_commands(tree, "StopBall"))
            self.assertEqual(len(stops), 1, level)
            self.assertEqual(stops[0][1:], K.STOP_BALL_DONOR, level)
            circles = [c for c in wf_dsl.iter_dsl_commands(tree, "CreateHitArea")
                       if c[9][0] == "Circle"]
            self.assertEqual(circles[0][9][1],
                             [{"min": K.HIT_AREA_RADIUS, "max": K.HIT_AREA_RADIUS}], level)
            self.assertEqual(gates["presentation"]["funnel_scale"], K.FUNNEL_SCALE)

    def test_only_one_funnel_show_effect_survives(self):
        """「只要一排」第一级：母本自带的那一个，kit 不再追加第二个（偏离 D-7）。"""
        for level in ("1", "2"):
            tree, _ = K.build_skill_tree(ctx(), level, fake_family())
            funnels = [c for c in wf_dsl.iter_dsl_commands(tree, "ShowEffect")
                       if isinstance(c[2], list) and str(c[2][1]).endswith(K.FX_FUNNEL)]
            self.assertEqual(len(funnels), 1, level)
            self.assertEqual(funnels[0][-1],
                             ["Some", [{"min": K.FUNNEL_SCALE, "max": K.FUNNEL_SCALE}]], level)

    def test_alv_boost_reaches_eighty_and_keeps_the_base(self):
        tree, gates = K.build_skill_tree(ctx(), "2", fake_family())
        self.assertEqual(gates["alv"]["boosted_total"], 80.0)
        attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
        self.assertEqual(len(attacks), 2)
        self.assertTrue(all(cna[2] == 255 for cna in attacks))       # 元素继承
        plain = [cna for cna in attacks if "alv_min" not in cna[6][0]]
        self.assertEqual(len(plain), 1)
        self.assertEqual(plain[0][6][0]["max"], 43)                  # 非 536 分支不动

    def test_two_skill_damage_conditions_coexist_with_different_ids(self):
        for level in ("1", "2"):
            tree, _ = K.build_skill_tree(ctx(), level, fake_family())
            lamps = [cc for cc in wf_dsl.iter_dsl_commands(tree, "CreateCondition")
                     if cc[2] and cc[2][0][0] == "ACSkillDamage"]
            self.assertEqual(len(lamps), 2, level)
            self.assertNotEqual(lamps[0][2][0][1], lamps[1][2][0][1], level)
            self.assertNotEqual(lamps[0][2][0][2], lamps[1][2][0][2], level)
            for lamp in lamps:
                self.assertEqual(lamp[10], 1)

    def test_graft_subject_ids_do_not_collide_with_the_donor(self):
        tree, _ = K.build_skill_tree(ctx(), "2", fake_family())
        binds = sorted(cmd[1] for cmd in wf_dsl.iter_dsl_commands(tree, "FindAllSubjects"))
        self.assertEqual(binds, [K.SUBJECT_BASE, K.SUBJECT_BASE + 1])
        for cmd in wf_dsl.iter_dsl_commands(tree, "FindAllSubjects"):
            inner = cmd[9][1][0][1]
            self.assertEqual(inner[1], cmd[1])         # CreateCondition p1 == FindAll 绑定 id
        dispel = [c for c in wf_dsl.iter_dsl_commands(tree, "CreateHitArea")
                  if c[9][0] == "Rectangle"]
        self.assertEqual(len(dispel), 1)
        self.assertEqual([dispel[0][s] for s in K.HIT_AREA_SUBJECT_SLOTS], [6, 7, 8])
        delete = dispel[0][K.HIT_AREA_ONHIT_SLOT][1][0][1]
        self.assertEqual((delete[0], delete[1]), ("DeleteCondition", 8))

    def test_light_block_filter_only_narrows_the_full_team_one(self):
        parts = graft_parts()
        full = K.make_light_block(parts, bind=5, light_only=False, frames=900,
                                  value={"min": 0.25, "max": 0.5})
        light = K.make_light_block(parts, bind=4, light_only=True, frames=1200,
                                   value={"min": 0.6, "max": 1.2})
        self.assertEqual(full[1][3], [])                       # 主队全员
        self.assertEqual(light[1][3], parts["unique"][1][3])   # 光属性过滤照抄同树 ACUnique 块
        self.assertEqual(full[1][2], light[1][2])              # selector 不变

    def test_every_effect_ref_lands_inside_the_cloned_family(self):
        for level in ("1", "2"):
            tree, _ = K.build_skill_tree(ctx(), level, fake_family())
            paths = K._effect_paths(tree)
            self.assertTrue(paths)
            for path in paths:
                self.assertTrue(path.startswith(K.FX_DST_DIR + "/"), path)

    def test_graft_picker_needs_all_three_blocks(self):
        parts = graft_parts()
        self.assertEqual(sorted(parts), ["dispel", "skill_damage", "unique"])
        empty = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
                 ["Block", []]]
        with self.assertRaises(K.KitError):
            K.pick_graft_blocks(empty)

    def test_retune_rejects_a_drifted_template(self):
        donor = ctx().template_dsl(ctx().program_path("2").replace(K.CODE, K.TEMPLATE_CODE))
        tampered = copy.deepcopy(donor)
        list(wf_dsl.iter_dsl_commands(tampered, "StopBall"))[0][2] = 91
        with self.assertRaises(K.KitError):
            K.retune_presentation(tampered, "2")

    def test_boost_alv_rejects_a_drifted_template(self):
        donor = ctx().template_dsl(ctx().program_path("2").replace(K.CODE, K.TEMPLATE_CODE))
        tampered = copy.deepcopy(donor)
        for cna in wf_dsl.iter_dsl_commands(tampered, "CreateNormalAttack"):
            if "alv_min" in cna[6][0]:
                cna[6][0]["alv_max"] = 8
        with self.assertRaises(K.KitError):
            K.boost_alv(tampered, "2")


@unittest.skipUnless(_BASELINE, "official baseline / live store not available")
class PowerFlipTreeTests(unittest.TestCase):
    def test_three_levels_assemble_and_pass_the_gates(self):
        for level in (1, 2, 3):
            tree, gates = K.build_pf_tree(ctx(), level)
            self.assertEqual(tree[0], "ActionDsl", level)
            self.assertEqual(tree[1], 1, level)          # special 底座 movementPriority
            self.assertEqual(tree[10], 0, level)
            self.assertEqual(gates["pierce_frames"], K.PF_PIERCE_FRAMES[level])
            self.assertEqual(K._dsl_problems(tree), [], level)

    def test_lifecycle_commands_survive(self):
        """``SetPowerFilpSuppress`` / ``NotifyPowerflipEnd`` 掉了＝球状态错乱（A 卡 §4.2）。"""
        for level in (1, 2, 3):
            tree, _ = K.build_pf_tree(ctx(), level)
            self.assertTrue(wf_dsl.iter_dsl_commands(tree, "SetPowerFilpSuppress").__next__())
            self.assertTrue(wf_dsl.iter_dsl_commands(tree, "NotifyPowerflipEnd").__next__())

    def test_support_block_binds_do_not_collide(self):
        for level in (1, 2, 3):
            _tree, gates = K.build_pf_tree(ctx(), level)
            self.assertIn(K.PF_SUPPORT_BIND, gates["bound_ids"])
            self.assertEqual(gates["bound_ids"].count(K.PF_SUPPORT_BIND), 1)
            self.assertEqual(gates["support_block_bind"], K.PF_SUPPORT_BIND)

    def test_support_block_grants_no_flying(self):
        """作者 09-21「丝缇涅尔也不要浮游」：三档树里 ACFlying 为 0，攻击力提升与贯穿两条仍在。"""
        import json
        import wf_seasonal7_kit_philia as PH
        for level in (1, 2, 3):
            tree, _ = K.build_pf_tree(ctx(), level)
            self.assertNotIn("ACFlying", json.dumps(tree, ensure_ascii=False), level)
            kinds = [c[2][0][0] for c in PH.cmds(tree, "CreateCondition")]
            self.assertEqual(kinds.count("ACAttackPoint"), 1, level)
            self.assertEqual(kinds.count("ACPiercing"), 1, level)

    def test_hit_areas_keep_the_powerflip_multiplier_slot(self):
        """``CreateHitArea`` 第 24 位写 4 ＝ 按直击算，整块 PF 乘区被跳过。"""
        import wf_seasonal7_kit_philia as PH
        for level in (1, 2, 3):
            tree, _ = K.build_pf_tree(ctx(), level)
            for cha in PH.cmds(tree, "CreateHitArea"):
                self.assertEqual(cha[24], 0, level)

    def test_multipliers_are_scaled_uniformly(self):
        """三档统一 ×``PF_SCALE``，逐条对官方底座的原值核算（唯一的缩放旋钮）。"""
        import wf_seasonal7_kit_philia as PH
        for level in (1, 2, 3):
            base = ctx().template_dsl(K.SPECIAL_PROGRAMS[level])
            want = [round(cna[6][0]["min"] * K.PF_SCALE, 6) for cna in PH.cmds(base, "CreateNormalAttack")]
            _tree, gates = K.build_pf_tree(ctx(), level)
            self.assertTrue(want)
            self.assertEqual(gates["multipliers"], want, level)

    def test_official_base_fingerprint_is_locked(self):
        with self.assertRaises(K.KitError):
            K._source_tree(ctx(), K.SPECIAL_PROGRAMS[1], "0" * 64)


# ---------------------------------------------------------------- 3. 已构建的 workspace

@unittest.skipUnless((WORKSPACE / "evidence/kit-report.json").is_file(),
                     "workspace ma-stinel has not been built yet")
class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = MC.MAPack(MS.get_spec("stinel"), record_sources=False)
        cls.report = json.loads((WORKSPACE / "evidence/kit-report.json").read_text("utf-8"))
        cls.claims = json.loads((WORKSPACE / "evidence/table_claims.json").read_text("utf-8"))

    def claimed(self, logical: str) -> set[str]:
        return {key for entry in self.claims if entry["logical_path"] == logical
                for key in entry["outer_keys"]}

    def test_package_carries_the_self_owned_keys(self):
        cas = self.pack.pkg_flat(KL.CAS)
        for key in K.CAS_TEXTS:
            self.assertIn(key, cas)
        switched = C.core.load_nested_table_bytes(
            self.pack.pkg_path("common", KL.SWITCHED).read_bytes(), KL.SWITCHED)
        self.assertIn(K.VOICE_KEY, switched.rows)
        self.assertIn(K.PF_KEY, self.pack.pkg_flat(K.PFA))

    def test_every_self_owned_key_is_claimed(self):
        for key in K.CAS_TEXTS:
            self.assertIn(key, self.claimed(KL.CAS))
        self.assertIn(K.VOICE_KEY, self.claimed(KL.SWITCHED))
        self.assertIn(K.PF_KEY, self.claimed(K.PFA))
        self.assertEqual(self.claimed(KL.ABILITY), set(K.ABILITY_KEYS))
        self.assertEqual(self.claimed(KL.LEADER), {str(K.CID)})
        self.assertEqual(self.claimed(KL.CHARACTER), {str(K.CID)})

    def test_no_unique_condition_key_was_added(self):
        unique = self.pack.pkg_path("common", MS.UNIQUE_CONDITION_LOGICAL)
        if unique.is_file():
            self.assertFalse([k for k in self.pack.pkg_flat(MS.UNIQUE_CONDITION_LOGICAL)
                              if k.startswith(str(K.CID))])
        self.assertEqual(self.claimed(MS.UNIQUE_CONDITION_LOGICAL), set())

    def test_written_dsl_round_trips_and_keeps_the_attribution(self):
        for level in ("1", "2"):
            logical = wf_dsl.dsl_logical(
                f"battle/action/skill/action/rare5/{K.CODE}${K.CODE}_{level}")
            tree = C.amf_parse(self.pack.pkg_path("common", logical).read_bytes())
            self.assertEqual(tree[0], "ActionDsl", logical)
            self.assertEqual(tree[10], 0, logical)
            lamps = [cc for cc in wf_dsl.iter_dsl_commands(tree, "CreateCondition")
                     if cc[2] and cc[2][0][0] == "ACSkillDamage"]
            self.assertEqual(len(lamps), 2, logical)

    def test_power_flip_programs_are_in_the_package(self):
        for program in K.PF_PROGRAMS:
            tree = C.amf_parse(
                self.pack.pkg_path("common", wf_dsl.dsl_logical(program)).read_bytes())
            self.assertEqual(tree[0], "ActionDsl", program)
            self.assertEqual(tree[1], 1, program)
        self.assertEqual(self.pack.pkg_flat(K.PFA)[K.PF_KEY].strip(), ",".join(K.PF_PROGRAMS))

    def test_action_skill_energy_matches_the_plan(self):
        rows = B.KitContext(self.pack).pkg_nested(K.CODE)
        self.assertEqual(sorted(rows), ["1", "2"])
        for level in ("1", "2"):
            cells = list(rows[level])
            self.assertEqual((cells[4], cells[5]), K.ENERGY, level)

    def test_character_row_routes_the_voice(self):
        row = self.pack.pkg_character_row()
        self.assertEqual(row[9:17], KL.voice_route(K.CODE, K.VOICE_ROUTE))
        self.assertEqual(row[6], str(K.PF_TYPE))
        self.assertEqual(row[26], K.STANCE)
        self.assertEqual(row[27], str(K.CID))

    def test_report_status_and_gate(self):
        gate = self.report["kit_gate"]
        self.assertEqual(gate["rows"], K.LEADER_ROWS + K.ABILITY_RECORDS)
        self.assertEqual(gate["programs"], 5)          # 技能 2 + PF 3
        ready = gate["fx_lut_applied"] and gate["pixel_present"] and not gate["pixel_missing"]
        self.assertEqual(self.report["status"], KL.READY if ready else KL.DRAFT)
        if not ready:
            self.assertTrue(gate["reason"])

    def test_report_panel_and_capabilities(self):
        self.assertEqual(self.report["cid"], K.CID)
        self.assertEqual(len(self.report["panel"]),
                         len(K.PANEL_LEADER) + len(K.PANEL_SLOT3) + 1)
        for text in self.report["panel"]:
            self.assertEqual(KL.panel_problems(text), [], text)
        self.assertEqual(self.report["required_capabilities"],
                         ["kyubi-fever-ratio-v1", "panel-description-override-v2"])
        self.assertEqual(len(self.report["deviations"]), len(K.DEVIATIONS))

    def test_effect_family_is_the_only_cloned_one(self):
        families = json.loads((WORKSPACE / "evidence/effect-families.json").read_text("utf-8"))
        self.assertEqual(sorted(families), [K.FX_DST_DIR])
        self.assertEqual(sorted(families[K.FX_DST_DIR]["copied_bases"]),
                         sorted((K.FX_FUNNEL, K.FX_EXPLOSION)))
        self.assertEqual(families[K.FX_DST_DIR]["missing_effects"], [])
        self.assertTrue(families[K.FX_DST_DIR]["complete_family"])

    def test_parts_surgery_left_one_row(self):
        gates = json.loads((WORKSPACE / "evidence/kit-gates.json").read_text("utf-8"))
        surgery = gates.get("parts_surgery")
        if not K.SINGLE_ROW_SURGERY:
            self.assertIsNone(surgery)
            return
        self.assertEqual(surgery["segments_left"], K.FUNNEL_MIRROR_SEGMENTS - 1)
        parts = C.amf_parse(self.pack.pkg_path(
            "medium" if not (self.pack.pkg_path("common", surgery["file"]).is_file()) else "common",
            surgery["file"]).read_bytes())
        segs = parts["g"][K.FUNNEL_MIRROR_GROUP]["s"]
        self.assertEqual(len(segs), K.FUNNEL_MIRROR_SEGMENTS - 1)
        transforms = parts["t"]
        for seg in segs:
            index = (int(seg["l"][0]["m"]) & 0xFFFFFFFF) >> 12
            self.assertGreaterEqual(float(transforms[index].get("a", 4096)), 0)


if __name__ == "__main__":
    unittest.main()
