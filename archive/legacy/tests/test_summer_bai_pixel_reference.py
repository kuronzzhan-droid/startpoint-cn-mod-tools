"""Read-only regression against the archived live sprite family and API reference."""

from wf.paths import root_path
from io import BytesIO
from pathlib import Path
import sys
import unittest

from PIL import Image

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_summer_bai_pixel_reference as revision
from wf_assets import png_decode
from wf_summer_bai_pixels import CODE, KINDS, decode_family


class SummerBaiReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(('${WF_ROOT}/out/夏日白-用户像素替换-20260918'.replace("${WF_ROOT}", str(root_path()))))
        if not (cls.root / 'before').is_dir():
            raise unittest.SkipTest('local author reference and preimage required')
        cls.load = staticmethod(lambda name: (cls.root / 'before' / name).read_bytes())
        cls.reference = (cls.root / 'API还原原稿.png').read_bytes()
        cls.outputs, cls.report = revision.build(cls.load, cls.reference)

    def test_only_two_existing_sprite_sheets_change(self):
        prefix = f'character/{CODE}/pixelart/'
        self.assertEqual(set(self.outputs), {prefix+'sprite_sheet.png',
                                           prefix+'special_sprite_sheet.png'})
        for logical, raw in self.outputs.items():
            before = Image.open(BytesIO(png_decode(self.load(logical))))
            after = Image.open(BytesIO(png_decode(raw)))
            self.assertEqual(before.size, after.size)

    def test_all_runtime_sequences_and_markers_preserved(self):
        for kind in KINDS:
            before = decode_family(self.load, CODE, kind)
            after = decode_family(lambda name: self.outputs.get(name, self.load(name)), CODE, kind)
            self.assertEqual(before['timeline'], after['timeline'])
            self.assertEqual(before['frame'], after['frame'])
            self.assertEqual(before['atlas'], after['atlas'])
            self.assertEqual(len(before['frames']), len(after['frames']))
            self.assertTrue(all(im.getbbox() for im in after['frames']))
        self.assertEqual(sum(f['ticks'] for f in self.report['families']), 793)
        self.assertEqual(sum(f['sequences'] for f in self.report['families']), 18)

    def test_idle_matches_author_reference_pixel_for_pixel(self):
        f = decode_family(lambda name: self.outputs.get(name, self.load(name)), CODE, 'pixelart')
        got = f['frames'][0]; got = got.crop(got.getbbox())
        wanted = Image.open(BytesIO(self.reference)).convert('RGBA')
        wanted = wanted.crop(wanted.getbbox())
        self.assertEqual(got.size, wanted.size)
        self.assertEqual(got.tobytes(), wanted.tobytes())

    def test_reject_unreviewed_native_dimensions(self):
        buf = BytesIO(); Image.new('RGBA', (16, 16), 'white').save(buf, format='PNG')
        with self.assertRaises(ValueError):
            revision.build(self.load, buf.getvalue())

    def test_palette_transfer_is_deterministic(self):
        outputs, report = revision.build(self.load, self.reference)
        self.assertEqual(outputs, self.outputs)
        self.assertEqual(report, self.report)


if __name__ == '__main__':
    unittest.main()
