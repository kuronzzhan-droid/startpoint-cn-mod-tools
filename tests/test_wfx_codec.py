# -*- coding: utf-8 -*-
"""wf_wfx:wfx:<code>:<arg>:<value>:<flags>:<label> 编解码、掩码、值域与 unique_condition 行约束。"""
from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wf_battle_rules  # noqa: E402
import wf_wfx as W  # noqa: E402


class SidCodecTests(unittest.TestCase):
    def test_design_doc_examples_encode_exactly(self):
        """设计稿 4.12 调用手册里的 7 个 sid 必须原样产出、原样解回。

        例 5 按作者裁决 #2(2026-09-28)改写:码 20 并入官方乘区池,PF 伤害 = 池号 4(696/413),
        不再是正文里的伤害掩码 112(pf1|pf2|pf3,已被裁决取代,见 test_wfx_registry 的裁决钉)。"""
        cases = [
            ((21, 0, 1, 1, "wfx_leader_dmg1"), "wfx:21:0:1:1:wfx_leader_dmg1"),
            ((10, 0, -1, 1, "wfx_atk_floor100"), "wfx:10:0:-1:1:wfx_atk_floor100"),
            ((31, 127, -0.01, 0, "wfx_gauge_down1"), "wfx:31:127:-0.01:0:wfx_gauge_down1"),
            ((22, 6, -0.5, 1, "wfx_boss_skill_res50"), "wfx:22:6:-0.5:1:wfx_boss_skill_res50"),
            ((23, 0, 50000, 1, "wfx_boss_cap50k"), "wfx:23:0:50000:1:wfx_boss_cap50k"),
            ((20, 4, 0.3, 0, "wfx_pf_mul30"), "wfx:20:4:0.3:0:wfx_pf_mul30"),
            ((50, 0, 15, 1, "wfx_combo15"), "wfx:50:0:15:1:wfx_combo15"),
        ]
        for args, sid in cases:
            with self.subTest(sid=sid):
                self.assertEqual(sid, W.encode_sid(*args))
                spec = W.decode_sid(sid)
                self.assertEqual(sid, spec.sid)
                self.assertEqual((args[0], args[1], args[3], args[4]),
                                 (spec.code, spec.arg, spec.flags, spec.label))
                self.assertEqual(Decimal(W.format_value(args[2])), spec.value)

    def test_value_formatting_is_canonical(self):
        for raw, text in ((0.3, "0.3"), (-0.5, "-0.5"), (1, "1"), (100, "100"), (1e-07, "0.0000001"),
                          (-0.0, "0"), (Decimal("1.50"), "1.5"), ("-0.6667", "-0.6667"), (2.0, "2")):
            with self.subTest(raw=raw):
                self.assertEqual(text, W.format_value(raw))
        for bad in ("1e3", "0.30", "+1", "-0", "01", "", ".5", float("inf"), True, None):
            with self.subTest(bad=bad), self.assertRaises(W.WfxError):
                W.format_value(bad)

    def test_decoder_rejects_non_canonical_or_malformed_sids(self):
        for sid in ("wfx:21:0:1:1", "wfx:21:0:1:1:a:b", "wfx:021:0:1:1:a", "wfx:21:0:1.0:1:a",
                    "wfx:21:0:1e2:1:a", "wfx:21:-1:1:1:a", "wfx:21:0:1:1:", "wfx:21:0:1:1:bad label",
                    "wfx:21:0:1:1:a,b", "wfx:x:0:1:1:a", "wfxq:1:2:3:4", "unique_zeta"):
            with self.subTest(sid=sid), self.assertRaises(W.WfxError):
                W.decode_sid(sid)

    def test_classification(self):
        self.assertEqual("effect", W.classify_sid("wfx:21:0:1:1:a"))
        self.assertEqual("reserved", W.classify_sid("wfxq:990099:0:1:99000101"))
        for sid in ("wfx_21_0_1", "WFX:21:0:1:1:a", "wfx;21:0:1:1:a", "wfx21:0:1:1:a", "Wfx:21:0:1:1:a",
                    " wfx:21:0:1:1:lead", "\twfx:21:0:1:1:tab", " WFXQ:1"):
            with self.subTest(sid=sid):
                self.assertEqual("lookalike", W.classify_sid(sid))
        self.assertIsNone(W.classify_sid("cursed_dice_59100103"))
        self.assertIsNone(W.classify_sid(""))
        self.assertIsNone(W.classify_sid(None))

    def test_whitespace_padded_sid_is_not_a_canonical_effect(self):
        """客户端按原值 split(":"):首段 " wfx" 不是 "wfx",效果不会生效。解码与分类都不许 strip。"""
        with self.assertRaises(W.WfxError):
            W.decode_sid(" wfx:21:0:1:1:lead")
        with self.assertRaises(W.WfxError):
            W.decode_sid("wfx:21:0:1:1:trail ")


class SemanticValidationTests(unittest.TestCase):
    def problems(self, sid: str) -> list[str]:
        return W.spec_problems(W.parse_sid(sid))

    def test_value_ranges_follow_the_registry(self):
        ok = ["wfx:10:0:-1:0:a", "wfx:10:0:-0.6:0:a", "wfx:21:0:1:0:a", "wfx:23:255:50000:0:a",
              "wfx:30:1:0:0:a", "wfx:31:127:-1:0:a", "wfx:31:4:2:0:a", "wfx:40:0:-0.3:0:a",
              "wfx:40:2:120:0:a", "wfx:50:0:1:1:a", "wfx:51:0:0:1:a", "wfx:52:0:0:0:a", "wfx:52:0:3:0:a",
              "wfx:20:0:-1:0:a", "wfx:20:4:0.3:0:a", "wfx:20:260:0.1:0:a", "wfx:22:32512:5:0:a",
              "wfx:31:2:0.5:0:a"]         # 只选移动充能(423 规则允许)
        for sid in ok:
            with self.subTest(sid=sid):
                self.assertEqual([], self.problems(sid))
        bad = ["wfx:10:0:-0.5:0:a",       # 下限必须 < -0.5
               "wfx:10:0:-1.5:0:a",       # 钳到 -1.0
               "wfx:10:1:-1:0:a",         # 不用参数位
               "wfx:21:0:0:0:a",          # 上限 >= 1
               "wfx:21:0:1.5:0:a",        # 上限取整数
               "wfx:20:0:-1.01:0:a",      # 每层 >= -1
               "wfx:20:32768:0.3:0:a",    # 池号/属性组外的位
               "wfx:20:112:0.3:0:a",      # 裁决 #2 之后 112 不是池号(旧伤害掩码写法)
               "wfx:20:5:0.3:0:a",        # 只有 5 个官方池
               "wfx:20:6:0.3:0:a",        # 旧掩码「技能主位|合击位」不再合法
               "wfx:30:0:0:0:a",          # 回槽掩码至少选一种加槽类型
               "wfx:30:1:1:0:a",          # 不读的值规范写 0
               "wfx:40:7:0.1:0:a",        # 冲刺参数号 0–6
               "wfx:50:0:0:0:a",          # 连击上限 >= 1
               "wfx:52:0:4:0:a",          # PF 最高 3 档
               "wfx:51:0:0:2:a",          # flags 未定义位
               "wfx:11:0:1:0:a",          # 号段内未定义
               "wfx:81:0:1:0:a"]          # 预留号段
        for sid in bad:
            with self.subTest(sid=sid):
                self.assertTrue(self.problems(sid), sid)

    def test_gauge_arg_reuses_the_423_mask_layout(self):
        mask = W.gauge_arg(["skill", "ability"], origins=["weapon"], owners=["other"])
        self.assertEqual(wf_battle_rules.gauge_mask(["skill", "ability"], origins=["weapon"], owners=["other"]),
                         mask)
        self.assertEqual([], self.problems(f"wfx:31:{mask}:-0.5:0:a"))
        # 423 的专项规则照样适用:移动充能不能再带来源位
        self.assertTrue(self.problems(f"wfx:30:{2 | 1024}:0:0:a"))

    def test_damage_mask_groups(self):
        self.assertEqual(0, W.damage_mask())
        self.assertEqual(112, W.damage_mask(["pf1", "pf2", "pf3"]))
        self.assertEqual(6, W.damage_mask(["skill_main", "skill_unison"]))
        fire_skill = W.damage_mask(["skill_main"], ["fire"])
        self.assertEqual(2 | 256, fire_skill)
        self.assertEqual(256 << 6, W.damage_mask(elements=["colorless"]))
        self.assertEqual((["skill_main"], ["fire"]), W.damage_mask_parts(fire_skill))
        self.assertEqual(255 | 32512, W.damage_mask(
            ["direct", "skill_main", "skill_unison", "ability", "pf1", "pf2", "pf3", "other"],
            ["fire", "water", "thunder", "wind", "light", "dark", "colorless"]))
        with self.assertRaises(W.WfxError):
            W.damage_mask(["poison"])
        with self.assertRaises(W.WfxError):
            W.damage_mask(elements=["ice"])

    def test_damage_pool_arg_follows_ruling_two(self):
        """作者裁决 #2:码 20 的 arg = 官方独立乘区池号 + 属性组,不是伤害掩码。"""
        self.assertEqual(0, W.damage_pool_arg("all"))
        self.assertEqual(4, W.damage_pool_arg("power_flip"))
        self.assertEqual(2 | 256, W.damage_pool_arg("skill", ["fire"]))
        self.assertEqual(3 | (256 << 3), W.damage_pool_arg("ability", ["wind"]))
        pool, elements = W.damage_pool_parts(1 | 256 | (256 << 5))
        self.assertEqual(("direct", "693", "410"),
                         (pool["name"], pool["instant_content"], pool["during_content"]))
        self.assertEqual(["fire", "dark"], elements)
        for bad in (("pf1",), ("skill_main",), ("all", ["ice"])):
            with self.subTest(bad=bad), self.assertRaises(W.WfxError):
                W.damage_pool_arg(*bad)
        with self.assertRaises(W.WfxError):
            W.damage_pool_parts(112)
        # 码 21–23 仍是伤害掩码(裁决 #2 不影响它们)
        self.assertEqual([], self.problems("wfx:21:112:1:0:a"))
        self.assertEqual([], self.problems("wfx:22:6:-0.5:0:a"))

    def test_required_capabilities_include_dependencies(self):
        self.assertEqual(["wfx-damage-v1", "wfx-core-v1"],
                         W.required_capabilities(W.decode_sid("wfx:21:0:1:1:a")))
        self.assertEqual(["wfx-gauge-v1", "wfx-core-v1", "gauge-gain-rules-v1"],
                         W.required_capabilities(W.decode_sid("wfx:31:127:-0.01:0:a")))
        self.assertEqual(["wfx-dash-v1", "wfx-core-v1", "dash-parameter-v1"],
                         W.required_capabilities(W.decode_sid("wfx:40:0:-0.3:0:a")))
        self.assertEqual(["wfx-lock-v1", "wfx-core-v1"],
                         W.required_capabilities(W.decode_sid("wfx:51:0:0:1:a")))

    def test_encode_refuses_anything_the_decoder_would_reject(self):
        for args in ((21, 0, 0, 0, "a"), (99, 0, 1, 0, "a"), (21, 0, 1, 2, "a"), (21, 0, 1, 0, "a:b"),
                     (21, -1, 1, 0, "a"), (21, 0, 1, 0, "")):
            with self.subTest(args=args), self.assertRaises(W.WfxError):
                W.encode_sid(*args)

    def test_apply_targets(self):
        combo = W.decode_sid("wfx:50:0:15:1:a")
        self.assertEqual([], W.apply_target_problems(combo, 2))
        self.assertEqual([], W.apply_target_problems(combo, "5"))
        self.assertTrue(W.apply_target_problems(combo, 0))
        self.assertEqual([], W.apply_target_problems(W.decode_sid("wfx:21:0:1:1:a"), 0))


class UniqueRowTests(unittest.TestCase):
    def test_layout_matches_the_cursed_weapon_helper(self):
        import wf_cursed_weapons
        sid = W.encode_sid(21, 0, 1, 1, "wfx_leader_dmg1")
        ours = W.unique_row(sid, "噬主", "unique_devil_leader", "99999999", "1", bad=True)
        theirs = wf_cursed_weapons.unique_row(sid, "噬主", "unique_devil_leader", "99999999", "1", bad=True)
        self.assertEqual(theirs, ours)
        self.assertEqual(W.UNIQUE_COLUMNS, len(ours))

    def test_row_constraints(self):
        stacked = W.encode_sid(31, 127, -0.01, 0, "wfx_gauge_down1")
        pinned = W.encode_sid(50, 0, 15, 1, "wfx_combo15")
        self.assertEqual(stacked, W.unique_row(stacked, "倒流", "unique_gerald_time_seal", "99999999", "99",
                                               bad=True)[0])
        with self.assertRaisesRegex(W.WfxError, "叠层"):
            W.unique_row(stacked, "倒流", "unique_gerald_time_seal", "99999999", "(None)", bad=True)
        with self.assertRaisesRegex(W.WfxError, "pin"):
            W.unique_row(pinned, "孤星", "unique_devil_leader", "99999999", "1", bad=True, cancelable=True)
        with self.assertRaisesRegex(W.WfxError, "图标"):
            W.unique_row(pinned, "孤星", "unique_devil_leader", "99999999", "1", bad=True,
                         known_icons={"unique_zeta"})
        self.assertEqual(pinned, W.unique_row(pinned, "孤星", "unique_devil_leader", "99999999", "1", bad=True,
                                              known_icons={"unique_devil_leader"})[0])
        with self.assertRaisesRegex(W.WfxError, "持续帧"):
            W.unique_row(pinned, "孤星", "unique_devil_leader", "0", "1", bad=True)

    def test_non_wfx_rows_are_not_judged(self):
        row = ["unique_zeta", "阿尔贝斯之缚", "battle/common/unique_condition/unique_zeta", "900", "(None)",
               "(None)", "(None)", "(None)", "(None)", "false", "false", "1", "1", "true", "(None)"]
        self.assertEqual([], W.unique_row_problems(row))
        self.assertTrue(W.unique_row_problems(["wfxq:1:2:3:4"] + row[1:]))
        self.assertTrue(W.unique_row_problems(["wfx_typo"] + row[1:]))
        for sid in ("WFX:21:0:1:1:a", "wfx;21:0:1:1:a", "wfx21:0:1:1:a", " wfx:21:0:1:1:lead"):
            with self.subTest(sid=sid):
                problems = W.unique_row_problems([sid] + row[1:])
                self.assertEqual(1, len(problems), problems)
                self.assertIn("静默失效", problems[0])
        self.assertIn("空白", W.unique_row_problems([" wfx:21:0:1:1:lead"] + row[1:])[0])

    def test_uid_allocation_and_collision(self):
        self.assertEqual(99000001, W.allocate_uid([]))
        self.assertEqual(99000003, W.allocate_uid(["99000001", 99000002, "1"]))
        self.assertEqual(7, W.allocate_uid(["5", "6"], start=5))
        self.assertEqual([], W.uid_problems(99000101, ["99000100"]))
        self.assertTrue(W.uid_problems("99000100", ["99000100"]))
        for bad in ("0", "-1", "abc", "2147483648"):
            self.assertTrue(W.uid_problems(bad, []), bad)


if __name__ == "__main__":
    unittest.main()
