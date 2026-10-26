from pathlib import Path
import sys
import tempfile
import unittest
import wave

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_art_voice_audio as audio
import wf_art_voice_asr as asr
import wf_assets

FFMPEG=Path('C:/ProgramData/HP/LCDDisplayHelper/bin/ffmpeg.exe')
FFPROBE=FFMPEG.with_name('ffprobe.exe')


class ArtVoiceAudioTests(unittest.TestCase):
    @unittest.skipUnless(FFMPEG.is_file() and FFPROBE.is_file(),'local ffmpeg unavailable')
    def test_real_codec_preserves_duration_and_native_storage(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source.wav';target=root/'standard.mp3'
            rate=32000
            values=np.zeros((38400,2),dtype='<i2')
            wavelet=(14000*np.sin(2*np.pi*440*np.arange(25600)/rate)).astype('<i2')
            values[3200:28800,0]=wavelet;values[3200:28800,1]=wavelet
            with wave.open(str(source),'wb') as handle:
                handle.setnchannels(2);handle.setsampwidth(2);handle.setframerate(rate);handle.writeframes(values.tobytes())
            stored,report=audio.convert(source,target,ffmpeg=FFMPEG,ffprobe=FFPROBE,
                                        code='fixture',slot='battle/skill_ready')
            self.assertEqual(wf_assets.mp3_decode(stored),target.read_bytes())
            self.assertEqual(report['codec']['srate'],[44100])
            self.assertEqual(report['codec']['channels'],[1])
            self.assertEqual(report['codec']['bitrate'],[96])
            self.assertEqual(report['converted_pcm']['clipped_fraction'],0)
            self.assertLessEqual(abs(report['sample_delta']),128)
            self.assertGreater(report['converted_pcm']['leading_quiet_seconds'],0.08)
            self.assertGreater(report['converted_pcm']['trailing_quiet_seconds'],0.28)

    def test_invalid_pcm_and_clipping_are_detected(self):
        for data in ([],[float('nan')],[float('inf')]):
            with self.assertRaises(ValueError):audio.amplitude(data)
        self.assertGreater(audio.amplitude([0,1,-1])['clipped_fraction'],0)

    def test_asr_missing_words_remain_review_required(self):
        outcome=asr.comparison('君の隣を、守る。','守る',lambda x:x)
        self.assertTrue(outcome['requires_review'])
        self.assertLess(outcome['reading_similarity'],0.8)

    def test_asr_punctuation_is_not_a_content_failure(self):
        outcome=asr.comparison('準備、完了。','準備完了',lambda x:x)
        self.assertFalse(outcome['requires_review'])


if __name__=='__main__':unittest.main()
