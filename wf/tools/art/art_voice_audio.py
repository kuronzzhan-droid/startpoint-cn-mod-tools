"""本轮合成语音的原生编码与客观音频 QC，保留完整表演时序。"""
from __future__ import annotations

from wf.paths import root_path

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
import wf_assets
import wf_voice_gate as gate
from wf.art.audio_probe import metadata, pcm


def sha(data):
    return hashlib.sha256(data).hexdigest()


def amplitude(samples):
    values = np.asarray(samples, dtype=np.float64).reshape(-1)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError('empty or non-finite decoded audio')
    absolute = np.abs(values)
    active = np.flatnonzero(absolute > 0.004)
    return dict(samples=len(values), seconds=len(values) / 44100,
        rms_dbfs=20 * float(np.log10(max(float(np.sqrt(np.mean(values ** 2))), 1e-12))),
        peak=float(absolute.max()), clipped_fraction=float(np.mean(absolute >= 0.999)),
        leading_quiet_seconds=float(active[0] / 44100) if len(active) else len(values) / 44100,
        trailing_quiet_seconds=float((len(values) - 1 - active[-1]) / 44100) if len(active) else len(values) / 44100)


def convert(source, target, *, ffmpeg, ffprobe, code, slot):
    source, target = Path(source), Path(target)
    source_sha = sha(source.read_bytes())
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('standard recording already exists; inspect receipt or choose a retake')
    temporary = target.with_suffix('.tmp.mp3')
    if temporary.exists():
        raise ValueError('stale conversion output')
    source_meta = metadata(source, Path(ffprobe))
    if source_meta['streams'][0]['channels'] not in (1, 2):
        raise ValueError('unreviewed source channel layout')
    # New performances receive consistent game loudness. There is no silence
    # removal, time stretch, concatenation, or content-dependent cut.
    command = [str(ffmpeg), '-v', 'error', '-i', str(source), '-map', '0:a:0',
        '-map_metadata', '-1', '-vn', '-af', 'loudnorm=I=-18:TP=-2:LRA=9',
        '-c:a', 'libmp3lame', '-ar', '44100', '-ac', '1', '-b:a', '96k',
        '-minrate', '96k', '-maxrate', '96k', '-write_xing', '1',
        '-id3v2_version', '0', str(temporary)]
    subprocess.run(command, check=True, capture_output=True)
    # Short generated calls can overshoot the requested loudnorm true peak
    # after lossy encoding. Measure the real decoded MP3, then attenuate the
    # entire performance uniformly when needed; do not clip or trim samples.
    peak_guard_gain = 1.0
    first_peak = amplitude(pcm(temporary, Path(ffmpeg)))['peak']
    if first_peak > 0.90:
        peak_guard_gain = 0.80 / first_peak
        guarded = list(command)
        guarded.insert(1, '-y')
        guarded[guarded.index('-af') + 1] += f',volume={peak_guard_gain:.12f}'
        subprocess.run(guarded, check=True, capture_output=True)
    standard = temporary.read_bytes()
    stored = wf_assets.mp3_encode(standard)
    voice = gate.VoiceFile(code, slot, stored)
    info = gate.probe(stored)
    findings = [asdict(x) for x in gate.check_voice_set([voice])]
    # The second native ready slot shares the ready duration budget.
    family = 'skill_ready' if slot == 'battle/matched_skill_ready' else gate.slot_family(slot)
    limit = gate.OFFICIAL_DURATION[family][-1] if family else None
    before, after = amplitude(pcm(source, Path(ffmpeg))), amplitude(pcm(temporary, Path(ffmpeg)))
    hard = [x for x in findings if x['level'] == 'error']
    # A singleton numbered slot can look unreachable to the set-level gate;
    # the integration module separately validates each complete character set.
    hard = [x for x in hard if x['rule'] != 'index_gap_unreachable']
    if hard or not info['xing'] or info['tail'] != 0 or wf_assets.mp3_decode(stored) != standard:
        raise ValueError(f'native audio container validation failed: {hard}')
    if abs(before['samples'] - after['samples']) > 128:
        raise ValueError('conversion changed performance duration')
    if after['clipped_fraction'] > 0 or after['peak'] >= 0.999:
        raise ValueError('converted performance clips')
    if limit is not None and info['duration'] > limit:
        raise ValueError(f'{slot} exceeds official family duration: {info["duration"]:.3f} > {limit}')
    temporary.replace(target)
    return stored, dict(source=str(source), source_sha256=source_sha,
        standard=str(target), standard_sha256=sha(standard), storage_sha256=sha(stored),
        source_metadata=source_meta, codec=info, source_pcm=before, converted_pcm=after,
        sample_delta=after['samples']-before['samples'], sample_delta_limit=128,
        family=family, official_max_seconds=limit, storage_roundtrip_equal=True,
        processing='loudnorm I=-18 TP=-2 LRA=9; measured uniform peak attenuation; mono 44100 Hz 96kbps CBR',
        pre_guard_peak=first_peak, peak_guard_gain=peak_guard_gain,
        no_trim_no_speed_no_concatenation=True, findings=findings)


def process_available(plan, recordings, output, ffmpeg, ffprobe):
    report=[]
    for line in plan:
        role, slot = line['role'], line['slot']
        source=recordings/role/'raw'/(slot+'.mp3')
        receipt=recordings/role/'receipts'/(slot+'.json')
        if not source.exists() or not receipt.exists():
            continue
        generated=json.loads(receipt.read_bytes())
        if generated.get('status')!='generated' or generated.get('sha256')!=sha(source.read_bytes()):
            raise ValueError('unverified source recording')
        target=output/role/'standard'/(slot+'.mp3')
        qc=output/role/'qc'/(slot+'.json')
        if qc.exists():
            item=json.loads(qc.read_bytes())
            if item['source_sha256']!=sha(source.read_bytes()) or item['standard_sha256']!=sha(target.read_bytes()):
                raise ValueError('QC source or standard recording drift')
        else:
            from wf_art_voice_lines import ROLES
            _stored,item=convert(source,target,ffmpeg=ffmpeg,ffprobe=ffprobe,code=ROLES[role][1],slot=slot)
            qc.parent.mkdir(parents=True,exist_ok=True)
            qc.write_text(json.dumps(item,ensure_ascii=False,indent=2),encoding='utf-8')
        report.append(dict(role=role,slot=slot,seconds=item['codec']['duration'],peak=item['converted_pcm']['peak']))
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--recordings',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--ffmpeg',type=Path,required=True)
    p.add_argument('--ffprobe',type=Path,required=True)
    a=p.parse_args()
    allowed=Path(('${WF_ROOT}/角色语音/角色重录_20260912'.replace("${WF_ROOT}", str(root_path()))))
    if not a.output.resolve().is_relative_to(allowed):
        raise SystemExit('output outside assigned voice directory')
    report=process_available(json.loads(a.plan.read_bytes()),a.recordings,a.output,a.ffmpeg,a.ffprobe)
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'qc-summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(processed=len(report),max_peak=max((x['peak'] for x in report),default=0))))


if __name__=='__main__':main()
