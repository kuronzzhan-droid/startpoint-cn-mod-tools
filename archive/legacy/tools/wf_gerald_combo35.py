"""水杰拉尔能力4：保留现有共鸣/主位门槛，35连击、25%攻击上限250%、5%充能。"""
from copy import deepcopy
import hashlib

import wf_mod_tool as core
from wf_client_legality import client_legality_problems

KEY = '1299924'
TABLE = 'master/ability/ability.orderedmap'
BASE_SHA = '6385a87a5feca9fc6032125b668e3e4d4c29cf28392a04f142083f0522c121a2'


def revise(text: str) -> str:
    rows = core.read_csv_lines(text)
    if len(rows) != 2 or any(len(r) != 126 for r in rows):
        raise ValueError('unexpected Gerald ability-4 schema')
    normalized = deepcopy(rows)
    for row in normalized:
        row[30:32] = ['5000000', '5000000']
    normalized[0][34] = '8'
    normalized[1][51:53] = ['10000', '10000']
    if hashlib.sha256(core.write_csv_lines(normalized).encode()).hexdigest() != BASE_SHA:
        raise ValueError('Gerald ability-4 condition or effect drift')
    # Accept only the reviewed old state or the complete new state (idempotency).
    revised = deepcopy(normalized)
    for row in revised:
        row[30:32] = ['3500000', '3500000']
    revised[0][34] = '10'
    revised[1][51:53] = ['5000', '5000']
    if rows not in (normalized, revised):
        raise ValueError('unreviewed partial ability-4 revision')
    for row in revised:
        problems = client_legality_problems('ability', row)
        if problems:
            raise ValueError('; '.join(problems))
    return core.write_csv_lines(revised)


def apply_candidate(repo, workspace, *, apply=False):
    from wf_character_revision import RevisionCandidate
    candidate = RevisionCandidate(repo, workspace, character_id='129992',
        code_name='unicorn_lancer_rose', package_version='0.1.11',
        snapshot_key='gerald_combo35', evidence_name='gerald-combo35.json')
    before = core.read_orderedmap_file_from_bytes(candidate.read('common', TABLE))[KEY]
    candidate.splice(TABLE, {KEY: core.read_csv_lines(revise(before))})
    return candidate.finish(dict(combo=35, attack_per_trigger=25, attack_max=250,
        skill_gauge=5, preserve_existing_conditions=True), apply=apply)


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    print(json.dumps(apply_candidate(args.repo,args.workspace,apply=args.apply),ensure_ascii=False))
