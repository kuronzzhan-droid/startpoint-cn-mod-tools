"""真实官方图集染色及透明度、骨架、混合方式、时序保护。"""

from wf.paths import root_path
import colorsys
from copy import deepcopy
from io import BytesIO
import os
from pathlib import Path
import sys
import unittest
import zlib

from PIL import Image

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
from wf_assets import png_decode
from wf_enhancement_policy import OfficialBaseline
from wf_mod_tool import sha1_path
import wf_scutum_effects as fx


class ScutumEffectsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cdn = Path(os.environ.get('WF_SCUTUM_OFFICIAL_CDN', ('${WF_ROOT}/startpoint-cn/.cdn/cn'.replace("${WF_ROOT}", str(root_path())))))
        if not (cdn / 'archive-common-full').is_dir():
            raise unittest.SkipTest('official CN archive required')
        cls.baseline = OfficialBaseline(cdn, write_cache=False)
        cls.source = {}
        for suffix in fx.SUFFIXES:
            h = sha1_path(fx.SOURCE + suffix)
            cls.source[fx.SOURCE + suffix] = cls.baseline.get('common', h[:2]+'/'+h[2:])
        cls.outputs = fx.assets(cls.source.__getitem__)

    def tree(self, raw):
        return wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']

    def test_texture_really_recoloured_without_alpha_or_brightness_changes(self):
        before = Image.open(BytesIO(png_decode(self.source[fx.SOURCE+'.png'])))
        after = Image.open(BytesIO(png_decode(self.outputs['common',fx.TARGET+'.png'])))
        self.assertEqual(after.size, before.size)
        self.assertEqual(after.mode, before.mode)
        self.assertEqual(after.getchannel('A').tobytes(), before.getchannel('A').tobytes())
        changed = 0
        for original, tinted in zip(before.getdata(), after.getdata()):
            if original[3] == 0:
                self.assertEqual(tinted, original)
                continue
            self.assertEqual(max(tinted[:3]), max(original[:3]))
            self.assertEqual(min(tinted[:3]), min(original[:3]))
            if max(original[:3]) == min(original[:3]):
                self.assertEqual(tinted, original)
            else:
                changed += tinted != original
                hue = colorsys.rgb_to_hsv(*tinted[:3])[0] * 360
                self.assertGreaterEqual(hue, 109)
                self.assertLessEqual(hue, 171)
        self.assertGreater(changed, 1000)
        self.assertNotEqual(self.outputs['common',fx.TARGET+'.png'], self.source[fx.SOURCE+'.png'])

    def test_timeline_identical_atlas_only_names_change(self):
        suffix = '.timeline.amf3.deflate'
        self.assertEqual(self.outputs['common',fx.TARGET+suffix], self.source[fx.SOURCE+suffix])
        suffix = '.atlas.amf3.deflate'
        self.assertEqual(self.tree(self.outputs['common',fx.TARGET+suffix]),
                         fx.remap(self.tree(self.source[fx.SOURCE+suffix])))

    def test_no_ignored_tint_fields_geometry_alpha_blend_and_frames_unchanged(self):
        suffix = '.parts.amf3.deflate'
        before = self.tree(self.source[fx.SOURCE+suffix])
        after = self.tree(self.outputs['common',fx.TARGET+suffix])
        self.assertEqual(after, fx.remap(before))
        self.assertEqual(len(after['g']),111)
        self.assertEqual(len(after['i']),28)
        self.assertEqual(len(after['t']),218)
        self.assertFalse(any('c' in key for g in after['g'] for s in g['s'] for key in s['l']))
        self.assertEqual(sum(len(s['l']) for g in after['g'] for s in g['s']),1438)

    def test_reject_source_colour_and_root_drift(self):
        before = self.tree(self.source[fx.SOURCE+'.parts.amf3.deflate'])
        copy = deepcopy(before); copy['g'][0]['t'] = 65
        with self.assertRaises(ValueError):fx.remap_parts(copy)
        copy = deepcopy(before);copy['g'][-1]['s'][0]['l'][0]['c']=0x64000000
        with self.assertRaises(ValueError):fx.remap_parts(copy)
        self.assertEqual(before,self.tree(self.source[fx.SOURCE+'.parts.amf3.deflate']))

    def test_build_emits_exact_four_private_assets_only(self):
        class Seed:
            def __init__(self, inputs):self.inputs,self.outputs=inputs,{}
            def official(self, logical):return self.inputs[logical]
            def emit(self,tier,logical,raw):self.outputs[tier,logical]=raw
        seed = Seed(self.source)
        meta = fx.build(seed)
        self.assertEqual(seed.outputs,self.outputs)
        self.assertEqual(len(meta['assets']),4)
        self.assertFalse(meta['requires_new_apk'])


if __name__ == '__main__':unittest.main()
