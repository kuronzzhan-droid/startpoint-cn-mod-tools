"""Seed Audio 角色独立语音生成；密钥仅从进程环境读取，不保存请求头。"""
from __future__ import annotations

from wf.paths import root_path
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
import uuid

ENDPOINT='https://openspeech.bytedance.com/api/v3/tts/create'
MODEL='seed-audio-1.0'

# 模板版本：1 = 第一轮（默认，旧调用方原样保留）；2 = 中秋第二轮配方。
# v2 骨架对齐接口官方范例：场景约束 → 参考音分工 → 不朗读说明 → 表演要求 →
# 「{persona_short}（{voice_tag}）用{tone}的语气说道：“{tts_text}”」，台词永远在最后、
# 用全角引号封边。第一轮把台词裸放在「只说以下日语台词：」之后，既没有把语气绑到这一句的
# 结构，也没有引号封边 —— 实证后果是 11 例句首插词、2 例注音被念出（recon §P1-1/P1-2）。
PROMPT_V2=('录音棚干声，只有这一位说话者；无背景音乐、无环境音、无战斗音效、无混响、无第二人声。\n'
           '{reference_note}'
           '不要朗读本段说明，不要添加台词以外的任何字、注音、旁白或解说；'
           '台词一字不增不减，不重复其中任何词句。\n'
           '表演要求：{performance}。\n'
           '{persona_short}（{voice_tag}）用{tone}的语气说道：“{tts_text}”')
REFERENCE_NOTE_2=('音色以@音频1为准；若有@音频2，只参考它的语气与短句力度。'
                  '两段参考都是这位角色本人，不要复述参考里的任何台词。\n')
REFERENCE_NOTE_1='音色以@音频1为准；这段参考就是这位角色本人，不要复述参考里的任何台词。\n'
# 台词里出现这些符号的实证后果：引号内容被抢到句首先念、原位只剩 ☃ 占位；括号注音被读出来。
# 这道门只卡**实际发给接口的文本**（tts_text，缺省时才是 ja）。稿子里的 ja 允许留装饰符号
# （丝缇涅尔的 ♡ 是作者点名要的「杂鱼」变奏），但那时必须另写一条不含这些符号的 tts_text。
# ♡♥ 与 ♪☆★ 同类：都是模型会抢到句首念出来、或换成 ☃ 占位的装饰符号。
FORBIDDEN_TTS_CHARS='「」『』（）()〈〉《》【】〔〕×♪☆★♡♥“”"'
V2_FIELDS=('persona_short','voice_tag','tone','performance')
AUDIO_FORMATS=('mp3','wav')


def sha(raw):return hashlib.sha256(raw).hexdigest()


def audio_format(line):
    value=str(line.get('audio_format') or 'mp3').lower()
    if value not in AUDIO_FORMATS:raise ValueError('unsupported audio format: '+value)
    return value


def prompt_version(line):
    value=line.get('prompt_version',1)
    version=1 if value in (None,'') else int(value)
    if version not in (1,2,3,4):raise ValueError('unsupported prompt template version: '+str(value))
    return version


def spoken_text(line):
    text=(line.get('tts_text') or line['ja']).strip()
    if not text:raise ValueError('empty spoken text')
    return text


def check_spoken_text(text):
    bad=sorted({c for c in text if c in FORBIDDEN_TTS_CHARS})
    if bad:
        raise ValueError('spoken text carries symbols the model reads aloud or relocates: '+''.join(bad))
    return text


def prompt_v2(line,reference_count):
    text=check_spoken_text(spoken_text(line))
    fields={name:str(line.get(name) or '').strip() for name in V2_FIELDS}
    missing=[name for name,value in fields.items() if not value]
    if missing:raise ValueError('prompt template v2 requires '+', '.join(missing))
    note=(REFERENCE_NOTE_2 if reference_count>=2 else REFERENCE_NOTE_1 if reference_count==1 else '')
    return PROMPT_V2.format(reference_note=note,tts_text=text,**fields)


def prompt_v1(line,reference_count):
    return (line['persona']+'。'+('参考音频来自同一位虚构游戏角色，保持音色统一。' if reference_count else '')+
        '仅一位角色，用自然日语说指定台词。录音棚干声，无音乐、环境音、战斗音效或其他说话者。'
        '不要朗读说明，不复述参考音频中的台词，不添加文字。'+line['direction']+
        '。只说以下日语台词：'+line.get('tts_text',line['ja']))


def prompt_v3(line,reference_count):
    """Brief positive direction for a single, already-cleaned voice reference."""
    if reference_count > 1:raise ValueError('brief prompt accepts at most one reference')
    text=check_spoken_text(spoken_text(line))
    tone=str(line.get('tone') or '').strip()
    if not tone:raise ValueError('brief prompt requires tone')
    reference='保持@音频1的本人音色。' if reference_count else ''
    return reference+'录音棚单人近讲干声。用'+tone+'的语气说日语：“'+text+'”'


def prompt_v4(line,reference_count):
    """Brief direction with a required speaking anchor and optional acting sample.

    The first reference must contain normal speech; a short combat shout alone
    cannot anchor this mode. Explicit roles prevent an accidental ref reorder.
    """
    refs=line['references']
    if reference_count not in (1,2) or len(refs)!=reference_count:
        raise ValueError('anchored prompt requires one or two references')
    if refs[0].get('purpose')!='normal_timbre':
        raise ValueError('first reference must be normal_timbre')
    if reference_count==2 and refs[1].get('purpose')!='performance':
        raise ValueError('second reference must be performance')
    text=check_spoken_text(spoken_text(line))
    tone=str(line.get('tone') or '').strip()
    if not tone:raise ValueError('anchored prompt requires tone')
    note='说话音色始终以@音频1为准。'
    if reference_count==2:note+='@音频2仅参考发力和语气。'
    return note+'录音棚单人近讲干声。用'+tone+'的语气说日语：“'+text+'”'


def payload(line):
    refs=[]
    for item in line['references']:
        path=Path(item['path']);raw=path.read_bytes()
        if sha(raw)!=item['sha256']:raise ValueError('reference hash drift')
        refs.append({'audio_data':base64.b64encode(raw).decode('ascii')})
    builder={1:prompt_v1,2:prompt_v2,3:prompt_v3,4:prompt_v4}[prompt_version(line)]
    result=dict(model=MODEL,text_prompt=builder(line,len(refs)),
        audio_config=dict(format=audio_format(line),sample_rate=48000,pitch_rate=0,speech_rate=0,
                          loudness_rate=0,enable_subtitle=True),watermark={})
    if refs:result['references']=refs
    return result


def generate(line,output,key,*,opener=urllib.request.urlopen):
    role,slot=line['role'],line['slot']
    if not re.fullmatch(r'[a-z]+', role) or not re.fullmatch(r'(ally|battle|home)/[a-z0-9_]+', slot):
        raise ValueError('unsafe recording path')
    extension=audio_format(line)
    target=output/role/'raw'/(slot+'.'+extension);receipt=output/role/'receipts'/(slot+'.json')
    request_payload=payload(line)
    fingerprint=sha(json.dumps(request_payload,ensure_ascii=False,sort_keys=True).encode())
    if target.exists() and receipt.exists():
        saved=json.loads(receipt.read_bytes())
        if saved.get('request_fingerprint')==fingerprint and saved.get('sha256')==sha(target.read_bytes()):
            return dict(role=role,slot=slot,status='cached')
        raise ValueError('existing recording differs; use a separate retake output')
    if target.exists() or receipt.exists():raise ValueError('incomplete prior recording requires separate retake')
    rid=str(uuid.uuid4());started=time.monotonic()
    meta=dict(role=role,slot=slot,request_id=rid,model=MODEL,endpoint=ENDPOINT,
        request_fingerprint=fingerprint,ja=line['ja'],zh=line['zh'],direction=line.get('direction',''),
        persona=line.get('persona',''),references=line['references'],
        prompt_version=prompt_version(line),audio_format=extension)
    for name in V2_FIELDS+('tts_text',):
        if line.get(name):meta[name]=line[name]
    request=urllib.request.Request(ENDPOINT,data=json.dumps(request_payload).encode(),headers={
        'Content-Type':'application/json','X-Api-Key':key,'X-Api-Request-Id':rid},method='POST')
    try:
        with opener(request,timeout=300) as response:
            body=json.loads(response.read());meta['http_status']=response.status
        if not isinstance(body.get('audio'),str):raise ValueError('response contains no inline audio')
        raw=base64.b64decode(body['audio'],validate=True)
        if len(raw)<512:raise ValueError('audio payload is too short')
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        meta.update(status='generated',sha256=sha(raw),bytes=len(raw))
        meta['response']={name:body[name] for name in ('duration','original_duration','subtitle') if name in body}
    except urllib.error.HTTPError as exc:
        meta.update(status='failed',http_status=exc.code,error='HTTP '+str(exc.code))
        # Inspect only scalar error messages; never persist an HTTP body/header dump.
        try:
            error_body=json.loads(exc.read(16384))
            detail=error_body.get('error',error_body)
            if isinstance(detail,dict):
                for name in ('code','message'):
                    value=detail.get(name)
                    if isinstance(value,(str,int)):
                        text=str(value).replace(key,'[REDACTED]')
                        meta['api_'+name]=re.sub(r'[A-Za-z0-9_-]{24,}','[opaque]',text)[:300]
        except (ValueError,TypeError):pass
        exc.close()
    except Exception as exc:
        meta.update(status='failed',error=type(exc).__name__+': '+str(exc).replace(key,'[REDACTED]'))
    meta['elapsed_seconds']=round(time.monotonic()-started,2)
    receipt.parent.mkdir(parents=True,exist_ok=True)
    receipt.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    return {name:meta.get(name) for name in ('role','slot','status','http_status','elapsed_seconds','error','api_code','api_message')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--only',action='append',default=[])
    parser.add_argument('--workers',type=int,choices=(1,2,3),default=2)
    args=parser.parse_args();key=os.environ.pop('WF_SEED_AUDIO_KEY','')
    if not key:raise SystemExit('missing process credential')
    output=args.output.resolve()
    allowed=(Path(('${WF_ROOT}/startpoint-cn/work/codex_out/character-art-voice-20260912/voice'.replace("${WF_ROOT}", str(root_path())))),
             Path(('${WF_ROOT}/角色语音/角色重录_20260912'.replace("${WF_ROOT}", str(root_path())))))
    if not any(output==p or output.is_relative_to(p) for p in allowed):
        raise SystemExit('output outside assigned voice workspace')
    lines=json.loads(args.plan.read_text(encoding='utf-8'))
    if args.only:lines=[x for x in lines if x['role']+':'+x['slot'] in args.only]
    if not lines:raise SystemExit('empty generation selection')
    failed=0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(generate,line,output,key) for line in lines]
        for future in as_completed(futures):
            result=future.result();failed+=result['status']=='failed'
            print(json.dumps(result,ensure_ascii=False),flush=True)
    if failed:raise SystemExit(1)


if __name__=='__main__':main()
