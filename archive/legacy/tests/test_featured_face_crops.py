"""Tight UI crop boundaries and native shape preservation."""
from pathlib import Path
import sys
import unittest

import numpy as np
from PIL import Image

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_featured_face_crops as face
import wf_ui_derive_gate as gate


class FeaturedFaceCropsTests(unittest.TestCase):
    def setUp(self):
        self.source = Image.new('RGBA', (600, 800), (230, 175, 110, 255))
        self.masks = {}
        for slot in gate.SHAPE_SLOTS:
            width, height = gate.OFFICIAL_ICON_SIZES[slot]
            yy, xx = np.mgrid[:height, :width]
            self.masks[slot] = ((xx * 3 + yy * 7) % 256).astype(np.uint8)

    def test_native_sizes_and_each_exact_alpha_mask_are_preserved(self):
        original = self.source.tobytes()
        result = face.make_images('wind_spgirl_campus', self.source, (170, 60, 390, 280), self.masks)
        self.assertEqual(set(result), set(gate.OFFICIAL_ICON_SIZES))
        for slot, image in result.items():
            self.assertEqual(image.size, gate.OFFICIAL_ICON_SIZES[slot])
            if slot in self.masks:
                np.testing.assert_array_equal(np.array(image)[:, :, 3], self.masks[slot])
        self.assertEqual(self.source.tobytes(), original)

    def test_filled_source_cutin_retains_transparent_padding_and_visible_face_center(self):
        result = face.make_images('ruin_girl_campus', self.source, (170, 60, 390, 280), self.masks)
        rgba = np.array(result['skill_cutin'])
        self.assertLess(float((rgba[:, :, 3] > 8).mean()), .741)
        self.assertEqual(rgba[256, 512].tolist(), [230, 175, 110, 255])
        self.assertTrue(np.all(rgba[:, :160, 3] == 0))
        self.assertTrue(np.all(rgba[:, 960:, 3] == 0))

    def test_transparent_art_keeps_holes_and_soft_edges_inside_native_frame(self):
        source = Image.new('RGBA', (600, 800))
        source.paste((230, 175, 110, 255), (190, 80, 380, 260))
        source.paste((230, 175, 110, 100), (220, 130, 260, 180))
        source.paste((0, 0, 0, 0), (290, 130, 335, 180))
        result = face.make_images('wind_spgirl_campus', source,
                                  (170, 60, 390, 280), self.masks,
                                  transparent_background=True)
        filled = face.make_images('wind_spgirl_campus', source,
                                  (170, 60, 390, 280), self.masks)
        for slot, image in result.items():
            alpha = np.asarray(image.getchannel('A'))
            if slot in self.masks:
                self.assertTrue(np.all(alpha <= self.masks[slot]))
            if slot != 'skill_cutin':
                self.assertGreater(float((alpha == 0).mean()), .05)
                self.assertLess(alpha.sum(), np.asarray(filled[slot].getchannel('A')).sum())
        # Cut-in is already transparent and must stay byte-identical.
        self.assertEqual(result['skill_cutin'].tobytes(), filled['skill_cutin'].tobytes())

    def test_wrong_character_or_outside_non_square_crop_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unassigned'):
            face.make_images('foreign_character', self.source, (170, 60, 390, 280), self.masks)
        for crop in ((-1, 0, 100, 101), (0, 0, 601, 601), (0, 0, 100, 90)):
            with self.assertRaises(ValueError):
                face.make_images('scutum_valentine', self.source, crop, self.masks)
        with self.assertRaisesRegex(ValueError, 'both evolution states'):
            face.assets('white_tiger_summer', {0: b''}, {0: (0, 0, 10, 10)}, lambda *_: b'', native_masks=self.masks)

    def test_skill_banner_includes_chest_below_face_crop(self):
        source = Image.new('RGBA', (600, 800))
        source.paste((220, 170, 100, 255), (200, 90, 360, 230))
        source.paste((30, 90, 210, 255), (180, 250, 390, 490))
        result = face.make_images('wind_spgirl_campus', source,
                                  (170, 60, 390, 280), self.masks,
                                  transparent_background=True)
        rgba = np.asarray(result['skill_cutin'])
        chest = (rgba[:, :, 2] > 180) & (rgba[:, :, 0] < 70) & (rgba[:, :, 3] > 200)
        self.assertGreater(int(chest.sum()), 20000)
        self.assertGreater(int(np.nonzero(chest)[0].max()), 450)


if __name__ == '__main__':
    unittest.main()
