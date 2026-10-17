"""盾牌座动图循环与原生动作时间线；保留庆祝、一次动作和标记语义。"""
from bisect import bisect_right
from copy import deepcopy
from fractions import Fraction

LOOPS = frozenset(('neutral', 'walk_back', 'walk_front', 'ghost_neutral'))


def loop_frames(durations):
    period = Fraction(sum(durations) * 60, 1000)
    if period.numerator > 3600:
        raise ValueError('source loop requires an excessive native supercycle')
    return period.numerator


def frame_index(tick, durations):
    ends, elapsed = [], 0
    for duration in durations:
        elapsed += duration * 60
        ends.append(elapsed)
    return bisect_right(ends, (tick * 1000) % elapsed)


def retime(tree, duration):
    result = deepcopy(tree)
    mapping, cursor = [], 1
    for sequence in result['sequences']:
        old = deepcopy(sequence)
        length = old['end'] - old['begin'] + 1
        if old['kind'] == 'loop' and old['name'] in LOOPS:
            length = duration
        sequence.update(begin=cursor, end=cursor + length - 1)
        mapping.append((old, sequence))
        cursor += length
    for channel in ('circles', 'points'):
        for track in result.get(channel, []):
            old_frames = sorted(track['frames'], key=lambda item: item['begin'])
            new_frames = []
            for frame in old_frames:
                owner = next(((old, new) for old, new in mapping
                              if old['begin'] <= frame['begin'] <= old['end']), None)
                if owner is None:
                    raise ValueError('animation marker is outside all source sequences')
                old, new = owner
                offset = frame['begin'] - old['begin']
                if offset > new['end'] - new['begin']:
                    raise ValueError('retiming would discard an animation marker')
                record = deepcopy(frame)
                record['begin'] = new['begin'] + offset
                new_frames.append(record)
            # Native markers hold their previous value. Keep the official one
            # body marker per sequence and the single global hp_gauge point.
            track['frames'] = new_frames
    if result.get('sounds'):
        raise ValueError('Scutum source unexpectedly contains sound timeline events')
    return result


def exposure_runs(timeline, durations):
    """原生稀疏图集后缀表示曝光段的结束帧，而不是起始帧。"""
    runs, previous = [], None
    last = 0
    for sequence in timeline['sequences']:
        for frame in range(sequence['begin'], sequence['end'] + 1):
            pose = frame_index(frame - sequence['begin'], durations)
            if previous is not None and pose != previous:
                runs.append((frame - 1, previous))
            previous, last = pose, frame
    if previous is not None:
        runs.append((last, previous))
    return runs
