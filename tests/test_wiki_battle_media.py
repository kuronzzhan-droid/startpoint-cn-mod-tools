"""Pinned native-to-public media proof; no game store or network writes."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_wiki_pixel_render import fixture, packed
from wf_wiki_pixel_render import render_actions, tree
from wf_wiki_battle_media import resolve_native_media
import wf_wiki_battle_media as media_module


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class BattleMediaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo, self.site, self.output = [self.root / x for x in ('repo', 'site', 'output')]
        self.repo.mkdir(); (self.site / 'data').mkdir(parents=True)
        self.cid = 'c' + '1' * 12
        self.raw = fixture()
        tl = tree(self.raw['pixelart.timeline.amf3.deflate'])
        next(s for s in tl['sequences'] if s['name'] == 'skill_ready')['begin'] = 3
        self.raw['pixelart.timeline.amf3.deflate'] = packed(tl)
        self.actions = render_actions(self.raw, self.save)
        self.avatar = self.actions[0]['poster']['url']
        self.voice = self.save(bytes.fromhex('fffb7400') + bytes(284), '.mp3')
        self.switched_voice = self.save(bytes.fromhex('fffb7400') + bytes(283) + b'\x01', '.mp3')
        self.chunk = {'id': self.cid, 'voices': [
            {'category': 'battle', 'label': '战斗开始 1', 'audio': self.voice},
            {'category': 'battle', 'label': '技能准备', 'audio': self.voice},
            {'category': 'battle', 'label': '技能准备 3', 'audio': self.voice},
            {'category': 'battle', 'label': '切换后技能准备', 'audio': self.switched_voice},
            {'category': 'battle', 'label': '技能发动 1', 'audio': self.voice}]}
        self.evidence = {'schema': 1, 'site': {'path': str(self.site)},
                         'characters': {self.cid: {'sources': self.sources(self.raw)}},
                         'coffin': self.coffin()}
        self.write_site()

    def save(self, raw, suffix='.webp'):
        url = 'media/' + sha(raw) + suffix
        path = self.site / url; path.parent.mkdir(exist_ok=True)
        path.write_bytes(raw)
        return url

    def pin(self, relative, raw):
        path = self.repo / relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return {'path': str(path), 'sha256': sha(raw)}

    def sources(self, raw):
        return {key: self.pin('native/' + key, value) for key, value in raw.items()}

    def coffin(self):
        sheet = Image.new('RGBA', (12, 15), (80, 40, 20, 255)); stream = io.BytesIO()
        sheet.save(stream, 'PNG')
        entry = dict(n='battle/common/layer0/.gen/coffin/f0089', x=0, y=0, w=12, h=15,
                     fw=64, fh=64, fx=-26, fy=-23)
        return {'sources': {'sheet': self.pin('coffin/layer0.png', stream.getvalue()),
                            'atlas': self.pin('coffin/layer0.atlas.amf3.deflate', packed([entry])),
                            'frame': self.pin('coffin/coffin.frame.amf3.deflate', packed({'x': -32, 'y': -37}))}}

    def write_site(self):
        raw = ('window.WF_WIKI_CHUNKS = window.WF_WIKI_CHUNKS || {};\n'
               f'window.WF_WIKI_CHUNKS["character:{self.cid}"] = ' + json.dumps(self.chunk) + ';\n').encode()
        (self.site / 'data/character.js').write_bytes(raw)
        catalog = {'characters': [{'id': self.cid, 'name': '夹具', 'origin': '新增MOD',
                                   'media': {'square0': self.avatar}}],
                   'dataManifest': {'chunks': {'character:' + self.cid: {'url': 'data/character.js', 'sha256': sha(raw)}}}}
        pixels = {'format': 1, 'characters': {self.cid: {'actions': self.actions}}}
        for field, name, prefix, value in [('catalogSha256', 'data.js', 'window.WF_WIKI = ', catalog),
                                           ('pixelsSha256', 'data/pixel-previews.js', 'window.WF_PIXEL_PREVIEWS=', pixels)]:
            data = (prefix + json.dumps(value) + ';\n').encode()
            (self.site / name).write_bytes(data); self.evidence['site'][field] = sha(data)

    def resolve(self):
        return resolve_native_media(self.repo, self.evidence, self.output)

    def add_native_se(self, cue='cast'):
        logical = 'sound_effect/monster/se_fixture'
        timeline = 'battle/boss/fixture/fixture.timeline.amf3.deflate'
        audio = (self.site / self.switched_voice).read_bytes()
        native = packed({'sounds': [{'path': logical, 'begin': 12, 'loop': 1}],
                         'sequences': [{'name': 'skill_fire', 'begin': 10, 'end': 18}]})
        specs = {timeline: self.pin('se/timeline', native), logical + '.mp3': self.pin('se/audio', audio)}
        self.evidence['characters'][self.cid]['nativeSe'] = specs
        directory = self.repo / 'mod-tools/wiki-battle'; directory.mkdir(parents=True, exist_ok=True)
        rule = {'cue': cue, 'timeline': timeline, 'sound': logical, 'sequence': 'skill_fire',
                'begin': 12, 'decodedSha256': sha(audio)}
        override = {'schema': 1, 'characters': {self.cid: {'nativeSe': [rule]}}}
        (directory / 'media-overrides.json').write_text(json.dumps(override), encoding='utf8')
        return specs, rule, override

    def test_verified_native_skill_se_is_separate_from_character_voice(self):
        self.chunk['voices'] = []; self.write_site(); self.add_native_se()
        media = self.resolve()['media'][self.cid]
        self.assertEqual(media['voices']['cast'], [])
        self.assertEqual(len(media['seCues']['cast']), 1)
        self.assertEqual(media['seCues']['deploy'], [])
        self.assertTrue(any('原生音效' in text for text in media['missingCues']))
        self.assertEqual((self.output / media['seCues']['cast'][0]).read_bytes(),
                         (self.site / self.switched_voice).read_bytes())

    def test_native_se_rejects_unmatched_event_and_looping_sound(self):
        specs, rule, override = self.add_native_se()
        timeline = next(k for k in specs if k.endswith('deflate'))
        for sound in [{'path': rule['sound'], 'begin': 12, 'loop': -1},
                      {'path': rule['sound'], 'begin': 13, 'loop': 1}]:
            data = {'sounds': [sound], 'sequences': [{'name': 'skill_fire', 'begin': 10, 'end': 18}]}
            specs[timeline] = self.pin('se/timeline', packed(data))
            with self.assertRaisesRegex(ValueError, '音效|事件'):
                self.resolve()
        self.assertFalse(self.output.exists())

    def test_native_se_wrong_decoded_hash_rejected(self):
        specs, rule, override = self.add_native_se()
        rule['decodedSha256'] = 'f' * 64
        (self.repo / 'mod-tools/wiki-battle/media-overrides.json').write_text(json.dumps(override))
        with self.assertRaisesRegex(ValueError, '音效|哈希'):
            self.resolve()

    def test_native_frames_match_and_different_crop_offsets_share_origin(self):
        result = self.resolve(); media = result['media'][self.cid]
        self.assertEqual((media['actions']['idle']['anchorX'], media['actions']['idle']['anchorY']), (4, 3))
        self.assertEqual((media['actions']['skill_ready']['anchorX'], media['actions']['skill_ready']['anchorY']), (2, 3))
        self.assertFalse(media['actions']['skill_ready']['animated'])
        self.assertEqual(media['actions']['idle']['duration'], .083)
        self.assertEqual(len(media['voices']['ready']), 1)  # Same recording deduplicated; switched cue excluded.
        self.assertNotIn(self.switched_voice, media['voices']['ready'])
        self.assertEqual(result['coffin']['width'], 64)
        self.assertEqual(result['coffin']['height'], 64)
        self.assertEqual((result['coffin']['anchorX'], result['coffin']['anchorY']), (32, 37))
        with Image.open(self.output / result['coffin']['url']) as im:
            self.assertEqual(im.size, (64, 64)); self.assertIsNotNone(im.getbbox())
        self.assertEqual(len(list(self.output.rglob('*.webp'))), 1)

    def test_changed_source_hash_rejected_before_output(self):
        p = Path(self.evidence['characters'][self.cid]['sources']['sprite_sheet.png']['path'])
        p.write_bytes(p.read_bytes() + b'change')
        with self.assertRaisesRegex(ValueError, '哈希'):
            self.resolve()
        self.assertFalse(self.output.exists())

    def test_public_frame_mismatch_uses_same_character_verified_static_only(self):
        altered = Image.new('RGBA', (7, 5), (1, 2, 3, 255)); stream = io.BytesIO()
        altered.save(stream, 'WEBP', lossless=True)
        self.actions[0]['url'] = self.save(stream.getvalue())
        self.write_site()
        media = self.resolve()['media'][self.cid]
        self.assertFalse(media['actions']['idle']['animated'])
        self.assertEqual(media['actions']['idle']['url'], self.actions[0]['poster']['url'])
        self.assertTrue(any('静帧' in s for s in media['missingCues']))

    def test_wrong_poster_and_animation_both_fail_instead_of_guessing_anchor(self):
        self.actions[0]['url'] = self.actions[1]['url']
        self.actions[0]['poster'] = self.actions[1]['poster']
        self.write_site()
        with self.assertRaisesRegex(ValueError, '静帧|匹配'):
            self.resolve()

    def test_missing_ready_reuses_verified_idle_and_marks_gap(self):
        self.actions = [a for a in self.actions if a['kind'] != 'skill_ready']; self.write_site()
        media = self.resolve()['media'][self.cid]
        self.assertFalse(media['actions']['skill_ready']['animated'])
        self.assertTrue(any('准备动作' in s for s in media['missingCues']))

    def test_unknown_voice_override_rejected(self):
        directory = self.repo / 'mod-tools/wiki-battle'; directory.mkdir(parents=True)
        (directory / 'media-overrides.json').write_text(json.dumps({'schema': 1, 'characters': {
            self.cid: {'voices': {'ready': ['media/' + 'f' * 64 + '.mp3']}}}}))
        with self.assertRaisesRegex(ValueError, '语音|来源'):
            self.resolve()

    def test_coffin_out_of_atlas_and_transparent_are_rejected(self):
        source = self.evidence['coffin']['sources']['atlas']
        raw = packed([dict(n='battle/common/layer0/.gen/coffin/f0089', x=11, y=0, w=12, h=15, fw=64, fh=64, fx=0, fy=0)])
        Path(source['path']).write_bytes(raw); source['sha256'] = sha(raw)
        with self.assertRaisesRegex(ValueError, '越界'):
            self.resolve()
        self.evidence['coffin'] = self.coffin()
        source = self.evidence['coffin']['sources']['sheet']; stream = io.BytesIO()
        Image.new('RGBA', (12, 15)).save(stream, 'PNG'); raw = stream.getvalue()
        Path(source['path']).write_bytes(raw); source['sha256'] = sha(raw)
        with self.assertRaisesRegex(ValueError, '透明'):
            self.resolve()

    def test_unsafe_public_url_and_output_overlap_rejected(self):
        self.actions[0]['url'] = '../outside.webp'; self.write_site()
        with self.assertRaisesRegex(ValueError, '路径|URL'):
            self.resolve()
        with self.assertRaisesRegex(ValueError, '输出|覆盖'):
            resolve_native_media(self.repo, self.evidence, self.site)

    def test_coffin_trim_cannot_silently_clip_outside_original_frame(self):
        spec = self.evidence['coffin']['sources']['atlas']
        raw = packed([dict(n='battle/common/layer0/.gen/coffin/f0089', x=0, y=0, w=12, h=15,
                           fw=64, fh=64, fx=-60, fy=-23)])
        Path(spec['path']).write_bytes(raw); spec['sha256'] = sha(raw)
        with self.assertRaisesRegex(ValueError, '越界'):
            self.resolve()
        self.assertFalse(self.output.exists())

    def test_switched_ready_cannot_be_overridden_into_ordinary_ready(self):
        directory = self.repo / 'mod-tools/wiki-battle'; directory.mkdir(parents=True)
        (directory / 'media-overrides.json').write_text(json.dumps({'schema': 1, 'characters': {
            self.cid: {'voices': {'ready': [self.switched_voice]}}}}))
        with self.assertRaisesRegex(ValueError, '语音|来源'):
            self.resolve()

    def test_late_native_source_drift_rejects_before_coffin_write(self):
        original = media_module._coffin
        path = Path(self.evidence['characters'][self.cid]['sources']['sprite_sheet.png']['path'])
        def mutate(reader, spec):
            result = original(reader, spec); path.write_bytes(b'changed after read'); return result
        with patch.object(media_module, '_coffin', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, '哈希'):
                self.resolve()
        self.assertFalse(self.output.exists())

    def test_nonfinite_origin_cannot_become_css_anchor(self):
        spec = self.evidence['characters'][self.cid]['sources']['pixelart.frame.amf3.deflate']
        frame = tree(Path(spec['path']).read_bytes()); frame['x'] = float('inf')
        raw = packed(frame); Path(spec['path']).write_bytes(raw); spec['sha256'] = sha(raw)
        with self.assertRaisesRegex(ValueError, '坐标'):
            self.resolve()

    def test_public_hash_tamper_and_extra_script_are_rejected(self):
        p = self.site / self.avatar; p.write_bytes(p.read_bytes() + b'tamper')
        with self.assertRaisesRegex(ValueError, '哈希'):
            self.resolve()
        p = self.site / 'data.js'; raw = p.read_bytes() + b'alert(1);'
        p.write_bytes(raw); self.evidence['site']['catalogSha256'] = sha(raw)
        with self.assertRaises(ValueError):
            self.resolve()


if __name__ == '__main__':
    unittest.main()
