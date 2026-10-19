"""Candidate-only reverse identity references that prevent isolated renaming."""
from __future__ import annotations

import zlib
import wf_mod_tool as maps
import wf_quest_lib as codec

from . import schema as s
from .behavior_wire import decode_wire

GENERAL_FUNNEL = 'master/battle/boss/funnel/general_funnel.orderedmap'
STANDARD_FUNNEL = 'master/battle/boss/funnel/standard_funnel.orderedmap'
WATCH = 'master/battle/boss/general_enemy_watch.orderedmap'
STATES = 'master/battle/boss/general_boss_state.orderedmap'


def _table(state, logical):
    raw = state.raw(logical)
    if raw is None:
        raise ValueError(f'missing identity reference table: {logical}')
    # The legacy recursive codec cannot represent a valid zero-key map.
    index = maps.read_orderedmap_raw_rows_from_bytes(raw, logical)
    return codec.parse_node(raw) if index.keys else {}


def identity_references(state):
    """Scan every current tier and ESDL, retaining concrete incoming links.

    Mirrors the established rogue-builder identity lock, without its cached
    external-store loader. A malformed/missing source prevents certification.
    """
    evidence = []

    def add(code, kind, logical, path):
        if code not in ('', '(None)', None):
            evidence.append({'target': code, 'kind': kind, 'logical': logical,
                             'path': list(path)})

    for path, text in s.iter_leaves(_table(state, GENERAL_FUNNEL)):
        for index, row in enumerate(s.parse_rows(text)):
            add(s.cell(row, 32), 'damage_share c32', GENERAL_FUNNEL, (*path, str(index)))
    for path, _ in s.iter_leaves(_table(state, WATCH)):
        if len(path) < 5:
            raise ValueError(f'malformed identity watch path: {path}')
        if path[3] == '1':
            add(path[4], 'enemy_watch partner', WATCH, path)
    for path, text in s.iter_leaves(_table(state, STATES)):
        for index, row in enumerate(s.parse_rows(text)):
            if s.cell(row, 29) == '15':
                add(s.cell(row, 30), 'GeneralBossAlive c29=15/c30', STATES, (*path, str(index)))
    decoded = {}
    from wf.rules.rogue_lineage import standard_funnel_boss_references
    for path, text in s.iter_leaves(_table(state, STANDARD_FUNNEL)):
        def load(logical):
            if logical not in decoded:
                raw = state.raw(logical)
                if raw is None:
                    raise ValueError(f'missing StandardFunnel identity resource: {logical}')
                decoded[logical] = decode_wire(raw)['tree']
            return decoded[logical]
        for kind, code in standard_funnel_boss_references(
                {'entry': text}, lambda value: s.parse_rows(value)[0], load):
            add(code, 'StandardFunnel ' + kind, STANDARD_FUNNEL, path)
    return evidence


def require_rename_safe(state, code):
    try:
        links = identity_references(state)
    except (ValueError, TypeError, IndexError, KeyError, zlib.error) as error:
        raise ValueError(f'identity-locked scan degraded; cannot rename {code}: {error}') from error
    hits = [item for item in links if item['target'] == code]
    if hits:
        chain = '; '.join(f"{item['kind']} {item['logical']}/{'/'.join(item['path'])} -> {code}"
                          for item in hits)
        raise ValueError(f'identity-locked boss {code}; isolated rename would break: {chain}')


def clone_self_watches(state, code, alias):
    """Copy the complete GeneralBoss self subtree, retaining every routine."""
    node = _table(state, WATCH).get('1', {}).get(code)
    if node is not None:
        if not isinstance(node, dict):
            raise ValueError(f'malformed GeneralBoss self watch: {code}')
        state.set_leaf(WATCH, ['1', alias],
                       {alias if key == code else key: value for key, value in node.items()}, new=True)
