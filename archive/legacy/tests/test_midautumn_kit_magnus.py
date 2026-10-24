# -*- coding: utf-8 -*-
"""玛格诺斯（119990 lion_swordman_moon）kit 的单测 —— rework1（2026-09-21）。

四层：
1. 纯静态（无 IO）：行计划的硬约束——队长表禁 422/724/713、422 必须挂前置 42 且 param_id 显式、
   629 排在 525 之前且同触发同 CT、固有 ID 8 位 / 上限不是 (None)、自有键全部声明、面板文案规则；
2. 设计稿对账：``B/design/magnus.json`` 的 ``plan_rework1`` 与 kit 常量逐项一致；
3. 集成（需要 live store + ``.cdn/cn`` 官方归档）：用 kitlib 的真实代码路径回放 23 行
   （``build_row`` 的 ``expect_describe`` 逐字比对），并从官方 donor 树重建 6 棵 DSL；
4. 成品包（需要已重建的 workspace）：PF 三档、克隆特效族、克拉莉丝裁段都真的落进了包里。
"""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_dsl  # noqa: E402
import wf_midautumn_kit_magnus as KM  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_mod_tool as core  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
WORKSPACE = REPO / "work/character_packs/ma-magnus"
PKG_COMMON = WORKSPACE / "package/roots/common"


def _live_available() -> bool:
    profile = core.resolve_profile()
    return (profile is not None and profile.store.is_dir()
            and (core.project_root() / ".cdn" / "cn").is_dir())


_LIVE = _live_available()

# 队长表写这三个 kind = 角色页 C7050（裁决 §8 / 记忆卡 wf-dash-parameter-leader-table-trap）
LEADER_FORBIDDEN_KINDS = ("422", "724", "713")
ABILITY_CONTENT_COL = 47
ABILITY_DURING_CONTENT_COL = 109
LEADER_CONTENT_COL = 45
LEADER_DURING_CONTENT_COL = 107


class PlanStaticTests(unittest.TestCase):
    """不碰任何表，只看 kit 常量自身的一致性。"""

    def test_identity_matches_the_registry(self):
        spec = MS.SPECS["magnus"]
        self.assertEqual((spec.cid, spec.code), (KM.CID, KM.CODE))
        self.assertEqual((spec.template_id, spec.template_code),
                         (KM.TEMPLATE_ID, KM.TEMPLATE_CODE))
        self.assertEqual(spec.element, 0, "玛格诺斯改口为火，不翻属性")

    def test_unique_id_is_eight_digits_under_cid(self):
        self.assertEqual(KM.UID, str(KM.CID * 100 + 1))
        self.assertEqual(KM.UID_AURA, str(KM.CID * 100 + 2))
        self.assertEqual({len(KM.UID), len(KM.UID_AURA)}, {8})
        self.assertNotEqual(KM.UID, KM.UID_AURA)

    def test_unique_condition_is_unbounded_in_both_axes(self):
        self.assertNotIn(KM.UNIQUE_CAP, ("", "(None)"), "(None) 会被读成上限 1，叠层全死")
        self.assertEqual(KM.UNIQUE_CAP, "99", "「不设置上限」的官方写法是 99")
        self.assertEqual(KM.UNIQUE_FRAMES, "99999999", "「无时间限制」的官方写法")
        self.assertEqual(KM.UNIQUE_CELLS[3], KM.UNIQUE_FRAMES)
        self.assertEqual(KM.UNIQUE_CELLS[4], KM.UNIQUE_CAP)

    def test_aura_state_lives_exactly_as_long_as_the_ring(self):
        """「烈焰光环」的时长必须与光环寿命同源——写死另一个数字＝面板与画面脱钩。"""
        self.assertEqual(KM.AURA_UNIQUE_CELLS[3], str(KM.AURA_FRAMES))
        self.assertEqual(KM.AURA_UNIQUE_CELLS[2], KM.UC_AURA_ICON_ROW)
        self.assertEqual(KM.AURA_UNIQUE_CELLS[14], "(None)", "c14 是 PF 语音替换，这个状态不碰它")
        self.assertEqual(KM.AURA_UNIQUE_CAP, "1", "上限 1 层（官方同值先例 unique_ice_dragon 等）")
        self.assertNotIn(KM.AURA_UNIQUE_CAP, ("", "(None)"),
                         "(None) 同样是上限 1，但 KL.unique_row 拒绝它")
        self.assertEqual(KM.AURA_MARK_STACKS, 1, "ACUnique 第二参是层数；上限 1 ⇒ 只能是 1")
        self.assertEqual(KM.AURA_MARK_TARGET_KIND, 3,
                         "下标 10 付与对象种类：自身/Member 写 3，错配 = 施法 C16102")

    def test_every_self_owned_key_is_declared(self):
        declared = {logical: set(keys) for logical, keys in SPEC_KEYS().items()}
        self.assertIn(KM.UID, declared[MS.UNIQUE_CONDITION_LOGICAL])
        self.assertIn(KM.UID_AURA, declared[MS.UNIQUE_CONDITION_LOGICAL])
        self.assertEqual(set(KM.CAS_TEXTS), declared[KL.CAS])
        self.assertIn(KM.VOICE_KEY, declared[KL.SWITCHED])
        self.assertEqual(declared[KM.PFA], {KM.PF_KEY})

    def test_ability_key_c0_c1_c2_are_uniform_per_key(self):
        for slot, records in KM.PLAN.items():
            c0 = {cells.get(0) for _d, _s, cells, _e in records}
            self.assertEqual(c0, {f"{KM.CODE}_{slot}"}, f"slot {slot} c0")
            c1 = {cells.get(1) for _d, _s, cells, _e in records}
            self.assertEqual(len(c1), 1, f"slot {slot} 主位限制必须单值: {c1}")
            c2 = {cells.get(2) for _d, _s, cells, _e in records}
            self.assertEqual(len(c2), 1, f"slot {slot} 雕像组必须单值: {c2}")
            self.assertLessEqual(c2 - set(_statue_groups()), set(), f"slot {slot} 雕像组不认识")

    def test_only_slot3_is_main_position_only(self):
        main_only = {slot for slot, records in KM.PLAN.items()
                     if records[0][2].get(1) == "false"}
        self.assertEqual(main_only, {3}, "目标面板只有能力 3 带 Ⓜ")

    def test_invoke_row_precedes_the_consume_row(self):
        """629 发动追击必须排在同触发的 525 消耗行之前，否则最后一层先被吃掉。"""
        slot3 = KM.PLAN[3]
        invoke = next(i for i, (_d, _s, c, _e) in enumerate(slot3)
                      if c.get(70) == KM.CHASE_STRING)
        consume = next(i for i, (_d, _s, _c, e) in enumerate(slot3) if "消耗固有状态" in e)
        self.assertLess(invoke, consume)

    def test_invoke_and_consume_share_precondition_trigger_and_cooldown(self):
        by_desc = {e: c for _d, _s, c, e in KM.PLAN[3]}
        invoke = next(c for e, c in by_desc.items() if "发动技能动作" in e)
        consume = next(c for e, c in by_desc.items() if "消耗固有状态" in e)
        for col in (6, 7, 9, 10, 12, 27, 28, 30, 31, 34, 35):
            self.assertEqual(invoke.get(col), consume.get(col), f"c{col} 必须同形")
        self.assertEqual(invoke[6], "188", "前置 188 = 固有状态实例数")
        self.assertEqual(invoke[9], "100000",
                         "188 数的是实例数（恒为 1）：阈值只能写 ≥1，写 ≥2 永不成立")
        self.assertEqual(invoke[27], "136",
                         "作者确认自身技能命中 = 136 OneOfEnemySkillHit")
        self.assertEqual(invoke[35], "36", "多敌时一次 PF 触发多次 ⇒ 必须带 CT 限流")

    def test_629_row_carries_both_the_string_key_and_the_program(self):
        invoke = next(c for _d, _s, c, e in KM.PLAN[3] if "发动技能动作" in e)
        self.assertEqual(invoke[70], KM.CHASE_STRING)
        self.assertEqual(invoke[71], KM.CHASE_PROGRAM)
        self.assertIn(KM.CHASE_STRING, KM.CAS_TEXTS, "629 必须配一条面板字符串")

    def test_stack_gates_never_use_the_instance_counting_preconditions(self):
        """「引擎点火 N 层以上」只能走 during 134；前置 188 / during 194 数实例恒为 1。"""
        layered = [c for _d, _s, c, _e in KM.PLAN[3]
                   if c.get(97) is None and c.get(ABILITY_DURING_CONTENT_COL) == "411"]
        gate = next(c for _d, _s, c, e in KM.PLAN[3] if "≥5(限1次)" in e)
        self.assertEqual(gate[100], "500000", "阈值 = 5 层")
        self.assertEqual(gate[102], "1", "limit 1 ⇒ 平坦门槛（写 (None) 才是按层成长）")
        # 第一批输出 c102=(None)（按层无上限）＋ 2026-09-27 第二批覆盖：能力栏改为最多计 10 层，
        # 无上限部分搬进队长（wf_balance_20260927b_magnus）。留空串 = 上限 0，全程零收益，仍禁止。
        grow = next(c for _d, _s, c, e in KM.PLAN[3] if c.get(109) == "411" and c.get(110) == "5")
        self.assertEqual(grow[100], "100000", "每 1 层")
        self.assertEqual(grow[102], KM.LAYER_ABILITY_LIMIT)
        self.assertEqual(grow[102], "10")
        self.assertEqual(grow[104], KM.UID)
        del layered

    def test_during_134_rows_declare_the_unique_id(self):
        """during 134 的固有 id 列必须是本角色的固有（puller 契约在集成层按成品行复核）。"""
        seen = 0
        for slot in (2, 3):
            for _d, _s, cells, expect in KM.PLAN[slot]:
                if "状态累积计数固有" not in expect:
                    continue
                self.assertEqual(cells.get(104), KM.UID, expect)
                seen += 1
        self.assertEqual(seen, 4, "槽 2 两条按层加成 + 槽 3 两条独立乘区")

    def test_leader_rows_never_carry_dash_fever_or_713(self):
        for index, (_donor, _source, cells, _expect) in enumerate(KM.LEADER):
            for col in (LEADER_CONTENT_COL, LEADER_DURING_CONTENT_COL):
                value = cells.get(col)
                if value is not None:
                    self.assertNotIn(str(value), LEADER_FORBIDDEN_KINDS, f"leader#{index}")

    def test_dash_rows_live_in_the_ability_table_behind_the_leader_precondition(self):
        dash = [c for _d, _s, c, e in KM.PLAN[5] if "冲刺参数" in e]
        self.assertEqual(len(dash), 2, "常驻 CD 行 + 疾走抵消行")
        for cells in dash:
            self.assertEqual(cells.get(0), f"{KM.CODE}_5")
        # 422 的前置/param_id 来自 donor，行装配后由 _dash_problems 复核（见集成层）
        self.assertEqual(sorted(int(c[113]) for c in dash),
                         sorted((KM.DASH_PARAM0_BASE, KM.DASH_PARAM0_SWIFT)))
        for cells in dash:
            self.assertEqual(cells[113], cells[114], "满级单值，行拉平")

    def test_swift_offset_matches_the_cancellation_formula(self):
        """非 Swift 90×(1+s0) 帧 == Swift 中 20×(1+s0+m) 帧 ⇒ m = 3.5×(1+s0)。"""
        s0 = KM.DASH_PARAM0_BASE / 100000
        m = KM.DASH_PARAM0_SWIFT / 100000
        self.assertAlmostEqual(90 * (1 + s0), 20 * (1 + s0 + m), places=6)

    def test_722_row_is_gated_on_this_character_element_only(self):
        pf = next(c for _d, _s, c, e in KM.LEADER if "强化弹射覆盖" in e)
        self.assertEqual(pf[45], "722")
        self.assertEqual(pf[4], "2", "前置必须是编成门（官方 141201#1 先例）")
        self.assertEqual(pf[9], "Red", "门必须是本角色属性")
        self.assertEqual(pf[80], KM.PF_KEY)
        self.assertEqual(pf[81], "1,2,3")
        self.assertEqual(pf[82], KM.PF_STRING)
        self.assertEqual(len(KM.PF_PROGRAMS), 3)
        self.assertTrue(all(KM.PF_KEY in p for p in KM.PF_PROGRAMS))

    def test_ball_flip_combo_row_is_wired_cell_by_cell(self):
        """作者追加行的逐格改：donor ＝ 官方唯一一族「BallFlip → AddCombo」的队长行。

        触发/内容 kind 本身来自 donor（不在 cells 里），在集成层按**装配后的整行**复核。
        """
        donor, source, cells, expect = next(item for item in KM.LEADER if "追加连击" in item[3])
        self.assertEqual((donor, source), ("131005#4", "official"))
        self.assertEqual(cells[4], "188", "前置 kind：队长表里 187 零先例，188 有 6 行先例")
        self.assertEqual(cells[5], "0", "前置 188 的 puller 列留空 = 角色页 C7050")
        self.assertEqual((cells[7], cells[8]), ("100000", "100000"), "阈值 ≥1 个实例（≥2 永不成立）")
        self.assertEqual(cells[9], "", "这一行不带属性组：作者原话没写属性共鸣")
        self.assertEqual(cells[10], KM.UID_AURA, "前置的固有 id 列不能留空")
        self.assertEqual((cells[28], cells[29]), ("100000", "100000"), "每 1 次弹射")
        self.assertEqual(cells[33], "0", "无冷却（donor 是 CT10 秒）")
        self.assertEqual((cells[49], cells[50]), ("3500000", "3500000"), "连击类 ×100000 ⇒ +35")
        self.assertNotIn(46, cells, "226 的 target 列照官方 226 行留空（= 自身）")
        self.assertEqual(cells[1], "0", "c1 觉醒标记：donor 是 [觉醒1追加]，本角色全部是 '0'")
        self.assertEqual(cells[2], "", "c2 觉醒等级同上")
        self.assertEqual(expect, f"状态计数固有≥1[固有{KM.UID_AURA}] 时: 弹射≥1 → 自身 追加连击 35")

    def test_ball_flip_combo_row_carries_no_resonance_gate(self):
        """其余 5 行都挂火共鸣门（自带或 FIRE_LEADER），这一行必须是唯一一条不挂门的。"""
        gates = [cells.get(4) for _d, _s, cells, _e in KM.LEADER]
        self.assertEqual(gates.count("188"), 1, "只有作者追加行用 188")
        row = next(c for _d, _s, c, e in KM.LEADER if "追加连击" in e)
        self.assertEqual(row[4], "188")
        self.assertNotEqual(row[4], KM.FIRE_LEADER[4], "不是火共鸣门")
        for col in (7, 8, 9):
            self.assertNotEqual(row.get(col), KM.FIRE_LEADER[col], f"c{col} 不许写成火共鸣门的值")
        for _d, _s, cells, expect in KM.LEADER:
            if "追加连击" in expect:
                self.assertNotIn("火·编成", expect)
            elif cells.get(107) == "411":
                # 2026-09-27 第二批覆盖：从能力 3#4 搬入的「点火每层全队独立乘区」原行就没有前置（c6=0），
                # 转置后照旧不挂门（wf_balance_20260927b_magnus）。
                self.assertNotIn("火·编成", expect)
                self.assertNotIn(4, cells, "前置取 donor 161123#0 的 0")
            else:
                self.assertIn("火·编成≥6", expect, f"其余队长行仍是火共鸣门: {expect}")

    def test_the_aura_state_is_only_gated_on_by_the_leader_row(self):
        """新固有只服务队长技那一行；词条 6 键一条都不许引用它（引用 = 悄悄多一层效果）。"""
        for slot, records in KM.PLAN.items():
            for _d, _s, cells, expect in records:
                self.assertNotIn(KM.UID_AURA, [str(v) for v in cells.values()],
                                 f"slot {slot}: {expect}")

    def test_all_rows_are_flattened_to_the_max_level_value(self):
        """作者总口径「全部都按照满级的描述」⇒ 强度两端相等。"""
        pairs = ((51, 52), (49, 50), (113, 114))
        for label, records in [("leader", [r[2] for r in KM.LEADER])] + \
                [(f"slot{s}", [r[2] for r in rs]) for s, rs in KM.PLAN.items()]:
            for cells in records:
                for lo, hi in pairs:
                    if lo in cells and hi in cells:
                        self.assertEqual(cells[lo], cells[hi], f"{label} c{lo}/c{hi}")

    def test_panel_strings_follow_the_batch_rules(self):
        for key, text in KM.CAS_TEXTS.items():
            for line in text.split("\n"):
                self.assertEqual(
                    KL.panel_problems(line.replace(KM.MAIN_ICON, ""),
                                      skill_flag=key in KM.SKILL_FLAG_TEXT_KEYS),
                    [], f"{key}: {line}")
        for value in KM.TEXTS.values():
            self.assertEqual(KL.panel_problems(value), [], value)

    def test_main_position_slot_override_carries_its_own_icon(self):
        """desc_override 把客户端逐行画的 Ⓜ 一起盖掉 ⇒ 主位键的覆盖文案必须自带图标。"""
        for slot in KM.SLOT_OVERRIDE_SLOTS:
            lines = KM.CAS_TEXTS[KM.SLOT_OVERRIDE[slot]].split("\n")
            wants = KM.PLAN[slot][0][2].get(1) == "false"
            for line in lines:
                self.assertEqual(line.startswith(KM.MAIN_ICON), wants, f"slot {slot}: {line}")

    def test_panel_override_line_counts_match_the_target_panel(self):
        # 第一批输出 队长 7 / 槽1 3 行 ＋ 2026-09-27 第二批覆盖：队长 +3（自身技伤、点火逐层两行）、
        # 槽1 +1（每 3PF 自身技伤单列），见 wf_balance_20260927b_magnus；
        # ＋ 第三轮覆盖：队长 +1（旗号 2「强化自身技能」行），同轮面板同条件合并 −4（L4–L7 并一行、
        # L8+L9 删共鸣后并一行），见 wf_balance_20260927c_magnus。
        counts = {KM.LEADER_OVERRIDE: 7, KM.SLOT_OVERRIDE[1]: 4,
                  KM.SLOT_OVERRIDE[2]: 1, KM.SLOT_OVERRIDE[3]: 6, KM.SLOT_OVERRIDE[5]: 2}
        for key, want in counts.items():
            self.assertEqual(len(KM.CAS_TEXTS[key].split("\n")), want, key)

    def test_the_new_leader_line_is_the_last_one_and_names_the_state(self):
        lines = KM.CAS_TEXTS[KM.LEADER_OVERRIDE].split("\n")
        self.assertEqual(lines[-1], "自身持有「烈焰光环」期间，每次弹射，连击＋35")
        self.assertIn(KM.AURA_UNIQUE_NAME, lines[-1], "面板必须点名这个状态，玩家才对得上图标")
        self.assertNotIn("强化弹射", lines[-1], "作者说的是弹射（BallFlip），不是强化弹射")
        self.assertNotIn("共鸣", lines[-1], "这一行不带属性共鸣门，文案也不能写")

    def test_target_panel_leader_block_matches_the_override_string(self):
        """目标面板（作者过目的那一版）与实际写进表的覆盖串必须逐行逐字相同。"""
        path = REPO / "work/character_packs/midautumn-20260920/rework1/panel/magnus.json"
        if not path.is_file():
            self.skipTest(f"panel target absent: {path}")
        panel = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([line["text"] for line in panel["leader"]["lines"]],
                         KM.CAS_TEXTS[KM.LEADER_OVERRIDE].split("\n"))

    def test_energy_is_six_hundred_on_both_levels(self):
        self.assertEqual(KM.ENERGY["1"][:2], ("600", "600"))
        self.assertEqual(KM.ENERGY["2"][:2], ("600", "600"))
        self.assertEqual(KM.ENERGY["1"][0], KM.ENERGY["2"][0],
                         "官方 492 个双档技能的 c4 两档恒同值")

    def test_voice_route_avoids_the_always_on_change_skill_flag(self):
        self.assertEqual(KM.VOICE_ROUTE["kind"], 1,
                         "kind 3 会因 536 常驻而让 skill_ready 永不播")
        self.assertEqual(KM.VOICE_ROUTE["condition_id"], KM.UID)

    def test_cloned_effect_families_live_under_this_code_name(self):
        for subdir, src_dir, names in KM.FX_CLONES:
            self.assertTrue(src_dir.startswith("battle/effect/skill_unique/"), src_dir)
            self.assertNotIn(KM.CODE, src_dir, "克隆源必须是官方族")
            self.assertTrue(names)
        for path in (KM.ZETA_LANCE, KM.CLARISSE, KM.AURA):
            self.assertTrue(path.startswith(f"battle/effect/skill_unique/{KM.CODE}/"),
                            f"兄弟目录名会「进战斗数据不足」: {path}")
        self.assertTrue(KM.FLAME.startswith(f"battle/effect/skill_unique/{KM.TEMPLATE_CODE}/"),
                        "母本件不克隆 ⇒ 直接引用官方路径，图集零增量")

    def test_clarisse_tail_cut_constants(self):
        self.assertEqual(KM.CLARISSE_NEW_R, (1 << 30) | KM.CLARISSE_CUT)
        self.assertEqual(KM.CLARISSE_NEW_T, KM.CLARISSE_TOTAL - KM.CLARISSE_CUT)
        self.assertEqual(KM.CLARISSE_NEW_R >> 30, 1, "kind=1 播一次，末帧定格")

    def test_burst_sequences_leave_a_tail_the_client_can_jump_to(self):
        """反馈轮 2 根因：单段 `neutral`(once) ⇒ 终止时无段可跳＝立删（爆炸突然消失）。"""
        seqs = [dict(s) for s in KM.CLARISSE_SEQUENCES]
        KM._sequence_problems(seqs, KM.CLARISSE_NEW_T)          # 覆盖/末段/寿命落点全在这里判
        self.assertEqual(seqs[0]["name"], "neutral", "首段名保持母本，别改成 start")
        self.assertEqual(seqs[-1]["name"], "end")
        self.assertEqual(seqs[-1]["kind"], "once")
        self.assertGreaterEqual(int(seqs[-1]["end"]) - int(seqs[-1]["begin"]) + 1, 16,
                                "收尾至少要有 16 帧过渡，作者要的是「补帧」")

    def test_hit_window_is_one_number_for_all_three_knobs(self):
        """suppress / Wait+2 / 参考点 / 演出寿命 官方恒等 —— 只抬一个就会又被连坐删掉。"""
        self.assertEqual(KM.PF_HIT_WINDOW_DONOR, {1: 20, 2: 30, 3: 30}, "官方底座原值")
        self.assertGreater(KM.PF_HIT_WINDOW, max(KM.PF_HIT_WINDOW_DONOR.values()),
                           "原值放不下 79 帧的克拉莉丝末端")
        self.assertLessEqual(KM.PF_HIT_WINDOW, 60,
                             "官方 psycho_reaper 722 用 40；超过 1 秒会明显拖慢弹板归还")
        self.assertLess(KM.PF_HIT_WINDOW, KM.CLARISSE_NEW_T, "寿命必须落在 loop 段里")

    def test_burst_sound_matches_the_burst_length(self):
        """`se_clarisse` 是 157 帧技能的蓄力音（5.07s、峰值第 89 帧），按在爆炸帧上必然错位。"""
        self.assertEqual(KM.BURST_SOUND_DONOR, "sound_effect/unique/se_clarisse")
        self.assertNotEqual(KM.BURST_SOUND, KM.BURST_SOUND_DONOR)
        self.assertTrue(KM.BURST_SOUND.startswith("sound_effect/"), KM.BURST_SOUND)
        self.assertNotIn(".mp3", KM.BURST_SOUND, "timeline 里写的是不带扩展名的逻辑路径")

    def test_power_flip_carries_no_chase_knobs_any_more(self):
        """反馈轮 1：作者要求去掉强化弹射追踪 ⇒ 常量与文案都不许再出现。"""
        for name in ("CHASE_TAG", "CHASE_STEP", "CHASE_SPEED", "CHASE_SELECTOR",
                     "CHASE_BIND", "PF_EXTRA_FX", "ZETA_HIT", "ZETA_END"):
            self.assertFalse(hasattr(KM, name), f"{name} 应随追踪/方块特效一起删掉")
        for text in (KM.CAS_TEXTS[KM.PF_STRING], KM._SKILL_DESC,
                     KM.TEXTS["desc1"], KM.TEXTS["desc2"]):
            self.assertNotIn("追击", text, "行为删了文案不能留")

    def test_zeta_family_is_the_cone_plus_its_hexagon_free_ending(self):
        """反馈轮 1「只要锥形」＋反馈轮 2「收尾要补帧」：end 族回来，但六边形擦成全透明。"""
        by_sub = dict((sub, names) for sub, _src, names in KM.FX_CLONES)
        self.assertEqual(tuple(by_sub["lance"]), ("zeta_lance",))
        self.assertEqual(tuple(by_sub[KM.LANCE_END_SUBDIR]), ("zeta_lance_end",))
        for names in by_sub.values():
            self.assertNotIn("zeta_lance_hit", names, "hit 族还是不要（26 颗方块的主场）")
        self.assertEqual(tuple(KM.LANCE_HEX_LEAVES),
                         ("zeta_lance_end/k", "zeta_lance_end/l"))
        for leaf in KM.LANCE_HEX_LEAVES:
            self.assertTrue(leaf.startswith("zeta_lance_end/"), leaf)
        self.assertEqual(KM.LANCE_HEX_SOLID["zeta_lance_end/k"], (255, 255, 0))
        self.assertEqual(sorted(KM.PF_LANCE_SCALE), [1, 2, 3])
        tiers = [KM.PF_LANCE_SCALE[n] for n in (1, 2, 3)]
        self.assertEqual(tiers, sorted(tiers))
        self.assertLess(tiers[0], tiers[2], "三档靠锥形 scale 递增表达「逐渐增强」")

    def test_lance_ending_lives_in_its_own_subdir(self):
        """1.4.965 在 `lance/zeta_lance_end.*` 发过一次，反馈轮 1 删掉后 live 里成了孤儿路径。

        再写回同一路径＝preflight 的 `occupied_without_hash_bound_prior_path_ownership`
        （实测对 1.4.978 归档会多 2 条自有键冲突，`can_prepare` 直接 false，
        而 `flow rebase` 只归位表行、清不掉资产路径冲突）。所以必须是新目录。
        """
        self.assertEqual(KM.LANCE_END_SUBDIR, "lance_end")
        self.assertNotEqual(KM.LANCE_END_SUBDIR, "lance")
        self.assertEqual(KM.ZETA_LANCE_END,
                         f"{KM.FX_ROOT}/{KM.LANCE_END_SUBDIR}/zeta_lance_end")
        self.assertTrue(KM.ZETA_LANCE_END.startswith(f"battle/effect/skill_unique/{KM.CODE}/"),
                        "兄弟目录名会「进战斗数据不足」")
        subdirs = [sub for sub, _src, _n in KM.FX_CLONES]
        self.assertEqual(len(subdirs), len(set(subdirs)), "子目录名不许重复")

    def test_lance_points_along_the_ball(self):
        """EF = BallImpl.getDirEF() = 球的飞行角（官方 zeta$zeta_1 同写法）；AB 会恒定朝上。"""
        self.assertEqual(KM.PF_LANCE_COORD, ["EF"])

    def test_aura_ring_is_drawn_exactly_on_the_judgement_circle(self):
        """反馈轮 1「没有碰撞到的技能伤害」的根因：环比判定圆大 24%，外圈是纯装饰。"""
        for level in ("1", "2"):
            scale, radius, _mult = KM.AURA_TUNING[level]
            drawn = KM.AURA_RING_PX_PER_SCALE * scale / 2
            self.assertLess(abs(drawn - radius), 2.0,
                            f"lv{level} 画出来的环半径 {drawn:.1f} 必须等于判定半径 {radius}")
        self.assertLess(KM.AURA_TUNING["1"][0], 3.75, "作者要求「稍微小一点」")
        self.assertLess(KM.AURA_TUNING["2"][0], 5.00)
        for level in ("1", "2"):
            shrink = 1 - KM.AURA_TUNING[level][0] / {"1": 3.75, "2": 5.00}[level]
            self.assertTrue(0.10 <= shrink <= 0.25, f"lv{level} 缩了 {shrink:.1%}，越界就不是「稍微」")
        self.assertEqual(KM.AURA_RADIUS, {"1": 200, "2": 270}, "缩的是画面，判定强度不动")
        self.assertEqual(KM.AURA_MAX_HITS, 10, "每目标上限不动 ⇒ 单次技能总伤不变")
        self.assertLess(KM.AURA_HIT_INTERVAL, 600 / (KM.AURA_MAX_HITS - 0.5),
                        "母本 CalculatedUsingMaxNumOfHits(10) 推出来的 63 帧太稀，擦过就打不出第二跳")

    def test_deviations_are_registered(self):
        self.assertTrue(KM.DEVIATIONS)
        for item in KM.DEVIATIONS:
            self.assertEqual({"want", "got", "why"}, set(item))


class UniqueIconTests(unittest.TestCase):
    """两枚 48×48 状态图标：同一个 alpha 外框、不同画面（纯绘制，不碰任何表）。"""

    def _frame(self):
        from PIL import Image, ImageDraw
        frame = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        ImageDraw.Draw(frame).rounded_rectangle((2, 2, 45, 45), radius=6,
                                                fill=(9, 9, 9, 137))
        return frame

    def test_both_icons_keep_the_donor_alpha_and_differ_visibly(self):
        frame = self._frame()
        alpha = frame.getchannel("A").tobytes()
        painted = {}
        for _key, logical, painter in KM.UNIQUE_ICONS:
            image = getattr(KM, painter)(frame)
            self.assertEqual(image.size, (48, 48), logical)
            self.assertEqual(image.getchannel("A").tobytes(), alpha,
                             f"{logical}: alpha 必须一格不改（图集 alpha 门禁）")
            painted[logical] = image.convert("RGB").tobytes()
        self.assertEqual(len(painted), 2)
        a, b = painted[KM.UC_ICON_LOGICAL], painted[KM.UC_AURA_ICON_LOGICAL]
        self.assertNotEqual(a, b, "两枚图标不能长一样")
        differing = sum(1 for x, y in zip(a[::3], b[::3]) if x != y)
        self.assertGreater(differing, 48 * 48 * 0.15, "差异太小，48px 下认不出是两个状态")

    def test_icon_rows_and_painters_line_up(self):
        self.assertEqual([key for key, _l, _p in KM.UNIQUE_ICONS], [KM.UID, KM.UID_AURA])
        self.assertEqual(KM.UNIQUE_CELLS[2] + ".png", KM.UC_ICON_LOGICAL)
        self.assertEqual(KM.AURA_UNIQUE_CELLS[2] + ".png", KM.UC_AURA_ICON_LOGICAL)
        for _key, logical, painter in KM.UNIQUE_ICONS:
            self.assertTrue(callable(getattr(KM, painter)), painter)
            self.assertTrue(logical.startswith("battle/common/unique_condition/"), logical)

    def test_icon_donor_frame_must_be_48(self):
        from PIL import Image
        for _key, _logical, painter in KM.UNIQUE_ICONS:
            with self.assertRaises(KM.KitError):
                getattr(KM, painter)(Image.new("RGBA", (64, 64), (0, 0, 0, 0)))


def SPEC_KEYS() -> dict[str, tuple[str, ...]]:
    return dict(KM.SPEC["extra_keys"])


def _statue_groups() -> tuple[str, ...]:
    import wf_client_legality as L
    return tuple(L.ABILITY_STATUE_GROUPS)


class DesignDocumentTests(unittest.TestCase):
    """kit 常量必须与设计稿 plan_rework1 逐项一致（漂移会让 build 直接报错）。"""

    @classmethod
    def setUpClass(cls):
        path = (REPO / "work/character_packs/midautumn-20260920/design/magnus.json")
        if not path.is_file():
            raise unittest.SkipTest(f"design document absent: {path}")
        cls.design = json.loads(path.read_text(encoding="utf-8"))

    def test_kit_matches_the_design_document(self):
        self.assertEqual(KM._design_problems(self.design), [])

    def test_design_texts_match_the_kit(self):
        for key, value in KM.TEXTS.items():
            self.assertEqual(self.design["texts"][key], value, key)

    def test_first_round_design_is_kept_as_history_only(self):
        self.assertNotIn("plan", self.design, "旧 plan 必须移进 history，不得与 rework1 并存")
        self.assertIn("design_20260920", self.design.get("history", {}))


class InstallStagedAssetsTests(unittest.TestCase):
    """kitlib 的向后兼容小补丁：像素交付件若是标准 PNG，装包时换成 WF 存储态魔数。"""

    class _Pack:
        def __init__(self, batch_dir):
            self.batch_dir = Path(batch_dir)

    class _Ctx:
        def __init__(self, pack):
            self.pack = pack
            self.written = {}

        def write_asset(self, root, logical, data, owner=None):
            self.written[(root, logical)] = (data, owner)

    def _run(self, payload: bytes, logical: str):
        with tempfile.TemporaryDirectory() as tmp:
            batch = Path(tmp)
            staged = batch / "pixel" / "magnus"
            staged.mkdir(parents=True)
            (staged / "sheet.png").write_bytes(payload)
            (staged / "install.json").write_text(json.dumps(
                [{"root": "common", "logical": logical, "file": "sheet.png"}]), encoding="utf-8")
            ctx = self._Ctx(self._Pack(batch))
            result = KL.install_staged_assets(ctx, staged / "install.json")
            return ctx, result

    def test_standard_png_gets_the_store_signature(self):
        payload = b"\x89PNG\r\n\x1a\n" + b"rest-of-the-file"
        ctx, result = self._run(payload, "character/x/pixelart/sprite_sheet.png")
        data, owner = ctx.written[("common", "character/x/pixelart/sprite_sheet.png")]
        self.assertEqual(data, b"\x89png\r\n\x1a\n" + b"rest-of-the-file")
        self.assertEqual(owner, "pixel")
        self.assertTrue(result["installed"][0]["store_signature_applied"])

    def test_store_png_is_passed_through_untouched(self):
        payload = b"\x89png\r\n\x1a\n" + b"already-store"
        ctx, result = self._run(payload, "character/x/pixelart/sprite_sheet.png")
        data, _owner = ctx.written[("common", "character/x/pixelart/sprite_sheet.png")]
        self.assertEqual(data, payload)
        self.assertFalse(result["installed"][0]["store_signature_applied"])

    def test_non_png_payloads_are_untouched(self):
        payload = b"\x89PNG\r\n\x1a\nnot-really"
        ctx, _result = self._run(payload, "character/x/pixelart/pixelart.frame.amf3.deflate")
        data, _owner = ctx.written[("common", "character/x/pixelart/pixelart.frame.amf3.deflate")]
        self.assertEqual(data, payload)

    def test_missing_install_json_is_silently_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            ctx = self._Ctx(self._Pack(tmp))
            result = KL.install_staged_assets(ctx, Path(tmp) / "nope.json")
        self.assertFalse(result["present"])
        self.assertEqual(ctx.written, {})


# ---------------------------------------------------------------- 集成（只读）

class _ReadOnlyPack:
    """DSL 构建用得到的包口：只读已重建的 workspace（不存在时按「文件缺失」处理）。"""

    def __init__(self, batch_dir: Path, ctx=None):
        self.batch_dir = batch_dir
        self._ctx = ctx

    def pkg_path(self, root: str, logical: str) -> Path:
        return WORKSPACE / "package/roots" / root / logical

    def template_asset(self, logical: str):
        """(root, raw, source)：与 ``S7Pack.template_asset`` 同形，只读官方归档。"""
        raw = self._ctx.official_read(logical)
        if raw is None:
            raise FileNotFoundError(logical)
        return "common", raw, "official"


class _ReadOnlyCtx:
    """kitlib.build_row / unique_row 与 kit 的 DSL 构建只用到这几个口，全部只读。"""

    def __init__(self):
        from wf_enhancement_policy import OfficialBaseline
        import wf_seasonal7_common as C
        self.root = core.project_root()
        self.spec = MS.get_spec("magnus", with_kit=False)
        self._baseline = OfficialBaseline(self.root / ".cdn/cn",
                                          cache_dir=self.root / "mod-tools/work/official-baseline",
                                          write_cache=False)
        self._store = core.resolve_profile().store
        self._cache: dict = {}
        self.walk = C.walk
        self.csv_split = core.read_csv_lines
        self.amf_parse = C.amf_parse
        self.png_open = C.png_open
        self._C = C
        self.pack = _ReadOnlyPack(self.root / "work/character_packs/midautumn-20260920", self)

    def official_read(self, logical: str, root: str | None = None):
        digest = core.sha1_path(logical)
        try:
            return self._baseline.get(root or "common", digest[:2] + "/" + digest[2:])
        except Exception:
            return None

    def official_flat(self, table: str) -> dict[str, str]:
        if ("o", table) not in self._cache:
            self._cache[("o", table)] = core.read_orderedmap_file_from_bytes(
                self.official_read(table))
        return self._cache[("o", table)]

    def live_flat(self, table: str) -> dict[str, str]:
        if ("s", table) not in self._cache:
            self._cache[("s", table)] = core.load_table(table, self._store).text_rows()
        return self._cache[("s", table)]

    template_flat = official_flat
    pkg_flat = official_flat

    def template_dsl(self, program: str):
        logical = program if program.endswith(".deflate") else wf_dsl.dsl_logical(program)
        raw = self.official_read(logical)
        if raw is None:
            raise AssertionError(f"official baseline lacks {logical}")
        return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]

    def rewrite_effect_refs(self, tree, family, *, strict: bool = False):
        return self._C.rewrite_effect_refs(tree, family, strict=strict)

    def program_path(self, level: str) -> str:
        import wf_seasonal7_tables as T
        return T.program_path(self.spec, level)


def _stub_families() -> dict[str, dict]:
    """``clone_effect_family`` 的返回形状里 ``rewrite_effect_refs`` 真正用到的那几个键。"""
    out = {}
    for subdir, src_dir, names in KM.FX_CLONES:
        donor = src_dir.rsplit("/", 1)[-1]
        out[subdir] = {"src_dir": src_dir,
                       "dst_dir": f"battle/effect/skill_unique/{KM.CODE}/{subdir}",
                       "donor": donor, "dst_name": subdir,
                       "copied_bases": list(names)}
    return out


@unittest.skipUnless(_LIVE, "requires live store and .cdn/cn official archives")
class RowIntegrationTests(unittest.TestCase):
    """用 kitlib 的真实代码路径回放全部行：donor 漂移 / 列改动写错 / 描述器漂移都会红。"""

    @classmethod
    def setUpClass(cls):
        cls.ctx = _ReadOnlyCtx()

    def _leader_rows(self):
        return [KL.build_row(self.ctx, "leader_ability", d, c, source=s, element=0,
                             expect_describe=e, label=f"L{i}")[0]
                for i, (d, s, c, e) in enumerate(KM.LEADER)]

    def _ability_rows(self, slot):
        return [KL.build_row(self.ctx, "ability", d, c, source=s, element=0,
                             expect_describe=e, label=f"{KM.CID}{slot}#{i}")[0]
                for i, (d, s, c, e) in enumerate(KM.PLAN[slot])]

    def test_leader_rows_build_and_render_as_designed(self):
        for index, (donor, source, cells, expect) in enumerate(KM.LEADER):
            with self.subTest(leader=index):
                row, evidence = KL.build_row(self.ctx, "leader_ability", donor, cells,
                                             source=source, element=0,
                                             expect_describe=expect, label=f"L{index}")
                self.assertEqual(len(row), KL.LEADER_NCOLS)
                self.assertEqual(row[0], KM.CODE)
                self.assertEqual(evidence["describe"], expect)
        KM._leader_forbidden(self._leader_rows())

    def test_ability_rows_build_and_pass_the_key_contract(self):
        for slot in KM.PLAN:
            rows = self._ability_rows(slot)
            for row in rows:
                self.assertEqual(len(row), KL.ABILITY_NCOLS)
            KL.check_ability_key(rows, f"{KM.CID}{slot}", KM.CODE, slot)

    def test_slot3_order_contract_holds_on_the_built_rows(self):
        rows = self._ability_rows(3)
        KM._order_problems(rows)                       # 顺序或 CT 不一致会抛
        kinds = [row[ABILITY_CONTENT_COL] for row in rows]
        self.assertLess(kinds.index("629"), kinds.index("525"))

    def test_slot5_dash_contract_holds_on_the_built_rows(self):
        rows = self._ability_rows(5)
        KM._dash_problems(rows)                        # 前置 42 / param_id / 抵消公式
        dash = [r for r in rows if r[ABILITY_DURING_CONTENT_COL] == "422"]
        self.assertEqual(len(dash), 2)
        for row in dash:
            self.assertEqual(row[6], "42", "422 只在他当队长时生效，靠前置 42 隔离")
            self.assertEqual(row[118], "0", "param_id 0 必须显式写，留空 = 声明即必填闸门报错")

    def test_during_134_puller_contract_on_the_built_rows(self):
        """换 kind 必须重查 puller，否则 parseAt98 → 角色页 C7050。"""
        seen = 0
        for slot in (2, 3):
            for row in self._ability_rows(slot):
                if row[97] != "134":
                    continue
                self.assertEqual(row[98], "0", f"slot {slot} during 134 puller")
                self.assertEqual(row[104], KM.UID)
                seen += 1
        self.assertEqual(seen, 4)

    def test_unique_condition_row(self):
        key, row = KL.unique_row(self.ctx, self.ctx.spec, 1, KM.UNIQUE_DONOR,
                                 KM.UNIQUE_CELLS, name=KM.UNIQUE_NAME)
        self.assertEqual(key, KM.UID)
        self.assertEqual(len(row), KL.UNIQUE_NCOLS)
        self.assertEqual(row[1], KM.UNIQUE_NAME)
        self.assertEqual(row[2], KM.UC_ICON_ROW)
        self.assertEqual(row[3], KM.UNIQUE_FRAMES)
        self.assertEqual(row[4], KM.UNIQUE_CAP)
        self.assertEqual(row[14], KM.CODE, "PF 语音独占 code = 自身")

    def test_aura_unique_condition_row(self):
        """「烈焰光环」：600 帧 / 1 层 / Good 方向 / overwrite_mode 0（＝重开技能刷新时长）。"""
        key, row = KL.unique_row(self.ctx, self.ctx.spec, 2, KM.AURA_UNIQUE_DONOR,
                                 KM.AURA_UNIQUE_CELLS, name=KM.AURA_UNIQUE_NAME)
        self.assertEqual(key, KM.UID_AURA)
        self.assertEqual(len(row), KL.UNIQUE_NCOLS)
        self.assertEqual(row[0], f"unique_{KM.CODE}_aura")
        self.assertEqual(row[1], KM.AURA_UNIQUE_NAME)
        self.assertEqual(row[2], KM.UC_AURA_ICON_ROW)
        self.assertEqual(row[3], str(KM.AURA_FRAMES), "时长与光环寿命同源")
        self.assertEqual(row[4], "1", "上限 1 层")
        self.assertEqual(row[11], "0", "condition_direction 0 = Good（增益），写别的值直接 C7050")
        self.assertEqual(row[12], "0",
                         "overwrite_mode 0 + 上限 1 ⇒ ChooseOneWithLongerRemainingTime = 刷新时长")
        self.assertEqual(row[14], "(None)", "不替换 PF 语音角色")

    def test_the_new_leader_row_renders_and_is_legal(self):
        donor, source, cells, expect = next(
            item for item in KM.LEADER if "追加连击" in item[3])
        row, evidence = KL.build_row(self.ctx, "leader_ability", donor, cells,
                                     source=source, element=0, expect_describe=expect,
                                     label="aura-combo")
        self.assertEqual(evidence["describe"], expect)
        self.assertEqual(evidence["capabilities"], [],
                         "这一行不需要任何客户端补丁（前置/触发/内容都是官方已解析的 kind）")
        self.assertEqual(row[3], "0", "触发模式 0 = 瞬发")
        self.assertEqual(row[4], "188")
        self.assertEqual(row[10], KM.UID_AURA)
        self.assertEqual(row[25], "6", "触发 6 = BallFlip（弹板弹球），不是强化弹射")
        self.assertEqual((row[28], row[29]), ("100000", "100000"))
        self.assertEqual(row[32], "(None)", "无触发次数上限")
        self.assertEqual(row[33], "0", "无冷却")
        self.assertEqual(row[LEADER_CONTENT_COL], "226", "内容 226 AddCombo")
        self.assertEqual((row[49], row[50]), ("3500000", "3500000"))
        self.assertEqual(row[46], "", "226 的 target 列留空 = 自身（官方 221004#2/131005#4 同形）")
        self.assertEqual(row[11], "0", "前置 2/3 不用")
        self.assertEqual(row[18], "0")

    def test_the_precondition_and_content_kinds_have_official_leader_precedents(self):
        """落表判据：这一行用到的三个 kind 必须都能在官方**队长表**里找到先例。

        对照组同时统计 187 —— 它在队长表是 0 行（所以前置才改用 188）。
        """
        official = self.ctx.official_flat(KL.LEADER)
        pre = {"187": 0, "188": 0}
        trigger6 = content226 = 0
        for value in official.values():
            for row in core.read_csv_lines(value):
                cell = (lambda i: (row[i] if i < len(row) else "").strip())
                if cell(3) != "0":
                    continue
                for col in (4, 11, 18):
                    if cell(col) in pre:
                        pre[cell(col)] += 1
                trigger6 += cell(25) == "6"
                content226 += cell(LEADER_CONTENT_COL) == "226"
        self.assertEqual(pre["187"], 0, "若 187 在队长表出现了先例，可以把前置换回 187")
        self.assertGreaterEqual(pre["188"], 6, "188 在队长表的先例")
        self.assertGreaterEqual(trigger6, 5, "触发 6 BallFlip 在队长表的先例")
        self.assertGreaterEqual(content226, 12, "内容 226 AddCombo 在队长表的先例")

    def test_only_the_dash_rows_need_a_client_patch(self):
        caps = set()
        for slot, records in KM.PLAN.items():
            for donor, source, cells, _expect in records:
                _row, evidence = KL.build_row(self.ctx, "ability", donor, cells,
                                              source=source, element=0)
                caps.update(evidence["capabilities"])
        for donor, source, cells, _expect in KM.LEADER:
            _row, evidence = KL.build_row(self.ctx, "leader_ability", donor, cells,
                                          source=source, element=0)
            caps.update(evidence["capabilities"])
        self.assertEqual(sorted(caps), ["dash-parameter-v1"])
        self.assertIn("panel-description-override-v2", KM.SPEC["required_capabilities"])

    def test_custom_ability_string_keys_are_free_officially(self):
        official = self.ctx.official_flat(KL.CAS)
        for key in KM.CAS_TEXTS:
            self.assertNotIn(key, official)


@unittest.skipUnless(_LIVE, "requires live store and .cdn/cn official archives")
class SkillTreeIntegrationTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ctx = _ReadOnlyCtx()
        cls.families = _stub_families()

    def _effects(self, tree):
        return list(wf_dsl.iter_dsl_commands(tree, "ShowEffect"))

    def _assert_no_cd_coordsys(self, tree):
        """CD 的 getDirCD() 在球/敌人/角色上都是 throw ⇒ U_4f5401。

        EF 只有 Mate(-33) 会抛：``BallImpl.getDirEF()`` 返回球的飞行角，
        官方赛达 ``zeta$zeta_1`` 就是 ``(-18, ["EF"])``，所以球上允许 EF。
        """
        for show in self._effects(tree):
            self.assertIn(show[6][0], ("AB", "GH", "EF"), show[1])
            if show[3] in (-18,) or show[3] >= 0:
                self.assertNotEqual(show[6][0], "CD", show[1])
            if show[3] == -33:
                self.assertIn(show[6][0], ("AB", "GH"), show[1])

    def test_main_tree_merges_the_aura_ring(self):
        for level in ("1", "2"):
            with self.subTest(level=level):
                tree, meta = KM.build_main_tree(self.ctx, level, self.families)
                self.assertEqual(tree[10], 0, "根头 buffTargetAs=0 ⇒ 按技能伤害结算")
                ids = KM._declared_ids(tree)
                self.assertEqual(len(ids), len(set(ids)))
                self.assertEqual(sorted(ids), [0, 1, 2, 3, 4, 5, *KM.AURA_BINDS])
                scale, radius, mult = KM.AURA_TUNING[level]
                self.assertEqual(meta["aura"], {
                    "scale": scale, "radius": radius, "multiplier": mult,
                    "ring_diameter_px": round(KM.AURA_RING_PX_PER_SCALE * scale, 1),
                    "hit_interval": KM.AURA_HIT_INTERVAL, "max_hits": KM.AURA_MAX_HITS,
                    "lifetime": KM.AURA_FRAMES, "binds": list(KM.AURA_BINDS)})
                self.assertEqual(wf_dsl.player_side_dsl_problems(tree), [])
                self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)
                self._assert_no_cd_coordsys(tree)

    def _aura_marks(self, tree):
        return [c for c in wf_dsl.iter_dsl_commands(tree, "CreateCondition")
                if c[2] and isinstance(c[2][0], list) and c[2][0][0] == "ACUnique"]

    def test_main_tree_marks_the_aura_state_on_self(self):
        """光环出现时给自身付「烈焰光环」——队长技那一行就是靠它判定「持有光环」。"""
        for level in ("1", "2"):
            with self.subTest(level=level):
                tree, meta = KM.build_main_tree(self.ctx, level, self.families)
                marks = self._aura_marks(tree)
                self.assertEqual(len(marks), 1, "整棵树只许有这一条固有付与")
                mark = marks[0]
                self.assertEqual(len(mark), 13, "CreateCondition 12 参，多一格少一格都是签名漂移")
                self.assertEqual(mark[1], -17, "主体 -17 = 自身（内置绑定，不吃 lookup）")
                self.assertEqual(mark[10], KM.AURA_MARK_TARGET_KIND,
                                 "下标 10 付与对象种类；错配 = 施法 C16102")
                node = mark[2][0]
                self.assertEqual(node[0], "ACUnique")
                self.assertEqual(node[1], int(KM.UID_AURA))
                self.assertEqual(node[2], [{"min": KM.AURA_MARK_STACKS,
                                            "max": KM.AURA_MARK_STACKS}],
                                 "ACUnique 第二参是层数，不是帧数")
                self.assertEqual(meta["aura_mark"]["duration_frames"], KM.AURA_FRAMES)
                self.assertEqual(meta["aura_mark"]["duration_frames"],
                                 meta["aura"]["lifetime"], "状态时长与光环寿命必须同源")

    def test_the_aura_mark_sits_with_the_ring_not_somewhere_else(self):
        """付与节点必须紧跟在光环判定区后面：搬走就会出现「环在、状态不在」的错位。"""
        tree, _meta = KM.build_main_tree(self.ctx, "2", self.families)
        root = tree[11][1]
        names = [node[1][0] for node in root]
        area_at = next(i for i, node in enumerate(root)
                       if node[1][0] == "CreateHitArea" and node[1][19] == KM.AURA_BINDS[0])
        self.assertEqual(names[area_at + 1], "CreateCondition", names)
        self.assertEqual(root[area_at + 1][1][2][0][1], int(KM.UID_AURA))
        self.assertEqual(names[area_at - 1], "ShowEffect")

    def test_the_aura_mark_is_the_official_command_except_for_the_two_knobs(self):
        """整条克隆官方 psycho_reaper_meteor23 的自身付与：除固有 id 与层数外一格不许漂。"""
        donor = self.ctx.template_dsl(KM.AURA_MARK_DONOR)
        official = next(c for c in wf_dsl.iter_dsl_commands(donor, "CreateCondition")
                        if c[2] and isinstance(c[2][0], list) and c[2][0][0] == "ACUnique")
        self.assertEqual(official[2][0][1], KM.AURA_MARK_DONOR_UID, "母本固有 id 漂了")
        mark, _meta = KM.aura_mark(self.ctx)
        command = mark[1]
        self.assertEqual(len(command), len(official))
        for index in range(len(official)):
            if index == 2:
                continue
            self.assertEqual(command[index], official[index], f"p{index} 漂了")

    def test_chase_tree_never_refreshes_the_aura_state(self):
        """629 追击不创建光环 ⇒ 也不许刷新它，否则 PF 命中就能无限续时长。"""
        tree, _meta = KM.build_chase_tree(self.ctx, self.families)
        self.assertEqual(self._aura_marks(tree), [])

    def test_main_tree_keeps_the_template_slash_untouched(self):
        expected = {"1": 28.0, "2": 42.0}
        for level in ("1", "2"):
            _tree, meta = KM.build_main_tree(self.ctx, level, self.families)
            self.assertEqual(float(meta["slash"]["max"]), expected[level])
            self.assertEqual(meta["slash"]["alv_min"], 1.75)
            self.assertEqual(meta["slash"]["alv_max"], 3.5)

    def test_enhanced_form_really_widens_the_ring(self):
        low, high = KM.AURA_TUNING["1"], KM.AURA_TUNING["2"]
        self.assertGreater(high[0], low[0], "536 换形态后光环范围必须真的变大")
        self.assertGreater(high[1], low[1])
        self.assertGreater(high[2], low[2])

    def test_aura_block_drops_the_element_tolerance_and_foreign_hit_effect(self):
        tree, _meta = KM.build_main_tree(self.ctx, "2", self.families)
        area = next(a for a in wf_dsl.iter_dsl_commands(tree, "CreateHitArea")
                    if a[19] == KM.AURA_BINDS[0])
        self.assertEqual(area[24], 0, "写 4 = 按直击算，整块乘区被跳过")
        self.assertEqual(
            [c[0] for c in wf_dsl.iter_dsl_commands(area[23], "CreateCondition")], [],
            "目标面板没有火耐性↓这一条")
        cna = next(iter(wf_dsl.iter_dsl_commands(area[23], "CreateNormalAttack")))
        self.assertEqual(cna[15], ["Fine"], "命中特效用引擎内置件 ⇒ 只需克隆 _aura")
        self.assertEqual(cna[1], KM.AURA_BINDS[2])

    def test_aura_block_is_the_official_block_except_for_the_listed_knobs(self):
        """「碰到光圈不掉血」的排查基线：逐参对齐官方魏虎原块，只允许这几格不同。

        允许不同的格（都写在 kit 常量里）：p9 判定圆、p13 寿命、p14 命中间隔、p15 每目标上限、
        p19/p21/p22 绑定 id、p23 命中块（去掉火耐性行 + 换倍率/命中特效）。
        其余 19 格（尤其是 p2 挂球、p7 跟随球、p24 伤害归属 0）一格都不许漂。
        """
        donor = self.ctx.template_dsl(KM.AURA_DONOR)
        official = next(c for c in wf_dsl.iter_dsl_commands(donor, "CreateHitArea")
                        if c[2] == -18)
        tunable = {9, 13, 14, 15, 19, 21, 22, 23}
        for level in ("1", "2"):
            tree, _meta = KM.build_main_tree(self.ctx, level, self.families)
            area = next(a for a in wf_dsl.iter_dsl_commands(tree, "CreateHitArea")
                        if a[19] == KM.AURA_BINDS[0])
            self.assertEqual(len(area), len(official), "26 参判定区的参数个数必须一致")
            for index in range(len(official)):
                if index in tunable:
                    continue
                self.assertEqual(area[index], official[index],
                                 f"lv{level} 判定区 p{index} 漂了：{area[index]!r}")
            self.assertEqual(area[2], -18, "判定区挂球")
            self.assertEqual(area[3], ["AB"])
            self.assertEqual(area[7], True, "trackingPos：每帧重取球的位置")
            self.assertEqual(area[24], 0, "0 = 按 createdBy 标志算 ⇒ 技能伤害")
            self.assertEqual(area[13], ["SpecifyHitAreaLifetimeDirectly", KM.AURA_FRAMES])
            self.assertEqual(area[14], ["SpecifyMinHitIntervalDirectly", KM.AURA_HIT_INTERVAL])
            self.assertEqual(area[15], ["Some", [{"min": KM.AURA_MAX_HITS,
                                                  "max": KM.AURA_MAX_HITS}]])
            self.assertEqual(area[9], ["Circle", [{"min": KM.AURA_RADIUS[level],
                                                   "max": KM.AURA_RADIUS[level]}]])
            hits = [c[1][0] for c in area[23][1]]
            self.assertEqual(hits, ["ShakeCamera", "CreateNormalAttack"],
                             "命中块只剩摄像机抖 + 一发技能伤害")
            self.assertEqual(area[23][1][1][1][1], area[22],
                             "CNA 的目标位必须是判定区 p22 绑定，否则 lookup 拿不到被打中的敌人")
            ring = next(s for s in self._effects(tree) if s[1] == "aura_ring")
            self.assertEqual((ring[3], ring[6]), (-18, ["AB"]), "光圈挂球、绝对坐标（官方原样）")
            self.assertEqual(ring[5], ["SpecifyEffectLifetimeDirectly", KM.AURA_FRAMES],
                             "演出寿命必须与判定区寿命同值，否则看得见的环比判定活得久")
            drawn = KM.AURA_RING_PX_PER_SCALE * ring[12][1][0]["max"] / 2
            self.assertLess(abs(drawn - KM.AURA_RADIUS[level]), 2.0,
                            "环画出来的半径必须等于判定半径")

    def test_main_tree_only_references_official_or_cloned_effects(self):
        for level in ("1", "2"):
            tree, _meta = KM.build_main_tree(self.ctx, level, self.families)
            paths = {str(s[2][1]) for s in self._effects(tree)}
            self.assertIn(KM.AURA, paths)
            for path in paths:
                self.assertTrue(
                    path.startswith(f"battle/effect/skill_unique/{KM.TEMPLATE_CODE}/")
                    or path.startswith(f"battle/effect/skill_unique/{KM.CODE}/"), path)

    def test_chase_tree(self):
        tree, meta = KM.build_chase_tree(self.ctx, self.families)
        self.assertEqual(tree[10], 0, "629 以 AbilitySkill 执行 ⇒ 自动按技能伤害结算")
        attacks = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
        self.assertEqual(len(attacks), 1)
        self.assertEqual((attacks[0][6][0]["min"], attacks[0][6][0]["max"]),
                         (KM.CHASE_MULT, KM.CHASE_MULT))
        names = sorted(show[1] for show in self._effects(tree))
        self.assertEqual(names, ["ignite_aura", "ignite_burst"])
        aura = next(s for s in self._effects(tree) if s[1] == "ignite_aura")
        self.assertEqual(aura[2][1], KM.FLAME, "球身光环留母本件，图集零增量")
        self.assertEqual(aura[5], ["PlayOnlyFirstSequence"], "母本 _flame 是 once/70 帧")
        burst = next(s for s in self._effects(tree) if s[1] == "ignite_burst")
        self.assertEqual(burst[2][1], KM.CLARISSE)
        # 反馈轮 2 复核补漏：爆炸素材只有一份，寿命必须与 722 那三棵树同一个数。
        self.assertEqual(burst[5], ["SpecifyEffectLifetimeDirectly", KM.PF_HIT_WINDOW])
        self.assertEqual(burst[12], ["Some", [{"min": KM.BURST_SCALE, "max": KM.BURST_SCALE}]])
        self.assertEqual(meta["burst_radius"], KM.BURST_RADIUS)
        self.assertEqual(wf_dsl.player_side_dsl_problems(tree), [])
        self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)
        self._assert_no_cd_coordsys(tree)

    def test_chase_down_per_activation_is_at_most_one(self):
        """2026-09-27 第二批覆盖（口径 B3/B6，wf_balance_20260927b_magnus）：追击 CT 0.6 秒 ⇒ 每次削韧 ≤1。

        第一批输出 = 母本 p13 0.25 × 5 段 = 1.25；只改 p13 → 0.2（5 × 0.2 = 1.0 = 母本 4 × 0.25），
        p14 Fever 点、倍率、段数一格不动。
        """
        tree, meta = KM.build_chase_tree(self.ctx, self.families)
        cna = next(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
        donor = self.ctx.template_dsl(KM.CHASE_DONOR)
        d_cna = next(wf_dsl.iter_dsl_commands(donor, "CreateNormalAttack"))
        self.assertEqual(d_cna[13], [{"min": KM.CHASE_DOWN_DONOR, "max": KM.CHASE_DOWN_DONOR}], "母本 p13 漂了")
        self.assertEqual(cna[13], [{"min": KM.CHASE_DOWN, "max": KM.CHASE_DOWN}])
        self.assertEqual(cna[14], d_cna[14], "p14 Fever 点跟母本")
        self.assertEqual(meta["down"], {"per_hit": 0.2, "hits": 5, "per_activation": 1.0})
        self.assertLessEqual(meta["down"]["per_activation"], KM.CHASE_DOWN_CAP)
        chase_row = next(c for _d, _s, c, _e in KM.PLAN[3] if c.get(71) == KM.CHASE_PROGRAM)
        self.assertLessEqual(int(chase_row[35]), 180, "触发 CT ≤3 秒 ⇒ 口径 B3 的 ≤1 档")
        from unittest import mock
        with mock.patch.object(KM, "CHASE_DOWN_DONOR", 0.3):
            with self.assertRaises(KM.KitError):
                KM.build_chase_tree(self.ctx, self.families)
        with mock.patch.object(KM, "CHASE_DOWN", 0.25):
            with self.assertRaises(KM.KitError):
                KM.build_chase_tree(self.ctx, self.families)

    def test_chase_burst_is_pinned_to_the_hit_point(self):
        tree, _meta = KM.build_chase_tree(self.ctx, self.families)
        points = list(wf_dsl.iter_dsl_commands(tree, "CreateReferencePoint"))
        self.assertTrue(points, "爆炸必须挂在命中那一帧快照出来的固定点上，否则跟着球跑")
        self.assertTrue(any(p[1] == -18 and p[2] == ["AB"] for p in points))
        radii = sorted(a[9][1][0]["max"] for a in wf_dsl.iter_dsl_commands(tree, "CreateHitArea"))
        self.assertIn(KM.BURST_RADIUS, radii)

    def test_chase_burst_anchor_lives_exactly_as_long_as_the_burst(self):
        """反馈轮 2 复核补漏的根因判定：官方母本「参考点 == 演出寿命」，反馈轮 1 只抬了后者。"""
        tree, meta = KM.build_chase_tree(self.ctx, self.families)
        donor = self.ctx.template_dsl(KM.CHASE_DONOR)
        d_points = list(wf_dsl.iter_dsl_commands(donor, "CreateReferencePoint"))
        self.assertEqual([p[9] for p in d_points], [KM.CHASE_BURST_RP_DONOR],
                         "母本参考点寿命漂移 ⇒ 这一轮的判据要重算")
        d_burst = next(s for s in wf_dsl.iter_dsl_commands(donor, "ShowEffect")
                       if not str(s[2][1]).endswith("_player"))
        self.assertEqual(d_burst[5], ["SpecifyEffectLifetimeDirectly", KM.CHASE_BURST_RP_DONOR],
                         "官方这一组三个数恒等：参考点 / 演出 / 判定区都是 30")

        burst = next(s for s in self._effects(tree) if s[1] == "ignite_burst")
        point = next(p for p in wf_dsl.iter_dsl_commands(tree, "CreateReferencePoint")
                     if p[10] == burst[3])
        self.assertEqual(point[9], KM.PF_HIT_WINDOW, "锚点不抬 ⇒ 爆炸照样被连坐提前终止")
        self.assertEqual(burst[5][1], point[9], "官方形状：参考点寿命 == 演出寿命")
        self.assertEqual(meta["burst_window"],
                         {"bind": burst[3], "donor": KM.CHASE_BURST_RP_DONOR,
                          "frames": KM.PF_HIT_WINDOW,
                          "hit_area": KM.CHASE_BURST_HIT_LIFETIME})

        # 伤害闸不许跟着走：判定区寿命与每目标上限必须留在母本值上
        area = next(a for a in wf_dsl.iter_dsl_commands(tree, "CreateHitArea")
                    if a[2] == burst[3])
        self.assertEqual(area[13],
                         ["SpecifyHitAreaLifetimeDirectly", KM.CHASE_BURST_HIT_LIFETIME],
                         "判定区寿命是伤害节流闸，改它就是改伤害")
        self.assertEqual(area[14], ["CalculatedUsingMaxNumOfHits", KM.BURST_MAX_HITS])

    def test_every_clarisse_user_shares_one_lifetime(self):
        """切 `end` 段改的是**素材本身** ⇒ 判据必须覆盖全部使用者，不能只盯 PF 三棵树。

        这条就是复核员抓到的那个漏网使用者的回归闸：629 追击树曾停在 79 帧没人发现。
        """
        trees = {"ignite": KM.build_chase_tree(self.ctx, self.families)[0]}
        for level in (1, 2, 3):
            trees[f"pf{level}"] = KM.build_pf_tree(self.ctx, level, self.families)[0]
        for level in ("1", "2"):
            trees[f"skill{level}"] = KM.build_main_tree(self.ctx, level, self.families)[0]
        seen = 0
        for name, tree in trees.items():
            with self.subTest(tree=name):
                KM.burst_window_problems(name, tree)          # 闸门本体
                for use in KM.burst_users(tree):
                    seen += 1
                    self.assertEqual(use["lifetime"],
                                     ["SpecifyEffectLifetimeDirectly", KM.PF_HIT_WINDOW])
        self.assertEqual(seen, 4, "克拉莉丝共 4 个使用者：629 追击 + 三档 PF")
        loop = next(s for s in KM.CLARISSE_SEQUENCES if s["kind"] == "loop")
        self.assertLess(int(loop["begin"]), KM.PF_HIT_WINDOW)
        self.assertLess(KM.PF_HIT_WINDOW, int(loop["end"]),
                        "寿命必须落在 loop 段内部：到了 end 边界就会多播一遍尾巴")
        self.assertLess(KM.PF_HIT_WINDOW, KM.CLARISSE_NEW_T,
                        "写 CLARISSE_NEW_T(79) 就会绕回 loop 段重播 —— 复核员抓到的正是这个")

    def test_burst_window_gate_rejects_a_stale_user(self):
        """删判定断言：把任意一个使用者退回 79 帧，闸门必须报错。"""
        tree, _meta = KM.build_chase_tree(self.ctx, self.families)
        KM.burst_window_problems("ignite", tree)              # 基线绿
        burst = next(s for s in self._effects(tree) if s[1] == "ignite_burst")
        burst[5] = ["SpecifyEffectLifetimeDirectly", KM.CLARISSE_NEW_T]
        with self.assertRaises(KM.KitError):
            KM.burst_window_problems("ignite", tree)
        burst[5] = ["SpecifyEffectLifetimeDirectly", KM.PF_HIT_WINDOW]
        point = next(p for p in wf_dsl.iter_dsl_commands(tree, "CreateReferencePoint")
                     if p[10] == burst[3])
        point[9] = KM.CHASE_BURST_RP_DONOR
        with self.assertRaises(KM.KitError):
            KM.burst_window_problems("ignite", tree)

    def test_power_flip_trees(self):
        for level in (1, 2, 3):
            with self.subTest(level=level):
                raw = self.ctx.official_read(wf_dsl.dsl_logical(KM.SPECIAL_PROGRAMS[level]))
                self.assertEqual(hashlib.sha256(raw).hexdigest(), KM.SPECIAL_SHA[level],
                                 "官方 special 底座漂移 ⇒ 倍率要重算")
                tree, meta = KM.build_pf_tree(self.ctx, level, self.families)
                self.assertEqual(tree[1], 1, "追踪树不带 StopBall ⇒ 优先级保持 1")
                self.assertEqual(tree[10], 0)
                suppress = list(wf_dsl.iter_dsl_commands(tree, "SetPowerFilpSuppress"))
                self.assertEqual(suppress[0][1], KM.PF_SUPPRESS)
                self.assertTrue(list(wf_dsl.iter_dsl_commands(tree, "NotifyPowerflipEnd")),
                                "空场也一定要收尾，否则 PF 卡死")
                for area in wf_dsl.iter_dsl_commands(tree, "CreateHitArea"):
                    self.assertEqual(area[24], 0)
                    self.assertEqual(area[9][1][0]["max"], KM.BURST_RADIUS)
                self.assertEqual(wf_dsl.player_side_dsl_problems(tree), [])
                self.assertEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))["tree"], tree)
                self._assert_no_cd_coordsys(tree)
                self.assertIsNone(meta["chase"], "反馈轮 1：不再追踪 boss")

    def test_power_flip_keeps_the_native_trajectory(self):
        """去追踪：弹道必须回到官方 special 底座（删判定用的反向断言）。"""
        for level in (1, 2, 3):
            tree, meta = KM.build_pf_tree(self.ctx, level, self.families)
            base = self.ctx.template_dsl(KM.SPECIAL_PROGRAMS[level])
            for name in ("MoveBall", "FindNearSubjects", "RemoveEvent", "Repeat"):
                # 底座自带一条 RemoveEvent("ヒット判定") ⇒ 判据是与底座同名同数
                actual = [c for c in wf_dsl.iter_dsl_commands(tree, name)
                          if not (name == 'RemoveEvent' and str(c[1]).startswith('magnus_kyon_orbit_'))]
                self.assertEqual(len(actual),
                                 len(list(wf_dsl.iter_dsl_commands(base, name))),
                                 f"lv{level} 的 {name} 条数与官方底座不一致")
            self.assertEqual([n for n in tree[11][1]
                              if n[0] == "Event" and n[1][0] == "Repeat"], [])
            self.assertEqual(meta["extra_effects"], [])
            base = self.ctx.template_dsl(KM.SPECIAL_PROGRAMS[level])
            from wf_magnus_pf_orbit import NAME
            self.assertEqual([n[1][0] for n in tree[11][1]
                              if not (n[0] == 'Command' and n[1][0] == 'ShowEffect' and str(n[1][1]).startswith(NAME))
                              and not (n[0] == 'Event' and n[1][0] == 'Wait' and str(n[1][2]).startswith(NAME))],
                             [n[1][0] if n[0] == "Command" else n[1][0] for n in base[11][1]],
                             f"lv{level} root 命令序列必须和官方底座逐条对齐")

    def test_power_flip_tiers_are_one_cone_that_grows(self):
        totals, fx, scales = [], [], []
        for level in (1, 2, 3):
            tree, meta = KM.build_pf_tree(self.ctx, level, self.families)
            totals.append(meta["total"])
            fx.append({str(s[2][1]) for s in self._effects(tree)})
            lance = [s for s in self._effects(tree) if str(s[2][1]) == KM.ZETA_LANCE]
            self.assertEqual(len(lance), 1, "只留一层锥形")
            self.assertEqual(lance[0][3], -18)
            self.assertEqual(lance[0][6], ["EF"], "朝球的飞行方向，AB 会恒定朝上")
            self.assertEqual(lance[0][10:12], [True, True], "位置和朝向都必须持续跟随小人")
            scales.append(lance[0][12][1][0]["max"])
            del tree
        self.assertEqual(totals, sorted(totals), "三档逐渐增强")
        self.assertEqual(scales, [KM.PF_LANCE_SCALE[n] for n in (1, 2, 3)])
        self.assertEqual(scales, sorted(scales))
        self.assertEqual(fx[0], fx[1], "不再按档位叠加别的基名")
        self.assertEqual(fx[1], fx[2])
        for names in fx:
            from wf_magnus_pf_orbit import EFFECT
            self.assertEqual(names, {KM.ZETA_LANCE, KM.ZETA_LANCE_END, KM.CLARISSE, EFFECT},
                             "zeta_lance_hit（26 颗方块的主场）不许再出现")
        self.assertIn(KM.ZETA_LANCE, fx[0])

    def test_hit_window_is_retimed_on_all_three_knobs(self):
        """反馈轮 2 根因①：79 帧的爆炸塞进 20/30 帧的参考点 ⇒ 满强度那一帧被连坐删掉。"""
        for level in (1, 2, 3):
            with self.subTest(level=level):
                tree, meta = KM.build_pf_tree(self.ctx, level, self.families)
                body = KM._collision_body(tree)
                suppress = [n[1][1] for n in body
                            if n[0] == "Command" and n[1][0] == "SetPowerFilpSuppress"]
                waits = [n[1][1] for n in body if n[0] == "Event" and n[1][0] == "Wait"]
                points = list(wf_dsl.iter_dsl_commands(tree, "CreateReferencePoint"))
                self.assertEqual(suppress, [KM.PF_HIT_WINDOW])
                self.assertEqual(waits, [KM.PF_HIT_WINDOW - 2], "Wait 官方恒等 suppress−2")
                self.assertEqual([p[9] for p in points], [KM.PF_HIT_WINDOW])
                burst = [s for s in self._effects(tree) if str(s[2][1]) == KM.CLARISSE]
                self.assertEqual(len(burst), 1)
                self.assertEqual(burst[0][5], ["SpecifyEffectLifetimeDirectly", KM.PF_HIT_WINDOW],
                                 "演出寿命必须和参考点寿命相等（官方 5/5 例都相等）")
                self.assertEqual(burst[0][3], points[0][10], "爆炸挂的就是这个参考点")
                self.assertEqual(meta["hit_window"],
                                 {"donor": KM.PF_HIT_WINDOW_DONOR[level],
                                  "frames": KM.PF_HIT_WINDOW, "wait": KM.PF_HIT_WINDOW - 2})
                # 伤害窗口不许被这次改动挪动：两块判定区还是底座的 13+6 / 22+7
                base = self.ctx.template_dsl(KM.SPECIAL_PROGRAMS[level])
                self.assertEqual([a[13] for a in wf_dsl.iter_dsl_commands(tree, "CreateHitArea")],
                                 [a[13] for a in wf_dsl.iter_dsl_commands(base, "CreateHitArea")],
                                 "命中窗口只放长演出，不许顺手改判定区寿命")

    def test_lance_gets_an_explicit_ending_right_after_hide_effect(self):
        """反馈轮 2 根因②：HideEffect 把锥形硬删，而 zeta_lance 没有 `end` 段可跳＝立删。"""
        for level in (1, 2, 3):
            with self.subTest(level=level):
                tree, meta = KM.build_pf_tree(self.ctx, level, self.families)
                body = KM._collision_body(tree)
                names = [n[1][1] if n[1][0] in ("HideEffect", "ShowEffect") else n[1][0]
                         for n in body]
                self.assertEqual(names[:2], [KM.LANCE_FX_NAME, KM.LANCE_END_FX_NAME],
                                 "收尾必须紧跟在 HideEffect 后面，中间不许插别的命令")
                end = [s for s in self._effects(tree) if str(s[2][1]) == KM.ZETA_LANCE_END]
                self.assertEqual(len(end), 1)
                show = end[0]
                self.assertEqual(show[3], -18, "球的位置（官方赛达也是 -18）")
                self.assertEqual(show[5], ["PlayOnlyFirstSequence"], "官方 zeta$zeta_1 同写法")
                self.assertEqual(show[6], ["EF"], "收尾要和锥形同朝向")
                self.assertEqual([show[10], show[11]], [False, False],
                                 "tracking 两关＝创建帧快照；开着的话球一没这 32 帧就跟着没")
                self.assertEqual(show[12][1][0]["max"], KM.PF_LANCE_SCALE[level],
                                 "收尾要和本档锥形一样大")
                self.assertEqual(meta["lance_end"]["frames"], KM.LANCE_END_FRAMES)

    def test_lance_hex_rects_are_erased_and_nothing_else_is(self):
        """黄/橙六边形按图集 rect 擦成全透明；擦之前先证明它不和保留的 rect 相交。"""
        import wf_seasonal7_common as C
        boxes = KM.lance_hex_boxes(self.ctx)
        self.assertEqual(sorted(boxes), sorted(KM.LANCE_HEX_LEAVES))
        src_dir = dict((sub, src) for sub, src, _n in KM.FX_CLONES)[KM.LANCE_END_SUBDIR]
        sheet = self.ctx.png_open(
            self.ctx.pack.template_asset(f"{src_dir}/zeta.png")[1]).convert("RGBA")
        out = KM.lance_png_transform(self.ctx, None)(sheet)
        self.assertEqual(out.size, sheet.size, "擦图不许改画布")
        for leaf, box in boxes.items():
            self.assertEqual(max(p[3] for p in out.crop(box).getdata()), 0, leaf)
            self.assertGreater(max(p[3] for p in sheet.crop(box).getdata()), 0,
                               f"{leaf} 母本本来就是空的？那断言没在判东西")
        atlas = self.ctx.amf_parse(
            self.ctx.pack.template_asset(f"{src_dir}/zeta.atlas.amf3.deflate")[1])
        kept = 0
        for item in atlas:
            leaf = "/".join(str(item["n"]).split("/")[-2:])
            base = leaf.split("/")[0]
            if leaf in KM.LANCE_HEX_LEAVES or base not in ("zeta_lance", "zeta_lance_end"):
                continue
            box = (item["x"], item["y"], item["x"] + item["w"], item["y"] + item["h"])
            self.assertEqual(list(out.crop(box).getdata()), list(sheet.crop(box).getdata()), leaf)
            kept += 1
        self.assertGreaterEqual(kept, 19, "保留的 rect 少了说明族名判错了")
        self.assertEqual(C.sha256(C.png_store_bytes(out)) == C.sha256(C.png_store_bytes(sheet)),
                         False, "擦了就必须和母本不同字节")


@unittest.skipUnless(PKG_COMMON.is_dir(), "requires a rebuilt ma-magnus workspace")
class PackageIntegrationTests(unittest.TestCase):
    """成品包层：PF 三档、克隆族、克拉莉丝裁段都真的落进了包（漏建本体树会静默用旧版）。"""

    @classmethod
    def setUpClass(cls):
        import wf_seasonal7_common as C
        cls.C = C

    def _tree(self, program: str):
        return self.C.amf_parse((PKG_COMMON / wf_dsl.dsl_logical(program)).read_bytes())

    def test_power_flip_action_row_points_at_the_three_programs(self):
        table = core.read_orderedmap_file_from_bytes(
            (PKG_COMMON / KM.PFA).read_bytes())
        self.assertIn(KM.PF_KEY, table)
        row = list(core.read_csv_lines(table[KM.PF_KEY]))[0]
        self.assertEqual(list(row), list(KM.PF_PROGRAMS))

    def test_all_six_trees_are_in_the_package(self):
        for program in (*(f"battle/action/skill/action/rare5/{KM.CODE}${KM.CODE}_{n}"
                          for n in (1, 2)), KM.CHASE_PROGRAM, *KM.PF_PROGRAMS):
            self.assertTrue((PKG_COMMON / wf_dsl.dsl_logical(program)).is_file(), program)

    def test_cloned_effect_families_are_in_the_package(self):
        for subdir, _src, names in KM.FX_CLONES:
            base = PKG_COMMON / f"battle/effect/skill_unique/{KM.CODE}/{subdir}"
            self.assertTrue((base / f"{subdir}.png").is_file(), subdir)
            self.assertTrue((base / f"{subdir}.atlas.amf3.deflate").is_file(), subdir)
            for name in names:
                self.assertTrue((base / f"{name}.parts.amf3.deflate").is_file(), name)

    def test_clarisse_only_plays_its_end_burst(self):
        base = PKG_COMMON / f"battle/effect/skill_unique/{KM.CODE}/burst"
        parts = self.C.amf_parse((base / "clarisse.parts.amf3.deflate").read_bytes())
        timeline = self.C.amf_parse((base / "clarisse.timeline.amf3.deflate").read_bytes())
        keyframe = parts["g"][0]["s"][0]["l"][0]
        self.assertEqual(int(keyframe["r"]), KM.CLARISSE_NEW_R)
        self.assertEqual(int(keyframe["t"]), KM.CLARISSE_NEW_T)
        self.assertEqual(int(parts["g"][0]["t"]), KM.CLARISSE_NEW_T)
        self.assertEqual(int(timeline["sequences"][-1]["end"]), KM.CLARISSE_NEW_T)
        self.assertEqual(timeline["sequences"][0]["begin"], 1)
        self.assertGreater(len(parts["g"]), 1, "g[1] 及以下一个字节都不许改")
        # 反馈轮 2：包里必须真的是 start/loop/end 三段 + 换过的爆炸音
        KM._sequence_problems(timeline["sequences"], KM.CLARISSE_NEW_T)
        self.assertEqual([s["name"] for s in timeline["sequences"]],
                         [s["name"] for s in KM.CLARISSE_SEQUENCES])
        self.assertEqual([s["path"] for s in timeline["sounds"]], [KM.BURST_SOUND])

    def test_lance_ending_is_in_the_package_without_the_yellow_hexagons(self):
        sub = KM.LANCE_END_SUBDIR
        base = PKG_COMMON / f"battle/effect/skill_unique/{KM.CODE}/{sub}"
        for kind in ("parts", "timeline"):
            self.assertTrue((base / f"zeta_lance_end.{kind}.amf3.deflate").is_file(), kind)
        old = PKG_COMMON / f"battle/effect/skill_unique/{KM.CODE}/lance/zeta_lance_end.parts.amf3.deflate"
        self.assertFalse(old.is_file(), "旧 lance/ 路径是 live 孤儿，包里不许再出现（会撞占用闸门）")
        timeline = self.C.amf_parse((base / "zeta_lance_end.timeline.amf3.deflate").read_bytes())
        parts = self.C.amf_parse((base / "zeta_lance_end.parts.amf3.deflate").read_bytes())
        self.assertEqual(int(parts["g"][0]["t"]), KM.LANCE_END_FRAMES)
        self.assertEqual(int(timeline["sequences"][-1]["end"]), KM.LANCE_END_FRAMES)
        atlas = self.C.amf_parse((base / f"{sub}.atlas.amf3.deflate").read_bytes())
        sheet = self.C.png_open((base / f"{sub}.png").read_bytes()).convert("RGBA")
        erased, kept = 0, 0
        for item in atlas:
            leaf = "/".join(str(item["n"]).split("/")[-2:])
            box = (item["x"], item["y"], item["x"] + item["w"], item["y"] + item["h"])
            top = max(p[3] for p in sheet.crop(box).getdata())
            if leaf in KM.LANCE_HEX_LEAVES:
                self.assertEqual(top, 0, f"{leaf} 还有像素 ⇒ 黄色小方框会再出现")
                erased += 1
            elif leaf.split("/")[0] in ("zeta_lance", "zeta_lance_end"):
                self.assertGreater(top, 0, f"{leaf} 被误擦了")
                kept += 1
        self.assertEqual(erased, len(KM.LANCE_HEX_LEAVES))
        self.assertGreaterEqual(kept, 19)

    def test_package_carries_both_unique_rows_and_both_icons(self):
        table = core.read_orderedmap_file_from_bytes(
            (PKG_COMMON / MS.UNIQUE_CONDITION_LOGICAL).read_bytes())
        self.assertEqual(sorted(k for k in table if k.startswith(str(KM.CID))),
                         sorted((KM.UID, KM.UID_AURA)))
        aura = list(core.read_csv_lines(table[KM.UID_AURA]))[0]
        self.assertEqual(aura[1], KM.AURA_UNIQUE_NAME)
        self.assertEqual(aura[3], str(KM.AURA_FRAMES))
        self.assertEqual(aura[4], "1")
        icons = {}
        for _key, logical, _painter in KM.UNIQUE_ICONS:
            path = PKG_COMMON / logical
            self.assertTrue(path.is_file(), logical)
            image = self.C.png_open(path.read_bytes())
            self.assertEqual(image.size, (48, 48), logical)
            icons[logical] = path.read_bytes()
        self.assertEqual(len(set(icons.values())), 2, "两枚图标在包里不能是同一份字节")

    def test_package_skill_trees_apply_the_aura_state_and_the_chase_tree_does_not(self):
        def marks(tree):
            return [c for c in wf_dsl.iter_dsl_commands(tree, "CreateCondition")
                    if c[2] and isinstance(c[2][0], list) and c[2][0][0] == "ACUnique"]

        for level in (1, 2):
            tree = self._tree(f"battle/action/skill/action/rare5/{KM.CODE}${KM.CODE}_{level}")
            # 2026-09-27 第三轮（wf_balance_20260927c_magnus）：根块包进旗号 2 分支后两侧各执行其一 ⇒ 逐支判
            # （第二批及以前的包没有分支 ⇒ gate_branches 返回整个根块，判据不变）。
            for branch in KM.gate_branches(tree):
                found = marks(branch)
                self.assertEqual([c[2][0][1] for c in found], [int(KM.UID_AURA)], f"level {level}")
                self.assertEqual(found[0][1], -17)
                self.assertEqual(found[0][10], KM.AURA_MARK_TARGET_KIND)
        self.assertEqual(marks(self._tree(KM.CHASE_PROGRAM)), [])
        for program in KM.PF_PROGRAMS:
            self.assertEqual(marks(self._tree(program)), [], program)

    def test_package_leader_table_carries_the_ball_flip_combo_row(self):
        table = core.read_orderedmap_file_from_bytes(
            (PKG_COMMON / KL.LEADER).read_bytes())
        rows = list(core.read_csv_lines(table[str(KM.CID)]))
        self.assertEqual(len(rows), len(KM.LEADER))
        row = next(r for r in rows if r[45] == "226")
        self.assertEqual((row[4], row[10], row[25], row[45], row[49]),
                         ("188", KM.UID_AURA, "6", "226", "3500000"))

    def test_package_trees_reference_only_paths_that_exist(self):
        for program in (f"battle/action/skill/action/rare5/{KM.CODE}${KM.CODE}_2",
                        KM.CHASE_PROGRAM, KM.PF_PROGRAMS[2]):
            tree = self._tree(program)
            for show in wf_dsl.iter_dsl_commands(tree, "ShowEffect"):
                path = str(show[2][1])
                if not path.startswith(f"battle/effect/skill_unique/{KM.CODE}/"):
                    continue
                self.assertTrue(
                    (PKG_COMMON / f"{path}.parts.amf3.deflate").is_file()
                    or (PKG_COMMON / f"{path}.timeline.amf3.deflate").is_file(), path)


if __name__ == "__main__":
    unittest.main()
