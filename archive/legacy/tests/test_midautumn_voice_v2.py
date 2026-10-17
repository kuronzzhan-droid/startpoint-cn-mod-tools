# -*- coding: utf-8 -*-
"""中秋第二轮语音管线（prompt 模板 v2）的单测。

覆盖：v2 prompt 逐段结构、按角色槽表、逐槽参考音、边缘裁剪边界、多 take 选优、
跨进程配额锁、台词稿适配、资产词表新增名、45001127 的独立状态。
旧行为（模板 v1、22 槽、定增益后处理）在 tests/test_seasonal7_voice.py 里原样保留。
"""
import base64
import contextlib
from contextlib import ExitStack
import inspect
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import wave

import numpy as np

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_art_voice_api as api
import wf_assets
import wf_midautumn_voice as MV
import wf_seasonal7_voice as s7

try:
    FFMPEG, FFPROBE = s7.find_tool('ffmpeg'), s7.find_tool('ffprobe')
except FileNotFoundError:
    FFMPEG = FFPROBE = None
HAVE_FFMPEG = FFMPEG is not None and FFPROBE is not None


def v2_line(**changes):
    line = dict(role='fluffy', slot='battle/power_flip_0', prompt_version=2, audio_format='wav',
                persona='十几岁后段的少女声。共鸣靠前。', persona_short='十几岁后段的少女声',
                voice_tag='共鸣靠前，语速偏快', tone='极短的发力吐气',
                performance='语速极快；气息短促；整条目标 0.86–1.41 秒，不拖字、不逐字慢读',
                ja='もう一つ！', tts_text='もう一つ！', zh='再来一个！',
                direction='短促', references=[])
    line.update(changes)
    return line


class PromptTemplateTests(unittest.TestCase):
    def test_v2_puts_the_line_last_inside_full_width_quotes(self):
        text = api.payload(v2_line())['text_prompt']
        lines = text.split('\n')
        self.assertEqual(len(lines), 4)                       # 无参考音时少一行分工说明
        self.assertTrue(lines[0].startswith('录音棚干声'))
        self.assertIn('不要朗读本段说明', lines[1])
        self.assertTrue(lines[2].startswith('表演要求：'))
        self.assertTrue(text.endswith('用极短的发力吐气的语气说道：“もう一つ！”'))
        self.assertIn('十几岁后段的少女声（共鸣靠前，语速偏快）', text)
        # 台词被引号封边，且引号只出现这一对。
        self.assertEqual(text.count('“'), 1)
        self.assertEqual(text.count('”'), 1)
        self.assertLess(text.index('表演要求'), text.index('“'))

    def test_reference_note_names_which_audio_does_what(self):
        with tempfile.TemporaryDirectory() as temp:
            refs = []
            for name in ('a', 'b'):
                path = Path(temp) / (name + '.wav')
                path.write_bytes(b'RIFF' + name.encode() * 64)
                refs.append(dict(path=str(path), sha256=s7.sha(path.read_bytes())))
            two = api.payload(v2_line(references=refs))['text_prompt']
            self.assertIn('音色以@音频1为准；若有@音频2，只参考它的语气与短句力度。', two)
            one = api.payload(v2_line(references=refs[:1]))['text_prompt']
            self.assertIn('音色以@音频1为准；这段参考就是这位角色本人', one)
            self.assertNotIn('@音频2', one)

    def test_v2_rejects_the_symbols_that_relocate_or_get_read_aloud(self):
        for bad in ('「散れ」', '『月』', '月華（げっか）', '月華(げっか)', 'バツ×', '月♪'):
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError, 'symbols the model'):
                api.payload(v2_line(tts_text=bad))

    def test_v2_requires_the_four_split_fields(self):
        for name in api.V2_FIELDS:
            with self.subTest(field=name), self.assertRaisesRegex(ValueError, name):
                api.payload(v2_line(**{name: ''}))

    def test_v1_payload_is_byte_for_byte_the_old_shape(self):
        line = dict(role='regis', slot='battle/skill_ready', persona='成年女性教师',
                    direction='自然日语', ja='準備できたわ。', zh='准备好了。', references=[])
        payload = api.payload(line)
        self.assertEqual(payload['audio_config']['format'], 'mp3')
        self.assertTrue(payload['text_prompt'].startswith('成年女性教师。仅一位角色'))
        self.assertTrue(payload['text_prompt'].endswith('只说以下日语台词：準備できたわ。'))
        self.assertNotIn('“', payload['text_prompt'])

    def test_audio_format_drives_container_and_file_extension(self):
        self.assertEqual(api.payload(v2_line())['audio_config']['format'], 'wav')
        self.assertTrue(api.payload(v2_line())['audio_config']['enable_subtitle'])
        with self.assertRaises(ValueError):
            api.payload(v2_line(audio_format='flac'))

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def read(self, *_):
                return json.dumps({'audio': base64.b64encode(b'riffdata' * 200).decode(),
                                   'duration': 1.1}).encode()

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(api.generate(v2_line(), root, 'k', opener=lambda *a, **k: Response())['status'],
                             'generated')
            self.assertTrue((root / 'fluffy' / 'raw' / 'battle' / 'power_flip_0.wav').is_file())
            self.assertFalse((root / 'fluffy' / 'raw' / 'battle' / 'power_flip_0.mp3').exists())
            receipt = json.loads((root / 'fluffy' / 'receipts' / 'battle' / 'power_flip_0.json').read_bytes())
            self.assertEqual((receipt['prompt_version'], receipt['audio_format']), (2, 'wav'))
            self.assertEqual(receipt['tone'], '极短的发力吐气')


class TextRuleTests(unittest.TestCase):
    def test_ruby_expands_to_the_reading(self):
        self.assertEqual(s7.expand_ruby('黒狼騎士（こくろうきし）、カイル。'), 'こくろうきし、カイル。')
        self.assertEqual(s7.expand_ruby('向（む）こうでは教官（きょうかん）を'), 'むこうではきょうかんを')
        self.assertEqual(s7.expand_ruby('月見団子(つきみだんご)'), 'つきみだんご')
        # 非注音括号不动（它会被 api 的符号门拦下，不该在这里被偷偷吃掉）。
        self.assertEqual(s7.expand_ruby('これは（たぶん）'), 'これは（たぶん）')

    def test_duration_band_is_official_p25_to_p75(self):
        self.assertEqual(s7.prompt_band('battle/skill_ready'), (1.15, 1.88))
        self.assertEqual(s7.prompt_band('battle/matched_skill_ready'), (1.15, 1.88))
        self.assertEqual(s7.prompt_band('battle/matched_skill_2'), (2.01, 2.82))
        self.assertEqual(s7.prompt_band('home/home_3'), (8.88, 13.22))
        performance, tone = s7.compose_performance('气息骤停；音量压到最低', 'battle/skill_ready')
        self.assertTrue(performance.endswith('整条目标 1.15–1.88 秒，不拖字、不逐字慢读'))
        self.assertEqual(tone, '气息骤停')
        self.assertNotIn('至2.2秒', performance)              # 不再是第一轮的 p50–p90

    def test_direction_object_becomes_the_six_element_performance(self):
        performance, tone = s7.compose_performance(
            dict(tone='懒散带笑', pace='偏慢', breath='浅', volume='中', stress='第一个音', ending='硬切'),
            'battle/power_flip_0')
        self.assertEqual(tone, '懒散带笑')
        self.assertTrue(performance.startswith('语速偏慢；气息浅；音量中；重音落在第一个音；收尾硬切'))
        self.assertIn('0.86–1.41 秒', performance)

    def test_speaker_label_splits_persona_and_drops_display_quotes(self):
        short, tag = s7.speaker_label(dict(persona='成年男性，「冷酷大哥」声线。音色厚而偏哑。共鸣压在胸腔。'))
        self.assertEqual(short, '成年男性，冷酷大哥声线')
        self.assertEqual(tag, '音色厚而偏哑；共鸣压在胸腔')
        self.assertEqual(s7.speaker_label(dict(persona='x', persona_short='A', voice_tag='B')), ('A', 'B'))

    def test_line_rule_findings(self):
        self.assertEqual(s7.repeated_phrases('整列になって、整列を崩す'), ['整列'])
        long_home = s7.check_ja_rules('home/home_0', 'あ' * 90, 'あ' * 90)
        self.assertIn('over_char_budget', {f['rule'] for f in long_home})

    def test_rules_that_the_recipe_calls_forbidden_are_errors_not_warnings(self):
        # recipe.ja_writing_rules 写「禁止」的三条：短槽 ……、全角空格、超字数预算。
        # 第一版全是 warn ⇒ 钱花完了才在 select 发现，现在 plan 就拦。
        cases = {'battle/skill_ready': ('息、止めるよ。', '息、……止めるよ。', 'ellipsis_in_short_slot'),
                 'battle/skill_0': ('散れ', '散　れ', 'ideographic_space'),
                 'battle/outhole_0': ('あ' * 13, 'あ' * 13, 'over_char_budget')}
        for slot, (ja, tts, rule) in cases.items():
            with self.subTest(rule=rule):
                hit = [f for f in s7.check_ja_rules(slot, ja, tts) if f['rule'] == rule]
                self.assertEqual([f['level'] for f in hit], ['error'])
                self.assertTrue(hit[0]['fix'] and hit[0]['why'])

    def test_symbol_gate_only_guards_the_text_that_reaches_the_api(self):
        # ja 里留装饰符号是允许的（丝缇涅尔的 ♡），前提是另写了干净的 tts_text。
        clean = s7.check_ja_rules('battle/win_0', 'ざぁこ♡ 弱いんだから', 'ざぁこ、弱いんだから',
                                  has_tts_text=True)
        self.assertEqual([f['rule'] for f in clean if f['level'] == 'error'], [])
        self.assertIn('decorative_symbol_in_ja', {f['rule'] for f in clean})
        # 同样的 ja 没写 tts_text ⇒ ♡ 会原样发给接口 ⇒ error，并指名要补 tts_text。
        bare = [f for f in s7.check_ja_rules('battle/win_0', 'ざぁこ♡ 弱いんだから', 'ざぁこ♡ 弱いんだから')
                if f['level'] == 'error']
        self.assertEqual([f['rule'] for f in bare], ['forbidden_symbol'])
        self.assertEqual(bare[0]['field'], 'tts_text')
        self.assertIn('tts_text', bare[0]['fix'])
        self.assertIn('♡', api.FORBIDDEN_TTS_CHARS)
        self.assertIn('♥', api.FORBIDDEN_TTS_CHARS)
        # tts_text 自己带符号照样是 error（这次怪不到缺 tts_text 头上）。
        own = [f for f in s7.check_ja_rules('battle/skill_0', '散れ', '「散れ」', has_tts_text=True)
               if f['level'] == 'error']
        self.assertEqual([f['rule'] for f in own], ['forbidden_symbol'])
        self.assertIn('ja 可以保留', own[0]['fix'])

    def test_char_budget_is_derived_from_the_same_numbers_as_the_duration_gate(self):
        for fam, target in s7.SLOT_TARGETS.items():
            with self.subTest(family=fam):
                budget = s7.char_budget(fam)
                cps = budget['chars_per_second']
                self.assertEqual(cps, s7.CHARS_PER_SECOND_SHORT if fam in s7.SHORT_BATTLE_FAMILIES
                                 else s7.CHARS_PER_SECOND_LONG)
                # 硬上限 = 语速 × p90 = take_gates 里 duration_band 的上沿，一个数两处用。
                self.assertEqual(budget['hard_max'], int(cps * target['p90']))
                self.assertLessEqual(budget['hard_max'] / cps, target['p90'])
                # 软目标带（prompt 写给模型的那条）永远比硬上限紧。
                self.assertLessEqual(budget['target'][1], budget['hard_max'])
                self.assertLessEqual(budget['target'][0], budget['target'][1])
        # 长槽也有预算，不是只卡战斗短槽。
        self.assertEqual(s7.char_budget('home')['hard_max'], 63)
        self.assertEqual(s7.char_budget('join')['hard_max'], 55)
        self.assertEqual(s7.char_budget('evolution')['hard_max'], 60)
        self.assertEqual(s7.char_budget('outhole_N')['hard_max'], 9)

    def test_over_budget_is_an_error_and_merely_over_target_is_a_warning(self):
        budget = s7.char_budget('outhole_N')                      # target 3–7、hard 9
        hard = [f for f in s7.check_ja_rules('battle/outhole_0', 'あ' * 13, 'あ' * 13)
                if f['rule'] == 'over_char_budget']
        self.assertEqual(hard[0]['level'], 'error')
        # 报错要给全预算数字：改稿的人不该回头再查表。
        for key in ('chars', 'limit', 'target_chars', 'hard_max_chars', 'chars_per_second',
                    'estimated_seconds', 'p90_seconds', 'band_seconds'):
            self.assertIn(key, hard[0])
        self.assertEqual(hard[0]['chars'], 13)
        self.assertEqual(hard[0]['limit'], budget['hard_max'])
        soft = [f for f in s7.check_ja_rules('battle/outhole_0', 'あ' * 8, 'あ' * 8)
                if f['rule'].startswith('over_char')]
        self.assertEqual([(f['rule'], f['level']) for f in soft], [('over_char_target', 'warn')])
        short = [f for f in s7.check_ja_rules('battle/outhole_0', 'あ', 'あ')
                 if f['rule'] == 'under_char_budget']
        self.assertEqual(short[0]['level'], 'warn')

    def test_a_line_over_budget_really_would_fail_the_duration_gate(self):
        # 自洽性的实证：按预算语速，超硬上限那一条的预估秒数越过 take_gates 的 p90。
        line = dict(role='fluffy', slot='battle/outhole_0', ja='あ' * 13, tts_text='あ' * 13)
        budget = s7.char_budget('outhole_N')
        seconds = round(13 / budget['chars_per_second'], 3)
        metrics = dict(subtitle_present=False, text_exact=False, text_superset=False,
                       lead_in_seconds=0.05, tail_seconds=0.05, max_inner_gap_seconds=0.0,
                       dead_air_share=0.1)
        qc = dict(seconds=seconds, raw_lufs_i=-18.0, limiter_reduction_bound_db=0.5,
                  final=dict(lufs_i=-14.0, true_peak_dbtp=-2.0), mastered_pcm=dict(clipped_fraction=0))
        self.assertIn('duration_band', s7.take_gates(line, metrics, qc))
        inside = dict(qc, seconds=round(budget['hard_max'] / budget['chars_per_second'], 3))
        self.assertNotIn('duration_band', s7.take_gates(line, metrics, inside))


class RoleSlotTests(unittest.TestCase):
    def setUp(self):
        self.saved = s7.ROLES
        s7.ROLES = dict(fluffy=dict(cid='1', code='a'), kyle=dict(cid='2', code='b', slots=list(s7.SLOTS_26)))

    def tearDown(self):
        s7.ROLES = self.saved

    def test_kyle_has_twenty_six_slots_and_everyone_else_twenty_two(self):
        self.assertEqual(len(s7.role_slots('kyle')), 26)
        self.assertEqual(len(s7.role_slots('fluffy')), 22)
        self.assertEqual(len(s7.role_slots(None)), 22)
        extra = set(s7.role_slots('kyle')) - set(s7.SLOTS)
        self.assertEqual(extra, {'battle/skill_4', 'battle/skill_5',
                                 'battle/battle_start_2', 'battle/battle_start_3'})

    def test_every_kyle_slot_stays_engine_reachable(self):
        self.assertEqual(s7.gate.engine_reachable(list(s7.SLOTS_26)),
                         {'unreachable': [], 'dead_prefix': []})
        # 缺号即断：少了 skill_4 时 skill_5 永远播不到。
        broken = [s for s in s7.SLOTS_26 if s != 'battle/skill_4']
        self.assertEqual(s7.gate.engine_reachable(broken)['unreachable'], ['battle/skill_5'])

    def test_unknown_slot_names_report_the_accepted_set(self):
        for bad in ('skill_ready_2', 'skill_ready_3', 'skill_6', 'home_6', 'exchange_power_flip_0'):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError) as caught:
                    s7.normalize_slot(bad, s7.role_slots('kyle'))
                self.assertIn('this role accepts', str(caught.exception))
        self.assertEqual(s7.normalize_slot('skill_5', s7.role_slots('kyle')), 'battle/skill_5')
        with self.assertRaises(ValueError):
            s7.normalize_slot('skill_5', s7.role_slots('fluffy'))
        with self.assertRaises(ValueError):
            s7.normalize_slot('skill_5')                      # 默认仍是 22 槽

    def test_family_maps_the_new_numbered_slots(self):
        self.assertEqual(s7.family('battle/skill_5'), 'skill_N')
        self.assertEqual(s7.family('battle/matched_skill_0'), 'skill_N')
        self.assertEqual(s7.family('battle/battle_start_3'), 'battle_start_N')
        self.assertEqual(s7.family('battle/matched_skill_ready'), 'skill_ready')

    def test_slot_order_keeps_the_old_twenty_two_sequence(self):
        self.assertEqual(sorted(s7.SLOTS, key=s7.slot_order), list(s7.SLOTS))


def ref_record(path: Path, name: str, **changes) -> dict:
    """索引里一条合格的参考音记录：区间内 + 整合响度测得出。"""
    low, high = s7.REF_RANGES_V2.get(name, (0.3, 20.0))
    record = dict(path=str(path), sha256=s7.sha(path.read_bytes()), seconds=1.0,
                  range_seconds=[low, high], range_ok=True, lufs_i=-16.0, lufs_i_raw=-16.0,
                  loudness_measurable=True, loudness_method='ebu_r128', rms_dbfs=-16.8,
                  peak_dbfs=-1.5)
    record.update(changes)
    return record


def refs_index_v2(root: Path, role='fluffy'):
    groups, mapping = {}, {}
    for name in ('ready', 'skill', 'pf', 'outhole', 'start', 'win', 'home', 'join'):
        path = root / 'refs' / role / f'{name}.wav'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'RIFF' + name.encode() * 64)
        groups[name] = ref_record(path, name, seconds=(1.0 if name not in ('home', 'join') else 10.0))
    second = root / 'refs' / role / 'home.2.wav'
    second.write_bytes(b'RIFFsecond' * 16)
    groups['home']['second'] = ref_record(second, 'home', seconds=10.0)
    recipe = json.loads((MV.RECIPE_FILE).read_text(encoding='utf-8'))
    mapping = recipe['reference_policy']['per_role'][role]['slot_to_group']
    return dict(schema=2, roles={role: dict(groups=groups, slot_to_group=mapping)})


class ReferenceResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.index = refs_index_v2(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_each_slot_gets_its_own_group_and_never_crosses(self):
        for slot, group in (('battle/power_flip_0', 'pf'), ('battle/skill_ready', 'ready'),
                            ('battle/matched_skill_ready', 'ready'), ('battle/skill_3', 'skill'),
                            ('battle/outhole_1', 'outhole'), ('battle/battle_start_2', 'start'),
                            ('battle/win_0', 'win'), ('home/home_4', 'home'), ('ally/join', 'join')):
            with self.subTest(slot=slot):
                items = s7.resolve_references('fluffy', None, self.index, slot=slot)
                self.assertTrue(items[0]['path'].endswith(f'{group}.wav'))
                # 短槽绝不挂 home：第一轮 0.6s 的 PF 请求里挂着 13s 的家常独白。
                self.assertFalse(any('home.wav' in i['path'] for i in items) and group != 'home')

    def test_second_reference_is_optional_and_same_group(self):
        self.assertEqual(len(s7.resolve_references('fluffy', None, self.index, slot='home/home_0')), 2)
        self.assertEqual(len(s7.resolve_references('fluffy', None, self.index, slot='battle/power_flip_0')), 1)

    def test_missing_mapping_is_an_explicit_error(self):
        index = json.loads(json.dumps(self.index))
        index['roles']['fluffy']['slot_to_group'].pop('battle/power_flip_0')
        with self.assertRaisesRegex(ValueError, 'no reference group mapped'):
            s7.resolve_references('fluffy', None, index, slot='battle/power_flip_0')
        index = json.loads(json.dumps(self.index))
        index['roles']['fluffy'].pop('groups')
        with self.assertRaisesRegex(ValueError, 'per-slot groups'):
            s7.resolve_references('fluffy', None, index, slot='battle/power_flip_0')

    def test_v2_reference_cleaning_targets_minus_sixteen_and_drops_the_one_point_five_floor(self):
        self.assertIn('loudnorm=I=-16:TP=-1.5:LRA=11', s7.REF_FILTERS_V2)
        self.assertNotIn('loudnorm', s7.REF_FILTERS_V2_KEEP_LEVEL)
        self.assertEqual(s7.REF_RANGES_V2['ready'][0], 0.5)
        self.assertLess(s7.REF_RANGES_V2['pf'][0], 1.5)
        self.assertEqual(s7.REF_RANGES_V2['home'], (8.0, 15.0))

    def test_out_of_range_reference_is_refused_not_merely_warned(self):
        index = json.loads(json.dumps(self.index))
        index['roles']['fluffy']['groups']['pf'].update(seconds=0.293, range_ok=False)
        with self.assertRaises(ValueError) as caught:
            s7.resolve_references('fluffy', None, index, slot='battle/power_flip_0')
        self.assertIn('outside 0.5-2.5s', str(caught.exception))
        self.assertIn('exemptions', str(caught.exception))
        # 别的槽不受牵连：只有映射到这个 group 的槽被拦。
        s7.resolve_references('fluffy', None, index, slot='battle/skill_ready')

    def test_fake_loudness_is_refused_unless_the_record_says_it_switched_rulers(self):
        index = json.loads(json.dumps(self.index))
        group = index['roles']['fluffy']['groups']['outhole']
        # -70 LUFS 是「测不出」的下限，不是电平；第一版把它当真数记进索引照用。
        group.update(lufs_i=None, lufs_i_raw=-70.0, loudness_measurable=False,
                     loudness_method='ebu_r128')
        with self.assertRaisesRegex(ValueError, 'unmeasurable'):
            s7.resolve_references('fluffy', None, index, slot='battle/outhole_0')
        # 换成 RMS 归一并在记录里写明 ⇒ 放行。
        group['loudness_method'] = 'rms'
        group['rms_dbfs'] = s7.REFERENCE_TARGET_RMS_DBFS
        self.assertEqual(len(s7.resolve_references('fluffy', None, index, slot='battle/outhole_0')), 1)

    def test_an_explicit_exemption_with_a_reason_is_the_only_way_through(self):
        index = json.loads(json.dumps(self.index))
        group = index['roles']['fluffy']['groups']['ready']
        group.update(seconds=0.32, range_ok=False)
        with self.assertRaises(ValueError):
            s7.resolve_references('fluffy', None, index, slot='battle/skill_ready')
        group['exempt_reason'] = '库里只有这一条 skill_ready'
        self.assertEqual(len(s7.resolve_references('fluffy', None, index, slot='battle/skill_ready')), 1)
        # 空理由不算豁免。
        group['exempt_reason'] = '   '
        with self.assertRaises(ValueError):
            s7.resolve_references('fluffy', None, index, slot='battle/skill_ready')

    def test_the_second_reference_goes_through_the_same_gate(self):
        index = json.loads(json.dumps(self.index))
        index['roles']['fluffy']['groups']['home']['second'].update(seconds=2.0, range_ok=False)
        with self.assertRaisesRegex(ValueError, 'second'):
            s7.resolve_references('fluffy', None, index, slot='home/home_0')

    def test_live_reference_index_has_no_unexempted_defect(self):
        index_path = MV.REWORK2 / 'refs' / 'refs-v2.json'
        if not index_path.is_file():
            self.skipTest('refs-v2.json not built yet')
        index = json.loads(index_path.read_text(encoding='utf-8'))
        blocking = {role: item.get('blocking') for role, item in index['roles'].items()
                    if item.get('blocking')}
        self.assertEqual(blocking, {})
        for role, item in index['roles'].items():
            for name, group in item['groups'].items():
                for label, record in (('primary', group), ('second', group.get('second'))):
                    if not record or 'path' not in record:
                        continue
                    with self.subTest(role=role, group=name, label=label):
                        self.assertEqual(s7.reference_defects(record), [])
                        self.assertIn(record['loudness_method'], ('ebu_r128', 'rms'))


class ScriptAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.scripts = self.root / 'scripts'
        self.scripts.mkdir()
        (self.scripts / 'fluffy.json').write_text(json.dumps(dict(
            key='fluffy', name='芙拉菲', continuity='忽略', grammar='忽略', bible='忽略',
            editor_notes='忽略', changed_vs_round1='忽略',
            persona='十几岁后段的少女声。共鸣靠前。',
            lines=[dict(slot='power_flip_0', ja='もう一つ！', tts_text='もう一つ！', zh='再来一个！',
                        direction='极短的发力吐气；音量到顶', seconds=[0.8, 1.2])]),
            ensure_ascii=False), encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_script_becomes_a_design_with_a_voice_object(self):
        path = MV.synthesize_design('fluffy', folder=self.scripts, out_dir=self.root / 'design',
                                    route={'kind': 3})
        voice = s7.load_design_voice(path)
        self.assertEqual(voice['prompt_version'], 2)
        self.assertEqual(voice['references'], 'groups')
        self.assertEqual(voice['route'], {'kind': 3})
        self.assertEqual(voice['persona'], '十几岁后段的少女声。共鸣靠前。')
        # 稿里的说明性字段不进管线（seconds 由官方分位决定，不是稿里写的）。
        self.assertEqual(set(voice['lines'][0]), {'slot', 'ja', 'tts_text', 'zh', 'direction'})
        self.assertNotIn('bible', json.loads(path.read_text(encoding='utf-8'))['voice'])

    def test_missing_script_names_the_file(self):
        with self.assertRaises(SystemExit):
            MV.synthesize_design('nicola', folder=self.scripts, out_dir=self.root / 'design')

    def test_recipe_reference_specs_resolve_real_sources(self):
        specs = MV.reference_specs(MV.load_recipe(), ['fluffy', 'kyle', 'thorn'])
        self.assertTrue(Path(specs['fluffy']['groups']['pf']['source']).name.startswith('power_flip'))
        # 凯尔的 derive 只写文件名，全路径在 source_measurements 里。
        self.assertTrue(Path(specs['kyle']['groups']['short']['source']).is_absolute())
        # 「同 long.wav」这种中文注记不能当滤镜送给 ffmpeg。
        for group in specs['kyle']['groups'].values():
            self.assertTrue(group['filters'] is None or group['filters'].isascii())
            self.assertNotIn('start_periods=-1', group['filters'] or '')
        self.assertEqual(specs['thorn']['filters'], s7.REF_FILTERS_V2_KEEP_LEVEL)

    def test_reference_exemptions_travel_from_the_recipe_into_the_builder(self):
        """豁免的真源是角色的参考音策略；传不过来的话闸门就只剩「全拦」或「全放」。"""
        recipe = dict(reference_policy=dict(per_role=dict(mia=dict(
            kind='official_master_voice', groups={'pf': dict(source='x.mp3')},
            slot_to_group={'battle/power_flip_0': 'pf'},
            exemptions={'pf': '库里只有这一条 power_flip'}))))
        specs = MV.reference_specs(recipe, ['mia'])
        self.assertEqual(specs['mia']['exemptions'], {'pf': '库里只有这一条 power_flip'})
        # 没写豁免的角色拿到空字典（None 会被下游当成「没有这一项」而漏检）。
        recipe['reference_policy']['per_role']['mia'].pop('exemptions')
        self.assertEqual(MV.reference_specs(recipe, ['mia'])['mia']['exemptions'], {})

    def test_the_live_recipe_declares_no_reference_exemption(self):
        """本轮 9 个超区间 group 全部换成了区间内的官方原声，一条豁免都不该有。"""
        policy = MV.load_recipe()['reference_policy']['per_role']
        self.assertEqual({role: item.get('exemptions') for role, item in policy.items()
                          if item.get('exemptions')}, {})


class FailureClassificationTests(unittest.TestCase):
    def test_reference_audit_is_its_own_state_with_its_own_remedy(self):
        reference = dict(http_status=400, api_code='45001127',
                         api_message='audio risk audit tts_create_ref: chunk 0 rejected')
        self.assertEqual(s7.classify_failure(reference), 'needs_new_reference')
        self.assertEqual(s7.classify_failure(dict(http_status=400, api_code='45001125',
                                                  api_message='demo text audit failed')), 'needs_rewrite')
        self.assertIn('换参考音', s7.REMEDY['needs_new_reference'])
        self.assertIn('改写 ja', s7.REMEDY['needs_rewrite'])


class QuotaLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_same_role_cannot_be_held_twice(self):
        with s7.exclusive_lock('role-fluffy', lock_dir=self.root):
            with self.assertRaisesRegex(RuntimeError, 'holds the voice lock'):
                with s7.exclusive_lock('role-fluffy', lock_dir=self.root, timeout=0):
                    self.fail('two holders of the same role lock')
            with s7.exclusive_lock('role-kyle', lock_dir=self.root, timeout=0):
                pass
        with s7.exclusive_lock('role-fluffy', lock_dir=self.root, timeout=0):
            pass

    def test_quota_slots_are_bounded(self):
        from contextlib import ExitStack
        with ExitStack() as stack:
            held = [stack.enter_context(s7.quota_slot(slots=2, lock_dir=self.root)) for _ in range(2)]
            self.assertEqual(sorted(held), [0, 1])
            with self.assertRaisesRegex(RuntimeError, 'no free'):
                with s7.quota_slot(slots=2, lock_dir=self.root, timeout=0, sleep=lambda _s: None):
                    self.fail('third concurrent slot')

    def test_run_generation_takes_the_role_lock(self):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def read(self, *_):
                return json.dumps({'audio': base64.b64encode(b'x' * 600).decode(), 'duration': 1}).encode()

        saved = s7.ROLES
        s7.ROLES = dict(fluffy=dict(cid='1', code='a'))
        try:
            line = v2_line(references=[])
            with s7.exclusive_lock('role-fluffy', lock_dir=self.root):
                with self.assertRaises(RuntimeError):
                    s7.run_generation([line], self.root / 'run', 'k-secret-credential-value-01',
                                      workers=1, opener=lambda *a, **k: Response(),
                                      role_locks=True, lock_dir=self.root)
            summary = s7.run_generation([line], self.root / 'run', 'k-secret-credential-value-01',
                                        workers=1, opener=lambda *a, **k: Response(),
                                        role_locks=True, lock_dir=self.root)
            self.assertEqual(summary['counts'], {'generated': 1})
            self.assertEqual(summary['role_locks'], ['fluffy'])
        finally:
            s7.ROLES = saved

    def test_generation_holds_a_global_quota_slot_per_in_flight_request(self):
        """配额槽必须真的接进 run_generation —— 第一版定义了、单测了、全仓零调用。"""
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_):
                pass

            def read(self, *_):
                return json.dumps({'audio': base64.b64encode(b'x' * 600).decode(), 'duration': 1}).encode()

        saved = s7.ROLES
        s7.ROLES = dict(fluffy=dict(cid='1', code='a'))
        try:
            line = v2_line(references=[])
            # 外面占满全局配额 ⇒ 生成拿不到槽位，不会照样打接口。
            with ExitStack() as stack:
                for _ in range(s7.MAX_WORKERS):
                    stack.enter_context(s7.quota_slot(slots=s7.MAX_WORKERS, lock_dir=self.root))
                with self.assertRaisesRegex(RuntimeError, 'no free'):
                    s7.run_generation([line], self.root / 'run', 'k-secret-credential-value-01',
                                      workers=1, opener=lambda *a, **k: self.fail('called the API'),
                                      role_locks=False, lock_dir=self.root,
                                      quota_timeout=0, sleep=lambda _s: None)
            summary = s7.run_generation([line], self.root / 'run', 'k-secret-credential-value-01',
                                        workers=1, opener=lambda *a, **k: Response(),
                                        role_locks=False, lock_dir=self.root)
            self.assertEqual(summary['counts'], {'generated': 1})
            self.assertEqual(summary['quota_slots'], s7.MAX_WORKERS)
        finally:
            s7.ROLES = saved

    def test_role_lock_is_on_by_default(self):
        """防重复计费不能靠操作者记得加参数。"""
        self.assertIs(inspect.signature(s7.run_generation).parameters['role_locks'].default, True)
        parsed = []
        saved = (s7._plans, s7.run_generation, s7._take_key, s7.VOICE_DIR, s7.GENERATION_DIR)
        s7.VOICE_DIR, s7.GENERATION_DIR = self.root, self.root / 'generation'
        s7._take_key = lambda: 'k-secret-credential-value-01'
        s7._plans = lambda args: [plan_stub()]
        s7.run_generation = lambda *a, **kw: parsed.append(kw) or dict(
            counts={'generated': 1}, rewrite_queue=0, needs_new_reference=[])
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                s7.main(['generate', '--roles', 'fluffy', '--run', 'r1'])
                s7.main(['generate', '--roles', 'fluffy', '--run', 'r1', '--no-role-lock'])
        finally:
            (s7._plans, s7.run_generation, s7._take_key, s7.VOICE_DIR, s7.GENERATION_DIR) = saved
        self.assertEqual([kw['role_locks'] for kw in parsed], [True, False])
        self.assertEqual([kw['quota_slots'] for kw in parsed], [s7.MAX_WORKERS, s7.MAX_WORKERS])


_PATH_GLOBALS = ('PACK', 'DESIGN_DIR', 'VOICE_DIR', 'REFS_DIR', 'REFS_INDEX', 'GENERATION_DIR',
                 'SMOKE_DIR', 'KEY_FILE', 'ROLES')


def snapshot_paths():
    return {name: getattr(s7, name) for name in _PATH_GLOBALS} | {
        'load_refs_index_defaults': s7.load_refs_index.__defaults__}


def restore_paths(saved):
    for name in _PATH_GLOBALS:
        setattr(s7, name, saved[name])
    s7.load_refs_index.__defaults__ = saved['load_refs_index_defaults']


class PlanReportTests(unittest.TestCase):
    """`plan` 是改稿的人唯一的反馈面：逐角色报到底、每条问题带预算数字、有 error 就 rc≠0。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.saved = snapshot_paths()
        index = refs_index_v2(self.root)
        index['roles'].update(refs_index_v2(self.root, 'nicola')['roles'])
        index_path = self.root / 'refs-v2.json'
        index_path.write_text(json.dumps(index, ensure_ascii=False), encoding='utf-8')
        s7.load_refs_index.__defaults__ = (index_path,)
        s7.VOICE_DIR, s7.GENERATION_DIR = self.root, self.root / 'generation'
        s7.DESIGN_DIR = self.root / 'design'
        s7.ROLES = dict(fluffy=dict(cid='1', code='a', slots=['battle/outhole_0']),
                        nicola=dict(cid='2', code='b', slots=['battle/outhole_0']))

    def tearDown(self):
        restore_paths(self.saved)
        self.temp.cleanup()

    def design(self, role, **line):
        body = dict(slot='battle/outhole_0', ja='いたっ', zh='好痛', direction='短促')
        body.update(line)
        path = s7.DESIGN_DIR / f'{role}.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(voice=dict(prompt_version=2, persona='少女声。明亮。',
                                                   references='groups', lines=[body])),
                                   ensure_ascii=False), encoding='utf-8')

    def plan(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = s7.main(['plan', '--roles', 'fluffy', 'nicola', '--run', 'r1', '--prompt-version', '2'])
        rows = [json.loads(x) for x in out.getvalue().splitlines() if x.strip()]
        return rc, {r['role']: r for r in rows if 'status' in r}, [r for r in rows if 'level' in r]

    def test_a_broken_script_reports_every_problem_and_fails_the_exit_code(self):
        self.design('fluffy', ja='「いたっ」' + 'あ' * 14)      # 禁用符号 + 超字数预算
        self.design('nicola')                                   # 干净
        rc, summary, problems = self.plan()
        self.assertEqual(rc, 1)
        # 一个角色坏掉不许连累其它角色：11 个改稿代理各看各的。
        self.assertEqual(summary['nicola']['status'], 'ok')
        self.assertTrue(summary['nicola']['plan_written'])
        self.assertEqual(summary['fluffy']['status'], 'text_rules_failed')
        self.assertFalse(summary['fluffy']['plan_written'])
        self.assertGreaterEqual(summary['fluffy']['text_errors'], 2)
        # 输出形状保持稳定：老字段一个没少。
        for key in ('role', 'lines', 'slots', 'prompt_version', 'route', 'text_warnings'):
            self.assertIn(key, summary['fluffy'])
        rules = {p['rule'] for p in problems if p['role'] == 'fluffy'}
        self.assertLessEqual({'forbidden_symbol', 'over_char_budget'}, rules)
        budget = next(p for p in problems if p['rule'] == 'over_char_budget')
        self.assertEqual(budget['limit'], s7.char_budget('outhole_N')['hard_max'])
        self.assertTrue(budget['fix'] and budget['why'])
        # 有 error 的角色不写 plan 文件（别让人拿着坏稿子去 generate）。
        self.assertFalse((s7.GENERATION_DIR / 'r1' / 'plan' / 'fluffy.json').exists())
        self.assertTrue((s7.GENERATION_DIR / 'r1' / 'plan' / 'nicola.json').is_file())

    def test_a_clean_script_plans_and_returns_zero(self):
        self.design('fluffy')
        self.design('nicola')
        rc, summary, problems = self.plan()
        self.assertEqual(rc, 0)
        self.assertEqual({r['status'] for r in summary.values()}, {'ok'})
        self.assertEqual([p for p in problems if p['level'] == 'error'], [])

    def test_generate_stays_strict_even_though_plan_reports(self):
        self.design('fluffy', ja='「いたっ」')
        with self.assertRaisesRegex(ValueError, 'hard text rules'):
            s7.plan_role('fluffy')
        self.assertEqual(len(s7.plan_role('fluffy', strict_text=False)['text_errors']), 1)

    def test_a_blocked_role_is_reported_not_a_traceback(self):
        self.design('fluffy')
        self.design('nicola')
        index = json.loads((self.root / 'refs-v2.json').read_text(encoding='utf-8'))
        index['roles']['fluffy']['groups']['outhole'].update(seconds=0.2, range_ok=False)
        (self.root / 'refs-v2.json').write_text(json.dumps(index, ensure_ascii=False), encoding='utf-8')
        rc, summary, _problems = self.plan()
        self.assertEqual(rc, 1)
        self.assertEqual(summary['fluffy']['status'], 'blocked')
        self.assertIn('not fit to send', summary['fluffy']['problem'])
        self.assertEqual(summary['nicola']['status'], 'ok')


class SelectOutputTests(unittest.TestCase):
    def test_select_summary_counts_the_takes_with_no_text_verification(self):
        """空 subtitle 的槽只记 text_unverified；收口摘要必须看得见条数。"""
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'run'
            line = dict(role='fluffy', slot='battle/power_flip_0', ja='もう一つ！',
                        tts_text='もう一つ！', code='a')
            take_fixture(root, 1, line['slot'], subtitle=None, duration=1.0, seconds=1.0, raw_lufs=-18)
            summary = s7.select_takes([line], root, takes=[1])
            self.assertEqual(summary['text_unverified'], ['fluffy:battle/power_flip_0'])
            saved = (s7.VOICE_DIR, s7.GENERATION_DIR, s7._plans)
            s7.VOICE_DIR, s7.GENERATION_DIR = Path(temp), Path(temp)
            s7._plans = lambda args: [plan_stub(lines=[line])]
            try:
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    s7.main(['select', '--roles', 'fluffy', '--run', 'run', '--take', '1'])
            finally:
                (s7.VOICE_DIR, s7.GENERATION_DIR, s7._plans) = saved
            printed = json.loads(out.getvalue())
            self.assertEqual(printed['text_unverified'], 1)
            self.assertEqual(printed['text_unverified_slots'], ['fluffy:battle/power_flip_0'])


class MidautumnCliTests(unittest.TestCase):
    """rework2 的触发条件必须算上 select，否则它会静默指着第一轮的树选优。"""

    def setUp(self):
        self.saved = snapshot_paths()

    def tearDown(self):
        restore_paths(self.saved)

    def run_select(self, *args):
        try:
            MV.main(['select', '--roles', 'mia', *args])
        except BaseException as exc:                       # noqa: BLE001
            return exc
        return None

    def test_select_without_a_round_is_an_error_not_a_silent_fallback(self):
        with contextlib.redirect_stderr(io.StringIO()) as err:
            exc = self.run_select()
        self.assertIsInstance(exc, SystemExit)
        self.assertEqual(exc.code, 2)
        self.assertIn('必须显式指定轮次', err.getvalue())

    def test_an_explicit_round_picks_the_matching_generation_tree(self):
        self.run_select('--prompt-version', '2')
        self.assertTrue(s7.GENERATION_DIR.is_relative_to(MV.REWORK2))
        self.run_select('--prompt-version', '1')
        self.assertFalse(s7.GENERATION_DIR.is_relative_to(MV.REWORK2))

    def test_smoke_help_says_it_only_covers_template_v1(self):
        self.assertIn('只冒烟 prompt 模板 v1', s7.run_smoke.__doc__)
        parser_help = io.StringIO()
        with contextlib.redirect_stdout(parser_help), self.assertRaises(SystemExit):
            s7.main(['--help'])
        self.assertIn('只支持模板 v1', parser_help.getvalue())


def plan_stub(role='fluffy', **changes):
    plan = dict(role=role, design='x', lines=[v2_line(role=role, references=[])],
                slots=list(s7.SLOTS), prompt_version=2, text_warnings=[], text_errors=[], route=None)
    plan.update(changes)
    return plan


class CliExitCodeTests(unittest.TestCase):
    """退出码是分波次驱动脚本唯一看得见的信号 —— 错了就是「失败被吞成成功」。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.saved = (s7.VOICE_DIR, s7.GENERATION_DIR, s7._plans, s7.run_generation,
                      s7.process_run, s7._take_key, s7.find_tool)
        s7.VOICE_DIR, s7.GENERATION_DIR = self.root, self.root / 'generation'
        s7._take_key = lambda: 'k-secret-credential-value-01'
        s7._plans = lambda args: [plan_stub()]

    def tearDown(self):
        (s7.VOICE_DIR, s7.GENERATION_DIR, s7._plans, s7.run_generation,
         s7.process_run, s7._take_key, s7.find_tool) = self.saved
        self.temp.cleanup()

    def generate_rc(self, counts):
        s7.run_generation = lambda *a, **kw: dict(counts=counts, rewrite_queue=0,
                                                  needs_new_reference=[])
        with contextlib.redirect_stdout(io.StringIO()):
            return s7.main(['generate', '--roles', 'fluffy', '--run', 'r1'])

    def test_only_generated_and_cached_mean_success(self):
        for counts in ({'generated': 22}, {'cached': 22}, {'generated': 3, 'cached': 19}):
            with self.subTest(counts=counts):
                self.assertEqual(self.generate_rc(counts), 0)

    def test_any_failure_state_makes_the_exit_code_nonzero(self):
        # 真超集（`>`）写法下这三种全会报 0：{'generated','fatal'} 不是 {'generated','cached'}
        # 的真超集。第一轮 charlene 22/22 全 45001127 正是最后这种形状。
        for counts in ({'generated': 3, 'fatal': 1}, {'needs_rewrite': 22},
                       {'generated': 2, 'needs_new_reference': 2}, {'needs_new_reference': 22},
                       {'generated': 1, 'cached': 1, 'retry_exhausted': 1}, {'conflict': 1},
                       {'failed': 1}):
            with self.subTest(counts=counts):
                self.assertNotEqual(self.generate_rc(counts), 0)

    def process_rc(self, items, over_max=()):
        summary = dict(items=items, over_official_max=list(over_max), over_official_p90=[],
                       retake_candidates=[])
        s7.process_run = lambda *a, **kw: summary
        s7.find_tool = lambda name: Path(name)
        with contextlib.redirect_stdout(io.StringIO()):
            return s7.main(['process', '--roles', 'fluffy', '--run', 'r1'])

    def test_process_reports_qc_failures_through_the_exit_code(self):
        good = [dict(role='fluffy', slot='battle/power_flip_0', status='mastered')]
        self.assertEqual(self.process_rc(good), 0)
        for status in ('rejected', 'stale_plan', 'missing'):
            with self.subTest(status=status):
                bad = [dict(role='fluffy', slot='battle/power_flip_0', status=status)]
                self.assertNotEqual(self.process_rc(bad), 0)
        self.assertNotEqual(self.process_rc(good, over_max=['fluffy:battle/power_flip_0']), 0)


def write_wav(path: Path, samples: np.ndarray, rate: int = 48000):
    frames = (np.clip(samples, -1, 1) * 32767).astype('<i2')
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), 'wb') as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(frames.tobytes())


def burst(lead: float, body: float, tail: float, rate: int = 48000, level: float = 0.2):
    t = np.arange(int(body * rate)) / rate
    tone = level * np.sin(2 * np.pi * 220 * t) * np.hanning(len(t))
    return np.concatenate([np.zeros(int(lead * rate)), tone, np.zeros(int(tail * rate))])


@unittest.skipUnless(HAVE_FFMPEG, 'local ffmpeg unavailable')
class EdgeTrimTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_head_keeps_100ms_and_tail_keeps_150ms(self):
        source = self.root / 'raw.wav'
        write_wav(source, burst(1.28, 0.70, 0.40))
        start, end = s7.edge_bounds(source, ffmpeg=FFMPEG)
        # 夹具是加窗正弦，两端各有几十毫秒渐弱落在判活阈值下 ⇒ 用区间而不是点值。
        self.assertLessEqual(start, 1.28 - 0.10 + 0.06)       # 留够 100ms 头
        self.assertGreaterEqual(start, 1.28 - 0.10 - 0.02)    # 但不多留
        self.assertGreaterEqual(end, 1.28 + 0.70 - 0.06)      # 正文不被切掉
        self.assertLessEqual(end, 1.28 + 0.70 + 0.15 + 0.02)  # 尾巴最多留 150ms
        self.assertLess(end - start, 1.28 + 0.70 + 0.40)

    def test_leading_silence_shorter_than_the_pad_is_not_cut_below_zero(self):
        source = self.root / 'tight.wav'
        write_wav(source, burst(0.02, 0.60, 0.02))
        start, end = s7.edge_bounds(source, ffmpeg=FFMPEG)
        self.assertEqual(start, 0.0)
        self.assertAlmostEqual(end, 0.64, delta=0.05)

    def test_silence_is_refused_rather_than_trimmed_to_nothing(self):
        source = self.root / 'silent.wav'
        write_wav(source, np.zeros(48000))
        with self.assertRaisesRegex(ValueError, 'silent generated audio'):
            s7.edge_bounds(source, ffmpeg=FFMPEG)

    def test_trim_policy_is_battle_only(self):
        self.assertTrue(s7.master_policy('battle/power_flip_0', 2)['trim'])
        self.assertTrue(s7.master_policy('battle/win_0', 2)['trim'])
        self.assertFalse(s7.master_policy('home/home_0', 2)['trim'])
        self.assertFalse(s7.master_policy('ally/join', 2)['trim'])
        self.assertEqual(s7.master_policy('battle/power_flip_0', 1), dict(mode='fixed_gain', trim=False))


@unittest.skipUnless(HAVE_FFMPEG, 'local ffmpeg unavailable')
class TwoPassMasteringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_quiet_burst_reaches_target_and_records_the_cut(self):
        source = self.root / 'raw.wav'
        write_wav(source, burst(0.9, 1.0, 0.5, level=0.02))
        target = self.root / 'standard' / 'power_flip_0.mp3'
        stored, report = s7.master_voice(source, target, slot='battle/power_flip_0', code='fixture',
                                         ffmpeg=FFMPEG, ffprobe=FFPROBE, mode='two_pass', trim=True)
        self.assertLessEqual(abs(report['final']['lufs_i'] - s7.TARGET_LUFS), 0.6)
        self.assertLessEqual(report['final']['true_peak_dbtp'], s7.PEAK_CEILING)
        self.assertLessEqual(report['limiter_reduction_bound_db'], s7.SAFETY_LIMITER_REDUCTION_DB + 1e-6)
        self.assertGreater(report['trim']['removed_seconds'], 0.9)
        self.assertLess(report['seconds'], 2.4)
        self.assertFalse(report['no_trim_no_speed_no_concatenation'])
        self.assertTrue(report['no_speed_no_concatenation'])
        self.assertEqual(report['params']['mode'], 'two_pass')
        self.assertIn('edge_trim', report['params'])
        self.assertEqual(wf_assets.mp3_decode(stored), target.read_bytes())
        self.assertLess(report['mastered_pcm']['leading_quiet_seconds'], 0.16)

    def test_untrimmed_long_slot_keeps_every_sample(self):
        source = self.root / 'long.wav'
        write_wav(source, burst(0.6, 8.5, 0.6, level=0.05))
        _stored, report = s7.master_voice(source, self.root / 'o' / 'home_0.mp3', slot='home/home_0',
                                          code='fixture', ffmpeg=FFMPEG, ffprobe=FFPROBE,
                                          mode='two_pass', trim=False)
        self.assertIsNone(report['trim'])
        self.assertTrue(report['no_trim_no_speed_no_concatenation'])
        self.assertLessEqual(abs(report['sample_delta']), s7.SAMPLE_DELTA_LIMIT)
        self.assertLess(abs(report['raw_lufs_i'] - report['baseline_encoded']['lufs_i']), 40)

    def test_master_params_track_the_policy_so_qc_drift_is_detectable(self):
        self.assertEqual(s7.master_params(), s7.MASTER_PARAMS)
        self.assertNotEqual(s7.master_params(mode='two_pass', trim=True), s7.MASTER_PARAMS)
        self.assertNotEqual(s7.master_params(mode='two_pass', trim=True),
                            s7.master_params(mode='two_pass', trim=False))


class LimiterBoundTests(unittest.TestCase):
    """限幅上界只许钳一次：两遍 loudnorm 走安全网 2 dB，定增益仍是 4 dB。"""

    def test_two_pass_is_clamped_and_fixed_gain_is_not(self):
        self.assertEqual(s7.limiter_bound('two_pass'), s7.SAFETY_LIMITER_REDUCTION_DB)
        self.assertEqual(s7.limiter_bound('fixed_gain'), s7.MAX_LIMITER_REDUCTION_DB)
        # 比安全网还严的显式上界不被放宽。
        self.assertEqual(s7.limiter_bound('two_pass', 1.0), 1.0)

    def test_master_params_report_the_clamped_bound(self):
        for trim in (False, True):
            params = s7.master_params(mode='two_pass', trim=trim)
            self.assertEqual(params['max_limiter_reduction_db'], s7.SAFETY_LIMITER_REDUCTION_DB)
            # 显式传未钳的 4.0（master_voice 的入参默认值）不能算出另一份参数。
            self.assertEqual(s7.master_params(mode='two_pass', trim=trim,
                                              max_limiter_reduction_db=s7.MAX_LIMITER_REDUCTION_DB),
                             params)
        self.assertEqual(s7.master_params(**s7.master_policy('battle/power_flip_0', 1)),
                         s7.MASTER_PARAMS)


@unittest.skipUnless(HAVE_FFMPEG, 'local ffmpeg unavailable')
class ProcessResumeTests(unittest.TestCase):
    """第二遍 `process` 必须命中缓存：报告里的参数与续跑重算的期望参数得逐字相同。

    曾经 `process_run` 按 `master_params(**policy)` 算出 4 dB、`master_voice` 写进报告的
    是钳过的 2 dB ⇒ 缓存分支恒抛「QC drift…use a new run directory」，把补抽流程逼成
    重开 run 目录重新生成（= 重复计费）。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.temp.name) / 'takes' / '01'
        self.line = v2_line(slot='battle/power_flip_0', code='fixture_code')
        base = self.run_dir / self.line['role']
        source = base / 'raw' / (self.line['slot'] + '.wav')
        write_wav(source, burst(0.9, 1.0, 0.5, level=0.05))
        receipt = base / 'receipts' / (self.line['slot'] + '.json')
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(json.dumps(dict(status='generated', sha256=s7.sha(source.read_bytes()),
                                           request_fingerprint=s7.request_fingerprint(self.line))),
                           encoding='utf-8')
        self.qc = base / 'qc' / (self.line['slot'] + '.json')

    def tearDown(self):
        self.temp.cleanup()

    def process(self):
        return s7.process_run([self.line], self.run_dir, ffmpeg=FFMPEG, ffprobe=FFPROBE, version=2)

    def test_second_pass_is_cached_instead_of_a_false_drift(self):
        self.assertEqual([x['status'] for x in self.process()['items']], ['mastered'])
        self.assertEqual([x['status'] for x in self.process()['items']], ['cached'])
        self.assertEqual([x['status'] for x in self.process()['items']], ['cached'])

    def test_recorded_params_equal_what_the_resume_recomputes(self):
        self.process()
        report = json.loads(self.qc.read_bytes())
        self.assertEqual(report['params'], s7.master_params(**s7.master_policy(self.line['slot'], 2)))
        self.assertEqual(report['params']['max_limiter_reduction_db'], s7.SAFETY_LIMITER_REDUCTION_DB)

    def test_genuine_drift_still_refuses_to_reuse_the_report(self):
        self.process()
        report = json.loads(self.qc.read_bytes())
        report['params'] = dict(report['params'], max_limiter_reduction_db=s7.MAX_LIMITER_REDUCTION_DB)
        self.qc.write_text(json.dumps(report), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'QC drift'):
            self.process()

    def test_summary_params_follow_the_lines_when_no_version_is_passed(self):
        """lines 自带 v2 而命令行没写 --prompt-version 时，摘要不能写成 v1 的定增益参数。"""
        summary = s7.process_run([self.line], self.run_dir, ffmpeg=FFMPEG, ffprobe=FFPROBE)
        self.assertEqual(summary['effective_prompt_version'], 2)
        self.assertEqual(summary['params'], 'per-slot; see each qc report')
        self.assertEqual(json.loads(self.qc.read_bytes())['params']['mode'], 'two_pass')
        written = json.loads((self.run_dir / 'qc-summary.json').read_bytes())
        self.assertEqual(written['params'], 'per-slot; see each qc report')
        # v1 的 line 仍然写 MASTER_PARAMS，旧行为一字不动。
        v1 = s7.process_run([dict(self.line, prompt_version=1)], self.run_dir / 'nothing-here',
                            ffmpeg=FFMPEG, ffprobe=FFPROBE)
        self.assertEqual(v1['params'], s7.MASTER_PARAMS)


@unittest.skipUnless(HAVE_FFMPEG, 'local ffmpeg unavailable')
class ReferenceLevelTests(unittest.TestCase):
    """极短参考音的电平：loudnorm 在 <0.4s 上拿不到测量值 ⇒ 一点增益都没加。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_strip_loudnorm_leaves_the_rest_of_the_chain_intact(self):
        bare = s7.strip_loudnorm(s7.REF_FILTERS_V2)
        self.assertNotIn('loudnorm', bare)
        self.assertIn('highpass=f=70', bare)
        self.assertIn('silenceremove', bare)
        self.assertFalse(bare.startswith(',') or bare.endswith(',') or ',,' in bare)
        self.assertEqual(s7.strip_loudnorm(s7.REF_FILTERS_V2_KEEP_LEVEL), s7.REF_FILTERS_V2_KEEP_LEVEL)
        self.assertEqual(s7.strip_loudnorm('loudnorm=I=-16:TP=-1.5:LRA=11'), '')

    def test_short_clip_loudnorm_is_a_no_op_and_rms_fixes_it(self):
        source = self.root / 'short.wav'
        write_wav(source, burst(0.02, 0.30, 0.02, level=0.35))
        target = self.root / 'short.ref.wav'
        info = s7.clean_reference_file(source, target, ffmpeg=FFMPEG, filters=s7.REF_FILTERS_V2)
        self.assertLess(info['duration_seconds'], s7.SHORT_REFERENCE_SECONDS)
        # 先证明病灶确实在：整合响度是测不出的下限，不是真实电平。
        self.assertLessEqual(s7.measure(target, FFMPEG)['lufs_i'], s7.LOUDNESS_UNMEASURABLE_LUFS)
        loud = s7.pcm_levels(target, ffmpeg=FFMPEG)
        result = s7.rms_normalize_reference(source, target, ffmpeg=FFMPEG, filters=s7.REF_FILTERS_V2)
        self.assertAlmostEqual(result['levels']['rms_dbfs'], s7.REFERENCE_TARGET_RMS_DBFS, delta=0.3)
        self.assertLessEqual(result['levels']['peak_dbfs'], s7.REFERENCE_PEAK_CEILING_DBFS + 0.05)
        self.assertNotAlmostEqual(loud['rms_dbfs'], result['levels']['rms_dbfs'], delta=0.3)

    def test_the_peak_ceiling_wins_when_the_crest_factor_is_large(self):
        """定增益不能把尖峰推过天花板：短喊声的波峰因数常常大过 RMS 目标留的余量。"""
        source = self.root / 'crest.wav'
        body = burst(0.02, 0.30, 0.02, level=0.02)
        body[len(body) // 2] = 0.95                        # 一个接近满刻度的尖峰
        write_wav(source, body)
        result = s7.rms_normalize_reference(source, self.root / 'crest.ref.wav',
                                            ffmpeg=FFMPEG, filters=s7.REF_FILTERS_V2)
        self.assertLessEqual(result['levels']['peak_dbfs'], s7.REFERENCE_PEAK_CEILING_DBFS + 0.05)
        # 被峰值钳住 ⇒ RMS 到不了目标；这正是「宁可欠响也不削波」。
        self.assertLess(result['levels']['rms_dbfs'], s7.REFERENCE_TARGET_RMS_DBFS - 1.0)
        self.assertLess(result['gain_db'], s7.REFERENCE_TARGET_RMS_DBFS - result['before']['rms_dbfs'])

    def build(self, sources, **spec):
        specs = {'fixture': dict(kind='test', note='', filters=s7.REF_FILTERS_V2,
                                 groups={name: dict(source=str(path), range=rng)
                                         for name, (path, rng) in sources.items()},
                                 slot_to_group={'battle/power_flip_0': 'pf'}, **spec)}
        return s7.build_references_v2(specs, out_dir=self.root / 'refs', ffmpeg=FFMPEG,
                                      index_path=self.root / 'refs' / 'refs-v2.json')

    def test_index_records_which_ruler_measured_each_reference(self):
        short, long = self.root / 's.wav', self.root / 'l.wav'
        write_wav(short, burst(0.02, 0.30, 0.02, level=0.35))
        write_wav(long, burst(0.05, 1.20, 0.05, level=0.20))
        index = self.build({'pf': (short, (0.5, 2.5)), 'ready': (long, (0.5, 2.5))})
        groups = index['roles']['fixture']['groups']
        self.assertEqual(groups['ready']['loudness_method'], 'ebu_r128')
        self.assertTrue(groups['ready']['loudness_measurable'])
        self.assertEqual(groups['pf']['loudness_method'], 'rms')
        self.assertFalse(groups['pf']['loudness_measurable'])
        # 测不出时不再把 -70 当电平写进 lufs_i；原始读数另存，真实电平看 rms_dbfs。
        self.assertIsNone(groups['pf']['lufs_i'])
        self.assertLessEqual(groups['pf']['lufs_i_raw'], s7.LOUDNESS_UNMEASURABLE_LUFS)
        self.assertAlmostEqual(groups['pf']['rms_dbfs'], s7.REFERENCE_TARGET_RMS_DBFS, delta=0.3)
        self.assertIn('rms_gain_db', groups['pf'])
        # 区间外（0.30s < 0.5s）仍然算缺陷，而且没豁免 ⇒ 进 blocking。
        self.assertEqual([v['group'] for v in index['roles']['fixture']['blocking']], ['pf'])
        with self.assertRaises(ValueError):
            s7.resolve_references('fixture', None, index, slot='battle/power_flip_0')

    def test_a_reason_in_the_role_policy_is_what_clears_the_gate(self):
        short = self.root / 's.wav'
        write_wav(short, burst(0.02, 0.30, 0.02, level=0.35))
        index = self.build({'pf': (short, (0.5, 2.5))}, exemptions={'pf': '库里只有这一条'})
        self.assertEqual(index['roles']['fixture']['blocking'], [])
        self.assertEqual([v['exempted'] for v in index['roles']['fixture']['violations']], [True])
        self.assertEqual(len(s7.resolve_references('fixture', None, index, slot='battle/power_flip_0')), 1)
        with self.assertRaisesRegex(ValueError, 'unknown groups'):
            self.build({'pf': (short, (0.5, 2.5))}, exemptions={'nope': '打错了'})


class QuotePolicyTests(unittest.TestCase):
    """表演指导里引的台词片段会被模型抢到句首念出来：逐条 opt-in 换成位置指代。"""

    JA = '月が高い。積み荷を縛り直して、出る。'
    TTS = '月が高い。積み荷をしばり直して、出る。'

    def test_fragments_become_positions_and_no_line_text_survives(self):
        direction = '低い声で。「月が高い」语速偏快。重音在「縛り」，「出る」短、平。引的不是台词的「ほかの言葉」和「重点」。'
        out = s7.neutralize_quotes(direction, (self.JA, self.TTS))
        self.assertEqual(out, '低い声で。第一句语速偏快。重音在最后一句中段，最后一句句尾短、平。引的不是台词的该处和重点。')
        for fragment in ('月が高い', '縛り', 'しばり', '出る', 'ほかの言葉'):
            self.assertNotIn(fragment, out)

    def test_reading_override_is_matched_through_the_tts_form(self):
        self.assertEqual(s7.quote_reference('しばり直して', (self.JA, self.TTS)), '最后一句中段')
        self.assertEqual(s7.quote_reference('もう、ひとつ', ('モウヒトツ！',)), '这句')   # 片假名/标点不影响
        self.assertEqual(s7.quote_reference('高い。積み荷', (self.JA,)), '第一句后半到最后一句')
        self.assertEqual(s7.quote_reference('もう一つ', ('もう一つ！',)), '这句')
        self.assertIsNone(s7.quote_reference('別の台詞', (self.JA,)))

    def test_inline_fragments_without_brackets(self):
        ja = '金木犀、気づきました？三日前から匂ってます。今日は、歩いて来ました。……遠回りして。'
        direction = '开头金木犀像刚想起来一样轻轻抛出，気づきました？尾音上挑。今日は、歩いて来ました重音落在歩いて。最后遠回りして压到最轻。'
        out = s7.neutralize_inline(direction, (ja,))
        self.assertEqual(out, '开头第一句开头像刚想起来一样轻轻抛出，第一句句尾尾音上挑。第3句重音落在第3句中段。最后最后一句压到最轻。')
        self.assertFalse(s7._HAS_KANA.search(out))

    def test_inline_leaves_kanji_stubs_and_chinese_alone(self):
        ja = '全員から一口、借りる。'
        out = s7.neutralize_inline('一口气说完，重音落在一口，借りる尾音不落死。', (ja,))
        self.assertEqual(out, '一口气说完，重音落在一口，这句句尾尾音不落死。')     # 「一口气」不能被换坏
        performance, _tone = s7.compose_performance('重音落在一口，借りる轻收。', 'battle/skill_0',
                                                    quote_policy='positional_inline', spoken_forms=(ja,))
        self.assertNotIn('借りる', performance)

    def test_policy_is_per_line_and_the_default_keeps_old_fingerprints(self):
        direction = '重音在「縛り」。'
        old, _tone = s7.compose_performance(direction, 'battle/win_1')
        self.assertIn('縛り', old)                                            # 默认 = 本轮已生成 take 的原样
        new, _tone = s7.compose_performance(direction, 'battle/win_1', quote_policy='positional',
                                            spoken_forms=(self.JA, self.TTS))
        self.assertNotIn('縛り', new)
        self.assertIn('最后一句中段', new)
        with self.assertRaisesRegex(ValueError, 'quote_policy'):
            s7.compose_performance(direction, 'battle/win_1', quote_policy='nope')


def take_fixture(root: Path, take: int, slot: str, *, subtitle, duration, seconds, raw_lufs,
                 lufs=-14.1, limiter=0.4, lead_ms=100, role='fluffy'):
    base = s7.take_dir(root, take) / role
    standard = base / 'standard' / (slot + '.mp3')
    standard.parent.mkdir(parents=True, exist_ok=True)
    standard.write_bytes(f'audio-{take}-{slot}'.encode())
    words = None
    if subtitle is not None:
        words = [dict(text=subtitle, start_time=lead_ms, end_time=int(duration * 1000) - 50)]
    receipt = dict(status='generated', response=dict(
        duration=duration,
        subtitle=dict(text=subtitle or '', sentences=[dict(words=words)] if words else [])))
    (base / 'receipts' / (slot + '.json')).parent.mkdir(parents=True, exist_ok=True)
    (base / 'receipts' / (slot + '.json')).write_text(json.dumps(receipt, ensure_ascii=False),
                                                      encoding='utf-8')
    qc = dict(standard_sha256=s7.sha(standard.read_bytes()), seconds=seconds, raw_lufs_i=raw_lufs,
              final=dict(lufs_i=lufs, true_peak_dbtp=-1.8), limiter_reduction_bound_db=limiter,
              mastered_pcm=dict(clipped_fraction=0.0),
              source_pcm=dict(seconds=duration, leading_quiet_seconds=lead_ms / 1000.0,
                              trailing_quiet_seconds=0.05))
    (base / 'qc' / (slot + '.json')).parent.mkdir(parents=True, exist_ok=True)
    (base / 'qc' / (slot + '.json')).write_text(json.dumps(qc), encoding='utf-8')
    return standard


class SelectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'run'
        self.line = dict(role='fluffy', slot='battle/power_flip_0', ja='もう一つ！',
                         tts_text='もう一つ！', code='a')

    def tearDown(self):
        self.temp.cleanup()

    def test_picks_the_take_closest_to_the_official_median(self):
        take_fixture(self.root, 1, 'battle/power_flip_0', subtitle='もう一つ！', duration=1.4,
                     seconds=1.38, raw_lufs=-18.0)
        take_fixture(self.root, 2, 'battle/power_flip_0', subtitle='もう一つ！', duration=1.1,
                     seconds=1.07, raw_lufs=-18.0)
        summary = s7.select_takes([self.line], self.root)
        chosen = summary['roles']['fluffy']['battle/power_flip_0']
        self.assertEqual(chosen['take'], 2)                   # p50 = 1.07
        self.assertEqual(chosen['alternatives'], 1)
        self.assertEqual(summary['retake'], 0)
        self.assertTrue(Path(chosen['standard']).is_file())

    def test_inserted_words_and_long_lead_in_are_dropped(self):
        take_fixture(self.root, 1, 'battle/power_flip_0', subtitle='散れもう一つ！', duration=1.2,
                     seconds=1.05, raw_lufs=-18.0)
        take_fixture(self.root, 2, 'battle/power_flip_0', subtitle='もう一つ！', duration=1.9,
                     seconds=1.05, raw_lufs=-18.0, lead_ms=1280)
        summary = s7.select_takes([self.line], self.root)
        self.assertEqual(summary['retake'], 1)
        reasons = summary['retake_queue'][0]['reasons']
        self.assertIn('text_superset', reasons)
        self.assertIn('lead_in', reasons)
        self.assertEqual(summary['retake_queue'][0]['action'], '改台词（插词/超长）')

    def test_katakana_and_punctuation_differences_are_harmless(self):
        take_fixture(self.root, 1, 'battle/power_flip_0', subtitle='モウ一ツ', duration=1.1,
                     seconds=1.05, raw_lufs=-18.0)
        summary = s7.select_takes([self.line], self.root)
        self.assertEqual(summary['retake'], 0)

    def test_missing_subtitle_falls_back_to_pcm_and_ranks_last(self):
        take_fixture(self.root, 1, 'battle/power_flip_0', subtitle=None, duration=1.1,
                     seconds=1.07, raw_lufs=-18.0)
        summary = s7.select_takes([self.line], self.root)
        chosen = summary['roles']['fluffy']['battle/power_flip_0']
        self.assertTrue(chosen['text_unverified'])
        self.assertEqual(summary['text_unverified'], ['fluffy:battle/power_flip_0'])
        take_fixture(self.root, 2, 'battle/power_flip_0', subtitle='もう一つ！', duration=1.6,
                     seconds=1.5, raw_lufs=-18.0)
        summary = s7.select_takes([self.line], self.root)
        chosen = summary['roles']['fluffy']['battle/power_flip_0']
        self.assertEqual(chosen['take'], 2)                   # 可验证的优先，哪怕分数更差
        self.assertFalse(chosen['text_unverified'])
        self.assertGreater(chosen['score'],
                           s7.take_score(self.line, dict(dead_air_share=0.1, max_inner_gap_seconds=0.0),
                                         dict(seconds=1.07, limiter_reduction_bound_db=0.4)))

    def test_pcm_lead_in_still_blocks_a_take_without_subtitle(self):
        take_fixture(self.root, 1, 'battle/power_flip_0', subtitle=None, duration=2.0,
                     seconds=1.07, raw_lufs=-18.0, lead_ms=1280)
        summary = s7.select_takes([self.line], self.root)
        self.assertEqual(summary['retake'], 1)
        self.assertIn('lead_in', summary['retake_queue'][0]['reasons'])

    def test_bad_master_is_dropped_and_quiet_source_is_not(self):
        take_fixture(self.root, 1, 'battle/power_flip_0', subtitle='もう一つ！', duration=1.1,
                     seconds=1.07, raw_lufs=-25.6)             # recipe 的 -20 会丢掉它
        summary = s7.select_takes([self.line], self.root)
        self.assertEqual(summary['retake'], 0)
        take_fixture(self.root, 2, 'battle/power_flip_0', subtitle='もう一つ！', duration=1.1,
                     seconds=1.07, raw_lufs=-30.0)
        take_fixture(self.root, 3, 'battle/power_flip_0', subtitle='もう一つ！', duration=1.1,
                     seconds=1.07, raw_lufs=-18.0, limiter=3.5)
        summary = s7.select_takes([self.line], self.root)
        by_take = {r['take']: r['failed'] for r in _all_records(summary, 'battle/power_flip_0')}
        self.assertIn('raw_loudness', by_take.get(2, []))
        self.assertIn('limiter_reduction', by_take.get(3, []))

    def test_partial_retake_round_does_not_break_the_other_slots(self):
        """补抽轮只有被补抽的槽位：别的槽位在该 take 下缺文件，select 不能崩，也不能把 missing 当成毛病。"""
        other = dict(self.line, slot='battle/power_flip_1')
        take_fixture(self.root, 1, 'battle/power_flip_0', subtitle='もう一つ！', duration=1.1,
                     seconds=1.07, raw_lufs=-18.0)
        take_fixture(self.root, 1, 'battle/power_flip_1', subtitle='散れもう一つ！', duration=1.2,
                     seconds=1.05, raw_lufs=-18.0)             # 插词 -> 进补抽队列
        take_fixture(self.root, 4, 'battle/power_flip_1', subtitle='散れもう一つ！', duration=1.2,
                     seconds=1.05, raw_lufs=-18.0)             # 补抽了还是插词；take 4 没有 power_flip_0
        summary = s7.select_takes([self.line, other], self.root)
        chosen = summary['roles']['fluffy']['battle/power_flip_0']
        self.assertEqual(chosen['take'], 1)
        self.assertEqual(chosen['rejected'], [dict(take=4, failed=['missing'], score=None,
                                                   seconds=None, raw_lufs_i=None)])
        self.assertEqual(summary['retake_queue'][0]['reasons'], ['text_superset'])
        take_fixture(self.root, 5, 'battle/power_flip_1', subtitle='もう一つ！', duration=1.1,
                     seconds=1.07, raw_lufs=-18.0)
        summary = s7.select_takes([self.line, other], self.root)
        self.assertEqual(summary['retake'], 0)
        self.assertEqual(summary['roles']['fluffy']['battle/power_flip_1']['take'], 5)

    def test_inner_gap_limit_follows_the_official_p90_by_length(self):
        self.assertEqual(s7.inner_gap_limit(1.2, 'そこだ。'), 0.35)
        self.assertEqual(s7.inner_gap_limit(2.0, '間合いは、俺が詰める。'), 0.45)
        self.assertEqual(s7.inner_gap_limit(2.8, '近寄るな。焦げても知らんぞ。'), 0.60)
        self.assertEqual(s7.inner_gap_limit(1.2, '……そこだ。'), 0.90)
        self.assertEqual(s7.inner_gap_limit(2.2, 'ざ——いえ、後で。'), 0.90)
        line = dict(self.line, slot='battle/skill_2', ja='近寄るな。焦げても知らんぞ。',
                    tts_text='近寄るな。焦げても知らんぞ。')
        metrics = dict(subtitle_present=True, text_exact=True, text_superset=False, lead_in_seconds=0.1,
                       tail_seconds=0.06, max_inner_gap_seconds=0.56, dead_air_share=0.05)
        qc = dict(seconds=2.82, raw_lufs_i=-20.0, final=dict(lufs_i=-14.0, true_peak_dbtp=-1.5),
                  limiter_reduction_bound_db=0.4, mastered_pcm=dict(clipped_fraction=0.0))
        self.assertNotIn('inner_gap', s7.take_gates(line, metrics, qc))
        self.assertIn('inner_gap', s7.take_gates(line, dict(metrics, max_inner_gap_seconds=0.64), qc))
        self.assertIn('inner_gap', s7.take_gates(line, metrics, dict(qc, seconds=2.2)))

    def test_over_official_max_is_always_fatal(self):
        take_fixture(self.root, 1, 'battle/power_flip_0', subtitle='もう一つ！', duration=3.4,
                     seconds=3.30, raw_lufs=-18.0)
        summary = s7.select_takes([self.line], self.root)
        self.assertEqual(summary['retake_queue'][0]['reasons'], ['over_official_max'])

    def test_pack_reads_the_selected_recording_and_catches_drift(self):
        standard = take_fixture(self.root, 1, 'battle/power_flip_0', subtitle='もう一つ！',
                                duration=1.1, seconds=1.07, raw_lufs=-18.0)
        s7.select_takes([self.line], self.root)
        picked = s7.selected_standard(self.root, 'fluffy', ['battle/power_flip_0'])
        self.assertEqual(picked['battle/power_flip_0'], standard.read_bytes())
        standard.write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'drifted from its QC'):
            s7.selected_standard(self.root, 'fluffy', ['battle/power_flip_0'])
        with self.assertRaisesRegex(ValueError, 'lacks 1 slot'):
            s7.selected_standard(self.root, 'fluffy', ['battle/win_0'])


def _all_records(summary, slot):
    out = []
    for items in summary['roles'].values():
        if slot in items:
            out.append(items[slot])
            out += items[slot]['rejected']
    for entry in summary['retake_queue']:
        if entry['slot'] == slot:
            out += entry['takes']
    return out


def peaky(lead: float, body: float, tail: float, rate: int = 48000, level: float = 0.05,
          spike: float = 0.9, spikes: int = 3, spike_ms: float = 20.0):
    """安静的正文 + 几个短促强音节：峰均比高得像凯尔的原始音（实测 18~22 dB）。

    凯尔 raw 中位 -20.1 LUFS、峰值 -1.8 dBFS ⇒ 峰均比约 18 dB，官方成品只有 12~13 dB。
    两遍 loudnorm 的 linear=true 不做动态处理，增益被 TP 钉死 ⇒ 成品响度 ≈ TP目标 - 峰均比，
    所以「轻」的根因是峰均比，不是限幅上界。

    强音节要用加窗正弦（几十毫秒）而不是直流脉冲：1 ms 的方波尖峰任何压缩器都咬不住，
    那种夹具测的是 ffmpeg 的起音极限，不是本管线的行为。
    """
    t = np.arange(int(body * rate)) / rate
    tone = np.sin(2 * np.pi * 220 * t)
    envelope = np.full(len(t), level)
    width = max(2, int(spike_ms * rate / 1000))
    for i in range(spikes):
        at = int((i + 1) * len(t) / (spikes + 1))
        envelope[at:at + width] = np.maximum(level, spike * np.hanning(width))
    return np.concatenate([np.zeros(int(lead * rate)), tone * envelope, np.zeros(int(tail * rate))])


class LoudnessBandTests(unittest.TestCase):
    """成品响度闸门只许有一处数字：`loudness_verdict`。

    以前 `master_voice` 用 ±LOUDNESS_TOLERANCE(1.0) 写 `loudness_status`、`take_gates` 用
    ±0.5 判 `master_loudness`，于是 QC 报告写着 ok 的条目照样被选优丢掉。
    """

    def test_band_matches_the_measured_official_distribution(self):
        low, high = s7.MASTER_LOUDNESS_BAND
        self.assertEqual((low, high), (-15.0, -12.8))
        # 官方各族 p10 最低 -14.9（join）、p90 最高 -12.0（power_flip_0）：带子必须把它们包住，
        # 又不能宽到把 -16 这种听得出来的轻放进来。
        self.assertLess(low, -14.9)
        self.assertGreater(high, -13.2)
        self.assertGreater(low, -16.0)
        self.assertLess(s7.TARGET_LUFS, high)
        self.assertGreater(s7.TARGET_LUFS, low)

    def test_verdict_edges(self):
        self.assertEqual(s7.loudness_verdict(-14.0), 'ok')
        self.assertEqual(s7.loudness_verdict(-15.0), 'ok')
        self.assertEqual(s7.loudness_verdict(-12.8), 'ok')
        self.assertEqual(s7.loudness_verdict(-15.01), 'under_target')
        self.assertEqual(s7.loudness_verdict(-12.79), 'over_target')
        self.assertEqual(s7.loudness_verdict(None), 'unmeasured')

    def test_take_gates_read_the_same_function_and_not_a_second_number(self):
        line = dict(role='fluffy', slot='battle/power_flip_0', ja='もう一つ！', tts_text='もう一つ！')
        metrics = dict(subtitle_present=True, text_exact=True, text_superset=False,
                       lead_in_seconds=0.1, tail_seconds=0.1, max_inner_gap_seconds=0.0,
                       dead_air_share=0.1)
        for lufs in (-14.0, -14.6, -15.0, -15.3, -12.9, -12.5, -18.0):
            qc = dict(seconds=1.07, raw_lufs_i=-18.0, final=dict(lufs_i=lufs, true_peak_dbtp=-1.8),
                      limiter_reduction_bound_db=0.4, mastered_pcm=dict(clipped_fraction=0.0))
            failed = s7.take_gates(line, metrics, qc)
            with self.subTest(lufs=lufs):
                self.assertEqual('master_loudness' in failed,
                                 s7.loudness_verdict(lufs) != 'ok')
        # 闸门不见了也要红：合格带外的一条必须仍然被拦。
        self.assertIn('master_loudness', s7.take_gates(
            line, metrics, dict(seconds=1.07, raw_lufs_i=-18.0,
                                final=dict(lufs_i=-17.0, true_peak_dbtp=-1.8),
                                limiter_reduction_bound_db=0.4,
                                mastered_pcm=dict(clipped_fraction=0.0))))

    def test_limiter_gate_uses_the_bound_the_report_was_made_under(self):
        line = dict(role='fluffy', slot='battle/power_flip_0', ja='あ', tts_text='あ')
        metrics = dict(subtitle_present=False, text_exact=False, text_superset=False,
                       lead_in_seconds=0.1, tail_seconds=0.1, max_inner_gap_seconds=0.0,
                       dead_air_share=0.1)

        def gate_for(params, reduction):
            qc = dict(seconds=1.07, raw_lufs_i=-18.0, final=dict(lufs_i=-14.0, true_peak_dbtp=-1.8),
                      limiter_reduction_bound_db=reduction, mastered_pcm=dict(clipped_fraction=0.0),
                      params=params)
            return s7.take_gates(line, metrics, qc)

        two_pass = s7.master_params(**s7.master_policy('battle/power_flip_0', 2))
        self.assertNotIn('limiter_reduction', gate_for(two_pass, s7.SAFETY_LIMITER_REDUCTION_DB))
        self.assertIn('limiter_reduction', gate_for(two_pass, s7.SAFETY_LIMITER_REDUCTION_DB + 0.2))
        # v1 定增益的报告本来就允许 4 dB，不能套两遍 loudnorm 的安全网。
        self.assertNotIn('limiter_reduction', gate_for(s7.MASTER_PARAMS, 3.5))
        self.assertIn('limiter_reduction', gate_for(s7.MASTER_PARAMS, 4.2))
        # 没记 params 的旧报告回落到最严的那个数。
        self.assertIn('limiter_reduction', gate_for(None, 3.5))


class DensityLadderTests(unittest.TestCase):
    def test_ladder_is_monotone_from_light_to_firm(self):
        names = [s['name'] for s in s7.DENSITY_STAGES]
        self.assertEqual(names, ['light', 'medium', 'firm'])
        ratios = [s['ratio'] for s in s7.DENSITY_STAGES]
        thresholds = [s['threshold_below_peak_db'] for s in s7.DENSITY_STAGES]
        attacks = [s['attack_ms'] for s in s7.DENSITY_STAGES]
        self.assertEqual(ratios, sorted(ratios))
        self.assertEqual(thresholds, sorted(thresholds, reverse=True))
        self.assertEqual(attacks, sorted(attacks, reverse=True))
        # 咬得住齿音/爆破音才压得下峰均比：慢起音（5 ms，主控实验的形状）几乎没用。
        self.assertLessEqual(max(attacks), 1.0)

    def test_filter_threshold_is_relative_to_the_normalised_peak(self):
        stage = dict(s7.DENSITY_STAGES[0], threshold_below_peak_db=-20.0)
        text = s7.density_filter(stage, normalize_peak_dbfs=-1.0)
        self.assertIn('acompressor=', text)
        self.assertIn(':makeup=1', text)          # 电平交给 loudnorm，密度级不做补偿增益
        threshold = float(re.search(r'threshold=([0-9.]+)', text).group(1))
        self.assertAlmostEqual(threshold, 10 ** (-21.0 / 20), places=6)
        self.assertAlmostEqual(
            float(re.search(r'threshold=([0-9.]+)',
                            s7.density_filter(stage, normalize_peak_dbfs=-6.0)).group(1)),
            10 ** (-26.0 / 20), places=6)

    def test_strategy_params_carry_the_ladder_but_never_the_per_item_stage(self):
        params = s7.master_params(**s7.master_policy('battle/power_flip_0', 2))
        self.assertIn('density', params)
        for name in ('light', 'medium', 'firm'):
            self.assertIn(name, params['density'])
        # 逐条自适应的结果绝不能进 params：否则续跑重算的期望值与报告必然不同 ⇒ 满屏假 QC drift。
        for word in ('stage=', 'applied', 'crest'):
            self.assertNotIn(word, params['density'])
        self.assertEqual(params['density'], s7.density_ladder())

    def test_v1_params_are_untouched_even_if_density_is_asked_for(self):
        self.assertEqual(s7.master_params(density=True), s7.MASTER_PARAMS)
        self.assertEqual(s7.master_params(mode='fixed_gain', trim=False, density=True),
                         s7.MASTER_PARAMS)
        self.assertNotIn('density', s7.master_params(**s7.master_policy('battle/power_flip_0', 1)))
        self.assertEqual(s7.master_policy('battle/power_flip_0', 1), dict(mode='fixed_gain', trim=False))
        self.assertTrue(s7.master_policy('battle/power_flip_0', 2)['density'])


@unittest.skipUnless(HAVE_FFMPEG, 'local ffmpeg unavailable')
class DensityMasteringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def master(self, samples, **changes):
        source = self.root / f'raw{len(list(self.root.glob("raw*.wav")))}.wav'
        write_wav(source, samples)
        options = dict(slot='battle/power_flip_0', code='fixture', ffmpeg=FFMPEG, ffprobe=FFPROBE,
                       mode='two_pass', trim=True, density=True)
        options.update(changes)
        target = self.root / 'out' / f'{source.stem}.mp3'
        return source, target, s7.master_voice(source, target, **options)

    def test_peaky_quiet_take_is_pulled_into_band_without_density_only_at_a_cost(self):
        samples = peaky(0.9, 1.0, 0.5)
        _src, _tgt, (_stored, plain) = self.master(samples, density=False)
        self.assertIsNone(plain['density'])
        self.assertEqual(plain['loudness_status'], 'under_target')
        self.assertLess(plain['final']['lufs_i'], s7.MASTER_LOUDNESS_BAND[0])

        _src, target, (stored, dense) = self.master(samples)
        self.assertEqual(dense['loudness_status'], 'ok')
        self.assertGreaterEqual(dense['final']['lufs_i'], s7.MASTER_LOUDNESS_BAND[0])
        self.assertGreater(dense['final']['lufs_i'], plain['final']['lufs_i'] + 1.0)
        self.assertTrue(dense['density']['applied'])
        self.assertIn(dense['density']['stage'], [s['name'] for s in s7.DENSITY_STAGES])
        # 峰均比压下来了，这才是响度上得去的原因。
        self.assertLess(dense['density']['after']['crest_db'], dense['density']['before']['crest_db'] - 3)
        self.assertEqual(wf_assets.mp3_decode(stored), target.read_bytes())

    def test_density_changes_neither_length_nor_headroom(self):
        _src, _tgt, (_stored, report) = self.master(peaky(0.9, 1.0, 0.5))
        self.assertTrue(report['density']['applied'])
        self.assertLessEqual(abs(report['sample_delta']), s7.SAMPLE_DELTA_LIMIT)
        self.assertEqual(report['mastered_pcm']['clipped_fraction'], 0.0)
        self.assertLess(report['mastered_pcm']['peak'], 0.999)
        self.assertLessEqual(report['final']['true_peak_dbtp'], s7.PEAK_CEILING)
        # 密度级之后限幅仍然只是安全网。
        self.assertLessEqual(report['limiter_reduction_bound_db'],
                             s7.SAFETY_LIMITER_REDUCTION_DB + 1e-6)
        self.assertEqual(report['params']['max_limiter_reduction_db'],
                         s7.SAFETY_LIMITER_REDUCTION_DB)
        # 时长按官方口径也没被动过：裁的只有边缘那一刀。
        self.assertTrue(report['no_speed_no_concatenation'])

    def test_a_take_that_already_lands_in_band_is_left_alone(self):
        _src, _tgt, (_stored, report) = self.master(burst(0.9, 1.0, 0.5, level=0.02))
        self.assertEqual(report['loudness_status'], 'ok')
        self.assertFalse(report['density']['applied'])
        self.assertIsNone(report['density']['stage'])
        self.assertEqual(report['density']['stages_tried'], [None])

    def test_stages_escalate_one_at_a_time_and_stop_as_soon_as_it_is_enough(self):
        _src, _tgt, (_stored, report) = self.master(peaky(0.9, 1.0, 0.5))
        # 这条夹具的峰均比 19.5 dB：light 还差一点（-15.8），medium 够了（-14.1）⇒
        # 逐档升级，且够了就停 —— firm 一次都不该跑。
        self.assertEqual(report['density']['stages_tried'], [None, 'light', 'medium'])
        self.assertEqual(report['density']['stage'], 'medium')
        self.assertEqual(report['loudness_status'], 'ok')
        by_stage = dict((row[0], row[1]) for row in report['density']['mastered_lufs_by_stage'])
        self.assertEqual(list(by_stage), [None, 'light', 'medium'])
        self.assertLess(by_stage['light'], s7.MASTER_LOUDNESS_BAND[0])
        self.assertGreater(by_stage['medium'], by_stage['light'])

    def test_a_stage_that_does_not_help_is_climbed_past_rather_than_accepted(self):
        # 第一档换成 ratio=1（acompressor 的恒等档）⇒ 它一定不够，必须自己爬到下一档。
        noop = dict(s7.DENSITY_STAGES[0], ratio=1.0)
        with unittest.mock.patch.object(s7, 'DENSITY_STAGES', (noop, s7.DENSITY_STAGES[2])):
            _src, _tgt, (_stored, report) = self.master(peaky(0.9, 1.0, 0.5))
        self.assertEqual(report['density']['stages_tried'], [None, 'light', 'firm'])
        self.assertEqual(report['density']['stage'], 'firm')
        self.assertEqual(report['loudness_status'], 'ok')

    def test_the_per_item_stage_stays_out_of_the_drift_relevant_params(self):
        _src, _tgt, (_stored, applied) = self.master(peaky(0.9, 1.0, 0.5))
        _src, _tgt, (_stored, skipped) = self.master(burst(0.9, 1.0, 0.5, level=0.02))
        self.assertNotEqual(applied['density']['stage'], skipped['density']['stage'])
        self.assertEqual(applied['params'], skipped['params'])
        self.assertEqual(applied['params'],
                         s7.master_params(**s7.master_policy('battle/power_flip_0', 2)))

    def test_v1_is_byte_identical_whatever_density_says(self):
        samples = burst(0.9, 1.0, 0.5, level=0.05)
        _s, _t, (off, report_off) = self.master(samples, mode='fixed_gain', trim=False, density=False)
        _s, _t, (on, report_on) = self.master(samples, mode='fixed_gain', trim=False, density=True)
        self.assertEqual(off, on)
        self.assertEqual(report_off['params'], s7.MASTER_PARAMS)
        self.assertEqual(report_on['params'], s7.MASTER_PARAMS)
        self.assertIsNone(report_on['density'])
        self.assertIsNone(report_on['loudnorm'])


@unittest.skipUnless(HAVE_FFMPEG, 'local ffmpeg unavailable')
class RemasterTests(unittest.TestCase):
    """`--remaster`：允许用新策略覆盖旧的 qc/standard；raw 与 receipts 一个字节不动。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.temp.name) / 'takes' / '01'
        self.line = v2_line(slot='battle/power_flip_0', code='fixture_code')
        base = self.run_dir / self.line['role']
        self.source = base / 'raw' / (self.line['slot'] + '.wav')
        write_wav(self.source, peaky(0.9, 1.0, 0.5))
        self.receipt = base / 'receipts' / (self.line['slot'] + '.json')
        self.receipt.parent.mkdir(parents=True, exist_ok=True)
        self.receipt.write_text(json.dumps(dict(status='generated', sha256=s7.sha(self.source.read_bytes()),
                                                request_fingerprint=s7.request_fingerprint(self.line))),
                                encoding='utf-8')
        self.qc = base / 'qc' / (self.line['slot'] + '.json')
        self.standard = base / 'standard' / (self.line['slot'] + '.mp3')

    def tearDown(self):
        self.temp.cleanup()

    def process(self, **changes):
        return s7.process_run([self.line], self.run_dir, ffmpeg=FFMPEG, ffprobe=FFPROBE,
                              version=2, **changes)

    def test_resume_is_still_cached_and_remaster_is_a_no_op_when_nothing_changed(self):
        self.assertEqual([x['status'] for x in self.process()['items']], ['mastered'])
        self.assertEqual([x['status'] for x in self.process()['items']], ['cached'])
        # 开关不是「无条件重做」：策略没变就仍然命中缓存，不白烧一遍 ffmpeg。
        self.assertEqual([x['status'] for x in self.process(remaster=True)['items']], ['cached'])

    def test_a_strategy_change_needs_the_switch_and_leaves_raw_alone(self):
        self.process()
        before = (self.source.read_bytes(), self.receipt.read_bytes())
        stale = json.loads(self.qc.read_bytes())
        self.assertEqual(stale['params'], s7.master_params(**s7.master_policy(self.line['slot'], 2)))
        # 模拟「旧策略产物」：把报告改成没有密度级的那一版参数。
        old_params = {k: v for k, v in stale['params'].items() if k != 'density'}
        self.qc.write_text(json.dumps(dict(stale, params=old_params)), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'QC drift'):
            self.process()
        summary = self.process(remaster=True)
        self.assertEqual([x['status'] for x in summary['items']], ['remastered'])
        fresh = json.loads(self.qc.read_bytes())
        self.assertEqual(fresh['params'], s7.master_params(**s7.master_policy(self.line['slot'], 2)))
        self.assertEqual(fresh['standard_sha256'], s7.sha(self.standard.read_bytes()))
        self.assertEqual((self.source.read_bytes(), self.receipt.read_bytes()), before)
        self.assertEqual([x['status'] for x in self.process()['items']], ['cached'])

    def test_remaster_reports_the_density_stage_in_the_run_summary(self):
        summary = self.process()
        self.assertEqual(summary['items'][0]['density'], 'medium')
        self.assertEqual(summary['items'][0]['loudness_status'], 'ok')
        self.assertEqual(summary['retake_candidates'], [])

    def test_the_switch_is_only_on_process(self):
        self.assertIn('--remaster', _cli_help(['process', '--help']))
        for command in ('select', 'plan', 'generate'):
            self.assertNotIn('--remaster', _cli_help([command, '--help']))


def _cli_help(argv):
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.suppress(SystemExit):
        s7.main(argv)
    return buffer.getvalue()


class AssetVocabularyTests(unittest.TestCase):
    def test_numbered_and_switched_voices_are_probed(self):
        vocab = set(wf_assets._voice_vocab())
        for name in ('battle/matched_skill_ready.mp3', 'battle/skill_4.mp3', 'battle/skill_7.mp3',
                     'battle/matched_skill_0.mp3', 'battle/matched_skill_3.mp3',
                     'battle/battle_start_2.mp3', 'battle/battle_start_3.mp3',
                     'battle/exchange_power_flip_0.mp3', 'battle/exchange_power_flip_1.mp3'):
            with self.subTest(name=name):
                self.assertIn(name, vocab)
        # 旧词表条目一个都不能丢。
        for name in ('battle/skill_0.mp3', 'battle/skill_3.mp3', 'battle/skill_ready.mp3',
                     'ally/join.mp3', 'ally/evolution.mp3', 'home/home_9.mp3',
                     'battle/normal_attack_0.mp3', 'login/login_2.mp3'):
            self.assertIn(name, vocab)

    def test_every_engine_slot_this_batch_ships_is_in_the_vocabulary(self):
        vocab = set(wf_assets._voice_vocab())
        for slot in s7.SLOTS_26:
            self.assertIn(slot + '.mp3', vocab, slot)


if __name__ == '__main__':
    unittest.main()
