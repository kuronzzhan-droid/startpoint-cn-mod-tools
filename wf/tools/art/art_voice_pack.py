"""已审核录音的离线接入；返回自有 MP3/字幕，不写候选、store 或发布链。"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import re

import wf_assets
import wf_voice_gate as gate
from wf_art_voice_lines import ROLES
from wf_art_voice_enablement import rows as enablement_rows

SPEECH_TABLE = 'master/character/character_speech.orderedmap'
EXPECTED_COUNTS = dict(bianca=22, celtie=23, nephtim=24, lion=12, ginovi=21)


def validate_plan(plan):
    counts={role:0 for role in ROLES}
    slots={role:set() for role in ROLES}
    for row in plan:
        role, slot=row['role'], row['slot']
        if (role not in ROLES or not isinstance(slot, str)
                or not re.fullmatch(r'(ally|battle|home)/[a-z0-9_]+', slot)
                or slot in slots[role] or not row['ja'] or not row['zh']):
            raise ValueError('unknown role, duplicate slot or missing subtitle')
        slots[role].add(slot);counts[role]+=1
    if counts != EXPECTED_COUNTS:
        raise ValueError('incomplete full recording set')
    for role, items in slots.items():
        if not {'battle/skill_ready','battle/matched_skill_ready',
                *(f'battle/skill_{i}' for i in range(4))}.issubset(items):
            raise ValueError('missing actual native ready or skill slot')
        if any(gate.engine_reachable(sorted(items)).values()):
            raise ValueError('unreachable native numbered voice')
    return slots


def speech_rows(original, plan):
    """只替换已有 Home/Join/Evolution 的中文；保留解锁和觉醒条件。

    原生没有 battle 类型 CharacterSpeechValues；战斗中文留在交付文本
    manifest，不伪造会令客户端读表失败的新 speech 类型。
    """
    validate_plan(plan)
    result={}
    for role, (cid, _code, _persona) in ROLES.items():
        replacements={x['slot']:x['zh'] for x in plan
                      if x['role']==role and not x['slot'].startswith('battle/')}
        rows=deepcopy(original[cid]);found=set()
        for row in rows:
            if len(row)!=5:
                raise ValueError('unreviewed CharacterSpeechValues schema')
            if row[4] in replacements:
                if row[4] in found:
                    raise ValueError('ambiguous duplicate speech slot')
                row[3]=replacements[row[4]];found.add(row[4])
        if found != set(replacements):
            raise ValueError('a generated Home/Ally recording lacks native subtitle binding')
        result[cid]=rows
    return result


def assets(plan, standard_loader):
    """standard_loader(role, slot) -> 已 QC 的标准 MP3 bytes；返回 common 资产。"""
    validate_plan(plan)
    output={};voices=[];hashes=set()
    for line in plan:
        role, slot=line['role'],line['slot'];code=ROLES[role][1]
        standard=standard_loader(role,slot)
        digest=hashlib.sha256(standard).hexdigest()
        if digest in hashes:
            raise ValueError('different lines share one recording')
        hashes.add(digest)
        stored=wf_assets.mp3_encode(standard)
        if wf_assets.mp3_decode(stored)!=standard:
            raise ValueError('native MP3 storage roundtrip failed')
        voice=gate.VoiceFile(code,slot,stored);voices.append(voice)
        if slot=='battle/matched_skill_ready' and gate.probe(stored)['duration']>gate.OFFICIAL_DURATION['skill_ready'][-1]:
            raise ValueError('second ready exceeds the native ready duration budget')
        output['common',f'character/{code}/voice/{slot}.mp3']=stored
    errors=[asdict(x) for x in gate.check_voice_set(voices) if x.level=='error']
    if errors:
        raise ValueError(f'full-set voice gate failed: {errors}')
    return output


def metadata(plan):
    slots=validate_plan(plan)
    return dict(voice_count=sum(map(len,slots.values())),counts=dict(EXPECTED_COUNTS),
        language='ja',home_ally_subtitles='zh-CN',battle_subtitles='delivery manifest only',
        numbered_skills='four distinct files; native sequential enumeration then random choice',
        ready='two distinct native files; condition routing supplied by wf_art_voice_routes',
        real_actor_imitation=False,voice_actor='AI 合成配音',
        native_enablement='enablement_rows: CV label and exact character voice exclusions',
        new_client_capabilities=[])
