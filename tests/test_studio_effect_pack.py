import unittest
from PIL import Image
from wf_studio_effect_pack import pack_cells


class StudioEffectPackTests(unittest.TestCase):
    def test_trim_and_dedupe_reconstructs_every_frame_at_its_original_origin(self):
        a = Image.new("RGBA", (768, 640))
        a.paste((12, 240, 200, 128), (303, 120, 384, 216))
        frames = [(a, -384, -320), (a, -390, -310), (Image.new("RGBA", (768, 640)), 10, 20)]
        sheet, packed = pack_cells(frames)
        self.assertEqual(packed[0][0], packed[1][0])
        self.assertLess(sheet.width * sheet.height, 768 * 640)
        for (original, ox, oy), ((x, y, w, h), px, py) in zip(frames, packed):
            rebuilt = Image.new("RGBA", original.size)
            rebuilt.paste(sheet.crop((x, y, x + w, y + h)), (px - ox, py - oy))
            self.assertEqual(rebuilt.tobytes(), original.tobytes())

    def test_oversized_opaque_art_is_rejected_without_downsampling(self):
        with self.assertRaisesRegex(ValueError, "4096"):
            pack_cells([(Image.new("RGBA", (4100, 1), "red"), 0, 0)])


if __name__ == "__main__":
    unittest.main()
