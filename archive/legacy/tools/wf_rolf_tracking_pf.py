"""冰雪罗尔夫：无浮游辅助PF + 锁定射击 + 短时球追踪，保留已有三档冰焰。"""
from copy import deepcopy

import wf_seasonal7_kit_philia as K

CODE = 'black_wolf_knight_wt26'
PF = CODE+'_pf'
DESCRIPTION_KEY = CODE+'_pf_description'
DESCRIPTION = '特殊强化弹射：球追踪敌人并向锁定方向发射冰焰光柱，同时发动辅助强化弹射；不赋予浮游效果。'
CHASE_TAG = CODE+'_chase'
HIT_TAG = CODE+'_chase_hit'
STEP = 4
SPEED = 40


def logical(level):
    if level not in (1, 2, 3):
        raise ValueError(level)
    return f'battle/action/power_flip/action/override/{PF}${PF}_lv{level}.action.dsl.amf3.deflate'


def cmd(*values):
    return ['Command', list(values)]


def block(*values):
    return ['Block', list(values)]


def revise(tree, level):
    out = deepcopy(tree)
    if K.cmds(out, 'MoveBall'):
        validate(out, level)
        return out
    if len(K.cmds(out, 'CreateHitArea')) != level:
        raise ValueError('Rolf beam level drift')
    suppress = K.cmds(out, 'SetPowerFilpSuppress')
    if len(suppress) != 1 or suppress[0][1] != (20,25,35)[level-1]:
        raise ValueError('Rolf PF lifetime drift')
    duration = suppress[0][1]
    # Old composition reused support donor bindings0/1 and shot bindings0/1.
    # Rebind only support selectors with their lexical references.
    for number, find in enumerate(K.cmds(out, 'FindAllSubjects'), 20):
        old = find[1]
        find[1] = number
        for name, at in [('ShowEffect',3), ('CreateCondition',1), ('CreateRatioHeal',1)]:
            for c in K.cmds(find[9], name):
                if c[at] == old:
                    c[at] = number
    waits = [n[1] for n in out[11][1] if n[0] == 'Event' and n[1][0] == 'Wait']
    if len(waits) != 1 or waits[0][1] != 1:
        raise ValueError('Rolf shot launch drift')
    launch = waits[0]
    shots = [n for n in launch[3][1] if n[0] == 'Command' and n[1][0] == 'CreateHitArea']
    endings = [n for n in launch[3][1] if n[0] == 'Event']
    if len(shots) != level or len(endings) != 1 or len(K.cmds(endings, 'NotifyPowerflipEnd')) != 1:
        raise ValueError('Rolf lifecycle drift')
    for area in K.cmds(shots, 'CreateHitArea'):
        if area[2:4] != [-18, ['EF']]:
            raise ValueError('beam origin drift')
        area[3] = ['GH', 1000]
    for fx in K.cmds(shots, 'ShowEffect'):
        if fx[3] == -18:
            if '/wt26_beam_lv' not in fx[2][1]:
                raise ValueError('unexpected beam art')
            fx[6] = ['GH', 1000]
    # End notification remains outside target lookup: empty arena still ends PF.
    launch[3] = block(cmd('FindNearSubjects', -18, 1, 49, ['DoNothing'], 1000, block(*shots)))
    steer = cmd('FindNearSubjects', -18, 1, 49, ['DoNothing'], 1001,
        block(cmd('MoveBall', -18, ['GH',1001], 0, STEP, SPEED, ['KeepGoing'], False)))
    out[11][1].extend([
        ['Event', ['Repeat', STEP, (duration-2)//STEP, CHASE_TAG, block(steer)]],
        ['Event', ['CollisionOfBallAndEnemy', duration, 1, HIT_TAG, 1002,
                   block(cmd('RemoveEvent', CHASE_TAG))]],
        ['Event', ['Wait', duration, CODE+'_end', block(
            cmd('RemoveEvent', CHASE_TAG), cmd('RemoveEvent', HIT_TAG),
            cmd('NotifyPowerflipEnd', -18))]],
    ])
    validate(out, level)
    return out


def validate(tree, level):
    report = K.dsl_gates(tree, element=0)
    if errors := K.dsl_gate_failures(report):
        raise ValueError(errors)
    moves = K.cmds(tree, 'MoveBall')
    if moves != [['MoveBall', -18, ['GH',1001], 0, STEP, SPEED, ['KeepGoing'], False]]:
        raise ValueError('chase movement drift')
    if len(K.cmds(tree, 'CreateHitArea')) != level or len(K.cmds(tree, 'NotifyPowerflipEnd')) != 1:
        raise ValueError('shot count or PF lifecycle drift')
    if any(v[0] == 'ACFlying' for c in K.cmds(tree, 'CreateCondition') for v in c[2]):
        raise ValueError('Rolf must not grant Flying')
    return report
