"""引擎点火按整招增加基础倍率；入口快照，按满级基础伤害占比分摊。"""
from copy import deepcopy
from math import isclose

from wf_dsl import iter_dsl_commands

UID = 11999001
VARIABLE = 11999005
MAX_LAYERS = 99
PER_CAST = 5.0


def _attacks(node, areas=()):
    if not isinstance(node, list):
        return
    if node and node[0] == 'CreateHitArea':
        areas = (*areas, node)
    if node and node[0] == 'CreateNormalAttack':
        yield node, areas
    for child in node:
        yield from _attacks(child, areas)


def _hit_count(area):
    mode = area[14]
    if mode[0] == 'CalculatedUsingMaxNumOfHits':
        return mode[1]
    if (mode == ['SpecifyMinHitIntervalDirectly', 30]
            and area[15] == ['Some', [{'min': 10, 'max': 10}]]):
        return 10
    raise ValueError('Magnus hit budget drift')


def with_ignition_growth(source, expected_hits):
    """单目标全段命中的整招增量为 5×入口层数，不改原倍率、段数或伤害归属。

    原生 BindConditionAccumulationVariable 保存入口层数；事件 Environment 派生
    继承该变量，因此十跳光环不受途中点火消耗/增加影响。vlv 是加法项，保留 alv。
    """
    tree = deepcopy(source)
    if tree[0] != 'ActionDsl' or tree[10] != 0 or tree[11][0] != 'Block':
        raise ValueError('Expected Magnus skill damage root')
    if list(iter_dsl_commands(tree, 'BindConditionAccumulationVariable')):
        raise ValueError('Unexpected existing condition binding')
    attacks = list(_attacks(tree))
    hits = []
    for attack, areas in attacks:
        if not areas or any(_hit_count(a) != 1 for a in areas[:-1]):
            raise ValueError('Unexpected repeated outer collision area')
        hits.append(_hit_count(areas[-1]))
        if len(attack[6]) != 1 or 'vlv' in attack[6][0]:
            raise ValueError('Unexpected multiplier expression')
    if tuple(hits) != tuple(expected_hits):
        raise ValueError(f'Magnus hit budget drift: {hits} != {expected_hits}')
    base = [a[6][0]['max'] for a, _ in attacks]
    total = sum(m * n for m, n in zip(base, hits))
    if total <= 0:
        raise ValueError('Expected positive original damage')
    growth = [PER_CAST * m / total for m in base]
    for (attack, _), amount in zip(attacks, growth):
        attack[6][0]['vlv'] = [{'vid': VARIABLE, 'min': 0, 'max': amount}]
    if not isclose(sum(g * n for g, n in zip(growth, hits)), PER_CAST):
        raise ValueError('Per-cast multiplier budget differs')
    tree[11][1].insert(0, ['Command', ['BindConditionAccumulationVariable',
        -17, VARIABLE, ['DCUnique', UID], 1, MAX_LAYERS]])
    return tree, dict(unique=UID, variable=VARIABLE, snapshot='action_start',
        per_cast_per_layer=PER_CAST, hits=hits, per_hit_per_layer=growth,
        base_total_at_max_skill_level=total, preserves_ability_level_terms=True)
