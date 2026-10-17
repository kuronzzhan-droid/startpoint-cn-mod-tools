# -*- coding: utf-8 -*-
"""wf_portrait_white_matte：只删与画面边缘连通的纯白背景，其余一律保留。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wf_portrait_white_matte as M  # noqa: E402


def canvas(size=120):
    return np.full((size, size, 3), 255, dtype=np.int32)


def scene():
    """白底上：一个带黑描边的白色物体（本体白）、一个封闭白洞、一个 9px 小孤岛、一条浅色特效。"""
    rgb = canvas()
    rgb[20:80, 20:80] = (30, 30, 30)          # 黑描边的方块
    rgb[24:76, 24:76] = (255, 255, 255)       # 方块内部是白的（＝角色身上的白）
    rgb[40:60, 40:60] = (200, 60, 60)         # 白里面再画个红块
    rgb[95:98, 95:98] = (90, 160, 90)         # 小孤岛（花瓣/叶子）
    rgb[100:104, 10:70] = (190, 240, 225)     # 浅色特效条（离白 65）
    return rgb


class BackgroundOnly(unittest.TestCase):
    def test_border_connected_white_is_removed_and_nothing_else(self):
        rgb = scene()
        rgba, background, _pockets = M.matte(rgb, aa_radius=0)
        alpha = rgba[:, :, 3]
        self.assertTrue(background[0, 0] and alpha[0, 0] == 0)
        self.assertTrue((alpha[20:80, 20:80] == 255).all())          # 描边与围住的白色本体全保留
        self.assertTrue((alpha[95:98, 95:98] == 255).all())          # 小孤岛不清理
        self.assertTrue((alpha[100:104, 10:70] == 255).all())        # 浅色特效不删
        self.assertTrue((rgba[24:40, 24:40, :3] == 255).all())       # 本体白色的颜色不动

    def test_enclosed_white_is_kept_by_default_and_listed(self):
        rgb = scene()
        _rgba, background, pockets = M.matte(rgb)
        self.assertFalse(background[30, 30])
        self.assertEqual(len(pockets), 1)
        self.assertFalse(pockets[0]["removed"])

    def test_seed_removes_exactly_that_pocket(self):
        rgb = scene()
        rgba, background, pockets = M.matte(rgb, remove_seeds=[[30, 30]], aa_radius=0)
        self.assertTrue(background[30, 30])
        self.assertTrue(pockets[0]["removed"])
        self.assertTrue((rgba[40:60, 40:60, 3] == 255).all())        # 洞里的红块仍在
        self.assertTrue((rgba[20:24, 20:80, 3] == 255).all())        # 描边仍在

    def test_seed_on_non_white_pixel_is_an_error(self):
        with self.assertRaises(M.MatteError):
            M.matte(scene(), remove_seeds=[[50, 50]])

    def test_non_white_content_has_no_deletion_path(self):
        rng = np.random.default_rng(7)
        rgb = canvas(96)
        rgb[10:86, 10:86] = rng.integers(0, 200, size=(76, 76, 3))   # 任意非白内容
        rgba, _bg, _p = M.matte(rgb, aa_radius=2)
        report = M.audit(rgb, rgba[:, :, 3].astype(np.int32))
        self.assertEqual(report["eaten_px"], 0)
        self.assertEqual(report["leftover_bg_px"], 0)


class AntiAlias(unittest.TestCase):
    def test_blended_edge_is_unmixed_and_interior_untouched(self):
        rgb = canvas(60)
        rgb[20:40, 20:40] = (40, 80, 160)
        rgb[19, 20:40] = (148, 168, 208)                              # 上边一行 = 50% 前景 + 50% 白
        rgba, _bg, _p = M.matte(rgb, aa_radius=2)
        edge_alpha = rgba[19, 25:35, 3]
        self.assertTrue(((edge_alpha > 110) & (edge_alpha < 150)).all(), edge_alpha)
        self.assertTrue((rgba[19, 25:35, :3] == (40, 80, 160)).all())  # 半透明边缘取纯前景色，不带白
        self.assertTrue((rgba[26:34, 26:34, 3] == 255).all())
        self.assertTrue((rgba[26:34, 26:34, :3] == (40, 80, 160)).all())

    def test_near_white_foreground_edge_stays_opaque(self):
        rgb = canvas(60)
        rgb[20:40, 20:40] = (250, 250, 246)                           # 近白的本体（白毛）直接挨着背景
        rgb[19:41, 19] = rgb[19:41, 40] = rgb[19, 19:41] = rgb[40, 19:41] = (240, 240, 236)
        rgba, _bg, _p = M.matte(rgb, core_tol=4, aa_radius=2)
        self.assertTrue((rgba[22:38, 22:38, 3] == 255).all())


class PaperNoise(unittest.TestCase):
    """v2：白纸并不处处纯白。三条补充规则只作用于近白像素。"""

    @staticmethod
    def page():
        rgb = canvas(100)
        rgb[30:70, 30:70] = (40, 60, 140)                   # 本体
        rgb[29, 30:70] = rgb[70, 30:70] = (20, 20, 20)      # 上下墨线
        return rgb

    def test_near_white_halo_next_to_the_background_is_absorbed(self):
        rgb = self.page()
        rgb[26:28, 30:70] = (248, 248, 249)                  # 轮廓外 2px 的纸面灰（离白 7）
        rgba, _bg, _p = M.matte(rgb, aa_radius=0)
        self.assertTrue((rgba[26:28, 30:70, 3] == 0).all())
        self.assertTrue((rgba[29, 30:70, 3] == 255).all())   # 墨线一根不少

    def test_halo_absorption_is_depth_limited(self):
        rgb = self.page()
        rgb[5:25, 30:70] = (249, 249, 249)                   # 一大片近白（比如没描边的白物件）直接挨着背景
        rgba, _bg, _p = M.matte(rgb, aa_radius=0, speck_max_px=0)
        self.assertTrue((rgba[10:20, 35:65, 3] == 255).all())  # 只啃掉外沿 2px，里面保留

    def test_floating_near_white_speck_is_dropped_but_colour_and_attached_white_stay(self):
        rgb = self.page()
        rgb[10:13, 10:14] = (236, 236, 238)                  # 悬空的近白噪点（离白 19，halo 收不进）
        rgb[80:83, 80:84] = (250, 240, 200)                  # 暖色小花瓣（离白 55）——内容
        rgb[31:33, 31:69] = (250, 250, 250)                  # 贴着墨线画的白色高光
        rgba, _bg, _p = M.matte(rgb, aa_radius=0)
        self.assertTrue((rgba[10:13, 10:14, 3] == 0).all())
        self.assertTrue((rgba[80:83, 80:84, 3] == 255).all())
        self.assertTrue((rgba[31:33, 31:69, 3] == 255).all())
        report = M.audit(rgb, rgba[:, :, 3].astype(np.int32), aa_radius=0)
        self.assertEqual(report["eaten_px"], 0)
        self.assertEqual(report["floating_white_px"], 0)

    def test_big_near_white_island_is_not_a_speck(self):
        rgb = canvas(100)
        rgb[20:60, 20:60] = (236, 236, 238)                  # 1600px 的近白物件：不是碎屑
        rgba, _bg, _p = M.matte(rgb, aa_radius=0, halo_depth=0)
        self.assertTrue((rgba[25:55, 25:55, 3] == 255).all())

    def test_remove_region_uses_a_local_tolerance_and_refuses_content_level_tol(self):
        rgb = self.page()
        rgb[40:50, 40:50] = (240, 238, 246)                  # 本体里一块离白 17 的「缝隙背景」
        rgba, _bg, _p = M.matte(rgb, aa_radius=0, remove_regions=[{"polygon": [[38, 38], [52, 38], [52, 52], [38, 52]], "tol": 20}])
        self.assertTrue((rgba[41:49, 41:49, 3] == 0).all())
        self.assertTrue((rgba[32:38, 32:38, 3] == 255).all())  # 圈外、以及圈内的非近白像素都不动
        with self.assertRaises(M.MatteError):
            M.matte(rgb, remove_regions=[{"polygon": [[0, 0], [9, 0], [9, 9]], "tol": 60}])


class ProtectRegions(unittest.TestCase):
    """浅到几乎和白纸同色、描边又很淡的内容（蕾贝卡的白花瓣）：保护区内纸面噪点规则一律不生效。"""

    @staticmethod
    def petal():
        rgb = canvas(80)
        rgb[30:50, 30:50] = (240, 236, 238)                  # 淡描边（离白 19）
        rgb[32:48, 32:48] = (251, 250, 252)                  # 花瓣内部（离白 5）
        return rgb

    def test_pale_petal_is_hollowed_without_protection(self):
        rgba, _bg, _p = M.matte(self.petal(), aa_radius=0, halo_tol=20, halo_depth=4)
        self.assertLess(int((rgba[30:50, 30:50, 3] == 255).sum()), 400)   # 反例：不保护就被掏

    def test_protected_petal_survives_the_same_settings(self):
        region = [{"polygon": [[28, 28], [52, 28], [52, 52], [28, 52]]}]
        rgba, _bg, _p = M.matte(self.petal(), aa_radius=0, halo_tol=20, halo_depth=4, protect_regions=region)
        self.assertTrue((rgba[30:50, 30:50, 3] == 255).all())
        self.assertEqual(int(rgba[0, 0, 3]), 0)                           # 圈外的白底照删


class AuditCatchesTheOldFailure(unittest.TestCase):
    def test_deleted_effect_is_reported(self):
        rgb = scene()
        rgba, _bg, _p = M.matte(rgb, aa_radius=0)
        alpha = rgba[:, :, 3].astype(np.int32)
        alpha[100:104, 10:70] = 0                                     # 模拟第一轮把特效删了
        report = M.audit(rgb, alpha, aa_radius=0)
        self.assertGreater(report["eaten_px"], 100)


if __name__ == "__main__":
    unittest.main()
