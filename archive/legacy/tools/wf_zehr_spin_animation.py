"""原生 flatomo 时间轴伸缩；保留补间曲线，并增加低透明度内层刀光。"""
from copy import deepcopy
from wf_zehr_slow_spin import stretched
from wf_flatomo_capacity import image_capacities, validate_image_capacities


def smooth_parts(parts, *, ornament=False):
    if parts.get('m'):
        raise ValueError('independent movie clips cannot be retimed safely')
    result = deepcopy(parts)
    for group in result['g']:
        group['t'] = stretched(group['t'])
        for strip in group['s']:
            bits = int(strip['s']) & 0xffffffff
            kind, start = bits >> 30, bits & 0x3fffffff
            if kind not in (0, 2):
                raise ValueError('unsupported animation strip kind')
            # Keep native bitfields (including tween/easing) intact.
            strip['s'] = (kind << 30) | stretched(start)
            cursor = start
            for key in strip['l']:
                timing = int(key.get('t') or 0)
                duration = (timing & 0xffff) or 1
                new_duration = stretched(cursor + duration) - stretched(cursor)
                if new_duration > 0xffff:
                    raise ValueError('retimed keyframe exceeds native duration')
                key['t'] = (timing & ~0xffff) | new_duration
                cursor += duration
                if kind == 2:
                    ref = int(key.get('r') or 0) & 0xffffffff
                    loop, base = ref >> 30, ref & 0x3fffffff
                    # Rounding can add one frame to a parent strip. A source
                    # that never wraps must not flash its first frame there.
                    if loop == 2 and base + duration <= parts['g'][strip['i']]['t']:
                        loop = 1
                    key['r'] = (loop << 30) | stretched(base)
    if ornament:
        original = result['g'][0]
        index = len(result['g'])
        result['g'].append(original)
        # A smaller, 45-degree-offset blade layer. Reuse native texture regions.
        matrices = [dict(a=4096,b=0,c=0,d=4096,x=0,y=0),
                    dict(a=1680,b=1680,c=-1680,d=1680,x=0,y=0)]
        strips = []
        for matrix, alpha in zip(matrices, (255, 64)):
            result['t'].append(matrix)
            strips.append(dict(s=2 << 30, i=index, l=[dict(
                m=((len(result['t'])-1) << 12) | alpha,
                t=original['t'], r=1 << 30)]))
        result['g'][0] = dict(t=original['t'], s=strips)
    result['a']=[max(1,n) for n in image_capacities(result)]
    validate_image_capacities(result)
    return result
