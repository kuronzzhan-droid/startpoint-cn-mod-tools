# -*- coding: utf-8 -*-
"""澄波响 kit（169988 ``psychic_teleport_moon``）rework1：计划自查 + 行装配 + DSL 门禁。

三组用例：

1. **纯静态**（不需要 live / 官方基线）：模块常量、``design/hibiki.json`` 的 ``plan_rework1``
   镜像互锁、裁决 §8 的计划自查（队长表禁 422/724/713、前置白名单、629 必配字符串键与动作路径、
   固有 ID 8 位与上限非 ``(None)``、c2 雕像组每键单值、during puller 契约、面板禁词），
   以及本模块补的 DSL 小工具。
2. **官方基线**（缺 ``.cdn/cn`` 或 live store 时跳过）：27 行逐行装配并与模块登记的 ``wf_describe``
   回读逐字比对；两棵技能树、三棵 722 树、一棵 629 PF 追击树的装配与门禁；固有状态图标。
3. **已构建的 workspace**（``work/character_packs/ma-hibiki`` 不存在时跳过）：包内自有键、认领、
   kit-report、DSL 程序清单、面板接管文案的 CSV 往返（多行 ``\\n`` 必须活下来）。

不写 live store / ``assets/`` / ``.cdn``，不跑发布；官方基线只读。
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

pass  # Imports resolve from this checkout/package, not external source copies.

import wf_balance_20260927b_hibiki as B2  # noqa: E402  2026-09-27 第二批平衡修订模块
import wf_balance_20260927c_hibiki as B3  # noqa: E402  2026-09-27 第三轮平衡修订模块（成长复核队长面板 + 槽2/槽4 同条件合并）
import wf_client_legality as L  # noqa: E402
import wf_midautumn_common as MC  # noqa: E402
import wf_midautumn_kit_hibiki as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_build as B  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402
import wf_seasonal7_kit_philia as PH  # noqa: E402

ROOT = core.project_root()
DESIGN = MS.load_design(ROOT, "hibiki")
WORKSPACE = ROOT / "work/character_packs/ma-hibiki"
PANEL_JSON = ROOT / "work/character_packs/midautumn-20260920/rework1/panel/hibiki.json"


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return (profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()
            and (ROOT / "work/codex_out/newchars-r2-20260906/gerald-native-pf").is_dir())


_BASELINE = _baseline_available()
_CTX = None


def ctx():
    """只读上下文：``record_sources=False`` ⇒ 母本取数不写 workspace（框架 §10.2）。"""
    global _CTX
    if _CTX is None:
        _CTX = B.KitContext(MC.MAPack(MS.get_spec("hibiki"), record_sources=False))
    return _CTX


def _batch2(fn, value):
    """「第一批输出 + 第二批覆盖」：候选包 / kit-report 还停在第二批之前时，套上第二批修订
    （``wf_balance_20260927b_hibiki`` 的纯函数）再与本模块常量比；主会话暂存脚本回写候选后
    候选本身就是第二批输出，修订函数对自身输出拒绝（ValueError）⇒ 原样返回。
    kit-report.json 是 rework1 构建证据，第二批不重建 kit（禁止重跑写包脚本），所以一直走覆盖分支。"""
    try:
        return fn(value)
    except ValueError:
        return value


def fake_family() -> dict:
    """``clone_effect_family`` 结果的只读替身（测树装配时不往包里写特效）。"""
    return {"src_dir": K.FX_SRC_DIR, "dst_dir": K.FX_DST_DIR, "donor": K.TEMPLATE_CODE,
            "dst_name": K.FX_SUBDIR, "copied_bases": [K.FX_BACK, K.FX_EF]}


def _synthetic_support_block(kinds: list[str]) -> list:
    """``strip_ac_flying`` 单元测试用的最小合成块，不依赖 ``PH.pf_support_block`` 的当前实现。"""
    def cc(kind: str) -> list:
        return ["Command", ["CreateCondition", 400, [[kind, [{"min": 60, "max": 60}]]],
                            [{"min": 1, "max": 1}], ["None"], True, False, "", None, False, 3,
                            [{"min": 1, "max": 1}], False]]
    return ["Command", ["FindAllSubjects", 400, 33, [], [], [], [], [], ["DoNothing"],
                        ["Block", [cc(k) for k in kinds]]]]


def assembled_rows():
    """27 行成品（leader 9 + ability 18），只装配不写包。"""
    leader = [KL.apply_cells(KL.donor_row(ctx(), KL.LEADER, addr, source=src), cells,
                             KL.LEADER_NCOLS)
              for addr, src, cells, _expect in K.LEADER]
    ability = {}
    for slot in range(1, 7):
        rows = []
        for addr, src, cells, _expect in K.PLAN[slot]:
            merged = {0: f"{K.CODE}_{slot}", 1: K._UNISONABLE[slot], 2: K._STATUE[slot], **cells}
            rows.append(KL.apply_cells(KL.donor_row(ctx(), KL.ABILITY, addr, source=src),
                                       merged, KL.ABILITY_NCOLS))
        ability[f"{K.CID}{slot}"] = rows
    return leader, ability


# ---------------------------------------------------------------- 1. 纯静态

class ConstantTests(unittest.TestCase):
    def test_identity_matches_the_registry(self):
        spec = MS.get_spec("hibiki")
        self.assertEqual((spec.cid, spec.code), (K.CID, K.CODE))
        self.assertEqual((spec.template_id, spec.template_code), (K.TEMPLATE_ID, K.TEMPLATE_CODE))
        self.assertEqual(spec.element, K.ELEMENT)
        self.assertEqual(spec.pf_type, 3)            # 辅助型 ⇒ 722 是硬需求（原生 Lv1/Lv2 零伤害）
        self.assertEqual(spec.stance, "Attacker")

    def test_unique_condition_id_is_eight_digits_and_uncapped(self):
        self.assertEqual(K.UID, str(K.CID * 100 + 1))
        self.assertEqual(len(K.UID), 8)
        self.assertTrue(MS.unique_condition_ok(K.CID, K.UID))
        # rework1：作者「不设置上限」= 官方写法 99；(None) 是上限 1 层，按层加成会全死
        self.assertEqual(K.UNIQUE_CAP, "99")
        self.assertNotIn(K.UNIQUE_CAP, ("", "(None)"))

    def test_spec_declares_every_self_owned_key(self):
        keys = MS.get_spec("hibiki").extra_keys
        self.assertEqual(keys[MS.UNIQUE_CONDITION_LOGICAL], (K.UID,))
        self.assertEqual(keys[K.PFA], (K.PF_KEY,))
        self.assertEqual(set(keys[KL.CAS]), set(K.CAS_TEXTS))
        self.assertEqual(len(K.CAS_TEXTS), 10)       # 722 + 两条 629 + 队长块 + 6 槽
        self.assertEqual(keys[KL.SWITCHED], (K.VOICE_KEY,))

    def test_pf_and_invoke_programs(self):
        self.assertEqual(sorted(K.SPECIAL_SHA), [1, 2, 3])
        self.assertEqual(len(K.PF_PROGRAMS), 3)
        self.assertTrue(K.INVOKE_PROGRAM.startswith("battle/action/skill/action/ability_skill/"))
        self.assertEqual(K.INVOKE_BTA, 133)            # 629 载荷按 PF 伤害结算（偏离 D-15）
        self.assertEqual(K.INVOKE_SCALE, K.PF_SCALE)  # 作者指定追加与本体 PF3 同倍率

    def test_damage_attribution_switches_are_pinned(self):
        """反馈轮 4：伤害归属的两个位，取值钉死在源码证明过的那一组。

        根头 ``tree[10]=3`` 是 ``NormalAttackCalculator.as:422`` 唯一认的开关；判定区
        ``params[23]`` 留 0 ＝ 不覆盖、回落到根头（``Environment.as:735-752``）。写 1 会退回
        技能池，写 4 会变直击 —— 这条测试就是拦这两种改法。
        """
        self.assertEqual(K.INVOKE_BTA, 133)
        self.assertNotIn(K.INVOKE_BTA, (0, 1, 2, 4))
        self.assertEqual(K.INVOKE_HITAREA_BTA, 0)

    def test_the_413_rows_that_the_629_hit_cannot_reach_are_pinned(self):
        """返修轮：面板承诺、629 追击拿不到的那 ＋55%（两行 during kind 413）钉死。

        ``NormalAttackCalculator.as:457`` 的 ``getStatModifierSeparatedTermPowerFlipDamage``
        只在 ``as:446`` 的 ``if(createdByPowerFlipAction)`` 里 ⇒ 629 载荷恒读不到；
        换成 during kind **23** 就读得到（``as:424``，在 ``as:422`` 的通用池 if 里），
        但对她真拍板的 PF 是把 ×1.55 独立乘区降级为同池相加 ＝ 平衡改动
        （施工单 §12.6 **方案 F**，需作者拍板）。

        这条测试是那次改法的闸门：谁把 413 换成 23，必须同时改面板文案
        （去掉「额外乘区」）、`damage_pools` 与施工单 —— 不能悄悄改掉。
        """
        rows = [(slot, cells) for slot in (3, 5)
                for _a, _s, cells, _e in K.PLAN[slot] if cells.get(109) == "413"]
        self.assertEqual([(slot, cells.get(113), cells.get(114), cells.get(102))
                          for slot, cells in rows],
                         [(3, "5000", "5000", "5"),        # 每层回响 ＋5%，封顶 5 层 ＝ ＋25%
                          (5, "30000", "30000", None)])    # 常驻 ＋30%
        for _slot, cells in rows:
            self.assertEqual(cells.get(114), cells.get(113))   # 低/满级同值 ⇒ 面板出单值
        # 面板那两行必须自称「额外乘区」（413 的语义）；改 kind 就得改这里
        self.assertIn("额外乘区", K.PANEL_ABILITY[3])
        self.assertIn("额外乘区", K.PANEL_ABILITY[5])

    def test_plan_counts(self):
        # 2026-09-27 第二批平衡：回响每层的两条无上限成长从槽 3/槽 4 搬进队长（10 → 12 行）
        self.assertEqual(K.LEADER_ROWS, 12)
        self.assertEqual(K.ABILITY_RECORDS, 19)
        self.assertEqual({slot: len(rows) for slot, rows in K.PLAN.items()},
                         {1: 2, 2: 2, 3: 3, 4: 3, 5: 6, 6: 3})
        self.assertEqual(K.ABILITY_KEYS, tuple(f"{K.CID}{n}" for n in range(1, 7)))

    def test_design_mirror_is_in_sync(self):
        self.assertEqual(K.design_problems(DESIGN), [])
        self.assertIn("plan", DESIGN)                # 首建版计划原样保留作历史
        self.assertEqual(DESIGN["plan_rework1"]["leader_rows"], K.LEADER_ROWS)

    def test_design_mirror_catches_drift(self):
        broken = copy.deepcopy(DESIGN)
        broken["plan_rework1"]["leader_rows"] = 6
        self.assertTrue(any("leader row count" in p for p in K.design_problems(broken)))
        self.assertEqual(K.design_problems({}), ["design has no plan_rework1 block"])


class PlanSelfCheckTests(unittest.TestCase):
    """裁决 §8：装配前对行计划的硬自查（不需要 donor 表，只看本模块登记的格子）。"""

    def test_leader_plan_carries_no_patched_kinds(self):
        # 422 冲刺参数 / 724 Fever 比例 / 713 只许写 ability 表；写进队长表 = C7050
        for index, (_addr, _src, cells, _expect) in enumerate(K.LEADER):
            for col in (K.LEADER_INSTANT_KIND, K.LEADER_DURING_KIND):
                self.assertNotIn(str(cells.get(col, "")), K.FORBIDDEN_LEADER_KINDS, index)

    def test_dash_rows_stay_in_the_ability_table_and_are_leader_scoped(self):
        dash = [cells for _a, _s, cells, _e in K.PLAN[5] if cells.get(109) == "422"]
        self.assertEqual(len(dash), 5)               # 速度 / CD / 蓄力 / 发动高度
        for cells in dash:
            self.assertEqual(cells[6], "42")         # 前置 42 = 队长，避免与基诺维/泽赫尔相加
        self.assertEqual(sorted(c[118] for c in dash), ["0", "0", "1", "3", "6"])

    def test_leader_722_row_has_no_precondition(self):
        cells = K.LEADER[0][2]
        self.assertEqual(cells[45], "722")
        self.assertEqual(cells[80], K.PF_KEY)
        self.assertEqual(cells[82], K.CAS_PF)
        self.assertEqual(cells[81], "1,2,3")
        for col in (4, 11, 18):
            self.assertIn(cells.get(col, "0"), ("", "0"), f"722 行挂了前置 c{col}")

    def test_the_two_invoke_rows(self):
        invoke = [(n, cells) for n, (_a, _s, cells, _e) in enumerate(K.LEADER)
                  if cells.get(45) == "629"]
        self.assertEqual(len(invoke), 2)
        by_trigger = {cells[25]: cells for _n, cells in invoke}
        self.assertEqual(sorted(by_trigger), ["23", "4"])
        skill_row = by_trigger["23"]                 # 暗属性角色发动技能时（官方同形 141111#1）
        self.assertEqual((skill_row[26], skill_row[27]), ("5", K.ELEMENT_TOKEN))
        self.assertEqual(skill_row[4], "2")          # 暗共鸣门
        self.assertEqual(skill_row[68], K.CAS_INVOKE_SKILL)
        dash_row = by_trigger["4"]                   # 冲刺时 CT 5 秒
        self.assertEqual(dash_row[33], "90")  # 1.5 seconds; skill-triggered row stays unchanged.
        self.assertEqual(dash_row[68], K.CAS_INVOKE_DASH)
        for _n, cells in invoke:
            self.assertEqual(cells[69], K.INVOKE_PROGRAM)
            self.assertEqual(cells[32], "(None)")    # 触发次数无上限
            self.assertEqual(cells[46], "0")         # target = 自身

    def test_no_629_row_can_land_in_a_unisonable_key(self):
        """629 在合击位零先例且演出者硬绑主位（记忆卡 wf-unison-slot-mechanics）。

        她的两行 629 都在队长表（队长本来就只在主位生效）；词条表一条都没有，
        所以能力 3 改成仅主位与 629 没有冲突，也不需要给槽 3 补 202。
        """
        for slot, rows in K.PLAN.items():
            for index, (_a, _s, cells, _e) in enumerate(rows):
                for col in (47, 109):                # 瞬发 kind / 持续 kind
                    self.assertNotEqual(str(cells.get(col, "")), "629", f"{slot}#{index}")
        self.assertEqual([n for n, (_a, _s, cells, _e) in enumerate(K.LEADER)
                          if cells.get(45) == "629"], [5, 7])

    def test_uncapped_hit_row(self):
        """任意等级PF累计命中4次自身攻击保持无上限（2026-09-27 第二批平衡：50% → 5%；第三轮 5% → 35%）。"""
        l7 = K.LEADER[6][2]
        self.assertEqual(l7[25], "15")
        self.assertEqual(l7[28], "400000")
        self.assertEqual(l7[32], "(None)")           # 新行：无上限、只给自身
        self.assertEqual((l7[46], l7[47]), ("0", ""))
        self.assertEqual((l7[49], l7[50]), ("35000", "35000"))

    def test_echo_rows(self):
        """回响：461 挂暗共鸣门；能力侧 PF 伤害/攻击力封顶 10 层（2026-09-27 第二批平衡，原 99 层），
        无上限部分在队长两条 during 134（上限照抄 99 ＝ 固有上限，每层 2.5%，第三轮回调到 20%）；
        独立乘区与全队暗攻仍封顶 5 层。"""
        gain = K.PLAN[3][0][2]
        self.assertEqual(gain[47], "461")
        self.assertEqual((gain[6], gain[11]), ("2", K.ELEMENT_TOKEN))
        self.assertEqual(gain[68], K.UID)
        caps = {}
        for slot in (3, 4, 6):
            for _a, _s, cells, _e in K.PLAN[slot]:
                if cells.get(97) == "134":
                    caps[(slot, cells[109])] = cells[102]
        self.assertEqual(caps[(3, "23")], K.ECHO_ABILITY_CAP)   # PF 伤害 +10%/层，10 层（第二批）
        self.assertEqual(caps[(4, "0")], K.ECHO_ABILITY_CAP)    # 自身攻击力 +5%/层，10 层（第二批）
        self.assertEqual(K.ECHO_ABILITY_CAP, "10")
        leader = {cells[107]: cells for _a, _s, cells, _e in K.LEADER if cells.get(95) == "134"}
        self.assertEqual(sorted(leader), ["0", "23"])            # 队长：每层攻击力 / PF 伤害
        for cells in leader.values():
            self.assertEqual((cells[100], cells[102], cells[111], cells[112]),
                             (K.UNIQUE_CAP, K.UID, "20000", "20000"))
        self.assertEqual(caps[(3, "413")], "5")              # 独立乘区 +5%/层，作者「最大 25%」
        self.assertEqual(caps[(6, "0")], "5")                # 全队暗攻 +15%/层
        for cells in (K.PLAN[3][1][2], K.PLAN[3][2][2], K.PLAN[4][2][2], K.PLAN[6][2][2]):
            self.assertEqual(cells[104], K.UID)

    def test_ability_2_values_are_doubled(self):
        self.assertEqual((K.PLAN[2][0][2][51], K.PLAN[2][0][2][52]), ("8000", "8000"))
        self.assertEqual((K.PLAN[2][1][2][51], K.PLAN[2][1][2][52]), ("12000", "12000"))

    def test_ability_5_gains_the_flat_independent_multiplier(self):
        first = K.PLAN[5][0][2]
        self.assertEqual(first[109], "413")
        self.assertEqual((first[113], first[114]), ("30000", "30000"))
        self.assertEqual(first[118], "")             # 不是 422 行，冲刺参数 id 必须留空
        self.assertEqual(first[6], "0")              # 常驻，不挂队长前置

    def test_statue_group_and_unisonable_are_single_valued(self):
        self.assertEqual(sorted(K._STATUE), [1, 2, 3, 4, 5, 6])
        for group in K._STATUE.values():
            self.assertIn(group, L.ABILITY_STATUE_GROUPS)
        self.assertEqual(K.MAIN_ONLY_SLOTS, (3,))    # 槽 3 仅主位（面板 main_only）
        self.assertEqual(K._UNISONABLE,
                         {slot: ("false" if slot in K.MAIN_ONLY_SLOTS else "true")
                          for slot in range(1, 7)})

    def test_slot_3_is_main_only_for_every_record_of_the_key(self):
        """反馈轮 1：能力 3 必须整键仅主位 —— c1 一键单值，不能有的行限、有的行不限。

        c1 由 ``MAIN_ONLY_SLOTS`` 派生，行计划里任何一格都不许再写 c1 盖掉它。
        """
        self.assertEqual(K._UNISONABLE[3], "false")
        for slot, rows in K.PLAN.items():
            for index, (_a, _s, cells, _e) in enumerate(rows):
                self.assertNotIn(1, cells, f"{slot}#{index} 不许逐行改写 c1")
        merged = [{0: f"{K.CODE}_3", 1: K._UNISONABLE[3], 2: K._STATUE[3], **cells}
                  for _a, _s, cells, _e in K.PLAN[3]]
        self.assertEqual(len(merged), 3)
        self.assertEqual({row[1] for row in merged}, {"false"})

    def test_the_echo_stack_has_no_source_outside_the_main_only_key(self):
        """回响（16998801）只由槽 3 的 461 行产出 ⇒ 她在合击位时层数恒 0，

        槽 4 #2「每层回响→自身攻击力」（2026-09-27 第二批起封顶 10 层，文案回到能力 4）与
        槽 6 #2 都只是读层数（c104），不会另外加层。技能 DSL 也加 1 层，但副位不放技能。
        """
        givers, readers = [], []
        for slot, rows in K.PLAN.items():
            for index, (_a, _s, cells, _e) in enumerate(rows):
                if cells.get(68) == K.UID:           # 461 的付与目标固有
                    givers.append((slot, index))
                if cells.get(104) == K.UID:          # during 134 的计数源
                    readers.append((slot, index))
        self.assertEqual(givers, [(3, 0)], "回响只能有一个产出口，且必须在仅主位的槽 3")
        self.assertEqual(readers, [(3, 1), (3, 2), (4, 2), (6, 2)])
        for slot, _index in givers:
            self.assertIn(slot, K.MAIN_ONLY_SLOTS)
        # 2026-09-24 作者增加队长每3PF回响+2；队长位仍不让合击位单独产层。
        leader_givers = [cells for _a, _s, cells, _e in K.LEADER if cells.get(66) == K.UID]
        self.assertEqual(len(leader_givers), 1)
        self.assertEqual(leader_givers[0][72], "2")

    def test_precondition_kinds_are_whitelisted(self):
        for index, (_a, _s, cells, _e) in enumerate(K.LEADER):
            for col in (4, 11, 18):
                self.assertIn(str(cells.get(col, "")), K.ALLOWED_PRECONDITION_KINDS, index)
        for slot, rows in K.PLAN.items():
            for index, (_a, _s, cells, _e) in enumerate(rows):
                for col in (6, 13, 20):
                    self.assertIn(str(cells.get(col, "")), K.ALLOWED_PRECONDITION_KINDS,
                                  f"{slot}#{index}")

    def test_during_puller_columns(self):
        # during 134 / during 1 的 puller 写 '0'；during 30 留空。写反 = 点「角色」C7050
        for slot, rows in K.PLAN.items():
            for index, (_a, _s, cells, _e) in enumerate(rows):
                if cells.get(5) != "1":
                    continue
                want = "0" if cells.get(97) in ("134", "1") else ""
                self.assertEqual(cells.get(98, ""), want, f"{slot}#{index}")
        for index, (_a, _s, cells, _e) in enumerate(K.LEADER):
            if cells.get(3) != "1":
                continue
            want = "0" if cells.get(95) in ("134", "1") else ""
            self.assertEqual(cells.get(96, ""), want, index)

    def test_row_self_check_rejects_a_leader_422(self):
        rows = [[""] * KL.LEADER_NCOLS]
        rows[0][3] = "1"
        rows[0][K.LEADER_DURING_KIND] = "422"
        with self.assertRaises(K.KitError):
            K._row_self_check("leader_ability", rows, "leader")

    def test_row_self_check_rejects_a_629_without_a_string_key(self):
        rows = [[""] * KL.LEADER_NCOLS]
        rows[0][3] = "0"
        rows[0][K.LEADER_INSTANT_KIND] = "629"
        rows[0][K.LEADER_ACTION_PATH] = K.INVOKE_PROGRAM
        with self.assertRaises(K.KitError):
            K._row_self_check("leader_ability", rows, "leader")


class PanelTextTests(unittest.TestCase):
    def test_panel_obeys_the_batch_rules(self):
        for key, text in K.CAS_TEXTS.items():
            self.assertEqual(KL.panel_problems(text.replace(K.MAIN_ICON, "")), [], key)

    def test_panel_is_transcribed_from_the_authors_sheet(self):
        """逐行等于 rework1/panel/hibiki.json（作者已过目的那一版）。"""
        if not PANEL_JSON.is_file():
            self.skipTest("rework1/panel/hibiki.json missing")
        want = json.loads(PANEL_JSON.read_text(encoding="utf-8"))
        self.assertEqual(K.PANEL_LEADER.split("\n"),
                         [line["text"] for line in want["leader"]["lines"]])
        for block in want["abilities"]:
            slot = int(block["index"])
            self.assertEqual(K.PANEL_ABILITY[slot].split("\n"),
                             [line["text"] for line in block["lines"]], slot)
            self.assertEqual(K._UNISONABLE[slot], "false" if block["main_only"] else "true", slot)
            # 写进表的 override 正文＝作者原文 + 主位槽逐行的 Ⓜ
            self.assertEqual(
                [line.replace(K.MAIN_ICON, "")
                 for line in K.CAS_TEXTS[K.CAS_ABILITY[slot]].split("\n")],
                [line["text"] for line in block["lines"]], slot)

    def test_main_only_slots_carry_the_icon_on_every_override_line(self):
        """反馈轮 1：desc_override 盖掉客户端逐行画的 Ⓜ ⇒ 仅主位的槽每行必须自带图标。"""
        for slot in range(1, 7):
            wants = slot in K.MAIN_ONLY_SLOTS
            lines = K.CAS_TEXTS[K.CAS_ABILITY[slot]].split("\n")
            self.assertTrue(lines)
            for line in lines:
                self.assertEqual(line.startswith(K.MAIN_ICON), wants, f"slot {slot}: {line}")
        # 队长块本身就在主位语境里，不画 Ⓜ
        self.assertNotIn(K.MAIN_ICON, K.CAS_TEXTS[K.CAS_LEADER])
        self.assertEqual(K.MAIN_ICON, " <icon id='main'>  ")   # live 先例 desc_override_ginovi_3

    def test_leader_and_slot_override_keys(self):
        # desc_override 的键 = 该块第 0 行的 string_id（队长块 = c0，能力槽 = <code>_<slot>）
        self.assertEqual(K.CAS_LEADER, f"desc_override_{K.CODE}")
        self.assertEqual(K.LEADER[0][2][0], K.CODE)
        for slot in range(1, 7):
            self.assertEqual(K.CAS_ABILITY[slot], f"desc_override_{K.CODE}_{slot}")
            self.assertEqual(L.panel_override_capability(K.CAS_ABILITY[slot]),
                             "panel-description-override-v2")
        self.assertIn("panel-description-override-v2", K.SPEC["required_capabilities"])

    def test_deviations_are_registered(self):
        ids = [item["id"] for item in DESIGN["deviations"]]
        self.assertEqual(len(ids), len(set(ids)))
        for item in DESIGN["deviations"]:
            self.assertTrue(item["intended"] and item["actual"] and item["reason"], item["id"])
        for wanted in DESIGN["rework1"]["deviations_new"]:
            self.assertIn(wanted, ids)


class TreeHelperTests(unittest.TestCase):
    def test_remap_subjects_covers_delete_condition(self):
        node = ["Command", ["FindAllSubjects", 1, 113, [6], [], [], [], [], ["DoNothing"],
                            ["Block", [["Command", ["DeleteCondition", 1, ["DCAll", 3], 1, 0, "",
                                                    ["Default"]]]]]]]
        plain = copy.deepcopy(node)
        PH.remap_subjects(plain, {1: 201}.__getitem__)
        self.assertEqual(PH.cmds(plain, "DeleteCondition")[0][1], 1)   # philia 的版本不收录它
        fixed = copy.deepcopy(node)
        K.remap_subjects(fixed, {1: 201}.__getitem__)
        self.assertEqual(fixed[1][1], 201)
        self.assertEqual(PH.cmds(fixed, "DeleteCondition")[0][1], 201)

    def test_one_cmd_and_ac_node(self):
        cc = ["CreateCondition", -17, [["ACPiercing", [{"min": 60, "max": 60}]]]]
        self.assertEqual(K.ac_node(cc, "ACPiercing")[1][0]["min"], 60)
        with self.assertRaises(K.KitError):
            K.ac_node(cc, "ACFlying")
        with self.assertRaises(K.KitError):
            K.one_cmd(["Block", []], "ShowEffect")

    def test_conditional_names(self):
        tree = ["Block", [["Command", ["ConditionalsNumExecutionsOfPowerflip", 1, ["Block", []],
                                       ["Block", []]]]]]
        self.assertEqual(K.conditional_names(tree), {"ConditionalsNumExecutionsOfPowerflip"})

    def test_dsl_problems_rejects_num_executions_and_duplicate_binds(self):
        def find_all(bind):
            return ["Command", ["FindAllSubjects", bind, 33, [], [], [], [], [], ["DoNothing"],
                                ["Block", []]]]
        tree = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
                ["Block", [find_all(1), find_all(1)]]]
        self.assertTrue(any("duplicate bound subject ids" in p
                            for p in K.dsl_problems(tree, element=None)))
        tree2 = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
                 ["Block", [["Command", ["ConditionalsNumExecutionsOfPowerflip", 1, ["Block", []],
                                         ["Block", []]]]]]]
        self.assertTrue(any("ConditionalsNumExecutions" in p
                            for p in K.dsl_problems(tree2, element=None)))

    def test_write_dsl_checked_rejects_the_wrapper_shape(self):
        # 记忆卡 wf-dsl-encode-wrapper-trap：喂 {tree, numbers} 包装壳 = 进战斗 F1034
        with self.assertRaises(K.KitError):
            K.write_dsl_checked(None, "x", {"tree": ["ActionDsl"], "numbers": []})

    def test_draw_icon_keeps_the_donor_alpha(self):
        from PIL import Image
        frame = Image.new("RGBA", (48, 48), (0, 0, 0, 0))
        for y in range(6, 42):
            for x in range(6, 42):
                frame.putpixel((x, y), (10, 10, 10, 255))
        icon = K.draw_icon(frame)
        self.assertEqual(icon.size, (48, 48))
        self.assertEqual(icon.getchannel("A").tobytes(), frame.getchannel("A").tobytes())
        with self.assertRaises(K.KitError):
            K.draw_icon(Image.new("RGBA", (64, 64)))


# ---------------------------------------------------------------- 2. 官方基线

@unittest.skipUnless(_BASELINE, "needs the official .cdn/cn baseline + live store + supporter sources")
class RowAssemblyTests(unittest.TestCase):
    def test_every_row_is_legal_and_describes_as_planned(self):
        leader, ability = assembled_rows()
        checked = 0
        for row, (addr, _src, _cells, expect) in zip(leader, K.LEADER):
            self.assertEqual(KL.row_problems("leader_ability", row), {}, addr)
            self.assertEqual(KL.describe("leader_ability", row), expect, addr)
            self.assertEqual(row[0], K.CODE)
            checked += 1
        K._row_self_check("leader_ability", leader, "leader")
        for slot in range(1, 7):
            key = f"{K.CID}{slot}"
            rows = ability[key]
            for row, (addr, _src, _cells, expect) in zip(rows, K.PLAN[slot]):
                self.assertEqual(KL.row_problems("ability", row, K.ELEMENT), {}, addr)
                self.assertEqual(KL.describe("ability", row), expect, addr)
                checked += 1
            KL.check_ability_key(rows, key, K.CODE, slot)
            K._row_self_check("ability", rows, key)
        self.assertEqual(checked, K.LEADER_ROWS + K.ABILITY_RECORDS)
        self.assertEqual(checked, 31)                     # 2026-09-27 第二批平衡：队长 +2 行

    def test_required_capabilities(self):
        leader, ability = assembled_rows()
        caps = set()
        for row in leader:
            caps.update(KL.capabilities("leader_ability", row))
        for rows in ability.values():
            for row in rows:
                caps.update(KL.capabilities("ability", row))
        self.assertIn("dash-parameter-v1", caps)
        self.assertLessEqual(caps, set(K.SPEC["required_capabilities"]))

    def test_statue_group_precedent_report_only_flags_the_known_gaps(self):
        _leader, ability = assembled_rows()
        report = K.statue_group_report(ctx(), ability)
        zero = sorted({f"{e['group']}×{e['trigger']}{e['kind']}"
                       for e in report if e["official_rows"] == 0})
        # 422 是官方全表 0 行的补丁 kind；413×attack_common 官方 0 行（power_flip / action_skill
        # 上才有先例，rework1 新增，偏离 D-18）；461×power_flip 官方 0 行（live 有先例，首建版就在）。
        # c2 只喂 ability_statue_group 的外观三列，记录而非阻断。
        self.assertEqual(zero, ["attack_common×during413", "attack_common×during422",
                                "power_flip×instant461"])

    def test_unique_row_rejects_a_none_cap(self):
        spec = MS.get_spec("hibiki")
        with self.assertRaises(KL.KitError):
            KL.unique_row(ctx(), spec, 1, donor=K.UNIQUE_DONOR,
                          cells={0: K.UNIQUE_STRING_ID, 4: "(None)"}, name=K.UNIQUE_NAME)


@unittest.skipUnless(_BASELINE, "needs the official .cdn/cn baseline + supporter sources")
class SkillTreeTests(unittest.TestCase):
    def test_both_levels_assemble_and_pass_the_gates(self):
        for level, want_field in (("1", 2.4), ("2", 3.0)):
            tree, gates = K.build_skill_tree(ctx(), level, fake_family())
            self.assertEqual(tree[0], "ActionDsl")
            self.assertEqual(tree[1], 1)
            self.assertEqual(tree[10], 0)                     # 技能伤害归属（设计 D-1）
            self.assertEqual(K.dsl_problems(tree), [])
            self.assertEqual(gates["n_attacks"], 1)           # 唯一伤害块 = 月光音场
            cna = PH.cmds(tree, "CreateNormalAttack")[0]
            self.assertEqual(cna[2], 255)                     # 继承角色属性，不写显式元素
            self.assertEqual(cna[6][0]["max"], want_field)
            self.assertEqual(cna[15], ["Fine"])
            self.assertEqual([p for p in gates["fx_paths"]
                              if not p.startswith(K.FX_DST_DIR + "/")], [])
            for path in PH.spec_paths(tree):
                self.assertFalse(path.startswith(K.FORBIDDEN_FX_PREFIXES), path)

    def test_team_block_and_echo(self):
        tree, _ = K.build_skill_tree(ctx(), "2", fake_family())
        conds = {c[2][0][0]: c for c in PH.cmds(tree, "CreateCondition")}
        self.assertEqual(set(conds), {"ACAttackPoint", "ACPowerFlipDamage", "ACPiercing", "ACUnique"})
        self.assertEqual(conds["ACPowerFlipDamage"][2][0][1][0]["min"], K.TEAM_PFDMG_FRAMES)
        self.assertEqual(conds["ACPowerFlipDamage"][2][0][2][0]["min"], 1.2)
        self.assertEqual(conds["ACPiercing"][2][0][1][0]["min"], 810)
        self.assertEqual(conds["ACPowerFlipDamage"][10], 2)   # 97 = 球 ⇒ 付与对象种类 2
        echo = conds["ACUnique"]
        self.assertEqual(echo[1], -17)
        self.assertEqual(echo[10], 3)                         # 自身/Member ⇒ 3
        self.assertEqual(K.ac_node(echo, "ACUnique")[1], int(K.UID))
        self.assertEqual(len(PH.cmds(tree, "DeleteCondition")), 2)
        self.assertEqual(len(PH.cmds(tree, "StopBall")), 1)

    def test_removed_template_blocks_are_gone(self):
        tree, _ = K.build_skill_tree(ctx(), "1", fake_family())
        self.assertEqual(PH.cmds(tree, "CreateRatioAttack"), [])     # 自伤（裁决 §2：零先例不用）
        self.assertEqual(PH.cmds(tree, "CreateRatioHeal"), [])
        self.assertEqual(K.conditional_names(tree), set())
        self.assertEqual([c for c in PH.cmds(tree, "CreateCondition")
                          if c[2][0][0] == "ACSkillDamage"], [])

    def test_subject_ids_land_in_the_planned_bands(self):
        _tree, gates = K.build_skill_tree(ctx(), "1", fake_family())
        self.assertEqual(gates["bound_ids"], [100, 101, 102, 200, 201, 202])


@unittest.skipUnless(_BASELINE, "needs the official .cdn/cn baseline + supporter sources")
class PowerFlipTests(unittest.TestCase):
    TOTALS = {1: 24.0, 2: 36.8, 3: 62.4}

    def test_three_levels_scale_and_keep_the_lifecycle(self):
        for level in (1, 2, 3):
            tree, gates = K.build_pf_tree(ctx(), level)
            self.assertEqual(tree[10], 0)
            self.assertEqual(K.dsl_problems(tree, element=None), [])
            self.assertAlmostEqual(gates["total"], self.TOTALS[level], places=6)
            self.assertTrue(PH.cmds(tree, "SetPowerFilpSuppress"))
            self.assertTrue(PH.cmds(tree, "NotifyPowerflipEnd"))
            for cha in PH.cmds(tree, "CreateHitArea"):
                self.assertEqual(cha[24], 0)   # p23=4 会按直击算，整块 PF 乘区被跳过
            self.assertEqual(gates["pierce_frames"], K.PF_PIERCE_FRAMES[level])

    def test_support_block_is_appended_once(self):
        """rework1 反馈轮 3（作者「澄波响去掉浮游效果」）：ACFlying 已从三档辅助增益块删掉，
        只剩 ACAttackPoint / ACPiercing（原样保留，绑定/参数不动）。

        注：``PH.pf_support_block`` 是与菲莉亚共用的读代码，同一批反馈期间对方也在改它
        （本模块不碰那个文件）；不管它现在是「已经删过」还是「原样三件套」，本模块自己的
        分支都要把最终结果收到同一个终态，所以这里只断言终态，不假设 ``ac_flying_removed``
        具体是 0 还是 1（那两个分支各自的行为见下面两条测试）。"""
        for level in (1, 2, 3):
            tree, gates = K.build_pf_tree(ctx(), level)
            kinds = [c[2][0][0] for c in PH.cmds(tree, "CreateCondition")]
            self.assertEqual(kinds, ["ACAttackPoint", "ACPiercing"])
            self.assertEqual(K.count_ac_flying(tree), 0)
            self.assertIn(gates["ac_flying_removed"], (0, 1))
            self.assertEqual(gates["ac_flying_count"], 0)
            self.assertEqual(gates["support_block_kinds"], ["ACAttackPoint", "ACPiercing"])
            pierce = next(c for c in PH.cmds(tree, "CreateCondition")
                          if c[2][0][0] == "ACPiercing")
            self.assertEqual(K.ac_node(pierce, "ACPiercing")[1][0]["min"],
                             K.PF_PIERCE_FRAMES[level])
            self.assertIn(K.PF_SUPPORT_BIND, PH.bound_ids(tree))

    def test_accepts_a_donor_that_still_carries_flying(self):
        """分支 1：``pf_support_block`` 默认送回官方原始三件套（共享函数默认保留浮游，
        芙拉菲/丝缇涅尔还要用），本模块自己删干净。"""
        donor = PH.pf_support_block(ctx().root, 1)
        self.assertEqual([c[2][0][0] for c in PH.cmds(donor, "CreateCondition")],
                         ["ACAttackPoint", "ACPiercing", "ACFlying"])
        tree, gates = K.build_pf_tree(ctx(), 1)
        self.assertEqual(gates["ac_flying_removed"], 1)
        self.assertEqual(gates["ac_flying_count"], 0)
        self.assertEqual(K.count_ac_flying(tree), 0)
        kinds = [c[2][0][0] for c in PH.cmds(tree, "CreateCondition")]
        self.assertEqual(kinds, ["ACAttackPoint", "ACPiercing"])

    def test_accepts_a_donor_that_already_dropped_flying(self):
        """分支 2：共享函数哪天改成源头就删（``keep_flying=False`` 的形态）时不重复删。"""
        original = PH.pf_support_block

        def already_dropped(root, level):
            return original(root, level, keep_flying=False)

        K.PH.pf_support_block = already_dropped
        try:
            tree, gates = K.build_pf_tree(ctx(), 1)
            self.assertEqual(gates["ac_flying_removed"], 0)
            self.assertEqual(gates["ac_flying_count"], 0)
            self.assertEqual(K.count_ac_flying(tree), 0)
        finally:
            K.PH.pf_support_block = original

    def test_rejects_a_block_that_is_neither_known_shape(self):
        """真漂移（既不是原始三件套也不是删后两件套，比如少了 ACAttackPoint）必须当场炸。"""
        original = PH.pf_support_block

        def missing_attack_point(root, level):
            block = original(root, level)
            find_all = block[1]
            body = find_all[9][1]
            find_all[9][1] = [e for e in body if e[1][2][0][0] != "ACAttackPoint"]
            return block

        K.PH.pf_support_block = missing_attack_point
        try:
            with self.assertRaises(K.KitError):
                K.build_pf_tree(ctx(), 1)
        finally:
            K.PH.pf_support_block = original

    def test_strip_ac_flying_removes_the_one_entry(self):
        block = _synthetic_support_block(["ACAttackPoint", "ACPiercing", "ACFlying"])
        removed = K.strip_ac_flying(block)
        self.assertEqual(removed, 1)
        kinds = [c[2][0][0] for c in PH.cmds(block, "CreateCondition")]
        self.assertEqual(kinds, ["ACAttackPoint", "ACPiercing"])

    def test_strip_ac_flying_rejects_a_block_without_exactly_one(self):
        """``strip_ac_flying`` 自己也不该在没有恰好 1 条 ACFlying 时悄悄通过。"""
        with self.assertRaises(K.KitError):
            K.strip_ac_flying(_synthetic_support_block(["ACAttackPoint", "ACPiercing"]))
        with self.assertRaises(K.KitError):
            K.strip_ac_flying(_synthetic_support_block(
                ["ACAttackPoint", "ACPiercing", "ACFlying", "ACFlying"]))

    def test_official_effects_are_referenced_not_packaged(self):
        for level in (1, 2, 3):
            tree, gates = K.build_pf_tree(ctx(), level)
            self.assertTrue(gates["official_effects"])
            for path in gates["official_effects"]:
                self.assertFalse(path.startswith(f"battle/effect/skill_unique/{K.CODE}/"), path)

    def test_source_fingerprint_is_locked(self):
        with self.assertRaises(K.KitError):
            K.source_tree(ctx(), K.SPECIAL_PROGRAMS[1], "0" * 64)


@unittest.skipUnless(_BASELINE, "needs the official .cdn/cn baseline")
class InvokeTreeTests(unittest.TestCase):
    """rework1 的 629 PF 追击树（斩铁式：官方 PF 底座只留命中块）。"""

    def test_tree_shape_and_gates(self):
        tree, gates = K.build_invoke_tree(ctx())
        self.assertEqual(tree[0], "ActionDsl")
        self.assertEqual(tree[1], 1)
        self.assertEqual(tree[10], K.INVOKE_BTA)           # 3 = 通用伤害池走强化弹射
        self.assertEqual(K.dsl_problems(tree, element=None), [])
        self.assertEqual(gates["total"], 62.4)             # (4 + 9) × 4.8
        self.assertEqual(gates["multipliers"], [19.2, 43.2])

    def test_detoughness_is_one_per_call(self):
        """2026-09-27 第二批平衡（口径 B.3）：触发 CT ≤3 秒的 629 每次削韧 ≤1 ⇒ 每段 p13 6.25 → 0.25。"""
        tree, gates = K.build_invoke_tree(ctx())
        self.assertEqual([c[13] for c in PH.cmds(tree, "CreateNormalAttack")],
                         [[{"min": 0.25, "max": 0.25}]] * 2)
        self.assertEqual(gates["detoughness"], {"per_segment": 0.25, "segments": [3, 1],
                                                "per_call": 1.0, "official_per_segment": 6.25})
        invokes = [cells for _a, _s, cells, _e in K.LEADER if cells.get(45) == "629"]
        self.assertTrue(all(int(cells[33]) <= 180 for cells in invokes))   # 两行 CT 都 ≤3 秒

    def test_damage_attribution_is_on_the_root_not_the_hit_areas(self):
        """反馈轮 4：归属开关只写根头，判定区归属位全部留 0（不覆盖、回落到根头）。

        ``ActionEvaluator.as:3470`` 把 ``CreateHitArea`` 的 ``params[23]`` 读进 ``_loc17_``，
        ``as:3498`` 交给 ``Environment.createLocalEnvironmentDetail``；
        ``Environment.getBuffTargetAs`` 遇 0 才往上找 —— 所以 0 是「继承根头 3」，
        4 会把这一下变成直击（本批罗尔夫/凯尔真机实证）。官方 **1731** 个玩家侧判定区里
        这一位只有 0（1721）与 4（10），值 3 零先例（扫描脚本见 :data:`K.INVOKE_BTA` 注释）。
        """
        tree, gates = K.build_invoke_tree(ctx())
        chas = PH.cmds(tree, "CreateHitArea")
        self.assertEqual([c[24] for c in chas], [K.INVOKE_HITAREA_BTA] * len(chas))
        self.assertEqual(gates["hit_area_buff_target_as"], [K.INVOKE_HITAREA_BTA] * len(chas))
        self.assertEqual(gates["buff_target_as"], K.INVOKE_BTA)

    def test_build_rejects_a_drifted_hit_area_attribution(self):
        """判定区归属位漂移（donor 换版 / 有人手改命中块）必须当场炸，不能静默发出去。

        喂一棵 ``params[23]`` 被改过的 donor 进 :func:`build_invoke_tree`，门禁没了就转绿。
        """
        real = K.source_tree

        def patched(bad_value):
            def fake(ctx_obj, program, sha=None):
                tree = real(ctx_obj, program, sha)
                if program == K.SPECIAL_PROGRAMS[3]:
                    tree = copy.deepcopy(tree)
                    for cha in PH.cmds(tree, "CreateHitArea"):
                        cha[24] = bad_value
                return tree
            return fake

        for bad_value in (3, 4):
            K.source_tree = patched(bad_value)
            try:
                with self.assertRaises(K.KitError) as cm:
                    K.build_invoke_tree(ctx())
            finally:
                K.source_tree = real
            self.assertIn("p23", str(cm.exception))

    def test_engine_boundary_is_recorded_in_the_gates(self):
        """引擎硬限写进 kit-gates，面板/施工单与它对账（反馈轮 4 的「吃得到/吃不到」）。"""
        _tree, gates = K.build_invoke_tree(ctx())
        self.assertEqual(gates["damage_pools"], {
            "power_flip_general": True,          # NormalAttackCalculator.as:422（bta==3）
            "skill_general": False,              # as:477（bta==3 ⇒ 不进）
            "power_flip_charge_tier": True,      # damage-type-rules-v1，固定PF3
            "power_flip_separated_term": True,
            "power_flip_resistance": True,
            "skill_separated_term": False,
            "skill_resistance": False,
            "counts_as_power_flip_for_triggers": True,    # 队长248行合并普通发动计数
            "damage_label": "power_flip"})

    def test_power_flip_lifecycle_commands_are_gone(self):
        # SetPowerFilpSuppress 会压掉玩家真正的拍板；NotifyPowerflipEnd 在非 PF 上下文不计数
        tree, _ = K.build_invoke_tree(ctx())
        for name in ("SetPowerFilpSuppress", "NotifyPowerflipEnd", "RemoveEvent", "HideEffect"):
            self.assertEqual(PH.cmds(tree, name), [], name)
        self.assertEqual(len(PH.cmds(tree, "CreateHitArea")), 2)

    def test_only_official_powerflip_effects_are_referenced(self):
        _tree, gates = K.build_invoke_tree(ctx())
        self.assertTrue(gates["official_effects"])
        for path in gates["official_effects"]:
            self.assertTrue(path.startswith("battle/effect/powerflip/"), path)

    def test_coordinate_systems_stay_ab(self):
        """主体是球/敌人的 ShowEffect 与判定区坐标系只能 AB 或 GH（U_4f5401 教训）。"""
        tree, _ = K.build_invoke_tree(ctx())
        ref = PH.cmds(tree, "CreateReferencePoint")[0]
        self.assertEqual((ref[1], ref[2]), (-18, ["AB"]))
        for show in PH.cmds(tree, "ShowEffect"):
            self.assertIn(show[6], (["AB"], ["GH"]))
        for cha in PH.cmds(tree, "CreateHitArea"):
            self.assertIn(cha[3], (["AB"], ["GH"]))


# ---------------------------------------------------------------- 3. 已构建的 workspace

@unittest.skipUnless((WORKSPACE / "evidence/kit-report.json").is_file(),
                     "workspace ma-hibiki has not been built yet")
class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = MC.MAPack(MS.get_spec("hibiki"), record_sources=False)
        cls.report = json.loads((WORKSPACE / "evidence/kit-report.json").read_text("utf-8"))
        cls.claims = json.loads((WORKSPACE / "evidence/table_claims.json").read_text("utf-8"))

    def claimed(self, logical: str) -> set[str]:
        return {key for entry in self.claims if entry["logical_path"] == logical
                for key in entry["outer_keys"]}

    def test_package_carries_every_self_owned_key(self):
        self.assertIn(K.UID, self.pack.pkg_flat(MS.UNIQUE_CONDITION_LOGICAL))
        self.assertIn(K.PF_KEY, self.pack.pkg_flat(K.PFA))
        cas = self.pack.pkg_flat(KL.CAS)
        for key in K.CAS_TEXTS:
            self.assertIn(key, cas, key)
        switched = C.core.load_nested_table_bytes(
            self.pack.pkg_path("common", KL.SWITCHED).read_bytes(), KL.SWITCHED)
        self.assertIn(K.VOICE_KEY, switched.rows)            # 嵌套表，不能用 pkg_flat
        inner = switched.rows[K.VOICE_KEY].text_rows()
        self.assertEqual(sorted(inner), ["1", "2"])
        for cells in inner.values():
            self.assertEqual(len(C.csv_split(cells)[0]), 17)  # = action_skill c7..c23

    def test_panel_override_survives_the_csv_round_trip(self):
        """多行 desc_override 的 ``\\n`` 必须活过 orderedmap 的 CSV 编解码。"""
        cas = self.pack.pkg_flat(KL.CAS)
        overlay = {B2.CAS_LEADER: (B2.leader_panel, B3.leader_panel), B2.CAS_SLOT3: (B2.slot3_panel,),
                   B2.CAS_SLOT4: (B2.slot4_panel, B3.slot4_panel), B3.CAS_SLOT2: (B3.slot2_panel,)}
        for key, text in K.CAS_TEXTS.items():
            got = C.csv_split(cas[key])[0][0]
            for fn in overlay.get(key, ()):               # 第一批输出 + 第二批覆盖 + 第三轮覆盖
                got = _batch2(fn, got)
            self.assertEqual(got, text, key)
        # 第二批：+1 行回响每层（9 行）；第三轮口径 5：原第5行按数据条件拆两行（10 行）
        self.assertEqual(len(K.PANEL_LEADER.split("\n")), 10)

    def test_every_self_owned_key_is_claimed(self):
        # 漏认领 = rebase 静默回滚（记忆卡 wf-unison-slot-mechanics）
        self.assertIn(K.UID, self.claimed(MS.UNIQUE_CONDITION_LOGICAL))
        self.assertIn(K.PF_KEY, self.claimed(K.PFA))
        self.assertLessEqual(set(K.CAS_TEXTS), self.claimed(KL.CAS))
        self.assertIn(K.VOICE_KEY, self.claimed(KL.SWITCHED))
        self.assertEqual(self.claimed(KL.ABILITY), set(K.ABILITY_KEYS))
        self.assertEqual(self.claimed(KL.LEADER), {str(K.CID)})

    def test_written_tables_match_the_plan(self):
        leader = C.csv_split(self.pack.pkg_flat(KL.LEADER)[str(K.CID)])
        ability = self.pack.pkg_flat(KL.ABILITY)
        a3, a4 = (C.csv_split(ability[key]) for key in (B2.ABILITY3, B2.ABILITY4))
        leader = _batch2(lambda rows: B2.leader_rows(rows, a3, a4), leader)   # 第一批输出 + 第二批覆盖
        self.assertEqual(len(leader), K.LEADER_ROWS)
        for slot in range(1, 7):
            rows = C.csv_split(ability[f"{K.CID}{slot}"])
            self.assertEqual(len(rows), len(K.PLAN[slot]), slot)
            self.assertEqual({r[2] for r in rows}, {K._STATUE[slot]}, slot)
            self.assertEqual({r[1] for r in rows}, {K._UNISONABLE[slot]}, slot)
        unique = C.csv_split(self.pack.pkg_flat(MS.UNIQUE_CONDITION_LOGICAL)[K.UID])[0]
        self.assertEqual(unique[4], K.UNIQUE_CAP)
        self.assertEqual(unique[1], K.UNIQUE_NAME)

    def test_power_flip_action_points_at_the_three_programs(self):
        row = C.csv_split(self.pack.pkg_flat(K.PFA)[K.PF_KEY])[0]
        self.assertEqual(row, list(K.PF_PROGRAMS))
        programs = set(self.report["skills"]["programs"])
        import wf_dsl
        for program in K.PF_PROGRAMS:
            self.assertIn(wf_dsl.dsl_logical(program), programs)
        self.assertIn(wf_dsl.dsl_logical(K.INVOKE_PROGRAM), programs)

    def test_written_dsl_round_trips(self):
        import wf_dsl
        programs = list(K.PF_PROGRAMS) + [K.INVOKE_PROGRAM] + [
            f"battle/action/skill/action/rare5/{K.CODE}${K.CODE}_{n}" for n in (1, 2)]
        for program in programs:
            logical = wf_dsl.dsl_logical(program)
            tree = C.amf_parse(self.pack.pkg_path("common", logical).read_bytes())
            self.assertEqual(tree[0], "ActionDsl", logical)
            self.assertEqual(K.dsl_problems(tree, element=None), [], logical)
        invoke = C.amf_parse(self.pack.pkg_path("common", wf_dsl.dsl_logical(K.INVOKE_PROGRAM))
                             .read_bytes())
        self.assertEqual(invoke[10], K.INVOKE_BTA)
        # 反馈轮 4：打进包里的那棵树，两个归属位都要是源码证明过的取值。
        invoke_chas = PH.cmds(invoke, "CreateHitArea")
        self.assertEqual(len(invoke_chas), 2)
        self.assertEqual([c[24] for c in invoke_chas], [K.INVOKE_HITAREA_BTA] * 2)

    def test_character_row_routes_the_voice(self):
        row = self.pack.pkg_character_row()
        self.assertEqual(row[9:17], KL.voice_route(K.CODE, K.VOICE_ROUTE))
        self.assertEqual(row[26], "Attacker")
        self.assertEqual(row[27], str(K.CID))

    def test_action_skill_energy_and_icon(self):
        table = C.core.load_nested_table_bytes(
            self.pack.pkg_path("common", KL.ACTION).read_bytes(), KL.ACTION)
        rows = {k: C.csv_split(v)[0] for k, v in table.rows[K.CODE].text_rows().items()}
        self.assertEqual(sorted(rows), ["1", "2"])
        for level, cells in rows.items():
            self.assertEqual(cells[2], K.SKILL_ICON)
            self.assertEqual(cells[4], str(K.SKILL_ENERGY[level]["c4"]))
            self.assertEqual(cells[5], str(K.SKILL_ENERGY[level]["c5"]))

    def test_report_status_gate_only_covers_kit_owned_work(self):
        gate = self.report["kit_gate"]
        self.assertEqual(gate["rows"], 29)
        self.assertEqual(gate["programs"], 6)               # 技能 2 档 + 722 三档 + 629 追击
        expected = KL.READY if gate["pixel_present"] and not gate["pixel_missing"] else KL.DRAFT
        self.assertEqual(self.report["status"], expected)

    def test_report_panel_and_deviations(self):
        self.assertEqual(self.report["cid"], K.CID)
        panel = list(self.report["panel"])                # rework1 构建证据 + 第二批覆盖
        panel[0] = _batch2(B3.leader_panel, _batch2(B2.leader_panel, panel[0]))   # + 第三轮覆盖
        panel[2] = _batch2(B3.slot2_panel, panel[2])                               # 第三轮面板同条件合并
        panel[3] = _batch2(lambda text: B2.slot3_panel(text, icon=""), panel[3])
        panel[4] = _batch2(B3.slot4_panel, _batch2(B2.slot4_panel, panel[4]))
        self.assertEqual(panel, [K.PANEL_LEADER] + [K.PANEL_ABILITY[s] for s in range(1, 7)])
        for text in self.report["panel"]:
            self.assertEqual(KL.panel_problems(text), [], text)
        self.assertEqual(len(self.report["deviations"]), len(DESIGN["deviations"]))
        self.assertEqual(set(self.report["required_capabilities"]),
                         set(K.SPEC["required_capabilities"]))
        self.assertEqual(self.report["unique_condition"][K.UID]["cap"], K.UNIQUE_CAP)
        self.assertEqual(self.report["ability_skill_programs"], [K.INVOKE_PROGRAM])

    def test_effect_family_is_the_only_cloned_one(self):
        families = json.loads((WORKSPACE / "evidence/effect-families.json").read_text("utf-8"))
        self.assertEqual(sorted(families), [K.FX_DST_DIR])
        self.assertEqual(sorted(families[K.FX_DST_DIR]["copied_bases"]),
                         sorted([K.FX_BACK, K.FX_EF]))
        self.assertEqual(families[K.FX_DST_DIR]["missing_effects"], [])


if __name__ == "__main__":
    unittest.main()
