"""菲莉亚与泽赫尔出手手感修订：仅回写四个主动技能候选资产。"""
import json
from pathlib import Path
import zlib

import wf_dsl
from wf_character_revision import RevisionCandidate, encode_tree
from wf_philia_wind_revision import revise_skill as philia
from wf_zehr_skill_feel import revise_skill as zehr
from wf_seasonal7_kit_philia import dsl_gates, dsl_gate_failures


def apply_candidate(repo, *, apply=False):
    results = {}
    for key, cid, code, transform in (
        ('philia', '159996', 'wind_oracle_yukata', philia),
        ('zehr', '159997', 'guildknight_leader_tavern', zehr),
    ):
        candidate = RevisionCandidate(repo, repo/f'work/character_packs/s7-{key}',
            character_id=cid, code_name=code, package_version='1.0.4',
            snapshot_key='skill_feel_20260917', evidence_name='skill-feel-20260917.json')
        gates = []
        for level in (1, 2):
            logical = f'battle/action/skill/action/rare5/{code}${code}_{level}.action.dsl.amf3.deflate'
            old = wf_dsl.parse_dsl(zlib.decompress(candidate.read('common', logical), -15))['tree']
            tree = transform(old)
            report = dsl_gates(tree)
            if errors := dsl_gate_failures(report):
                raise ValueError(f'{code}/{level}: {errors}')
            gates.append(report)
            candidate.emit('common', logical, encode_tree(tree))
        results[key] = candidate.finish(dict(stop_frames=15,
            blade_speed=12 if key == 'philia' else None,
            repeated_hit_stock=key == 'philia', gates=gates), apply=apply)
    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(apply_candidate(Path(__file__).resolve().parents[1], apply=args.apply), ensure_ascii=False))
