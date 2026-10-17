import unittest
import numpy as np

import wf_seasonal7_voice as voice
from wf_voice_selection_timing import (delivery_edges, delivery_dead_air,
    acoustic_timing, delivery_gap, raw_level_is_blocking)


class DeliveryTimingTests(unittest.TestCase):
    def test_acoustic_gap_uses_audio_and_is_gain_invariant(self):
        a = np.r_[np.zeros(4410), np.full(8820, .2), np.zeros(13230),
                  np.full(8820, .2), np.zeros(4410)]
        timing = acoustic_timing(a)
        self.assertEqual(timing, acoustic_timing(a / 100))
        self.assertEqual(timing['max_inner_gap_seconds'], .3)
        self.assertEqual(timing['active_span_seconds'], .7)
        self.assertEqual(delivery_gap(dict(max_inner_gap_seconds=.8),
                                     dict(delivery_timing=timing)), (.3, .7))

    def test_silence_and_nonfinite_audio_cannot_supply_good_timing(self):
        for a in (np.zeros(44100), np.array([np.nan]), np.array([])):
            with self.assertRaises(ValueError):
                acoustic_timing(a)

    def test_quiet_source_requires_complete_mastering_proof(self):
        qc = dict(raw_lufs_i=-35, mastering_mode='two_pass', storage_roundtrip_equal=True,
                  source_pcm=dict(peak=.1), mastered_pcm=dict(samples=44100),
                  sample_delta=0, sample_delta_limit=64)
        self.assertFalse(raw_level_is_blocking(qc, -26))
        for patch in (dict(storage_roundtrip_equal=False), dict(sample_delta=100),
                      dict(raw_lufs_i=-70), dict(raw_lufs_i=float('nan')),
                      dict(mastering_mode='fixed_gain')):
            self.assertTrue(raw_level_is_blocking(dict(qc, **patch), -26))

    def test_trimmed_lead_is_not_rejected_again(self):
        metrics = dict(duration=2.84, lead_in_seconds=1.12, tail_seconds=0.06)
        qc = dict(seconds=1.81, trim=dict(start_seconds=1.0, end_seconds=2.78))
        self.assertEqual(delivery_edges(metrics, qc), (0.12, 0.0))
        self.assertAlmostEqual(delivery_dead_air(metrics, qc), 0.12 / 1.81)

    def test_untrimmed_silence_stays_visible(self):
        self.assertEqual(delivery_edges(dict(lead_in_seconds=1.12, tail_seconds=0.7), {}),
                         (1.12, 0.7))

    def test_missing_subtitle_uses_mastered_audio(self):
        qc = dict(source_pcm=dict(leading_quiet_seconds=1.3, trailing_quiet_seconds=0.8),
                  mastered_pcm=dict(leading_quiet_seconds=0.1, trailing_quiet_seconds=0.15))
        self.assertEqual(delivery_edges({}, qc), (0.1, 0.15))

    def test_aligned_words_do_not_override_measured_audio_edges(self):
        # A provider ends its final word early even though speech continues.
        # Silence gates must use the deliverable, like the internal-gap gate.
        timing = acoustic_timing(np.r_[np.zeros(4410), np.full(44100, .2),
                                      np.zeros(6615)])
        qc = dict(seconds=1.25, delivery_timing=timing,
                  trim=dict(start_seconds=.4, end_seconds=1.65))
        self.assertEqual(delivery_edges(dict(lead_in_seconds=.8, tail_seconds=.9), qc),
                         (.1, .15))
        self.assertAlmostEqual(delivery_dead_air({}, qc), .2)

    def test_dash_is_not_a_spoken_word_but_inserted_words_still_fail(self):
        self.assertEqual(voice.normalize_spoken('——ひとつとっておけ。'),
                         voice.normalize_spoken('ひとつとっておけ'))
        self.assertNotEqual(voice.normalize_spoken('よばんぶんだ、ひとつとっておけ。'),
                            voice.normalize_spoken('——ひとつとっておけ。'))


if __name__ == '__main__':
    unittest.main()
