"""Marker-slot replacements and conservative parameter edits on cloned kits."""
from __future__ import annotations

import copy
import math

from wf.rules.boss_preload import programs, walk, _expected, tier
from . import schema as s
from .behavior_clone import identity, isolate_enemy, select_enemy
from .behavior_guards import borrowed_check, check_behavior_positions
from .behavior_model import Programs, STATES, marker, read_behavior
from .behavior_wire import compress, decode_wire, encode_wire, write_tree
from .edit_state import leaf
from .enemies import _level_path
from .esdl import decode_esdl, encode_esdl
from .parameters import join


def _fired(view, row):
    import re
    timeline = marker(view, s.cell(row, 25))
    if timeline.get('missing'):
        raise ValueError('marker timeline missing; action slots cannot be verified')
    return {int(match[1]) for point in timeline.get('points', [])
            if (match := re.fullmatch(r'enemy_action(\d+)', point.get('path', '')))
            and any(frame.get('data') for frame in point.get('frames', []))}


def _programs_at(view, row, slot):
    if slot not in _fired(view, row):
        raise ValueError(f'action slot {slot} is not fired by an existing marker')
    roots = programs(s.cell(row, 110 + slot))
    if not roots:
        raise ValueError(f'action slot {slot} is empty')
    return roots


def _scale(value, multiplier):
    if isinstance(value, dict) and set(value) == {'min', 'max'}:
        return {key: float(number) * multiplier for key, number in value.items()}
    if isinstance(value, list) and value and all(isinstance(item, dict) and set(item) == {'min', 'max'} for item in value):
        return [_scale(item, multiplier) for item in value]
    if isinstance(value, list) and value[:1] == ['SLv'] and len(value) == 2:
        return ['SLv', _scale(value[1], multiplier)]
    raise ValueError('damage multiplier needs an existing constant SLv min/max expression')


def edit_damage(state, row, slot, multiplier, owner):
    roots = _programs_at(state, row, slot); graph = Programs(state); closure = graph.closure(roots)
    if graph.missing:
        raise ValueError('damage DSL closure missing: ' + ', '.join(sorted(graph.missing)))
    mapped = {program: 'battle/action/enemy/action/studio_behavior/' + identity(owner, program)
              for program in closure}
    changed = 0
    def rewrite(value):
        nonlocal changed
        if isinstance(value, str):
            return ','.join(mapped.get(part, part) for part in value.split(','))
        if isinstance(value, dict):
            return {key: rewrite(item) for key, item in value.items()}
        if isinstance(value, list):
            value = [rewrite(item) for item in value]
            if value[:1] == ['CreateNormalAttack']:
                value[6] = _scale(value[6], multiplier); changed += 1
            return value
        return value
    candidate = {mapped[p]: rewrite(copy.deepcopy(tree)) for p, tree in closure.items()}
    if not changed:
        raise ValueError('selected action has no editable CreateNormalAttack multiplier')
    for program, tree in candidate.items():
        path = program + '.action.dsl.amf3.deflate'
        state.set_raw(path, compress(write_tree(tree)), new=state.raw(path) is None)
    row[110 + slot] = ','.join(mapped[p] for p in roots)


def _preload_shims(state, row, closure, owner, level):
    spawned = {node[1][1] for tree in closure.values() for node in walk(tree)
               if isinstance(node, list) and len(node) > 1 and node[0] == 'SpawnFunnel'
               and isinstance(node[1], list) and len(node[1]) > 1 and node[1][0] == 'Funnel'}
    funnels = state.table('master/battle/boss/funnel/general_funnel.orderedmap')
    for code in sorted(spawned):
        frow = tier(funnels.get(code), level)
        if not frow:
            raise ValueError(f'C8016: missing borrowed Funnel {code}')
        graph = Programs(state); trees = graph.closure([p for cell in frow for p in programs(cell)])
        if graph.missing or not trees:
            raise ValueError(f'C8016: missing Funnel preload closure {code}')
        from .behavior_guards import effect_dependencies, reject_loops
        reject_loops(trees)
        effect_dependencies(state, trees, int(frow[0]))
        if any(isinstance(node, list) and node and node[0] in ('SpawnFunnel', 'SpawnAlterEgo')
               for tree in trees.values() for node in walk(tree)):
            raise ValueError('C8016: nested borrowed summon preload cannot be proven')
        if frow[0] == row[0]:
            continue
        for program, tree in trees.items():
            fixed = _expected(tree, frow[0])
            if fixed is None:
                continue
            available = [slot for slot in range(50, 0, -1) if slot not in _fired(state, row)
                         and not s.present(s.cell(row, 110 + slot))]
            if not available:
                raise ValueError('C8016: no non-fired empty marker slot for fixed-element preload')
            target = 'battle/action/enemy/action/studio_behavior/' + identity(owner, 'preload:' + program)
            state.set_raw(target + '.action.dsl.amf3.deflate', compress(write_tree(fixed)), new=True)
            row[110 + available[0]] = target
            from .behavior_guards import effect_dependencies
            effect_dependencies(state, {target: fixed}, int(frow[0]))


def _general_parameters(state, row, request, owner):
    if 'damageMultiplier' in request:
        edit_damage(state, row, request['slot'], request['damageMultiplier'], owner)
    if not any(key in request for key in ('intervalFrames', 'trialThreshold')):
        return
    routine = row[42]; tree = state.table(STATES).get(routine)
    if tree is None:
        raise ValueError('missing routine')
    matches = [(path, text) for path, text in s.iter_leaves(tree)
               if request['state'] in ('/'.join(path), path[-1])]
    if len(matches) != 1:
        raise ValueError('state must identify one routine state, use group/state')
    path, text = matches[0]; cells = s.parse_rows(text)[0]
    if 'intervalFrames' in request:
        if cells[46] != '2':
            raise ValueError('intervalFrames only edits native Time termination states')
        cells[47] = str(request['intervalFrames'])
    if 'trialThreshold' in request:
        if s.cell(cells, 22) not in {'0', '1', '2', '3'}:
            raise ValueError('state has no existing HitCountCheck trial')
        if cells[22] == '3' and not 4 <= request['trialThreshold'] <= 9:
            raise ValueError('SkillChain trial threshold must be 4..9')
        cells[23] = str(request['trialThreshold'])
    target = identity(owner, 'routine')
    if routine != target:
        state.set_leaf(STATES, [target], tree, new=True)
    state.set_leaf(STATES, [target, *path], join(cells)); row[42] = target


def _standard_parameters(state, row, request, owner):
    if 'damageMultiplier' in request:
        raise ValueError('StandardBoss does not have GeneralBoss marker action slots')
    path = row[1] if row[1].endswith('.esdl.amf3.deflate') else row[1] + '.esdl.amf3.deflate'
    document = decode_esdl(state.raw(path)); tree = document['tree']
    form = request.get('form', 0)
    if form >= len(tree['forms']):
        raise ValueError('unknown esdl form')
    states = [x for x in tree['forms'][form]['states'] if str(x['canonicalPath']) == request['state']]
    if len(states) != 1:
        raise ValueError('unknown esdl canonical state')
    current = states[0]
    if 'intervalFrames' in request:
        condition = current.get('terminationCondition', [])
        if not (condition[:1] == ['TimeElapsed'] and condition[1][:1] == ['Frame']):
            raise ValueError('intervalFrames only edits native TimeElapsed/Frame esdl states')
        condition[1][1] = request['intervalFrames']
    if 'trialThreshold' in request:
        trial = current.get('trial', [])
        if trial[:1] == ['HitCountCheck']:
            content = trial[1]['content']
            if content[0] not in ('DirectAttack', 'Skill', 'PowerFlip', 'SkillChain'):
                raise ValueError('evaluated trial expressions cannot be replaced by a constant')
            if content[0] == 'SkillChain' and not 4 <= request['trialThreshold'] <= 9:
                raise ValueError('SkillChain trial threshold must be 4..9')
            content[1] = request['trialThreshold']
        elif trial[:1] == ['DamageCheck'] and request['trialThreshold'] <= 100:
            trial[1]['percentage'] = float(request['trialThreshold'])
        else:
            raise ValueError('state lacks an editable trial (DamageCheck percentage must be <=100)')
    target = 'battle/enemy/boss/' + identity(owner, 'esdl')
    state.set_raw(target + '.esdl.amf3.deflate', encode_esdl(document), new=state.raw(target + '.esdl.amf3.deflate') is None)
    row[1] = target


def apply_behavior(state, quest, request):
    for key, dependency in [('intervalFrames','state'), ('trialThreshold','state'), ('damageMultiplier','slot')]:
        if key in request and dependency not in request:
            raise ValueError(f'{key} requires {dependency}')
    for key in ('intervalFrames','damageMultiplier','trialThreshold'):
        if key in request and (isinstance(request[key], bool) or not isinstance(request[key], (int,float))
                               or not math.isfinite(request[key]) or request[key] <= 0):
            raise ValueError(f'invalid behavior parameter {key}')
    document, enemy = select_enemy(state, quest, request['enemyCode'])
    old_code = enemy['code']; owner = identity(document['quest']['selector'], request['enemyCode'])
    alias, path, row = isolate_enemy(state, document, enemy)
    if request['operation'] == 'behavior_replace':
        if enemy['table'] != s.GENERAL_BOSS:
            raise ValueError('marker action slots exist only on GeneralBoss')
        _programs_at(state, row, request['slot'])
        donors = state.table(s.GENERAL_BOSS); donor = request['sourceEnemyCode']
        donor_path = _level_path(donors, donor, enemy['level'])
        if donor_path is None:
            raise ValueError('unknown donor enemy or level band')
        donor_row = s.parse_rows(leaf(donors, donor_path))[0]
        roots = _programs_at(state, donor_row, request['sourceSlot'])
        graph = Programs(state); native_closure = graph.closure(roots)
        if graph.missing:
            raise ValueError('C8016: replacement DSL closure missing: ' + ', '.join(sorted(graph.missing)))
        from .behavior_guards import reject_loops
        reject_loops(native_closure)
        if donor not in (old_code, request['enemyCode']):
            closure, _ = borrowed_check(state, roots, row)
            _preload_shims(state, row, closure, owner, enemy['level'])
        row[110 + request['slot']] = ','.join(roots)
    elif request['operation'] == 'behavior_parameters':
        if enemy['table'] == s.GENERAL_BOSS:
            _general_parameters(state, row, request, owner)
        else:
            _standard_parameters(state, row, request, owner)
    else:
        raise ValueError('unknown behavior operation')
    state.set_leaf(enemy['table'], path, join(row))
    from .reader import BossReader
    candidate = BossReader(state).show(quest)
    check = check_behavior_positions(state, candidate)
    if check['blocking']:
        raise ValueError('; '.join(check['issues']))
    return [document['quest']['selector']]
