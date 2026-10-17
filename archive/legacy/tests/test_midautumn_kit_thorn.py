# -*- coding: utf-8 -*-
"""索恩 kit（159994 ``tweyen_light``）：设计稿自查 + 行装配 + 技能树门禁。

三组用例：

1. **纯静态**（不需要 live / 官方基线）：模块常量与 ``design/thorn.json`` 的互锁、裁决 §8 的
   设计自查（队长表禁 422/724/713、零固有状态、零 desc_override、词条 c1/c2 每键单值、
   during 136 的 puller 列留空、面板禁词），以及本模块的小工具
   （``design_row`` / ``donor_address`` / ``edits_from_donor`` / ``_write_dsl_checked`` 包装壳拦截）
   与设计稿登记的两棵成品树的结构自查（三条弱体的付与对象种类与 forceApply、抗性↓ 元素码 254、
   CNA 条件特攻、换尾的绑定一致性、特效路径全部落在官方 donor 族内）。
2. **官方基线**（缺 ``.cdn/cn`` 或 live store 时跳过）：15 行逐行装配并与设计登记的
   ``wf_describe`` 回读逐字比对；两棵技能树从官方 donor 重建后与设计稿逐节点一致、四道
   DSL 门全空、AMF3 编码往返逐字节一致。
3. **已构建的 workspace**（``work/character_packs/ma-thorn`` 不存在时跳过）：包内自有键、
   认领、kit-report、技能能量与施法目标列、语音路由、零克隆（包里不许出现特效族）。

不写 live store / ``assets/`` / ``.cdn``，不跑发布；官方基线与 workspace 只读。
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
import wf_midautumn_kit_thorn as K  # noqa: E402
import wf_midautumn_kitlib as KL  # noqa: E402
import wf_midautumn_specs as MS  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_seasonal7_build as B  # noqa: E402
import wf_seasonal7_common as C  # noqa: E402

ROOT = core.project_root()
DESIGN = MS.load_design(ROOT, "thorn")
WORKSPACE = ROOT / "work/character_packs/ma-thorn"
LEADER_PLAN = DESIGN["plan"]["leader_ability"]
ABILITY_PLAN = DESIGN["plan"]["ability"]
PROGRAMS = {str(p["level"]): p for p in DESIGN["plan"]["skills"]["programs"]}


def _baseline_available() -> bool:
    profile = core.resolve_profile()
    return profile is not None and profile.store.is_dir() and (ROOT / ".cdn" / "cn").is_dir()


_BASELINE = _baseline_available()
_CTX = None


def ctx():
    """只读上下文：``record_sources=False`` ⇒ 母本取数不写 workspace（框架 §10.2）。"""
    global _CTX
    if _CTX is None:
        _CTX = B.KitContext(MC.MAPack(MS.get_spec("thorn"), record_sources=False))
    return _CTX


def design_rows():
    """(kind, label, donor_spec, cells, desc_expected, changed) 六元组，队长在前词条在后。"""
    out = []
    for entry, spec in zip(LEADER_PLAN["rows"], K.LEADER_DONORS):
        out.append(("leader_ability", f"leader#{entry['index']}", spec["donor"], entry["cells"],
                    entry["desc_expected"], spec["changed"]))
    for key in K.ABILITY_KEYS:
        block = ABILITY_PLAN["keys"][key]
        for entry, spec in zip(block["records"], K.ABILITY_DONORS[key]):
            out.append(("ability", f"{key}#{entry['index']}", spec["donor"], entry["cells"],
                        entry["desc_expected"], spec["changed"]))
    return out


def conditions_of(tree, ac_name: str):
    return [c for c in wf_dsl.iter_dsl_commands(tree, "CreateCondition")
            if c[2] and isinstance(c[2][0], list) and c[2][0][0] == ac_name]


# ---------------------------------------------------------------- 1. 纯静态

class DesignInterlockTests(unittest.TestCase):
    """模块常量 ↔ 设计稿：任何一边单独改都要红。"""

    def test_identity(self):
        self.assertEqual((DESIGN["key"], DESIGN["cid"], DESIGN["code"]), (K.KEY, K.CID, K.CODE))
        spec = MS.get_spec("thorn")
        self.assertEqual((spec.cid, spec.code, spec.element), (K.CID, K.CODE, K.ELEMENT))
        self.assertEqual((spec.template_id, spec.template_code), (K.TEMPLATE_ID, K.TEMPLATE_CODE))
        self.assertEqual((spec.pf_type, spec.stance), (K.PF_TYPE, K.STANCE))
        self.assertEqual(MS.text_placeholders(spec), [])

    def test_row_counts_match_the_design(self):
        self.assertEqual(len(LEADER_PLAN["rows"]), K.LEADER_ROWS)
        self.assertEqual(len(K.LEADER_DONORS), K.LEADER_ROWS)
        self.assertEqual(sorted(ABILITY_PLAN["keys"]), sorted(K.ABILITY_KEYS))
        self.assertEqual(sorted(K.ABILITY_DONORS), sorted(K.ABILITY_KEYS))
        total = 0
        for key in K.ABILITY_KEYS:
            records = ABILITY_PLAN["keys"][key]["records"]
            self.assertEqual(len(records), len(K.ABILITY_DONORS[key]), key)
            total += len(records)
        self.assertEqual(total, K.ABILITY_RECORDS)

    def test_donor_keys_appear_in_the_design_prose(self):
        for entry, spec in zip(LEADER_PLAN["rows"], K.LEADER_DONORS):
            K.check_design_donor_text(entry, spec["donor"], "leader")
        for key in K.ABILITY_KEYS:
            block = ABILITY_PLAN["keys"][key]
            for entry, spec in zip(block["records"], K.ABILITY_DONORS[key]):
                K.check_design_donor_text(entry, spec["donor"], key)

    def test_extra_keys_declare_every_self_owned_key(self):
        spec = MS.get_spec("thorn")
        self.assertEqual(spec.extra_keys.get(KL.SWITCHED), (K.VOICE_KEY,))
        self.assertEqual(K.SPEC["extra_keys"][KL.SWITCHED], (K.VOICE_KEY,))
        # rework1：零固有状态，但多了 536 的 c70 串与四个槽的面板覆盖串。
        self.assertEqual(set(spec.extra_keys), {KL.SWITCHED, KL.CAS})
        want = (K.CAS_CHANGE_SKILL, *(K.CAS_ABILITY[s] for s in K.OVERRIDE_SLOTS))
        self.assertEqual(tuple(spec.extra_keys[KL.CAS]), want)
        self.assertEqual(K.SPEC["required_capabilities"], (L.PANEL_OVERRIDE_V2,))

    def test_voice_route_matches_the_design(self):
        route = DESIGN["voice"]["route"]
        self.assertEqual(int(route["kind"]), K.VOICE_ROUTE["kind"])
        self.assertEqual(str(route["threshold"]), K.VOICE_ROUTE["threshold"])
        cols = KL.voice_route(K.CODE, K.VOICE_ROUTE)
        self.assertEqual(cols[0], "0")
        self.assertEqual(cols[4], "0.5")
        self.assertEqual(cols[5], K.VOICE_KEY)
        self.assertEqual(len(DESIGN["voice"]["lines"]), 22)

    def test_energy_block_shape(self):
        energy = DESIGN["plan"]["skills"]["energy"]
        for level in ("1", "2"):
            pair = energy[f"lv{level}"]
            self.assertEqual(sorted(pair), ["c4", "c5"])
            self.assertTrue(int(pair["c4"]) > 0 and int(pair["c5"]) > 0)


class DesignSelfCheckTests(unittest.TestCase):
    """裁决 §8 要求的 kit 前自查，全部落在设计稿登记的成品行上。"""

    def test_leader_table_carries_no_forbidden_kind(self):
        rows = [K.design_row(entry["cells"], KL.LEADER_NCOLS, "leader")
                for entry in LEADER_PLAN["rows"]]
        K.ban_forbidden_leader_kinds(rows)
        for row in rows:
            self.assertNotIn(row[K.LEADER_INSTANT_KIND], K.FORBIDDEN_LEADER_KINDS)
            self.assertNotIn(row[K.LEADER_DURING_KIND], K.FORBIDDEN_LEADER_KINDS)

    def test_ban_forbidden_leader_kinds_actually_trips(self):
        row = K.design_row(LEADER_PLAN["rows"][0]["cells"], KL.LEADER_NCOLS, "leader")
        row[K.LEADER_INSTANT_KIND] = "422"
        with self.assertRaises(K.KitError):
            K.ban_forbidden_leader_kinds([row])

    def test_no_unique_condition_and_no_power_up_string(self):
        self.assertEqual(DESIGN["plan"]["unique_conditions"]["add"], [])
        texts = DESIGN["plan"]["texts"]
        self.assertEqual(texts["custom_ability_power_up_string"]["rows"], [])
        self.assertIsNone(texts["desc_override"]["value"])

    def test_custom_ability_string_mirrors_the_module(self):
        plan = {e["key"]: e["text"]
                for e in DESIGN["plan"]["texts"]["custom_ability_string"]["rows"]}
        want = {K.CAS_CHANGE_SKILL: K.CHANGE_SKILL_TEXT}
        for slot in K.OVERRIDE_SLOTS:
            uni = ABILITY_PLAN["keys"][f"{K.CID}{slot}"]["unisonable_per_record"][0]
            want[K.CAS_ABILITY[slot]] = K.override_text(slot, uni)
        self.assertEqual(plan, want)

    def test_panel_override_keys_follow_the_string_id_rule(self):
        for slot in K.OVERRIDE_SLOTS:
            key = f"{K.CID}{slot}"
            string_id = ABILITY_PLAN["keys"][key]["records"][0]["cells"]["c0"]
            self.assertEqual(K.CAS_ABILITY[slot], L.PANEL_OVERRIDE_KEY_PREFIX + string_id)
        # 能力 5／6 本轮未改，继续走客户端自渲染 ⇒ 不许偷偷多出覆盖串。
        self.assertEqual(K.OVERRIDE_SLOTS, (1, 2, 3, 4))

    def test_override_text_carries_the_main_only_icon(self):
        # 主位限定槽（c1=false）的覆盖文案每行都要自带 <icon id='main'>：desc_override 会盖掉
        # 客户端逐行画的角标，写成字面「Ⓜ」在客户端里只会渲成白色文字（作者 09-21 真机反馈）。
        slot3_lines = K.override_text(3, "false").split("\n")
        self.assertTrue(slot3_lines)
        for line in slot3_lines:
            self.assertTrue(line.startswith(K.MAIN_ICON), line)
        self.assertNotIn("Ⓜ", K.override_text(3, "false"))
        for line in K.override_text(1, "true").split("\n"):
            self.assertFalse(line.startswith(K.MAIN_ICON), line)
        self.assertNotIn("Ⓜ", K.override_text(1, "true"))
        for slot in K.OVERRIDE_SLOTS:
            uni = ABILITY_PLAN["keys"][f"{K.CID}{slot}"]["unisonable_per_record"][0]
            text = K.override_text(slot, uni)
            self.assertNotIn("Ⓜ", text, slot)
            lines = text.split("\n")
            # 多记录槽的覆盖串行数必须等于面板行数（换行分行，不许挤成一行）。
            self.assertEqual(len(lines), len(K.PANEL_ABILITY[slot]), slot)

    def test_change_skill_string_is_a_skill_flag_entry(self):
        # 裁决 §3：技能强化条目不写数字与时间。
        self.assertEqual(KL.panel_problems(K.CHANGE_SKILL_TEXT, skill_flag=True), [])
        rows = [K.design_row(r["cells"], KL.ABILITY_NCOLS, "x")
                for key in K.ABILITY_KEYS for r in ABILITY_PLAN["keys"][key]["records"]]
        flagged = [r for r in rows if r[47] == "536"]
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0][70], K.CAS_CHANGE_SKILL)

    def test_resonance_rows_really_carry_the_resonance_precondition(self):
        ability = {key: [K.design_row(r["cells"], KL.ABILITY_NCOLS, key)
                         for r in ABILITY_PLAN["keys"][key]["records"]] for key in K.ABILITY_KEYS}
        checked = K.check_resonance_rows(ability)
        self.assertEqual(len(checked), len(K.RESONANCE_ROWS))
        bad = copy.deepcopy(ability)
        key, index = K.RESONANCE_ROWS[0]
        bad[key][index][6] = "0"
        with self.assertRaises(K.KitError):
            K.check_resonance_rows(bad)

    def test_self_skill_panel_rows_trigger_on_self(self):
        """平衡第二批（2026-09-27，作者「索恩改成自身发动技能」）：面板写「自身发动技能时」的
        能力 3 #0–#2 触发方必须是自身（c27=23、c28=0、c29 空）；#4/#5「光属性角色发动技能时」保持 7+White。"""
        ability = {key: [K.design_row(r["cells"], KL.ABILITY_NCOLS, key)
                         for r in ABILITY_PLAN["keys"][key]["records"]] for key in K.ABILITY_KEYS}
        checked = K.check_self_trigger_rows(ability)
        self.assertEqual(checked, [f"{key}#{index}" for key, index in K.SELF_TRIGGER_ROWS])
        # 2026-09-27 第三轮面板合并（wf_balance_20260927c_panels）：#1/#2 同条件并入面板第2行 ⇒ 记录→面板行映射。
        panel_line = {0: 0, 1: 1, 2: 1}
        for _key, index in K.SELF_TRIGGER_ROWS:
            self.assertTrue(K.PANEL_ABILITY[3][panel_line[index]].startswith("自身发动技能时："), index)
        slot3 = ability[f"{K.CID}3"]
        for index in (4, 5):
            self.assertEqual(slot3[index][27:30], ["23", "7", "White"], index)
            self.assertIn("光属性角色发动技能时", K.PANEL_ABILITY[3][-1])
        bad = copy.deepcopy(ability)
        bad[f"{K.CID}3"][1][28], bad[f"{K.CID}3"][1][29] = "7", "White"
        with self.assertRaises(K.KitError):
            K.check_self_trigger_rows(bad)

    def test_overridden_slots_are_flattened_to_the_max_level_value(self):
        """覆盖文案写的是满级单值 ⇒ 对应行必须 min = max（记忆卡 wf-leader-override-text-rules）。"""
        for slot in K.OVERRIDE_SLOTS:
            key = f"{K.CID}{slot}"
            for record in ABILITY_PLAN["keys"][key]["records"]:
                row = K.design_row(record["cells"], KL.ABILITY_NCOLS, key)
                for low, high in ((51, 52), (113, 114)):
                    if row[low] or row[high]:
                        self.assertEqual(row[low], row[high], f"{key} c{low}/c{high}")

    def test_ability_4_uses_the_three_independent_multiplier_slayers(self):
        rows = [K.design_row(r["cells"], KL.ABILITY_NCOLS, "4")
                for r in ABILITY_PLAN["keys"][f"{K.CID}4"]["records"]]
        # 118 麻痹 / 53 眩晕畏缩(气绝) / 119 冻结(迟缓)，都是 P4 独立乘区池（研究卡 B §6.6）
        self.assertEqual([r[47] for r in rows], ["118", "53", "119"])
        for row in rows:
            self.assertEqual(row[48], "5")          # target 5 = 全队
            self.assertEqual(row[49], "White")
            self.assertEqual((row[51], row[52]), ("15000", "15000"))

    def test_no_limit_rows_use_the_none_sentinel_not_an_empty_string(self):
        """「不设置上限」= 上限列写 ``(None)``；留空串 ⇒ parseInt("") = 0 ⇒ 整行零收益。"""
        for key, index in ((f"{K.CID}2", 0), (f"{K.CID}3", 3)):
            row = K.design_row(ABILITY_PLAN["keys"][key]["records"][index]["cells"],
                               KL.ABILITY_NCOLS, key)
            self.assertEqual(row[97], K.DURING_DEBUFF_COUNT_KIND)
            self.assertEqual(row[102], "(None)", f"{key}#{index}")

    def test_ability_c1_c2_are_single_valued_per_key(self):
        for key in K.ABILITY_KEYS:
            block = ABILITY_PLAN["keys"][key]
            rows = [K.design_row(r["cells"], KL.ABILITY_NCOLS, key) for r in block["records"]]
            self.assertEqual(len({r[1] for r in rows}), 1, key)
            self.assertEqual(len({r[2] for r in rows}), 1, key)
            self.assertIn(rows[0][2], L.ABILITY_STATUE_GROUPS, key)
            self.assertEqual(rows[0][2], str(block["statue_group"]), key)
            slot = key[-1]
            for row in rows:
                self.assertEqual(row[0], f"{K.CODE}_{slot}")

    def test_during_136_leaves_the_puller_columns_empty(self):
        leader = [K.design_row(e["cells"], KL.LEADER_NCOLS, "leader") for e in LEADER_PLAN["rows"]]
        ability = {key: [K.design_row(r["cells"], KL.ABILITY_NCOLS, key)
                         for r in ABILITY_PLAN["keys"][key]["records"]] for key in K.ABILITY_KEYS}
        checked = K.check_during_pullers(leader, ability)
        self.assertEqual(len(checked), 4)          # 队长 L1/L2 + 词条 2#0 + 词条 3#3
        bad = copy.deepcopy(leader)
        bad[1][K.LEADER_DURING_PULLER[0]] = "1"
        with self.assertRaises(K.KitError):
            K.check_during_pullers(bad, ability)

    def test_panel_texts_pass_the_batch_rules(self):
        for _kind, label, _donor, _cells, expect, _changed in design_rows():
            self.assertEqual(KL.panel_problems(expect), [], f"{label}: {expect}")
        spec = MS.get_spec("thorn")
        for name in ("title", "profile", "leader", "skill1", "desc1", "skill2", "desc2"):
            self.assertEqual(KL.panel_problems(spec.texts[name]), [], name)

    def test_element_columns_are_light(self):
        for key in K.ABILITY_KEYS:
            for record in ABILITY_PLAN["keys"][key]["records"]:
                row = K.design_row(record["cells"], KL.ABILITY_NCOLS, key)
                self.assertEqual(L.ability_element_column_problems("ability", row, K.ELEMENT), [])


class HelperTests(unittest.TestCase):
    def test_design_row_rejects_out_of_range_columns(self):
        with self.assertRaises(K.KitError):
            K.design_row({"c999": "1"}, KL.ABILITY_NCOLS, "x")
        row = K.design_row({"c0": "a", "c3": 7}, 5, "x")
        self.assertEqual(row, ["a", "", "", "7", ""])

    def test_donor_address_shapes(self):
        self.assertEqual(K.donor_address("151165#2"), ("151165", 2))
        for bad in ("151165", "151165#L1", "abc#0", "#0"):
            with self.assertRaises(K.KitError):
                K.donor_address(bad)

    def test_edits_from_donor_traps_unexpected_drift(self):
        donor = ["a", "b", "c"]
        want = ["a", "x", "c"]
        self.assertEqual(K.edits_from_donor(donor, want, (1,), "x"), {1: "x"})
        with self.assertRaises(K.KitError):
            K.edits_from_donor(donor, want, (2,), "x")
        with self.assertRaises(K.KitError):
            K.edits_from_donor(donor, ["a", "b", "c"], (1,), "x")

    def test_write_dsl_checked_rejects_the_wrapper_shape(self):
        class Boom:
            def write_dsl(self, *a, **kw):
                raise AssertionError("must not reach write_dsl")
        with self.assertRaises(K.KitError):
            K._write_dsl_checked(Boom(), "p", {"tree": [], "numbers": []})

    def test_find_statements_and_only(self):
        tree = ["Block", [["Command", ["A", 1]], ["Command", ["B", 2]], ["Command", ["A", 3]]]]
        self.assertEqual(len(K.find_statements(tree, "A")), 2)
        self.assertEqual(K._command(K._only(K.find_statements(tree, "B"), "B"))[1], 2)
        with self.assertRaises(K.KitError):
            K._only(K.find_statements(tree, "A"), "A")


class DesignTreeShapeTests(unittest.TestCase):
    """设计稿登记的两棵成品树的结构自查（不需要官方基线）。"""

    def test_root_and_onhit_shape(self):
        for level, entry in PROGRAMS.items():
            tree = entry["tree"]
            self.assertEqual(tree[0], "ActionDsl", level)
            self.assertEqual(tree[10], 0, level)        # 自动档＝技能伤害归属
            self.assertEqual(len(K._statements(tree)), K.KIT_ROOT_STATEMENTS, level)
            hit = K._command(K._only(K.find_statements(tree, "CreateHitArea"), "CreateHitArea"))
            self.assertEqual(len(hit), K.HIT_AREA_NCOLS, level)
            onhit = hit[K.HIT_AREA_ONHIT_SLOT]
            self.assertEqual(onhit[0], "Block", level)
            # rework1：震屏 + CNA + ConditionalsChangeSkillFlag + 抗性↓ = 4 条
            self.assertEqual(len(onhit[1]), K.ONHIT_DONOR_STATEMENTS + 2, level)

    def test_three_debuffs_are_bound_to_the_cna_subject(self):
        for level, entry in PROGRAMS.items():
            tree = entry["tree"]
            cna = K._command(K._only(K.find_statements(tree, "CreateNormalAttack"), "CNA"))
            self.assertEqual(cna[4], [["DCParalysis"]], level)
            # 麻痹/迟缓各两条（536 长时长分支 + 基础分支），抗性↓ 一条。
            for ac, count in (("ACParalysis", 2), ("ACFrozen", 2), ("ACToleranceOfElement", 1)):
                cmds = conditions_of(tree, ac)
                self.assertEqual(len(cmds), count, f"{level} {ac}")
                for cmd in cmds:
                    self.assertEqual(cmd[1], cna[1], f"{level} {ac}")
                    self.assertEqual(cmd[10], K.CONDITION_TARGET_KIND_ENEMY, f"{level} {ac}")
                    self.assertIs(cmd[12], K.CONDITION_FORCE_APPLY, f"{level} {ac}")

    def test_skill_flag_branch_shape(self):
        """536 开着走长时长分支；分支必须是完整 Block（禁 ``["DoNothing"]``）。"""
        for level, entry in PROGRAMS.items():
            branches = K.find_statements(entry["tree"], "ConditionalsChangeSkillFlag")
            self.assertEqual(len(branches), 1, level)
            cmd = K._command(branches[0])
            self.assertEqual(cmd[1], K.SKILL_FLAG_INDEX, level)
            values = K.SKILL_VALUES[level]
            for side, para, froz in ((2, "paralysis_long", "frozen_long"),
                                     (3, "paralysis", "frozen")):
                block = cmd[side]
                self.assertEqual(block[0], "Block", f"{level} side {side}")
                self.assertEqual(len(block[1]), 2, f"{level} side {side}")
                names = [K._command(s)[2][0][0] for s in block[1]]
                self.assertEqual(names, ["ACParalysis", "ACFrozen"], f"{level} side {side}")
                self.assertEqual(K._command(block[1][0])[2][0][1], K._range(values[para]))
                self.assertEqual(K._command(block[1][1])[2][0][1], K._range(values[froz]))
            # 强化档必须真的比基础档长，否则这条「大幅延长」就是空头支票。
            self.assertGreater(values["paralysis_long"][1], values["paralysis"][1], level)
            self.assertGreater(values["frozen_long"][1], values["frozen"][1], level)

    def test_skill_multiplier_is_fifty(self):
        self.assertEqual(K.SKILL_VALUES["2"]["cna"], (12.5, 12.5))
        self.assertEqual(K.SKILL_VALUES["2"]["cna"][1] * K.SKILL_SEGMENTS, K.SKILL_TOTAL_LV2)
        for level in ("1", "2"):
            low, high = K.SKILL_VALUES[level]["cna"]
            self.assertEqual(low, high, f"lv{level} 倍率未拉平成满级单值")

    def test_tolerance_uses_element_254(self):
        for level, entry in PROGRAMS.items():
            cmd = K._only(conditions_of(entry["tree"], "ACToleranceOfElement"), "tolerance")
            ac = cmd[2][0]
            self.assertEqual(ac[2], K.TOLERANCE_ELEMENT_ALL, level)
            self.assertEqual(ac[4], [{"min": K.TOLERANCE_STACKS, "max": K.TOLERANCE_STACKS}], level)
            self.assertLess(ac[3][0]["min"], 0, level)

    def test_tail_binding_is_consistent(self):
        for level, entry in PROGRAMS.items():
            tail = K._statements(entry["tree"])[2]
            cmd = K._command(tail)
            self.assertEqual(cmd[0], "FindAllSubjects", level)
            self.assertEqual((cmd[1], cmd[2], cmd[3]), (K.TAIL_BIND, K.TAIL_SELECTOR, K.TAIL_FILTER))
            inner = K._command(K._only(K.find_statements(cmd[9], "CreateCondition"), "tail"))
            self.assertEqual(inner[1], K.TAIL_BIND, level)     # lookup 位必须 = 绑定 id（防 C16103）
            self.assertEqual(inner[2][0][0], "ACSkillDamage", level)

    def test_design_values_match_the_module_constants(self):
        for level, entry in PROGRAMS.items():
            values = K.SKILL_VALUES[level]
            tree = entry["tree"]
            cna = K._command(K._only(K.find_statements(tree, "CreateNormalAttack"), "CNA"))
            self.assertEqual(cna[6], K._range(values["cna"]), level)
            self.assertEqual(sorted([c[2][0][1] for c in conditions_of(tree, "ACParalysis")],
                                    key=lambda v: v[0]["max"]),
                             sorted([K._range(values["paralysis"]),
                                     K._range(values["paralysis_long"])],
                                    key=lambda v: v[0]["max"]), level)
            self.assertEqual(sorted([c[2][0][1] for c in conditions_of(tree, "ACFrozen")],
                                    key=lambda v: v[0]["max"]),
                             sorted([K._range(values["frozen"]), K._range(values["frozen_long"])],
                                    key=lambda v: v[0]["max"]), level)

    def test_effects_reference_the_official_family_only(self):
        for level, entry in PROGRAMS.items():
            paths = K.effect_paths(entry["tree"])
            self.assertTrue(paths, level)
            for path in sorted(paths):
                self.assertTrue(path.startswith(K.FX_SRC_DIR + "/"), f"{level}: {path}")
                self.assertIn(path.rsplit("/", 1)[-1], K.FX_MEMBERS, f"{level}: {path}")


# ---------------------------------------------------------------- 2. 官方基线

@unittest.skipUnless(_BASELINE, "official baseline (.cdn/cn) or live store is unavailable")
class BaselineRowTests(unittest.TestCase):
    def test_every_row_rebuilds_from_the_official_donor(self):
        for kind, label, donor, cells, expect, changed in design_rows():
            with self.subTest(label):
                row, evidence = K._build(ctx(), kind, donor, cells, expect, changed, label)
                self.assertEqual(evidence["describe"], expect)
                ncols = KL.ABILITY_NCOLS if kind == "ability" else KL.LEADER_NCOLS
                self.assertEqual(len(row), ncols)
                self.assertEqual(KL.row_problems(kind, row,
                                                 K.ELEMENT if kind == "ability" else None), {})

    def test_full_row_mismatch_is_reported(self):
        kind, label, donor, cells, expect, changed = design_rows()[0]
        broken = dict(cells)
        broken["c49"] = "1"
        with self.assertRaises(K.KitError):
            K._build(ctx(), kind, donor, broken, expect, changed, label)

    def test_rows_need_no_client_patch(self):
        caps = set()
        for kind, label, donor, cells, expect, changed in design_rows():
            _row, evidence = K._build(ctx(), kind, donor, cells, expect, changed, label)
            caps.update(evidence["capabilities"])
        self.assertEqual(sorted(caps), [])

    def test_official_action_skill_donor_is_the_arrow_rain_row(self):
        rows = K._official_action_rows(ctx(), "psychic_gal")
        self.assertEqual(sorted(rows), ["1", "2"])
        for level, energy in (("1", ("500", "500")), ("2", ("500", "450"))):
            self.assertEqual(rows[level][2], "dynamic/skill/atk_nearest")
            self.assertEqual((rows[level][4], rows[level][5]), energy)
            design = DESIGN["plan"]["skills"]["energy"][f"lv{level}"]
            self.assertEqual((str(design["c4"]), str(design["c5"])), energy)


@unittest.skipUnless(_BASELINE, "official baseline (.cdn/cn) or live store is unavailable")
class BaselineSkillTreeTests(unittest.TestCase):
    def test_tree_rebuilds_to_the_design_and_passes_every_gate(self):
        for level in ("1", "2"):
            with self.subTest(level):
                tree, gates = K.build_skill_tree(ctx(), level)
                K.check_design_tree(DESIGN, level, tree)
                self.assertEqual(K._dsl_problems(tree), [])
                self.assertEqual(gates["buff_target_as"], 0)
                self.assertEqual(gates["onhit_statements"], K.ONHIT_DONOR_STATEMENTS + 2)
                self.assertEqual(len(gates["dropped_tail"]), 3)
                self.assertEqual(gates["skill_flag"], K.SKILL_FLAG_INDEX)
                self.assertAlmostEqual(gates["total_multiplier"],
                                       K.SKILL_TOTAL_LV2 if level == "2"
                                       else K.SKILL_TOTAL_LV2 * 2 / 3, places=1)

    def test_encoded_tree_round_trips_byte_for_byte(self):
        for level in ("1", "2"):
            tree, _ = K.build_skill_tree(ctx(), level)
            blob = wf_dsl.encode_amf3(tree)
            self.assertEqual(wf_dsl.parse_dsl(blob)["tree"], tree, level)
            self.assertEqual(len(blob), PROGRAMS[level]["encoded_bytes"], level)

    def test_design_tree_drift_is_caught(self):
        tree, _ = K.build_skill_tree(ctx(), "2")
        broken = copy.deepcopy(tree)
        K._command(K._only(K.find_statements(broken, "CreateNormalAttack"), "CNA"))[6] = \
            [{"min": 1, "max": 1}]
        with self.assertRaises(K.KitError):
            K.check_design_tree(DESIGN, "2", broken)

    def test_donor_pickers_take_the_ranged_shape(self):
        statement = K.pick_condition(ctx().template_dsl(K.TOLERANCE_DONOR.format(lv="2")),
                                     "ACToleranceOfElement")
        ac = K._command(statement)[2][0]
        self.assertIn("min", ac[1][0])                   # 排掉 alv 觉醒成长形
        self.assertEqual(K.slayer_param(ctx()), [["DCParalysis"]])
        empty = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
                 ["Block", []]]
        with self.assertRaises(K.KitError):
            K.pick_condition(empty, "ACParalysis")


# ---------------------------------------------------------------- 3. 已构建的 workspace

@unittest.skipUnless((WORKSPACE / "evidence/kit-report.json").is_file(),
                     "workspace ma-thorn has not been built yet")
class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = MC.MAPack(MS.get_spec("thorn"), record_sources=False)
        cls.report = json.loads((WORKSPACE / "evidence/kit-report.json").read_text("utf-8"))
        cls.claims = json.loads((WORKSPACE / "evidence/table_claims.json").read_text("utf-8"))

    def claimed(self, logical: str) -> set[str]:
        return {key for entry in self.claims if entry["logical_path"] == logical
                for key in entry["outer_keys"]}

    def test_every_self_owned_key_is_claimed(self):
        self.assertEqual(self.claimed(KL.ABILITY), set(K.ABILITY_KEYS))
        self.assertEqual(self.claimed(KL.LEADER), {str(K.CID)})
        self.assertEqual(self.claimed(KL.CHARACTER), {str(K.CID)})
        self.assertIn(K.VOICE_KEY, self.claimed(KL.SWITCHED))
        self.assertEqual(self.claimed(MS.UNIQUE_CONDITION_LOGICAL), set())
        self.assertEqual(self.claimed(KL.CAS),
                         {K.CAS_CHANGE_SKILL, *(K.CAS_ABILITY[s] for s in K.OVERRIDE_SLOTS)})

    def test_package_custom_ability_strings(self):
        import wf_balance_20260927c_panels as P3
        rows = self.pack.pkg_flat(KL.CAS)
        plan = {e["key"]: e["text"]
                for e in DESIGN["plan"]["texts"]["custom_ability_string"]["rows"]}
        # 包里的 CAS 是整表（含 live 的所有键）；这里只锁本角色自有的那 5 个。
        self.assertEqual(set(plan), set(self.claimed(KL.CAS)))
        # 第三轮面板合并（2026-09-27，wf_balance_20260927c_panels）：设计稿 / PANEL_ABILITY 已是合并稿；
        # 主会话暂存回写候选（manifest.snapshot.revision_20260927d.source == 该模块）之前，包里能力3 仍是改前 5 行。
        manifest = json.loads((WORKSPACE / "package/manifest.json").read_text("utf-8"))
        pending_c = (manifest.get("snapshot", {}).get("revision_20260927d") or {}).get("source") != P3.SOURCE
        # 同一轮主会话 C：技能强化条目「迟缓」→「冻结」（P3.SKILL_TEXT），再按技能强化文案 R2 改官方格式
        # （P3.FLAG_TEXT）；P3.cas_changes = (live 改前, 最终改后)，同样等暂存回写。
        flag_edits = P3.cas_changes(str(K.CID))
        for key, text in plan.items():
            self.assertIn(key, rows, key)
            if pending_c and key in P3.PANELS_BY_CAS:
                self.assertEqual(text, "\n".join(P3.PANELS_BY_CAS[key]["after"]), key)
                text = "\n".join(P3.PANELS_BY_CAS[key]["before"])
            elif pending_c and key in flag_edits:
                self.assertEqual(text, flag_edits[key][1], key)
                text = flag_edits[key][0]
            self.assertEqual(C.csv_split(rows[key])[0][0], text, key)
        for slot in K.OVERRIDE_SLOTS:
            text = plan[K.CAS_ABILITY[slot]]
            self.assertNotIn("Ⓜ", text, slot)
            lines = text.split("\n")
            self.assertEqual([line.replace(K.MAIN_ICON, "") for line in lines],
                             list(K.PANEL_ABILITY[slot]), slot)

    def test_package_rows_match_the_design(self):
        rows = self.pack.pkg_flat(KL.ABILITY)
        # 平衡第二批（2026-09-27，wf_balance_20260927b_thorn）：design 已把能力3 #1/#2 的触发方改成自身
        # （c28 7→0、c29 White→空）；主会话暂存回写候选（manifest.snapshot.revision_20260927b）之前，
        # 包里仍是改前两格 ⇒ 期望 = 设计行 + 第二批改前覆盖；回写后期望 = 设计行本身。
        manifest = json.loads((WORKSPACE / "package/manifest.json").read_text("utf-8"))
        pending_b = manifest.get("snapshot", {}).get("revision_20260927b") is None
        total = 0
        for key in K.ABILITY_KEYS:
            records = C.csv_split(rows[key])
            self.assertEqual(len(records), len(K.ABILITY_DONORS[key]), key)
            total += len(records)
            for index, record in enumerate(records):
                want = K.design_row(ABILITY_PLAN["keys"][key]["records"][index]["cells"],
                                    KL.ABILITY_NCOLS, key)
                if pending_b and key == f"{K.CID}3" and index in (1, 2):
                    self.assertEqual((want[28], want[29]), ("0", ""), f"{key}#{index}")
                    want[28], want[29] = "7", "White"
                self.assertEqual(list(record), want, f"{key}#{index}")
        self.assertEqual(total, K.ABILITY_RECORDS)
        leader = C.csv_split(self.pack.pkg_flat(KL.LEADER)[str(K.CID)])
        self.assertEqual(len(leader), K.LEADER_ROWS)
        for index, record in enumerate(leader):
            self.assertEqual(list(record),
                             K.design_row(LEADER_PLAN["rows"][index]["cells"],
                                          KL.LEADER_NCOLS, "leader"))

    def test_action_skill_targeting_and_energy(self):
        rows = B.KitContext(self.pack).pkg_nested(K.CODE)
        self.assertEqual(sorted(rows), ["1", "2"])
        for level in ("1", "2"):
            cells = list(rows[level])
            design = DESIGN["plan"]["skills"]["energy"][f"lv{level}"]
            self.assertEqual(cells[2], "dynamic/skill/atk_nearest", level)
            self.assertEqual((cells[4], cells[5]), (str(design["c4"]), str(design["c5"])), level)
            self.assertEqual(cells[0], MS.get_spec("thorn").texts[f"skill{level}"])

    def test_skill_description_matches_the_design_or_the_pending_revision(self):
        # 2026-09-27 第三轮（wf_balance_20260927c_panels，主会话 C）：技能说明「迟缓」→「冻结」。design 顶层 texts 已是改后；
        # 主会话暂存回写候选（manifest.snapshot.revision_20260927d.source == 该模块）之前，包里 action c1 / character_text
        # c5/c7 / 服务端镜像仍是改前文字。
        import wf_balance_20260927c_panels as P3
        before, after = P3.SKILL_TEXT[str(K.CID)]["desc"]
        texts = MS.get_spec("thorn").texts
        self.assertEqual((texts["desc1"], texts["desc2"]), (after, after))
        manifest = json.loads((WORKSPACE / "package/manifest.json").read_text("utf-8"))
        pending_c = (manifest.get("snapshot", {}).get("revision_20260927d") or {}).get("source") != P3.SOURCE
        want = before if pending_c else after
        rows = B.KitContext(self.pack).pkg_nested(K.CODE)
        self.assertEqual({level: list(rows[level])[1] for level in ("1", "2")}, {"1": want, "2": want})
        text_row = self.pack.pkg_character_text_row()
        self.assertEqual((text_row[5], text_row[7]), (want, want))
        server = json.loads(self.pack.pkg_path("server", "cdndata/character_text.json").read_text("utf-8"))
        self.assertEqual(server[str(K.CID)], [text_row])                 # 服务端镜像随 character_text 同步
        self.assertNotIn("迟缓", after)

    def test_written_dsl_equals_the_design_tree(self):
        # 设计稿登记的是零克隆基线树（D-8 默认项）；一旦 B/pixel/thorn/fx_lut.json 交付，
        # kit 会把效果引用整族改写到 K.FX_DST_DIR（保留成员基名，只换目录前缀，D-8 实际落法）。
        # 这里按 kit-report 实际报告的 effect_mode 决定要不要做同样的前缀替换再比较，
        # 这样测试跟着 kit 的真实分支走，不会因为像素/特效交付节奏而漂移。
        cloned = self.report["effect_mode"] == "clone+lut"
        src_prefix, dst_prefix = K.FX_SRC_DIR + "/", K.FX_DST_DIR + "/"

        def rewritten(node):
            if isinstance(node, str):
                return dst_prefix + node[len(src_prefix):] if node.startswith(src_prefix) else node
            if isinstance(node, list):
                return [rewritten(item) for item in node]
            return node

        for level in ("1", "2"):
            logical = wf_dsl.dsl_logical(
                f"battle/action/skill/action/rare5/{K.CODE}${K.CODE}_{level}")
            tree = C.amf_parse(self.pack.pkg_path("common", logical).read_bytes())
            expected = rewritten(PROGRAMS[level]["tree"]) if cloned else PROGRAMS[level]["tree"]
            self.assertEqual(tree, expected, logical)

    def test_character_row_routes_the_voice(self):
        row = self.pack.pkg_character_row()
        self.assertEqual(row[9:17], KL.voice_route(K.CODE, K.VOICE_ROUTE))
        self.assertEqual(row[6], str(K.PF_TYPE))
        self.assertEqual(row[26], K.STANCE)
        self.assertEqual(row[27], str(K.CID))

    def test_effect_family_matches_the_reported_mode(self):
        # D-8：默认零克隆（official-reference，无 fx_lut.json 时）；fx_lut.json 一旦交付，
        # kit 改走 clone+lut，包里必须有 K.FX_DST_DIR 整族且 report 登记这一族。两态都锁：
        # 不允许「报告说克隆了但包里没有」或反过来。
        family_dir = self.pack.pkg_path("common", K.FX_DST_DIR)
        if self.report["effect_mode"] == "clone+lut":
            self.assertEqual(self.report["effect_families"], [K.FX_DST_DIR])
            self.assertTrue(family_dir.is_dir(), family_dir)
        else:
            self.assertEqual(self.report["effect_mode"], "official-reference")
            self.assertEqual(self.report["effect_families"], [])
            self.assertFalse(family_dir.exists(), family_dir)

    def test_report_status_and_gate(self):
        gate = self.report["kit_gate"]
        self.assertEqual(gate["rows"], K.LEADER_ROWS + K.ABILITY_RECORDS)
        self.assertEqual(gate["programs"], 2)
        ready = gate["pixel_present"] and not gate["pixel_missing"]
        self.assertEqual(self.report["status"], KL.READY if ready else KL.DRAFT)
        if not ready:
            self.assertTrue(gate["reason"])

    def test_report_panel_and_capabilities(self):
        import wf_balance_20260927c_panels as P3
        self.assertEqual(self.report["cid"], K.CID)
        # kit-report 是 rework1 构建证据（第三轮之前的面板）；第三轮（wf_balance_20260927c_panels）改了能力1–4
        # （能力3 合并、能力4 合成一句、迟缓→冻结、口径3 冒号，能力2 只改冒号）。覆盖段应逐字 == 按槽取第三轮改前文字
        # （未重跑 kit）或 == 当前 PANEL_ABILITY（重跑 kit 后）。
        panel = list(self.report["panel"])
        head = K.LEADER_ROWS + K.ABILITY_RECORDS
        now = [line for s in K.OVERRIDE_SLOTS for line in K.PANEL_ABILITY[s]]
        before = []
        for slot in K.OVERRIDE_SLOTS:
            entry = P3.PANELS_BY_CAS.get(K.CAS_ABILITY[slot])
            before += ([P3._strip_icon(line) for line in entry["before"]] if entry else list(K.PANEL_ABILITY[slot]))
        for slot in (1, 2, 3, 4):
            entry = P3.PANELS_BY_CAS[K.CAS_ABILITY[slot]]
            self.assertEqual([P3._strip_icon(line) for line in entry["after"]], list(K.PANEL_ABILITY[slot]), slot)
        self.assertIn(panel[head:], (before, now))
        for text in self.report["panel"]:
            self.assertEqual(KL.panel_problems(text), [], text)
        self.assertEqual(self.report["required_capabilities"], [L.PANEL_OVERRIDE_V2])
        self.assertTrue(self.report["deviations"])
        self.assertIn("D-8", [d["id"] for d in self.report["deviations"]])


if __name__ == "__main__":
    unittest.main()
