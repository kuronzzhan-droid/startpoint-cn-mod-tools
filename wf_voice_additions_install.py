"""Apply reviewed additional voice deliveries without rebuilding existing character assets."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import zlib

import wf_assets
import wf_character_pack as package
import wf_character_workspace as workspace
import wf_mod_tool as core
import wf_share_update_codec as codec

SPEECH = 'master/character/character_speech.orderedmap'
sha = lambda raw: hashlib.sha256(raw).hexdigest()


def install(repo, pack_name, delivery, *, apply=False):
    root = Path(repo).resolve()
    ws = workspace.load_workspace(root/'work/character_packs'/pack_name)
    delivery = Path(delivery).resolve()
    document = json.loads((delivery/'交付清单.json').read_bytes())
    if not document['technical_checks_passed']:
        raise ValueError('unverified recording delivery')
    manifest = json.loads((ws.package_dir/'manifest.json').read_bytes())
    original = {(tier, e['logical_path']): (ws.package_dir/'roots'/tier/e['logical_path']).read_bytes()
                for tier, entries in manifest['roots'].items() for e in entries}
    for tier, entries in manifest['roots'].items():
        for entry in entries:
            if sha(original[tier, entry['logical_path']]) != entry['sha256']:
                raise ValueError('candidate manifest drift')
    outputs, added_home = {}, []
    for line in document['selection']:
        if line['code'] != ws.code_name:
            raise ValueError('delivery character mismatch')
        if not re.fullmatch(r'(home|battle|ally)/[A-Za-z0-9_]+', line['slot']):
            raise ValueError('invalid native voice slot')
        logical = f"character/{ws.code_name}/voice/{line['slot']}.mp3"
        p = (delivery/line['files']['native']['path']).resolve()
        if not p.is_relative_to(delivery):
            raise ValueError('delivery path escape')
        raw = p.read_bytes()
        if sha(raw) != line['files']['native']['sha256']:
            raise ValueError('recording changed after review')
        if wf_assets.mp3_encode(wf_assets.mp3_decode(raw)) != raw:
            raise ValueError('native MP3 roundtrip failed')
        prior = original.get(('common', logical))
        if prior is not None and prior != raw:
            raise ValueError('addition would overwrite an existing voice')
        outputs['common', logical] = raw
        if line['slot'].startswith('home/'):
            added_home.append(['0', '2', '', line['zh'], line['slot']])
    trim_path = delivery/'trim-receipt.json'
    if trim_path.exists():
        trim = json.loads(trim_path.read_bytes())
        if not re.fullmatch(r'battle/[A-Za-z0-9_]+', trim['slot']):
            raise ValueError('invalid trimmed battle slot')
        key = 'common', f"character/{ws.code_name}/voice/{trim['slot']}.mp3"
        raw = (delivery/trim['native_path']).read_bytes()
        if sha(raw) != trim['after_native_sha256'] or sha(original[key]) not in (
                trim['before_native_sha256'], trim['after_native_sha256']):
            raise ValueError('trim preimage differs')
        outputs[key] = raw
    if added_home:
        flat = codec.unpack(original['common', SPEECH]);rows = codec.node(flat[str(ws.character_id)])['csv']
        for row in added_home:
            matches = [r for r in rows if r[4] == row[4]]
            if matches and matches != [row]:
                raise ValueError('home subtitle path already used')
            if not matches:rows.append(row)
        flat[str(ws.character_id)] = zlib.compress(core.write_csv_lines(rows).rstrip('\n').encode())
        outputs['common', SPEECH] = codec.pack(flat)
    report = dict(character_id=ws.character_id, code=ws.code_name, files=len(outputs),
                  additions=len(document['selection']), delivery=str(delivery),
                  delivery_sha256=sha((delivery/'交付清单.json').read_bytes()), applied=apply,
                  runtime_verified=False,
                  requires_ready_router_update=any(x['slot'].startswith('battle/skill_ready')
                                                   for x in document['selection']),
                  rebuild_command=f'python mod-tools/wf_voice_additions_install.py --pack {pack_name} --delivery "{delivery}" --apply')
    report['changed'] = [dict(root=tier, logical_path=logical,
                             before_sha256=sha(original[tier, logical]) if (tier, logical) in original else None,
                             after_sha256=sha(raw)) for (tier, logical), raw in outputs.items()]
    for (tier, logical), raw in outputs.items():
        entries = manifest['roots'][tier]
        entry = next((e for e in entries if e['logical_path'] == logical), None)
        if entry is None:
            entry = dict(logical_path=logical);entries.append(entry)
        entry.update(sha256=sha(raw), size=len(raw))
        entries.sort(key=lambda e: e['logical_path'])
    # Keep earlier additions reproducible when the same character receives
    # another delivery. The latest report alone loses the older rebuild input.
    history = manifest['snapshot'].setdefault('voice_addition_history', [])
    previous = manifest['snapshot'].get('voice_additions_20260924')
    if previous and previous['delivery_sha256'] == report['delivery_sha256']:
        prior_outputs = {(x['root'], x['logical_path']): x['after_sha256'] for x in previous['changed']}
        if prior_outputs == {(tier, logical): sha(raw) for (tier, logical), raw in outputs.items()}:
            report = {**previous, 'applied': apply}
    for item in (previous, report):
        if item and not any(x['delivery_sha256'] == item['delivery_sha256'] for x in history):
            history.append(item)
    manifest['snapshot']['voice_additions_20260924'] = report
    manifest['qa'].update(release_ready=False, workspace_input_sha256='')
    if apply:
        for (tier, logical), raw in outputs.items():
            p = ws.package_dir/'roots'/tier/logical;p.parent.mkdir(parents=True, exist_ok=True);p.write_bytes(raw)
        (ws.package_dir/'manifest.json').write_bytes(package.canonical_manifest_bytes(manifest))
        (ws.evidence_dir/'voice-additions-20260924.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf8')
        (ws.evidence_dir/'voice-addition-history.json').write_text(json.dumps(history,ensure_ascii=False,indent=2),'utf8')
        assert all((ws.package_dir/'roots'/tier/logical).read_bytes() == raw
                   for (tier, logical), raw in original.items() if (tier, logical) not in outputs)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack', required=True)
    parser.add_argument('--delivery', type=Path, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(install(Path(__file__).resolve().parents[1], args.pack,
                             args.delivery, apply=args.apply), ensure_ascii=False))
