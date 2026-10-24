"""Enemy-following lightning: reuse the accepted native electric-border layer."""
import copy

import wf_flatomo_capacity as capacity

NAME = 'kyle_pf_hit_residue'
FRAMES = 39


def effect(directory):
    return directory + '/hit_residue'


def animation(native, directory):
    parts = copy.deepcopy(native)
    # g57 is Targis's independent electric arcs, without the orb or slash fill.
    # Keep their original transforms and timing; the native root is uniformly scaled.
    parts['g'][0] = {'t': FRAMES, 's': [{'s': -2147483648, 'i': 57, 'l': [
        {'m': 0, 't': 16646146, 'r': 0x40000000},
        {'m': 255, 't': 21, 'r': 0x40000002},
        {'m': 255, 't': 16646159, 'r': 0x40000017},
        {'m': 0, 't': 1, 'r': 0x40000026}]}]}
    for item in parts['i']:
        item['p'] = f"{directory}/.gen/native/{item['p'].split('/')[-1]}"
    parts['a'] = capacity.image_capacities(parts)
    capacity.validate_image_capacities(parts)
    timeline = {'sequences': [{'begin': 1, 'end': FRAMES, 'name': 'neutral', 'kind': 'once'}],
                'sounds': [], 'points': [], 'circles': [], 'rectangles': [], 'matrices': []}
    return parts, timeline


def command(directory):
    # The outer collision environment binds 2 to the enemy. Track its position,
    # not direction. Native ActionEffect fades early if the enemy terminates.
    return ['Command', ['ShowEffect', NAME, ['SpecifyEffectDirectly', effect(directory)],
                        2, ['ForesideOfCharacter'], ['PlayOnlyFirstSequence'], ['AB'],
                        0, 0, 0, True, False, ['Some', [{'min': 1.4, 'max': 1.4}]]]]
