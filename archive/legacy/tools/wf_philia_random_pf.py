"""五道PF风刃间隔72度，命中时随机整体朝向；仅用原生概率分支。

一次等概率选择36个整体旋转角，相邻10度，所选分支同时发射五道。
兼容把922版的五次独立抽样迁移为一次整体抽样，风刃倍率提高25%。
"""
from copy import deepcopy
from math import radians

import wf_seasonal7_kit_philia as K

CHOICES = 36
ID_BASE = 1000
SWORD_DAMAGE = {0.4: (0.8, 1.0), 0.55: (1.0, 1.25), 0.8: (1.3, 1.625)}
RAIN_DAMAGE = {0.4: 1.5, 0.55: 2.5, 0.8: 3.5}  # 两段合计3/5/7倍。
PREVIOUS_RAIN_DAMAGE = {0.4: 2.5, 0.55: 3.5, 0.8: 5.5}


def launch_body(tree):
    collisions = [e for e in K.events(tree) if e[0] == 'CollisionOfBallAndEnemy']
    if len(collisions) != 1:
        raise ValueError('PF collision event drift')
    burst = [c for c in K.cmds(collisions[0][5], 'CreateReferencePoint') if c[10] == 1]
    if len(burst) != 1 or burst[0][1] != collisions[0][4] or burst[0][6]:
        raise ValueError('PF must snapshot collision position')
    return burst[0][11][1]


def revise_pf(source):
    tree = deepcopy(source)
    body = launch_body(tree)
    choices = K.cmds(body, 'ConditionalsProbability')
    if len(choices) == 1:
        validate(tree)
        _upgrade_rain(tree)
        return tree
    if choices:
        validate(tree, legacy=True)
        replaced = [n for n in body if n[0] == 'Command' and n[1][0] == 'ConditionalsProbability']
        swords = [c[1][1][0][1][1][1][0] for c in choices]
    else:
        swords = [n for n in body if n[0] == 'Command' and n[1][0] == 'CreateHitArea'
                  and 200 <= n[1][19] < 225]
        replaced = swords
    if len(swords) != 5:
        raise ValueError('expected five original PF blades')
    branches = []
    for j in range(CHOICES):
        volley = []
        for i, node in enumerate(swords):
            blade = deepcopy(node)
            attacks = K.cmds(blade, 'CreateNormalAttack')
            old, new = SWORD_DAMAGE[_rain_baseline(
                attacks[1][6][0]['min'], attacks[0][6][0]['min'], legacy=True)]
            if attacks[0][6] != K.slv(old, old):
                raise ValueError('source windblade multiplier drift')
            attacks[0][6] = K.slv(new, new)
            # Keep the external impact anchor; remap every local binding/reference.
            ids = {1: 1}
            def rebind(old):
                if old not in ids:
                    ids[old] = ID_BASE + (i*CHOICES+j)*10 + len(ids)-1
                return ids[old]
            K.remap_subjects(blade, rebind)
            blade[1][6] = radians((j*10+i*72) % 360)
            for fx in K.cmds(blade[1][20], 'ShowEffect'):
                if fx[3] == 1 and fx[6] == ['AB']:
                    fx[9] = blade[1][6]
            volley.append(blade)
        branches.append(['Block', [['Command', ['ProbabilityWeight', 1.0]], ['Block', volley]]])
    first = body.index(replaced[0])
    body[:] = [n for n in body if n not in replaced]
    body.insert(first, ['Command', ['ConditionalsProbability', ['Block', branches]]])
    _upgrade_rain(tree)
    validate(tree)
    return tree


def validate(tree, *, legacy=False):
    if tree[10] != 0:
        raise ValueError('PF must inherit native power flip damage bucket')
    choices = K.cmds(launch_body(tree), 'ConditionalsProbability')
    if len(choices) != (5 if legacy else 1):
        raise ValueError('random draw count drift')
    for slot, choice in enumerate(choices):
        if len(choice) != 2 or choice[1][0] != 'Block' or len(choice[1][1]) != CHOICES:
            raise ValueError('native random branch shape drift')
        for j, branch in enumerate(choice[1][1]):
            weight, payload = branch[1]
            if branch[0] != 'Block' or weight != ['Command', ['ProbabilityWeight', 1.0]] \
                    or payload[0] != 'Block' or len(payload[1]) != (1 if legacy else 5):
                raise ValueError('native weighted branch pair drift')
            for i, node in enumerate(payload[1]):
                angle = j*10+slot*2 if legacy else (j*10+i*72) % 360
                _validate_blade(node[1], radians(angle), legacy=legacy)
    if errors := K.dsl_gate_failures(K.dsl_gates(tree)):
        raise ValueError(errors)


def _validate_blade(blade, angle, *, legacy=False):
    moves = K.cmds(blade[20], 'MoveHitArea')
    rains = K.cmds(blade[23], 'CreateReferencePoint')
    if blade[0] != 'CreateHitArea' or blade[6] != angle \
            or blade[3] != ['AB'] or blade[18] != ['None'] \
            or blade[15] != ['Some', K.slv(1, 1)] \
            or len(moves) != 1 or moves[0][2:5] != [['CD'], 0, 14] \
            or len(rains) != 1 or rains[0][1] != blade[21] or rains[0][6]:
        raise ValueError('random blade direction, piercing or impact rain drift')
    attacks = K.cmds(['Command', blade], 'CreateNormalAttack')
    if len(attacks) != 2:
        raise ValueError('blade/rain attack count drift')
    rain = attacks[1][6][0]['min']
    old, new = SWORD_DAMAGE[_rain_baseline(rain, attacks[0][6][0]['min'], legacy=legacy)]
    if attacks[0][6] != K.slv(old if legacy else new, old if legacy else new) \
            or attacks[1][6] != K.slv(rain, rain) \
            or any(c[24] != 0 for c in K.cmds(['Command', blade], 'CreateHitArea')):
        raise ValueError('PF damage multiplier or native PF damage bucket drift')


def _rain_baseline(value, sword, *, legacy=False):
    # 旧Lv1的2.5与新Lv2的2.5重叠，必须结合风刃倍率识别档位。
    for baseline, values in SWORD_DAMAGE.items():
        if sword == values[0 if legacy else 1] and value in (
                baseline, PREVIOUS_RAIN_DAMAGE[baseline], RAIN_DAMAGE[baseline]):
            return baseline
    raise ValueError('rain multiplier baseline drift')


def _upgrade_rain(tree):
    choice = K.cmds(launch_body(tree), 'ConditionalsProbability')[0]
    for branch in choice[1][1]:
        for blade in branch[1][1][1]:
            sword, rain = K.cmds(blade, 'CreateNormalAttack')
            value = RAIN_DAMAGE[_rain_baseline(rain[6][0]['min'], sword[6][0]['min'])]
            rain[6] = K.slv(value, value)
