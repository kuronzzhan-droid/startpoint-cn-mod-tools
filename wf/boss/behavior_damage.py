"""Scale a slot's private action closure without mutating any other consumer."""
import copy

from wf.rules.boss_preload import programs
from . import schema as s
from .behavior_clone import identity, owns_resource, set_owned_resource
from .behavior_identity import GENERAL_FUNNEL, WATCH
from .behavior_model import Programs
from .behavior_wire import compress, write_tree

SUFFIX = '.action.dsl.amf3.deflate'


def _external_roots(state, current_path, slot):
    roots = set()
    for logical in (s.GENERAL_BOSS, GENERAL_FUNNEL, WATCH):
        for path, text in s.iter_leaves(state.table(logical)):
            for index, row in enumerate(s.parse_rows(text)):
                for column, value in enumerate(row):
                    if (logical == s.GENERAL_BOSS and list(path) == current_path
                            and index == 0 and column == 110 + slot):
                        continue
                    roots.update(programs(value))
    return roots


def _shared(state, graph, owned, current_path, slot):
    shared = set()
    for root in sorted(_external_roots(state, current_path, slot)):
        # Per-root closure bounds still apply; unrelated native missing inputs
        # do not turn an otherwise isolated parameter edit into a new gate.
        shared.update(owned.intersection(graph.closure([root])))
        if shared == owned:
            break
    return shared


def _target(state, scope, program):
    candidate = 'battle/action/enemy/action/studio_behavior/' + identity(scope, program)
    index = 0
    while state.raw(candidate + SUFFIX) is not None:
        if not owns_resource(state, candidate + SUFFIX):
            raise ValueError(f'behavior resource collision: {candidate + SUFFIX}')
        # Re-entering an earlier source must not overwrite another slot/band's
        # existing clone. Ordinary repeated edits reuse their current closure.
        index += 1
        candidate = 'battle/action/enemy/action/studio_behavior/' + identity(scope, f'{program}:{index}')
    return candidate


def _scale(value, multiplier):
    if isinstance(value, dict) and set(value) == {'min', 'max'}:
        return {key: float(number) * multiplier for key, number in value.items()}
    if isinstance(value, list) and value and all(isinstance(item, dict) and set(item) == {'min', 'max'} for item in value):
        return [_scale(item, multiplier) for item in value]
    if isinstance(value, list) and value[:1] == ['SLv'] and len(value) == 2:
        return ['SLv', _scale(value[1], multiplier)]
    raise ValueError('damage multiplier needs an existing constant SLv min/max expression')


def edit_damage(state, row, slot, multiplier, owner, *, roots, current_path):
    graph = Programs(state)
    closure = graph.closure(roots)
    if graph.missing:
        raise ValueError('damage DSL closure missing: ' + ', '.join(sorted(graph.missing)))
    owned = {p for p in closure if owns_resource(state, p + SUFFIX)}
    shared = _shared(state, graph, owned, current_path, slot) if owned else set()
    scope = identity(owner, f'damage-slot:{slot}')
    mapped = {program: program if program in owned - shared else _target(state, scope, program)
              for program in closure}
    changed = 0

    def rewrite(value):
        nonlocal changed
        if isinstance(value, str):
            return ','.join(mapped.get(part.strip(), part) for part in value.split(','))
        if isinstance(value, dict):
            return {key: rewrite(item) for key, item in value.items()}
        if isinstance(value, list):
            value = [rewrite(item) for item in value]
            if value[:1] == ['CreateNormalAttack']:
                value[6] = _scale(value[6], multiplier)
                changed += 1
            return value
        return value

    candidate = {mapped[p]: rewrite(copy.deepcopy(tree)) for p, tree in closure.items()}
    if not changed:
        raise ValueError('selected action has no editable CreateNormalAttack multiplier')
    for program, tree in candidate.items():
        set_owned_resource(state, program + SUFFIX, compress(write_tree(tree)))
    row[110 + slot] = ','.join(mapped[p] for p in roots)
