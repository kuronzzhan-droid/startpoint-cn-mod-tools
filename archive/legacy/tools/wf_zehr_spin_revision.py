"""从不可变原速归档重建泽赫尔PF特效；仅覆盖九个已存在的战斗资产。"""
import argparse
import hashlib
import json
from pathlib import Path
import zlib

import wf_dsl
from wf_character_revision import RevisionCandidate, encode_tree
from wf_seasonal7_kit_zehr import typed_signature_problems
from wf_zehr_slow_spin import slow_attack, slow_timeline
from wf_zehr_spin_animation import smooth_parts

CODE = 'guildknight_leader_tavern'


def apply_candidate(repo, source, *, apply=False):
    source = source.resolve()
    manifest = json.loads((source/'manifest.json').read_bytes())
    entries = {e['logical_path']:e for e in manifest['roots']['common']}
    candidate = RevisionCandidate(repo, repo/'work/character_packs/s7-zehr',
        character_id='159997', code_name=CODE, package_version='1.0.2',
        snapshot_key='spin33_range_20260917', evidence_name='spin33-range-20260917.json')

    def read(logical):
        raw = (source/'roots/common'/logical).read_bytes()
        if hashlib.sha256(raw).hexdigest() != entries[logical]['sha256']:
            raise ValueError('source archive hash mismatch: '+logical)
        return wf_dsl.parse_dsl(zlib.decompress(raw,-15))['tree']

    budgets = []
    for level, name in enumerate(('one','two','three'),1):
        logical = f'battle/action/power_flip/action/override/{CODE}_pf${CODE}_pf_lv{level}.action.dsl.amf3.deflate'
        tree, budget = slow_attack(read(logical))
        problems = wf_dsl.player_side_dsl_problems(tree)+typed_signature_problems(tree)
        if problems:
            raise ValueError(str(problems))
        candidate.emit('common',logical,encode_tree(tree))
        budgets.append(budget)
        stem = f'battle/effect/skill_unique/{CODE}/pf_spin/powerflip_attack_spin_{name}'
        for suffix in ('parts','timeline'):
            logical = stem+'.'+suffix+'.amf3.deflate'
            tree = read(logical)
            tree = smooth_parts(tree,ornament=level>1) if suffix=='parts' else slow_timeline(tree)
            candidate.emit('common',logical,encode_tree(tree))
    return candidate.finish(dict(source=str(source),speed_ratio=.33,budgets=budgets,
        native_tween=True,inner_blade_layer_levels=[2,3],texture_atlas_unchanged=True),apply=apply)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--apply',action='store_true')
    args = parser.parse_args()
    print(json.dumps(apply_candidate(Path(__file__).resolve().parents[1],args.source,
        apply=args.apply),ensure_ascii=False))
