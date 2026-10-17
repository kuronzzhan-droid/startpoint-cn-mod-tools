"""已减速泽赫尔PF单次回旋命中提高35%；保留所有时序与Lv3收尾。"""
from copy import deepcopy
from math import isclose
import zlib

import wf_dsl
from wf_character_revision import RevisionCandidate, encode_tree
from wf_seasonal7_kit_zehr import pf_program, typed_signature_problems
from wf_zehr_slow_spin import TOTAL_DAMAGE_RATIO
from wf_zantetsu_fever_revision import nodes

CODE = 'guildknight_leader_tavern'
PREVIOUS_HIT = {1: 14.625, 2: 21.375, 3: 28.35}
HIT = {level: round(value*TOTAL_DAMAGE_RATIO/1.5, 6) for level,value in PREVIOUS_HIT.items()}


def revise(tree, level):
    result = deepcopy(tree)
    area = nodes(result, 'CreateHitArea')[0]
    if area[2] != -18 or area[13] != ['SpecifyHitAreaLifetimeDirectly', {1:210,2:270,3:330}[level]] \
            or area[14] != ['CalculatedUsingMaxNumOfHits', level+2]:
        raise ValueError('expected existing 33 percent speed PF hit budget')
    attacks = nodes(area[23], 'CreateNormalAttack')
    if len(attacks) != 1 or len(attacks[0][6]) != 1:
        raise ValueError('expected exactly one spin attack')
    value = attacks[0][6][0]
    if set(value) != {'min','max'} or not isclose(value['min'],value['max']) \
            or not any(isclose(value['min'], n) for n in (PREVIOUS_HIT[level], HIT[level])):
        raise ValueError('spin multiplier baseline drift')
    attacks[0][6] = [dict(min=HIT[level], max=HIT[level])]
    problems = wf_dsl.player_side_dsl_problems(result)+typed_signature_problems(result)
    if problems:
        raise ValueError(problems)
    return result


def apply_candidate(repo, *, apply=False):
    c = RevisionCandidate(repo, repo/'work/character_packs/s7-zehr',
        character_id='159997', code_name=CODE, package_version='1.0.7',
        snapshot_key='pf_hit_20260917', evidence_name='pf-hit-20260917.json')
    for level in (1,2,3):
        logical = wf_dsl.dsl_logical(pf_program(level))
        tree = wf_dsl.parse_dsl(zlib.decompress(c.read('common',logical),-15))['tree']
        c.emit('common',logical,encode_tree(revise(tree,level)))
    return c.finish(dict(per_hit_before=PREVIOUS_HIT,per_hit_after=HIT,ratio=1.35,
                         timing_and_art_unchanged=True,finisher_unchanged=True),apply=apply)
