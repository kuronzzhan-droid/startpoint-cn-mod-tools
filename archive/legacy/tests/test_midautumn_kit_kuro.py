# -*- coding: utf-8 -*-
"""黑（139991 ``outlaw_panther_moon``）kit 的单测 · **rework1**。

纯静态用例（方案自洽、裁决 §8 的自查项、面板文案规则、DSL 变形器、图标绘制）永远跑；
需要官方基线 / live store 的集成用例在缺环境时自动跳过（与 ``test_midautumn_framework`` 同口径）。
不写 live store / ``assets/`` / ``.cdn``，不跑发布，不碰设备。
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_kuro as B2  # noqa: E402
import wf_client_legality as L  # noqa: E402
import wf_midautumn_common as MC  # noqa: E402
import wf_midautumn_kit_kuro as KIT  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_build as B  # noqa: E402


def _live_available() -> bool:
    profile = core.resolve_profile()
    return (profile is not None and profile.store.is_dir()
            and (core.project_root() / "assets" / "mana_node.json").is_file()
            and (core.project_root() / ".cdn" / "cn").is_dir())


_LIVE = _live_available()
_CTX = None

#: 面板行数 = 队长 5 ＋ 词条 2+2+6+1+1+1（desc_override 整块接管，与行数无关）。
#: 2026-09-27 平衡第二批：队长面板 4 → 6 行（wf_balance_20260927b_kuro.LEADER_ADDED_LINES）；
#: 第三轮面板同条件合并（wf_balance_20260927c_kuro）：队长第 1、2 行、能力6 两行各并为一行 ⇒ 20 → 18；
#: 第三轮技能强化条目 R2（同模块第 7 节）：能力3 第 5、6 行（强化分支的抽取表 / 翻倍表）删除 ⇒ 18 → 16。
PANEL_LINES = len(KIT.PANEL_LEADER) + sum(len(v) for v in KIT.PANEL_ABILITY.values())
ABILITY_ROWS = sum(len(v) for v in KIT.ABILITY.values())


def panel_before_balance_b(panel: list[str]) -> list[str]:
    """第一批 kit 产物的面板（2026-09-27 第二批由修订候选回写、不重跑 kit，workspace 的 kit-report
    可能仍是这一版）：去掉队长追加的两行，能力2 第1行、能力3 第2行换回改前文案，第三轮合并的行拆回原两行，
    第三轮口径 3 改过的能力3 第 4 行与第 6 节改过的能力2 第 1 行换回改前文案，第 7 节（R2）改写的能力1 第 2 行换回
    改前文案、能力3 骰运行之后补回删掉的两行（C3.PANEL_LINE_ORIGINS）。"""
    import wf_balance_20260927c_kuro as C3
    swap = {B2.NEW_ABILITY2_LINE: B2.OLD_ABILITY2_LINE,
            B2.NEW_ABILITY3_LINE.replace(KIT.MAIN_ICON, ""): B2.OLD_ABILITY3_LINE.replace(KIT.MAIN_ICON, "")}
    # 第三轮面板统一口径（口径 3 冒号改逗号）改过的能力3 行换回改前文案
    swap.update({C3.NEW_ABILITY3_LINES[i].replace(KIT.MAIN_ICON, ""): C3.OLD_ABILITY3_LINES[i].replace(KIT.MAIN_ICON, "")
                 for i in C3.ABILITY3_FIXES})
    # 第三轮第 6 节（作者追加 5%×25）改过的能力2 第 1 行换回第一批文案（第二批 2%×25 行本身已在 swap 里）
    swap[C3.NEW_ABILITY2_LINES[0]] = B2.OLD_ABILITY2_LINE
    # 队长追加的两行：第二批的数字或第三轮（wf_balance_20260927c_kuro）改后的数字
    added = set(B2.LEADER_ADDED_LINES) | set(C3.LEADER_ADDED_LINES)
    # 第三轮第 7 节（R2）：能力1 强化条目行、能力3 骰运行（其后两行被删）展开回改前原文
    return [x for line in panel if line not in added
            for x in C3.MERGED_LINES.get(line) or C3.PANEL_LINE_ORIGINS.get(line) or (swap.get(line, line),)]


def ctx():
    """只读探针包（``record_sources=False``，不写 workspace，见框架文档 §10.2）。"""
    global _CTX
    if _CTX is None:
        _CTX = B.KitContext(MC.MAPack(MS.get_spec(KIT.KEY), record_sources=False))
    return _CTX


def donor_tree(level: str):
    return ctx().template_dsl(KIT.donor_program(ctx(), level))


def split_donor(donor: str) -> tuple[str, str]:
    """``live:1499893#1`` → ``("live", "1499893#1")``；``2310694#0`` → ``("official", …)``。"""
    head, _, tail = donor.partition("live:")
    return ("live", tail) if tail else ("official", head)


def walk(node):
    yield node
    if isinstance(node, list):
        for child in node:
            yield from walk(child)


def calls(tree, name):
    """树里所有 ``["Command", [<name>, …]]`` 的 payload。"""
    return [node[1] for node in walk(tree)
            if isinstance(node, list) and len(node) == 2 and node[0] == "Command"
            and isinstance(node[1], list) and node[1] and node[1][0] == name]


# ---------------------------------------------------------------- 静态：方案自洽

class PlanTests(unittest.TestCase):
    def test_identity_matches_the_roster(self):
        spec = MS.SPECS[KIT.KEY]
        self.assertEqual((spec.cid, spec.code, spec.element, spec.pf_type, spec.stance),
                         (KIT.CID, KIT.CODE, KIT.ELEMENT, KIT.PF_TYPE, KIT.STANCE))
        self.assertEqual((spec.template_id, spec.template_code),
                         (KIT.TEMPLATE_ID, KIT.TEMPLATE_CODE))

    def test_unique_condition_ids_are_eight_digits(self):
        for index, uid in enumerate((KIT.UID_DICE, KIT.UID_STEP), start=1):
            self.assertEqual(uid, f"{KIT.CID}0{index}")
            self.assertEqual(len(uid), 8)
        self.assertNotEqual(KIT.UID_DICE, KIT.UID_STEP)

    def test_spec_declares_every_kit_owned_key(self):
        extra = KIT.SPEC["extra_keys"]
        self.assertEqual(sorted(extra[KL.UNIQUE]), sorted((KIT.UID_DICE, KIT.UID_STEP)))
        self.assertEqual(sorted(extra[KL.CAS]), sorted(KIT.CAS_TEXTS))
        self.assertEqual(list(extra[KL.SWITCHED]), [KIT.VOICE_KEY])

    def test_merged_spec_carries_the_kit_overrides(self):
        spec = MS.get_spec(KIT.KEY)
        self.assertEqual(sorted(spec.required_capabilities),
                         sorted(KIT.SPEC["required_capabilities"]))
        self.assertIn(KIT.UID_STEP, spec.extra_keys[KL.UNIQUE])
        self.assertIn(KIT.CAS_LEADER, spec.extra_keys[KL.CAS])

    def test_ability_keys_are_the_six_character_slots(self):
        self.assertEqual(sorted(KIT.ABILITY), [KIT.ability_key(slot) for slot in range(1, 7)])
        self.assertEqual(sorted(KIT.STATUE_GROUPS), sorted(KIT.ABILITY))

    def test_every_ability_key_has_a_single_statue_group_and_unisonable_flag(self):
        for key, records in KIT.ABILITY.items():
            self.assertEqual({cells.get(2) for _d, cells, _e in records},
                             {KIT.STATUE_GROUPS[key]}, key)
            self.assertEqual(len({cells.get(1) for _d, cells, _e in records}), 1, key)

    def test_statue_groups_are_known_enums(self):
        for group in KIT.STATUE_GROUPS.values():
            self.assertIn(group, L.ABILITY_STATUE_GROUPS)

    def test_ability_c0_is_code_underscore_slot(self):
        for key, records in KIT.ABILITY.items():
            for donor, cells, _expect in records:
                self.assertEqual(cells.get(0), f"{KIT.CODE}_{key[-1]}", f"{key} {donor}")

    def test_leader_c0_is_the_code(self):
        for _donor, cells, _expect in KIT.LEADER:
            self.assertEqual(cells.get(0), KIT.CODE)

    def test_only_the_two_fever_rows_carry_the_patch_kind(self):
        rows = [f"{key}#{index}" for key, records in KIT.ABILITY.items()
                for index, (_d, cells, _e) in enumerate(records)
                if "724" in (cells.get(col) for col in KIT.ABILITY_KIND_COLUMNS)]
        self.assertEqual(rows, ["1399913#0", "1399913#2"])

    def test_the_fever_rows_are_one_positive_and_one_negative(self):
        records = KIT.ABILITY["1399913"]
        self.assertEqual(records[0][1][51], "35000")
        self.assertEqual(records[2][1][51], "-50000")
        self.assertEqual(records[0][1][13], "186")           # 前置 NotFever
        self.assertEqual(records[2][1][6], "12")             # 前置 Fever

    def test_leader_plan_never_uses_the_ability_only_kinds(self):
        for index, (_donor, cells, _expect) in enumerate(KIT.LEADER):
            for col in KIT.LEADER_KIND_COLUMNS:
                self.assertNotIn(cells.get(col), KIT.ABILITY_ONLY_KINDS, f"leader#{index}")

    def test_ability_plan_never_uses_the_c2308_kinds(self):
        for key, records in KIT.ABILITY.items():
            for index, (_donor, cells, _expect) in enumerate(records):
                for col in KIT.ABILITY_KIND_COLUMNS:
                    self.assertNotIn(cells.get(col), KIT.C2308_KINDS, f"{key}#{index}")

    def test_unique_stack_sources_point_at_our_own_uniques(self):
        """``IC 461`` 的固有 id 列（c68）与前置 187 的固有 id 列（c12）只许指向自家的两个 uid。"""
        mine = {KIT.UID_DICE, KIT.UID_STEP}
        used = set()
        for records in KIT.ABILITY.values():
            for _donor, cells, _expect in records:
                if cells.get(47) == "461":
                    used.add(cells[68])
                if cells.get(6) == "187":
                    used.add(cells[12])
        self.assertEqual(used, mine)

    def test_precondition_188_is_never_used(self):
        """裁决 §8：前置 188 数的是实例数（恒 1），阈值 ≥2 永不成立。"""
        for records in KIT.ABILITY.values():
            for _donor, cells, _expect in records:
                for col in (6, 13, 20):
                    self.assertNotEqual(cells.get(col), "188")

    def test_element_columns_are_all_yellow(self):
        for records in KIT.ABILITY.values():
            for donor, cells, _expect in records:
                for col in (11, 18, 29, 49, 111):
                    value = cells.get(col)
                    if value:
                        self.assertEqual(value, KIT.ELEMENT_TOKEN, f"{donor} c{col}")

    def test_voice_route_targets_the_permanent_unique(self):
        """kind 3 ChangeSkillFlag 不能用：536 在共鸣队里常驻会让 skill_ready 永不播。"""
        self.assertEqual(KIT.VOICE_ROUTE["kind"], 1)
        self.assertEqual(KIT.VOICE_ROUTE["condition_kind"], "28")
        self.assertEqual(KIT.VOICE_ROUTE["condition_id"], KIT.UID_DICE)

    def test_skill_energy_is_the_author_value_on_both_levels(self):
        """作者放行第 5 条：黑 550，觉醒前后两档都写这个数。"""
        self.assertEqual(KIT.SKILL_ENERGY, {"1": ("550", "550"), "2": ("550", "550")})

    def test_additional_direct_attack_stays_at_three_stages(self):
        """跨角色段数取优不相加：全批统一 3 段，黑（辅助）的 % 低于凯尔/罗尔夫。"""
        for level in ("1", "2"):
            ac = KIT.SKILL_ADDITIONAL_AC[level]
            self.assertEqual(ac[0], "ACAdditionalDirectAttack")
            self.assertEqual(ac[2], [{"min": 3, "max": 3}])
            self.assertLessEqual(ac[3][0]["max"], 1.0)

    def test_ability_4_carries_a_three_second_cooldown(self):
        """反馈轮 2：作者原话「黑的能力4带上ct3s」→ 两条记录的 c35（CT 列）都是 180 帧＝3 秒。"""
        records = KIT.ABILITY["1399914"]
        self.assertEqual(len(records), 2)
        for _donor, cells, expect in records:
            self.assertEqual(cells.get(35), "180", cells)
            self.assertIn("(CT3秒)", expect)


class UniqueConditionTests(unittest.TestCase):
    def test_caps_are_numbers_not_none(self):
        """``(None)``／空串 = 上限 1，会把 461 叠层与 DSL 的层数门全弄死。"""
        for cap in (KIT.DICE_CAP, KIT.STEP_CAP):
            self.assertNotIn(cap, ("", "(None)"))
            self.assertTrue(cap.isdigit())

    def test_dice_is_permanent_and_step_is_timed(self):
        self.assertEqual(KIT.DICE_FRAMES, "99999999")       # 无时间限制
        self.assertEqual(KIT.DICE_CAP, "6")                 # 面板「最多6层」
        self.assertEqual(KIT.STEP_FRAMES, "900")            # 15 秒
        self.assertEqual(KIT.STEP_CAP, "1")                 # 二值状态，图标不画层数

    def test_icon_logical_paths_live_under_the_official_namespace(self):
        for icon in (KIT.DICE_ICON, KIT.STEP_ICON):
            self.assertTrue(icon.startswith("battle/common/unique_condition/unique_"))
            self.assertIn(KIT.CODE, icon)
        self.assertEqual(sorted(KIT.UNIQUE_ICONS), sorted((KIT.UID_DICE, KIT.UID_STEP)))


# ---------------------------------------------------------------- 静态：面板

class PanelTests(unittest.TestCase):
    def test_registered_panel_text_obeys_the_batch_rules(self):
        for key, text in KIT.CAS_TEXTS.items():
            for line in text.split("\n"):
                self.assertEqual(
                    KL.panel_problems(line.replace(KIT.MAIN_ICON, ""),
                                      skill_flag=key in KIT.SKILL_FLAG_TEXT_KEYS),
                    [], f"{key}: {line}")

    def test_texts_obey_the_batch_rules(self):
        for name in ("title", "skill1", "desc1", "skill2", "desc2", "leader", "profile"):
            self.assertEqual(KL.panel_problems(KIT.TEXTS[name]), [], name)

    def test_no_always_true_hp_condition_text(self):
        for text in list(KIT.CAS_TEXTS.values()) + list(KIT.TEXTS.values()):
            self.assertNotIn("生命值100%以下", text)

    def test_skill_description_names_the_direct_attack_judgement(self):
        for level in ("1", "2"):
            self.assertIn("以直接攻击伤害判定", KIT.TEXTS[f"desc{level}"])

    def test_texts_have_the_ten_design_keys(self):
        self.assertEqual(sorted(KIT.TEXTS), sorted(
            ("name", "furigana", "profile", "title", "skill1", "desc1",
             "skill2", "desc2", "leader", "cv")))

    def test_override_keys_match_the_first_row_string_id(self):
        """客户端查的是 ``desc_override_`` ＋ 该块第 0 行的 c0。"""
        self.assertEqual(KIT.CAS_LEADER, L.PANEL_OVERRIDE_KEY_PREFIX + KIT.LEADER[0][1][0])
        for slot in range(1, 7):
            first = KIT.ABILITY[KIT.ability_key(slot)][0][1][0]
            self.assertEqual(KIT.CAS_ABILITY[slot], L.PANEL_OVERRIDE_KEY_PREFIX + first)

    def test_only_the_main_position_slot_carries_the_main_icon(self):
        """desc_override 会盖掉客户端逐行画的 Ⓜ ⇒ 主位键必须每行自带。"""
        for slot in range(1, 7):
            text = KIT.CAS_TEXTS[KIT.CAS_ABILITY[slot]]
            for line in text.split("\n"):
                self.assertEqual(line.startswith(KIT.MAIN_ICON), KIT._main_only(slot),
                                 f"slot {slot}: {line}")
        self.assertEqual([slot for slot in range(1, 7) if KIT._main_only(slot)], [3])

    def test_panel_lines_cover_every_slot(self):
        self.assertEqual(sorted(KIT.PANEL_ABILITY), list(range(1, 7)))
        self.assertEqual(PANEL_LINES, 16)       # 2026-09-27 第二批：18 + 队长追加 2 行；第三轮合并 −2、R2 删能力3 两行 −2

    def test_the_skill_flag_entry_has_no_numbers_or_time(self):
        """裁决 §3：能力里的「技能强化」条目不写数字与时间。"""
        text = KIT.CAS_TEXTS[KIT.CAS_CHANGE_SKILL]
        self.assertFalse(any(ch.isdigit() for ch in text))
        for unit in ("秒", "%", "％"):
            self.assertNotIn(unit, text)

    def test_the_skill_flag_entry_is_the_only_enhancement_text(self):
        """2026-09-27 第三轮 R2（wf_balance_20260927c_kuro 第 7 节）：强化条目官方格式点名技能；面板里只有开关行（能力1 第 2 行
        = 「雷属性共鸣时，」＋ 条目，开关行 c1=true 不带图标）写强化，其余面板与技能说明不写强化后效果。"""
        entry = KIT.CAS_TEXTS[KIT.CAS_CHANGE_SKILL]
        self.assertTrue(entry.startswith(f"强化『{KIT.TEXTS['skill1']}』："))
        self.assertEqual(KIT.PANEL_ABILITY[1][1], "雷属性共鸣时，" + entry)
        self.assertEqual(KIT.ABILITY[KIT.ability_key(1)][1][1][47], "536")
        for slot, lines in KIT.PANEL_ABILITY.items():
            for index, line in enumerate(lines):
                if (slot, index) != (1, 1):
                    self.assertNotIn("强化", line, (slot, index))
        for line in KIT.PANEL_LEADER:
            self.assertNotIn("强化", line)
        for name in ("desc1", "desc2"):
            for word in ("强化", "骰运", "随机", "抽取"):
                self.assertNotIn(word, KIT.TEXTS[name])

    def test_capabilities_include_the_panel_override_patch(self):
        self.assertIn(L.PANEL_OVERRIDE_V2, KIT.SPEC["required_capabilities"])
        for key in KIT.CAS_TEXTS:
            if key.startswith(L.PANEL_OVERRIDE_KEY_PREFIX):
                self.assertEqual(L.panel_override_capability(key), L.PANEL_OVERRIDE_V2)


# ---------------------------------------------------------------- 静态：图标

class IconTests(unittest.TestCase):
    def _frame(self):
        from PIL import Image
        frame = Image.new("RGBA", (48, 48), (255, 255, 255, 255))
        for xy in ((0, 0), (47, 0), (0, 47), (47, 47)):
            frame.putpixel(xy, (255, 255, 255, 0))
        return frame

    def test_icons_keep_the_frame_size_and_alpha(self):
        frame = self._frame()
        for painter in (KIT.draw_dice_icon, KIT.draw_step_icon):
            icon = painter(frame)
            self.assertEqual(icon.size, (48, 48))
            self.assertEqual(icon.mode, "RGBA")
            self.assertEqual(icon.getchannel("A").tobytes(), frame.getchannel("A").tobytes())

    def test_icons_reject_a_frame_of_the_wrong_size(self):
        from PIL import Image
        for painter in (KIT.draw_dice_icon, KIT.draw_step_icon):
            with self.assertRaises(KL.KitError):
                painter(Image.new("RGBA", (32, 32)))

    def test_icons_are_gold_on_ink(self):
        for painter in (KIT.draw_dice_icon, KIT.draw_step_icon):
            icon = painter(self._frame())
            pixels = [icon.getpixel((x, y)) for x in range(48) for y in range(48)]
            self.assertTrue(any(p[0] > 150 and p[1] > 120 and p[2] < 160 for p in pixels),
                            "看不到金色图案")
            self.assertTrue(any(sum(p[:3]) < 150 for p in pixels), "看不到夜靛底")

    def test_the_two_icons_are_not_the_same_picture(self):
        frame = self._frame()
        self.assertNotEqual(KIT.draw_dice_icon(frame).tobytes(),
                            KIT.draw_step_icon(frame).tobytes())


# ---------------------------------------------------------------- 静态：DSL 变形器


def _show_effect(label: str, name: str, lifetime, scale):
    return ["Command", ["ShowEffect", label,
                        ["SpecifyEffectDirectly",
                         f"battle/effect/skill_unique/outlaw_panther_ny22/"
                         f"outlaw_panther_ny22_{name}"],
                        -18, ["ForesideOfCharacter"], lifetime, ["AB"], 0, 0, 0, True, False,
                        scale]]


DONOR_LEVEL_2 = ["ActionDsl", 2, ["None"], False, False, False, False, False, False, False, 0,
                 ["Block", [
                     ["Command", ["StopBall", -18, 75, ["Stop"], ["AB"], 0]],
                     _show_effect("扇子を開く", "open", ["PlayOnlyFirstSequence"], ["None"]),
                     ["Event", ["Wait", 10, "*", ["Block", [
                         ["Command", ["CreateHitArea", "*", -18, ["AB"], 0, 0, 0, True, False,
                                      ["Circle", [{"min": 300, "max": 300}]],
                                      ["Center"], ["Center"], ["Single"],
                                      ["SpecifyHitAreaLifetimeDirectly", 60],
                                      ["CalculatedUsingMaxNumOfHits", 15],
                                      ["Some", [{"min": 15, "max": 15}]], False, True,
                                      ["None"], 0,
                                      ["Block", [
                                          _show_effect("回転演出", "rotation",
                                                       ["SpecifyEffectLifetimeDirectly", 60],
                                                       ["Some", [{"min": 6, "max": 6}]]),
                                          _show_effect("紙吹雪演出", "kamihubuki",
                                                       ["SpecifyEffectLifetimeDirectly", 60],
                                                       ["None"]),
                                      ]],
                                      1, 2,
                                      ["Block", [
                                          ["Command", ["ShakeCamera", 1]],
                                          ["Command", ["CreateNormalAttack", 2, 255, [], [], 5,
                                                       [{"min": 0.6933333333333334, "max": 0.8}],
                                                       [{"min": 0, "max": 0}], False, False,
                                                       False, False, False,
                                                       [{"min": 0.8, "max": 0.8}],
                                                       [{"min": 0.8, "max": 0.8}],
                                                       ["Fine"], True]]]],
                                      0, 0, ["None"]]],
                         ["Event", ["Wait", 59, "*", ["Block", [
                             _show_effect("終了演出", "close", ["PlayOnlyFirstSequence"],
                                          ["None"]),
                         ]]]],
                     ]]]],
                     ["Command", ["FindAllSubjects", 3, 33, [], [], [], [], [], ["DoNothing"],
                                  ["Block", [
                                      ["Command", ["CreateCondition", 3,
                                                   [["ACPowerFlipDamage",
                                                     [{"min": 900, "max": 900}],
                                                     [{"min": 0.4, "max": 0.5}],
                                                     [{"min": 1, "max": 1}]]],
                                                   [{"min": 1, "max": 1}],
                                                   ["GenericConditionHitEffect"], True, False,
                                                   "", None, False, 3,
                                                   [{"min": 1, "max": 1}], False]]]]]]]]]


class SkillMutationTests(unittest.TestCase):
    def setUp(self):
        self.tree = copy.deepcopy(DONOR_LEVEL_2)

    def mutated(self):
        return KIT.mutate_tree(self.tree, "2")

    def test_the_stub_donor_matches_the_command_fingerprint(self):
        self.assertEqual(KIT._command_counts(self.tree), KIT.DONOR_COMMAND_COUNTS)

    def test_s1_cancels_the_recovery_with_the_official_non_stopping_form(self):
        tree, ev = self.mutated()
        stop, = calls(tree, "StopBall")
        self.assertEqual(stop[1:], KIT.STOPBALL_AFTER)
        self.assertEqual(stop[3], ["RestoreToSpeedBeforeActionExecution"])
        self.assertEqual(stop[4], ["AB"])            # 坐标系不动（CD/EF 对球会 throw）
        self.assertEqual(ev["stop_ball"]["before"], KIT.STOPBALL_BEFORE)

    def test_s2_switches_both_hit_areas_to_direct_attack_damage(self):
        tree, _ev = self.mutated()
        areas = calls(tree, "CreateHitArea")
        self.assertEqual(len(areas), 2)
        for area in areas:
            self.assertEqual(area[KIT.HITAREA_BUFF_TARGET_SLOT], KIT.HITAREA_BUFF_TARGET_AS)

    def test_s2_leaves_the_root_header_alone(self):
        tree, _ev = self.mutated()
        self.assertEqual(tree[1], 2)
        self.assertEqual(tree[10], 0)

    def test_s3_rewrites_only_the_multiplier_slot(self):
        tree, _ev = self.mutated()
        for cna in calls(tree, "CreateNormalAttack"):
            self.assertEqual(cna[2], 255)
            self.assertEqual(cna[6], KIT.SKILL_MULTIPLIER["2"][1])

    def test_s4_replaces_the_pf_condition_with_a_direct_damage_one(self):
        tree, _ev = self.mutated()
        team = [c for c in calls(tree, "CreateCondition") if c[1] == 3]
        self.assertEqual(len(team), 2)
        self.assertEqual(team[0][2][0][0], "ACDirectDamage")
        self.assertEqual(team[1][2][0][0], "ACAdditionalDirectAttack")
        for condition in team:
            self.assertEqual(condition[10], KIT.CREATE_CONDITION_TARGET_KIND)
            self.assertIsInstance(condition[2], list)
            self.assertIsInstance(condition[2][0], list)   # AC 必须还包在列表里

    def test_s6_wraps_the_event_in_a_change_skill_flag_branch(self):
        tree, ev = self.mutated()
        branch, = calls(tree, "ConditionalsChangeSkillFlag")
        self.assertEqual(branch[1], 1)
        enhanced, plain = branch[2], branch[3]
        self.assertEqual(enhanced[0], "Block")
        self.assertEqual(plain[0], "Block")
        self.assertEqual(len(plain[1]), 1)                       # 常态档只有原来的 Event
        self.assertEqual(plain[1][0][0], "Event")
        self.assertEqual(ev["change_skill_flag"]["plain"]["max_hits"], KIT.HITAREA_MAX_HITS[0])

    def test_the_enhanced_branch_lasts_longer_and_scales_with_combo(self):
        tree, _ev = self.mutated()
        branch, = calls(tree, "ConditionalsChangeSkillFlag")
        enhanced_area, = calls(branch[2], "CreateHitArea")
        plain_area, = calls(branch[3], "CreateHitArea")
        self.assertEqual(enhanced_area[13], ["SpecifyHitAreaLifetimeDirectly",
                                             KIT.HITAREA_LIFETIME[1]])
        self.assertEqual(plain_area[13], ["SpecifyHitAreaLifetimeDirectly",
                                          KIT.HITAREA_LIFETIME[0]])
        self.assertEqual(enhanced_area[15], ["Some", [{"min": KIT.HITAREA_MAX_HITS[1],
                                                       "max": KIT.HITAREA_MAX_HITS[1]}]])
        enhanced_cna, = calls(branch[2], "CreateNormalAttack")
        plain_cna, = calls(branch[3], "CreateNormalAttack")
        self.assertIs(enhanced_cna[8], True)      # enablesComboBonus
        self.assertIs(plain_cna[8], False)

    def test_the_enhanced_branch_keeps_the_effects_in_sync_with_the_hit_area(self):
        tree, _ev = self.mutated()
        branch, = calls(tree, "ConditionalsChangeSkillFlag")
        area, = calls(branch[2], "CreateHitArea")
        for statement in area[20][1]:
            self.assertEqual(statement[1][5],
                             ["SpecifyEffectLifetimeDirectly", KIT.EFFECT_LIFETIME[1]])
        wait = [node for node in walk(branch[2])
                if isinstance(node, list) and len(node) == 2 and node[0] == "Event"]
        self.assertIn(KIT.CLOSE_WAIT[1], [node[1][1] for node in wait])

    def test_the_roulette_only_exists_in_the_enhanced_branch(self):
        tree, _ev = self.mutated()
        branch, = calls(tree, "ConditionalsChangeSkillFlag")
        self.assertEqual(len(calls(branch[2], "ConditionalsProbability")), KIT.ROULETTE_SLOTS)
        self.assertEqual(calls(branch[3], "ConditionalsProbability"), [])

    def test_every_probability_branch_has_exactly_a_weight_and_a_block(self):
        """形状写歪 = 进战斗 INTERNAL ERROR（不是静默）。"""
        tree, _ev = self.mutated()
        wheels = calls(tree, "ConditionalsProbability")
        self.assertEqual(len(wheels), KIT.ROULETTE_SLOTS)
        for wheel in wheels:
            block = wheel[1]
            self.assertEqual(block[0], "Block")
            self.assertEqual(len(block[1]), 6)
            for option in block[1]:
                self.assertEqual(option[0], "Block")
                self.assertEqual(len(option[1]), 2)
                self.assertEqual(option[1][0], ["Command", ["ProbabilityWeight", 1]])
                self.assertEqual(option[1][1][0], "Block")

    def test_the_gate_chain_counts_dice_layers_from_two_to_six(self):
        tree, _ev = self.mutated()
        gates = calls(tree, "ConditionalsConditionAccumulationNumber")
        self.assertEqual(len(gates), KIT.ROULETTE_SLOTS - 1)
        self.assertEqual(sorted(gate[2] for gate in gates), list(range(2, KIT.ROULETTE_SLOTS + 1)))
        for gate in gates:
            self.assertEqual(gate[1], ["DCUnique", int(KIT.UID_DICE)])
            self.assertEqual(gate[4], ["Block", []])          # 空分支不能写 ["DoNothing"]

    def test_the_roulette_pool_matches_the_panel_line(self):
        tree, _ev = self.mutated()
        self.assertEqual(len(calls(tree, "AddFeverPoint")), KIT.ROULETTE_SLOTS)
        self.assertEqual(len(calls(tree, "AddCombo")), KIT.ROULETTE_SLOTS)
        self.assertEqual(len(calls(tree, "AddSkillPoint")), KIT.ROULETTE_SLOTS)
        self.assertEqual(calls(tree, "AddFeverPoint")[0][1],
                         [{"min": KIT.ROULETTE_FEVER_POINT, "max": KIT.ROULETTE_FEVER_POINT}])
        self.assertEqual(calls(tree, "AddCombo")[0][1],
                         [{"min": KIT.ROULETTE_COMBO, "max": KIT.ROULETTE_COMBO}])
        selves = [c for c in calls(tree, "CreateCondition") if c[1] == -17]
        self.assertEqual(len(selves), 3 * KIT.ROULETTE_SLOTS)
        self.assertEqual({c[2][0][0] for c in selves},
                         {"ACAttackPoint", "ACPiercing", "ACDirectDamage"})
        for condition in selves:
            self.assertEqual(condition[10], KIT.CREATE_CONDITION_TARGET_KIND)

    def test_the_leader_skill_gauge_uses_selector_34(self):
        """09-21 作者纠正 ＋ 官方 student_gunsmith_2 实读：选择器 34 ＝ 队长。"""
        tree, _ev = self.mutated()
        finds = [c for c in calls(tree, "FindAllSubjects") if c[2] == KIT.LEADER_SELECTOR]
        self.assertEqual(len(finds), KIT.ROULETTE_SLOTS)
        binds = sorted(find[1] for find in finds)
        self.assertEqual(binds, [KIT.ROULETTE_BIND_BASE + i for i in range(KIT.ROULETTE_SLOTS)])
        for find in finds:
            add, = calls(find[9], "AddSkillPoint")
            self.assertEqual(add[1], find[1])        # CHA p1 必须 = 所在 FindAll 的绑定 id
            self.assertEqual(add[2], [{"min": KIT.ROULETTE_LEADER_SKILL,
                                       "max": KIT.ROULETTE_LEADER_SKILL}])

    def test_roulette_binds_never_collide_with_the_donor(self):
        tree, _ev = self.mutated()
        binds = [find[1] for find in calls(tree, "FindAllSubjects")]
        self.assertEqual(len(binds), len(set(binds)))
        self.assertIn(3, binds)                       # 母本自己的队伍 buff 块

    def test_mutation_keeps_the_command_count_fingerprint(self):
        tree, _ev = self.mutated()
        self.assertEqual(KIT._command_counts(tree), KIT.MUTATED_COMMAND_COUNTS)

    def test_effects_stay_on_the_official_paths(self):
        tree, ev = self.mutated()
        for path in KIT.effect_paths(tree):
            self.assertTrue(path.startswith(KIT.OFFICIAL_EFFECT_PREFIX), path)
        self.assertEqual(len(ev["effect_refs"]), KIT.DONOR_COMMAND_COUNTS["ShowEffect"])

    def test_no_donothing_branch_is_introduced(self):
        """``["DoNothing"]`` 只许当 FindAllSubjects 的第 8 参；落在分支体 = F1009。"""
        tree, _ev = self.mutated()
        for node in walk(tree):
            if isinstance(node, list) and len(node) == 2 and node[0] == "Block":
                for item in node[1]:
                    self.assertNotEqual(item, ["DoNothing"])

    def test_a_drifted_stop_ball_is_rejected(self):
        self.tree[11][1][0][1][2] = 90
        with self.assertRaises(KL.KitError):
            self.mutated()

    def test_a_drifted_donor_is_rejected(self):
        self.tree[11][1].append(["Command", ["ShakeCamera", 1]])
        with self.assertRaises(KL.KitError):
            self.mutated()

    def test_a_drifted_multiplier_is_rejected(self):
        cna, = calls(self.tree, "CreateNormalAttack")
        cna[6] = [{"min": 9.0, "max": 9.0}]
        with self.assertRaises(KL.KitError):
            self.mutated()

    def test_a_drifted_condition_target_kind_is_rejected(self):
        condition, = calls(self.tree, "CreateCondition")
        condition[10] = 1
        with self.assertRaises(KL.KitError):
            self.mutated()

    def test_a_drifted_hit_area_lifetime_is_rejected(self):
        area, = calls(self.tree, "CreateHitArea")
        area[13] = ["SpecifyHitAreaLifetimeDirectly", 90]
        with self.assertRaises(KL.KitError):
            self.mutated()


class DonorNotationTests(unittest.TestCase):
    def test_design_donor_notation_normalises_to_the_kit_form(self):
        self.assertEqual(KIT._norm_donor("151171#L2"), "151171#1")
        self.assertEqual(KIT._norm_donor("live 1499893#L2"), "live:1499893#1")
        self.assertEqual(KIT._norm_donor("1611231#L1 + trigger block from live 1699893#L5"),
                         "1611231#0")
        self.assertEqual(KIT._norm_donor("331004"), "331004")

    def test_only_the_patch_kind_rows_come_from_live(self):
        """官方基线优先；live 只用于官方全表零行的补丁 kind 724。"""
        live = [(key, index) for key, records in KIT.ABILITY.items()
                for index, (donor, _c, _e) in enumerate(records)
                if split_donor(donor)[0] == "live"]
        self.assertEqual(live, [("1399913", 0), ("1399913", 2)])
        for donor, _cells, _expect in KIT.LEADER:
            self.assertEqual(split_donor(donor)[0], "official")


# ---------------------------------------------------------------- 集成（需要官方基线 / live store）

@unittest.skipUnless(_LIVE, "需要 .cdn/cn 官方基线与 live store")
class RowIntegrationTests(unittest.TestCase):
    def test_every_leader_row_builds_and_renders_as_registered(self):
        for index, (donor, cells, expect) in enumerate(KIT.LEADER):
            row, ev = KL.build_row(ctx(), "leader_ability", donor, cells,
                                   expect_describe=expect, label=f"leader#{index}")
            self.assertEqual(len(row), KL.LEADER_NCOLS)
            self.assertEqual(ev["describe"], expect)
            self.assertEqual(ev["capabilities"], [])

    def test_every_ability_row_builds_and_renders_as_registered(self):
        for key, records in KIT.ABILITY.items():
            built = []
            for index, (donor, cells, expect) in enumerate(records):
                source, donor_key = split_donor(donor)
                row, ev = KL.build_row(ctx(), "ability", donor_key, cells, source=source,
                                       element=KIT.ELEMENT, expect_describe=expect,
                                       label=f"{key}#{index}")
                self.assertEqual(len(row), KL.ABILITY_NCOLS)
                self.assertEqual(ev["describe"], expect)
                built.append(row)
            KL.check_ability_key(built, key, KIT.CODE, int(key[-1]))

    def test_only_the_fever_rows_need_a_client_capability(self):
        caps = {}
        for key, records in KIT.ABILITY.items():
            for index, (donor, cells, _expect) in enumerate(records):
                source, donor_key = split_donor(donor)
                row = KL.apply_cells(KL.donor_row(ctx(), KL.ABILITY, donor_key, source=source),
                                     cells, KL.ABILITY_NCOLS)
                got = KL.capabilities("ability", row)
                if got:
                    caps[f"{key}#{index}"] = got
        self.assertEqual(caps, {"1399913#0": ["kyubi-fever-ratio-v1"],
                                "1399913#2": ["kyubi-fever-ratio-v1"]})

    def test_guard_rows_passes_on_the_real_rows(self):
        leader = [KL.build_row(ctx(), "leader_ability", d, c, expect_describe=e)[0]
                  for d, c, e in KIT.LEADER]
        ability = {}
        for key, records in KIT.ABILITY.items():
            rows = []
            for donor, cells, expect in records:
                source, donor_key = split_donor(donor)
                rows.append(KL.build_row(ctx(), "ability", donor_key, cells, source=source,
                                         element=KIT.ELEMENT, expect_describe=expect)[0])
            ability[key] = rows
        guards = KIT.guard_rows(leader, ability)
        self.assertEqual(guards["kind_724_rows"], ["1399913#0", "1399913#2"])
        self.assertTrue(guards["leader_clean"])

    def test_unique_rows_match_the_design(self):
        spec = MS.get_spec(KIT.KEY)
        for n, (uid, name, icon, frames, cap) in enumerate(
                ((KIT.UID_DICE, KIT.DICE_NAME, KIT.DICE_ICON, KIT.DICE_FRAMES, KIT.DICE_CAP),
                 (KIT.UID_STEP, KIT.STEP_NAME, KIT.STEP_ICON, KIT.STEP_FRAMES, KIT.STEP_CAP)),
                start=1):
            key, row = KL.unique_row(ctx(), spec, n, donor=KIT.UNIQUE_DONOR,
                                     cells={0: icon.rsplit("/", 1)[-1], 3: frames, 4: cap},
                                     name=name, icon=icon)
            self.assertEqual(key, uid)
            self.assertEqual(len(row), KL.UNIQUE_NCOLS)
            self.assertEqual(row[1], name)
            self.assertEqual(row[2], icon)
            self.assertEqual(row[3], frames)
            self.assertEqual(row[4], cap)

    def test_the_new_custom_ability_string_keys_are_free(self):
        official = ctx().official_flat(KL.CAS)
        for key in KIT.CAS_TEXTS:
            self.assertNotIn(key, official, key)

    def test_identity_is_unoccupied(self):
        # 发布后自己的键被自己占用是预期（与 test_midautumn_framework 同口径）
        ledger = ctx().root / ".cdn" / "cn" / "character-releases" / "active.json"
        if ledger.is_file() and MS.get_spec(KIT.KEY).pkg_id in ledger.read_text(encoding="utf-8"):
            self.skipTest("already published: own keys are expected to be occupied")
        problems = MS.occupancy_problems([MS.get_spec(KIT.KEY)], repo_root=ctx().root,
                                         store=ctx().store)
        self.assertEqual(problems, {KIT.KEY: []})

    def test_statue_group_has_official_precedent_for_every_kind_in_the_key(self):
        """裁决 §8：跨 kind 组键前先确认所选组在每个 kind 上都有官方先例。"""
        import wf_seasonal7_common as S7C
        flat = ctx().official_flat(KL.ABILITY)
        seen: dict[tuple[str, str], int] = {}
        for raw in flat.values():
            for row in S7C.csv_split(raw):
                if len(row) < KL.ABILITY_NCOLS:
                    continue
                for col, tag in ((47, "I"), (109, "D")):
                    if row[col]:
                        seen[(row[2], tag + row[col])] = seen.get((row[2], tag + row[col]), 0) + 1
        for key, records in KIT.ABILITY.items():
            group = KIT.STATUE_GROUPS[key]
            for _donor, cells, _expect in records:
                for col, tag in ((47, "I"), (109, "D")):
                    kind = cells.get(col)
                    if not kind or kind == "724":      # 补丁 kind 官方全表零行
                        continue
                    self.assertGreater(seen.get((group, tag + kind), 0), 0,
                                       f"{key}: {group} × {tag}{kind} 官方零先例")

    def test_donor_program_points_at_the_rare4_template(self):
        for level in ("1", "2"):
            path = KIT.donor_program(ctx(), level)
            self.assertEqual(path, f"battle/action/skill/action/rare4/{KIT.TEMPLATE_CODE}$"
                                   f"{KIT.TEMPLATE_CODE}_{level}")
            self.assertNotEqual(path, ctx().program_path(level))

    def test_the_real_donor_trees_mutate_cleanly(self):
        for level in ("1", "2"):
            tree, ev = KIT.mutate_tree(donor_tree(level), level)
            self.assertEqual(KIT._command_counts(tree), KIT.MUTATED_COMMAND_COUNTS)
            self.assertEqual(ev["create_normal_attack"]["after"], KIT.SKILL_MULTIPLIER[level][1])
            self.assertEqual(len(ev["effect_refs"]), 4)

    def test_the_mutated_trees_survive_an_amf_round_trip(self):
        for level in ("1", "2"):
            tree, _ev = KIT.mutate_tree(donor_tree(level), level)
            blob = ctx().amf_bytes(tree)
            self.assertEqual(ctx().amf_parse(blob), tree)

    def test_the_mutated_trees_match_the_official_dsl_signatures(self):
        import wf_dsl_sig as SIG
        for level in ("1", "2"):
            tree, _ev = KIT.mutate_tree(donor_tree(level), level)
            for node in walk(tree):
                if (isinstance(node, list) and len(node) == 2 and node[0] == "Command"
                        and isinstance(node[1], list) and isinstance(node[1][0], str)):
                    name, args = node[1][0], node[1][1:]
                    self.assertIn(name, SIG.COMMANDS, name)
                    self.assertEqual(len(args), len(SIG.COMMANDS[name]),
                                     f"{name} 参数 {len(args)} 个，官方签名 "
                                     f"{len(SIG.COMMANDS[name])} 个")

    def test_the_icon_frame_donor_is_a_48px_official_asset(self):
        raw = ctx().official_read(KIT.UNIQUE_ICON_FRAME)
        self.assertIsNotNone(raw)
        frame = ctx().png_open(raw)
        self.assertEqual(frame.size, (48, 48))
        for painter in (KIT.draw_dice_icon, KIT.draw_step_icon):
            icon = painter(frame)
            self.assertEqual(icon.getchannel("A").tobytes(), frame.getchannel("A").tobytes())


@unittest.skipUnless(_LIVE, "需要 .cdn/cn 官方基线与 live store")
class DesignCrosscheckTests(unittest.TestCase):
    def test_design_json_agrees_with_the_kit(self):
        path = MS.design_path(ctx().root, KIT.KEY)
        if not path.is_file():
            self.skipTest("设计稿不在（work/ 未恢复）")
        # 2026-09-27 第三轮（wf_balance_20260927c_kuro）改了生成器的队长#4 / 能力2#3 / 队长面板；设计镜像由
        # 主会话 --write 落盘，落盘前用其内存同步结果互校（mirror_updates 幂等，已落盘时为恒等）。
        import tempfile
        import wf_balance_20260927c_kuro as C3
        design = json.loads(path.read_text(encoding="utf-8"))
        panel = json.loads((ctx().root / C3.PANEL_REL).read_text(encoding="utf-8"))
        design = C3.mirror_updates(design, panel)[0]

        class _Probe:
            spec = ctx().spec

        with tempfile.TemporaryDirectory() as tmp:
            target = MS.design_path(Path(tmp), KIT.KEY)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(design, ensure_ascii=False), encoding="utf-8")
            _Probe.root = Path(tmp)
            result = KIT.design_crosscheck(_Probe())
        self.assertTrue(result["present"])
        self.assertIn("statue_group", result["checked"])
        self.assertIn("custom_ability_string", result["checked"])

    def test_the_design_keeps_the_first_version_as_history(self):
        path = MS.design_path(ctx().root, KIT.KEY)
        if not path.is_file():
            self.skipTest("设计稿不在（work/ 未恢复）")
        design = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(design["plan"]["rework"], "rework1")
        self.assertIn("rework0", design.get("history", {}))
        self.assertIn("plan", design["history"]["rework0"])

    def test_a_drifted_design_is_rejected(self):
        path = MS.design_path(ctx().root, KIT.KEY)
        if not path.is_file():
            self.skipTest("设计稿不在（work/ 未恢复）")
        design = json.loads(path.read_text(encoding="utf-8"))
        design["texts"]["title"] = "月下博饼的花豹"
        import tempfile

        class _Probe:
            root = ctx().root
            spec = ctx().spec

        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            target = MS.design_path(fake_root, KIT.KEY)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(design, ensure_ascii=False), encoding="utf-8")
            _Probe.root = fake_root
            with self.assertRaises(KL.KitError):
                KIT.design_crosscheck(_Probe())


# ---------------------------------------------------------------- workspace 产物

@unittest.skipUnless(_LIVE, "需要 .cdn/cn 官方基线与 live store")
class WorkspaceTests(unittest.TestCase):
    """已经跑过 ``--step kit`` 的 workspace 在场时，核对落盘结果；没跑过就跳过。"""

    def setUp(self):
        self.report = core.project_root() / "work" / "character_packs" / "ma-kuro" \
            / "evidence" / "kit-report.json"
        if not self.report.is_file():
            self.skipTest("work/character_packs/ma-kuro 还没跑过 --step kit")
        self.value = json.loads(self.report.read_text(encoding="utf-8"))
        # 2026-09-27 平衡第二批（第一批输出 + 第二批覆盖）：第二批经修订候选回写、不重跑 kit，
        # kit-report 可能仍是第一批产物 ⇒ 期望面板/行数取两态之一，但必须整体落在其中一态。
        self.want_panel = [line.replace(KIT.MAIN_ICON, "")
                           for key in (KIT.CAS_LEADER, *KIT.CAS_ABILITY.values())
                           for line in KIT.CAS_TEXTS[key].split("\n")]
        self.before_b = self.value["panel"] == panel_before_balance_b(self.want_panel)

    def test_report_identity_and_capabilities(self):
        self.assertEqual((self.value["cid"], self.value["code"]), (KIT.CID, KIT.CODE))
        self.assertEqual(self.value["required_capabilities"],
                         sorted(KIT.SPEC["required_capabilities"]))
        self.assertIn(self.value["status"], (KL.DRAFT, KL.READY))

    def test_report_programs_are_the_two_rare5_skills(self):
        programs = self.value["skills"]["programs"]
        self.assertEqual(len(programs), 2)
        for program in programs:
            self.assertIn(f"rare5/{KIT.CODE}", program)

    def test_report_panel_text_obeys_the_rules(self):
        self.assertEqual(len(self.value["panel"]),
                         len(panel_before_balance_b(self.want_panel)) if self.before_b else PANEL_LINES)
        for text in self.value["panel"]:
            self.assertEqual(KL.panel_problems(text), [], text)

    def test_report_panel_matches_the_registered_override_text(self):
        want = panel_before_balance_b(self.want_panel) if self.before_b else self.want_panel
        self.assertEqual(self.value["panel"], want)

    def test_report_guards_and_statue_groups(self):
        self.assertEqual(self.value["guards"]["kind_724_rows"], ["1399913#0", "1399913#2"])
        self.assertEqual(self.value["statue_group"], KIT.STATUE_GROUPS)

    def test_written_rows_match_the_plan(self):
        rows = json.loads((self.report.parent / "kit-rows.json").read_text(encoding="utf-8"))
        added = 1 if self.before_b else 0        # 第二批：队长 +L5、能力2 +#3
        self.assertEqual(len(rows["leader"]), len(KIT.LEADER) - added)
        self.assertEqual(sum(len(v["records"]) for v in rows["ability"].values()), ABILITY_ROWS - added)
        self.assertEqual(rows["unique_condition"][KIT.UID_DICE][4], KIT.DICE_CAP)
        self.assertEqual(rows["unique_condition"][KIT.UID_STEP][4], KIT.STEP_CAP)
        self.assertEqual(sorted(rows["custom_ability_string"]), sorted(KIT.CAS_TEXTS))

    def test_the_package_carries_both_unique_icons(self):
        package = self.report.parent.parent / "package" / "roots" / "common"
        for _uid, (logical, _painter) in KIT.UNIQUE_ICONS.items():
            self.assertTrue((package / logical).is_file(), logical)

    def test_the_skill_energy_landed_on_both_levels(self):
        energy = self.value["skills"]["energy"]
        self.assertEqual({lv: tuple(v) for lv, v in energy.items()}, KIT.SKILL_ENERGY)


if __name__ == "__main__":
    unittest.main(verbosity=2)
