# -*- coding: utf-8 -*-
"""wf_ui_derive_gate:角色 UI 派生图三条判据的单测。

判据本身的官方基线口径见模块 docstring;这里全部用合成图,不读 store、不读归档,
所以离线可跑。合成图刻意做成「与官方形状一致 / 只在被测那一点上偏离」,
这样每个用例失败时指向唯一原因。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wf_ui_derive_gate as gate  # noqa: E402


def solid(slot: str, rgb=(120, 90, 60), alpha: int = 255) -> np.ndarray:
    w, h = gate.OFFICIAL_ICON_SIZES[slot]
    arr = np.zeros((h, w, 4), np.uint8)
    arr[:, :, 0], arr[:, :, 1], arr[:, :, 2] = rgb
    arr[:, :, 3] = alpha
    return arr


def gradient(slot: str) -> np.ndarray:
    """带横纵梯度的图:缩放后仍然可比,用来测「同宽高比槽同构图」。"""
    w, h = gate.OFFICIAL_ICON_SIZES[slot]
    yy, xx = np.mgrid[0:h, 0:w]
    arr = np.zeros((h, w, 4), np.uint8)
    arr[:, :, 0] = (xx * 255 // max(w - 1, 1)).astype(np.uint8)
    arr[:, :, 1] = (yy * 255 // max(h - 1, 1)).astype(np.uint8)
    arr[:, :, 2] = 64
    arr[:, :, 3] = 255
    return arr


def ellipse_mask(slot: str) -> np.ndarray:
    """一个内切椭圆蒙版,近似官方的圆/六边形/水滴条。"""
    w, h = gate.OFFICIAL_ICON_SIZES[slot]
    yy, xx = np.mgrid[0:h, 0:w]
    r = ((xx - (w - 1) / 2) / (w / 2)) ** 2 + ((yy - (h - 1) / 2) / (h / 2)) ** 2
    return np.where(r <= 1.0, 255, 0).astype(np.uint8)


class CoverageTests(unittest.TestCase):
    def test_opaque_square_passes(self):
        self.assertEqual(gate.derived_icon_problems({'square': solid('square')}), [])

    def test_cutout_icon_is_flagged(self):
        """抠图直接落盘 = 不透明占比掉到 0.2,游戏里角色浮在空框里。"""
        arr = solid('square')
        arr[:, :, 3] = 0
        arr[60:120, 60:120, 3] = 255          # 只剩中间一小块
        problems = gate.derived_icon_problems({'square': arr})
        self.assertTrue(any('不透明占比' in p for p in problems), problems)

    def test_opaque_skill_cutin_is_flagged(self):
        """cut-in 是透明抠图;整幅不透明会在战斗里盖住场地。"""
        problems = gate.derived_icon_problems({'skill_cutin': solid('skill_cutin')})
        self.assertTrue(any('skill_cutin' in p and '高于官方上界' in p for p in problems),
                        problems)

    def test_normal_skill_cutin_passes(self):
        arr = solid('skill_cutin')
        arr[:, :, 3] = 0
        arr[:, :400, 3] = 255                  # 约 0.39 覆盖,落在官方 p10..p90
        self.assertEqual(gate.derived_icon_problems({'skill_cutin': arr}), [])


def partial(slot: str, want: float) -> np.ndarray:
    """按列铺满 alpha,做出指定不透明占比的合成图(用来钉住占比包络本身)。"""
    w, h = gate.OFFICIAL_ICON_SIZES[slot]
    arr = solid(slot)
    arr[:, :, 3] = 0
    cols = max(0, min(w, int(round(want * w))))
    arr[:, :cols, 3] = 255
    return arr


class OfficialConstantTests(unittest.TestCase):
    """把官方普查数值**逐字钉死**。

    变异检验的教训:只钉结构不钉常量,把 `battle_control_board` /
    `cutin_skill_chain` / `square` 任一条包络撑成 (0.0, 1.0),整套用例照样全绿 ——
    而不透明占比正是抓住「深渊之兽头像只有上半」(0.303 vs 下界 0.690)的那条判据。

    口径:`.cdn/cn/archive-medium-full/pinball-1.4.0-*.zip`,489 个官方角色,
    只统计等于官方标准尺寸的样张(门禁也只对标准尺寸做占比判据)。
    """

    COMBINED = {
        'square': (0.697, 1.000),
        'square_132_132': (0.702, 1.000),
        'square_round_136_136': (0.699, 0.986),
        'square_round_95_95': (0.707, 0.987),
        'battle_member_status': (0.663, 0.808),
        'battle_control_board': (0.682, 0.683),
        'cutin_skill_chain': (0.753, 0.754),
        'thumb_level_up': (0.639, 0.995),
        'thumb_party_main': (0.447, 0.995),
        'thumb_party_unison': (0.643, 0.996),
        'skill_cutin': (0.208, 0.845),
    }
    BY_LEVEL = {
        'square': {'0': (0.690, 1.000), '1': (0.727, 1.000)},
        'square_132_132': {'0': (0.698, 1.000), '1': (0.732, 1.000)},
        'square_round_136_136': {'0': (0.695, 0.986), '1': (0.731, 0.986)},
        'square_round_95_95': {'0': (0.700, 0.987), '1': (0.737, 0.987)},
        'battle_member_status': {'0': (0.657, 0.808), '1': (0.680, 0.808)},
        'battle_control_board': {'0': (0.682, 0.683), '1': (0.682, 0.683)},
        'cutin_skill_chain': {'0': (0.753, 0.754), '1': (0.753, 0.754)},
        'thumb_level_up': {'0': (0.636, 0.995), '1': (0.691, 0.995)},
        'thumb_party_main': {'0': (0.569, 0.995), '1': (0.451, 0.995)},
        'thumb_party_unison': {'0': (0.638, 0.996), '1': (0.693, 0.996)},
        'skill_cutin': {'0': (0.198, 0.741), '1': (0.251, 0.868)},
    }
    # 异形槽的官方众数蒙版自身的覆盖率(build_official_masks_20260828d.py 的产物)。
    # 派生图套上蒙版后不透明占比**恒等于**它,所以它就是这些槽的包络上界。
    SHAPE_MASK_COVERAGE = {
        'battle_control_board': 0.683,
        'cutin_skill_chain': 0.754,
        'battle_member_status': 0.808,
        'square_round_136_136': 0.986,
        'square_round_95_95': 0.987,
        'thumb_level_up': 0.995,
        'thumb_party_main': 0.995,
        'thumb_party_unison': 0.996,
    }

    def test_combined_envelope_is_pinned(self):
        self.assertEqual(gate.OFFICIAL_COVERAGE, self.COMBINED)

    def test_per_level_envelope_is_pinned(self):
        self.assertEqual(gate.OFFICIAL_COVERAGE_BY_LEVEL, self.BY_LEVEL)

    def test_shape_slot_upper_bound_is_the_official_mask_coverage(self):
        """异形槽的上界不是随手写的,是它自己那张官方蒙版的覆盖率。"""
        for slot, want in self.SHAPE_MASK_COVERAGE.items():
            self.assertIn(slot, gate.SHAPE_SLOTS, slot)
            for level in ('0', '1'):
                self.assertAlmostEqual(gate.coverage_envelope(slot, level)[1], want,
                                       places=3, msg=f'{slot}_{level}')

    def test_opaque_icon_slots_keep_a_high_lower_bound(self):
        """官方图标是**有底的不透明图**;下界一旦被放低,抠图直落就抓不住了。"""
        for slot in ('square', 'square_132_132', 'square_round_136_136',
                     'square_round_95_95', 'battle_member_status',
                     'battle_control_board', 'cutin_skill_chain'):
            for level in ('0', '1', None):
                self.assertGreaterEqual(gate.coverage_envelope(slot, level)[0], 0.60,
                                        f'{slot} level={level}')

    def test_cutin_upper_bound_stays_below_full_opacity(self):
        """cut-in 叠在场地上;整幅不透明 = 一块盖住战场的实心矩形。"""
        for level in ('0', '1', None):
            hi = gate.coverage_envelope('skill_cutin', level)[1]
            self.assertLess(hi + gate.COVERAGE_SLACK, 1.0, f'level={level}')

    def test_every_slot_has_an_envelope_and_a_size(self):
        self.assertEqual(set(gate.OFFICIAL_COVERAGE), set(gate.OFFICIAL_ICON_SIZES))
        self.assertEqual(set(gate.OFFICIAL_COVERAGE_BY_LEVEL), set(gate.OFFICIAL_ICON_SIZES))

    def test_envelope_bounds_are_ordered(self):
        for slot in gate.OFFICIAL_ICON_SIZES:
            for level in ('0', '1', None):
                lo, hi = gate.coverage_envelope(slot, level)
                self.assertLessEqual(lo, hi, f'{slot} level={level}')


class LowCoverageTests(unittest.TestCase):
    """覆盖率掉到 0.30 = 抠图直落,每个不透明槽都必须报出来。"""

    def test_thumb_party_main_at_030_is_rejected(self):
        for level in ('0', '1', None):
            problems = gate.derived_icon_problems(
                {'thumb_party_main': partial('thumb_party_main', 0.30)}, level=level)
            self.assertTrue(any('低于官方下界' in p for p in problems), f'level={level}')

    def test_control_board_at_030_is_rejected(self):
        problems = gate.derived_icon_problems(
            {'battle_control_board': partial('battle_control_board', 0.30)}, level='0')
        self.assertTrue(any('低于官方下界' in p for p in problems), problems)

    def test_cutin_skill_chain_at_030_is_rejected(self):
        problems = gate.derived_icon_problems(
            {'cutin_skill_chain': partial('cutin_skill_chain', 0.30)}, level='0')
        self.assertTrue(any('低于官方下界' in p for p in problems), problems)

    def test_square_round_at_030_is_rejected(self):
        problems = gate.derived_icon_problems(
            {'square_round_136_136': partial('square_round_136_136', 0.30)}, level='1')
        self.assertTrue(any('低于官方下界' in p for p in problems), problems)


class PerLevelEnvelopeTests(unittest.TestCase):
    """`_0` 与 `_1` 不是同一个分布 —— 只按 `_0` 定包络两头都会误判。"""

    def test_dense_cutin_is_official_style_on_level_1(self):
        """`_1` 的 cut-in 有 0.88 这档官方先例(psychic_yamikawa 0.886 / shadow_redhood 0.882)。"""
        arr = partial('skill_cutin', 0.88)
        self.assertEqual(
            [p for p in gate.derived_icon_problems({'skill_cutin': arr}, level='1')
             if '不透明占比' in p], [])

    def test_same_dense_cutin_is_flagged_on_level_0(self):
        """同一张图放在 `_0` 就越界了:`_0` 465 张的 max 只有 0.784。"""
        arr = partial('skill_cutin', 0.88)
        problems = gate.derived_icon_problems({'skill_cutin': arr}, level='0')
        self.assertTrue(any('高于官方上界' in p for p in problems), problems)

    def test_fully_opaque_cutin_is_flagged_on_both_levels(self):
        """`flame_witch_1` 确实是 1.000,但那是 483 张里的 1 张;p99 包络照样要拦。"""
        for level in ('0', '1'):
            problems = gate.derived_icon_problems(
                {'skill_cutin': solid('skill_cutin')}, level=level)
            self.assertTrue(any('高于官方上界' in p for p in problems), f'level={level}')

    def test_sparse_thumb_party_main_is_allowed_only_on_level_1(self):
        """`thumb_party_main` 的下界反过来:`_0` p1=0.569,`_1` p1=0.451。"""
        arr = partial('thumb_party_main', 0.47)
        self.assertEqual(
            [p for p in gate.derived_icon_problems({'thumb_party_main': arr}, level='1')
             if '不透明占比' in p], [])
        problems = gate.derived_icon_problems({'thumb_party_main': arr}, level='0')
        self.assertTrue(any('低于官方下界' in p for p in problems), problems)

    def test_unknown_level_falls_back_to_combined(self):
        self.assertEqual(gate.coverage_envelope('skill_cutin', '9'),
                         gate.OFFICIAL_COVERAGE['skill_cutin'])
        self.assertEqual(gate.coverage_envelope('skill_cutin'),
                         gate.OFFICIAL_COVERAGE['skill_cutin'])


class SizeTests(unittest.TestCase):
    def test_wrong_size_is_flagged(self):
        arr = np.full((200, 200, 4), 255, np.uint8)
        problems = gate.derived_icon_problems({'square': arr})
        self.assertEqual(len(problems), 1)
        self.assertIn('尺寸 200x200', problems[0])

    def test_every_slot_has_a_declared_size(self):
        for slot in gate.OFFICIAL_COVERAGE:
            self.assertIn(slot, gate.OFFICIAL_ICON_SIZES, slot)


class ShapeMaskTests(unittest.TestCase):
    def test_masked_icon_passes(self):
        slot = 'cutin_skill_chain'
        mask = ellipse_mask(slot)
        arr = solid(slot)
        arr[:, :, 3] = np.minimum(arr[:, :, 3], mask)
        self.assertEqual(gate.mask_violation_ratio(arr, mask), 0.0)
        self.assertEqual(
            [p for p in gate.derived_icon_problems({slot: arr}, {slot: mask})
             if '蒙版' in p], [])

    def test_missing_mask_is_flagged(self):
        """派生时忘了套形状蒙版 = 六边形/水滴条在游戏里变成方砖。"""
        slot = 'cutin_skill_chain'
        mask = ellipse_mask(slot)
        arr = solid(slot)                      # 满框不透明
        self.assertGreater(gate.mask_violation_ratio(arr, mask), 0.5)
        problems = gate.derived_icon_problems({slot: arr}, {slot: mask})
        self.assertTrue(any('形状蒙版外' in p for p in problems), problems)

    def test_control_board_mask_is_checked(self):
        slot = 'battle_control_board'
        mask = ellipse_mask(slot)
        arr = solid(slot)
        problems = gate.derived_icon_problems({slot: arr}, {slot: mask})
        self.assertTrue(any('形状蒙版外' in p for p in problems), problems)

    def test_no_mask_supplied_skips_the_rule(self):
        slot = 'cutin_skill_chain'
        arr = solid(slot)
        self.assertEqual(
            [p for p in gate.derived_icon_problems({slot: arr}) if '蒙版' in p], [])

    def test_square_is_not_a_shape_slot(self):
        """square / square_132_132 官方满框无蒙版,不能拿别人的 alpha 去裁。"""
        self.assertNotIn('square', gate.SHAPE_SLOTS)
        self.assertNotIn('square_132_132', gate.SHAPE_SLOTS)

    def test_skill_cutin_is_not_a_shape_slot(self):
        """cut-in 的 alpha 是角色自己的剪影,不是框。"""
        self.assertNotIn('skill_cutin', gate.SHAPE_SLOTS)

    def test_mask_size_mismatch_raises(self):
        with self.assertRaises(ValueError):
            gate.mask_violation_ratio(solid('square'), np.zeros((10, 10), np.uint8))


class AspectGroupTests(unittest.TestCase):
    def test_same_composition_passes(self):
        icons = {s: gradient(s) for s in gate.ASPECT_GROUPS[0]}
        problems = [p for p in gate.derived_icon_problems(icons) if '构图不一致' in p]
        self.assertEqual(problems, [])

    def test_different_composition_is_flagged(self):
        """各槽各自从母版重采样 / 各自取景 = 同一角色的图标之间构图对不上。"""
        icons = {s: gradient(s) for s in gate.ASPECT_GROUPS[0]}
        shifted = gradient('square_round_95_95')
        shifted[:, :, 0] = np.roll(shifted[:, :, 0], 30, axis=1)
        icons['square_round_95_95'] = shifted
        problems = [p for p in gate.derived_icon_problems(icons) if '构图不一致' in p]
        self.assertTrue(problems, '构图明显不同却没有报出来')

    def test_thumb_group_is_checked(self):
        icons = {s: gradient(s) for s in gate.ASPECT_GROUPS[1]}
        bad = gradient('thumb_party_unison')
        bad[:, :, 1] = np.roll(bad[:, :, 1], 40, axis=0)
        icons['thumb_party_unison'] = bad
        problems = [p for p in gate.derived_icon_problems(icons) if '构图不一致' in p]
        self.assertTrue(problems, 'thumb 组没有被检查')

    def test_group_members_share_aspect_ratio(self):
        for group in gate.ASPECT_GROUPS:
            ratios = {round(gate.OFFICIAL_ICON_SIZES[s][0]
                            / gate.OFFICIAL_ICON_SIZES[s][1], 3) for s in group}
            self.assertEqual(len(ratios), 1, f'{group} 宽高比不一致: {ratios}')

    def test_divergence_is_symmetric(self):
        a = gradient('square')
        b = gradient('square_round_95_95')
        self.assertAlmostEqual(gate.group_divergence(a, b),
                               gate.group_divergence(b, a), places=6)


class UnknownSlotTests(unittest.TestCase):
    def test_unknown_slot_is_ignored(self):
        self.assertEqual(
            gate.derived_icon_problems({'not_a_slot': np.zeros((4, 4, 4), np.uint8)}), [])

    def test_non_rgba_raises(self):
        with self.assertRaises(ValueError):
            gate.coverage(np.zeros((8, 8, 3), np.uint8))


if __name__ == '__main__':
    unittest.main()
