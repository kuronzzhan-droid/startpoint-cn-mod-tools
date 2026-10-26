"""透明底局部修复回归：实体白纸、深色丝袜与外部像素边界。"""
import sys
from pathlib import Path
import unittest

import numpy as np

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_campus_art_matte as matte


class CampusMatteTests(unittest.TestCase):
    def test_effect_cleanup_keeps_dark_stocking_and_outside_pixels(self):
        rgb = np.full((30, 30, 3), [63, 60, 62], dtype=np.uint8)
        rgb[2:6, 2:6] = [75, 220, 208]
        alpha = np.full((30, 30), 255., dtype=float)
        result, actual, _ = matte.recover_effects(rgb, alpha, [[[0, 0], [15, 0], [15, 15], [0, 15]]])
        self.assertEqual(actual[10, 10], 255)
        np.testing.assert_array_equal(result[20:], rgb[20:])
        np.testing.assert_array_equal(actual[20:], alpha[20:])

    def test_local_paper_restoration_does_not_fill_neutral_checker(self):
        rgb = np.full((10, 10, 3), [210, 210, 210], dtype=np.uint8)
        rgb[2:5, 2:5] = [253, 245, 221]
        result = matte.repair_alpha(rgb, np.zeros((10, 10)), [dict(mode="restore_warm_paper",
            polygon=[[0, 0], [9, 0], [9, 9], [0, 9]])])
        self.assertEqual(result[3, 3], 255)
        self.assertEqual(result[8, 8], 0)

    def test_hair_gap_clear_keeps_colored_hair(self):
        rgb = np.full((10, 10, 3), [230, 230, 230], dtype=np.uint8)
        rgb[2:5, 2:5] = [102, 66, 152]
        result = matte.repair_alpha(rgb, np.full((10, 10), 255.), [dict(mode="clear_neutral",
            chroma=25, max_value=256, polygon=[[0, 0], [9, 0], [9, 9], [0, 9]])])
        self.assertEqual(result[3, 3], 255)
        self.assertEqual(result[8, 8], 0)


if __name__ == "__main__":
    unittest.main()
