"""Official 4th-anniversary Celtie contact/10-frame burst, tuned for Kyle."""
import copy
import hashlib

import wf_dsl
import wf_kyle_pf_effect as fx
import wf_seasonal7_common as common

SOURCE_HASHES = (
    'a9c343cd986c7a8ae72bd4cce4a7dc5697f4b773f76ce82c489ccd2617dc86b7',
    '09c7e10c7420a66118e342110ffc67419f08b6c2d43afa51969c5c417ed779e4',
    '3ea1cb719ef1a84afdba6e05d0d7cef90b55939cb598d4fbd51942b9273136cf')
RADII = (140, 160, 238)
SCALES = (2.8, 3.2, 4.76)
HITS = (3, 4, 5)
BURST_FRAMES = 10


def source(level):
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    raw = (root / fx.SOURCE / f'celtie_lv{level}.action.dsl.amf3.deflate').read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE_HASHES[level-1]:
        raise ValueError('official Celtie PF source changed')
    return common.amf_parse(raw)


def commands(tree, name):
    return list(wf_dsl.iter_dsl_commands(tree, name))


def build(knight, level):
    tree = source(level)
    outer, inner = commands(tree, 'CreateHitArea')
    life = fx.LIFETIMES[level-1]
    commands(tree, 'SetPowerFilpSuppress')[0][1] = life
    # The official Wait ends its PF independently of contact-point children.
    tree[11][1][1][1][1] = life
    outer[9][1] = [{'min': RADII[level-1], 'max': RADII[level-1]}]
    outer[13][1] = life
    # Existing battle-rules v4: explicit conversion marks real direct damage,
    # including native direct-hit counters, separated modifiers and statistics.
    outer[24] = inner[24] = 104
    aura = commands(outer[20], 'ShowEffect')[0]
    aura[2] = ['SpecifyEffectDirectly', fx.effect(level)]
    aura[4:7] = [['ForesideOfCharacter'], ['PlayOnlyFirstSequence'], ['AB']]
    aura[10:13] = [True, False, ['Some', [{'min': SCALES[level-1], 'max': SCALES[level-1]}]]]
    point, anchor = commands(outer[23], 'CreateReferencePoint')
    point[4] = -RADII[level-1]
    # Replace only Celtie's random slash visuals; keep both native reference
    # points and the stationary contact burst. No additional impact visual.
    anchor[11][1] = [node for node in anchor[11][1]
                     if not (node[0] == 'Command' and node[1][0] == 'ConditionalsProbability')]
    inner[14][1] = HITS[level-1]
    inner[15] = ['Some', [{'min': HITS[level-1], 'max': HITS[level-1]}]]
    attack = copy.deepcopy(commands(knight, 'CreateNormalAttack')[0])
    attack[1] = 7  # Celtie's inner collision binds the impacted enemy here.
    inner[23][1][0] = ['Command', attack]
    return tree


def verify(tree, knight, level):
    expected = build(knight, level)
    if tree != expected:
        raise ValueError('Kyle native contact burst, damage or lifecycle drift')
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(tree))['tree'] != tree:
        raise ValueError('PF DSL does not round-trip')
