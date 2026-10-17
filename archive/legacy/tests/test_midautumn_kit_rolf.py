# -*- coding: utf-8 -*-
"""罗尔夫 kit（149986 ``black_wolf_knight_moon``）rework1：行计划自查 + 行装配 + DSL 门禁。

三组用例：

1. **纯静态**（不需要 live / 官方基线）：模块常量与 ``design/rolf.json`` 的 ``plan_rework1``
   互锁；裁决 §8 的自查（队长表禁 422/724/713/693、422 必挂前置 42 且 c118 非空、
   前置 kind 白名单、201/202/521 必须 Initial 触发、629 必配字符串键且该键 unisonable=false、
   536/704 必带 c70、704 必挂前置 42 ＋ 风共鸣、during puller 契约）；面板文案逐块对齐
   ``rework1/panel/rolf.json``、面板禁词；以及本模块的小工具
   （``ConditionalsChangeSkillFlag`` 形状与旗号、``StopBall`` → 追击 ``MoveBall`` 的就地替换、
   AMF3 数值壳）。
2. **官方基线**（缺 ``.cdn/cn`` 或 live store 时跳过）：7＋19 行逐行装配并与 ``EXPECT`` 的
   ``wf_describe`` 回读逐字比对；两棵主技能树与一棵 629 追击树的装配与全部 DSL 门禁
   （元素、主体绑定、判定区归属、方向、坐标系），母本漂移断言。
3. **已构建的 workspace**（``work/character_packs/ma-rolf`` 不存在时跳过）：包内 3 棵 DSL 程序、
   ``custom_ability_string`` 10 键、零固有状态、特效仍指官方 wt23 路径。

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
import wf_dsl_sig  # noqa: E402
import wf_midautumn_common as MC  # noqa: E402
import wf_midautumn_kit_rolf as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_build as B  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402

ROOT = core.project_root()
DESIGN = MS.load_design(ROOT, "rolf")
WORKSPACE = ROOT / "work/character_packs/ma-rolf"
PANEL = ROOT / "work/character_packs/midautumn-20260920/rework1/panel/rolf.json"


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


_BASELINE = _baseline_available()
_CTX = None


def ctx():
    """只读上下文：``record_sources=False`` ⇒ 母本取数不写 workspace。"""
    global _CTX
    if _CTX is None:
        _CTX = B.KitContext(MC.MAPack(MS.get_spec("rolf"), record_sources=False))
    return _CTX


def panel_json() -> dict:
    return json.loads(PANEL.read_text(encoding="utf-8"))


def all_rows(context) -> dict:
    return K.build_rows(context)


# ---------------------------------------------------------------- 1. 纯静态

class ConstantTests(unittest.TestCase):
    def test_identity_matches_the_registry(self):
        spec = MS.get_spec("rolf")
        self.assertEqual((spec.cid, spec.code, spec.element), (K.CID, K.CODE, K.ELEMENT))
        self.assertEqual((spec.template_id, spec.template_code), (K.TEMPLATE_ID, K.TEMPLATE_CODE))
        self.assertEqual((spec.pf_type, spec.stance), (K.PF_TYPE, K.STANCE))

    def test_element_is_not_colorless(self):
        # element=6（Colorless）是敌专属，可玩角色写 6 会崩 C7050（记忆 wf-element6-colorless-crash）
        self.assertEqual(K.ELEMENT, 3)
        self.assertEqual(K.ELEMENT_TOKEN, "Green")
        self.assertEqual(K.DSL_WIND, K.ELEMENT + 1)     # DSL 显式元素码 = 内部 + 1

    def test_ability_keys_are_the_six_slots(self):
        self.assertEqual(K.ABILITY_KEYS, tuple(f"{K.CID}{n}" for n in range(1, 7)))
        self.assertEqual(sorted(K.PLAN), list(range(1, 7)))

    def test_no_unique_conditions_and_no_icons(self):
        """本轮零固有状态：SPEC 不许声明固有键，设计镜像的 unique_conditions 必须是空表。"""
        self.assertNotIn(MS.UNIQUE_CONDITION_LOGICAL, K.SPEC["extra_keys"])
        self.assertEqual(DESIGN["plan_rework1"]["unique_conditions"], [])

    def test_spec_declares_every_self_owned_key(self):
        declared = set(K.SPEC["extra_keys"][KL.CAS])
        self.assertEqual(declared, set(K.CAS_TEXTS))
        self.assertEqual(len(declared), 10)
        self.assertIn(K.CAS_FLAG2, declared)
        self.assertEqual(K.SPEC["extra_keys"][KL.SWITCHED], (K.VOICE_KEY,))

    def test_the_two_skill_flags_are_distinct_kinds_and_indices(self):
        """536 → 旗号 1（连击成长，只限主位）、704 → 旗号 2（4 档速度固定，队长 ∧ 风共鸣）。

        引擎侧：``InstantAbilitySource.as`` 把 536/704/705/706/707/708 映射成旗号 1..6，
        存进 ``instantChangeSkillFlag[成员][旗号]``；DSL ``case 86`` 按 ``int(params[0])``
        取，两个旗号互不干扰。两个旗号写成同一个下标 = 拆分失效。
        """
        self.assertEqual((K.SKILL_FLAG_INDEX, K.SKILL_FLAG_INDEX_BOOST), (1, 2))
        self.assertIn("536", KL.SKILL_FLAG_KINDS)
        self.assertIn("704", KL.SKILL_FLAG_KINDS)
        self.assertNotEqual(K.CAS_FLAG, K.CAS_FLAG2)
        self.assertEqual(K.CAS_FLAG2, f"change_skill_{K.CODE}_2")

    def test_required_capabilities_cover_dash_and_panel_override(self):
        self.assertIn("dash-parameter-v1", K.SPEC["required_capabilities"])
        self.assertIn(L.PANEL_OVERRIDE_V2, K.SPEC["required_capabilities"])

    def test_encore_program_path_stays_short_enough_for_windows(self):
        """``inspect`` 会把包复制到批目录下的临时目录；键名过长会撞 260 字符上限（20260921 实测）。"""
        self.assertTrue(K.ENCORE_PROGRAM.endswith(f"{K.CAS_ENCORE}${K.CAS_ENCORE}"))
        self.assertTrue(K.ENCORE_PROGRAM.startswith("battle/action/skill/action/ability_skill/"))
        self.assertLessEqual(len(K.CAS_ENCORE), 32)

    def test_voice_route_is_the_shipped_primula_shape(self):
        self.assertEqual(K.VOICE_ROUTE_COLS[0], "1")          # kind 1 ConditionExist
        self.assertEqual(K.VOICE_ROUTE_COLS[1], "31")         # 贯通
        self.assertEqual(K.VOICE_ROUTE_COLS[5], K.VOICE_KEY)
        self.assertEqual(list(DESIGN["voice"]["route"]["columns"]), K.VOICE_ROUTE_COLS)


class DesignMirrorTests(unittest.TestCase):
    def test_design_mirrors_the_module_plan(self):
        self.assertEqual(K.design_problems(DESIGN), [])

    def test_a_drifted_mirror_is_rejected(self):
        drifted = copy.deepcopy(DESIGN)
        drifted["plan_rework1"]["ability_records"] = 17
        self.assertTrue(K.design_problems(drifted))
        drifted = copy.deepcopy(DESIGN)
        drifted["plan_rework1"]["ability_skill_programs"] = []
        self.assertTrue(K.design_problems(drifted))
        self.assertTrue(K.design_problems({}))

    def test_row_counts_match_the_plan(self):
        self.assertEqual(len(K.LEADER), K.LEADER_ROWS)
        self.assertEqual(sum(len(rows) for rows in K.PLAN.values()), K.ABILITY_RECORDS)

    def test_skill_values_carry_the_boost_pair(self):
        values = DESIGN["plan_rework1"]["skills"]["values"]
        self.assertEqual(values["hit_area_damage_kind"], 4)
        self.assertEqual(values["encore_level"], 2)
        for level in ("1", "2"):
            self.assertEqual(values[level]["fixed_speed_speed_boost"], 4)
            self.assertEqual(values[level]["fixed_speed_charge_boost"], 0)
            self.assertEqual(values[level]["fixed_speed_speed"], 1)      # 常态 = 官方最轻的 1 档
            # 常态档的充能必须留在官方实读区间；强化档的 0 是作者点名要的例外
            self.assertIn(values[level]["fixed_speed_charge"], K.OFFICIAL_FIXED_SPEED_CHARGES)

    def test_fixed_speed_base_duration_is_four_seconds_and_piercing_is_untouched(self):
        """反馈轮 3：技能附加的最大速度固定基础时长 = 4 秒 = 240 帧；贯穿时长一格不动。"""
        values = DESIGN["plan_rework1"]["skills"]["values"]
        for level in ("1", "2"):
            self.assertEqual(values[level]["fixed_speed_frames"], 240, level)
        self.assertEqual(values["1"]["piercing_frames"], 720)
        self.assertEqual(values["2"]["piercing_frames"], 900)


class PlanSelfCheckTests(unittest.TestCase):
    def cells(self, slot: int):
        return [dict(entry[2]) for entry in K.PLAN[slot]]

    def test_leader_plan_never_writes_the_forbidden_kinds(self):
        for index, (_addr, _src, cells, _exp) in enumerate(K.LEADER):
            for col in (K.LEADER_INSTANT_KIND, K.LEADER_DURING_KIND):
                self.assertNotIn(str(cells.get(col, "")), K.FORBIDDEN_LEADER_KINDS,
                                 f"leader#{index} 写了队长表禁用 kind")

    def test_swift_offset_row_leaves_the_puller_empty(self):
        """during 34 ConditionSwift 的 puller 列写 '0' = parseAt98 C7050。"""
        swift = [c for c in self.cells(6) if str(c.get(97, "")) == "34"]
        self.assertEqual(len(swift), 1)
        self.assertEqual(swift[0][98], "")

    def test_the_invoke_string_key_and_program_are_wired_to_the_module(self):
        invoke = [c for c in self.cells(3) if c.get(70) == K.CAS_ENCORE]
        self.assertEqual(len(invoke), 1)
        self.assertEqual(invoke[0][71], K.ENCORE_PROGRAM)
        self.assertEqual(K._UNISONABLE[3], "false")     # 629 在副位不生效
        flag = [c for c in self.cells(3) if c.get(70) == K.CAS_FLAG]
        self.assertEqual(len(flag), 1)

    def test_the_boost_flag_row_is_leader_gated_in_the_plan(self):
        """704 行必须落在能承载队长门的槽（A6），并同时挂前置 42 ＋ 风共鸣。"""
        boost = [(slot, c) for slot in range(1, 7) for c in self.cells(slot)
                 if c.get(70) == K.CAS_FLAG2]
        self.assertEqual(len(boost), 1)
        slot, cells = boost[0]
        self.assertEqual(slot, 6)
        self.assertEqual(cells[6], "42")                       # 持有者为队长
        self.assertEqual((cells[13], cells[18]), ("2", K.ELEMENT_TOKEN))   # 风属性共鸣
        # 536 那条不许再带队长门：连击成长仍按现行条件（主位 + 风共鸣）生效
        flag = [c for c in self.cells(3) if c.get(70) == K.CAS_FLAG][0]
        self.assertNotEqual(flag.get(6), "42")

    def test_unlimited_growth_rows_write_none_not_an_empty_limit(self):
        """trigger_limit 留空 = 上限 0（词条全程零收益）；无上限的官方写法是 ``(None)``。"""
        # 2026-09-27 平衡第二批：3#1/#2 改成 D214 持有型（无 c34），IT 246 读秒搬到 6#5/#6
        wanted = {("3", 1), ("3", 2), ("3", 4), ("3", 5), ("6", 0), ("6", 3), ("6", 5), ("6", 6)}
        for slot, index in wanted:
            cells = self.cells(int(slot))[index]
            if 34 in cells:
                self.assertEqual(cells[34], "(None)", f"slot {slot}#{index}")

    def test_preconditions_stay_inside_the_vetted_set(self):
        for slot in range(1, 7):
            for index, cells in enumerate(self.cells(slot)):
                for col in (6, 13, 20):
                    if col in cells:
                        self.assertIn(str(cells[col]), K.ALLOWED_PRECONDITION_KINDS,
                                      f"slot {slot}#{index} c{col}")

    def test_statue_groups_are_single_valued_and_known(self):
        for slot, group in K._STATUE.items():
            self.assertIn(group, L.ABILITY_STATUE_GROUPS, f"slot {slot}")
            for cells in self.cells(slot):
                self.assertNotIn(2, cells, "c2 由 build_rows 统一注入，行计划里不该再写")


class KindGuardTests(unittest.TestCase):
    """``_ban_kinds`` 本身必须真的会拦 —— 删掉判据这些用例就得变红。"""

    def blank(self, ncols: int) -> list[str]:
        return [""] * ncols

    def test_forbidden_content_kind_in_the_leader_table_is_rejected(self):
        for kind in ("422", "724", "713", "693"):
            row = self.blank(KL.LEADER_NCOLS)
            row[K.LEADER_DURING_KIND] = kind
            with self.assertRaises(KL.KitError):
                K._ban_kinds("leader_ability", [row], "leader")

    def test_dash_row_without_the_leader_precondition_is_rejected(self):
        row = self.blank(KL.ABILITY_NCOLS)
        row[K.ABILITY_DURING_KIND] = "422"
        row[118] = "0"
        with self.assertRaises(KL.KitError):
            K._ban_kinds("ability", [row], "a")

    def test_dash_row_without_a_param_id_is_rejected(self):
        row = self.blank(KL.ABILITY_NCOLS)
        row[6] = "42"
        row[K.ABILITY_DURING_KIND] = "422"
        with self.assertRaises(KL.KitError):
            K._ban_kinds("ability", [row], "a")

    def test_invoke_without_a_string_key_is_rejected(self):
        row = self.blank(KL.ABILITY_NCOLS)
        row[1] = "false"
        row[K.ABILITY_INSTANT_KIND] = "629"
        row[35] = "300"
        with self.assertRaises(KL.KitError):
            K._ban_kinds("ability", [row], "a")

    def test_invoke_in_a_unisonable_key_is_rejected(self):
        row = self.blank(KL.ABILITY_NCOLS)
        row[1] = "true"
        row[K.ABILITY_INSTANT_KIND] = "629"
        row[35] = "300"
        row[70], row[71] = K.CAS_ENCORE, K.ENCORE_PROGRAM
        with self.assertRaises(KL.KitError):
            K._ban_kinds("ability", [row], "a")

    def test_direct_attack3_with_a_non_initial_trigger_is_rejected(self):
        row = self.blank(KL.ABILITY_NCOLS)
        row[1] = "true"
        row[27] = "12"
        row[K.ABILITY_INSTANT_KIND] = "202"
        with self.assertRaises(KL.KitError):
            K._ban_kinds("ability", [row], "a")

    def test_unvetted_precondition_kind_is_rejected(self):
        row = self.blank(KL.ABILITY_NCOLS)
        row[6] = "188"          # 数实例数恒 1，阈值 ≥2 永不成立（裁决 §8）
        with self.assertRaises(KL.KitError):
            K._ban_kinds("ability", [row], "a")

    def test_during_puller_contract(self):
        for trigger in K.PULLER_MUST_BE_EMPTY:
            row = self.blank(KL.ABILITY_NCOLS)
            row[K.ABILITY_DURING_TRIGGER] = trigger
            row[K.ABILITY_DURING_PULLER] = "0"
            with self.assertRaises(KL.KitError):
                K._check_pullers([row], K.ABILITY_DURING_TRIGGER, K.ABILITY_DURING_PULLER, "a")
        row = self.blank(KL.ABILITY_NCOLS)
        row[K.ABILITY_DURING_TRIGGER] = "204"
        with self.assertRaises(KL.KitError):
            K._check_pullers([row], K.ABILITY_DURING_TRIGGER, K.ABILITY_DURING_PULLER, "a")

    def test_invoke_row_must_exist_in_slot_three(self):
        with self.assertRaises(KL.KitError):
            K._order_problems([self.blank(KL.ABILITY_NCOLS)])

    def boost_row(self) -> list[str]:
        row = self.blank(KL.ABILITY_NCOLS)
        row[1] = "true"
        row[K.ABILITY_INSTANT_KIND] = "704"
        row[6] = "42"
        row[13], row[18] = "2", K.ELEMENT_TOKEN
        row[70] = K.CAS_FLAG2
        return row

    def test_a_well_formed_boost_flag_row_passes(self):
        K._ban_kinds("ability", [self.boost_row()], "a")        # 对照组：门禁不是恒红

    def test_boost_flag_row_without_the_leader_precondition_is_rejected(self):
        """丢了前置 42 = 主位非队长也吃 4 档速度固定（作者反馈第 3 轮点名要修的就是这个）。"""
        row = self.boost_row()
        row[6] = "0"
        with self.assertRaises(KL.KitError):
            K._ban_kinds("ability", [row], "a")

    def test_boost_flag_row_without_the_wind_resonance_is_rejected(self):
        row = self.boost_row()
        row[13], row[18] = "", ""
        with self.assertRaises(KL.KitError):
            K._ban_kinds("ability", [row], "a")
        row = self.boost_row()
        row[18] = "Red"
        with self.assertRaises(KL.KitError):
            K._ban_kinds("ability", [row], "a")

    def test_boost_flag_row_with_the_wrong_string_key_is_rejected(self):
        row = self.boost_row()
        row[70] = K.CAS_FLAG
        with self.assertRaises(KL.KitError):
            K._ban_kinds("ability", [row], "a")


class PanelTextTests(unittest.TestCase):
    def test_panel_text_obeys_the_project_rules(self):
        for key, text in K.CAS_TEXTS.items():
            for line in text.split("\n"):
                self.assertEqual(
                    KL.panel_problems(line.replace(K.MAIN_ICON, ""),
                                      skill_flag=(key in (K.CAS_FLAG, K.CAS_FLAG2))),
                    [], f"{key}: {line}")

    def test_skill_flag_entry_carries_no_numbers_or_time(self):
        for key in (K.CAS_FLAG, K.CAS_FLAG2):
            self.assertFalse(any(ch.isdigit() for ch in K.CAS_TEXTS[key]), key)

    def test_the_536_entry_no_longer_claims_the_fixed_speed_boost(self):
        """速度固定那半句搬去 704 条目；536 条目只剩连击成长（反馈轮 3）。"""
        self.assertNotIn("最大速度固定", K.CAS_TEXTS[K.CAS_FLAG])
        self.assertIn("连击", K.CAS_TEXTS[K.CAS_FLAG])
        self.assertIn("最大速度固定", K.CAS_TEXTS[K.CAS_FLAG2])
        # 2026-09-27 第三轮（wf_balance_20260927c_rolfmoon）：条件（前置 42 仅队长 + 风共鸣）不再写进条目，
        # 由 704 行前置承载、面板行写「风属性共鸣时，」；条目只写官方格式「强化『月下独奏』：…」。
        self.assertNotIn("队长", K.CAS_TEXTS[K.CAS_FLAG2])
        for key in (K.CAS_FLAG, K.CAS_FLAG2):
            self.assertTrue(K.CAS_TEXTS[key].startswith("强化『月下独奏』："), key)

    def test_panel_text_matches_the_author_approved_target(self):
        """多条记录用换行分行（禁止「／」挤成一行）；每行文字以目标面板 lines[].text 为准。"""
        panel = panel_json()
        joined = "\n".join(line["text"] for line in panel["leader"]["lines"])
        if joined != K.PANEL_LEADER:
            # 2026-09-27 第三轮（wf_balance_20260927c_rolfmoon）：镜像由主会话 --write 落盘前逐字停在第二批，
            # 只允许这一种过渡态，并且按第三轮模块补齐后必须逐字等于生成器。
            import wf_balance_20260927c_rolfmoon as RC
            self.assertEqual(joined, RC.B_PANEL_LEADER)
            _design, panel = RC.mirror_updates(DESIGN, panel)
            joined = "\n".join(line["text"] for line in panel["leader"]["lines"])
        self.assertEqual(joined, K.PANEL_LEADER)
        for block in panel["abilities"]:
            slot = block["index"]
            texts = [line["text"] for line in block["lines"]]
            if block["main_only"]:
                joined = "\n".join(K.MAIN_ICON + text for text in texts)
            else:
                joined = "\n".join(texts)
            self.assertEqual(joined, K.PANEL_ABILITY[slot], f"ability {slot}")

    def test_main_only_slot_matches_the_panel(self):
        for block in panel_json()["abilities"]:
            slot = block["index"]
            self.assertEqual(K._UNISONABLE[slot], "false" if block["main_only"] else "true",
                             f"ability {slot}")

    def test_main_position_slots_carry_their_own_icon_and_no_literal_glyph(self):
        """主位限制槽（能力3）覆盖串每行都要带 <icon id='main'>，全文不许出现字面「Ⓜ」；
        非主位槽不带图标。多记录槽的覆盖串行数＝目标面板对应槽位的行数（不许「／」挤成一行）。
        """
        panel_by_slot = {block["index"]: block for block in panel_json()["abilities"]}
        for slot in range(1, 7):
            text = K.CAS_TEXTS[K.CAS_ABILITY[slot]]
            self.assertNotIn("Ⓜ", text, f"ability {slot}")
            lines = text.split("\n")
            block = panel_by_slot[slot]
            self.assertEqual(len(lines), len(block["lines"]), f"ability {slot} line count")
            wants_icon = block["main_only"]
            for line in lines:
                self.assertEqual(line.startswith(K.MAIN_ICON), wants_icon,
                                 f"ability {slot}: {line}")
        self.assertNotIn("Ⓜ", K.PANEL_LEADER)
        self.assertEqual(len(K.PANEL_LEADER.split("\n")), len(panel_json()["leader"]["lines"]))

    def test_panel_identity_matches_the_module(self):
        panel = panel_json()
        self.assertEqual(panel["cid"], K.CID)
        self.assertEqual(panel["element"], "风")

    def test_skill_energy_matches_the_panel(self):
        energy = DESIGN["plan_rework1"]["skills"]["energy"]
        self.assertEqual(energy["inner1"]["c4"], panel_json()["skill"]["energy"])


class DslHelperTests(unittest.TestCase):
    def test_block_wraps_every_payload_in_a_command(self):
        node = K.block([["ShakeCamera", 1]])
        self.assertEqual(node, ["Block", [["Command", ["ShakeCamera", 1]]]])

    def test_flag_branch_has_the_official_shape(self):
        node = K.flag_branch([["ShakeCamera", 1]], [["ShakeCamera", 2]])
        self.assertEqual(node[0], "ConditionalsChangeSkillFlag")
        self.assertEqual(node[1], K.SKILL_FLAG_INDEX)
        for branch in node[2:]:
            self.assertEqual(branch[0], "Block")       # 禁写 ["DoNothing"]（F1009）
        self.assertNotIn("DoNothing", json.dumps(node))

    def test_flag_branch_can_select_the_second_flag(self):
        node = K.flag_branch([["ShakeCamera", 1]], [["ShakeCamera", 2]],
                             index=K.SKILL_FLAG_INDEX_BOOST)
        self.assertEqual(node[1], 2)

    def test_flag_branch_rejects_an_unknown_flag_index(self):
        """写错下标 = 分支永远走 else（引擎只是 hasAbilityPower(下标) 取不到），静默失效。"""
        for bad in (0, 3, 6):
            with self.assertRaises(KL.KitError):
                K.flag_branch([["ShakeCamera", 1]], [], index=bad)

    def test_number_shape_keeps_integers_integral(self):
        self.assertIsInstance(K.num(900), int)
        self.assertIsInstance(K.num(-0.1), float)
        self.assertEqual(K.span(4), [{"min": 4, "max": 4}])
        self.assertEqual(K.span(1.13, 1.3), [{"min": 1.13, "max": 1.3}])

    def test_swap_stop_ball_replaces_in_place_and_touches_nothing_else(self):
        tree = ["Block", [["Command", ["StopBall", -18, 70]],
                          ["Command", ["ShakeCamera", 1]]]]
        swapped = K.swap_stop_ball(tree, K.cmd(K.CHASE_MOVE_BALL))
        self.assertEqual(swapped, 1)
        self.assertEqual(tree, ["Block", [["Command", list(K.CHASE_MOVE_BALL)],
                                          ["Command", ["ShakeCamera", 1]]]])

    def test_swap_stop_ball_still_supports_plain_removal(self):
        tree = ["Block", [["Command", ["StopBall", -18, 70]],
                          ["Command", ["ShakeCamera", 1]]]]
        self.assertEqual(K.swap_stop_ball(tree, None), 1)
        self.assertEqual(tree, ["Block", [["Command", ["ShakeCamera", 1]]]])

    def test_swap_stop_ball_hands_each_site_its_own_copy(self):
        """共享同一个 replacement 对象 = 后续逐树改参会串台，必须 deepcopy。"""
        tree = ["Block", [["Command", ["StopBall", -18, 70]],
                          ["Block", [["Command", ["StopBall", -18, 9]]]]]]
        replacement = K.cmd(K.CHASE_MOVE_BALL)
        self.assertEqual(K.swap_stop_ball(tree, replacement), 2)
        first, second = tree[1][0], tree[1][1][1][0]
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first, replacement)

    def test_chase_move_ball_is_the_official_shape(self):
        """逐格钉死：官方铃鹿 silence_suzuka_2 的原行；任何一格漂了都必须红。"""
        self.assertEqual(K.CHASE_MOVE_BALL,
                         ["MoveBall", -18, ["GH", 0], 0, 1, 72, ["KeepGoing"], False])
        self.assertEqual(K.CHASE_MOVE_BALL[1], -18)          # 主体 = 球（引擎内建）
        self.assertEqual(K.CHASE_MOVE_BALL[2], ["GH", 0])    # 目标 = FindNearSubjects 的 0 号
        self.assertEqual(K.CHASE_MOVE_BALL[4], 1)            # 1 帧 ⇒ 没有长停顿
        # 速度 = 官方全库 210 条 MoveBall 的最高值。**不是**「≥ 球速上限」——那是 20260921
        # 返修推翻的旧说法，真实语义见 test_chase_speed_is_an_assignment_below_both_caps。
        self.assertEqual(K.CHASE_MOVE_BALL[5], 72)
        self.assertEqual(K.CHASE_MOVE_BALL[6], ["KeepGoing"])  # 收尾不动速度（空实现）
        self.assertIs(K.CHASE_MOVE_BALL[7], False)           # 不压制直击（罗尔夫的主轴）
        self.assertEqual(K.CHASE_FIND_HEAD,
                         [-18, 1, 49, ["CreateImaginaryTarget", -100000], 0])
        self.assertEqual(K.DONOR_STOP_BALL_FRAMES, 70)
        self.assertEqual(wf_dsl_sig.COMMANDS["MoveBall"],
                         ["int", "CoordSysSource", "Number", "int", "Number",
                          "EndingSpeedKind", "Boolean"])
        self.assertEqual(len(K.CHASE_MOVE_BALL) - 1,
                         len(wf_dsl_sig.COMMANDS["MoveBall"]))

    def test_ball_speed_cap_follows_the_fixed_speed_grade(self):
        """``BallImpl.physicalMove``: ``maxLinearVelocity = 68×速度格 + 68``。

        ``_getSpeedupCorrectionFactor`` 在 ``hasFixedSpeed()`` 分支取 ``ACFixedSpeed`` 的
        速度格且**不钳 1** ⇒ 68 只是「速度格 0」那一档，不是球的通用上限。
        """
        self.assertEqual(K.BALL_SPEED_CAP_BASE, 68)
        self.assertEqual(K.ball_speed_cap(0), 68)
        self.assertEqual(K.ball_speed_cap(1), 136)
        self.assertEqual(K.ball_speed_cap(4), 340)

    def test_chase_speed_is_an_assignment_below_both_caps(self):
        """20260921 返修：追击速度 72 **低于**本套件两档速度固定的上限 ⇒ 真机是减速。

        ``MoveBall`` 走 ``applyMovement`` → ``enterSkillMovingState`` ⇒ ``body.set_vx/set_vy``
        是**赋值**；``KeepGoing`` 收尾（``exitSkillMovingState`` case 1）是空实现。
        旧说法「72 ≥ 球基础速度上限 68 ⇒ 不会把最大速度固定的球改慢」与源码不符，
        本用例就是它的防回归闸：任何人把 72 重新说成「≥ 上限」都会红。
        """
        values = DESIGN["plan_rework1"]["skills"]["values"]
        level = str(values["encore_level"])
        speed = K.CHASE_MOVE_BALL[5]
        for key in ("fixed_speed_speed", "fixed_speed_speed_boost"):
            cap = K.ball_speed_cap(values[level][key])
            self.assertLess(speed, cap, f"{key}: 追击速度必须低于该档上限（=减速）")
        # 只有速度格 0（没有最大速度固定）那一档才是 68，追击在那档反而略快于上限
        self.assertGreater(speed, K.ball_speed_cap(0))

    def test_only_two_commands_can_re_aim_the_ball(self):
        """引擎层没有「只转向不改速」的原语：球移动命令只有 MoveBall / StopBall 两条。"""
        movers = sorted(name for name in wf_dsl_sig.COMMANDS
                        if name in ("MoveBall", "StopBall"))
        self.assertEqual(movers, ["MoveBall", "StopBall"])
        # StopBall 的 DSL 签名里根本没有「速度」格（case 14 把它写死 0）
        self.assertEqual(wf_dsl_sig.COMMANDS["StopBall"],
                         ["int", "int", "EndingSpeedKind", "CoordSysSource", "Number"])

    def test_write_dsl_rejects_the_wrapper_shell(self):
        """``write_dsl`` 只吃裸树；喂 ``{tree, numbers}`` 包装 = 进战斗 F1034。"""
        with self.assertRaises(KL.KitError):
            K.write_dsl_checked(None, "x", {"tree": ["ActionDsl"], "numbers": []})


# ---------------------------------------------------------------- 2. 官方基线

@unittest.skipUnless(_BASELINE, "需要 .cdn/cn 官方归档与 live store")
class OfficialRowTests(unittest.TestCase):
    def test_rows_assemble_and_render_as_designed(self):
        built = all_rows(ctx())
        self.assertEqual(len(built["leader"]), K.LEADER_ROWS)
        self.assertEqual(sum(len(r) for r in built["ability"].values()), K.ABILITY_RECORDS)
        rendered = {ev["label"]: ev["describe"] for ev in built["evidence"]}
        for label, want in K.EXPECT.items():
            self.assertEqual(rendered[label], want, label)

    def test_every_row_is_covered_by_the_expect_gate(self):
        """EXPECT 必须盖满 28 行（第二批 A6 +2）：漏一行就等于那一行没有 describe 门禁。"""
        built = all_rows(ctx())
        self.assertEqual(sorted(K.EXPECT), sorted(ev["label"] for ev in built["evidence"]))

    def test_only_the_dash_rows_need_a_client_capability(self):
        built = all_rows(ctx())
        self.assertEqual(built["capabilities"], ["dash-parameter-v1"])
        needing = [ev["label"] for ev in built["evidence"] if ev["capabilities"]]
        self.assertEqual(needing, [f"{K.CID}6#1", f"{K.CID}6#2"])

    def test_dash_rows_are_leader_gated_and_carry_a_param_id(self):
        rows = all_rows(ctx())["ability"][f"{K.CID}6"]
        dash = [r for r in rows if r[K.ABILITY_DURING_KIND] == "422"]
        self.assertEqual(len(dash), 2)
        for row in dash:
            self.assertEqual(row[6], "42")              # 前置 42 Leader（与别人的 422 隔离）
            self.assertEqual(row[118], "0")             # param_id 0 必须显式写
        self.assertEqual(sorted(r[113] for r in dash), ["-33000", "234500"])

    def test_invoke_row_declares_both_a_string_key_and_a_program(self):
        rows = all_rows(ctx())["ability"][f"{K.CID}3"]
        invoke = [r for r in rows if r[K.ABILITY_INSTANT_KIND] == "629"]
        self.assertEqual(len(invoke), 1)
        self.assertEqual(invoke[0][70], K.CAS_ENCORE)
        self.assertEqual(invoke[0][71], K.ENCORE_PROGRAM)
        self.assertEqual(invoke[0][35], "300")          # CT 5 秒，不能留空
        self.assertEqual(rows[0][1], "false")           # 629 在副位不生效

    def test_each_skill_flag_lives_in_exactly_one_slot(self):
        """629 与 536（旗号 1）只许在主位限制槽 A3；704（旗号 2）只许在队长承载槽 A6。"""
        want = {"629": f"{K.CID}3", "536": f"{K.CID}3", "704": f"{K.CID}6"}
        seen: dict[str, list[str]] = {}
        for key, rows in all_rows(ctx())["ability"].items():
            for row in rows:
                kind = row[K.ABILITY_INSTANT_KIND]
                if kind in want:
                    seen.setdefault(kind, []).append(key)
        self.assertEqual({k: sorted(set(v)) for k, v in seen.items()},
                         {k: [v] for k, v in want.items()})
        self.assertEqual({k: len(v) for k, v in seen.items()},
                         {"629": 1, "536": 1, "704": 1})

    def test_the_boost_flag_row_gates_on_leader_and_wind_resonance(self):
        """这一行是「不在队长位就只给 1 档」的唯一落点；门丢了作者反馈的缺陷就回来了。"""
        rows = all_rows(ctx())["ability"][f"{K.CID}6"]
        boost = [r for r in rows if r[K.ABILITY_INSTANT_KIND] == "704"]
        self.assertEqual(len(boost), 1)
        row = boost[0]
        self.assertEqual(row[6], "42")                              # 前置 42 Leader
        self.assertEqual((row[13], row[18]), ("2", K.ELEMENT_TOKEN))  # 前置 2 风共鸣
        self.assertEqual((row[16], row[17]), ("600000", "600000"))    # 编成 ≥6
        self.assertEqual(row[70], K.CAS_FLAG2)
        self.assertIn(row[27], ("", "0"))                            # Initial 触发
        self.assertEqual(row[2], "special")                          # 官方 704 全部 special

    def test_direct_attack3_row_uses_an_initial_trigger(self):
        """C2308：瞬发常驻 201/202/521 的触发不是 Initial 就会被 validate() 打回。"""
        rows = all_rows(ctx())["ability"][f"{K.CID}3"]
        da3 = [r for r in rows if r[K.ABILITY_INSTANT_KIND] == "202"]
        self.assertEqual(len(da3), 1)
        self.assertIn(da3[0][27], ("", "0"))
        self.assertEqual((da3[0][48], da3[0][49]), ("5", K.ELEMENT_TOKEN))

    def test_no_other_direct_attack_stage_source_exists(self):
        """段数多来源取优不相加 ⇒ 套件内只许有 202 一个来源（卡 B §1.1）。"""
        built = all_rows(ctx())
        for rows in list(built["ability"].values()) + [built["leader"]]:
            for row in rows:
                for col in (K.ABILITY_INSTANT_KIND, K.ABILITY_DURING_KIND,
                            K.LEADER_INSTANT_KIND, K.LEADER_DURING_KIND):
                    if col < len(row):
                        self.assertNotIn(row[col], ("201", "521", "45", "46", "252"))

    def test_a_drifted_cell_is_caught_by_the_describe_gate(self):
        with self.assertRaises(KL.KitError):
            KL.build_row(ctx(), "leader_ability", K.LEADER[0][0],
                         {0: K.CODE, 49: "1", 50: "1"},
                         expect_describe=K.EXPECT["leader#0"], label="drift")

    def test_statue_group_report_names_the_zero_precedent_rows(self):
        built = all_rows(ctx())
        report = K.statue_group_report(ctx(), built["ability"])
        zero = {f"{e['key']}#{e['record']} {e['kind']}" for e in report if e["official_rows"] == 0}
        # 422/693 官方全表 0 行；629 官方唯一一行的组是 special。c2 是纯面板外观。
        # 2026-09-27 平衡第二批：A6#6（IT 246 队长承载行，瞬发 33）× special 也是官方 0 行（A6#5 的 32 有先例）
        self.assertEqual(zero, {f"{K.CID}3#4 629", f"{K.CID}6#1 422",
                                f"{K.CID}6#2 422", f"{K.CID}6#3 693", f"{K.CID}6#6 33"})


@unittest.skipUnless(_BASELINE, "需要 .cdn/cn 官方归档与 live store")
class SkillTreeTests(unittest.TestCase):
    def values(self, level: str) -> dict:
        block = DESIGN["plan_rework1"]["skills"]["values"]
        out = dict(block[level])
        out["hit_area_damage_kind"] = block["hit_area_damage_kind"]
        return out

    def tree(self, level: str):
        return K.build_skill_tree(ctx(), level, self.values(level), None)

    def test_power_flip_block_is_removed_and_two_blocks_are_grafted(self):
        tree, gates = self.tree("2")
        self.assertEqual(gates["removed_power_flip"]["removed_command"], "FindAllSubjects")
        self.assertEqual(len(K.statements(tree)), 3)         # 主块 + 团队块 + 风属性块
        self.assertEqual(gates["team_conditions"], ["ACPiercing", "ACFixedSpeed"])
        self.assertEqual(gates["buff_target_as"], 0)
        self.assertEqual(json.dumps(tree).count("ACPowerFlipDamage"), 0)

    def test_both_hit_areas_switch_to_the_direct_attack_pool(self):
        tree, _ = self.tree("2")
        areas = list(wf_dsl.iter_dsl_commands(tree, "CreateHitArea"))
        self.assertEqual(len(areas), 2)
        for area in areas:
            self.assertEqual(area[K.HIT_AREA_DAMAGE_SLOT], 4)

    def test_combo_bonus_is_behind_the_skill_flag(self):
        """强化档吃连击成长、常态档不吃；分支必须成对出现。"""
        tree, _ = self.tree("2")
        attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
        self.assertEqual(len(attacks), 4)                     # 两段 × (then, else)
        self.assertEqual(sorted(a[K.CNA_COMBO_SLOT] for a in attacks),
                         [False, False, True, True])
        self.assertEqual(json.dumps(tree).count("ConditionalsChangeSkillFlag"), 3)

    def test_the_two_skill_flag_branches_use_different_flag_indices(self):
        """两条 CNA 判旗号 1（536，只限主位）、ACFixedSpeed 判旗号 2（704，队长 ∧ 风共鸣）。

        两处写成同一个下标 = 非队长的主位也会拿到 4 档，作者反馈第 3 轮的缺陷原样复发。
        """
        for level in ("1", "2"):
            tree, _ = self.tree(level)
            nodes = list(wf_dsl.iter_dsl_commands(tree, "ConditionalsChangeSkillFlag"))
            self.assertEqual(len(nodes), 3, level)
            by_index = {}
            for node in nodes:
                kinds = sorted({c[2][0][0] for c in wf_dsl.iter_dsl_commands(node, "CreateCondition")}
                               | {c[0] for c in wf_dsl.iter_dsl_commands(node, "CreateNormalAttack")})
                by_index.setdefault(node[1], []).append(kinds)
            self.assertEqual(sorted(by_index), [1, 2], level)
            self.assertEqual(by_index[1], [["CreateNormalAttack"], ["CreateNormalAttack"]], level)
            self.assertEqual(by_index[2], [["ACFixedSpeed"]], level)

    def test_fixed_speed_has_a_boosted_and_a_normal_branch(self):
        tree, _ = self.tree("2")
        values = self.values("2")
        speeds = [c[2][0] for c in wf_dsl.iter_dsl_commands(tree, "CreateCondition")
                  if c[2][0][0] == "ACFixedSpeed"]
        self.assertEqual(len(speeds), 2)
        boosted = [s for s in speeds if s[2] == K.span(values["fixed_speed_speed_boost"])]
        normal = [s for s in speeds if s[2] == K.span(values["fixed_speed_speed"])]
        self.assertEqual(len(boosted), 1)
        self.assertEqual(len(normal), 1)
        self.assertEqual(boosted[0][3], K.span(values["fixed_speed_charge_boost"]))
        self.assertEqual(normal[0][3], K.span(values["fixed_speed_charge"]))
        # 反馈轮 3：两支的基础时长都是 4 秒 = 240 帧
        for entry in speeds:
            self.assertEqual(entry[1], K.span(240))

    def test_piercing_keeps_its_own_duration(self):
        """贯穿时长不跟着速度固定缩短（作者只点名最大速度固定）。"""
        for level, frames in (("1", 720), ("2", 900)):
            tree, _ = self.tree(level)
            piercing = [c[2][0] for c in wf_dsl.iter_dsl_commands(tree, "CreateCondition")
                        if c[2][0][0] == "ACPiercing"]
            self.assertEqual(len(piercing), 1, level)
            self.assertEqual(piercing[0][1], K.span(frames), level)

    def test_grafted_conditions_keep_the_official_target_kinds(self):
        """``CreateCondition`` 下标 10 = 付与对象种类：82 配 3 Member、113 配 1（错配 = C16102）。"""
        tree, _ = self.tree("2")
        for node in wf_dsl.iter_dsl_commands(tree, "CreateCondition"):
            name = node[2][0][0]
            if name in ("ACPiercing", "ACFixedSpeed"):
                self.assertEqual(node[10], 3)
                self.assertEqual(node[1], K.BIND_TEAM)
            if name == "ACDirectDamage":
                self.assertEqual(node[10], 1)
                self.assertEqual(node[1], K.BIND_WIND)

    def test_selectors_and_element_filter(self):
        tree, _ = self.tree("2")
        found = {}
        for node in wf_dsl.iter_dsl_commands(tree, "FindAllSubjects"):
            found[node[2]] = node
        self.assertIn(K.SELECTOR_MAIN_PARTY, found)
        self.assertIn(K.SELECTOR_ELEMENT, found)
        self.assertEqual(found[K.SELECTOR_ELEMENT][3], [K.DSL_WIND])

    def test_effects_stay_on_the_official_template_paths(self):
        tree, gates = self.tree("2")
        self.assertEqual(set(gates["effect_paths"]), set(K.OFFICIAL_FX_PATHS))
        self.assertEqual(gates["effect_rewrites"], None)

    def test_all_dsl_gates_pass(self):
        for level in ("1", "2"):
            tree, _ = self.tree(level)
            self.assertEqual(K.dsl_problems(tree), [], level)

    def test_normal_trees_keep_the_donor_70_frame_stop_ball(self):
        """反馈轮 4 只动 629 追击树：正常技能树两档的停球一格不动。"""
        for level in ("1", "2"):
            tree, gates = self.tree(level)
            stops = list(wf_dsl.iter_dsl_commands(tree, "StopBall"))
            self.assertEqual(len(stops), 1, level)
            self.assertEqual(stops[0],
                             ["StopBall", -18, K.DONOR_STOP_BALL_FRAMES,
                              ["Stop"], ["GH", 0], 0], level)
            self.assertEqual(gates["stop_ball"]["frames"], K.DONOR_STOP_BALL_FRAMES, level)
            self.assertEqual(list(wf_dsl.iter_dsl_commands(tree, "MoveBall")), [], level)

    def test_a_drifted_donor_is_caught(self):
        tree = K.donor_tree(ctx(), "2")
        K.drop_power_flip_block(tree)
        with self.assertRaises(KL.KitError):
            K.drop_power_flip_block(tree)          # 第二次就没有第二条语句了


@unittest.skipUnless(_BASELINE, "需要 .cdn/cn 官方归档与 live store")
class EncoreTreeTests(unittest.TestCase):
    def build(self):
        block = DESIGN["plan_rework1"]["skills"]["values"]
        level = str(block["encore_level"])
        values = dict(block[level])
        values["hit_area_damage_kind"] = block["hit_area_damage_kind"]
        return K.build_encore_tree(ctx(), level, values, None)

    def test_encore_carries_only_the_damage_block(self):
        tree, gates = self.build()
        self.assertEqual(len(K.statements(tree)), 1)
        self.assertEqual(gates["team_blocks"], 0)
        self.assertEqual(list(wf_dsl.iter_dsl_commands(tree, "CreateCondition")), [])

    def test_encore_chases_the_enemy_without_the_long_stop(self):
        """反馈轮 4：母本 70 帧 StopBall → 铃鹿 1 帧 MoveBall（转向照旧、长停顿没了）。"""
        tree, gates = self.build()
        self.assertEqual(gates["stop_ball_swapped"], 1)
        self.assertEqual(json.dumps(tree).count("StopBall"), 0)
        moves = list(wf_dsl.iter_dsl_commands(tree, "MoveBall"))
        self.assertEqual(len(moves), 1)
        self.assertEqual(moves[0], K.CHASE_MOVE_BALL)
        self.assertEqual(gates["chase_command"], K.CHASE_MOVE_BALL)
        self.assertEqual(gates["chase_donor"], K.SUZUKA_PROGRAM)

    def test_gates_report_the_slowdown_instead_of_denying_it(self):
        """manifest 的证据串从 gates 取数：两档速度固定上限 + 「哪几档会被减速」。"""
        _, gates = self.build()
        values = DESIGN["plan_rework1"]["skills"]["values"]
        level = str(values["encore_level"])
        self.assertEqual(gates["chase_speed"], K.CHASE_MOVE_BALL[5])
        self.assertEqual(gates["fixed_speed_grades"],
                         {"none": 0,
                          "normal": values[level]["fixed_speed_speed"],
                          "boost": values[level]["fixed_speed_speed_boost"]})
        self.assertEqual(gates["ball_speed_caps"],
                         {"none": 68,
                          "normal": K.ball_speed_cap(values[level]["fixed_speed_speed"]),
                          "boost": K.ball_speed_cap(values[level]["fixed_speed_speed_boost"])})
        # 强化档与常态档都会被砸慢；速度格 0 那档不会
        self.assertEqual(gates["chase_slows_ball_at_grades"], ["boost", "normal"])

    def test_encore_chase_target_is_the_findnearsubjects_binding(self):
        """``["GH", 0]`` 必须落在绑定 0 的那个 FindNearSubjects 作用域内，否则战斗中 C16103。"""
        tree, _ = self.build()
        finds = list(wf_dsl.iter_dsl_commands(tree, "FindNearSubjects"))
        self.assertEqual(len(finds), 1)
        self.assertEqual(list(finds[0][1:6]), K.CHASE_FIND_HEAD)
        self.assertEqual(finds[0][5], 0)                       # 绑定 id
        self.assertEqual(K.CHASE_MOVE_BALL[2], ["GH", finds[0][5]])
        self.assertEqual(L.action_dsl_lookup_scope_problems(tree), [])

    def test_encore_chase_command_matches_the_official_donor_row(self):
        """整条 MoveBall 是从官方铃鹿树里搬的，不是手写的。"""
        self.assertEqual(K.chase_ball_command(ctx()), K.cmd(K.CHASE_MOVE_BALL))

    def test_official_donor_slams_the_ball_while_itself_speed_fixed(self):
        """官方标定：铃鹿**同一棵树**里既有这条 72，也给自己 ``ACFixedSpeed`` 速度格 4。

        这是「把球速赋值到 72」在官方设计里的先例 —— 不是「不会减速」的证明，
        而是「官方在 4 档速度固定的角色身上也这么赋值」的证明（返修待判项 §8.9 的依据）。
        """
        donor = ctx().template_dsl(K.SUZUKA_PROGRAM)
        moves = list(wf_dsl.iter_dsl_commands(donor, "MoveBall"))
        self.assertIn(K.CHASE_MOVE_BALL, moves)
        grades = sorted(c[2][0][2][0]["min"]
                        for c in wf_dsl.iter_dsl_commands(donor, "CreateCondition")
                        if c[2][0][0] == "ACFixedSpeed")
        self.assertEqual(grades, [1, 4])
        self.assertLess(K.CHASE_MOVE_BALL[5], K.ball_speed_cap(4))

    def test_encore_chase_sits_where_the_donor_stop_ball_was(self):
        """就地替换：MoveBall 仍是参考点块的第一条，斩击特效还在它后面。"""
        def head(tree):
            points = [n for n in wf_dsl.iter_dsl_commands(tree, "CreateReferencePoint")]
            self.assertEqual(len(points), 1)
            # 块里混着 ["Event", ["Wait", …]]，command() 对它返回 None
            return [c[0] if c else "Event" for c in K.block_commands(points[0], 11)][:2]

        donor = K.donor_tree(ctx(), str(DESIGN["plan_rework1"]["skills"]["values"]["encore_level"]))
        self.assertEqual(head(donor), ["StopBall", "ShowEffect"])
        tree, _ = self.build()
        self.assertEqual(head(tree), ["MoveBall", "ShowEffect"])

    def test_encore_combo_bonus_is_always_on_and_unbranched(self):
        tree, _ = self.build()
        attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
        self.assertEqual(len(attacks), 2)
        self.assertTrue(all(a[K.CNA_COMBO_SLOT] is True for a in attacks))
        self.assertEqual(json.dumps(tree).count("ConditionalsChangeSkillFlag"), 0)

    def test_encore_keeps_the_direct_attack_attribution(self):
        tree, _ = self.build()
        self.assertEqual(tree[10], 0)                 # 根 buffTargetAs 保持自动档
        for area in wf_dsl.iter_dsl_commands(tree, "CreateHitArea"):
            self.assertEqual(area[K.HIT_AREA_DAMAGE_SLOT], 4)

    def test_encore_dsl_gates_pass(self):
        tree, gates = self.build()
        self.assertEqual(K.dsl_problems(tree), [])
        self.assertEqual(set(gates["effect_paths"]), set(K.OFFICIAL_FX_PATHS))

    def test_encore_detoughness_is_capped_for_a_629_call(self):
        """2026-09-27 平衡第二批（口径 B.3）：629 CT 5 秒 ⇒ 每次 ≤3；斩击 10→1.5、爆击 1→0.1（×10）＝ 2.5。"""
        tree, gates = self.build()
        by_hits = {int(a[K.HIT_AREA_MAXHITS_SLOT][1]): a for a in wf_dsl.iter_dsl_commands(tree, "CreateHitArea")}
        slash = next(iter(wf_dsl.iter_dsl_commands(by_hits[1][K.HIT_AREA_ONHIT_SLOT], "CreateNormalAttack")))
        burst = next(iter(wf_dsl.iter_dsl_commands(by_hits[10][K.HIT_AREA_ONHIT_SLOT], "CreateNormalAttack")))
        self.assertEqual(slash[K.CNA_DETOUGHNESS_SLOT], [{"min": 1.5, "max": 1.5}])
        self.assertEqual(burst[K.CNA_DETOUGHNESS_SLOT], [{"min": 0.1, "max": 0.1}])
        self.assertEqual(gates["detoughness"]["per_cast"], 2.5)
        self.assertLessEqual(gates["detoughness"]["per_cast"], 3)

    def test_normal_skill_detoughness_is_untouched(self):
        """第二批只改 629 追击树；正常技能两档每次 10 ＋ 10×1 = 20 不动。"""
        values = DESIGN["plan_rework1"]["skills"]["values"]
        for level in ("1", "2"):
            level_values = dict(values[level])
            level_values["hit_area_damage_kind"] = values["hit_area_damage_kind"]
            tree, _ = K.build_skill_tree(ctx(), level, level_values, None)
            p13 = sorted({a[K.CNA_DETOUGHNESS_SLOT][0]["max"]
                          for a in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")})
            self.assertEqual(p13, [1, 10], level)


# ---------------------------------------------------------------- 3. 已构建的包

@unittest.skipUnless((WORKSPACE / "package").is_dir(), "workspace 还没构建")
class PackageTests(unittest.TestCase):
    def pkg(self) -> Path:
        return WORKSPACE / "package" / "roots" / "common"

    def test_three_dsl_programs_are_in_the_package(self):
        want = [f"battle/action/skill/action/rare5/{K.CODE}${K.CODE}_1",
                f"battle/action/skill/action/rare5/{K.CODE}${K.CODE}_2",
                K.ENCORE_PROGRAM]
        for program in want:
            path = self.pkg() / wf_dsl.dsl_logical(program)
            self.assertTrue(path.is_file(), program)

    def _packed_tree(self, program: str):
        import zlib
        data = (self.pkg() / wf_dsl.dsl_logical(program)).read_bytes()
        return wf_dsl.parse_dsl(zlib.decompress(data, -15))["tree"]

    def test_packed_encore_chases_and_the_packed_skills_still_stop(self):
        """回读包内产物（不是内存树）：追击树转向、正常两档仍 70 帧停球。"""
        encore = self._packed_tree(K.ENCORE_PROGRAM)
        self.assertEqual(list(wf_dsl.iter_dsl_commands(encore, "StopBall")), [])
        self.assertEqual(list(wf_dsl.iter_dsl_commands(encore, "MoveBall")),
                         [K.CHASE_MOVE_BALL])
        finds = list(wf_dsl.iter_dsl_commands(encore, "FindNearSubjects"))
        self.assertEqual([list(n[1:6]) for n in finds], [K.CHASE_FIND_HEAD])
        for level in ("1", "2"):
            tree = self._packed_tree(f"battle/action/skill/action/rare5/{K.CODE}${K.CODE}_{level}")
            self.assertEqual(list(wf_dsl.iter_dsl_commands(tree, "MoveBall")), [], level)
            self.assertEqual(list(wf_dsl.iter_dsl_commands(tree, "StopBall")),
                             [["StopBall", -18, K.DONOR_STOP_BALL_FRAMES,
                               ["Stop"], ["GH", 0], 0]], level)

    def test_custom_ability_string_carries_exactly_our_ten_keys(self):
        """多行 desc_override 的 ``\\n`` 必须活过 orderedmap 的 CSV 编解码（同 hibiki 的等价用例）。"""
        blob = core.read_orderedmap_file_from_bytes(
            (self.pkg() / KL.CAS).read_bytes())
        ours = {k for k in blob if k in K.CAS_TEXTS}
        self.assertEqual(ours, set(K.CAS_TEXTS))
        import wf_balance_20260927c_rolfmoon as RC
        for key, text in K.CAS_TEXTS.items():
            packed = C.csv_split(blob[key])[0][0]
            if key == K.CAS_LEADER and packed == RC.B_PANEL_LEADER:
                # 2026-09-27 第三轮成长复核：候选由主会话暂存脚本回写，回写前包内仍是第二批队长面板（唯一允许的过渡态）。
                self.assertEqual(RC.leader_text([[packed]]), [[text]])
                continue
            if key == K.CAS_ABILITY[4] and packed == "\n".join(RC.OLD_A4_LINES):
                # 同上：第三轮面板同条件合并回写前，包内仍是合并前两行。
                self.assertEqual(RC.ability4_text([[packed]]), [[text]])
                continue
            if key == K.CAS_ABILITY[3] and packed == "\n".join(RC.OLD_A3_LINES):
                # 同上：第三轮技能强化文案（能力3 第3行拆行）回写前，包内仍是 live 旧文。
                self.assertEqual(RC.ability3_text([[packed]]), [[text]])
                continue
            if key in RC.FLAG_TEXTS and packed == RC.FLAG_TEXTS[key][0]:
                # 同上：两条强化条目改官方格式回写前，包内仍是旧写法。
                self.assertEqual(RC.flag_text(key, [[packed]]), [[text]])
                continue
            self.assertEqual(packed, text, key)
        # 改键名前写出来的旧条目不许留在包里（否则 manifest 的 claimed_keys 会一直红）
        self.assertNotIn(f"ability_skill_{K.CODE}_encore", blob)

    def test_package_has_no_unique_condition_table(self):
        self.assertFalse((self.pkg() / MS.UNIQUE_CONDITION_LOGICAL).is_file())

    def test_manifest_declares_both_capabilities(self):
        manifest = json.loads((WORKSPACE / "package" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(manifest["required_capabilities"]),
                         sorted(K.SPEC["required_capabilities"]))

    def test_manifest_evidence_states_the_slowdown_and_the_pending_call(self):
        """20260921 返修：manifest 的证据串必须写清「追击那一帧是减速」＋ 待判项，不能再声称不会改慢。"""
        manifest = json.loads((WORKSPACE / "package" / "manifest.json").read_text(encoding="utf-8"))
        notes = [n for n in manifest["snapshot"]["seasonal7"]["reports"]["kit"]["notes"]
                 if isinstance(n, str)]
        hit = [n for n in notes if "返修" in n and "MoveBall" in n]
        self.assertEqual(len(hit), 1, "证据串里应恰好有一条返修更正")
        note = hit[0]
        for want in ("赋值", "可见的减速", "真机待判项",
                     str(int(K.ball_speed_cap(4))), str(int(K.ball_speed_cap(1)))):
            self.assertIn(want, note, want)

    def test_package_does_not_clone_any_effect_family(self):
        """裁决 §4：特效优先直接引用官方路径，零克隆零图集增量。"""
        self.assertFalse((self.pkg() / "battle" / "effect" / "skill_unique" / K.CODE).exists())


if __name__ == "__main__":
    unittest.main()
