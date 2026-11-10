"""Standard ESDL identity checks and isolated actor/action family cloning.

Field meanings are verified against TypePackerResource2 in the cumulative
Android client. No asset or table is written by this module.
"""
from __future__ import annotations
import hashlib


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values(): yield from walk(child)
    elif isinstance(value, list):
        for child in value: yield from walk(child)


def reverse_boss_references(tree):
    """Damage sharing and ESDL watches bind exact Boss master IDs."""
    result = []
    target = tree.get('bG')
    if target:
        if not isinstance(target, str): raise ValueError('dynamic damage-share target')
        result.append(('damage_share', target))
    for form in tree.get('au', []):
        for watch in form.get('h', []):
            key = watch.get('a')
            if isinstance(key, list) and key and key[0] in ('T1', 'T3'):
                if len(key) != 3 or not isinstance(key[2], str):
                    raise ValueError('malformed Boss watch key')
                result.append(('enemy_watch_partner', key[2]))
    return result


def funnel_boss_references(table, decode_row, esdl_loader):
    """Inspect every resource/level, including reverse links absent from CSV."""
    seen = set()
    result = set()
    def visit(node):
        if isinstance(node, dict):
            for value in node.values(): visit(value)
            return
        row = decode_row(node)
        if not row or not row[0]: raise ValueError('empty Standard Funnel resource row')
        logical = row[0].removesuffix('.esdl.amf3.deflate')+'.esdl.amf3.deflate'
        if logical not in seen:
            seen.add(logical)
            result.update(reverse_boss_references(esdl_loader(logical)))
    visit(table)
    return result


def action_roots(tree):
    prefix = tree.get('bH') or ''
    if not isinstance(prefix, str): raise ValueError('dynamic action prefix')
    result = set()
    def add(name):
        if not isinstance(name, str) or not name: raise ValueError('empty action reference')
        # The actual client ALWAYS concatenates prefix + filePath.
        path = prefix + name
        if not path.startswith('battle/action/'): raise ValueError('invalid action path: '+path)
        result.add(path)
    def callbacks(items):
        for item in items:
            if not isinstance(item, dict): raise ValueError('malformed action callback')
            if item.get('b'): add(item['b'])
    kind = tree.get('bx')
    if isinstance(kind, list) and kind[0] == 'T1':
        for name in kind[1].get('g', []): add(name)
    for form in tree.get('au', []):
        if form.get('o'): raise ValueError('ESDL form events require a separate schema audit')
        for key in ('i', 'k', 'm'): callbacks(form.get(key, []))
        for state in form.get('g', []):
            callbacks(state.get('i', []))
            if state.get('xi'): raise ValueError('quantum actions require a separate schema audit')
        for watch in form.get('h', []):
            command = watch.get('i', [])
            if command and command[0] == 'T4':
                for name in command[1]: add(name)
    return result


def replace_exact(value, mapping):
    if isinstance(value, str): return mapping.get(value, value)
    if isinstance(value, dict): return {k: replace_exact(v, mapping) for k, v in value.items()}
    if isinstance(value, list): return [replace_exact(v, mapping) for v in value]
    return value


def clone_family(actors, id_map, action_loader, *, namespace):
    """Clone a proved set of actors and their complete named action closure.

    All callbacks keep suffixes and use private action prefixes. Every changed
    literal is an explicitly declared actor ID, prefix or action reference.
    HP, state IDs, durations, trials and all command parameters stay unchanged.
    Unknown external Boss references fail closed.
    """
    if set(actors) != set(id_map) or len(set(id_map.values())) != len(id_map):
        raise ValueError('actor identity map is incomplete or collides')
    if not namespace.startswith('battle/action/enemy/action/mod_rogue/'):
        raise ValueError('private action namespace required')
    prefixes = {tree.get('bH') for tree in actors.values()}
    if any(not isinstance(p, str) or not p.endswith('$') for p in prefixes):
        raise ValueError('only statically prefixed actors are supported')
    prefix_map = {p: namespace+'/'+hashlib.sha256(p.encode()).hexdigest()[:12]+'$'
                  for p in prefixes}
    queue = sorted(set().union(*(action_roots(t) for t in actors.values())))
    actions = {}
    while queue:
        path = queue.pop(0)
        if path in actions: continue
        if len(actions) >= 512: raise ValueError('action closure exceeds bound')
        tree = action_loader(path)
        if not isinstance(tree, list) or tree[0] != 'ActionDsl': raise ValueError('not an ActionDSL: '+path)
        actions[path] = tree
        for value in walk(tree):
            if isinstance(value, str) and value.startswith('battle/action/'):
                path2 = value.removesuffix('.action.dsl.amf3.deflate')
                if path2 not in actions: queue.append(path2)
            if isinstance(value, list) and len(value) == 2 and value[0] in ('StandardBoss', 'StandardFunnel'):
                if value[1] not in id_map: raise ValueError('actor closure lacks '+str(value))
    path_map = {}
    for path in actions:
        prefix = next((p for p in prefixes if path.startswith(p)), None)
        path_map[path] = (prefix_map[prefix]+path[len(prefix):] if prefix else
                          namespace+'/external_'+hashlib.sha256(path.encode()).hexdigest()[:16])
    mapping = {**id_map, **prefix_map, **path_map}
    mapping.update({p+'.action.dsl.amf3.deflate': q+'.action.dsl.amf3.deflate' for p,q in path_map.items()})
    new_actors = {id_map[code]: replace_exact(tree, mapping) for code, tree in actors.items()}
    new_actions = {path_map[path]: replace_exact(tree, mapping) for path, tree in actions.items()}
    for tree in [*new_actors.values(), *new_actions.values()]:
        if any(isinstance(v,str) and v in mapping for v in walk(tree)):
            raise ValueError('stale source reference remains')
    for tree in new_actors.values():
        for kind, target in reverse_boss_references(tree):
            if target not in new_actors: raise ValueError('unresolved private Boss reference: '+target)
        if not action_roots(tree) <= set(new_actions): raise ValueError('private callback missing')
    # Inverse replay is a strong guard against incidental parameter changes.
    inverse = {new:old for old,new in mapping.items()}
    if len(inverse) != len(mapping): raise ValueError('ambiguous inverse mapping')
    for code, tree in actors.items():
        if replace_exact(new_actors[id_map[code]], inverse) != tree:
            raise ValueError('actor semantic drift outside declared references')
    for path, tree in actions.items():
        if replace_exact(new_actions[path_map[path]], inverse) != tree:
            raise ValueError('action semantic drift outside declared references')
    return dict(actors=new_actors, actions=new_actions, original_actions=actions,
                id_map=id_map, prefix_map=prefix_map, action_map=path_map)
