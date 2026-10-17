"""十字双空牙优先Boss且剑风持续朝向目标；不更改倍率或攻击范围。"""
from copy import deepcopy

TARGET = 90
FALLBACK_EVENT = 'campus_celtie_boss_fallback'


def _nodes(tree, name):
    if isinstance(tree, list):
        if tree and tree[0] == name:
            yield tree
        for child in tree:
            yield from _nodes(child, name)


def boss_lock(tree):
    result = deepcopy(tree)
    selections = list(_nodes(result, 'FindNearSubjects'))
    if len(selections) != 3 or any(n[3] != 49 or n[5] != 0 for n in selections):
        raise ValueError('expected three Starwind routes with native enemy selection')
    replacements = {}
    for near in selections:
        fallback = deepcopy(near)
        fallback[5] = TARGET
        # Dash smoke/afterimage also resolve the original enemy implicitly.
        for direction in _nodes(fallback, 'GH'):
            if direction[1] == 0:
                direction[1] = TARGET
        for move in _nodes(fallback, 'MoveBall'):
            move[2] = ['GH', TARGET]
        for event in _nodes(fallback, 'CollisionOfBallAndSpecificEnemy'):
            event[1] = TARGET
        for ref in _nodes(fallback, 'CreateReferencePoint'):
            ref[2], ref[7] = ['GH', TARGET], True
            for effect in _nodes(ref, 'ShowEffect'):
                effect[6], effect[11] = ['CD'], True
            for area in _nodes(ref, 'CreateHitArea'):
                area[3], area[8] = ['CD'], True
        boss = deepcopy(fallback)
        boss[3], boss[4] = 51, ['DoNothing']
        boss[6][1].insert(0, ['Command', ['RemoveEvent', FALLBACK_EVENT]])
        # FindNear's imaginary target cannot answer isBoss(). Register a local
        # one-frame fallback and synchronously cancel it only if a Boss exists.
        replacements[id(near)] = ['Block', [
            ['Event', ['Wait', 1, FALLBACK_EVENT, ['Block', [['Command', fallback]]]]],
            ['Command', boss]]]

    def replace(node):
        if isinstance(node, list):
            if len(node) == 2 and node[0] == 'Command' and id(node[1]) in replacements:
                return replacements[id(node[1])]
            return [replace(child) for child in node]
        return node

    return replace(result)
