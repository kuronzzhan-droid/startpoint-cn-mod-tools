"""浴菲莉亚向上直射风刃、命中点五向贯穿与逐命中剑雨（2026-09-17）。"""
from copy import deepcopy

SKILL_SPEED = 12
SKILL_WAIT = 24
SKILL_LIFETIME = 150
SKILL_REFERENCE_LIFETIME = 310
SKILL_STOP = 15
PF_TEXT = ('特殊强化弹射命中时，从命中处以随机朝向、等间距发射五道贯穿风刃，风刃命中处降下剑雨'
           '【均以强化弹射伤害计算】／强化弹射时，提升参战角色攻击力并赋予贯穿、浮游效果')


def skill_description(text):
    old = '射出10把追踪光剑，并在命中位置降下剑雨'
    new = '向上射出10道贯穿风刃，并在各命中位置降下剑雨'
    if not text.startswith((old, new)):
        raise ValueError('skill description baseline drift')
    return new + text[len(old):] if text.startswith(old) else text


def revise_skill(tree):
    import wf_seasonal7_kit_philia as K
    out = deepcopy(tree)
    launch = [e for e in out[11][1] if e[0] == 'Event' and e[1][:2] == ['Wait', 20]]
    if len(launch) != 1:
        raise ValueError('skill launch event drift')
    units = launch[0][1][3][1]
    waits = [e[1][1] for e in units]
    if len(units) != 10 or waits not in ([9*i for i in range(10)], [SKILL_WAIT*i for i in range(10)]):
        raise ValueError('skill sword count or interval drift')
    stops = K.cmds(out, 'StopBall')
    if len(stops) != 1 or stops[0][2] not in (110, 248, SKILL_STOP):
        raise ValueError('skill stop window drift')
    stops[0][2] = SKILL_STOP
    for i, unit in enumerate(units):
        unit[1][1] = SKILL_WAIT * i
        moves = K.cmds(unit, 'MoveHitArea')
        swords = [c for c in K.cmds(unit, 'CreateHitArea') if c[2] == -18]
        targets = [c for c in K.cmds(unit, 'CreateReferencePoint') if c[9] in (110, SKILL_REFERENCE_LIFETIME)]
        if len(moves) != 1 or moves[0][4] not in (18, 6, SKILL_SPEED) or len(swords) != 1 or len(targets) > 1:
            raise ValueError('skill sword movement or target drift')
        sword = swords[0]
        if sword[13] not in (['SpecifyHitAreaLifetimeDirectly', 100],
                                ['SpecifyHitAreaLifetimeDirectly', 300],
                                ['SpecifyHitAreaLifetimeDirectly', SKILL_LIFETIME]):
            raise ValueError('skill sword lifetime drift')
        if sword[3] not in (['GH', 5*i+1], ['AB']) or moves[0][2] != sword[3]:
            raise ValueError('skill sword coordinates drift')
        if sword[18] not in (['Some', 1], ['None']) or sword[15] != ['Some', K.slv(1, 1)]:
            raise ValueError('skill per-target or total-hit limit drift')
        # Native AB angle 0 is world up (ActionHitArea.applyMovement subtracts PI/2).
        sword[3], sword[6], sword[18] = ['AB'], 0, ['None']
        moves[0][2], moves[0][3] = ['AB'], 0
        moves[0][4] = SKILL_SPEED
        sword[13] = ['SpecifyHitAreaLifetimeDirectly', SKILL_LIFETIME]
        for fx in K.cmds(sword[20], 'ShowEffect'):
            if fx[3] == -18:
                fx[6], fx[9] = ['AB'], 0
        rains = [c for c in K.cmds(sword[23], 'CreateReferencePoint') if 200 <= c[10] < 240]
        if len(rains) != 1 or rains[0][1] != sword[21] or rains[0][6] is not False:
            raise ValueError('skill rain must snapshot each blade hit position')
        # Remove the enclosing nearest-target search and reference point completely.
        unit[1][3] = ['Block', [['Command', sword]]]
    from wf_philia_combo_stock import revise_skill as add_stock
    return add_stock(out)


def revise_pf(tree):
    import wf_seasonal7_kit_philia as K
    if K.cmds(tree, 'ConditionalsProbability'):
        from wf_philia_random_pf import revise_pf as random_pf
        return random_pf(tree)
    out = deepcopy(tree)
    events = [e for e in K.events(out) if e[0] == 'CollisionOfBallAndEnemy']
    if len(events) != 1:
        raise ValueError('PF collision event drift')
    collision = events[0]
    burst = [c for c in K.cmds(collision[5], 'CreateReferencePoint') if c[10] == 1]
    if len(burst) != 1 or burst[0][1] not in (-18, collision[4]):
        raise ValueError('PF impact reference drift')
    # ListeningEvent.as binds event[4] to the collided enemy in a local environment.
    # Snapshot that position, instead of the moving leader ball (-18).
    burst[0][1] = collision[4]
    burst[0][6] = False
    swords = [c for c in K.cmds(burst[0][11], 'CreateHitArea') if 200 <= c[19] < 225]
    if len(swords) != 5 or sorted(c[6] for c in swords) != sorted(K.PF_LAUNCH_DIRS):
        raise ValueError('PF five-direction layout drift')
    for sword in swords:
        if sword[18] not in (['Some', 1], ['None']) or sword[15] != ['Some', K.slv(1, 1)]:
            raise ValueError('PF per-target or total-hit limit drift')
        sword[18] = ['None']  # Keep one hit per enemy, but continue through other enemies.
        body = sword[20][1]
        delayed = [e for e in body if e[0] == 'Event']
        if len(delayed) > 1 or (delayed and delayed[0][1][:2] != ['Wait', 10]):
            raise ValueError('PF delayed steering drift')
        body[:] = [e for e in body if e not in delayed]
        moves = K.cmds(sword[20], 'MoveHitArea')
        if len(moves) != 1 or moves[0][2] != ['CD'] or moves[0][4] != 14:
            raise ValueError('PF radial movement drift')
        rains = [c for c in K.cmds(sword[23], 'CreateReferencePoint') if 300 <= c[10] < 320]
        if len(rains) != 1 or rains[0][1] != sword[21] or rains[0][6] is not False:
            raise ValueError('rain must snapshot this blade hit position')
    return out
