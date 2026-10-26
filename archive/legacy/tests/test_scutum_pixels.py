import bisect
import io
from pathlib import Path
import sys
import tempfile
import unittest
import zlib

from PIL import Image

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_assets
import wf_dsl
from wf_character_revision import encode_tree
from wf_client_legality import _pixelart_marker_problems
import wf_scutum_pixels as pixels
from wf_scutum_pixel_timeline import frame_index, loop_frames, retime


def source(path):
    frames = []
    for index in (0, 1, 0, 2):
        frame = Image.new('RGBA', (26, 30))
        for y in range(2 if index else 0, 30 if index else 28):
            for x in range(5, 21):
                frame.putpixel((x, y), (40 + index * 50, 190, 90, 255))
        frames.append(frame.resize((260, 300), Image.Resampling.NEAREST))
    frames[0].save(path, format='GIF', save_all=True, append_images=frames[1:],
                   duration=[180] * 4, disposal=2, loop=0, optimize=False)


def timeline():
    return dict(sequences=[dict(name='neutral', kind='loop', begin=1, end=2),
        dict(name='walk_front', kind='loop', begin=3, end=26),
        dict(name='skill_ready', kind='once', begin=27, end=86),
        dict(name='kachidoki', kind='loop', begin=87, end=134)],
        circles=[dict(path='unit_body', frames=[dict(begin=2, data=[dict(x=0, y=0, r=8.3)]),
            dict(begin=4, data=[dict(x=0, y=0, r=8.3)]), dict(begin=28, data=[]), dict(begin=88, data=[])])],
        points=[dict(path='hp_gauge', frames=[dict(begin=1, data=[dict(x=0, y=-10)])])], sounds=[])


def decode(raw):
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']


class Seed:
    def __init__(self):
        self.outputs = {}
        for name in ('pixelart', 'special'):
            root = f'character/scutum_valentine/pixelart/{name}'
            self.outputs['common', root + '.frame.amf3.deflate'] = encode_tree(
                dict(name=root, x=-128, y=-128, scale=3, smoothing=False))
            self.outputs['common', root + '.timeline.amf3.deflate'] = encode_tree(timeline())

    def emit(self, tier, logical, raw):
        self.outputs[tier, logical] = raw

    def official(self, logical):
        return encode_tree(timeline())


class ScutumPixelsTests(unittest.TestCase):
    def test_magic_not_extension_and_all_four_frames(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'misleading.jpeg'
            source(path)
            _, frames, durations = pixels.read_frames(path)
            self.assertEqual(durations, [180] * 4)
            self.assertEqual(len(frames), 4)
            self.assertEqual(len({f.tobytes() for f in frames}), 3)
            self.assertEqual(max(f.getbbox()[3] for f in frames), 30)

    def test_static_preview_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'preview.png'
            Image.new('RGBA', (260, 300), 'red').save(path)
            with self.assertRaisesRegex(ValueError, 'animated'):
                pixels.read_frames(path)

    def test_supercycle_preserves_720ms_without_loop_drift(self):
        self.assertEqual(loop_frames([180] * 4), 216)
        self.assertEqual(216 / 60, 720 * 5 / 1000)
        self.assertEqual([frame_index(t, [180] * 4) for t in (0, 10, 11, 21, 22, 32, 33, 43, 44)],
                         [0, 0, 1, 1, 2, 2, 3, 3, 0])

    def test_markers_and_external_once_durations_are_preserved(self):
        original = timeline()
        new = retime(original, 216)
        self.assertEqual(original, timeline())
        seq = {s['name']: s for s in new['sequences']}
        self.assertEqual(seq['kachidoki']['end'] - seq['kachidoki']['begin'] + 1, 48)
        self.assertEqual(seq['skill_ready']['end'] - seq['skill_ready']['begin'] + 1, 60)
        markers = new['circles'][0]['frames']
        def held(frame):
            return [m for m in markers if m['begin'] <= frame][-1]['data']
        self.assertEqual(held(seq['walk_front']['end']), [dict(x=0, y=0, r=8.3)])
        self.assertEqual(held(seq['skill_ready']['begin'] + 1), [])
        self.assertEqual(held(seq['kachidoki']['end']), [])
        self.assertTrue(all(m['data'] == [dict(x=0, y=-10)] for m in new['points'][0]['frames']))
        self.assertEqual(_pixelart_marker_problems(new, new['sequences']), [])
        self.assertEqual(len(markers), len(new['sequences']))
        self.assertEqual(len(new['points'][0]['frames']), 1)

    def test_every_native_frame_has_correct_pose_and_fixed_foot_anchor(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source.jpeg'
            source(path)
            seed = Seed()
            metadata = pixels.build(seed, path, Path(folder) / 'output')
            self.assertEqual(metadata['atlas_fy'], -99)
            self.assertEqual(metadata['lowest_foot_y'], 1)
            _, expected, durations = pixels.read_frames(path)
            for stem, name in (('sprite_sheet', 'pixelart'), ('special_sprite_sheet', 'special')):
                prefix = 'character/scutum_valentine/pixelart/'
                atlas = decode(seed.outputs['common', prefix + stem + '.atlas.amf3.deflate'])
                ends = [int(item['n'][-4:]) for item in atlas]
                sheet = Image.open(io.BytesIO(wf_assets.png_decode(seed.outputs['common', prefix + stem + '.png']))).convert('RGBA')
                animation = decode(seed.outputs['common', prefix + name + '.timeline.amf3.deflate'])
                for sequence in animation['sequences']:
                    for frame in range(sequence['begin'], sequence['end'] + 1):
                        rect = atlas[bisect.bisect_left(ends, frame)]
                        tile = sheet.crop((rect['x'], rect['y'], rect['x'] + rect['w'], rect['y'] + rect['h']))
                        self.assertEqual(tile.tobytes(), expected[frame_index(frame - sequence['begin'], durations)].tobytes())
                        self.assertLessEqual(-128 - rect['fy'] + tile.getbbox()[3], 1)
                self.assertEqual(ends[-1], animation['sequences'][-1]['end'])


if __name__ == '__main__':
    unittest.main()
