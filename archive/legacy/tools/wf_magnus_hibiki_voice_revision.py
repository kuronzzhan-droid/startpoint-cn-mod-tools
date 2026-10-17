"""Install selected character recordings into their candidates only."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

import wf_assets
import wf_midautumn_common as common
import wf_midautumn_specs as specs
import wf_mod_tool as core
import wf_seasonal7_manifest as manifest
import wf_seasonal7_voice as voice
import wf_voice_gate as gate

ROLES = {'magnus': ('119990', 'lion_swordman_moon', 12, 6, 8, 10),
         'hibiki': ('169988', 'psychic_teleport_moon', 8, 3, 6, 6),
         'kyle': ('139990', 'kyle_moon', 12, 6, 12, 8),
         'rolf': ('149986', 'black_wolf_knight_moon', 6, 2, 4, 2)}
SPEECH = 'master/character/character_speech.orderedmap'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def expected_slots(role):
    _, _, homes, ready, skills, flips = ROLES[role]
    prepared = ['battle/skill_ready', 'battle/matched_skill_ready']
    if ready >= 3:
        prepared += ['battle/skill_ready_alt_1']
    if ready == 6:
        prepared += ['battle/skill_ready_alt_2', 'battle/skill_ready_alt_3',
                     'battle/matched_skill_ready_alt_1']
    starts, wins = {'kyle': (4, 2), 'rolf': (2, 2)}.get(role, (3, 3))
    return {'ally/join', 'ally/evolution', *prepared,
            *(f'home/home_{i}' for i in range(homes)),
            *(f'battle/skill_{i}' for i in range(skills)),
            *(f'battle/power_flip_{i}' for i in range(flips)),
            *(f'battle/battle_start_{i}' for i in range(starts)),
            *(f'battle/win_{i}' for i in range(wins)),
            *(f'battle/outhole_{i}' for i in range(2))}


def speech_rows(before, lines):
    """Preserve existing unlocks and order; append only new native Home entries."""
    desired = {x['slot']: x['zh'] for x in lines if not x['slot'].startswith('battle/')}
    rows, seen = deepcopy(before), set()
    for row in rows:
        if len(row) != 5 or row[4] in seen or row[4] not in desired:
            raise ValueError('unknown or duplicate existing speech binding')
        expected_kind = '0' if row[4].startswith('home/') else '2' if row[4] == 'ally/join' else '1'
        if row[0] != expected_kind:
            raise ValueError('existing speech kind differs from its slot')
        row[3] = desired[row[4]]
        seen.add(row[4])
    missing = set(desired) - seen
    if any(not re.fullmatch(r'home/home_\d+', slot) for slot in missing):
        raise ValueError('cannot invent an acquisition or evolution binding')
    homes = [r for r in before if r[0] == '0']
    if not homes or any(r[:3] != ['0', '2', ''] for r in homes):
        raise ValueError('new home unlocks require the established both-evolutions baseline')
    for slot in sorted(missing, key=lambda s: int(s.rsplit('_', 1)[1])):
        rows.append(['0', '2', '', desired[slot], slot])
    for row in rows:
        voice.check_subtitle(row[3])
    return rows


def safe_file(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('delivery member escapes its root')
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('missing or escaped delivery file')
    return path


def delivery_entries(document):
    """Accept either saved delivery format without changing the selected audio."""
    if isinstance(document, list):
        if len(document) != 79:
            raise ValueError('expected the complete 79-line Magnos/Hibiki delivery')
        return ('magnus', 'hibiki'), document
    if not isinstance(document, dict):
        raise ValueError('expected a complete character delivery')
    role = document.get('role', 'kyle')
    totals = {'kyle': 48, 'rolf': 22}
    if role not in totals or document.get('count') != totals[role]:
        raise ValueError('unknown role or incomplete character delivery')
    selected = document.get('selection', [])
    if len(selected) != totals[role]:
        raise ValueError('character selection is incomplete')
    entries = []
    for line in selected:
        files = line['files']
        entries.append({**line, 'role': role, 'code': ROLES[role][1],
                        'mp3': files['standard']['path'], 'sha256': files['standard']['sha256'],
                        'native_file': files['native']['path'],
                        'native_sha256': files['native']['sha256'], 'qc': files['qc']['path']})
    return (role,), entries


def load_delivery(delivery):
    delivery = Path(delivery).resolve()
    roles, entries = delivery_entries(json.loads((delivery/'交付清单.json').read_bytes()))
    grouped = {r: [] for r in roles}
    assets = {r: {} for r in roles}
    seen, recordings = set(), set()
    for entry in entries:
        role, slot = entry['role'], entry['slot']
        if role not in grouped or slot not in expected_slots(role) or (role, slot) in seen:
            raise ValueError('unexpected or duplicate role/voice slot')
        seen.add((role, slot))
        if not entry['ja'] or not entry['zh'] or entry['code'] != ROLES[role][1]:
            raise ValueError('wrong character identity or empty subtitle')
        standard = safe_file(delivery, entry['mp3']).read_bytes()
        native = safe_file(delivery, entry['native_file']).read_bytes()
        if sha(standard) != entry['sha256'] or wf_assets.mp3_decode(native) != standard:
            raise ValueError('reviewed delivery digest or native roundtrip differs')
        if entry.get('native_sha256', sha(native)) != sha(native):
            raise ValueError('selected native recording changed')
        if sha(standard) in recordings:
            raise ValueError('distinct slots reuse the same recording')
        recordings.add(sha(standard))
        qc = json.loads(safe_file(delivery, entry['qc']).read_bytes())
        info = gate.probe(native)
        if (not info['ok'] or not info['cbr'] or not info['obfuscated'] or info['tail']
                or info['srate'] != [44100] or info['channels'] != [1] or info['bitrate'] != [96]
                or qc['standard_sha256'] != sha(standard) or qc['storage_sha256'] != sha(native)
                or qc['loudness_status'] != 'ok'):
            raise ValueError('voice format or reviewed mastering differs')
        grouped[role].append(entry)
        assets[role][f"character/{entry['code']}/voice/{slot}.mp3"] = native
    for role, lines in grouped.items():
        if {x['slot'] for x in lines} != expected_slots(role):
            raise ValueError('voice pool is incomplete')
        # The saved gate models the old fixed ready slots. Extra ready paths are
        # supplied as requested for the user's current multi-voice client; they
        # are not evidence of device-level reachability. Check numbered pools here.
        numbered = [x['slot'] for x in lines if 'ready' not in x['slot']]
        if any(gate.engine_reachable(numbered).values()):
            raise ValueError('numbered voice pool has a gap')
    return grouped, assets


def install(delivery, *, apply=False, roles=None):
    delivery = Path(delivery).resolve()
    grouped, assets = load_delivery(delivery)
    requested = set(grouped if roles is None else roles)
    if not requested or not requested <= set(grouped):
        raise ValueError('unknown or empty requested roles')
    plans = []
    for role, lines in grouped.items():
        if role not in requested:
            continue
        pack = common.MAPack(specs.get_spec(role), record_sources=False)
        pack.check_identity()
        prior = json.loads((pack.package/'manifest.json').read_bytes())
        original = {(tier, e['logical_path']): pack.pkg_path(tier, e['logical_path']).read_bytes()
                    for tier, entries in prior['roots'].items() for e in entries}
        for tier, entries in prior['roots'].items():
            for e in entries:
                if sha(original[tier, e['logical_path']]) != e['sha256']:
                    raise ValueError('candidate has unrecorded changes')
        cid = ROLES[role][0]
        before = core.read_orderedmap_file_from_bytes(original['common', SPEECH])
        rows = speech_rows(core.read_csv_lines(before[cid]), lines)
        plans.append((role, pack, lines, original, rows))
    reports = []
    for role, pack, lines, original, rows in plans:
        report = dict(role=role, voice_count=len(lines), home_count=ROLES[role][2],
                      character_id=ROLES[role][0], code=ROLES[role][1],
                      speech_before=core.read_csv_lines(core.read_orderedmap_file_from_bytes(
                          original['common', SPEECH])[ROLES[role][0]]), speech_after=rows,
                      readiness='all requested files supplied; current-client trigger not device-tested',
                      client_patch=False, writes_live=False, applied=apply)
        if apply:
            for logical, raw in assets[role].items():
                pack.write_pkg('common', logical, raw)
            pack.register_outputs('voice-20260923', [('common', p) for p in assets[role]])
            pack.write_flat(SPEECH, {ROLES[role][0]: rows})
            report['source_manifest_sha256'] = sha((delivery/'交付清单.json').read_bytes())
            report['source_delivery'] = str(delivery)
            report['rebuild_command'] = 'python mod-tools/wf_magnus_hibiki_voice_revision.py --delivery '+str(delivery)+' --apply'
            pack.write_evidence('voice-20260923.json', report)
            pack.write_evidence('voice-20260923-lines.json', lines)
            # The regular --script pack command reloads this hash-bound delivery.
            script = pack.batch_dir/'rework2/voice/scripts'/(role+'.json')
            source = json.loads(script.read_bytes())
            source['lines'] = [{k: x[k] for k in ('slot', 'ja', 'zh', 'tts_text', 'theme', 'tone', 'direction', 'performance')
                                if k in x} for x in lines]
            source['accepted_delivery'] = dict(path=str(delivery),
                                               manifest_sha256=report['source_manifest_sha256'],
                                               rebuild_command=report['rebuild_command'])
            script.write_text(json.dumps(source, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            built = manifest.build(pack)
            report['manifest_build'] = built
            allowed = {('common', SPEECH), *(('common', p) for p in assets[role])}
            for key, raw in original.items():
                if key not in allowed and pack.pkg_path(*key).read_bytes() != raw:
                    raise AssertionError('non-voice candidate data changed')
            old_rows = core.read_orderedmap_raw_rows_from_bytes(original['common', SPEECH], SPEECH)
            now = core.read_orderedmap_raw_rows_from_bytes(pack.pkg_path('common', SPEECH).read_bytes(), SPEECH)
            previous, current = dict(zip(old_rows.keys, old_rows.rows)), dict(zip(now.keys, now.rows))
            if any(current[k] != v for k, v in previous.items() if k != ROLES[role][0]):
                raise AssertionError('foreign character speech row changed')
        reports.append(report)
    return dict(applied=apply, writes_live=False,
                voices=sum(len(grouped[r]) for r in requested), packages=reports)


def install_accepted(role, source, *, apply=False):
    accepted = source['accepted_delivery']
    delivery = Path(accepted['path']).resolve()
    if sha((delivery/'交付清单.json').read_bytes()) != accepted['manifest_sha256']:
        raise ValueError('accepted delivery changed; select and synchronize the new source first')
    return install(delivery, apply=apply, roles=[role])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(install(args.delivery, apply=args.apply), ensure_ascii=False))
