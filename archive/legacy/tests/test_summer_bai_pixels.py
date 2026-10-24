"""真实绿衣安装稿逐 tick 回归，独立模拟原生 END suffix 与 marker 读取。"""

from wf.paths import root_path
from copy import deepcopy
from io import BytesIO
import os
from pathlib import Path
import sys
import unittest
import zlib

from PIL import Image

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_summer_bai_pixels as px
from wf_assets import png_decode
from wf_dsl import parse_dsl
from wf_enhancement_policy import OfficialBaseline
from wf_mod_tool import sha1_path
from wf_pixelart_vfx import restore_frame


def decode(raw):
    return parse_dsl(zlib.decompress(raw, -15))['tree']


def native_frames(outputs, kind):
    base = f'character/{px.CODE}/pixelart/'
    stem = 'sprite_sheet' if kind == 'pixelart' else 'special_sprite_sheet'
    frame = decode(outputs['common', base + kind + '.frame.amf3.deflate'])
    atlas = decode(outputs['common', base + stem + '.atlas.amf3.deflate'])
    sheet = Image.open(BytesIO(png_decode(outputs['common', base + stem + '.png'])))
    # FrameAnimationSource.as: numeric suffix fills every slot up to END,
    # not bisect/right or previous-keyframe semantics.
    ticks = []
    for entry in atlas:
        end = int(entry['n'][len(frame['name']):])
        if end <= len(ticks):
            raise ValueError('nonincreasing END suffix')
        pose = restore_frame(sheet, entry)
        while len(ticks) < end:
            ticks.append(pose)
    return ticks


def state(timeline, section, path, tick):
    result = []
    for group in timeline.get(section, []):
        if group['path'] == path:
            for key in group['frames']:
                if key['begin'] <= tick:
                    result = key['data']
    return result


class SummerBaiPixelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo = Path(os.environ.get('WF_SUMMER_BAI_REPO', ('${WF_ROOT}/startpoint-cn'.replace("${WF_ROOT}", str(root_path())))))
        package = repo / 'work/character_packs/summer-bai-native-20260912/package/roots/common'
        cdn = repo / '.cdn/cn'
        if not package.is_dir() or not (cdn / 'archive-common-full').is_dir():
            raise unittest.SkipTest('installed green package and official archive required')
        cls.before_raw = {}
        def existing(logical):
            raw = (package / logical).read_bytes()
            cls.before_raw[logical] = raw
            return raw
        baseline = OfficialBaseline(cdn, write_cache=False)
        def official(logical):
            key = sha1_path(logical)
            raw = baseline.get('common', key[:2] + '/' + key[2:])
            if raw is None:
                raise FileNotFoundError(logical)
            return raw
        cls.before = {k: px.decode_family(existing, px.CODE, k) for k in px.KINDS}
        cls.donor = {k: px.decode_family(official, px.DONOR, k, recolor=True) for k in px.KINDS}
        cls.uncoloured = {k: px.decode_family(official, px.DONOR, k) for k in px.KINDS}
        cls.outputs = px.assets(existing, official)
        cls.after = {k: px.decode_family(lambda p: cls.outputs['common', p], px.CODE, k)
                     for k in px.KINDS}

    def test_actual_bad_cadence_reproduced_then_restored(self):
        before = {s['name']: s['end'] - s['begin'] + 1
                  for family in self.before.values() for s in family['timeline']['sequences']}
        after = {s['name']: s['end'] - s['begin'] + 1
                 for family in self.after.values() for s in family['timeline']['sequences']}
        self.assertEqual([before[n] for n in ('skill_ready', 'special_land', 'special_pose')], [236, 187, 49])
        self.assertEqual([after[n] for n in ('skill_ready', 'special_land', 'special_pose')], [62, 189, 31])
        self.assertEqual(after['kachidoki'], 48)
        self.assertEqual(sum(len(f['frames']) for f in self.after.values()), 793)
        self.assertFalse(any(not im.getbbox() for f in self.before.values() for im in f['frames']))

    def test_every_tick_retains_native_pose_and_all_seven_compatibility_sequences(self):
        for kind in px.KINDS:
            actual = native_frames(self.outputs, kind)
            sources = {s['name']: (self.donor[kind], s)
                       for s in self.donor[kind]['timeline']['sequences']}
            old = {s['name']: s for s in self.before[kind]['timeline']['sequences']}
            fallback_seen = []
            for seq in self.after[kind]['timeline']['sequences']:
                source, ref = sources.get(seq['name'], (self.before[kind], old[seq['name']]))
                if source is self.before[kind]:
                    fallback_seen.append(seq['name'])
                expected = source['frames'][ref['begin'] - 1:ref['end']]
                got = actual[seq['begin'] - 1:seq['end']]
                self.assertEqual(len(got), len(expected))
                self.assertEqual(seq['kind'], ref['kind'])
                for offset, (a, b) in enumerate(zip(got, expected)):
                    self.assertEqual(a.tobytes(), b.tobytes(), (kind, seq['name'], offset))
            self.assertEqual(fallback_seen, list(px.FALLBACK) if kind == 'pixelart' else [])

    def test_markers_read_by_runtime_remain_identical_at_every_sequence_tick(self):
        for kind in px.KINDS:
            old, donor, after = (data[kind]['timeline'] for data in (self.before, self.donor, self.after))
            donor_by = {s['name']: s for s in donor['sequences']}
            old_by = {s['name']: s for s in old['sequences']}
            for seq in after['sequences']:
                source = donor if seq['name'] in donor_by else old
                ref = donor_by.get(seq['name'], old_by[seq['name']])
                for section in ('circles', 'points', 'sounds'):
                    paths = {g['path'] for tl in (source, after) for g in tl[section]}
                    for offset in range(seq['end'] - seq['begin'] + 1):
                        for path in paths:
                            self.assertEqual(state(after, section, path, seq['begin'] + offset),
                                             state(source, section, path, ref['begin'] + offset),
                                             (kind, seq['name'], section, path, offset))

    def test_palette_and_alpha_are_author_selected_not_new_character_art(self):
        for kind in px.KINDS:
            a, b = self.uncoloured[kind]['frames'], self.donor[kind]['frames']
            for src, dst in zip(a, b):
                self.assertEqual(src.getchannel('A').tobytes(), dst.getchannel('A').tobytes())
            # Migration validates every old sampled donor pose against the
            # real installed green package; this additionally locks key hues.
        self.assertEqual(px.PALETTE[(16, 24, 91)], (34, 59, 37))
        self.assertEqual(px.PALETTE[(84, 114, 190)], (215, 222, 176))

    def test_scope_eight_private_files_and_frame_anchor_bytes_unchanged(self):
        self.assertEqual(len(self.outputs), 8)
        for (tier, logical), raw in self.outputs.items():
            self.assertEqual(tier, 'common')
            self.assertTrue(logical.startswith('character/white_tiger_summer/pixelart/'))
            if '.frame.' in logical:
                self.assertEqual(raw, self.before_raw[logical])
        self.assertFalse(px.metadata()['requires_new_apk'])

    def test_rejects_unknown_repaint_missing_compatibility_and_playback_drift(self):
        for problem in ('repaint', 'missing', 'kind'):
            current = deepcopy(self.before['pixelart'])
            if problem == 'repaint':
                current['frames'][0].putpixel((128, 120), (255, 0, 255, 255))
            elif problem == 'missing':
                current['timeline']['sequences'].pop()
            else:
                current['timeline']['sequences'][0]['kind'] = 'once'
            with self.assertRaises(ValueError, msg=problem):
                px.retime_family(current, self.donor['pixelart'], 'pixelart')

    def test_last_suffix_gate_detects_real_missing_tail(self):
        from wf_character_revision import encode_tree
        data = dict(self.outputs)
        key = ('common', 'character/white_tiger_summer/pixelart/sprite_sheet.atlas.amf3.deflate')
        atlas = decode(data[key]); atlas.pop(); data[key] = encode_tree(atlas)
        with self.assertRaisesRegex(ValueError, 'final END suffix'):
            px.decode_family(lambda p: data['common', p], px.CODE, 'pixelart')


if __name__ == '__main__':
    unittest.main()
