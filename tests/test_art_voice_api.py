import base64
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import urllib.error

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_art_voice_api as api


def line():
    return dict(role='bianca',slot='battle/skill_ready',persona='成年女性教师',
                direction='自然日语',ja='準備できたわ。',zh='准备好了。',references=[])


class Response:
    status=200
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def read(self):return json.dumps({'audio':base64.b64encode(b'audio'*300).decode(),'duration':1.2}).encode()


class ArtVoiceApiTests(unittest.TestCase):
    def test_anchored_prompt_carries_normal_speech_first_and_short_acting_second(self):
        with tempfile.TemporaryDirectory() as temp:
            refs=[]
            for purpose in ('normal_timbre','performance'):
                raw=purpose.encode();path=Path(temp)/(purpose+'.wav');path.write_bytes(raw)
                refs.append(dict(path=str(path),sha256=api.sha(raw),purpose=purpose))
            value=dict(line(),prompt_version=4,tone='有力高呼',references=refs)
            request=api.payload(value)
            self.assertEqual([base64.b64decode(x['audio_data']) for x in request['references']],
                             [b'normal_timbre',b'performance'])
            self.assertIn('@音频2仅参考发力和语气',request['text_prompt'])
            self.assertTrue(request['text_prompt'].endswith('“準備できたわ。”'))
            self.assertNotIn(value['zh'],request['text_prompt'])
            self.assertNotIn('无背景音乐',request['text_prompt'])
            with self.assertRaisesRegex(ValueError,'first reference'):
                api.payload(dict(value,references=list(reversed(refs))))
            with self.assertRaisesRegex(ValueError,'one or two'):
                api.payload(dict(value,references=[]))
            with self.assertRaisesRegex(ValueError,'second reference'):
                api.payload(dict(value,references=[refs[0],refs[0]]))
            self.assertNotIn('@音频2',api.payload(dict(value,references=refs[:1]))['text_prompt'])

    def test_brief_prompt_keeps_script_and_one_reference_without_legacy_directions(self):
        value=dict(line(),prompt_version=3,tone='沉稳自然',performance='unused',voice_tag='unused')
        text=api.prompt_v3(value,1)
        self.assertIn('@音频1',text)
        self.assertTrue(text.endswith('“準備できたわ。”'))
        self.assertNotIn('unused',text)
        self.assertNotIn('无背景音乐',text)
        self.assertLess(len(text),100)
        self.assertEqual(api.payload(dict(value,references=[]))['text_prompt'],api.prompt_v3(value,0))
        with self.assertRaisesRegex(ValueError,'one reference'):api.prompt_v3(value,2)
        with self.assertRaises(ValueError):api.prompt_v3(dict(value,tts_text='準備（できた）'),1)

    def test_success_and_cache_never_persist_key(self):
        calls=[];key='test-secret-credential-12345678'
        def opener(request,**kw):
            self.assertEqual(request.get_header('X-api-key'),key)
            calls.append(request);return Response()
        with tempfile.TemporaryDirectory() as temp:
            target=Path(temp)
            self.assertEqual(api.generate(line(),target,key,opener=opener)['status'],'generated')
            self.assertEqual(api.generate(line(),target,key,opener=opener)['status'],'cached')
            self.assertEqual(len(calls),1)
            for path in target.rglob('*.json'):
                text=path.read_text(encoding='utf-8');self.assertNotIn(key,text);self.assertNotIn('X-api-key',text)

    def test_http_rejection_records_reason_without_raw_body_or_credential(self):
        key='secretcredentialvalue'
        def opener(*_,**__):
            raw=json.dumps({'error':{'code':45001125,'message':'demo text audit failed '+key},'private':key}).encode()
            raise urllib.error.HTTPError(api.ENDPOINT,400,'bad',{},io.BytesIO(raw))
        with tempfile.TemporaryDirectory() as temp:
            result=api.generate(line(),Path(temp),key,opener=opener)
            self.assertEqual(result['status'],'failed');self.assertEqual(result['api_code'],'45001125')
            raw=next(Path(temp).rglob('*.json')).read_text(encoding='utf-8')
            self.assertNotIn(key,raw);self.assertNotIn('private',raw)
            self.assertFalse(list(Path(temp).rglob('*.mp3')))

    def test_rejects_windows_path_escape_before_network(self):
        for slot in ['../escape','battle/../../x','C:/x','battle\\..\\x','/absolute','battle/skill_0:stream']:
            bad=dict(line(),slot=slot)
            with self.subTest(slot=slot),self.assertRaises(ValueError):
                api.generate(bad,Path('unused'),'key',opener=lambda *_:self.fail('network called'))

    def test_reference_drift_and_changed_plan_cannot_reuse_old_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);ref=root/'ref.wav';ref.write_bytes(b'reference')
            value=dict(line(),references=[dict(path=str(ref),sha256='wrong')])
            with self.assertRaisesRegex(ValueError,'reference hash drift'):api.payload(value)
            api.generate(line(),root,'key',opener=lambda *_,**__:Response())
            with self.assertRaisesRegex(ValueError,'existing recording differs'):
                api.generate(dict(line(),ja='異なる台詞'),root,'key',opener=lambda *_,**__:Response())


if __name__=='__main__':unittest.main()
