"""将已核验的原生双版本语音合并同步至七角色候选包；不写 live/CDN。"""
import argparse
import json
from pathlib import Path
import zipfile

import wf_mod_tool as core
import wf_seasonal7_common as common
import wf_seasonal7_manifest as manifest
import wf_seasonal7_specs as specs
import wf_seasonal7_voice as voice
from wf_seasonal7_voice_merge import sha, check_native_bindings


def install(delivery: Path, backup: Path, *, apply=False):
    data = json.loads((delivery/'合并清单.json').read_text(encoding='utf-8'))
    if data['client_capability'] != 'native' or data['fixed_slot_source'] != 'codex':
        raise ValueError('requires current native delivery with Codex fixed slots')
    plans = []
    for key in specs.all_keys():
        pack = common.S7Pack(specs.get_spec(key))
        pack.check_identity()
        plan = next(t for t in data['table_patches'] if t['role'] == key)
        speech_path = pack.pkg_path('common', voice.SPEECH_TABLE)
        rows = core.read_csv_lines(core.read_orderedmap_file_from_bytes(speech_path.read_bytes())[pack.spec.cid_s])
        if rows not in (plan['before_rows'], plan['after_rows']):
            raise ValueError(key + ': current candidate speech changed')
        entries = [e for e in data['audio'] if e['role'] == key and e['playback'] == 'native']
        if len(entries) != 40 or len({e['logical_path'] for e in entries}) != 40:
            raise ValueError('expected 40 distinct native files for ' + key)
        check_native_bindings(plan['after_rows'], {e['target_slot'] for e in entries})
        writes = []
        for entry in entries:
            source = delivery/entry['stored_file']
            raw = source.read_bytes()
            if sha(raw) != entry['stored_sha256']:
                raise ValueError('delivery audio changed: ' + str(source))
            writes.append((entry['logical_path'], raw))
        plans.append((pack, plan, writes))
    if not apply:
        return dict(applied=False, roles=[p.spec.key for p,_,_ in plans], audio=280,
                    table_keys=7, writes_live=False)
    if backup.exists():
        raise ValueError('backup destination must be new')
    backup.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(backup, 'x', zipfile.ZIP_DEFLATED) as archive:
        for pack, plan, writes in plans:
            paths = [pack.package/'manifest.json', pack.pkg_path('common',voice.SPEECH_TABLE)]
            paths += [pack.pkg_path('common',logical) for logical,_ in writes]
            paths += list(pack.evidence.rglob('*'))
            for p in paths:
                if p.is_file():
                    archive.write(p, pack.spec.key+'/'+p.relative_to(pack.workspace).as_posix())
    results = []
    for pack, plan, writes in plans:
        for logical, raw in writes:
            pack.write_pkg('common', logical, raw)
        pack.register_outputs('voice-union-native', [('common',p) for p,_ in writes])
        pack.write_flat(voice.SPEECH_TABLE, {pack.spec.cid_s: plan['after_rows']})
        pack.write_evidence('voice-union-native.json', dict(delivery=str(delivery.resolve()),
            manifest_sha256=sha((delivery/'合并清单.json').read_bytes()), native_audio=40,
            fixed_slot_source='codex', archived_claude_audio=4, client_patch=False))
        result = manifest.build(pack)
        results.append(dict(role=pack.spec.key, required=result['required'],
            manifest_errors=result['validate_manifest'], manifest_sha256=result['manifest_sha256']))
    return dict(applied=True, packages=results, audio=280, table_keys=7,
                backup=str(backup), writes_live=False)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery',required=True,type=Path)
    parser.add_argument('--backup',required=True,type=Path)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    print(json.dumps(install(args.delivery,args.backup,apply=args.apply),ensure_ascii=False))
