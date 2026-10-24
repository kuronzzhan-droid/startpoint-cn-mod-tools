"""阿虚命中红色斩击围绕狮子；锥形后移，小人处于锥形内部。"""
from copy import deepcopy
from math import pi

EFFECT = 'battle/effect/hit/normal_damage/slash/slash_red/slash_red'
NAME = 'magnus_kyon_orbit'
CONE_SHIFT_Y = 105
ORBIT_SCALE = 0.65
PF_FRAMES = 90


def effect_names():
    return [f'{NAME}_{i}' for i in range(8)]


def shows():
    result = []
    for i, name in enumerate(effect_names()):
        # Kyon uses eight native slashes spaced ten frames apart, turning by 120°.
        show = ['Command', ['ShowEffect', name, ['SpecifyEffectDirectly', EFFECT], -18,
            ['BacksideOfCharacter'], ['SpecifyEffectLifetimeDirectly', min(60, PF_FRAMES-i*10)],
            ['AB'], 0, 0, i * 2 * pi / 3, True, False,
            ['Some', [{'min': ORBIT_SCALE, 'max': ORBIT_SCALE}]]]]
        result.append(show if i == 0 else ['Event', ['Wait', i * 10, name, ['Block', [show]]]])
    return result


def shift_cone(parts):
    out = deepcopy(parts)
    root = out['g'][0]
    if len(root['s']) != 1 or len(root['s'][0]['l']) != 1:
        raise ValueError('unexpected Zeta root transform')
    key = root['s'][0]['l'][0]
    packed = int(key['m']) & 0xffffffff
    matrix = deepcopy(out['t'][packed >> 12])
    if matrix['x'] or matrix['y']:
        raise ValueError('cone origin was already shifted')
    matrix['y'] += CONE_SHIFT_Y * 4096
    key['m'] = (len(out['t']) << 12) | (packed & 4095)
    out['t'].append(matrix)
    return out


def attach(tree, cone_name='オーラ演出'):
    out = deepcopy(tree)
    body = out[11][1]
    positions = [i for i, v in enumerate(body) if v[0] == 'Command' and
                 v[1][:2] == ['ShowEffect', cone_name]]
    if len(positions) != 1:
        raise ValueError('expected one traveling cone')
    # Bind the ball; only visuals, no additional attack or hit area.
    body[positions[0] + 1:positions[0] + 1] = shows()
    collisions = [v for v in body if v[0] == 'Event' and v[1][0] == 'CollisionOfBallAndEnemy']
    if len(collisions) != 1:
        raise ValueError('expected one collision lifetime owner')
    hit = collisions[0][1][5][1]
    hides = [i for i, v in enumerate(hit) if v[0] == 'Command' and v[1][:2] == ['HideEffect', cone_name]]
    if len(hides) != 1:
        raise ValueError('cone cleanup absent')
    # Keep native cone Hide -> ending Show adjacent; remove the orbit immediately after.
    cleanup = [['Command', [cmd, name]] for name in effect_names()
               for cmd in ('RemoveEvent', 'HideEffect')]
    hit[hides[0] + 2:hides[0] + 2] = cleanup
    expiries = [v for v in body if v[0] == 'Event' and v[1][0] == 'Wait'
                and v[1][1] == PF_FRAMES and not str(v[1][2]).startswith(NAME)]
    if len(expiries) != 1:
        raise ValueError('expected native empty-field PF expiry')
    expiry = expiries[0][1][3][1]
    if not any(v == ['Command', ['NotifyPowerflipEnd', -18]] for v in expiry):
        raise ValueError('PF expiry lost native end notification')
    expiry[:0] = deepcopy(cleanup)
    return out


def assets(read_official):
    # Original red hit effect is already a native dependency; no sword texture.
    read_official(EFFECT + '.parts.amf3.deflate')
    return {}
