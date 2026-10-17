import base64
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import wave
import zlib

import numpy as np

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_art_voice_api as api
import wf_assets
import wf_mod_tool as core
import wf_seasonal7_voice as s7

try:
    FFMPEG, FFPROBE = s7.find_tool('ffmpeg'), s7.find_tool('ffprobe')
except FileNotFoundError:
    FFMPEG = FFPROBE = None
HAVE_FFMPEG = FFMPEG is not None and FFPROBE is not None

SHORT = {'join': 'ally/join', 'evolution': 'ally/evolution'}
# 官方 live character_voice_exclude 的 17 段（mech_voice.md §1.3h）。
LIVE_EXCLUDE = '|'.join([
    'character/ruin_girl/voice/', 'character/ruin_girl_3halfanv/voice/', 'character/ruin_girl_halfanv/voice/',
    'character/ruin_girl_smr21/voice/', 'bgm/character_unique/ruin_girl',
    'sound_effect/unique/se_ruin_girl_special_attack', 'ruin_girl_halfanv', 'urban_soldier', 'bishop_girl',
    'bishop_girl_smr20', 'red_gunner', 'urban_soldier_ny21', 'ruin_girl_smr21', 'magical_bayonetter',
    'dragon_slayer', 'dragon_slayer_smr21', 'berserker'])


def design_voice(refs_index=None, **changes):
    lines = []
    for index, slot in enumerate(s7.SLOTS):
        short = slot.split('/', 1)[1]
        zh = f'字幕,"引号"\n第二行{index}' if slot in s7.SUBTITLE_SLOTS else f'战斗{index}'
        lines.append(dict(slot=short, ja=f'台詞{index}です。', zh=zh, direction='落ち着いて'))
    voice = dict(persona='成熟从容的成年男性声音', references=None, lines=lines, route={'kind': 3})
    voice.update(changes)
    return voice


def make_refs(root: Path, role='regis'):
    entries = []
    for kind in ('battle', 'home'):
        path = root / 'refs' / role / f'{kind}.wav'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'RIFF' + kind.encode() * 64)
        entries.append(dict(kind=kind, path=str(path), sha256=s7.sha(path.read_bytes())))
    return dict(schema=1, roles={role: dict(references=entries)})


class Response:
    status = 200
    headers = {'X-Tt-Logid': 'log-1', 'Content-Type': 'application/json'}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, *_):
        return json.dumps({'audio': base64.b64encode(b'audio' * 300).decode(), 'duration': 1,
                           'subtitle': {'text': 'x', 'sentences': []}}).encode()


def http_error(status, code, message):
    raw = json.dumps({'error': {'code': code, 'message': message}}).encode()
    return urllib.error.HTTPError(api.ENDPOINT, status, 'err', {}, io.BytesIO(raw))


class SlotRouteTests(unittest.TestCase):
    def test_twenty_two_official_slots_are_reachable_and_normalized(self):
        self.assertEqual(len(s7.SLOTS), 22)
        self.assertEqual(s7.gate.engine_reachable(list(s7.SLOTS)), {'unreachable': [], 'dead_prefix': []})
        self.assertEqual(s7.normalize_slot('skill_3'), 'battle/skill_3')
        self.assertEqual(s7.normalize_slot('home_5'), 'home/home_5')
        self.assertEqual(s7.normalize_slot('join'), 'ally/join')
        self.assertEqual(s7.normalize_slot('battle/matched_skill_ready'), 'battle/matched_skill_ready')
        self.assertEqual(s7.family('battle/matched_skill_ready'), 'skill_ready')
        for bad in ('skill_4', 'home/matsuri', '../x', 'battle/../skill_0', 'battle\\skill_0', 'normal_attack_0',
                    'skill_0.mp3', 'exchange_power_flip_0', ''):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                s7.normalize_slot(bad)

    def test_role_keys_are_lowercase_and_codes_avoid_live_exclusions(self):
        codes = [info['code'] for info in s7.ROLES.values()]
        self.assertEqual(len(set(codes)), 7)
        for role, info in s7.ROLES.items():
            self.assertRegex(role, r'^[a-z]+$')
            for slot in s7.SLOTS:
                self.assertFalse(s7.native_excluded(f'character/{info["code"]}/voice/{slot}', LIVE_EXCLUDE))

    def test_route_kinds_zero_one_three(self):
        code = 'rec_android_seaside'
        key = code + '_voice_ready'
        self.assertEqual(s7.normalize_route({'kind': 0, 'hp_threshold': '0.5'}, code),
                         ['0', '', '', '', '0.5', key, 'false', 'false'])
        self.assertEqual(s7.normalize_route({'kind': 'ConditionExist', 'condition_kind': '28', 'condition_id': '139994'}, code),
                         ['1', '28', '139994', '', '', key, 'false', 'false'])
        self.assertEqual(s7.normalize_route({'kind': 'skill_flag'}, code), ['3', '', '', '', '', key, 'false', 'false'])
        self.assertEqual(s7.normalize_route(['3', '', '', '', '', key, 'false', 'false'], code)[0], '3')
        for bad in ({'kind': 4}, {'kind': 2}, {'kind': 0}, {'kind': 0, 'threshold': '1.5'}, {'kind': 1, 'c10': '28'},
                    ['3', '', '', '', '', 'other_voice_ready', 'false', 'false'],
                    ['3', '', '', '', '', key, 'true', 'false'], None, {'kind': 'Fever'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                s7.normalize_route(bad, code)


class RequestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.refs = make_refs(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_design_lines_become_api_payloads_in_slot_order(self):
        lines = s7.request_lines('regis', design_voice(), refs_index=self.refs)
        self.assertEqual([x['slot'] for x in lines], list(s7.SLOTS))
        first = lines[0]
        self.assertEqual((first['role'], first['code'], first['character_id']), ('regis', 'rec_android_seaside', '139994'))
        self.assertEqual(len(first['references']), 2)
        payload = api.payload(first)
        self.assertIn('目标9至13秒', payload['text_prompt'])
        self.assertTrue(payload['text_prompt'].endswith('只说以下日语台词：台詞0です。'))
        self.assertNotIn('。。', payload['text_prompt'])
        self.assertEqual(len(payload['references']), 2)
        skill = next(x for x in lines if x['slot'] == 'battle/skill_2')
        self.assertIn('1.8至3.2秒', skill['direction'])

    def test_tts_text_and_explicit_references(self):
        voice = design_voice()
        voice['lines'][0]['tts_text'] = 'みしま'
        ref = self.refs['roles']['regis']['references'][0]
        voice['references'] = [dict(path=ref['path'], sha256=ref['sha256'])]
        line = s7.request_lines('regis', voice, refs_index=self.refs)[0]
        self.assertTrue(api.payload(line)['text_prompt'].endswith('みしま'))
        self.assertEqual(len(line['references']), 1)

    def test_incomplete_duplicate_long_subtitle_and_drift_rejected(self):
        voice = design_voice()
        voice['lines'].pop()
        with self.assertRaisesRegex(ValueError, 'incomplete 22-slot'):
            s7.request_lines('regis', voice, refs_index=self.refs)
        self.assertEqual(len(s7.request_lines('regis', voice, refs_index=self.refs, allow_partial=True)), 21)
        voice = design_voice()
        voice['lines'][1]['slot'] = 'join'
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            s7.request_lines('regis', voice, refs_index=self.refs)
        voice = design_voice()
        voice['lines'][2]['zh'] = '长' * 83
        with self.assertRaisesRegex(ValueError, '82'):
            s7.request_lines('regis', voice, refs_index=self.refs)
        voice = design_voice()
        voice['lines'][10]['zh'] = '战' * 120  # battle 字幕不进表，不受 82 限制
        s7.request_lines('regis', voice, refs_index=self.refs)
        Path(self.refs['roles']['regis']['references'][0]['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'reference hash drift'):
            s7.request_lines('regis', design_voice(), refs_index=self.refs)

    def test_plan_role_reads_design_json_and_route(self):
        path = self.root / 'regis.json'
        path.write_text(json.dumps(dict(voice=design_voice(route={'kind': 0, 'threshold': 0.5})), ensure_ascii=False),
                        encoding='utf-8')
        plan = s7.plan_role('regis', path, refs_index=self.refs)
        self.assertEqual(plan['route'][0:5], ['0', '', '', '', '0.5'])
        self.assertEqual(len(plan['lines']), 22)


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        refs = make_refs(self.root)
        voice = design_voice()
        self.line = s7.request_lines('regis', voice, refs_index=refs)[10]
        self.out = self.root / 'run'
        self.key = 'k-secret-credential-value-0123456789'
        self.sleeps = []

    def tearDown(self):
        self.temp.cleanup()

    def gen(self, opener, **kw):
        return s7.generate_line(self.line, self.out, self.key, opener=opener, sleep=self.sleeps.append, **kw)

    def assert_no_key(self):
        for path in self.out.rglob('*'):
            if path.is_file() and path.suffix == '.json':
                self.assertNotIn(self.key, path.read_text(encoding='utf-8'))

    def test_success_then_cached_resume(self):
        calls = []

        def opener(request, **_):
            calls.append(request)
            return Response()
        self.assertEqual(self.gen(opener)['status'], 'generated')
        self.assertEqual(self.gen(opener)['status'], 'cached')
        self.assertEqual(len(calls), 1)
        self.assert_no_key()

    def test_quota_failure_retries_once_and_budget_persists_across_runs(self):
        calls = []

        def opener(*_a, **_k):
            calls.append(1)
            raise http_error(429, 45000292, 'quota exceeded ' + self.key)
        result = self.gen(opener)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.sleeps, [30.0])
        self.assertEqual(self.gen(opener)['status'], 'retry_exhausted')
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(list((self.out / 'regis' / 'attempts').rglob('*.json'))), 2)
        self.assert_no_key()

    def test_transient_failure_then_success(self):
        state = []

        def opener(*_a, **_k):
            state.append(1)
            if len(state) == 1:
                raise http_error(500, 55001309, 'audio generate internal error')
            return Response()
        result = self.gen(opener)
        self.assertEqual((result['status'], result['attempts']), ('generated', 2))
        self.assertEqual(self.sleeps, [10.0])

    def test_audit_failure_goes_to_rewrite_queue_without_retry(self):
        calls = []

        def opener(*_a, **_k):
            calls.append(1)
            raise http_error(400, 45001125, 'demo text audit failed')
        self.assertEqual(self.gen(opener)['status'], 'needs_rewrite')
        self.assertEqual(self.gen(opener)['status'], 'needs_rewrite')
        self.assertEqual(len(calls), 1)
        queue = s7.rewrite_queue([self.line], self.out)
        self.assertEqual([(q['slot'], q['api_code']) for q in queue], [(self.line['slot'], '45001125')])
        rewritten = dict(self.line, ja='改めて参ります。')
        self.assertEqual(s7.rewrite_queue([rewritten], self.out), [])
        self.assertEqual(s7.generate_line(rewritten, self.out, self.key, opener=lambda *a, **k: Response(),
                                          sleep=self.sleeps.append)['status'], 'generated')

    def test_other_client_error_is_not_retried_automatically(self):
        calls = []

        def opener(*_a, **_k):
            calls.append(1)
            raise http_error(403, 45000001, 'forbidden')
        self.assertEqual(self.gen(opener)['status'], 'failed')
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.gen(opener)['status'], 'failed')
        self.assertEqual(self.gen(opener)['status'], 'retry_exhausted')
        self.assertEqual(len(calls), 2)

    def test_changed_line_with_existing_audio_is_conflict_and_retry_cap(self):
        self.gen(lambda *a, **k: Response())
        changed = dict(self.line, ja='別の台詞')
        result = s7.generate_line(changed, self.out, self.key, opener=lambda *a, **k: self.fail('network'))
        self.assertEqual(result['status'], 'conflict')
        with self.assertRaises(ValueError):
            self.gen(lambda *a, **k: Response(), max_retries=2)

    def test_run_generation_caps_concurrency_and_writes_summary(self):
        with self.assertRaisesRegex(ValueError, 'capped at 2'):
            s7.run_generation([self.line], self.out, self.key, workers=3)
        summary = s7.run_generation([self.line], self.out, self.key, workers=2, opener=lambda *a, **k: Response(),
                                    sleep=self.sleeps.append)
        self.assertEqual(summary['counts'], {'generated': 1})
        self.assertTrue((self.out / 'generation-summary.json').is_file())
        self.assertEqual(json.loads((self.out / 'rewrite_queue.json').read_bytes()), [])
        self.assert_no_key()

    def test_scrub_and_child_env_never_put_key_in_argv(self):
        leak = self.out / 'leak.json'
        leak.parent.mkdir(parents=True, exist_ok=True)
        leak.write_text(json.dumps({'x': self.key}), encoding='utf-8')
        self.assertEqual(s7.scrub_secret(self.out, self.key), [str(leak)])
        self.assert_no_key()
        key_file = self.root / 'seed.key'
        key_file.write_text(self.key + '\n', encoding='utf-8')
        env = s7.child_env(key_file)
        self.assertEqual(env[s7.KEY_ENV], self.key)
        argv = s7._child_argv(['generate', '--key-file', str(key_file), '--roles', 'regis', f'--key-file={key_file}'])
        self.assertEqual(argv, ['generate', '--roles', 'regis'])

    def test_capturing_opener_reports_field_shapes_not_audio(self):
        sink = {}
        with s7.capturing_opener(sink, lambda *a, **k: Response())(object()) as response:
            body = json.loads(response.read())
        self.assertIn('audio', body)
        self.assertEqual(sink['fields']['audio']['type'], 'str')
        self.assertNotIn('value', sink['fields']['audio'])
        self.assertEqual(sink['fields']['subtitle']['keys'], ['sentences', 'text'])
        self.assertEqual(sink['headers']['X-Tt-Logid'], 'log-1')


def write_wav(path: Path, samples: np.ndarray, rate: int = 48000):
    data = np.clip(samples, -1, 1)
    frames = (data * 32767).astype('<i2')
    channels = 1 if frames.ndim == 1 else frames.shape[1]
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(frames.tobytes())


def speechlike(seconds: float, rate: int = 48000, level: float = 0.05, seed: int = 1):
    t = np.arange(int(seconds * rate)) / rate
    rng = np.random.default_rng(seed)
    f0 = 140 + 30 * np.sin(2 * np.pi * 0.7 * t)
    phase = 2 * np.pi * np.cumsum(f0) / rate
    voiced = sum(np.sin(k * phase) / k for k in range(1, 12))
    envelope = np.clip(np.sin(2 * np.pi * 2.5 * t), 0, None) ** 0.6
    envelope[: int(0.15 * rate)] = 0
    envelope[-int(0.3 * rate):] = 0
    return level * voiced * envelope + 0.002 * rng.standard_normal(len(t)) * envelope


@unittest.skipUnless(HAVE_FFMPEG, 'local ffmpeg unavailable')
class MasteringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_quiet_mono_source_reaches_minus_14_lufs_native_container(self):
        source = self.root / 'raw.wav'
        write_wav(source, speechlike(2.2, level=0.03))
        target = self.root / 'standard' / 'skill_0.mp3'
        stored, report = s7.master_voice(source, target, slot='battle/skill_0', code='fixture_code',
                                         ffmpeg=FFMPEG, ffprobe=FFPROBE)
        self.assertLessEqual(abs(report['final']['lufs_i'] - s7.TARGET_LUFS), s7.LOUDNESS_TOLERANCE)
        self.assertLessEqual(report['final']['true_peak_dbtp'], s7.PEAK_CEILING)
        self.assertEqual((report['codec']['srate'], report['codec']['channels'], report['codec']['bitrate']),
                         ([44100], [1], [96]))
        self.assertTrue(report['codec']['cbr'] and report['codec']['obfuscated'] and report['codec']['xing'])
        self.assertEqual(wf_assets.mp3_decode(stored), target.read_bytes())
        self.assertLessEqual(abs(report['sample_delta']), s7.SAMPLE_DELTA_LIMIT)
        self.assertEqual(report['findings'], [])
        self.assertFalse(list(target.parent.glob('*.tmp.mp3')))

    def test_peaky_stereo_source_uses_bounded_limiter_below_ceiling(self):
        speech = speechlike(2.5, level=0.25)
        clicks = np.zeros_like(speech)
        clicks[::9600] = 0.98
        stereo = np.stack([speech + clicks, speech - clicks * 0.5], axis=1)
        source = self.root / 'loud.wav'
        write_wav(source, stereo)
        stored, report = s7.master_voice(source, self.root / 'o' / 'power_flip_0.mp3', slot='battle/power_flip_0',
                                         code='fixture_code', ffmpeg=FFMPEG, ffprobe=FFPROBE)
        self.assertIsNotNone(report['limiter_ceiling_dbfs'])
        self.assertLessEqual(report['limiter_reduction_bound_db'], s7.MAX_LIMITER_REDUCTION_DB + 1e-6)
        self.assertLessEqual(report['final']['true_peak_dbtp'], s7.PEAK_CEILING)
        self.assertEqual(report['mastered_pcm']['clipped_fraction'], 0)
        self.assertEqual(report['codec']['channels'], [1])
        self.assertTrue(stored)

    def test_over_family_maximum_is_reported_not_hidden(self):
        source = self.root / 'long.wav'
        write_wav(source, speechlike(4.3))
        _stored, report = s7.master_voice(source, self.root / 'o' / 'matched.mp3', slot='battle/matched_skill_ready',
                                          code='fixture_code', ffmpeg=FFMPEG, ffprobe=FFPROBE)
        self.assertEqual(report['family'], 'skill_ready')
        self.assertEqual([f['rule'] for f in report['findings']], ['over_official_max'])
        self.assertEqual(report['findings'][0]['limit'], 3.81)


def encode_tone(path: Path, frequency: int, seconds: float):
    subprocess.run([str(FFMPEG), '-v', 'error', '-y', '-f', 'lavfi', '-i',
                    f'sine=frequency={frequency}:duration={seconds}:sample_rate=44100', '-af', 'volume=0.3',
                    '-map_metadata', '-1', '-c:a', 'libmp3lame', '-ar', '44100', '-ac', '1', '-b:a', '96k',
                    '-minrate', '96k', '-maxrate', '96k', '-write_xing', '1', '-id3v2_version', '0', str(path)],
                   check=True, capture_output=True)


def action_rows(code):
    return {level: [f'name{level}', 'desc', 'icon', 'true', '680', '630', '1',
                    f'battle/action/skill/action/rare5/{code}${code}_{level}',
                    '1', '2', '2400', '3000', '0', '0', '0', '0', '(None)', '', '', '', '', '', '', '']
            for level in ('1', '2')}


def character_row(code):
    row = [f'keep-{i}' for i in range(37)]
    row[0] = row[8] = code
    row[9:17] = ['(None)', '', '', '', '', '', '', '']
    return row


@unittest.skipUnless(HAVE_FFMPEG, 'local ffmpeg unavailable')
class PackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory()
        cls.standard = Path(cls.shared.name) / 'standard'
        for index, slot in enumerate(s7.SLOTS):
            path = cls.standard / (slot + '.mp3')
            path.parent.mkdir(parents=True, exist_ok=True)
            seconds = 4.0 if slot in s7.SUBTITLE_SLOTS else 2.5 if 'win' in slot else 1.2
            encode_tone(path, 300 + 37 * index, seconds)

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        refs = make_refs(self.root)
        self.lines = s7.request_lines('regis', design_voice(), refs_index=refs)
        self.package = self.root / 'work' / 'character_packs' / 'seasonal-regis' / 'package'
        self.package.mkdir(parents=True)
        self.code, self.cid = 'rec_android_seaside', '139994'
        (self.package.parent / 'workspace.json').write_text(json.dumps(dict(character_id=139994, code_name=self.code)))

    def tearDown(self):
        self.temp.cleanup()

    def pack(self, **kw):
        options = dict(route={'kind': 3}, character_row=character_row(self.code), action_rows=action_rows(self.code))
        options.update(kw)
        standard = options.pop('standard', self.standard)
        return s7.pack_voice(self.package, 'regis', self.lines, standard, **options)

    def test_writes_storage_state_voice_rows_and_claims(self):
        result = self.pack()
        self.assertEqual(len(result['assets']), 22)
        for slot in s7.SLOTS:
            path = self.package / 'roots' / 'common' / 'character' / self.code / 'voice' / (slot + '.mp3')
            self.assertEqual(wf_assets.mp3_decode(path.read_bytes()), (self.standard / (slot + '.mp3')).read_bytes())
            self.assertTrue(s7.gate.probe(path.read_bytes())['obfuscated'])
        speech = s7.decode_flat_rows(result['table_rows'][s7.SPEECH_TABLE][self.cid])
        self.assertEqual(len(speech), 8)
        self.assertEqual([r[4] for r in speech], [*s7.HOME_SLOTS, 'ally/join', 'ally/evolution'])
        self.assertEqual([r[:3] for r in speech[:6]], [['0', '2', '']] * 6)
        self.assertEqual(speech[6][:3], ['2', '', ''])
        self.assertEqual(speech[7][:3], ['1', '', '1'])
        self.assertEqual(speech[0][3], '字幕,"引号"\n第二行2')
        character = s7.decode_flat_rows(result['table_rows'][s7.CHARACTER_TABLE][self.cid])[0]
        original = character_row(self.code)
        self.assertEqual(character[9:17], ['3', '', '', '', '', self.code + '_voice_ready', 'false', 'false'])
        self.assertEqual(character[:9] + character[17:], original[:9] + original[17:])
        switched = dict(core.decode_action_skill_row(result['table_rows'][s7.SWITCH_TABLE][self.code + '_voice_ready']))
        for level in ('1', '2'):
            self.assertEqual(switched[level], action_rows(self.code)[level][7:24])
        self.assertEqual(result['claims'], [
            {'codec_id': 'flat', 'inner_keys': [], 'logical_path': s7.CHARACTER_TABLE, 'outer_keys': [self.cid],
             'root': 'common', 'semantic_claims': []},
            {'codec_id': 'flat', 'inner_keys': [], 'logical_path': s7.SPEECH_TABLE, 'outer_keys': [self.cid],
             'root': 'common', 'semantic_claims': []},
            {'codec_id': 'switched_nested', 'inner_keys': [{'keys': ['1', '2'], 'outer_key': self.code + '_voice_ready'}],
             'logical_path': s7.SWITCH_TABLE, 'outer_keys': [self.code + '_voice_ready'], 'root': 'common',
             'semantic_claims': []}])
        self.assertFalse(result['writes_live'])
        self.assertEqual(self.pack()['assets'][0]['state'], 'unchanged')

    def test_hp_high_and_condition_routes_and_server_mirror(self):
        mirror = [character_row(self.code)]
        result = self.pack(route={'kind': 0, 'threshold': '0.5'}, mirror_row=mirror, write=False)
        self.assertEqual(result['rows']['route'][:5], ['0', '', '', '', '0.5'])
        self.assertEqual(result['server_rows'][s7.SERVER_CHARACTER][self.cid][0][9:17], result['rows']['route'])
        self.assertEqual(mirror, [character_row(self.code)])
        self.assertEqual(result['claims'][-1]['codec_id'], 'json_object')
        self.assertFalse((self.package / 'roots').exists())
        result = self.pack(route={'kind': 1, 'condition_kind': '28', 'condition_id': '139994'}, write=False)
        self.assertEqual(result['rows']['route'][:3], ['1', '28', '139994'])

    def test_refuses_identity_existing_switch_foreign_file_and_exclusion(self):
        other = character_row(self.code)
        other[9:17] = ['0', '', '', '', '0.5', 'something_else', 'false', 'false']
        with self.assertRaisesRegex(ValueError, 'existing unrelated skill switch'):
            self.pack(character_row=other, write=False)
        with self.assertRaisesRegex(ValueError, 'identity'):
            s7.pack_voice(self.package, 'tekuto', [dict(x, role='tekuto') for x in self.lines], self.standard,
                          route={'kind': 3}, character_row=character_row('super_robot_tailcoat'),
                          action_rows=action_rows('super_robot_tailcoat'))
        outside = self.root / 'elsewhere'
        outside.mkdir()
        with self.assertRaisesRegex(ValueError, 'character_packs'):
            s7.pack_voice(outside, 'regis', self.lines, self.standard, route={'kind': 3},
                          character_row=character_row(self.code), action_rows=action_rows(self.code))
        with self.assertRaisesRegex(ValueError, 'character_voice_exclude'):
            self.pack(exclude_rules='rec_android', write=False)
        self.pack()
        foreign = self.package / 'roots' / 'common' / 'character' / self.code / 'voice' / 'home' / 'matsuri.mp3'
        foreign.write_bytes(b'old')
        altered = dict((slot, (self.standard / (slot + '.mp3')).read_bytes()) for slot in s7.SLOTS)
        altered['battle/win_0'] = (self.standard / 'battle/win_1.mp3').read_bytes()
        altered['battle/win_1'] = (self.standard / 'battle/win_0.mp3').read_bytes()
        with self.assertRaisesRegex(ValueError, 'differs'):
            self.pack(standard=altered)
        result = self.pack(standard=altered, replace=True)
        self.assertEqual(result['foreign_voice_files'], [f'character/{self.code}/voice/home/matsuri.mp3'])

    def test_over_max_duration_and_incomplete_plan_rejected(self):
        loud = dict((slot, (self.standard / (slot + '.mp3')).read_bytes()) for slot in s7.SLOTS)
        long_path = self.root / 'long.mp3'
        encode_tone(long_path, 999, 4.2)
        loud['battle/matched_skill_ready'] = long_path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'over_official_max'):
            self.pack(standard=loud, write=False)
        with self.assertRaisesRegex(ValueError, 'full 22-slot'):
            s7.pack_voice(self.package, 'regis', self.lines[:-1], self.standard, route={'kind': 3},
                          character_row=character_row(self.code), action_rows=action_rows(self.code), write=False)
        with self.assertRaisesRegex(ValueError, 'missing matched_skill_ready route'):
            self.pack(route=None, write=False)

    def test_apply_package_tables_splices_only_owned_keys(self):
        common = self.package / 'roots' / 'common'
        def table(logical, rows):
            path = common / logical
            path.parent.mkdir(parents=True, exist_ok=True)
            obj = core.OrderedMap(logical, list(rows), list(rows.values()), path)
            path.write_bytes(core.build_orderedmap_raw_rows(obj))
            return path
        foreign_row = s7.encode_flat_rows([['foreign', 'row']])
        char = table(s7.CHARACTER_TABLE, {'111001': foreign_row, self.cid: s7.encode_flat_rows([character_row(self.code)])})
        speech = table(s7.SPEECH_TABLE, {'111001': foreign_row, self.cid: s7.encode_flat_rows([['0', '2', '', '旧', 'home/x']])})
        switch = table(s7.SWITCH_TABLE, {'megumin': b'nested-bytes'})
        table(s7.ACTION_TABLE, {self.code: core.encode_action_skill_row(list(action_rows(self.code).items()))})
        server = self.package / 'roots' / 'server' / s7.SERVER_CHARACTER
        server.parent.mkdir(parents=True, exist_ok=True)
        server.write_text(json.dumps({'111001': [['x']], self.cid: [character_row(self.code)]}, ensure_ascii=False,
                                     separators=(',', ':')), encoding='utf-8')
        result = s7.pack_voice(self.package, 'regis', self.lines, self.standard, route={'kind': 3},
                               mirror_row=json.loads(server.read_bytes())[self.cid])
        report = s7.apply_package_tables(self.package, result)
        self.assertTrue(all(item['changed'] for item in report))
        for path, logical in ((char, s7.CHARACTER_TABLE), (speech, s7.SPEECH_TABLE), (switch, s7.SWITCH_TABLE)):
            rows = dict(zip(*(lambda t: (t.keys, t.rows))(core.read_orderedmap_raw_rows_from_bytes(path.read_bytes()))))
            if logical == s7.SWITCH_TABLE:
                self.assertEqual(rows['megumin'], b'nested-bytes')
            else:
                self.assertEqual(rows['111001'], foreign_row)
        speech_rows = dict(zip(*(lambda t: (t.keys, t.rows))(core.read_orderedmap_raw_rows_from_bytes(speech.read_bytes()))))
        self.assertEqual(len(s7.decode_flat_rows(speech_rows[self.cid])), 8)
        mirror = json.loads(server.read_bytes())
        self.assertEqual(mirror['111001'], [['x']])
        self.assertEqual(mirror[self.cid][0][9], '3')
        self.assertEqual(s7.apply_package_tables(self.package, result)[0]['changed'], False)


class ReferenceSelectionTests(unittest.TestCase):
    def test_first_candidate_inside_range_wins_and_rejections_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            durations = {'a': 1.29, 'b': 2.7, 'c': 3.0}

            def render(code, slot):
                path = Path(temp) / f'{slot}.wav'
                path.write_bytes(b'x')
                return path, dict(duration_seconds=durations[slot])
            chosen, path, info, rejected = s7.choose_reference([('x', 'a'), ('x', 'b'), ('x', 'c')], render, 1.5, 6.0)
            self.assertEqual(chosen, ('x', 'b'))
            self.assertEqual(info['duration_seconds'], 2.7)
            self.assertEqual(rejected[0]['source_logical'], 'character/x/voice/a.mp3')
            self.assertFalse((Path(temp) / 'a.wav').exists())
            with self.assertRaises(ValueError):
                s7.choose_reference([('x', 'a')], render, 1.5, 6.0)

    def test_every_role_has_battle_and_home_candidates_and_campus_recipe(self):
        self.assertEqual(set(s7.REF_CANDIDATES), set(s7.ROLES))
        for role, kinds in s7.REF_CANDIDATES.items():
            self.assertEqual(set(kinds), {'battle', 'home'})
            for kind, items in kinds.items():
                for code, slot in items:
                    self.assertTrue(slot.startswith('battle/' if kind == 'battle' else 'home/'))
        self.assertIn('highpass=f=70,loudnorm=I=-20:TP=-2:LRA=11', s7.REF_FILTERS)


if __name__ == '__main__':
    unittest.main()
