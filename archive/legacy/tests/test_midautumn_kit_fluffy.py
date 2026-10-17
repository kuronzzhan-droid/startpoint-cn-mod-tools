# -*- coding: utf-8 -*-
"""芙拉菲 kit（149987 ``combat_animal_moon``）单测 —— **rework1（2026-09-21）**。

三层：

1. **纯静态**（不需要 live / 官方基线）：模块常量、裁决 §8 的硬规矩、DSL 闸门工具自身；
2. **官方基线**：逐行装配（donor ＋ 逐格改 ＋ ``wf_describe`` 回读）、技能树嫁接、722 覆盖树；
3. **workspace**：``--step kit`` 跑完后对 ``evidence/kit-{report,gates}.json`` 的回执核对。

第 2/3 层在没有 `.cdn/cn` 官方归档、live store 或 workspace 时自动跳过。
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE.parent) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_dsl  # noqa: E402
import wf_midautumn_common as MC  # noqa: E402
import wf_midautumn_kit_fluffy as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_build as B  # noqa: E402

ROOT = core.project_root()
DESIGN = MS.load_design(ROOT, "fluffy")
PANEL = json.loads((ROOT / "work/character_packs/midautumn-20260920/rework1/panel/fluffy.json")
                   .read_text("utf-8"))
WORKSPACE = ROOT / "work/character_packs/ma-fluffy"


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


_BASELINE = _baseline_available()
_CTX = None


def ctx():
    """只读上下文：``record_sources=False`` ⇒ 母本取数不写 workspace（框架 §10.2）。"""
    global _CTX
    if _CTX is None:
        _CTX = B.KitContext(MC.MAPack(MS.get_spec("fluffy"), record_sources=False))
    return _CTX


def fake_family(subdir: str, src_dir: str, members) -> dict:
    """``clone_effect_family`` 结果的只读替身（测树装配时不往包里写特效）。"""
    return {"src_dir": src_dir, "dst_dir": f"battle/effect/skill_unique/{K.CODE}/{subdir}",
            "donor": src_dir.rsplit("/", 1)[-1], "dst_name": subdir,
            "copied_bases": list(members)}


def fake_families() -> list[dict]:
    return [fake_family(subdir, src, members) for subdir, src, members, _lut in K.FX_FAMILIES]


# ---------------------------------------------------------------- 1. 纯静态

class ConstantTests(unittest.TestCase):
    def test_identity_matches_the_registry(self):
        spec = MS.get_spec("fluffy", with_kit=False, with_design=False)
        self.assertEqual((spec.cid, spec.code), (K.CID, K.CODE))
        self.assertEqual((spec.template_id, spec.template_code), (K.TEMPLATE_ID, K.TEMPLATE_CODE))
        self.assertEqual(spec.element, K.ELEMENT)

    def test_pf_type_is_overridden_to_supporter(self):
        """作者 09-21：详情页显示「辅助」⇒ character c6=3（母本 141033 原值是 1 格斗）。"""
        self.assertEqual(K.SPEC["pf_type"], 3)
        self.assertEqual(MS.get_spec("fluffy").pf_type, 3)

    def test_no_unique_condition_is_declared(self):
        """本轮不新增固有状态 ⇒ 不需要 48×48 状态图标。"""
        self.assertNotIn(MS.UNIQUE_CONDITION_LOGICAL, K.SPEC["extra_keys"])

    def test_spec_declares_every_self_owned_key(self):
        declared = {t: set(v) for t, v in K.SPEC["extra_keys"].items()}
        self.assertEqual(declared[KL.CAS], set(K.CAS_TEXTS) - K.BASE_STRING_KEYS)
        self.assertEqual(K.BASE_STRING_KEYS, {K.SLOT_OVERRIDE[5]})
        self.assertEqual(K.SPEC["requires_client_base"], "1.4.998")
        self.assertEqual(declared[KL.SWITCHED], {K.VOICE_KEY})
        self.assertEqual(declared[K.PFA], {K.PF_KEY})
        # 629 与 722 的查找键必须在声明里，否则详情页 C8601
        for key in (K.INVOKE_STRING, K.PF_STRING, K.LEADER_OVERRIDE):
            self.assertIn(key, declared[KL.CAS])

    def test_row_and_record_counts(self):
        self.assertEqual(len(K.LEADER), K.LEADER_ROW_COUNT)
        self.assertEqual(sum(len(K.PLAN[s]) for s in range(1, 7)), K.ABILITY_RECORD_TOTAL)

    def test_desc_override_needs_the_panel_capability(self):
        self.assertIn("panel-description-override-v2", K.SPEC["required_capabilities"])


class PlanStaticTests(unittest.TestCase):
    """不碰基线也能查出来的行契约（裁决 §8 的自查清单）。"""

    def test_leader_plan_carries_no_forbidden_kind(self):
        """队长表禁 422/724/713（写进去 = 角色页 C7050）。"""
        for n, (_donor, _src, cells, _desc) in enumerate(K.LEADER):
            for col in (45, 107):
                self.assertNotIn(str(cells.get(col, "")), ("422", "724", "713"),
                                 f"leader#{n} 写了禁用 kind")

    def test_fever_kind_stays_out_and_dash_is_leader_scoped(self):
        """不引入724；新增422只允许队长位的Swift抵消。"""
        for slot in range(1, 7):
            for _donor, _src, cells, _desc in K.PLAN[slot]:
                self.assertNotEqual(str(cells.get(109, "")), "724")
                if cells.get(109) == "422":
                    self.assertEqual((cells[6], cells[97], cells[118]), ("42", "34", "0"))

    def test_slot3_is_main_position_only(self):
        for _donor, _src, cells, _desc in K.PLAN[3]:
            self.assertEqual(cells[1], "false", "槽 3 是 Ⓜ 主位限制键")
        for slot in (1, 2, 4, 5, 6):
            for _donor, _src, cells, _desc in K.PLAN[slot]:
                self.assertEqual(cells.get(1, "true"), "true")

    def test_statue_group_is_single_valued_per_key(self):
        """ability c2 每键单值（裁决 §8：官方 790 个多记录键 0 个混用）。"""
        for slot in range(1, 7):
            groups = {cells[2] for _d, _s, cells, _e in K.PLAN[slot]}
            self.assertEqual(len(groups), 1, f"槽 {slot} 的 c2 混用了 {groups}")

    def test_invoke_rows_carry_a_string_key_and_the_same_program(self):
        """629 行必须配字符串键；队长与词条两处指向同一棵 ability_skill 树。

        kind 629 本身来自 donor（官方 111165#4 / 1611053#0），``cells`` 里看不到 ⇒
        用只有 629 行才会写的字符串键列（leader c68/c69、ability c70/c71）来认。
        """
        leader = [cells for _d, _s, cells, _e in K.LEADER if 68 in cells]
        ability = [cells for _d, _s, cells, _e in K.PLAN[3] if 71 in cells]
        self.assertEqual(len(leader), 1)
        self.assertEqual(len(ability), 1)
        self.assertEqual(leader[0][68], K.INVOKE_STRING)
        self.assertEqual(leader[0][69], K.INVOKE_PROGRAM)
        self.assertEqual(ability[0][70], K.INVOKE_STRING)
        self.assertEqual(ability[0][71], K.INVOKE_PROGRAM)

    def test_trigger65_pair_shares_threshold_and_cooltime(self):
        """L#7（226 连击＋500）与 L#8（629）是同触发两行，阈值/CT 必须逐格一致（A 卡 §3.4）。"""
        pair = [cells for _d, _s, cells, _e in K.LEADER if cells.get(25) == "65" or 68 in cells]
        self.assertEqual(len(pair), 2)
        a, b = pair
        for col in (28, 29, 33):
            self.assertEqual(a[col], b[col], f"c{col} 不一致会出现「加了连击没放技能」")
        self.assertEqual(a[33], "360", "CT 6 秒 = 360 帧")

    def test_lv3_pair_checker_catches_drift(self):
        rows = [[""] * 124 for _ in range(2)]
        for row, kind in zip(rows, ("226", "629")):
            row[25], row[28], row[29], row[33], row[45] = "65", "500000", "500000", "600", kind
        rows[1][68], rows[1][69] = K.INVOKE_STRING, K.INVOKE_PROGRAM
        K._check_lv3_pair(rows)                                   # 一致 ⇒ 过
        drifted = copy.deepcopy(rows)
        drifted[1][33] = "900"
        with self.assertRaises(KL.KitError):
            K._check_lv3_pair(drifted)
        swapped = [copy.deepcopy(rows[1]), copy.deepcopy(rows[0])]
        with self.assertRaises(KL.KitError):
            K._check_lv3_pair(swapped)                            # 629 排在 226 之前 ⇒ 拒绝

    def test_forbidden_leader_kind_checker(self):
        row = [""] * 124
        row[45] = "422"
        with self.assertRaises(KL.KitError):
            K._ban_forbidden_leader_kinds([row])

    def test_order_checker_requires_the_invoke_row(self):
        row = [""] * 126
        row[47] = "33"
        with self.assertRaises(KL.KitError):
            K._order_problems([row])

    def test_wind_gate_is_the_official_resonance_precondition(self):
        """作者补充 09-21：本轮带门槛的条目一律用「X 属性共鸣」＝前置 kind 2 编成≥6。"""
        self.assertEqual(K.WIND_LEADER, {4: "2", 7: "600000", 8: "600000", 9: "Green"})
        self.assertEqual(K.WIND_ABILITY, {6: "2", 9: "600000", 10: "600000", 11: "Green"})


class PanelTextTests(unittest.TestCase):
    def test_every_override_line_obeys_the_batch_rules(self):
        for key, text in K.CAS_TEXTS.items():
            for line in text.split("\n"):
                KL.check_panel(line.replace(K.MAIN_ICON, ""),
                               skill_flag=key in K.SKILL_FLAG_TEXT_KEYS, label=key)

    def test_skill_flag_entries_carry_no_number_or_time(self):
        """裁决 §3：能力里的「技能强化」条目不写数字与时间。"""
        for key in K.SKILL_FLAG_TEXT_KEYS:
            self.assertEqual(KL.panel_problems(K.CAS_TEXTS[key], skill_flag=True), [])

    def test_slot3_override_lines_carry_the_main_position_icon(self):
        """desc_override 会盖掉客户端逐行画的 Ⓜ ⇒ 主位键必须自带图标。"""
        for line in K.CAS_TEXTS[K.SLOT_OVERRIDE[3]].split("\n"):
            self.assertTrue(line.startswith(K.MAIN_ICON))
        for slot in (1, 2):
            for line in K.CAS_TEXTS[K.SLOT_OVERRIDE[slot]].split("\n"):
                self.assertFalse(line.startswith(K.MAIN_ICON))

    def test_leader_override_matches_the_target_panel(self):
        """队长 override 逐行对齐 rework1/panel/fluffy.json（首行是偏离 D-1 的 722 说明）。"""
        lines = K.CAS_TEXTS[K.LEADER_OVERRIDE].split("\n")
        want = [entry["text"] for entry in PANEL["leader"]["lines"]]
        self.assertEqual(lines, want)

    def test_slot_overrides_match_the_target_panel(self):
        by_index = {entry["index"]: entry for entry in PANEL["abilities"]}
        for slot in K.SLOT_OVERRIDE_SLOTS:
            got = [line.replace(K.MAIN_ICON, "")
                   for line in K.CAS_TEXTS[K.SLOT_OVERRIDE[slot]].split("\n")]
            want = [line["text"] for line in by_index[slot]["lines"]]
            self.assertEqual(got, want, f"槽 {slot} 面板文字与目标面板不一致")

    def test_auto_text_slots_match_the_target_panel(self):
        by_index = {entry["index"]: entry for entry in PANEL["abilities"]}
        for slot, lines in K.PANEL_AUTO.items():
            want = tuple(line["text"] for line in by_index[slot]["lines"])
            self.assertEqual(lines, want)

    def test_main_only_flags_match_the_target_panel(self):
        by_index = {entry["index"]: entry for entry in PANEL["abilities"]}
        for slot in range(1, 7):
            want_main_only = bool(by_index[slot]["main_only"])
            got = K.PLAN[slot][0][2][1] == "false"
            self.assertEqual(got, want_main_only, f"槽 {slot} 的主位限制与目标面板不一致")

    def test_skill_texts_match_the_target_panel(self):
        self.assertEqual(K.TEXTS["skill1"], PANEL["skill"]["name"])
        self.assertEqual(K.TEXTS["skill2"], PANEL["skill"]["name"])
        self.assertEqual(K.TEXTS["desc1"], PANEL["skill"]["lines"][0]["text"])
        self.assertEqual(K.TEXTS["desc2"], K.TEXTS["desc1"])
        self.assertIn("65", K.TEXTS["desc1"])

    def test_skill_total_matches_the_number_written_on_the_panel(self):
        self.assertEqual(K.SKILL_TOTAL_NO_FLAG, 90.0)
        for level in ("1", "2"):
            mult = K.SKILL_MULT[level]
            total = sum(mult[seg]["max"] * K.HITS[seg] for seg in K.HITS)
            self.assertAlmostEqual(total, K.SKILL_TOTAL_NO_FLAG, places=6)

    def test_rows_are_flattened_to_a_single_max_value(self):
        """满级单值、行拉平（min=max）⇒ 面板文字与真实数值逐字一致。

        队长表与词条表列位不同：队长的阈值 min/max 是 c28/c29，词条的是 c30/c31，
        而词条的 c28/c29 是 **puller**（种类 + 组名，官方 SkillHit 行就是 ``'0'`` / ``''``），
        拿它当 min/max 对比会误报。
        """
        common = ((49, 50), (51, 52), (113, 114))
        for label, plan, pairs in [("leader", [e[2] for e in K.LEADER], common + ((28, 29),))] + \
                [(f"slot{s}", [e[2] for e in K.PLAN[s]], common + ((30, 31),))
                 for s in range(1, 7)]:
            for cells in plan:
                for lo, hi in pairs:
                    if lo in cells and hi in cells:
                        self.assertEqual(cells[lo], cells[hi], f"{label} c{lo}/c{hi} 没拉平")

    def test_both_skill_levels_are_identical(self):
        self.assertEqual(K.SKILL_MULT["1"], K.SKILL_MULT["2"])


class DslToolTests(unittest.TestCase):
    def test_wait_event_shape(self):
        node = K.wait_event(20, [["ShakeCamera", 1]])
        self.assertEqual(node[0], "Event")
        self.assertEqual(node[1][:3], ["Wait", 20, "*"])
        self.assertEqual(node[1][3], ["Block", [["Command", ["ShakeCamera", 1]]]])
        self.assertEqual(K.signature_problems(node), [])

    def test_signature_gate_rejects_bare_number_in_array_param(self):
        """裸数值塞进 Array 参 = 详情页/进战斗 F1034，AMF3 往返自检抓不到。"""
        good = ["Command", ["CreateNormalAttack", 7, 255, [], [], 3, [{"min": 1, "max": 1}],
                            [{"min": 0, "max": 0}], False, False, False, False, False,
                            [{"min": 1, "max": 1}], [{"min": 1, "max": 1}], ["Fine"], True]]
        self.assertEqual(K.signature_problems(good), [])
        bad = copy.deepcopy(good)
        bad[1][6] = 1.0                                        # p6 应是 Array
        problems = K.signature_problems(bad)
        self.assertTrue(any("p6" in p and "Array" in p for p in problems), problems)

    def test_signature_gate_rejects_unknown_construct_names(self):
        """构造名写错不报错也不崩，节点被静默吞掉（记忆卡 wf-dsl-command-wait-trace-trap）。"""
        self.assertTrue(K.signature_problems(["Command", ["Wait", 30]]))
        self.assertTrue(K.signature_problems(["Command", ["ShakeCamara", 1]]))
        self.assertTrue(K.signature_problems(["Command", ["ShakeCamera", 1, 2]]))

    def test_signature_gate_rejects_donothing_branch(self):
        """``["DoNothing"]`` 是 IfTargetNotFound 的枚举，写进 Conditionals 分支 = F1009。"""
        bad = ["Command", ["ConditionalsChangeSkillFlag", 1, ["Block", []], ["DoNothing"]]]
        problems = K.signature_problems(bad)
        self.assertTrue(any("p3" in p and "ActionDslExpression" in p for p in problems), problems)
        good = ["Command", ["ConditionalsChangeSkillFlag", 1, ["Block", []], ["Block", []]]]
        self.assertEqual(K.signature_problems(good), [])

    def test_add_combo_uses_the_alv2_channel(self):
        """704 没开时 ALv 项返回 0 ⇒ 加 0 连击；开了才加 50（客户端 Environment case 2）。"""
        cmd = K.add_combo_cmd()
        self.assertEqual(cmd[0], "AddCombo")
        self.assertEqual(K.signature_problems(["Command", cmd]), [])
        value = cmd[1][0]
        self.assertEqual((value["min"], value["max"]), (0.0, 0.0))
        self.assertEqual((value["alv2_min"], value["alv2_max"]), (55.0, 55.0))

    def test_roundtrip_gate_rejects_the_wrapper_shell(self):
        """``encode_amf3`` 只吃裸树；喂 ``{tree, numbers}`` 壳 = 进战斗 F1034。"""
        tree = ["ActionDsl", 3, ["None"], True, False, False, False, False, False, False, 0,
                ["Block", [["Command", ["ShakeCamera", 1]]]]]
        self.assertEqual(K.roundtrip_problems(tree), [])       # 裸树自身往返一致
        shell = {"tree": tree, "numbers": []}
        # 壳自己也「往返一致」——这正是往返自检抓不到它的原因（记忆卡原话）
        self.assertEqual(K.roundtrip_problems(shell), [])
        # 真正拦住它的是落盘前的形状断言与落盘后的回读比对
        with self.assertRaises(KL.KitError):
            K._write_dsl_checked(None, "x$y", shell)
        self.assertNotEqual(wf_dsl.parse_dsl(wf_dsl.encode_amf3(shell))["tree"], tree)
        self.assertGreater(K.MIN_ENCODED_BYTES, K.encoded_size(tree))

    def test_effect_refs_collects_both_resolver_shapes(self):
        tree = ["Block", [
            ["Command", ["ShowEffect", "a", ["SpecifyEffectDirectly", "x/y"], 1]],
            ["Command", ["ShowEffect", "b", ["ResolveByElement", "p/q", 4], 2]],
        ]]
        self.assertEqual(K.effect_refs(tree), ["x/y", "p/q"])

    def test_jab_family_is_direct_referenced_by_default(self):
        """施工单偏离 D-7：jab 族不克隆，走官方路径直接引用（图集预算）。"""
        self.assertFalse(K.CLONE_JAB_FAMILY)
        self.assertEqual([f[0] for f in K.FX_FAMILIES], ["rush"])
        for base in K.FX_JAB[2]:
            self.assertIn(f"{K.FX_JAB[1]}/{base}", K.FX_DIRECT_REFERENCE)


# ---------------------------------------------------------------- 2. 官方基线

@unittest.skipUnless(_BASELINE, "需要 .cdn/cn 官方归档与 live store")
class RowAssemblyTests(unittest.TestCase):
    def test_gauge_restriction_is_independent_of_hp_and_resonance(self):
        rows, _ = K.build_ability_rows(ctx())
        rule, = [row for row in rows[f"{K.CID}2"] if row[109] == "423"]
        self.assertEqual([rule[i] for i in (6, 13, 20)], ["0"] * 3)
        self.assertEqual(rule[97:102], ["0", "0", "", "0", "0"])
        self.assertEqual((rule[110], rule[118]), ("5", "12"))
        self.assertEqual(rule[1], "true")  # Both main and unison share the restriction.

    def test_leader_rows_render_exactly_as_planned(self):
        for n, (donor, source, cells, expect) in enumerate(K.LEADER):
            row, ev = KL.build_row(ctx(), "leader_ability", donor, cells, source=source,
                                   expect_describe=expect, label=f"L#{n}")
            self.assertEqual(row[0], K.CODE)
            self.assertEqual(ev["describe"], expect)

    def test_ability_rows_render_exactly_as_planned(self):
        for slot in range(1, 7):
            rows = []
            for n, (donor, source, cells, expect) in enumerate(K.PLAN[slot]):
                row, ev = KL.build_row(ctx(), "ability", donor, cells, source=source,
                                       element=K.ELEMENT, expect_describe=expect,
                                       label=f"A{slot}#{n}")
                self.assertEqual(ev["describe"], expect)
                rows.append(row)
            KL.check_ability_key(rows, f"{K.CID}{slot}", K.CODE, slot)

    def test_slot6_lost_its_second_record(self):
        """作者：「能力 6 的除自身外风属性角色技能槽＋5% 去掉」。"""
        self.assertEqual(len(K.PLAN[6]), 1)

    def test_slot3_was_replaced_wholesale(self):
        """作者用「能力 3，…」整段给出新内容 ⇒ 5 条全新行；反馈轮 1 再加 1 条清空连击。"""
        self.assertEqual(len(K.PLAN[3]), 6)
        # 六条的落点：during 技伤门 / PF 加连击 / 629 追击 / 694 独立乘区 / 704 换技能 Flag2 / 390 清空连击
        self.assertTrue(any(cells.get(70) == K.CAS_FLAG2 for _d, _s, cells, _e in K.PLAN[3]))
        self.assertTrue(any(71 in cells for _d, _s, cells, _e in K.PLAN[3]))
        descs = [desc for _d, _s, _c, desc in K.PLAN[3]]
        self.assertTrue(any("独立乘区技能伤害" in d for d in descs), descs)


class ComboResetPlanTests(unittest.TestCase):
    """反馈轮 1：「自身技能打完最后一段后会清空连击数」的行契约（不碰基线）。"""

    def _reset_cells(self):
        # kind 390 来自 donor（计划里不写 c47）⇒ 按 donor 名定位这一行
        hits = [cells for donor, _s, cells, _e in K.PLAN[3] if donor == "1410151#1"]
        self.assertEqual(len(hits), 1, "能力 3 应当只有一条 SetCombo 行")
        return hits[0]

    def test_row_uses_the_only_official_setcombo_donor(self):
        donors = [donor for donor, _s, _c, _e in K.PLAN[3]]
        self.assertIn("1410151#1", donors,
                      "kind 390 SetCombo 官方全库只有精灵公主 1410151#1 一行先例")

    def test_trigger_is_skill_hit_with_threshold_one(self):
        cells = self._reset_cells()
        self.assertEqual(cells[27], K.COMBO_RESET_TRIGGER, "必须是 107 SkillHit")
        self.assertEqual((cells[30], cells[31]),
                         (K.COMBO_RESET_THRESHOLD, K.COMBO_RESET_THRESHOLD))
        self.assertEqual(cells[28], "0", "官方 11 行 SkillHit 先例的 puller 都是 Myself")
        self.assertEqual(cells[34], "(None)", "每次技能都要清，不能设次数上限")

    def test_value_is_zero_and_row_is_main_only(self):
        cells = self._reset_cells()
        self.assertEqual((cells[51], cells[52]), ("0", "0"), "非 0 就不是清空")
        self.assertEqual(cells[1], "false", "落在 Ⓜ 能力 3：副位不清空（副位也没有 ＋50 连击）")
        for col, want in K.WIND_ABILITY.items():
            self.assertEqual(cells[col], want, "与同槽其余行同一道风共鸣门")

    def test_checker_rejects_a_wrong_trigger(self):
        rows = [[""] * KL.ABILITY_NCOLS for _ in range(2)]
        rows[0][47], rows[0][70], rows[0][71], rows[0][1] = "629", K.INVOKE_STRING, \
            K.INVOKE_PROGRAM, "false"
        rows[1][47] = K.COMBO_RESET_KIND
        rows[1][27] = "23"                       # SkillInvoke：技能开始时，不是最后一段之后
        rows[1][30] = rows[1][31] = K.COMBO_RESET_THRESHOLD
        rows[1][51] = rows[1][52] = K.COMBO_RESET_VALUE
        rows[1][28], rows[1][34] = "0", "(None)"
        with self.assertRaises(KL.KitError):
            K._order_problems(rows)

    def test_checker_rejects_a_nonzero_value(self):
        rows = [[""] * KL.ABILITY_NCOLS for _ in range(2)]
        rows[0][47], rows[0][70], rows[0][71], rows[0][1] = "629", K.INVOKE_STRING, \
            K.INVOKE_PROGRAM, "false"
        rows[1][47], rows[1][27] = K.COMBO_RESET_KIND, K.COMBO_RESET_TRIGGER
        rows[1][30] = rows[1][31] = K.COMBO_RESET_THRESHOLD
        rows[1][28], rows[1][34] = "0", "(None)"
        rows[1][51] = rows[1][52] = "100000"     # 把连击钉到 1，不是清空
        with self.assertRaises(KL.KitError):
            K._order_problems(rows)

    def test_panel_line_is_on_the_main_only_slot(self):
        lines = K.CAS_TEXTS[K.SLOT_OVERRIDE[3]].split("\n")
        self.assertTrue(lines[-1].endswith("自身技能的最后一击结束后，连击数归零"), lines[-1])
        self.assertTrue(lines[-1].startswith(K.MAIN_ICON), "能力 3 每行都要带 Ⓜ 图标")
        self.assertEqual([l["text"] for l in PANEL["abilities"][2]["lines"]],
                         [l.replace(K.MAIN_ICON, "") for l in lines])


@unittest.skipUnless(_BASELINE, "需要 .cdn/cn 官方归档与 live store")
class SkillTreeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trees, cls.gates = {}, {}
        for level in ("1", "2"):
            base = ctx().template_dsl(f"{K.PROGRAM_DIR}/{K.TEMPLATE_CODE}$"
                                      f"{K.TEMPLATE_CODE}_{level}")
            xm = ctx().template_dsl(f"{K.PROGRAM_DIR}/{K.GRAFT_CODE}${K.GRAFT_CODE}_{level}")
            cls.trees[level], cls.gates[level] = K.graft_tree(base, xm, level)

    def test_root_head_is_untouched(self):
        for level, tree in self.trees.items():
            self.assertEqual(tree[:2], ["ActionDsl", 3], level)
            self.assertEqual(tree[10], 0, "tree[10]=0 ⇒ 自动档＝技能伤害归属")

    # 嫁接来的八段：前四段 id +ID_SHIFT（11/14/17/20），后四段再 +ID_SHIFT_2（41/44/47/50）
    PESTLE_IDS = sorted([i + K.ID_SHIFT for i in K.GRAFT_PESTLE_AREA_IDS]
                        + [i + K.ID_SHIFT + K.ID_SHIFT_2 for i in K.GRAFT_PESTLE_AREA_IDS])

    def test_pestle_segments_were_doubled(self):
        for level, tree in self.trees.items():
            areas = [a for a in wf_dsl.iter_dsl_commands(tree, "CreateHitArea")
                     if a[19] in self.PESTLE_IDS]
            self.assertEqual(len(areas), 8, f"skill{level} 八连重击段数不对")
            self.assertEqual(sorted(a[19] for a in areas), self.PESTLE_IDS)
            self.assertEqual(self.gates[level]["segment_hits"]["pestle"], 8)

    def test_subject_ids_do_not_collide(self):
        """整棵树的判定区 id / 两个 bind id 必须互不相交（复制段数最容易在这里翻车）。"""
        for level, tree in self.trees.items():
            areas = list(wf_dsl.iter_dsl_commands(tree, "CreateHitArea"))
            ids = [a[19] for a in areas] + [a[21] for a in areas] + [a[22] for a in areas]
            self.assertEqual(len(set(ids)), len(ids), f"skill{level} 主体 id 撞号")
            for want in self.PESTLE_IDS:
                self.assertIn(want, ids, f"skill{level} 少了嫁接段 {want}")

    def test_no_recoil_timing(self):
        """无后摇：停球/隐身/替身球压到裂地一击之后第 3 帧，参考点寿命仍覆盖判定窗口。"""
        for level, tree in self.trees.items():
            stop = next(iter(wf_dsl.iter_dsl_commands(tree, "StopBall")))
            hide = next(iter(wf_dsl.iter_dsl_commands(tree, "HideCharacter")))
            rp = next(iter(wf_dsl.iter_dsl_commands(tree, "CreateReferencePoint")))
            self.assertEqual(stop[2], K.FRAME_FINISHER + 3, level)
            self.assertEqual(hide[2], K.STOP_BALL_FRAMES, level)
            self.assertGreaterEqual(rp[9], K.FRAME_FINISHER + K.FINISHER_LIFETIME)
            self.assertLess(K.STOP_BALL_FRAMES, rp[9], "停球必须早于参考点寿命，否则谈不上无后摇")

    def test_add_combo_is_attached_to_every_hit_area(self):
        for level, tree in self.trees.items():
            combos = list(wf_dsl.iter_dsl_commands(tree, "AddCombo"))
            self.assertEqual(len(combos), 1 + K.HITS["pestle"] + 1, level)
            for cmd in combos:
                self.assertEqual(cmd[1][0]["alv2_max"], 55.0)

    def test_only_the_finisher_counts_as_a_skill_hit(self):
        """反馈轮 1：整棵树里只有裂地一击 ``incrementCombo=true``。

        这是「词条 390 阈值 1 ＝ 最后一段打完」的全部依据：客户端 ``EnemyImpl`` 只在
        ``incrementCombo`` 为真时才调 ``countUpSkillHit``。若哪天前面的段又开回 true，
        清空点会提前到技能中段，本断言必须先红。
        """
        for level, tree in self.trees.items():
            cnas = list(wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack"))
            counting = [c for c in cnas if c[K.CNA_INCREMENT_COMBO] is True]
            silent = [c for c in cnas if c[K.CNA_INCREMENT_COMBO] is False]
            self.assertEqual(len(cnas), 1 + K.HITS["pestle"] + 2, level)
            self.assertEqual(len(silent), 9, f"skill{level} 精准连击 + 八连重击应当全部静音")
            # then/else 两支是同一击的副本 ⇒ 实际计数的只有裂地一击本身
            self.assertEqual(len(counting), 2, level)
            for cna in counting:
                self.assertAlmostEqual(cna[6][0]["max"], K.SKILL_MULT[level]["finisher"]["max"])
            self.assertEqual(self.gates[level]["skill_hit_counting_cna"]["silent"], 9)

    def test_the_invoke_tree_inherits_the_same_counting_layout(self):
        """629 追击版跑的是同一棵树 ⇒ 它打完最后一段同样清空（作者「自身技能」按字面两者都算）。"""
        invoke, _ev = K.build_invoke_tree(self.trees["2"])
        cnas = list(wf_dsl.iter_dsl_commands(invoke, "CreateNormalAttack"))
        self.assertEqual(len([c for c in cnas if c[K.CNA_INCREMENT_COMBO] is True]), 2)
        self.assertEqual(len([c for c in cnas if c[K.CNA_INCREMENT_COMBO] is False]), 9)

    def test_totals_match_the_panel(self):
        for level in ("1", "2"):
            self.assertAlmostEqual(self.gates[level]["total_no_flag"], 90.0, places=4)
            self.assertAlmostEqual(self.gates[level]["total_with_flag1"], 96.0, places=4)

    def test_finisher_branches_are_complete_blocks(self):
        """536 开关：then 支 p8=true 吃连击加成，else 支 p8=false；禁 ["DoNothing"]。"""
        for level, tree in self.trees.items():
            cond = list(wf_dsl.iter_dsl_commands(tree, "ConditionalsChangeSkillFlag"))
            self.assertEqual(len(cond), 1, level)
            self.assertEqual(cond[0][1], 1)
            for branch in (cond[0][2], cond[0][3]):
                self.assertEqual(branch[0], "Block")
            then_cna = next(iter(wf_dsl.iter_dsl_commands(cond[0][2], "CreateNormalAttack")))
            else_cna = next(iter(wf_dsl.iter_dsl_commands(cond[0][3], "CreateNormalAttack")))
            self.assertTrue(then_cna[8])
            self.assertFalse(else_cna[8])

    def test_all_dsl_gates_pass_after_effect_rewrite(self):
        for level in ("1", "2"):
            tree, _ = K.build_skill_tree(ctx(), level, fake_families()) \
                if False else (self.trees[level], None)
            problems = K.dsl_problems(tree, element=K.ELEMENT) + K.roundtrip_problems(tree)
            # 特效引用此时仍是官方路径（rewrite 在 build_skill_tree 里做），只查其余闸门
            self.assertEqual([p for p in problems if not p.startswith("effect")], [], level)

    def test_graft_rejects_a_drifted_donor(self):
        base = copy.deepcopy(ctx().template_dsl(
            f"{K.PROGRAM_DIR}/{K.TEMPLATE_CODE}${K.TEMPLATE_CODE}_2"))
        xm = ctx().template_dsl(f"{K.PROGRAM_DIR}/{K.GRAFT_CODE}${K.GRAFT_CODE}_2")
        next(iter(wf_dsl.iter_dsl_commands(base, "StopBall")))[2] = 31
        with self.assertRaises(KL.KitError):
            K.graft_tree(base, xm, "2")

    def test_invoke_tree_is_a_faithful_copy_of_the_skill(self):
        """629 树 = 技能档 2 深拷贝（rework1）＋ 2026-09-27 平衡第二批覆盖：全部 CNA p13 → 0.15。"""
        tree, gates = K.build_invoke_tree(self.trees["2"])
        expected = copy.deepcopy(self.trees["2"])
        for cna in wf_dsl.iter_dsl_commands(expected, "CreateNormalAttack"):
            cna[K.CNA_DETOUGHNESS] = [{"min": K.INVOKE_DETOUGHNESS, "max": K.INVOKE_DETOUGHNESS}]
        self.assertEqual(tree, expected)
        self.assertEqual(gates["damage_attribution"], 0)
        self.assertEqual(gates["detoughness"]["per_call"], 2.85)   # 19 段 × 0.15 ≤ 3（CT 6/12 秒）

    def test_pestle_detoughness_keeps_the_skill_within_thirty(self):
        """2026-09-27 平衡第二批（口径 B.1）：八连重击 p13 6.25 → 1.5，每次施放 65 → 27；其余段不动。"""
        for level, tree in self.trees.items():
            p13 = [cna[K.CNA_DETOUGHNESS][0]["max"]
                   for cna in wf_dsl.iter_dsl_commands(tree, "CreateNormalAttack")]
            self.assertEqual(p13[1:9], [K.PESTLE_DETOUGHNESS] * 8, level)
            self.assertAlmostEqual(p13[0], 15 / 11, places=9)      # 精准连击 ×10
            self.assertAlmostEqual(p13[9], 15 / 11, places=9)      # 裂地（then/else 副本）
            self.assertEqual(self.gates[level]["detoughness"]["per_cast"], 27.0)


@unittest.skipUnless(_BASELINE, "需要 .cdn/cn 官方归档与 live store")
class PowerFlipTests(unittest.TestCase):
    """722 双类型覆盖树：官方 fighter 底座 ＋ 官方 supporter 辅助增益块。"""

    @classmethod
    def setUpClass(cls):
        cls.trees, cls.gates = {}, {}
        for level in (1, 2, 3):
            cls.trees[level], cls.gates[level] = K.build_pf_tree(ctx(), level)

    def test_base_is_the_official_fighter_tree(self):
        for level, tree in self.trees.items():
            self.assertEqual(tree[1], 2, "拼树后 movementPriority 必须是 2")
            self.assertEqual(tree[10], 0)
            self.assertEqual(self.gates[level]["cna_total"], K.FIGHTER_CNA_TOTAL[level])

    def test_lifecycle_commands_survive(self):
        """覆盖树必须自带 SetPowerFilpSuppress ＋ NotifyPowerflipEnd，否则球卡死。"""
        for level, tree in self.trees.items():
            self.assertEqual([c[1] for c in wf_dsl.iter_dsl_commands(tree, "SetPowerFilpSuppress")],
                             K.FIGHTER_SUPPRESS[level])
            self.assertTrue(list(wf_dsl.iter_dsl_commands(tree, "NotifyPowerflipEnd")))

    def test_supporter_buff_block_was_grafted_in(self):
        for level, tree in self.trees.items():
            kinds = [c[2][0][0] for c in wf_dsl.iter_dsl_commands(tree, "CreateCondition")]
            for want in ("ACAttackPoint", "ACPiercing"):
                self.assertIn(want, kinds, f"lv{level} 丢了辅助增益 {want}")
            # 作者 09-21「芙拉菲也不要浮游」：成品树里不许再有 ACFlying
            self.assertNotIn("ACFlying", kinds, f"lv{level}")
            self.assertEqual(self.gates[level]["support_block_bind"], K.PF_SUPPORT_BIND)

    def test_hit_areas_keep_the_pf_multiplier_lane(self):
        """``CreateHitArea`` 第 24 位写 4 = 按直击算，整块 PF 乘区被跳过。"""
        for level, tree in self.trees.items():
            for cha in wf_dsl.iter_dsl_commands(tree, "CreateHitArea"):
                self.assertEqual(cha[24], 0, f"lv{level}")

    def test_no_package_local_effect_is_referenced(self):
        for level, tree in self.trees.items():
            for ref in K.effect_refs(tree):
                self.assertNotIn(f"skill_unique/{K.CODE}/", ref, f"lv{level} 引用了包内特效")


# ---------------------------------------------------------------- 3. workspace 回执

@unittest.skipUnless(_BASELINE, "需要 .cdn/cn 官方归档与 live store")
@unittest.skipUnless((WORKSPACE / "evidence" / "kit-report.json").is_file(),
                     "需要先跑 --step tables,kit,assets,manifest")
class WorkspaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = json.loads((WORKSPACE / "evidence" / "kit-report.json").read_text("utf-8"))
        cls.gates = json.loads((WORKSPACE / "evidence" / "kit-gates.json").read_text("utf-8"))

    def test_report_identity_and_capabilities(self):
        self.assertEqual((self.report["cid"], self.report["code"]), (K.CID, K.CODE))
        self.assertEqual(set(self.report["required_capabilities"]), {"panel-description-override-v2", "dash-parameter-v1", "gauge-gain-rules-v1"})

    def test_every_program_is_written(self):
        programs = self.report["skills"]["programs"]
        for level in ("1", "2"):
            self.assertTrue(any(f"{K.CODE}${K.CODE}_{level}." in p for p in programs), programs)
        self.assertTrue(any(K.INVOKE_STRING in p for p in programs), programs)
        for program in K.PF_PROGRAMS:
            stem = program.split("/")[-1]
            self.assertTrue(any(stem in p for p in programs), (stem, programs))

    def test_power_flip_action_row_points_at_three_levels(self):
        pf = self.gates["power_flip"]
        self.assertEqual(pf["key"], K.PF_KEY)
        self.assertEqual(pf["programs"], list(K.PF_PROGRAMS))
        self.assertEqual(sorted(pf["levels"]), ["1", "2", "3"])

    def test_character_row_says_supporter(self):
        self.assertEqual(self.gates["mirrors"]["character"][6], "3")

    def test_voice_route_is_change_skill_flag(self):
        route = self.gates["voice_route"]
        self.assertEqual(route[0], "3")                     # kind 3 = ChangeSkillFlag
        self.assertEqual(route[5], K.VOICE_KEY)
        self.assertEqual(self.gates["voice_ready"]["levels"], ["1", "2"])

    def test_action_skill_energy_is_580_on_both_levels(self):
        for level, cells in self.gates["action_skill"].items():
            self.assertEqual((cells[4], cells[5]), ("580", "580"), level)

    def test_package_carries_only_its_own_ability_and_leader_keys(self):
        self.assertEqual(sorted(self.gates["ability"]["rows"]), sorted(K.ABILITY_KEYS))
        self.assertEqual(len(self.gates["leader"]["rows"]), K.LEADER_ROW_COUNT)

    def test_panel_block_obeys_the_batch_rules(self):
        for line in self.report["panel"]:
            KL.check_panel(line.replace(K.MAIN_ICON, ""), label="report.panel")

    def test_deviations_are_registered(self):
        """做不到的条目不许静默降级（裁决 §6）。"""
        wants = [d["want"] for d in self.report["deviations"]]
        self.assertGreaterEqual(len(wants), 6)
        self.assertTrue(any("辅助＋格斗" in w for w in wants))

    def test_design_history_block_is_preserved(self):
        """rework1 的 plan 写在 design 的 ``rework1`` 段，旧 ``plan`` 留作历史。"""
        self.assertIn("plan", DESIGN)
        self.assertIn("rework1", DESIGN)
        self.assertEqual(DESIGN["rework1"]["leader_ability"]["row_count"], K.LEADER_ROW_COUNT)


if __name__ == "__main__":
    unittest.main()
