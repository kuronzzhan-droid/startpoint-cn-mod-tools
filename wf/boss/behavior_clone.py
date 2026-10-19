"""Isolate existing encounters before changing behavior, never mutate sharers."""
from __future__ import annotations

import hashlib
import wf_quest_lib as codec

from . import schema as s
from .edit_state import leaf
from .parameters import join, require_encounter
from .reader import BossReader


def identity(quest, code):
    return 'studio_behavior_' + hashlib.sha256((quest + '\0' + code).encode()).hexdigest()[:18]


def select_enemy(state, quest, code):
    document = BossReader(state).show(quest)
    require_encounter(document['quest']['kind'], document['quest']['row'])
    alias = identity(document['quest']['selector'], code)
    matches = [e for e in document['enemies'] if e['code'] in (code, alias)]
    paths = {(e.get('table'), tuple(e.get('path') or [])) for e in matches}
    if len(paths) != 1 or not matches:
        raise ValueError('behavior enemyCode must identify one actual selected enemy band')
    enemy = matches[0]
    if enemy['table'] not in (s.GENERAL_BOSS, s.STANDARD_BOSS):
        raise ValueError('behavior editing supports GeneralBoss / StandardBoss only')
    return document, enemy


def _introduced(state, logical, key):
    original = state.original.get(logical)
    if original is not None and key in codec.parse_node(original):
        return False
    return any(change['table'] == logical and change['path'] == [key]
               and change['old'] is None for change in state.changes)


def isolate_enemy(state, document, enemy):
    quest = document['quest']; code = enemy['code']
    original = codec.parse_node(state.original[enemy['table']])
    owned = code.startswith('studio_behavior_') and code not in original
    alias = code if owned else identity(quest['selector'], code)
    table = state.table(enemy['table'])
    if alias != code:
        from .behavior_identity import require_rename_safe
        require_rename_safe(state, code)
        if alias in table:
            raise ValueError(f'behavior enemy ID collision: {alias}')
        state.set_leaf(enemy['table'], [alias], table[code], new=True)
        levels = state.table(s.BOSS_LEVEL)
        if code in levels:
            state.set_leaf(s.BOSS_LEVEL, [alias], levels[code], new=True)
        if enemy['table'] == s.GENERAL_BOSS:
            variables = 'master/battle/boss/general_boss_variable.orderedmap'
            variable = state.table(variables).get(code)
            if variable is not None:
                state.set_leaf(variables, [alias], variable, new=True)
            from .behavior_identity import clone_self_watches
            clone_self_watches(state, code, alias)
    zone_id = identity(quest['selector'], 'zone')
    fd_id = identity(quest['selector'], 'field_data')
    fd = list(document['field_data']['row']); zone = state.table(s.ZONE)[document['zone']['id']]
    if zone_id in state.table(s.ZONE) and not _introduced(state, s.ZONE, zone_id):
        raise ValueError(f'behavior zone ID collision: {zone_id}')
    from .edit_state import put
    for path, text in list(s.iter_leaves(zone)):
        rows = s.parse_rows(text)
        for row in rows:
            for column in (24, 26, 28, 30, 32, 34):
                if s.cell(row, column) == code:
                    row[column] = alias
        put(zone, path, '\n'.join(join(row) for row in rows))
    state.set_leaf(s.ZONE, [zone_id], zone, new=zone_id not in state.table(s.ZONE))
    fd[2] = zone_id
    if fd_id in state.table(s.FIELD_DATA) and not _introduced(state, s.FIELD_DATA, fd_id):
        raise ValueError(f'behavior field_data ID collision: {fd_id}')
    state.set_leaf(s.FIELD_DATA, [fd_id], join(fd), new=fd_id not in state.table(s.FIELD_DATA))
    row = list(quest['row']); row[s.QUEST_COLUMNS[quest['kind']]['field_data']] = fd_id
    state.set_leaf(quest['table'], quest['path'], join(row))
    path = [alias, *enemy['path'][1:]]
    return alias, path, s.parse_rows(leaf(state.table(enemy['table']), path))[0]


def owns_resource(state, logical):
    return state.original.get(logical) is None and any(
        change['table'] == logical and change.get('resource') and change['old'] is None
        for change in state.changes)


def set_owned_resource(state, logical, raw):
    current = state.raw(logical)
    if current is not None and not owns_resource(state, logical):
        raise ValueError(f'behavior resource collision: {logical}')
    state.set_raw(logical, raw, new=current is None)
