# -*- coding: utf-8 -*-
"""wf_voice_gate 单测。

全部用**合成 mp3 字节**(合法帧头 + 全零负载),不读 store、不读归档、不需要 ffmpeg,
所以离线可跑。判据的官方基线口径写在被测模块的 docstring 里。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import wf_assets  # noqa: E402
import wf_voice_gate as gate  # noqa: E402

MP3_BR_INDEX = {32: 1, 40: 2, 48: 3, 56: 4, 64: 5, 80: 6, 96: 7, 112: 8, 128: 9,
                160: 10, 192: 11, 224: 12, 256: 13, 320: 14}
SR_INDEX = {44100: 0, 48000: 1, 32000: 2}


def frame(bitrate: int = 96, srate: int = 44100, channels: int = 1, pad: int = 0,
          marker: bytes = b'') -> bytes:
    """一个 MPEG1 Layer III 帧(标准 0xFF 同步头);负载填零,容器解析用不到内容。"""
    b1 = 0xFB                                     # MPEG1 / Layer III / 无 CRC
    b2 = (MP3_BR_INDEX[bitrate] << 4) | (SR_INDEX[srate] << 2) | (pad << 1)
    b3 = (0b11 if channels == 1 else 0b00) << 6
    size = 1152 // 8 * bitrate * 1000 // srate + pad
    body = bytearray(size - 4)
    body[4:4 + len(marker)] = marker
    return bytes([0xFF, b1, b2, b3]) + bytes(body)


def obf(one_frame: bytes) -> bytes:
    """把单帧转成存储态(首字节清最高位)。
    VBR 用例不能走 wf_assets.mp3_encode —— 它会先把 VBR 拒掉,拿不到被测数据。"""
    return bytes([one_frame[0] & 0x7F]) + one_frame[1:]


def id3(size: int = 100) -> bytes:
    body = bytes(size)
    syncsafe = bytes([(size >> 21) & 0x7F, (size >> 14) & 0x7F, (size >> 7) & 0x7F, size & 0x7F])
    return b'ID3\x03\x00\x00' + syncsafe + body


def mp3(n_audio_frames: int, *, bitrate: int = 96, srate: int = 44100, channels: int = 1,
        xing: bool = True, with_id3: bool = True, tail: int = 0,
        obfuscate: bool = True) -> bytes:
    data = id3() if with_id3 else b''
    if xing:
        data += frame(bitrate, srate, channels, marker=b'Info')
    for _ in range(n_audio_frames):
        data += frame(bitrate, srate, channels)
    data += bytes(tail)
    return wf_assets.mp3_encode(data) if obfuscate else data


def vf(character: str, slot: str, **kw) -> gate.VoiceFile:
    frames = kw.pop('frames', 60)
    return gate.VoiceFile(character, slot, mp3(frames, **kw))


def frames_for(seconds: float, srate: int = 44100) -> int:
    return max(1, round(seconds * srate / 1152))


class HeaderTests(unittest.TestCase):
    def test_id3_len_syncsafe(self):
        self.assertEqual(gate.id3_len(id3(100)), 110)
        self.assertEqual(gate.id3_len(id3(1000)), 1010)
        self.assertEqual(gate.id3_len(b'\xff\xfb\x70\xc0'), 0)

    def test_parse_accepts_both_sync_bytes(self):
        std = frame()[:4]
        stored = bytes([std[0] & 0x7F]) + std[1:]
        for hdr, flag in ((std, False), (stored, True)):
            h = gate.parse_header(hdr)
            self.assertIsNotNone(h)
            self.assertEqual((h['bitrate'], h['srate'], h['channels'], h['obfuscated']),
                             (96, 44100, 1, flag))

    def test_frame_size_matches_official_spec(self):
        """96 kbps / 44100 / MPEG1 L3 每帧 313 字节(padding 帧 314)。"""
        self.assertEqual(gate.parse_header(frame(pad=0)[:4])['size'], 313)
        self.assertEqual(gate.parse_header(frame(pad=1)[:4])['size'], 314)

    def test_reject_reserved_and_free_format(self):
        bad_version = bytes([0xFF, 0xEB, 0x70, 0xC0])      # ver=01 保留
        bad_layer = bytes([0xFF, 0xF9, 0x70, 0xC0])        # layer=00 保留
        free_bitrate = bytes([0xFF, 0xFB, 0x00, 0xC0])     # bitrate index 0
        bad_id = bytes([0xFF, 0xFB, 0x7C, 0xC0])           # srate index 3
        for hdr in (bad_version, bad_layer, free_bitrate, bad_id):
            self.assertIsNone(gate.parse_header(hdr), hdr.hex())

    def test_no_sync_returns_none(self):
        self.assertIsNone(gate.parse_header(b'ID3\x03'))
        self.assertIsNone(gate.parse_header(b'\xff'))


class ProbeTests(unittest.TestCase):
    def test_duration_excludes_xing_frame(self):
        info = gate.probe(mp3(100))
        self.assertTrue(info['ok'] and info['xing'])
        self.assertEqual(info['frames'], 101)
        self.assertEqual(info['audio_frames'], 100)
        self.assertAlmostEqual(info['duration'], 100 * 1152 / 44100, places=6)

    def test_official_shape_is_reported_clean(self):
        info = gate.probe(mp3(50))
        self.assertEqual((info['srate'], info['channels'], info['bitrate']),
                         ([44100], [1], [96]))
        self.assertTrue(info['cbr'] and info['obfuscated'])
        self.assertEqual(info['tail'], 0)

    def test_id3v1_tail_is_counted(self):
        self.assertEqual(gate.probe(mp3(10, tail=128))['tail'], 128)

    def test_standard_mp3_is_not_obfuscated(self):
        self.assertFalse(gate.probe(mp3(10, obfuscate=False))['obfuscated'])

    def test_vbr_detected(self):
        data = id3() + obf(frame(96)) + obf(frame(128)) + obf(frame(96))
        info = gate.probe(data)
        self.assertFalse(info['cbr'])
        self.assertEqual(info['bitrate'], [96, 128])

    def test_garbage_is_not_ok(self):
        info = gate.probe(b'not an mp3 at all')
        self.assertFalse(info['ok'])
        self.assertEqual(info['duration'], 0.0)

    def test_agrees_with_wf_assets_probe(self):
        """与仓里已有的 wf_assets.mp3_probe 在帧数/码率上必须一致(同一批文件两套解析器)。"""
        data = mp3(37)
        mine = gate.probe(data)
        theirs = wf_assets.mp3_probe(data, 1023)
        self.assertEqual(mine['frames'], theirs['frames'])
        self.assertEqual({b // 1000 for b in theirs['bitrates']}, set(mine['bitrate']))
        self.assertEqual(mine['tail'], theirs['tail'])


class SlotFamilyTests(unittest.TestCase):
    def test_known_slots(self):
        cases = {'battle/skill_1': 'skill_N', 'battle/skill_ready': 'skill_ready',
                 'battle/power_flip_0': 'power_flip_N', 'battle/battle_start_2': 'battle_start_N',
                 'battle/outhole_1': 'outhole_N', 'battle/win_0': 'win_N',
                 'battle/normal_attack_0': 'normal_attack_N',
                 'home/home_3': 'home', 'home/hoshimino': 'home',
                 'ally/join': 'join', 'ally/evolution': 'evolution', 'login/a': 'login'}
        for slot, fam in cases.items():
            self.assertEqual(gate.slot_family(slot), fam, slot)

    def test_unknown_slots(self):
        for slot in ('battle/matched_skill_0', 'battle/whatever', 'ally/mystery', 'noslash'):
            self.assertIsNone(gate.slot_family(slot), slot)

    def test_baseline_quantiles_are_monotonic(self):
        for fam, row in gate.OFFICIAL_DURATION.items():
            n, lo, p50, p90, p95, p99, mx = row
            self.assertGreater(n, 0, fam)
            self.assertLessEqual(lo, p50, fam)
            self.assertLessEqual(p50, p90, fam)
            self.assertLessEqual(p90, p95, fam)
            self.assertLessEqual(p95, p99, fam)
            self.assertLessEqual(p99, mx, fam)


class ReachabilityTests(unittest.TestCase):
    def test_contiguous_indices_all_reachable(self):
        r = gate.engine_reachable(['battle/skill_0', 'battle/skill_1', 'battle/skill_2'])
        self.assertEqual(r['unreachable'], [])
        self.assertEqual(r['dead_prefix'], [])

    def test_gap_makes_the_rest_unreachable(self):
        """generateVoicePaths 遇缺号即 break —— skill_0 + skill_2 时 skill_2 永远播不到。"""
        r = gate.engine_reachable(['battle/skill_0', 'battle/skill_2', 'battle/skill_3'])
        self.assertEqual(r['unreachable'], ['battle/skill_2', 'battle/skill_3'])

    def test_missing_index_zero_kills_the_whole_prefix(self):
        r = gate.engine_reachable(['battle/win_1'])
        self.assertEqual(r['unreachable'], ['battle/win_1'])

    def test_normal_attack_is_a_dead_prefix(self):
        r = gate.engine_reachable(['battle/normal_attack_0', 'battle/normal_attack_1'])
        self.assertEqual(r['dead_prefix'], ['battle/normal_attack_0', 'battle/normal_attack_1'])
        self.assertEqual(r['unreachable'], [])

    def test_single_slots_are_not_index_scanned(self):
        r = gate.engine_reachable(['battle/skill_ready', 'battle/matched_skill_ready'])
        self.assertEqual((r['unreachable'], r['dead_prefix']), ([], []))

    def test_home_and_ally_are_ignored(self):
        r = gate.engine_reachable(['home/home_5', 'ally/join'])
        self.assertEqual((r['unreachable'], r['dead_prefix']), ([], []))


class ContainerRuleTests(unittest.TestCase):
    def _rules(self, **kw) -> set[str]:
        f = vf('c', 'battle/skill_0', **kw)
        return {x.rule for x in gate.check_container(f, gate.probe(f.data))}

    def test_official_shape_passes(self):
        self.assertEqual(self._rules(), set())

    def test_stereo_flagged(self):
        self.assertIn('bad_channels', self._rules(channels=2))

    def test_bitrate_flagged(self):
        self.assertIn('bad_bitrate', self._rules(bitrate=128))

    def test_srate_flagged(self):
        self.assertIn('bad_srate', self._rules(srate=48000))

    def test_unobfuscated_flagged(self):
        self.assertIn('not_obfuscated', self._rules(obfuscate=False))

    def test_junk_tail_flagged(self):
        self.assertIn('bad_tail', self._rules(tail=64))
        self.assertNotIn('bad_tail', self._rules(tail=128))

    def test_unparsable_flagged(self):
        f = gate.VoiceFile('c', 'battle/skill_0', b'\x00' * 200)
        rules = {x.rule for x in gate.check_container(f, gate.probe(f.data))}
        self.assertEqual(rules, {'unparsable'})

    def test_vbr_flagged(self):
        data = id3() + obf(frame(96)) + obf(frame(128)) + obf(frame(96))
        f = gate.VoiceFile('c', 'battle/skill_0', data)
        self.assertIn('not_cbr', {x.rule for x in gate.check_container(f, gate.probe(f.data))})


class DurationRuleTests(unittest.TestCase):
    def _rule(self, slot: str, seconds: float) -> str | None:
        f = vf('c', slot, frames=frames_for(seconds))
        out = gate.check_duration(f, gate.probe(f.data))
        return out[0].rule if out else None

    def test_in_range_is_silent(self):
        self.assertIsNone(self._rule('battle/skill_0', 2.35))
        self.assertIsNone(self._rule('battle/skill_ready', 1.46))

    def test_over_official_max_is_error(self):
        f = vf('c', 'battle/skill_ready', frames=frames_for(21.42))
        out = gate.check_duration(f, gate.probe(f.data))
        self.assertEqual((out[0].level, out[0].rule), ('error', 'over_official_max'))

    def test_over_p90_is_warn_only(self):
        f = vf('c', 'battle/power_flip_0', frames=frames_for(2.5))   # p90 1.70 / max 3.13
        out = gate.check_duration(f, gate.probe(f.data))
        self.assertEqual((out[0].level, out[0].rule), ('warn', 'over_official_p90'))

    def test_below_min_is_warn(self):
        self.assertEqual(self._rule('battle/win_0', 0.5), 'below_official_min')

    def test_unknown_family_is_skipped(self):
        self.assertIsNone(self._rule('battle/matched_skill_0', 99.0))


class DuplicateRuleTests(unittest.TestCase):
    def test_distinct_files_are_silent(self):
        files = [vf('a', 'battle/skill_0', frames=30), vf('a', 'battle/skill_1', frames=31)]
        self.assertEqual(gate.check_duplicates(files), [])

    def test_cross_character_duplicate_is_error(self):
        data = mp3(30)
        files = [gate.VoiceFile('a', 'battle/skill_0', data),
                 gate.VoiceFile('b', 'battle/skill_0', data)]
        out = gate.check_duplicates(files)
        self.assertEqual([f.rule for f in out], ['cross_character_duplicate'])
        self.assertEqual(out[0].level, 'error')

    def test_intra_character_duplicate_is_warn(self):
        data = mp3(30)
        files = [gate.VoiceFile('a', 'battle/skill_0', data),
                 gate.VoiceFile('a', 'home/home_0', data)]
        out = gate.check_duplicates(files)
        self.assertEqual([f.rule for f in out], ['intra_character_duplicate'])
        self.assertEqual(out[0].level, 'warn')

    def test_same_family_duplicate_is_reported_separately(self):
        """同族重复 = 客户端 Std.random 抽到的永远是同一条。"""
        data = mp3(30)
        files = [gate.VoiceFile('a', 'battle/outhole_0', data),
                 gate.VoiceFile('a', 'battle/outhole_1', data),
                 gate.VoiceFile('a', 'battle/outhole_2', data)]
        rules = [f.rule for f in gate.check_duplicates(files)]
        self.assertIn('same_family_duplicate', rules)
        self.assertIn('intra_character_duplicate', rules)


class IntegrationTests(unittest.TestCase):
    def _clean_set(self) -> list[gate.VoiceFile]:
        return [vf('a', 'battle/skill_0', frames=frames_for(2.3)),
                vf('a', 'battle/skill_1', frames=frames_for(2.4)),
                vf('a', 'battle/skill_ready', frames=frames_for(1.5)),
                vf('a', 'battle/power_flip_0', frames=frames_for(1.0)),
                vf('a', 'home/home_0', frames=frames_for(11.0)),
                vf('a', 'ally/join', frames=frames_for(10.0)),
                vf('a', 'ally/evolution', frames=frames_for(11.5))]

    def test_clean_set_has_no_findings(self):
        self.assertEqual(gate.check_voice_set(self._clean_set()), [])

    def test_errors_sort_before_warns(self):
        files = self._clean_set()
        files.append(vf('a', 'battle/win_0', frames=frames_for(20.0)))   # 超 win_N max 9.04
        files.append(vf('a', 'battle/win_1', frames=frames_for(6.0)))    # 超 p90 5.41
        out = gate.check_voice_set(files)
        self.assertEqual(out[0].level, 'error')
        self.assertEqual(out[0].rule, 'over_official_max')
        self.assertTrue(all(f.level == 'warn' for f in out[1:]))

    def test_the_actual_shipped_defect_is_caught(self):
        """21.42 s 的同一份字节同时投在白虎和深渊之兽的 skill_ready —— 两条判据都要响。"""
        data = mp3(frames_for(21.42))
        files = [gate.VoiceFile('white_tiger_ghost_playable', 'battle/skill_ready', data),
                 gate.VoiceFile('abyss_beast_playable', 'battle/skill_ready', data)]
        rules = {f.rule for f in gate.check_voice_set(files) if f.level == 'error'}
        self.assertEqual(rules, {'over_official_max', 'cross_character_duplicate'})


if __name__ == '__main__':
    unittest.main()
