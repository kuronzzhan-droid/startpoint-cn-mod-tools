import sys
import unittest
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_wiki_ui_assets import crop_sprite, atlas_entries


class UiAssetTests(unittest.TestCase):
    def test_rotated_trimmed_sprite_restores_frame(self):
        sheet = Image.new('RGBA', (8, 8), (255, 0, 0, 255))
        result = crop_sprite(sheet, dict(x=1,y=2,w=2,h=3,r=True,fw=6,fh=5,fx=-1,fy=-2))
        self.assertEqual(result.size, (6, 5))
        self.assertEqual(result.getpixel((0, 0))[3], 0)
        self.assertEqual(result.getpixel((1, 2)), (255, 0, 0, 255))
        self.assertEqual(result.getpixel((3, 3)), (255, 0, 0, 255))

    def test_atlas_bounds_reject_invalid_rectangle(self):
        with self.assertRaises(ValueError):
            crop_sprite(Image.new('RGBA',(2,2)), dict(x=1,y=0,w=2,h=1))

    def test_nested_atlas_finds_only_sprite_entries(self):
        item=dict(n='a',x=0,y=0,w=1,h=1)
        self.assertEqual(list(atlas_entries({'root':[item,{'not':'sprite'}]})),[item])


if __name__ == '__main__':
    unittest.main()
