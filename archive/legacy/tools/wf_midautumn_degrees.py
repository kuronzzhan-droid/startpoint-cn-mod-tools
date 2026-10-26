"""Build the 12-character native degree supplement; candidate writes only."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import wf_assets
import wf_client_legality as legality
import wf_degree
import wf_midautumn_common as common
import wf_midautumn_specs as specs
import wf_mod_tool as core
import wf_seasonal7_manifest as manifest
import wf_share_update_codec as codec

DEGREE = 'master/degree/degree.orderedmap'
CHARACTER = 'master/character/character.orderedmap'
TEXT = 'master/character/character_text.orderedmap'
ACTION = 'master/skill/action_skill.orderedmap'
CAS = 'master/string/custom_ability_string.orderedmap'
NAME_KEYS = {CHARACTER: '119990', TEXT: '119990', ACTION: 'lion_swordman_moon',
             CAS: 'change_skill_lion_swordman_moon'}
LEADER = '疾风同路'
SKILL = '烈焰轰鸣'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def rename_rows(logical, rows):
    """Change only the display fields; callers preserve the other keys verbatim."""
    rows = deepcopy(rows)
    if logical == CHARACTER:
        rows[0][18] = LEADER
    elif logical == TEXT:
        rows[0][4], rows[0][6], rows[0][10] = SKILL, SKILL+'＋', LEADER
    elif logical == CAS:
        old = '月下咆哮·烈焰甩尾'
        if not any(old in cell or SKILL in cell for row in rows for cell in row):
            raise ValueError('Unknown Magnus skill reference')
        rows = [[cell.replace(old, SKILL) for cell in row] for row in rows]
    else:
        raise ValueError('Unexpected name table')
    return rows


def name_operations(logical, raw):
    outer = codec.unpack(raw)
    key = NAME_KEYS[logical]
    if logical == ACTION:
        inner = codec.unpack(outer[key])
        if set(inner) != {'1', '2'}:
            raise ValueError('Unexpected Magnus skill variants')
        operations = []
        for level, before in inner.items():
            rows = codec.csv_read(before)
            rows[0][0] = SKILL + ('＋' if level == '2' else '')
            operations.append(dict(path=[key, level], before=codec.node(before),
                                   after=codec.node(codec.csv_write(rows))))
        return operations
    before = outer[key]
    rows = rename_rows(logical, codec.csv_read(before))
    return [dict(path=[key], before=codec.node(before), after=codec.node(codec.csv_write(rows)))]


def load_art(folder):
    folder = Path(folder).resolve()
    items = json.loads((folder/'plate-manifest.json').read_bytes())['plates']
    expected = {(specs.get_spec(role).cid, state): (role, 9910049+index*2+state)
                for index, role in enumerate(specs.all_keys()) for state in (0, 1)}
    if len(items) == 27:
        expected.update({(139990, state): ('kyle', 9910071+state) for state in (2, 3, 4)})
    elif len(items) != len(expected):
        raise ValueError('Expected 24 base plates, optionally with all three reviewed Kyle extras')
    seen, result = set(), []
    for item in items:
        identity = (item['character_id'], item['state'])
        if identity not in expected or identity in seen:
            raise ValueError('Unexpected or duplicate plate identity')
        role, degree_id = expected[identity]
        if (item['role'], item['degree_id']) != (role, degree_id):
            raise ValueError('Degree IDs must keep the existing 48 IDs unchanged')
        seen.add(identity)
        source = folder/item['file']
        if not source.resolve().is_relative_to(folder):
            raise ValueError('Plate escapes delivery directory')
        raw = source.read_bytes()
        if sha(raw) != item['sha256'] or wf_degree.check_plate_bytes(raw):
            raise ValueError('Plate digest or native format differs')
        sid = f"degree_mod_character_{item['character_id']}_awake{item['state']}"
        logical = 'dynamic/degree/'+sid+'.png'
        row = [sid, str(991049+degree_id-9910049), item['name']+'·'+item['title'], sid,
               f"获得条件：将{item['name']}突破至上限并升至100级；已满足者完成一次木桩练习补领。",
               '2', wf_degree.ICON_BASE_IMAGE, wf_degree.ICON_DOT_IMAGE, logical[:-4]]
        problems = legality.degree_row_problems(row, category_ids={'1','2','3','4','5','6','7','8'})
        if problems:
            raise ValueError(str(problems))
        result.append(dict(item=item, row=row, logical=logical, native=wf_assets.png_encode(raw)))
    return result


def sync_candidates(art, *, apply=False):
    entries = load_art(art)
    reports = []
    for role in specs.all_keys():
        pack = common.MAPack(specs.get_spec(role), record_sources=False)
        pack.check_identity()
        old = json.loads((pack.package/'manifest.json').read_bytes())
        for root, files in old['roots'].items():
            for file in files:
                if sha(pack.pkg_path(root, file['logical_path']).read_bytes()) != file['sha256']:
                    raise ValueError('Unrecorded candidate edit: '+role)
        own = [e for e in entries if e['item']['role'] == role]
        reports.append(dict(role=role, degrees=[e['item']['degree_id'] for e in own], applied=apply))
        if not apply:
            continue
        for e in own:
            pack.write_pkg('common', e['logical'], e['native'])
        pack.register_outputs('character-degrees', [('common', e['logical']) for e in own])
        pack.write_flat(DEGREE, {str(e['item']['degree_id']): [e['row']] for e in own})
        if role == 'magnus':
            for logical in NAME_KEYS:
                raw = pack.pkg_path('common', logical).read_bytes()
                if logical == ACTION:
                    levels = {op['path'][1]: op['after']['csv'] for op in name_operations(logical, raw)}
                    pack.write_nested(logical, NAME_KEYS[logical], levels)
                else:
                    rows = codec.csv_read(codec.unpack(raw)[NAME_KEYS[logical]])
                    pack.write_flat(logical, {NAME_KEYS[logical]: rename_rows(logical, rows)})
            pack.sync_character_mirrors()
        pack.write_evidence('character-degrees.json', dict(delivery=str(Path(art).resolve()),
                            plates=[e['item'] for e in own], native_claims=reports[-1]['degrees']))
        manifest.build(pack)
    return reports
