"""离线日语 ASR 内容复核；与生成接口字幕独立，不表示人工听审。"""
from __future__ import annotations

from wf.paths import root_path, path

import argparse
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import time
import unicodedata

def normalized(text):
    return ''.join(x for x in unicodedata.normalize('NFKC', text) if x.isalnum())


def comparison(expected, recognized, reading):
    source, actual = normalized(expected), normalized(recognized)
    a, b = normalized(reading(expected)), normalized(reading(recognized))
    return dict(text_equal=source == actual,
        text_similarity=SequenceMatcher(None, source, actual, autojunk=False).ratio(),
        expected_reading=a, recognized_reading=b,
        reading_similarity=SequenceMatcher(None, a, b, autojunk=False).ratio(),
        requires_review=(source != actual and a != b))


def transcribe_available(plan, recordings, output, model, reading, *, model_snapshot=None):
    completed=0
    for line in plan:
        role, slot=line['role'], line['slot']
        source=recordings/role/'raw'/(slot+'.mp3')
        receipt=recordings/role/'receipts'/(slot+'.json')
        if not source.exists() or not receipt.exists():
            continue
        generated=json.loads(receipt.read_bytes())
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        if generated.get('status')!='generated' or generated.get('sha256')!=digest:
            raise ValueError('source recording not verified')
        target=output/role/(slot+'.json')
        if target.exists():
            saved=json.loads(target.read_bytes())
            if saved['source_sha256']!=digest or saved['expected']!=line['ja']:
                raise ValueError('ASR source drift')
            completed+=1
            continue
        segments, info=model.transcribe(str(source), language='ja', beam_size=5,
            vad_filter=False, condition_on_previous_text=False)
        items=[dict(start=s.start,end=s.end,text=s.text,avg_logprob=s.avg_logprob,
                    no_speech_prob=s.no_speech_prob) for s in segments]
        transcript=''.join(s['text'] for s in items).strip()
        result=dict(role=role,slot=slot,source=str(source),source_sha256=digest,
            expected=line['ja'],transcript=transcript,segments=items,
            comparison=comparison(line['ja'],transcript,reading),
            expected_pronunciation=line.get('tts_text',line['ja']),
            pronunciation_comparison=comparison(line.get('tts_text',line['ja']),transcript,reading),
            model='faster-whisper-large-v3',
            model_snapshot=str(model_snapshot) if model_snapshot is not None else None,
            language=info.language,independent_of_provider_subtitles=True,
            human_listening_review=False)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(dict(role=role,slot=slot,reading_similarity=result['pronunciation_comparison']['reading_similarity'],
                             requires_review=result['pronunciation_comparison']['requires_review']),ensure_ascii=False),flush=True)
        completed+=1
    return completed


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--recordings',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--watch-seconds',type=int,default=0)
    a=p.parse_args()
    allowed=Path(('${WF_ROOT}/startpoint-cn/work/codex_out/character-art-voice-20260912/voice'.replace("${WF_ROOT}", str(root_path()))))
    if not a.output.resolve().is_relative_to(allowed):
        raise SystemExit('ASR output outside assigned evidence directory')
    from faster_whisper import WhisperModel
    import pyopenjtalk
    model_snapshot = path("asr_model")
    model=WhisperModel(str(model_snapshot),device='cuda',compute_type='float16',local_files_only=True)
    reading=lambda text:pyopenjtalk.g2p(text,kana=True)
    plan=json.loads(a.plan.read_bytes());deadline=time.monotonic()+a.watch_seconds
    while True:
        count=transcribe_available(plan,a.recordings,a.output,model,reading,
                                   model_snapshot=model_snapshot)
        if count==len(plan) or time.monotonic()>=deadline:
            print(json.dumps(dict(completed=count,expected=len(plan))),flush=True)
            return
        time.sleep(20)


if __name__=='__main__':main()
