import json
def walk(n, path=()):
    if isinstance(n, list):
        yield path, n
        for i, x in enumerate(n):
            yield from walk(x, path + (i,))
def commands(tree, name=None):
    for p, n in walk(tree):
        if len(n) >= 2 and n[0] == 'Command' and isinstance(n[1], list) and n[1] and isinstance(n[1][0], str):
            if name is None or n[1][0] == name:
                yield p, n[1]
def get(tree, path):
    for i in path: tree = tree[i]
    return tree
def summary(tree):
    out = []
    for p, c in commands(tree):
        if c[0] == 'CreateCondition':
            out.append((p, 'CreateCondition', c[1], [(a[0], a[1:]) for a in c[2]], c[7]))
        elif c[0] in ('CreateNormalAttack', 'CreateRatioAttack', 'AddSkillPoint', 'CreateRatioHeal', 'ConsumeUniqueCondition', 'DeleteCondition'):
            out.append((p, c[0], c[1:8]))
        elif c[0].startswith('Conditionals') or c[0] in ('FindAllSubjects',):
            out.append((p, c[0], c[1:3]))
    return out
