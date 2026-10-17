"""泽赫尔能力5：光共鸣每5次Lv3强化弹射充能5%，CT5s；精简冷却文案。"""
from copy import deepcopy
import hashlib

import wf_mod_tool as core
from wf_client_legality import client_legality_problems
from wf_character_revision import RevisionCandidate

ABILITY = 'master/ability/ability.orderedmap'
CAS = 'master/string/custom_ability_string.orderedmap'
KEY = '1599975'
CODE = 'guildknight_leader_tavern'
BASE_SHA = '9d82d792a37885a6b9491e2ca07a5d220c793262359513d29371825fdf119f36'


def revise_rows(rows):
    if len(rows) != 2 or len(rows[1]) != 126:
        raise ValueError('unexpected Zehr ability-5 shape')
    baseline = deepcopy(rows)
    baseline[1][30:32] = ['100000', '100000']
    baseline[1][35] = '0'
    if hashlib.sha256(core.write_csv_lines(baseline).encode()).hexdigest() != BASE_SHA:
        raise ValueError('Zehr ability-5 condition or effect drift')
    result = deepcopy(baseline)
    # Native trigger65 counts Lv3 power flips; 100000=one event, CT uses frames.
    result[1][30:32] = ['500000', '500000']
    result[1][35] = '300'
    if rows not in (baseline, result):
        raise ValueError('partial or unreviewed Zehr ability-5 change')
    for row in result:
        errors = client_legality_problems('ability', row)
        if errors:
            raise ValueError(str(errors))
    return result


def compact_text(text):
    return text.replace('（每5秒1次）', '（CT 5s）')


def apply_candidate(repo, *, apply=False):
    c = RevisionCandidate(repo, repo/'work/character_packs/s7-zehr',
        character_id='159997', code_name=CODE, package_version='1.0.2',
        snapshot_key='pf5_ct5_20260917', evidence_name='pf5-ct5-20260917.json')
    table = core.read_orderedmap_file_from_bytes(c.read('common', ABILITY))
    c.splice(ABILITY, {KEY: revise_rows(core.read_csv_lines(table[KEY]))})
    strings = core.read_orderedmap_file_from_bytes(c.read('common', CAS))
    changes = {}
    for slot in (1, 2, 3):
        key = f'desc_override_{CODE}_{slot}'
        rows = core.read_csv_lines(strings[key])
        revised = [[compact_text(cell) for cell in row] for row in rows]
        if rows != revised:
            changes[key] = revised
    if changes:
        c.splice(CAS, changes)
    return c.finish(dict(level=3, trigger_count=5, cooldown_frames=300,
        gauge_percent=5, light_resonance=True, preserved_other_effects=True,
        ability2_has_no_cooldown=True), apply=apply)


if __name__ == '__main__':
    import argparse, json
    from pathlib import Path
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(apply_candidate(Path(__file__).resolve().parents[1],
                                    apply=args.apply), ensure_ascii=False))
