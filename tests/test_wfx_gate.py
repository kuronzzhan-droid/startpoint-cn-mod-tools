# -*- coding: utf-8 -*-
"""wfx_gate:档案 × 行 × DSL × 键 的拒绝与放行,以及四个出口的接线。

判据(设计稿 4.9):
- gray 档案 + 一条 wfx 施加行 → 拒绝;本机 local-mumu 当前也拒绝(还没有任何 APK 消费 wfx 码);
  装了 L2 的档案(测试里合成)→ 放行;
- 无 wfx 行、只用档案已有补丁的数据 → 空操作通过;
- 分享包 / scoped 发布不给档案 → 拒绝;wf_publish / flow 默认 local-mumu。
"""
from __future__ import annotations

from external_sources import client_patch_path, require_external_source

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
MOD_DIR = TESTS.parent
sys.path.insert(0, str(TESTS))
sys.path.insert(0, str(MOD_DIR))

from tool_source import tool_source  # noqa: E402
import wf_describe  # noqa: E402
import wf_dsl  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_quest_lib as quest  # noqa: E402
import wf_wfx as W  # noqa: E402
import wfx_gate as G  # noqa: E402
import wfx_registry  # noqa: E402

UID = 99000101
WFX_SID = W.encode_sid(21, 6, 1, 1, "wfx_skill_cap1")          # 技能伤害上限 1(wfx-damage-v1)
L2_PROFILE = G.ClientProfile(
    "future-l2",
    G.load_profiles()["local-mumu"].capabilities
    | {"wfx-core-v1", "wfx-damage-v1", "wfx-gauge-v1", "wfx-dash-v1", "wfx-lock-v1"})


def unique_text(sid: str = WFX_SID, max_acc: str = "1", cancelable: bool = False) -> str:
    row = ["x"] * W.UNIQUE_COLUMNS
    row[:] = [sid, "噬主", "battle/common/unique_condition/unique_devil_leader", "99999999", max_acc,
              "(None)", "(None)", "(None)", "(None)", "true" if cancelable else "false", "true", "1", "0",
              "false", "(None)"]
    return ",".join(row)


def ability_row(kind: str, *, mode: str = "0", block: str = "instant_content", value: str = "461",
                uid: int | str | None = UID) -> list[str]:
    layout = wf_describe.layout(kind)
    blocks = {name: int(index) for name, index in layout["blocks"].items()}
    row = [""] * int(layout["ncols"])
    row[blocks["precondition1"] - 1] = mode
    for name in ("precondition1", "precondition2", "precondition3"):
        row[blocks[name]] = "0"
    row[blocks[block]] = value
    offsets = {"instant_content": 21, "during_content": 9, "instant_precontent": 6, "during_trigger": 7}
    if uid is not None:
        row[blocks[block] + offsets[block]] = str(uid)
    return row


def text_of(*rows: list[str]) -> str:
    return "\n".join(",".join(row) for row in rows)


def dsl_bytes(tree) -> bytes:
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    return compressor.compress(wf_dsl.encode_amf3(tree)) + compressor.flush()


def trace_tree(text: str):
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
            ["Block", [["Command", ["Trace", text]]]]]


def unique_tree(uid: int):
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0,
            ["Block", [["Command", ["CreateCondition", -17, [["ACUnique", uid, [{"min": 1, "max": 1}]]]]]]]]


def rel(logical: str) -> str:
    digest = core.sha1_path(logical)
    return f"{digest[:2]}/{digest[2:]}"


class CheckTests(unittest.TestCase):
    def test_clean_data_is_a_no_op_pass_on_every_profile(self):
        rows = {"ability": {"1": text_of(ability_row("ability", value="213", uid=None))},
                "unique_condition": {"1": unique_text("unique_zeta")}}
        for profile in ("local-mumu", "gray-1047", "official"):
            with self.subTest(profile=profile):
                report = G.check(rows, {}, ["change_skill_ginovi"], profile)
                self.assertTrue(report.ok, report.problems)
                self.assertEqual([], report.requirements)
                self.assertEqual([], report.warnings)
                self.assertIn("无客户端能力需求", report.lines()[0])

    def test_gray_rejects_a_wfx_apply_row_and_says_it_would_fail_silently(self):
        rows = {"unique_condition": {str(UID): unique_text()},
                "equipment_enhancement_ability": {"5910120": text_of(ability_row("equipment_enhancement_ability"))}}
        report = G.check(rows, {}, (), "gray-1047")
        self.assertFalse(report.ok)
        text = "\n".join(report.problems)
        self.assertIn("会静默失效", text)
        self.assertIn("wfx-damage-v1", text)
        self.assertIn("wfx-core-v1", text)
        self.assertIn("equipment_enhancement_ability[5910120]#0", text)
        self.assertIn("尚无客户端实现", text)

    def test_local_mumu_rejects_too_until_an_l2_apk_is_installed(self):
        rows = {"unique_condition": {str(UID): unique_text()},
                "ability": {"1": text_of(ability_row("ability"))}}
        self.assertFalse(G.check(rows, {}, (), "local-mumu").ok)
        self.assertFalse(G.check(rows, {}, (), "official").ok)
        report = G.check(rows, {}, (), L2_PROFILE)
        self.assertTrue(report.ok, report.problems)
        self.assertIn("wfx-damage-v1", report.required_capabilities())

    def test_every_batch_one_code_is_blocked_on_every_current_profile(self):
        samples = {10: "wfx:10:0:-1:1:a", 20: "wfx:20:4:0.3:0:a", 21: "wfx:21:0:1:1:a",
                   22: "wfx:22:6:-0.5:1:a", 23: "wfx:23:0:50000:1:a", 30: "wfx:30:127:0:0:a",
                   31: "wfx:31:127:-0.01:0:a", 40: "wfx:40:0:-0.3:0:a", 50: "wfx:50:0:15:1:a",
                   51: "wfx:51:0:0:1:a", 52: "wfx:52:0:1:1:a"}
        planned = {code for code, effect in wfx_registry.effect_codes().items()
                   if wfx_registry.capabilities()[effect["capability"]]["status"] == "planned"}
        self.assertEqual(planned, set(samples))
        for code, sid in samples.items():
            rows = {"unique_condition": {str(UID): unique_text(sid, max_acc="99")}}
            for profile in G.load_profiles():
                with self.subTest(code=code, profile=profile):
                    self.assertFalse(G.check(rows, {}, (), profile).ok)
            with self.subTest(code=code, profile="future-l2"):
                self.assertTrue(G.check(rows, {}, (), L2_PROFILE).ok)

    def test_unreferenced_wfx_rows_are_still_reported(self):
        report = G.check({"unique_condition": {str(UID): unique_text()}}, {}, (), "gray-1047")
        self.assertFalse(report.ok)
        self.assertIn(f"unique_condition[{UID}]", "\n".join(report.problems))

    def test_uid_resolution_uses_the_store_context_when_the_table_is_not_published(self):
        rows = {"ability": {"1": text_of(ability_row("ability"))}}
        self.assertTrue(G.check(rows, {}, (), "gray-1047").ok)             # 没有上下文:uid 普通
        report = G.check(rows, {}, (), "gray-1047", unique_context={str(UID): unique_text()})
        self.assertFalse(report.ok)
        self.assertIn("ability[1]#0", "\n".join(report.problems))
        # 上下文里同 uid 是普通固有状态 → 通过
        self.assertTrue(G.check(rows, {}, (), "gray-1047",
                                unique_context={str(UID): unique_text("cursed_dice_1")}).ok)

    def test_only_the_parsed_block_counts_as_a_reference(self):
        context = {str(UID): unique_text()}
        # 持续行里残留的瞬发 461:客户端不解析 instant 块
        residue = ability_row("ability", mode="1")
        self.assertTrue(G.check({"ability": {"1": text_of(residue)}}, {}, (), "gray-1047",
                                unique_context=context).ok)
        # 瞬发前置内容 3(UniqueCondition)读 uid;0(Combo)不读
        reads = ability_row("ability", block="instant_precontent", value="3")
        ignores = ability_row("ability", block="instant_precontent", value="0")
        self.assertFalse(G.check({"ability": {"1": text_of(reads)}}, {}, (), "gray-1047",
                                 unique_context=context).ok)
        self.assertTrue(G.check({"ability": {"1": text_of(ignores)}}, {}, (), "gray-1047",
                                unique_context=context).ok)
        # 持续触发 134(按固有状态层数)读 uid
        trigger = ability_row("ability", mode="1", block="during_trigger", value="134")
        self.assertFalse(G.check({"ability": {"1": text_of(trigger)}}, {}, (), "gray-1047",
                                 unique_context=context).ok)

    def test_patch_kinds_borrowing_the_uid_column_are_not_uid_references(self):
        """负对照:423 的 c118 是规则码、422 的 c118 是 param_id;数值恰好等于 wfx uid 也不算引用。"""
        context = {str(UID): unique_text()}
        for value in ("422", "423", "424"):
            row = ability_row("ability", mode="1", block="during_content", value=value)
            with self.subTest(kind=value):
                report = G.check({"ability": {"1": text_of(row)}}, {}, (), "local-mumu",
                                 unique_context=context)
                self.assertTrue(report.ok, report.problems)
                self.assertFalse([c for c in report.required_capabilities() if c.startswith("wfx-")])
        # 同一个 uid 放在官方读 uid 的持续构造(81 UniqueSlayer)上就是引用
        slayer = ability_row("ability", mode="1", block="during_content", value="81")
        self.assertFalse(G.check({"ability": {"1": text_of(slayer)}}, {}, (), "local-mumu",
                                 unique_context=context).ok)

    def test_malformed_and_reserved_sids_are_blocked_regardless_of_profile(self):
        for sid in ("wfx:21:0:0:1:bad", "wfx:21:0:1:1", "wfx:99:0:1:0:a", "wfxq:990099:0:1:99000101",
                    "wfx:31:127:-0.01:0:stack_none"):
            max_acc = "(None)" if sid.endswith("stack_none") else "1"
            rows = {"unique_condition": {str(UID): unique_text(sid, max_acc=max_acc)}}
            with self.subTest(sid=sid):
                self.assertFalse(G.check(rows, {}, (), L2_PROFILE).ok)
        pinned_but_cancelable = {"unique_condition": {str(UID): unique_text(cancelable=True)}}
        self.assertFalse(G.check(pinned_but_cancelable, {}, (), L2_PROFILE).ok)

    def test_lookalike_and_whitespace_sids_are_blocked_as_silent_failures(self):
        """以 wfx 开头却不是登记前缀(大小写/分隔符写错、首尾空白):客户端不会当作效果状态,
        放行 = 诅咒静默失效。任何档案(含将来的 L2 档案)都拒绝;引用它的施加行同样拒绝。"""
        for sid in ("WFX:21:0:1:1:typo", "wfx;21:0:1:1:typo", "wfx21:0:1:1:typo", "Wfx:21:0:1:1:typo",
                    "wfx_typo_21", " wfx:21:0:1:1:lead", "wfx:21:0:1:1:trail "):
            unique = {"unique_condition": {str(UID): unique_text(sid)}}
            referencing = {**unique, "ability": {"1": text_of(ability_row("ability"))}}
            for profile in ("local-mumu", "gray-1047", "official", L2_PROFILE):
                with self.subTest(sid=sid, profile=getattr(profile, "name", profile)):
                    report = G.check(referencing, {}, (), profile)
                    self.assertFalse(report.ok)
                    self.assertIn(f"unique_condition[{UID}]", "\n".join(report.problems))
            if sid.strip() == sid and not sid.startswith("wfx:"):
                problems = "\n".join(G.check(unique, {}, (), L2_PROFILE).problems)
                self.assertIn("[会静默失效]", problems)
        # 只在上下文里的写错行被施加行引用:引用处拒绝
        context = {str(UID): unique_text("WFX:21:0:1:1:typo")}
        report = G.check({"ability": {"1": text_of(ability_row("ability"))}}, {}, (), L2_PROFILE,
                         unique_context=context)
        self.assertFalse(report.ok)
        self.assertIn("ability[1]#0", "\n".join(report.problems))
        # 与本框架无关的 sid 不受影响
        self.assertTrue(G.check({"unique_condition": {str(UID): unique_text("unique_wfxlike")}}, {}, (),
                                "official").ok)

    def test_dsl_apply_and_trace(self):
        context = {str(UID): unique_text()}
        report = G.check({}, {"skill.dsl": unique_tree(UID)}, (), "gray-1047", unique_context=context)
        self.assertFalse(report.ok)
        self.assertIn("DSL skill.dsl", "\n".join(report.problems))
        self.assertTrue(G.check({}, {"skill.dsl": unique_tree(12345)}, (), "gray-1047",
                                unique_context=context).ok)
        trace = G.check({}, {"skill.dsl": trace_tree("wfx:apply|uid=1|to=trigger")}, (), L2_PROFILE)
        self.assertFalse(trace.ok)
        self.assertIn("wfx-dsl-v1", "\n".join(trace.problems))
        self.assertTrue(G.check({}, {"skill.dsl": trace_tree("debug hello")}, (), "official").ok)

    def test_existing_patch_constructs_follow_the_profile(self):
        gauge_ea = ability_row("equipment_enhancement_ability", mode="1", block="during_content",
                               value="423", uid="8")
        rows = {"equipment_enhancement_ability": {"5920001": text_of(gauge_ea)}}
        self.assertTrue(G.check(rows, {}, (), "local-mumu").ok)
        gray = G.check(rows, {}, (), "gray-1047")
        self.assertFalse(gray.ok)
        self.assertIn("[会崩] 缺 equipment-gauge-gain-rules-v1", "\n".join(gray.problems))
        fever = {"ability": {"1": text_of(ability_row("ability", value="724", uid=None))}}
        self.assertTrue(G.check(fever, {}, (), "gray-1047").ok)
        self.assertIn("[会崩] 缺 kyubi-fever-ratio-v1", "\n".join(G.check(fever, {}, (), "official").problems))
        # 队长表 422:解析器不支持 → 能力不是解药,闸门不声称需要 dash-parameter-v1,
        # 但它是崩溃级(C7050),任何档案都拒绝(见 ParserScopeTests)
        leader = {"leader_ability": {"1": text_of(ability_row("leader_ability", mode="1",
                                                              block="during_content", value="422", uid="0"))}}
        for profile in ("local-mumu", "gray-1047", "official"):
            with self.subTest(profile=profile):
                report = G.check(leader, {}, (), profile)
                self.assertEqual([], report.required_capabilities())
                self.assertFalse(report.ok)
                self.assertIn("LeaderAbilityValues$/parseAt107", "\n".join(report.problems))

    def test_string_keys_are_cosmetic(self):
        report = G.check({}, {}, ["desc_override_equipment_5920001", "wfx_text_99000101"], "gray-1047")
        self.assertTrue(report.ok)
        warnings = "\n".join(report.warnings)
        self.assertIn("equipment-description-override-v1", warnings)
        self.assertIn("wfx-effect-during-v1", warnings)
        self.assertTrue(G.check({}, {}, ["desc_override_equipment_5920001"], "local-mumu").ok)
        self.assertEqual([], G.check({}, {}, ["desc_override_equipment_5920001"], "local-mumu").warnings)

    def test_enhanced_look_keys_are_cosmetic(self):
        """装备强化外观键(第二图标档 / 强化框换底):缺 equipment-enhanced-look-v1 只警告不拒绝;装了就安静。"""
        keys = ["enhanced_pixelart_tier2_item/equipment/mod/paradox/paradox_lv120",
                "enhanced_frame_override_item/equipment/mod/paradox/paradox_lv200"]
        for profile in ("gray-1047", "official"):
            with self.subTest(profile=profile):
                report = G.check({}, {}, keys, profile)
                self.assertTrue(report.ok, report.problems)
                self.assertEqual(["equipment-enhanced-look-v1"], report.required_capabilities())
                self.assertEqual(1, len(report.warnings))
                self.assertIn("equipment-enhanced-look-v1", report.warnings[0])
        patched = G.ClientProfile("look", G.load_profiles()["local-mumu"].capabilities | {"equipment-enhanced-look-v1"})
        report = G.check({}, {}, keys, patched)
        self.assertTrue(report.ok)
        self.assertEqual([], report.warnings)
        # 近名不归外观规则:没有下划线结尾的前缀、大小写不同
        self.assertEqual([], G.check({}, {}, ["enhanced_pixelart_tier2", "Enhanced_frame_override_x"],
                                     "official").required_capabilities())

    def test_item_rarity_frame_key_is_cosmetic_and_not_covered_by_v1_or_party_frame(self):
        """品质底色键:缺 item-rarity-frame-override-v1 只警告不拒绝;只装 v1 与编成槽框的客户端(旧装 14396ce0)也要警告
        (它们不读这个键);补上这一项就安静(现装 b0b13112 已含)。近名不归这条规则。"""
        key = "rarity_frame_override_item/materials/mod/cursed/forbidden_star_steel"
        installed = G.load_profiles()["local-mumu"]
        self.assertIn("equipment-enhanced-look-v1", installed.capabilities)
        self.assertIn("equipment-enhanced-party-frame-v1", installed.capabilities)
        self.assertIn("item-rarity-frame-override-v1", installed.capabilities)
        without = G.ClientProfile("look+party", installed.capabilities - {"item-rarity-frame-override-v1"})
        for profile in ("gray-1047", "official", without):
            with self.subTest(profile=getattr(profile, "name", profile)):
                report = G.check({}, {}, [key], profile)
                self.assertTrue(report.ok, report.problems)
                self.assertEqual(["item-rarity-frame-override-v1"], report.required_capabilities())
                self.assertEqual(1, len(report.warnings))
                self.assertIn("item-rarity-frame-override-v1", report.warnings[0])
        for profile in (installed, G.ClientProfile("rarity", without.capabilities | {"item-rarity-frame-override-v1"})):
            report = G.check({}, {}, [key], profile)
            self.assertTrue(report.ok)
            self.assertEqual([], report.warnings)
        self.assertEqual([], G.check({}, {}, ["rarity_frame_override", "Rarity_frame_override_x",
                                              "item_rarity_frame_override_x"], "official").required_capabilities())

    def test_enhanced_party_frame_key_is_cosmetic_and_not_covered_by_v1(self):
        """编成槽框键:缺 equipment-enhanced-party-frame-v1 只警告不拒绝;只装 v1 的客户端也要警告(v1 不读它)。"""
        key = "enhanced_party_frame_override_item/equipment/mod/paradox/paradox_lv200"
        for profile in ("gray-1047", "official"):
            with self.subTest(profile=profile):
                report = G.check({}, {}, [key], profile)
                self.assertTrue(report.ok, report.problems)
                self.assertEqual(["equipment-enhanced-party-frame-v1"], report.required_capabilities())
                self.assertIn("equipment-enhanced-party-frame-v1", report.warnings[0])
        v1_only = G.ClientProfile("v1", (G.load_profiles()["local-mumu"].capabilities
                                         | {"equipment-enhanced-look-v1"}) - {"equipment-enhanced-party-frame-v1"})
        self.assertEqual(1, len(G.check({}, {}, [key], v1_only).warnings))
        patched = G.ClientProfile("party", v1_only.capabilities | {"equipment-enhanced-party-frame-v1"})
        self.assertEqual([], G.check({}, {}, [key], patched).warnings)
        self.assertEqual([], G.check({}, {}, ["enhanced_party_frame_override"], "official").required_capabilities())

    def test_awakening_material_key_is_semantic_and_refused_without_the_patch(self):
        """觉醒专属素材键:没打补丁的接收端仍按稀有度提供星铁钢、服务端 400 = 静默失效 → 门禁拒绝(不是警告)。"""
        key = "awakening_material_5910101"
        without = G.ClientProfile("party-frame", G.load_profiles()["local-mumu"].capabilities
                                  - {"equipment-awakening-material-v1"})
        for profile in ("gray-1047", "official", without):
            with self.subTest(profile=getattr(profile, "name", profile)):
                report = G.check({}, {}, [key], profile)
                self.assertFalse(report.ok)
                self.assertEqual(["equipment-awakening-material-v1"], report.required_capabilities())
                self.assertIn("equipment-awakening-material-v1", report.problems[0])
                self.assertIn("会静默失效", report.problems[0])
        patched = G.ClientProfile("awaken", without.capabilities | {"equipment-awakening-material-v1"})
        report = G.check({}, {}, [key], patched)
        self.assertTrue(report.ok, report.problems)
        self.assertEqual([], report.warnings)
        self.assertEqual([], G.check({}, {}, ["awakening_material"], "official").required_capabilities())

    def test_sort_pin_key_is_cosmetic_and_not_covered_by_the_awakening_patch(self):
        """置顶键:缺 equipment-sort-pin-v1 只警告不拒绝;只装觉醒专属素材的客户端也要警告(它不读置顶键)。"""
        key = "equipment_sort_pin_5920001"
        awaken_only = G.ClientProfile("awaken", (G.load_profiles()["local-mumu"].capabilities
                                                 | {"equipment-awakening-material-v1"}) - {"equipment-sort-pin-v1"})
        for profile in ("gray-1047", "official", awaken_only):
            with self.subTest(profile=getattr(profile, "name", profile)):
                report = G.check({}, {}, [key], profile)
                self.assertTrue(report.ok, report.problems)
                self.assertEqual(["equipment-sort-pin-v1"], report.required_capabilities())
                self.assertIn("equipment-sort-pin-v1", report.warnings[0])
        self.assertEqual(1, len(G.check({}, {}, [key], awaken_only).warnings))
        both = G.ClientProfile("both", awaken_only.capabilities | {"equipment-sort-pin-v1"})
        self.assertEqual([], G.check({}, {}, [key], both).warnings)

    def test_weapon_data_tools_pass_the_gate_on_the_candidate_profile(self):
        """wf_weapon_awaken 的 30 键 + wf_weapon_sort_pin 的 46 键:候选 APK(14 项)零问题零警告;
        现装 14396ce0(12 项)上觉醒键被拒、置顶键只警告。"""
        import wf_weapon_awaken
        import wf_weapon_sort_pin
        keys = list(wf_weapon_awaken.cas_rows()) + list(wf_weapon_sort_pin.cas_rows())
        self.assertEqual(76, len(keys))
        import importlib.util
        path = client_patch_path('equipment-awakening-material/rules.py')
        spec = importlib.util.spec_from_file_location("_wfx_gate_awaken_rules_probe", require_external_source(path))
        awaken = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(awaken)
        installed = G.ClientProfile("14396ce0", frozenset(awaken.INHERITED_CAPABILITIES))   # 编成槽框 APK 的 12 项
        self.assertEqual(12, len(installed.capabilities))
        candidate = G.ClientProfile("candidate", installed.capabilities
                                    | {"equipment-awakening-material-v1", "equipment-sort-pin-v1"})
        self.assertEqual(14, len(candidate.capabilities))
        report = G.check({}, {}, keys, candidate)
        self.assertEqual(([], []), (report.problems, report.warnings))
        report = G.check({}, {}, keys, installed)
        self.assertFalse(report.ok)
        self.assertEqual(1, len(report.problems))
        self.assertIn("equipment-awakening-material-v1", report.problems[0])
        self.assertEqual(1, len(report.warnings))
        self.assertIn("equipment-sort-pin-v1", report.warnings[0])


class ParserScopeTests(unittest.TestCase):
    """设计稿 4.9 第 1 条:表 × 补丁构造是否在补丁扩展过的解析器范围。

    范围外 = 该表 parseAt 抛 C7050,与接收方装了什么无关(没有已发布补丁扩展它),所以任何档案
    都拒绝。required_client_capabilities 对范围外构造刻意返回空,闸门必须自己查范围。"""
    PROFILES = ("local-mumu", "gray-1047", "official")
    OUT_OF_SCOPE = (
        ("leader_ability", "1", "during_content", "422", "LeaderAbilityValues$/parseAt107"),
        ("ability_soul", "1", "during_content", "422", "AbilitySoulValues$/parseAt106"),
        ("equipment_enhancement_ability", "1", "during_content", "422",
         "EquipmentEnhancementAbilityValues$/parseAt109"),
        ("ex_ability", "1", "during_content", "422", "ExAbilityValues$/parseAt108"),
        ("leader_ability", "1", "during_content", "423", "LeaderAbilityValues$/parseAt107"),
        ("ex_ability", "1", "during_content", "423", "ExAbilityValues$/parseAt108"),
        ("equipment_enhancement_ability", "1", "during_content", "424",
         "EquipmentEnhancementAbilityValues$/parseAt109"),
        ("ability_soul", "1", "during_content", "424", "AbilitySoulValues$/parseAt106"),
        ("leader_ability", "0", "instant_content", "724", "LeaderAbilityValues$"),
        ("ability_soul", "0", "instant_content", "724", "AbilitySoulValues$"),
        ("equipment_enhancement_ability", "0", "instant_content", "724", "EquipmentEnhancementAbilityValues$"),
        ("ex_ability", "0", "instant_content", "724", "ExAbilityValues$"),
    )

    @staticmethod
    def rows(kind: str, mode: str, block: str, value: str):
        uid = "0" if block == "during_content" else None
        return {kind: {"1": text_of(ability_row(kind, mode=mode, block=block, value=value, uid=uid))}}

    def verdicts(self, rows):
        return tuple(G.check(rows, {}, (), profile).ok for profile in self.PROFILES)

    def test_out_of_scope_constructs_are_crash_level_on_every_profile(self):
        for kind, mode, block, value, parser in self.OUT_OF_SCOPE:
            rows = self.rows(kind, mode, block, value)
            for profile in (*self.PROFILES, L2_PROFILE):
                with self.subTest(kind=kind, value=value, profile=getattr(profile, "name", profile)):
                    report = G.check(rows, {}, (), profile)
                    self.assertFalse(report.ok)
                    text = "\n".join(report.problems)
                    self.assertIn("[会崩]", text)
                    self.assertIn("未被当前补丁扩展", text)
                    self.assertIn(parser, text)
                    self.assertIn(f"{kind}[1]#0", text)

    def test_in_scope_constructs_and_residue_follow_the_profile_only(self):
        dash = self.rows("ability", "1", "during_content", "422")
        self.assertEqual((True, True, False), self.verdicts(dash))
        self.assertNotIn("未被当前补丁扩展", "\n".join(G.check(dash, {}, (), "official").problems))
        self.assertEqual((True, True, False), self.verdicts(self.rows("ability", "0", "instant_content", "724")))
        self.assertEqual((True, False, False),
                         self.verdicts(self.rows("equipment_enhancement_ability", "1", "during_content", "423")))
        # 瞬发行里残留的持续块 422:客户端不解析它,不算
        residue = self.rows("leader_ability", "0", "during_content", "422")
        self.assertEqual((True, True, True), self.verdicts(residue))

    def test_negative_control_the_422_scope_entry_drives_the_verdict(self):
        """拿掉 PATCH_PARSER_TABLES 的 422 登记 → 队长表 422 回到 B1-0 之前的盲区判定(只剩能力判据:
        本机/灰放行、官方因缺 dash-parameter-v1 拦);放回即全档案拒绝。"""
        import wf_client_patch_scope as scope
        rows = self.rows("leader_ability", "1", "during_content", "422")
        self.assertEqual((False, False, False), self.verdicts(rows))
        with mock.patch.dict(scope.PATCH_PARSER_TABLES):
            del scope.PATCH_PARSER_TABLES["during_content", "422"]
            self.assertEqual((True, True, False), self.verdicts(rows))
            official = "\n".join(G.check(rows, {}, (), "official").problems)
            self.assertIn("dash-parameter-v1", official)
            self.assertNotIn("未被当前补丁扩展", official)
        self.assertEqual((False, False, False), self.verdicts(rows))

    def test_negative_control_the_gate_itself_must_call_the_scope_check(self):
        """变异:闸门不查解析器范围 → 队长表 422 在所有档案上放行(即评审发现的盲区)。"""
        rows = self.rows("leader_ability", "1", "during_content", "422")
        with mock.patch("wf_client_patch_scope.patch_parser_scope_problems", return_value=[]):
            self.assertEqual((True, True, True), self.verdicts(rows))
        self.assertEqual((False, False, False), self.verdicts(rows))


class ExitCoverageTests(unittest.TestCase):
    """哪些出口接了闸门、哪些没接(及原因),以源码为准钉住;改出口时两张表必须同步。"""

    def source(self, module: str) -> str:
        return tool_source(MOD_DIR, f"{module}.py").read_text(encoding="utf-8")

    def test_gated_exits_call_the_gate(self):
        calls = {"wf_publish": "wfx_gate.check_publish(", "wf_character_flow": "wfx_gate.check_package(",
                 "wf_release": "wfx_gate.check_package(", "wf_share_variant": "wfx_gate.check_entries(",
                 "wf_scoped_release": "wfx_gate.check_entries(",
                 "wf_local_scoped_release": "client_profile=client_profile"}
        self.assertEqual(set(calls), set(G.GATED_EXITS))
        for module, needle in calls.items():
            with self.subTest(module=module):
                self.assertIn(needle, self.source(module))

    def test_ungated_exits_are_documented_and_really_ungated(self):
        gated = set(G.GATED_EXITS)
        for name, reason in G.UNGATED_EXITS.items():
            module = name.split()[0]
            with self.subTest(exit=name):
                self.assertNotIn(module, gated)
                self.assertTrue(reason.strip())
                self.assertNotIn("wfx_gate", self.source(module),
                                 "已接闸门的出口要从 UNGATED_EXITS 挪到 GATED_EXITS")


class ReleaseCliExitTests(unittest.TestCase):
    """wf_release.py publish 绕过 flow 直接发包:同一闸门,默认 local-mumu,失败时不调发布原语。"""

    def package(self, root: Path, sid: str) -> Path:
        package = root / "package"
        target = package / "roots" / "common" / Path(*G.UNIQUE_CONDITION_LOGICAL.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(quest.build_node({str(UID): unique_text(sid)}))
        return package

    def run_cli(self, argv):
        import wf_release
        from types import SimpleNamespace
        result = SimpleNamespace(committed=True, release_id="r", from_version="1.4.1", version="1.4.2",
                                 active_manifest_sha256="a" * 64, archive_paths=(), snapshot_dir=None)
        stderr, stdout = io.StringIO(), io.StringIO()
        with mock.patch.object(wf_release, "publish_package", return_value=result) as publish, \
                mock.patch("wf_mod_tool.resolve_profile", return_value=None), \
                contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(stdout):
            code = wf_release.main(argv)
        return code, publish, stderr.getvalue()

    def test_wfx_package_is_refused_before_publish_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = self.package(Path(tmp), WFX_SID)
            base = ["publish", "--package-dir", str(package), "--confirm", "DIRECT_REAL_TEST"]
            for extra in ([], ["--client-profile", "gray-1047"]):
                with self.subTest(extra=extra):
                    code, publish, stderr = self.run_cli(base + extra)
                    self.assertEqual(2, code)
                    publish.assert_not_called()
                    self.assertIn("client capability gate", stderr)
            code, publish, stderr = self.run_cli(base + ["--client-profile", "nope"])
            self.assertEqual(2, code)
            publish.assert_not_called()
            self.assertIn("未知客户端档案", stderr)

    def test_clean_package_reaches_publish_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = self.package(Path(tmp), "unique_zeta")
            code, publish, stderr = self.run_cli(
                ["publish", "--package-dir", str(package), "--confirm", "DIRECT_REAL_TEST"])
            self.assertEqual(0, code, stderr)
            publish.assert_called_once()
            self.assertIn("[通过] 档案 local-mumu", stderr)


class EntryTests(unittest.TestCase):
    def test_tables_are_found_by_hashed_path_and_dsl_by_content(self):
        unique = quest.build_node({str(UID): unique_text()})
        ability = quest.build_node({"1": text_of(ability_row("ability"))})
        entries = [(f"production/upload/{rel(G.UNIQUE_CONDITION_LOGICAL)}", unique),
                   (rel(G.ABILITY_TABLE_LOGICALS["ability"]), ability)]
        report = G.check_publish(entries, None, "gray-1047")
        self.assertFalse(report.ok)
        self.assertIn("ability[1]#0", "\n".join(report.problems))
        # DSL 只知道哈希路径:按内容识别
        trace = G.check_publish([("aa/" + "b" * 38, dsl_bytes(trace_tree("wfx:echo|n=1")))], None, "local-mumu")
        self.assertFalse(trace.ok)
        self.assertIn("wfx-dsl-v1", "\n".join(trace.problems))

    def test_clean_dsl_is_not_even_parsed(self):
        entries = [("aa/" + "c" * 38, dsl_bytes(trace_tree("debug"))), ("aa/" + "d" * 38, b"\x89PNG\r\n")]
        with mock.patch.object(G, "_parse_dsl", side_effect=AssertionError("parsed")):
            self.assertTrue(G.check_publish(entries, None, "official").ok)

    def test_undecodable_gate_table_is_skipped_with_a_warning(self):
        """索引都解不开的表客户端也读不出:闸门不替表结构校验拦发布(B1-0 前的行为),只警告。
        tests/test_store_resolution 用 b"payload" 冒充 ability 表跑 --list,必须照旧通过。"""
        for logical in (G.UNIQUE_CONDITION_LOGICAL, G.ABILITY_TABLE_LOGICALS["ability"], G.CUSTOM_STRING_LOGICAL):
            with self.subTest(logical=logical):
                report = G.check_publish([(rel(logical), b"not an orderedmap")], None, "official")
                self.assertTrue(report.ok, report.problems)
                self.assertIn("不是可解码的 orderedmap", "\n".join(report.warnings))

    def test_unreadable_payload_is_a_clean_blocking_problem(self):
        """待投递文件读不出(如 Windows 超长路径):闸门无法判定 → 拦下并写明,不抛裸异常。"""
        def boom():
            raise FileNotFoundError(2, "No such file or directory")
        for logical in (G.ABILITY_TABLE_LOGICALS["ability"], "battle/action/x.action.dsl.amf3.deflate"):
            with self.subTest(logical=logical):
                report = G.check_entries([G.PayloadEntry(label=logical, read=boom, logical=logical)], "official")
                self.assertFalse(report.ok)
                self.assertIn("[读不出]", "\n".join(report.problems))

    def test_store_context_is_read_for_uid_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            path = core.table_path(store, G.UNIQUE_CONDITION_LOGICAL)
            path.parent.mkdir(parents=True)
            path.write_bytes(quest.build_node({str(UID): unique_text()}))
            ability = quest.build_node({"1": text_of(ability_row("ability"))})
            entries = [(rel(G.ABILITY_TABLE_LOGICALS["ability"]), ability)]
            self.assertFalse(G.check_publish(entries, store, "gray-1047").ok)
            self.assertTrue(G.check_publish(entries, None, "gray-1047").ok)

    def test_package_check_reads_common_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            package = Path(tmp)
            common = package / "roots" / "common"
            target = common / Path(*G.UNIQUE_CONDITION_LOGICAL.split("/"))
            target.parent.mkdir(parents=True)
            target.write_bytes(quest.build_node({str(UID): unique_text()}))
            report = G.check_package(package, (), None)
            self.assertEqual("local-mumu", report.profile)
            self.assertFalse(report.ok)
            target.write_bytes(quest.build_node({str(UID): unique_text("cursed_x")}))
            self.assertTrue(G.check_package(package, (), None).ok)


class PublishExitTests(unittest.TestCase):
    """wf_publish:默认 local-mumu;无 wfx 数据空操作;有 wfx 数据拒绝且不产出任何包。"""

    def setUp(self):
        from test_publish import PublisherCase
        self.case = PublisherCase("run_publish")
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        guard = mock.patch("wf_publish_guard.check", return_value=[])
        guard.start()
        self.addCleanup(guard.stop)

    def publish(self, args):
        return self.case.run_publish(args + ["--no-dev-catalog"])

    def test_wfx_rows_block_the_publish_on_the_default_profile(self):
        self.case.write_logical(G.UNIQUE_CONDITION_LOGICAL, quest.build_node({str(UID): unique_text()}))
        code, stdout, stderr = self.publish(["--tables", "unique_condition"])
        self.assertEqual(1, code)
        self.assertIn("档案 local-mumu", stdout)
        self.assertIn("能力闸门", stderr)
        self.assertEqual([], self.case.archives())
        code, _stdout, _stderr = self.publish(["--tables", "unique_condition", "--list"])
        self.assertEqual(1, code)

    def test_clean_tables_publish_exactly_as_before(self):
        self.case.write_logical(G.UNIQUE_CONDITION_LOGICAL, quest.build_node({"1": unique_text("unique_zeta")}))
        code, stdout, _stderr = self.publish(["--tables", "unique_condition"])
        self.assertEqual(0, code, stdout)
        self.assertIn("[通过] 档案 local-mumu", stdout)
        self.assertEqual(1, len(self.case.common_archives()))

    def test_explicit_profile_and_unknown_profile(self):
        gauge_ea = ability_row("equipment_enhancement_ability", mode="1", block="during_content",
                               value="423", uid="8")
        self.case.write_logical(G.ABILITY_TABLE_LOGICALS["equipment_enhancement_ability"],
                                quest.build_node({"5920001": text_of(gauge_ea)}))
        code, stdout, _ = self.publish(["--tables", "weapon_ability", "--list"])
        self.assertEqual(0, code, stdout)
        code, stdout, _ = self.publish(["--tables", "weapon_ability", "--list", "--client-profile", "gray-1047"])
        self.assertEqual(1, code)
        self.assertIn("equipment-gauge-gain-rules-v1", stdout)
        code, _, stderr = self.publish(["--tables", "weapon_ability", "--client-profile", "nope"])
        self.assertEqual(1, code)
        self.assertIn("未知客户端档案", stderr)

    def test_out_of_scope_leader_422_blocks_the_publish_on_the_default_profile(self):
        """出口级负对照:队长表 422 在本机(档案最全)也 C7050,wf_publish 必须返回 1、不产包。"""
        leader = ability_row("leader_ability", mode="1", block="during_content", value="422", uid="0")
        self.case.write_logical(G.ABILITY_TABLE_LOGICALS["leader_ability"],
                                quest.build_node({"1": text_of(leader)}))
        for extra in ([], ["--list"]):
            with self.subTest(extra=extra):
                code, stdout, stderr = self.publish(["--tables", "leader_ability", *extra])
                self.assertEqual(1, code)
                self.assertIn("LeaderAbilityValues$/parseAt107", stdout)
                self.assertIn("能力闸门", stderr)
        self.assertEqual([], self.case.archives())


class FlowExitTests(unittest.TestCase):
    def workspace(self, tmp: Path):
        import wf_character_workspace as workspace_module
        workspace = workspace_module.init_workspace(tmp, 111165, 129999, "seris_dragon_king", "seris")
        manifest_path = workspace.package_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["qa"] = {"delivery_mode": "runtime_test", "release_ready": False,
                          "user_authorized_direct_real_test": True}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return workspace

    def test_preflight_and_publish_refuse_wfx_packages_before_the_release_api(self):
        import wf_character_flow as flow
        from test_character_flow import FakeReleaseModule
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.workspace(Path(tmp))
            common = workspace.package_dir / "roots" / "common"
            target = common / Path(*G.UNIQUE_CONDITION_LOGICAL.split("/"))
            target.parent.mkdir(parents=True, exist_ok=True)
            original = target.read_bytes() if target.is_file() else None
            rows = G.decode_rows(original) if original else {}
            rows[str(UID)] = unique_text()
            target.write_bytes(quest.build_node(rows))

            fake = FakeReleaseModule()
            code, result = flow.run_command(["preflight", "--workspace", str(workspace.root)],
                                            release_module=fake)
            self.assertEqual(3, code)
            self.assertEqual([], fake.preflight_calls)
            self.assertEqual("local-mumu", result["client_capability_gate"]["profile"])
            self.assertIn("wfx-damage-v1", "\n".join(result["errors"]))

            code, result = flow.run_command(["publish", "--workspace", str(workspace.root),
                                             "--confirm", "DIRECT_REAL_TEST", "--client-profile", "gray-1047"],
                                            release_module=fake, dev_catalog_hook=None, mana_board_hook=None)
            self.assertEqual(2, code)
            self.assertEqual([], fake.publish_calls)
            self.assertIn("gray-1047", "\n".join(result["errors"]))

    def test_clean_package_reaches_the_release_api_with_a_passing_gate(self):
        import wf_character_flow as flow
        from test_character_flow import FakeReleaseModule
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.workspace(Path(tmp))
            fake = FakeReleaseModule()
            code, result = flow.run_command(["preflight", "--workspace", str(workspace.root)],
                                            release_module=fake)
            self.assertEqual(1, len(fake.preflight_calls))
            self.assertTrue(result["client_capability_gate"]["ok"], result["client_capability_gate"])
            code, result = flow.run_command(["publish", "--workspace", str(workspace.root),
                                             "--confirm", "DIRECT_REAL_TEST"],
                                            release_module=fake, dev_catalog_hook=None, mana_board_hook=None)
            self.assertEqual(0, code, result)
            self.assertEqual(1, len(fake.publish_calls))


class ShareExitTests(unittest.TestCase):
    def setUp(self):
        from test_share_variant import VariantFixture
        self.fixture = VariantFixture("build")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_share_build_and_plan_require_an_explicit_profile(self):
        import wf_share_variant as variant_mod
        with self.assertRaisesRegex(variant_mod.VariantError, "--client-profile"):
            self.fixture.build(anchor_from="1.4.130", client_profile=None)
        self.assertFalse(self.fixture.out.exists())
        for command in ("plan", "build"):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                code = variant_mod.main([command, "--tag", "t0729", "--cdn", str(self.fixture.cdn),
                                         "--repo-root", str(self.fixture.repo), "--out", str(self.fixture.out),
                                         "--foreign-lineage", "--anchor", "1.4.130"])
            with self.subTest(command=command):
                self.assertEqual(2, code)
                self.assertIn("--client-profile", stderr.getvalue())
        self.assertFalse(self.fixture.out.exists())

    def test_wfx_content_is_refused_for_the_named_receiver(self):
        import wf_share_variant as variant_mod
        from test_share_variant import write_zip
        write_zip(self.fixture.cdn / "archive-common-diff" / "pinball-1.4.55-1.4.56-1-mod07290102.zip",
                  {G.UNIQUE_CONDITION_LOGICAL: quest.build_node({str(UID): unique_text()})})
        with self.assertRaisesRegex(variant_mod.VariantError, "gray-1047"):
            self.fixture.build(anchor_from="1.4.130", variants=("full",), client_profile="gray-1047")
        self.assertFalse(self.fixture.out.exists())

    def test_clean_share_declares_the_profile(self):
        report = self.fixture.build(anchor_from="1.4.130", variants=("full",), client_profile="gray-1047")
        self.assertEqual("gray-1047", report["clientProfile"])
        pack = self.fixture.out / "wfshare-1.4.130-to-1.4.131-full"
        requires = json.loads((pack / "requires.json").read_text(encoding="utf-8"))
        self.assertEqual("gray-1047", requires["requires"]["clientProfile"])
        self.assertEqual([], requires["requires"]["clientCapabilities"])
        self.assertNotIn("bundledClientPatches", requires["requires"])
        self.assertIn("gray-1047", (pack / "说明.txt").read_text(encoding="utf-8"))

    # ---- 作者裁决 #3:分享包 = 数据 + 随包补丁,档案按「装上随包补丁后」计算

    def patch_report(self, payload: dict, name: str = "prepare-report.json") -> Path:
        path = Path(self.fixture._tmp.name) / "patch" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def ea_423_edge(self):
        from test_share_variant import write_zip
        gauge_ea = ability_row("equipment_enhancement_ability", mode="1", block="during_content",
                               value="423", uid="8")
        write_zip(self.fixture.cdn / "archive-common-diff" / "pinball-1.4.55-1.4.56-1-mod07290102.zip",
                  {G.ABILITY_TABLE_LOGICALS["equipment_enhancement_ability"]:
                   quest.build_node({"5920001": text_of(gauge_ea)})})

    def test_bundled_patch_counts_for_the_receiver(self):
        import wf_share_variant as variant_mod
        self.ea_423_edge()
        with self.assertRaisesRegex(variant_mod.VariantError, "equipment-gauge-gain-rules-v1"):
            self.fixture.build(anchor_from="1.4.130", variants=("full",), client_profile="gray-1047")
        self.assertFalse(self.fixture.out.exists())
        report_path = self.patch_report({
            "capabilities_added": ["equipment-rules-v1", "equipment-gauge-gain-rules-v1"],
            "target_abc_sha256": "d9" * 32})
        report = self.fixture.build(anchor_from="1.4.130", variants=("full",), client_profile="gray-1047",
                                    bundled_client_patches=[report_path])
        self.assertEqual("gray-1047", report["clientProfile"])
        bundled = report["bundledClientPatches"][0]
        self.assertEqual(["equipment-rules-v1", "equipment-gauge-gain-rules-v1"], bundled["capabilitiesAdded"])
        self.assertEqual(hashlib.sha256(report_path.read_bytes()).hexdigest(), bundled["reportSha256"])
        pack = self.fixture.out / "wfshare-1.4.130-to-1.4.131-full"
        requires = json.loads((pack / "requires.json").read_text(encoding="utf-8"))["requires"]
        self.assertEqual("gray-1047", requires["clientProfile"])
        self.assertIn("equipment-gauge-gain-rules-v1", requires["clientCapabilities"])
        self.assertEqual(bundled, requires["bundledClientPatches"][0])
        readme = (pack / "说明.txt").read_text(encoding="utf-8")
        self.assertIn("随包补丁", readme)
        self.assertIn("equipment-gauge-gain-rules-v1", readme)

    def test_bundled_patch_must_prove_what_it_adds(self):
        """只认补丁报告的 capabilities_added;整包 build-summary(含继承层)= 假设同基线,裁决 #3 不许。"""
        import wf_share_variant as variant_mod
        self.ea_423_edge()
        cases = (({"candidate_capabilities": ["equipment-gauge-gain-rules-v1"]}, "build-summary"),
                 ({"capabilities_added": ["wfx-core-v1"]}, "planned"),
                 ({"capabilities_added": ["no-such-capability-v9"]}, "没有"),
                 ({"capabilities_added": []}, "非空"))
        for number, (payload, message) in enumerate(cases):
            path = self.patch_report(payload, f"report-{number}.json")
            with self.subTest(payload=payload), self.assertRaisesRegex(variant_mod.VariantError, message):
                self.fixture.build(anchor_from="1.4.130", variants=("full",), client_profile="gray-1047",
                                   bundled_client_patches=[path])
        self.assertFalse(self.fixture.out.exists())

    def test_bundled_patch_cli_option(self):
        import wf_share_variant as variant_mod
        self.ea_423_edge()
        path = self.patch_report({"capabilities_added": ["equipment-gauge-gain-rules-v1"]})
        base = ["plan", "--tag", "t0729", "--cdn", str(self.fixture.cdn), "--repo-root", str(self.fixture.repo),
                "--out", str(self.fixture.out), "--foreign-lineage", "--anchor", "1.4.130", "--variant", "full",
                "--no-content-expectations", "--client-profile", "gray-1047"]
        for extra, expected in (([], 2), (["--bundled-client-patch", str(path)], 0)):
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                code = variant_mod.main(base + extra)
            with self.subTest(extra=extra):
                self.assertEqual(expected, code, stderr.getvalue())

    # ---- uid 上下文:本包只带引用行,wfx 行在 since 之前的链上(收方已有)

    def test_uid_references_resolve_against_the_whole_mod_chain(self):
        import wf_share_variant as variant_mod
        from test_share_variant import write_zip
        diff = self.fixture.cdn / "archive-common-diff"
        write_zip(diff / "pinball-1.4.55-1.4.56-1-mod07290102.zip",
                  {G.UNIQUE_CONDITION_LOGICAL: quest.build_node({str(UID): unique_text()})})
        write_zip(diff / "pinball-1.4.56-1.4.57-1-mod07290103.zip",
                  {G.ABILITY_TABLE_LOGICALS["ability"]: quest.build_node({"1": text_of(ability_row("ability"))})})
        params = dict(anchor_from="1.4.130", since="1.4.56", variants=("full",), client_profile="gray-1047",
                      expect_content_rows=None, dry_run=True)
        with self.assertRaisesRegex(variant_mod.VariantError, r"ability\[1\]#0"):
            self.fixture.build(**params)
        # 负对照:拿掉链尾上下文,这条只带引用行的边就推导不到
        with mock.patch.object(variant_mod, "_gate_unique_context", return_value=(None, None)):
            self.assertEqual("gray-1047", self.fixture.build(**params)["clientProfile"])


class ScopedExitTests(unittest.TestCase):
    MANIFEST = b'{"cdn_version":"1.4.54","patches":[]}\n'

    def plan(self, raw: bytes, logical: str = G.UNIQUE_CONDITION_LOGICAL):
        import wf_scoped_release as scoped
        from release_inventory_support import InventoryCase
        case = InventoryCase("setUp")
        case.setUp()
        contract = case.parse(case.payload([
            case.file_member("owner", raw, logical_path=logical)]))
        spec = scoped.EdgeSpec("1.4.311", "1.4.312", "wfxgate0928", "wfx-gate-fixture",
                               "wfx gate fixture", "wfx gate fixture", "2026-09-28")
        return scoped.build_edge_plan(contract, {("common", logical): None},
                                      lambda _member: raw, spec)

    def repository(self, root: Path):
        active = root / "asset-patch" / "active"
        active.mkdir(parents=True)
        manifest = active.parent / "manifest.json"
        manifest.write_bytes(self.MANIFEST)
        return active, manifest

    def publish(self, plan, active, manifest, **kwargs):
        import wf_scoped_release as scoped
        return scoped.publish_archives_and_manifest(
            (plan,), active, manifest,
            expected_manifest_sha256=hashlib.sha256(self.MANIFEST).hexdigest(), **kwargs)

    def test_missing_profile_and_wfx_payload_are_refused_before_any_write(self):
        import wf_scoped_release as scoped
        plan = self.plan(quest.build_node({str(UID): unique_text()}))
        with tempfile.TemporaryDirectory() as tmp:
            active, manifest = self.repository(Path(tmp))
            with self.assertRaisesRegex(scoped.ScopedReleaseError, "explicit client profile"):
                self.publish(plan, active, manifest)
            with self.assertRaisesRegex(scoped.ScopedReleaseError, "capability gate"):
                self.publish(plan, active, manifest, client_profile="gray-1047")
            with self.assertRaisesRegex(scoped.ScopedReleaseError, "未知客户端档案"):
                self.publish(plan, active, manifest, client_profile="nope")
            self.assertEqual(self.MANIFEST, manifest.read_bytes())
            self.assertEqual([], list(active.iterdir()))
            self.assertFalse((active.parent / ".wf-scoped-release.lock").exists())

    def test_clean_payload_publishes_with_an_explicit_profile(self):
        plan = self.plan(quest.build_node({"1": unique_text("unique_zeta")}))
        with tempfile.TemporaryDirectory() as tmp:
            active, manifest = self.repository(Path(tmp))
            published = self.publish(plan, active, manifest, client_profile="official")
            self.assertEqual({part.name for part in plan.parts}, {path.name for path in published})
            self.assertEqual(1, len(json.loads(manifest.read_bytes())["patches"]))

    def test_out_of_scope_construct_is_refused_before_any_write(self):
        import wf_scoped_release as scoped
        leader = ability_row("leader_ability", mode="1", block="during_content", value="422", uid="0")
        plan = self.plan(quest.build_node({"1": text_of(leader)}), G.ABILITY_TABLE_LOGICALS["leader_ability"])
        with tempfile.TemporaryDirectory() as tmp:
            active, manifest = self.repository(Path(tmp))
            with self.assertRaisesRegex(scoped.ScopedReleaseError, "parseAt107"):
                self.publish(plan, active, manifest, client_profile="local-mumu")
            self.assertEqual([], list(active.iterdir()))

    def test_uid_references_resolve_against_the_source_context(self):
        """边里只有引用 wfx uid 的 461 行:给了源 store 的 unique_condition 上下文才推导得到。"""
        import wf_scoped_release as scoped
        plan = self.plan(quest.build_node({"1": text_of(ability_row("ability"))}),
                         G.ABILITY_TABLE_LOGICALS["ability"])
        with tempfile.TemporaryDirectory() as tmp:
            active, manifest = self.repository(Path(tmp))
            with self.assertRaisesRegex(scoped.ScopedReleaseError, r"ability\[1\]#0"):
                self.publish(plan, active, manifest, client_profile="gray-1047",
                             client_unique_context={str(UID): unique_text()})
            self.assertEqual([], list(active.iterdir()))
            # 负对照:同一条边不给上下文 → 看不出引用的是 wfx 行
            self.assertTrue(self.publish(plan, active, manifest, client_profile="gray-1047"))

    def test_other_selected_edges_feed_the_context(self):
        """同批另一条边投递的 unique_condition 也进上下文(闸门逐边判,但 uid 按全批解析)。"""
        import wf_scoped_release as scoped
        referencing = self.plan(quest.build_node({"1": text_of(ability_row("ability"))}),
                                G.ABILITY_TABLE_LOGICALS["ability"])
        unique = self.plan(quest.build_node({str(UID): unique_text()}))
        with mock.patch("wfx_gate.check_entries", wraps=G.check_entries) as check:
            with self.assertRaises(scoped.ScopedReleaseError):
                scoped._client_capability_gate((referencing, unique), "gray-1047")
        context = check.call_args_list[0].kwargs["unique_context"]
        self.assertIn(str(UID), context)


class LocalScopedContextTests(unittest.TestCase):
    def test_build_captures_and_publish_passes_the_terminal_unique_condition(self):
        import wf_local_scoped_release as adapter
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = root / "store"
            path = core.table_path(store, G.UNIQUE_CONDITION_LOGICAL)
            path.parent.mkdir(parents=True)
            path.write_bytes(quest.build_node({str(UID): unique_text()}))
            captured = adapter._source_unique_condition({"common": store, "medium": root, "android": root})
            self.assertEqual(path.read_bytes(), captured)
            self.assertIsNone(adapter._source_unique_condition({"common": root / "empty"}))
            result = adapter.LocalScopedPlans(None, None, (), "primary", "compatibility", (), "d" * 64,
                                              captured)
            with mock.patch.object(adapter.scoped, "publish_archives_and_manifest",
                                   return_value=()) as publish:
                adapter.publish_local_scoped_plans(
                    result, root, selection="public", expected_manifest_sha256="0" * 64,
                    confirmation=adapter.PUBLISH_CONFIRMATION, client_profile="gray-1047")
            kwargs = publish.call_args.kwargs
            self.assertEqual("gray-1047", kwargs["client_profile"])
            self.assertIn(str(UID), kwargs["client_unique_context"])


if __name__ == "__main__":
    unittest.main()
