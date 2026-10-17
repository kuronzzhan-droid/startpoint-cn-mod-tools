"""Bind compiled Studio media to an isolated, flow-managed native candidate."""
from __future__ import annotations

from wf.paths import root_path

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import wf_seasonal7_common as C
import wf_seasonal7_tables as T
import wf_seasonal7_manifest as manifest

STUDIO = Path(('${WF_ROOT}/tool-projects/StarPoint-Character-Studio'.replace("${WF_ROOT}", str(root_path()))))
LANDMARKS = {
    'ghandagoza': [dict(face=[614, 306], eyes=[614, 269], square_height=520, head_height=420),
                   dict(face=[778, 571], eyes=[778, 541], square_height=520, head_height=380)],
    'soriz': [dict(face=[553, 427], eyes=[553, 394], square_height=470, head_height=500),
              dict(face=[670, 294], eyes=[670, 264], square_height=460, head_height=360)],
}


def native_timeline(tree, *, special):
    """Compiler only exports sequences; native battle needs body and HP anchors."""
    tree = dict(tree)
    tree.update(points=[], circles=[], sounds=[], rectangles=[], matrices=[])
    if not special:
        frames = [dict(begin=s['begin']+1, data=[dict(x=0, y=0, r=8.3)]
                       if s['name'] in ('neutral', 'walk_front', 'walk_back') else [])
                  for s in tree['sequences']]
        tree['circles'] = [dict(path='unit_body', frames=frames)]
        tree['points'] = [dict(path='hp_gauge', frames=[dict(begin=1, data=[dict(x=0, y=-10)])])]
    names = {s['name'] for s in tree['sequences']}
    required = {'special_land', 'special_pose'} if special else {
        'neutral', 'walk_front', 'walk_back', 'skill_ready', 'kachidoki',
        'into_coffin', 'ghost_raise', 'ghost_neutral', 'revive'}
    if not required <= names:
        raise ValueError(f'Missing native animation sequences: {required-names}')
    return tree


def bind_voices(pack, store, project):
    from audio_compile import encoded_sound
    counters, speech, report = Counter(), [], []
    known = {'join', 'evolution', 'home', 'skill_voice', 'skill_ready',
             'power_flip', 'outhole', 'battle_start', 'win', 'attack'}
    for voice in project['voices']:
        usage = voice['usage']
        if usage not in known:
            raise ValueError(f'Unmapped voice usage: {usage}')
        index = counters[usage]
        counters[usage] += 1
        if usage in ('join', 'evolution'):
            if index:
                raise ValueError('Multiple fixed ally voice slots')
            slot = 'ally/' + usage
            speech.append(['2', '', '', voice['text'], slot] if usage == 'join' else
                          ['1', '', '1', voice['text'], slot])
        elif usage == 'home':
            slot = f'home/home_{index}'
            speech.append(['0', '2', '', voice['text'], slot])
        elif usage == 'skill_ready':
            if index:
                raise ValueError('Multiple fixed skill ready slots')
            slot = 'battle/skill_ready'
        else:
            stem = 'skill' if usage == 'skill_voice' else usage
            slot = f'battle/{stem}_{index}'
        logical = f'character/{pack.spec.code}/voice/{slot}.mp3'
        raw = encoded_sound(store, project, voice['asset'])
        pack.write_asset('common', logical, raw, owner='voice')
        report.append(dict(slot=slot, sha256=hashlib.sha256(raw).hexdigest(), source=voice['asset']))
    if not all(counters[s] for s in ('join', 'evolution', 'home', 'skill_ready', 'skill_voice')):
        raise ValueError('Required voice slot is missing')
    planned = {f"character/{pack.spec.code}/voice/{x['slot']}.mp3" for x in report}
    root = pack.package / 'roots/common'
    for path in (root/f'character/{pack.spec.code}/voice').rglob('*.mp3'):
        if path.relative_to(root).as_posix() not in planned:
            assert path.resolve().is_relative_to(root.resolve())
            path.unlink()  # isolated donor scaffold only; never touches live or uploaded archive
    pack.write_flat(T.SPEECH, {pack.spec.cid_s: speech})
    char = C.csv_split(pack.pkg_flat(T.CHAR)[pack.spec.cid_s])[0]
    char[9:17] = ['(None)', '', '', '', '', '', '', '']
    char[4], char[7] = ('Human,Beast' if pack.spec.code == 'ghandagoza' else 'Human'), 'Male'
    pack.write_flat(T.CHAR, {pack.spec.cid_s: [char]})
    result = dict(status='candidate', mode='authored-original-voice',
                  summary='Both evolution states, join and evolution have native voice bindings',
                  files=report, speech=speech)
    pack.write_evidence('voice-report.json', result)
    return result


def selected_portraits(evidence):
    """Load an author's pinned originals; refuse drift or paths outside evidence."""
    evidence = Path(evidence).resolve()
    selection = evidence / 'portrait-selection.json'
    if not selection.is_file():
        return None
    entries = json.loads(selection.read_text(encoding='utf-8'))['states']
    if len(entries) != 2:
        raise ValueError('Portrait selection requires both evolution states')
    result = []
    for entry in entries:
        path = (evidence / entry['file']).resolve()
        if not path.is_relative_to(evidence):
            raise ValueError('Selected portrait must stay inside candidate evidence')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry['sha256']:
            raise ValueError('Selected portrait hash changed')
        result.append((raw, entry['landmarks']))
    return result


def build(pack, source):
    if str(STUDIO) not in sys.path:
        pass  # Imports resolve from this checkout/package, not external source copies.
    from studio_core import ProjectStore
    import wf_seasonal7_art as art
    source = Path(source)
    entry = next(x for x in json.loads((source/'inventory.json').read_text(encoding='utf-8'))
                 if x['code'] == pack.spec.code)
    store = ProjectStore(source/'studio-projects')
    project = store.load(entry['id'])
    outputs = []
    with zipfile.ZipFile(source/f'{pack.spec.code}-compiled.zip') as archive:
        for name in archive.namelist():
            if not name.startswith('compiled/common/'):
                continue
            logical = name[len('compiled/common/'):]
            if not (logical.startswith(f'character/{pack.spec.code}/pixelart/') or
                    logical.startswith(f'battle/effect/skill_unique/{pack.spec.code}/') or
                    logical.startswith(f'sound_effect/character_studio/{pack.spec.code}/')):
                continue
            if '..' in Path(logical).parts:
                raise ValueError('Unsafe compiled asset path')
            raw = archive.read(name)
            if '/pixelart/' in logical and logical.endswith('.timeline.amf3.deflate'):
                raw = C.amf_bytes(native_timeline(C.amf_parse(raw), special='/special.' in logical))
            pack.write_asset('common', logical, raw, owner='studio')
            outputs.append(logical)
    masters = pack.evidence_path('masters')
    masters.mkdir(parents=True, exist_ok=True)
    selected = selected_portraits(pack.evidence)
    landmarks = LANDMARKS[pack.spec.code] if selected is None else [x[1] for x in selected]
    for level, key in enumerate(('base', 'evolved')):
        raw = store.asset_bytes(project, project['portraits'][key]) if selected is None else selected[level][0]
        (masters/f'{pack.spec.key}-{level}.png').write_bytes(raw)
    manifest.build(pack)
    art_report = art.build(pack, landmarks, source_dir=masters, apply=True, headshots=True)
    voice_report = bind_voices(pack, store, project)
    pack.sync_character_mirrors()
    pack.write_evidence('pixel-report.json', dict(status='candidate', summary='All authored native action slots retained', files=outputs))
    manifest.build(pack)
    return dict(source_sha256=entry['sha256'], art=art_report, voice=voice_report, assets=outputs,
                runtime_verified=False, gameplay_complete=False)
