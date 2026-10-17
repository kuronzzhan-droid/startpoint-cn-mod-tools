# -*- coding: utf-8 -*-
"""AMF3 编码器回归测试(纯合成数据,不碰真实 store)。

覆盖:encode_amf3 ↔ parse_dsl 往返、int/double 类型保持、字符串引用表、
JSON 文本管道、非法结构拒绝。全库 1035 个真实 DSL 文件的字节级往返
已在 2026-07-06 落地时验证(见 docs/技能形态切换与资产包导入结论.md)。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import wf_dsl  # noqa: E402


SYNTH = ["ActionDsl", 2, ["None"], False, True, None, 0, -18, 120,
         ["Block", [["Command", ["StopBall", -18, 120, ["Stop"], ["AB"], 0]],
                    ["Command", ["Rectangle", [{"min": 300, "max": 300}],
                                 [{"min": 2000.0, "max": 2000.5}]]]]],
         "重复字符串", "重复字符串", 268435455, -268435456, 2.5]


class TestAmf3Encoder(unittest.TestCase):
    def test_roundtrip_synthetic(self):
        data = wf_dsl.encode_amf3(SYNTH)
        tree = wf_dsl.parse_dsl(data)["tree"]
        self.assertEqual(tree, SYNTH)

    def test_int_double_types_preserved(self):
        data = wf_dsl.encode_amf3([1, 1.0, -5, -5.0])
        tree = wf_dsl.parse_dsl(data)["tree"]
        self.assertEqual([type(x) for x in tree], [int, float, int, float])

    def test_string_table_refs(self):
        """重复字符串必须走引用表(与官方序列化器同构,保证字节级一致)。"""
        one = wf_dsl.encode_amf3(["abcdef"])
        two = wf_dsl.encode_amf3(["abcdef", "abcdef"])
        # 第二次出现只占 marker(1B)+ref(1B),远小于重复内联
        self.assertLess(len(two) - len(one), 4)

    def test_json_text_pipeline(self):
        data = wf_dsl.encode_amf3(SYNTH)
        txt = wf_dsl.dsl_to_json_text(data)
        self.assertEqual(wf_dsl.json_text_to_dsl(txt), data)

    def test_out_of_range_int_falls_to_double(self):
        data = wf_dsl.encode_amf3([1 << 29])
        tree = wf_dsl.parse_dsl(data)["tree"]
        self.assertEqual(tree, [float(1 << 29)])

    def test_reject_bad_nodes(self):
        with self.assertRaises(ValueError):
            wf_dsl.encode_amf3([{"": 1}])       # 空对象键
        with self.assertRaises(ValueError):
            wf_dsl.encode_amf3([(1, 2)])         # 元组不是合法节点

    def test_u29_padded_still_readable(self):
        """历史原地补丁(非规范 U29)与新编码器共存:解析端两者都认。"""
        raw = wf_dsl.encode_u29_padded(300, 3)
        v, i = wf_dsl._read_u29(raw, 0)
        self.assertEqual((v, i), (300, 3))


# ---------------------------------------------------------------- 方向门禁
import math  # noqa: E402


def _slv(v):
    return [{"min": float(v), "max": float(v)}]


def _hit_area(*, coord="AB", angle=0.0, shape=None, valign="Bottom",
              subject=1, bind=20, fx=(), dmg=()):
    """按 TypePackerResource2.as h[24] 的 26 个位置参数拼一条 CreateHitArea。"""
    shape = shape if shape is not None else ["Rectangle", _slv(180), _slv(2400)]
    return ["Command", ["CreateHitArea", "*", subject, [coord], 0, 0, angle,
                        False, False, shape, ["Center"], [valign], ["Single"],
                        ["SpecifyHitAreaLifetimeDirectly", 40],
                        ["CalculatedUsingMaxNumOfHits", 1], ["None"], False,
                        True, ["None"], bind, ["Block", list(fx)],
                        bind + 1, bind + 2, ["Block", list(dmg)], 0, 0,
                        ["None"]]]


def _show_effect(*, subject=20, coord="AB", angle=0.0, path="x/y"):
    return ["Command", ["ShowEffect", "lbl", ["SpecifyEffectDirectly", path],
                        subject, ["ForesideOfCharacter"],
                        ["UntilTargetTerminates"], [coord], 0, 0, angle,
                        True, True, ["None"]]]


def _ref_point(*, subject=-18, coord="AB", bind=1, body=()):
    return ["Command", ["CreateReferencePoint", subject, [coord], 0, 0, 0,
                        False, False, ["Single"], 90, bind,
                        ["Block", list(body)]]]


def _move_hit_area(*, subject=20, coord="CD"):
    return ["Command", ["MoveHitArea", subject, [coord], 0, 21, ["None"]]]


def _root(*body):
    return ["ActionDsl", 1, ["None"], False, False, False, False, False,
            False, False, 0, ["Block", list(body)]]


class BeamDirectionGateTests(unittest.TestCase):
    """玩家侧长柱判定的朝向门禁(见 wf_dsl.beam_direction_problems 的注释)。"""

    def test_player_convention_angle_zero_is_clean(self):
        """官方玩家侧长柱主流写法 (AB, Bottom, 0°) 47/81 条 —— 必须 0 命中。"""
        tree = _root(_hit_area(angle=0.0))
        self.assertEqual(wf_dsl.beam_direction_problems(tree), [])

    def test_enemy_convention_angle_180_is_flagged(self):
        """敌方蓝本 (AB, Bottom, 180°):克隆到玩家侧没翻转 = 朝自己那半场开炮。"""
        tree = _root(_hit_area(angle=math.pi))
        probs = wf_dsl.beam_direction_problems(tree)
        self.assertEqual(len(probs), 1)
        self.assertIn("180", probs[0])

    def test_sideways_90_and_270_are_flagged(self):
        """歼灭者原来那个十字里的两道横柱:官方角色程序零先例,判为缺陷。"""
        tree = _root(_hit_area(angle=math.pi / 2, bind=20),
                     _hit_area(angle=3 * math.pi / 2, bind=30))
        self.assertEqual(len(wf_dsl.beam_direction_problems(tree)), 2)

    def test_small_tilt_toward_enemy_is_clean(self):
        """朝敌方的小角度扇形(官方 GH/Top ±6°~±12° 有大量先例)不能误报。"""
        for deg in (-24, -6, 6, 24, 89, -89):
            tree = _root(_hit_area(angle=math.radians(deg)))
            self.assertEqual(wf_dsl.beam_direction_problems(tree), [],
                             f"{deg}° 被误报")

    def test_boundary_90_is_flagged_89_is_not(self):
        self.assertEqual(
            wf_dsl.beam_direction_problems(_root(_hit_area(angle=math.radians(89)))), [])
        self.assertEqual(
            len(wf_dsl.beam_direction_problems(_root(_hit_area(angle=math.radians(90))))), 1)

    def test_valign_center_rect_is_not_a_beam(self):
        """VAlign=Center 的矩形对称,角度只是朝向不是「往哪边长」,不判。"""
        tree = _root(_hit_area(angle=math.pi, valign="Center"))
        self.assertEqual(wf_dsl.beam_direction_problems(tree), [])

    def test_short_rect_is_not_a_beam(self):
        """交错圣剑那种 100×200 的短矩形不是光柱,门槛 1000 之下不判。"""
        tree = _root(_hit_area(angle=math.pi,
                               shape=["Rectangle", _slv(100), _slv(200)]))
        self.assertEqual(wf_dsl.beam_direction_problems(tree), [])

    def test_circle_is_not_a_beam(self):
        tree = _root(_hit_area(angle=math.pi, shape=["Circle", _slv(1600)]))
        self.assertEqual(wf_dsl.beam_direction_problems(tree), [])

    def test_non_ab_coord_is_runtime_dependent_and_skipped(self):
        """CD/EF/GH 的 r 取决于运行时目标,静态判不了,一律放过(否则误报 GH 21 条)。"""
        for coord in ("CD", "EF", "GH"):
            tree = _root(_hit_area(coord=coord, angle=math.pi))
            self.assertEqual(wf_dsl.beam_direction_problems(tree), [],
                             f"{coord} 不该被静态判定")

    def test_nested_inside_reference_point_and_wait(self):
        """真实程序里判定区埋在 CreateReferencePoint → Wait 里,遍历必须下钻。"""
        inner = ["Event", ["Wait", 10, "t", ["Block", [_hit_area(angle=math.pi)]]]]
        tree = _root(_ref_point(body=[inner]))
        self.assertEqual(len(wf_dsl.beam_direction_problems(tree)), 1)

    def test_official_precedent_towa_namakubi_shape_is_flagged(self):
        """官方唯一先例存档:rare2 `towa_namakubi` 的 2000 长柱确实写着 180°。

        规则对它会报警 —— 这不是规则过严,而是官方 951 个角色程序里独此一家
        (另外 3 条 180/90/270 在 `skill_invoker/`,是场地役物不是角色技能)。
        自制包不该复制这个写法,所以门禁保持严格。
        """
        tree = _root(_hit_area(angle=math.pi,
                               shape=["Rectangle", _slv(100), _slv(2000)]))
        self.assertEqual(len(wf_dsl.beam_direction_problems(tree)), 1)


class CoordSysSourceGateTests(unittest.TestCase):
    """CoordSysSource=CD 的合法承载体(getDirCD 在成员/球上直接 throw)。"""

    def test_cd_on_ball_is_flagged(self):
        tree = _root(_show_effect(subject=-18, coord="CD"))
        probs = wf_dsl.coord_sys_source_problems(tree)
        self.assertEqual(len(probs), 1)
        self.assertIn("-18", probs[0])

    def test_cd_on_self_member_is_flagged(self):
        tree = _root(_hit_area(subject=-17, coord="CD"))
        self.assertEqual(len(wf_dsl.coord_sys_source_problems(tree)), 1)

    def test_cd_on_hit_area_bind_is_clean(self):
        """官方 7094 条 ShowEffect coord=CD 全是挂在判定区绑定 id 上,必须放过。"""
        tree = _root(_hit_area(bind=20, fx=[_show_effect(subject=20, coord="CD")],
                               dmg=[]))
        self.assertEqual(wf_dsl.coord_sys_source_problems(tree), [])

    def test_move_hit_area_cd_on_bind_is_clean(self):
        tree = _root(_move_hit_area(subject=20, coord="CD"))
        self.assertEqual(wf_dsl.coord_sys_source_problems(tree), [])

    def test_ab_on_ball_is_clean(self):
        """AB 不读 getDirCD,挂在球上是官方最常见写法(CreateReferencePoint -18)。"""
        tree = _root(_ref_point(subject=-18, coord="AB"))
        self.assertEqual(wf_dsl.coord_sys_source_problems(tree), [])

    def test_reference_point_cd_on_ball_is_flagged(self):
        tree = _root(_ref_point(subject=-18, coord="CD"))
        self.assertEqual(len(wf_dsl.coord_sys_source_problems(tree)), 1)


class PlayerSideDslProblemsTests(unittest.TestCase):
    def test_combined_reports_both_families(self):
        tree = _root(_hit_area(angle=math.pi, bind=20),
                     _show_effect(subject=-18, coord="CD"))
        self.assertEqual(len(wf_dsl.player_side_dsl_problems(tree)), 2)

    def test_clean_program_reports_nothing(self):
        """修好之后的歼灭者「净化」形状:四道平行上射光柱 + CD 贴图挂判定区。"""
        rays = [_hit_area(angle=0.0, bind=20 + 3 * i,
                          fx=[_show_effect(subject=20 + 3 * i, coord="CD",
                                           angle=math.pi)])
                for i in range(4)]
        tree = _root(_ref_point(body=rays))
        self.assertEqual(wf_dsl.player_side_dsl_problems(tree), [])


if __name__ == "__main__":
    unittest.main()
