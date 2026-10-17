"""选中原稿回装时，不能再次误删手、纸袋和场景。"""
import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

pass  # Imports resolve from this checkout/package, not external source copies.
from wf_zantetsu_art_restore import SOURCE, restore_master


@unittest.skipUnless(SOURCE.exists(), "需要已选 C049 原稿")
class ZantetsuRestoreTests(unittest.TestCase):
    def test_restore_preserves_art_and_only_removes_white(self):
        image, report = restore_master()
        with Image.open(SOURCE) as original:
            before = np.asarray(original.convert("RGBA"))
        after = np.asarray(image)
        np.testing.assert_array_equal(before[:, :, :3], after[:, :, :3])
        removed = after[:, :, 3] < before[:, :, 3]
        self.assertGreater(removed.sum(), 10000)
        self.assertTrue((before[:, :, :3][removed].min(axis=1) >= 244).all())
        # Entire dark hand, paper bag, shop and flowerpot regions must survive.
        for box in ((804, 660, 840, 715), (800, 820, 855, 940),
                    (1000, 600, 1120, 1050), (15, 880, 180, 990)):
            x0, y0, x1, y1 = box
            self.assertTrue((after[y0:y1, x0:x1, 3] == 255).all())
        self.assertTrue(report["original_hand_bag_and_scene_retained"])


if __name__ == "__main__":
    unittest.main()
