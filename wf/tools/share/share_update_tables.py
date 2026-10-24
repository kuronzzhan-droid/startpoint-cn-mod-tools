"""Scoped update planner: compare each claimed leaf with its previous delivery.

An unknown receiver edit is a conflict, not permission to replace a shared table.
Unclaimed native keys and JSON fields retain their values. No publishing here.

API
  client_plan(common, payload) -> (plans, report)                 raises ValueError('...conflict...')
  server_plan(assets, payload, allowlist=None, format_fallback=None) -> (plans, report)
  client_census(common, payload) -> report                        read-only; lists every op status, never raises on conflicts
  server_census(assets, payload, allowlist=None, format_fallback=None) -> report
  plans feed wf_share_update_io.apply_plans(plans, backup_root); nothing here writes files.
  Builder helpers: native_diff(before_rows, after_rows, prefix=()) -> [replace ops];
                   cells_operation(op) -> cells op | None;  codec.json_style(raw) -> STYLE for created files.

Client formats (payload['tables'] maps 'master/<...>.orderedmap' -> table spec)
  wf-scoped-update-client-1 (1.4.1056 pack; behaviour unchanged):
    {'operations': [{'path': [k, ...], 'before': NODE|null, 'after': NODE}]}
    missing nested parents are created implicitly; any path depth may replace a whole node.
  wf-scoped-update-client-2:
    {'format': 'wf-scoped-update-client-2', 'baseline': str, 'target': str,
     'tables': {logical: {'create': bool (optional; a missing table file is a conflict unless true),
                          'ensure': [ENSURE, ...] (optional), 'operations': [OP, ...]}}}
    OP replace: {'path': [...], 'before': NODE|null  or  'before_any': [NODE|null, ...], 'after': NODE,
                 'create_parents': bool (optional, default false), 'line': str (optional feature-line label)}
      receiver == after -> already; receiver matches before / any before_any entry (null = key absent) -> apply;
      otherwise conflict.  Existing nested nodes are never replaced wholesale: 'children' nodes are
      only accepted in 'after' when every accepted pre-value is null (a brand-new subtree).
    OP cells:   {'path': [...], 'cells': [{'row': int, 'col': int, 'before': str | 'before_any': [str, ...],
                                           'after': str}, ...], 'shape': [int, ...] (optional), 'line': str}
      target must be an existing CSV leaf; only the declared cells are read and written; per cell
      value == after -> already, value in before/before_any -> apply, else conflict; shape mismatch or
      out-of-range cell -> conflict.
    ENSURE:     {'path': [...], 'value': NODE, 'create_parents': bool (optional), 'line': str}
      closure prerequisite: absent -> add, semantically equal -> already, different -> conflict.
    Parents: every parent on path[:-1] must already exist as a nested table; a missing parent is a
    conflict unless the op says create_parents=true; a parent that is a CSV leaf is always a conflict.
    Paths of ensure + operations in one table must not overlap (no path is a prefix of another).

Server formats (payload['files'] maps an assets-relative *.json path -> file spec)
  wf-scoped-update-server-1 (1.4.1056 pack; behaviour unchanged): 15-file SERVER_FILES allowlist,
    {'operations': [{'path', 'before_exists', 'before', 'after'}]}, rewritten with indent=2.
  wf-scoped-update-server-2:
    {'format': 'wf-scoped-update-server-2', 'baseline': str, 'target': str,
     'allowlist': [relative, ...],                       # payload-declared files
     'files': {relative: {'create': {'init': {} | [], 'style': STYLE} (optional),
                          'ensure': [SOP, ...] (optional), 'operations': [SOP, ...]}}}
    A file is accepted only when it is in payload['allowlist'] AND in the package allowlist
    (allowlist argument, default SERVER_FILES_2); the declared list must be a subset of the package list.
    SOP set:      {'op': 'set' (default), 'path': [str, ...] (non-empty dict path),
                   'before_exists': bool, 'before': any  or  'before_any': [{'exists': false} | {'exists': true, 'value': any}],
                   'after': any, 'create_parents': bool (optional), 'line': str}
    SOP list_add: {'op': 'list_add', 'path': [str, ...] ([] = document root), 'items': [int|str, ...]}
      appends the missing items in payload order; receiver order and receiver-only items are kept.
    ensure SOP:   {'op': 'set', 'path': [...], 'value': any, 'create_parents': bool} (absent -> add,
                   equal -> already, different -> conflict) or a list_add.
    Values compare type-strictly (codec.json_same).  A missing file is a conflict unless 'create' is
    given; created files are rendered with create.style.  Existing files are written back in their own
    formatting via codec.json_rewrite (canonical or splice, round-trip checked); a file whose format
    cannot be preserved is refused unless format_fallback='indent2'.

Report (both census functions): {'kind', 'format', 'baseline', 'target', 'ready', 'counts',
  'by_section', 'by_line', 'operations': [STATUS]}; STATUS = {'logical'|'file', 'section', 'index', 'op',
  'path', 'line', 'status': 'apply'|'already'|'conflict', 'matched', 'reason', ...}.
  plan reports keep the format-1 shape ({'kind', 'baseline', 'files'}) and add 'format', 'target',
  'counts', 'operations' for format 2.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path, PurePosixPath
import zlib

from wf_share_asset_index import relative_path
import wf_share_update_codec as codec
from wf_share_update_io import checked_path, describe, entry, strict_json

CLIENT_FORMAT_1 = 'wf-scoped-update-client-1'
CLIENT_FORMAT_2 = 'wf-scoped-update-client-2'
SERVER_FORMAT_1 = 'wf-scoped-update-server-1'
SERVER_FORMAT_2 = 'wf-scoped-update-server-2'


def semantic(value):
    if isinstance(value, dict):
        return {k: semantic(v) for k, v in value.items() if k != 'raw'}
    if isinstance(value, list):
        return [semantic(v) for v in value]
    return value


def encode(node):
    if 'children' in node:
        return codec.pack({k: encode(v) for k, v in node['children'].items()})
    return codec.leaf_raw(node)


def patch_native(rows, keys, before, after, label):
    key, *rest = keys
    current = rows.get(key)
    if rest:
        children = {} if current is None else codec.unpack(current)
        patch_native(children, rest, before, after, label)
        encoded = codec.pack(children)
        if current != encoded:
            rows[key] = encoded
        return
    observed = None if current is None else codec.node(current)
    if semantic(observed) == semantic(after):
        return
    if semantic(observed) != semantic(before):
        raise ValueError('Receiver native leaf conflict: ' + label)
    rows[key] = encode(after)


def operations_checked(operations):
    paths = set()
    for op in operations:
        path = op['path']
        if not isinstance(path, list) or not path or any(not isinstance(k, str) or not k for k in path):
            raise ValueError('Invalid claimed key path')
        key = tuple(path)
        if any(key[:len(p)] == p or p[:len(key)] == key for p in paths):
            raise ValueError('Overlapping claimed key paths')
        paths.add(key)
    return operations


def client_plan(common, payload):
    if isinstance(payload, (str, Path)):
        payload = strict_json(Path(payload).read_bytes())
    if payload.get('format') == CLIENT_FORMAT_2:
        return _client_plan_2(common, payload)
    if payload.get('format') != 'wf-scoped-update-client-1':
        raise ValueError('Unknown client update format')
    planned, reports = [], []
    for logical, table in payload['tables'].items():
        if not logical.startswith('master/') or not logical.endswith('.orderedmap'):
            raise ValueError('Expected a native master table')
        path = checked_path(common, relative_path(logical))
        before = path.read_bytes() if path.exists() else None
        rows = {} if before is None else codec.unpack(before)
        old_rows = dict(rows)
        for op in operations_checked(table['operations']):
            patch_native(rows, op['path'], op['before'], op['after'], logical + '|' + '/'.join(op['path']))
        after = before if rows == old_rows and before is not None else codec.pack(rows)
        item = entry(path, before, after, root='common', logical_path=logical,
                     owned_keys=sorted({op['path'][0] for op in table['operations']}))
        reports.append(describe(item))
        if before != after:
            planned.append(item)
    return planned, dict(kind='client', baseline=payload['target'], files=reports)


SERVER_FILES = {'character.json', 'cdndata/character.json', 'cdndata/character_text.json',
                'mana_board.json', 'mana_node.json', 'gacha.json', 'cdndata/gacha.json',
                'cdndata/gacha_feature_content.json', 'item_lookup.json', 'item_sale.json',
                'abyss_endurance_degree_reward.json', 'character_degree_rewards.json',
                'equipment_degree_rewards.json', 'abyss_shop_degree_reward.json',
                'abyss_spheal_degree_reward.json'}

# Default package allowlist for server-2 payloads: the format-1 files plus the weapon/five-boss files.
SERVER_FILES_2 = frozenset(SERVER_FILES | {
    'item_ids.json', 'equipment_ids.json', 'equipment_lookup.json', 'equipment_element.json',
    'equipment_max_level.json', 'equipment_enhancement_shop.json', 'equipment_awakening_material.json',
    'boss_coin_shop.json', 'boss_coin_shop_item_category_map.json'})


def patch_json(value, op, label):
    keys = op['path']
    current = value
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        if not isinstance(current[key], dict):
            raise ValueError('Receiver JSON parent schema conflict: ' + label)
        current = current[key]
    key = keys[-1]
    present = key in current
    if present and current[key] == op['after']:
        return
    if present != op['before_exists'] or (present and current[key] != op['before']):
        raise ValueError('Receiver JSON leaf conflict: ' + label + '|' + '/'.join(keys))
    current[key] = copy.deepcopy(op['after'])


def server_plan(assets, payload, allowlist=None, format_fallback=None):
    if isinstance(payload, (str, Path)):
        payload = strict_json(Path(payload).read_bytes())
    if payload.get('format') == SERVER_FORMAT_2:
        return _server_plan_2(assets, payload, allowlist, format_fallback)
    if payload.get('format') != 'wf-scoped-update-server-1':
        raise ValueError('Unknown server update format')
    planned, reports = [], []
    for relative, file in payload['files'].items():
        if relative not in SERVER_FILES:
            raise ValueError('Server file is not in the update allowlist: ' + relative)
        path = checked_path(assets, relative)
        before = path.read_bytes() if path.exists() else None
        old = {} if before is None else strict_json(before)
        if not isinstance(old, dict):
            raise ValueError('Expected a JSON object')
        merged = copy.deepcopy(old)
        for op in operations_checked(file['operations']):
            patch_json(merged, op, relative)
        after = before if old == merged and before is not None else (
            json.dumps(merged, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        item = entry(path, before, after, root='server', logical_path=relative)
        reports.append(describe(item))
        if before != after:
            planned.append(item)
    return planned, dict(kind='server', baseline=payload['target'], files=reports)


# =============================================================== shared format-2 helpers

def _load(payload):
    if isinstance(payload, (str, Path)):
        payload = strict_json(Path(payload).read_bytes())
    if not isinstance(payload, dict):
        raise ValueError('Expected a payload object')
    return payload


def _keys(value, required, optional, what):
    if not isinstance(value, dict):
        raise ValueError('Expected an object: ' + what)
    missing = set(required) - set(value)
    unknown = set(value) - set(required) - set(optional)
    if missing or unknown:
        raise ValueError('Invalid %s fields: missing %s, unknown %s' % (what, sorted(missing), sorted(unknown)))
    return value


def _flag(value, what):
    if type(value) is not bool:
        raise ValueError('Expected a boolean: ' + what)
    return value


def _label(op, where):
    if not isinstance(op, dict):
        raise ValueError('Expected an operation object: ' + where)
    path = op.get('path')
    return where + '|' + ('/'.join(map(str, path)) if isinstance(path, list) else repr(path))


def _line(op):
    line = op.get('line')
    if line is not None and not isinstance(line, str):
        raise ValueError('line label must be a string')
    return line


def _counts(statuses):
    def bucket():
        return dict(apply=0, already=0, conflict=0)
    counts, sections, lines = bucket(), {}, {}
    for status in statuses:
        counts[status['status']] += 1
        sections.setdefault(status['section'], bucket())[status['status']] += 1
        lines.setdefault(status.get('line') or '-', bucket())[status['status']] += 1
    return counts, sections, lines


def _raise_conflicts(kind, statuses):
    bad = [s for s in statuses if s['status'] == 'conflict']
    if bad:
        where = lambda s: (s.get('logical') or s.get('file')) + '|' + '/'.join(s['path'])
        first = bad[0]
        more = '' if len(bad) == 1 else ' (+%d more conflicts)' % (len(bad) - 1)
        raise ValueError('Receiver %s conflict: %s: %s%s' % (kind, where(first), first['reason'], more))


# =============================================================== client format 2

def _is_map(raw):
    """True for a nested orderedmap row, False for a CSV/empty leaf."""
    if raw == b'':
        return False
    try:
        zlib.decompress(raw).decode('utf-8')
        return False
    except (zlib.error, UnicodeDecodeError):
        codec.unpack(raw)
        return True


class _Map:
    """Lazily decoded nested orderedmap; only maps below a write are re-packed."""

    def __init__(self, rows):
        self.rows, self.children, self.dirty = rows, {}, False

    def child(self, key):
        if key not in self.children:
            raw = self.rows[key]
            if not _is_map(raw):
                return None
            self.children[key] = _Map(codec.unpack(raw))
        return self.children[key]

    def raw(self):
        if not self.dirty:
            raise AssertionError('clean map has original bytes')
        return codec.pack({k: (self.children[k].raw() if k in self.children and self.children[k].dirty else v)
                           for k, v in self.rows.items()})


def _parent(tree, path, create):
    """(parent map, [maps on the chain]) for path[-1]; (None, reason) when it is missing or not a table."""
    chain, current = [tree], tree
    for depth, key in enumerate(path[:-1]):
        if key not in current.rows:
            if not create:
                return None, 'parent missing: ' + '/'.join(path[:depth + 1])
            current.rows[key] = codec.pack({})
        try:
            nxt = current.child(key)
        except (ValueError, zlib.error) as exc:
            return None, 'parent unreadable: %s (%s)' % ('/'.join(path[:depth + 1]), exc)
        if nxt is None:
            return None, 'parent is a CSV leaf: ' + '/'.join(path[:depth + 1])
        chain.append(nxt)
        current = nxt
    return current, chain


def _probe(tree, path):
    """Read-only walk: ('ok', parent_map) | ('missing', depth) | ('leaf', depth) | ('bad', reason)."""
    current = tree
    for depth, key in enumerate(path[:-1]):
        if key not in current.rows:
            return 'missing', depth
        try:
            nxt = current.child(key)
        except (ValueError, zlib.error) as exc:
            return 'bad', 'parent unreadable: %s (%s)' % ('/'.join(path[:depth + 1]), exc)
        if nxt is None:
            return 'leaf', depth
        current = nxt
    return 'ok', current


def _has_children(node):
    return isinstance(node, dict) and 'children' in node


def _check_node(node, what):
    if not isinstance(node, dict):
        raise ValueError('Invalid payload node: ' + what)
    encode(node)
    return node


def _client_op_2(op, section, logical):
    label = _label(op, logical)
    if section == 'ensure':
        _keys(op, ['path', 'value'], ['create_parents', 'line'], 'ensure ' + label)
        _check_node(op['value'], label)
        kind = 'ensure'
    elif 'cells' in op:
        _keys(op, ['path', 'cells'], ['shape', 'line'], 'cells op ' + label)
        cells = op['cells']
        if not isinstance(cells, list) or not cells:
            raise ValueError('cells op needs cells: ' + label)
        seen = set()
        for cell in cells:
            _keys(cell, ['row', 'col', 'after'], ['before', 'before_any'], 'cell ' + label)
            if ('before' in cell) == ('before_any' in cell):
                raise ValueError('cell needs exactly one of before/before_any: ' + label)
            accepted = [cell['before']] if 'before' in cell else cell['before_any']
            if not isinstance(accepted, list) or not accepted or not all(isinstance(v, str) for v in accepted + [cell['after']]):
                raise ValueError('cell values must be strings: ' + label)
            index = (codec._cell_index(cell['row'], 'row'), codec._cell_index(cell['col'], 'col'))
            if index in seen:
                raise ValueError('duplicate cell in one op: ' + label)
            seen.add(index)
        if 'shape' in op and (not isinstance(op['shape'], list)
                              or any(type(n) is not int or n < 0 for n in op['shape'])):
            raise ValueError('invalid cells shape: ' + label)
        kind = 'cells'
    else:
        _keys(op, ['path', 'after'], ['before', 'before_any', 'create_parents', 'line'], 'op ' + label)
        if ('before' in op) == ('before_any' in op):
            raise ValueError('op needs exactly one of before/before_any: ' + label)
        accepted = [op['before']] if 'before' in op else op['before_any']
        if not isinstance(accepted, list) or not accepted:
            raise ValueError('before_any must be a non-empty list: ' + label)
        for node in accepted:
            if node is not None:
                _check_node(node, label)
                if _has_children(node):
                    raise ValueError('Nested whole-row replacement is not allowed; use sub-key ops: ' + label)
        _check_node(op['after'], label)
        if _has_children(op['after']) and any(node is not None for node in accepted):
            raise ValueError('Nested whole-row replacement is not allowed; use sub-key ops: ' + label)
        kind = 'replace'
    if 'create_parents' in op:
        _flag(op['create_parents'], 'create_parents')
    _line(op)
    return kind


def _client_status(tree, op, kind, section, index, logical):
    status = dict(logical=logical, section=section, index=index, op=kind, path=list(op['path']),
                  line=op.get('line'), status='conflict', matched=None, reason=None)
    path = op['path']
    create = op.get('create_parents', False) and kind != 'cells'
    probe, where = _probe(tree, path)
    if probe == 'bad' or probe == 'leaf':
        status['reason'] = where if probe == 'bad' else 'parent is a CSV leaf: ' + '/'.join(path[:where + 1])
        return status
    if probe == 'missing':
        if not create:
            status['reason'] = 'parent missing: ' + '/'.join(path[:where + 1])
            return status
        status['creates_parents'] = True
        current = None
    else:
        raw = where.rows.get(path[-1])
        try:
            current = None if raw is None else codec.node(raw)
        except (ValueError, zlib.error) as exc:
            status['reason'] = 'unreadable receiver node (%s)' % exc
            return status
    if kind == 'cells':
        return _cells_status(status, op, current)
    after = op['value'] if kind == 'ensure' else op['after']
    accepted = [None] if kind == 'ensure' else ([op['before']] if 'before' in op else op['before_any'])
    if semantic(current) == semantic(after):
        status.update(status='already', matched='after')
        return status
    for i, node in enumerate(accepted):
        if semantic(current) == semantic(node):
            status.update(status='apply', matched='absent' if kind == 'ensure' else
                          'before' if 'before' in op else 'before_any[%d]' % i)
            return status
    status['reason'] = 'receiver value differs from every accepted pre-value' if current is not None else 'receiver key is absent'
    if current is not None and 'csv' in current and after is not None and 'csv' in after:
        status['cells_vs_after'] = (codec.cells_diff(current['csv'], after['csv']) or [])[:12]
    return status


def _cells_status(status, op, current):
    if current is None:
        status['reason'] = 'cells target is absent'
        return status
    if 'csv' not in current:
        status['reason'] = 'cells target is not a CSV leaf'
        return status
    rows = current['csv']
    if 'shape' in op and codec.csv_shape(rows) != op['shape']:
        status['reason'] = 'CSV shape differs: %s != %s' % (codec.csv_shape(rows), op['shape'])
        return status
    cells, bad = [], False
    for cell in op['cells']:
        r, c = cell['row'], cell['col']
        item = dict(row=r, col=c, status='conflict', matched=None)
        if r >= len(rows) or c >= len(rows[r]):
            item['reason'] = 'cell out of range'
        else:
            value = rows[r][c]
            accepted = [cell['before']] if 'before' in cell else cell['before_any']
            if value == cell['after']:
                item.update(status='already', matched='after')
            elif value in accepted:
                item.update(status='apply', matched='before' if 'before' in cell else 'before_any[%d]' % accepted.index(value))
            else:
                item.update(current=value)
        bad = bad or item['status'] == 'conflict'
        cells.append(item)
    status['cells'] = cells
    if bad:
        status['reason'] = 'cell conflict at ' + ', '.join('%d/%d' % (c['row'], c['col']) for c in cells if c['status'] == 'conflict')
    elif all(c['status'] == 'already' for c in cells):
        status.update(status='already', matched='after')
    else:
        status.update(status='apply', matched='cells')
    return status


def _client_apply(tree, op, kind, status):
    parent, chain = _parent(tree, op['path'], op.get('create_parents', False) and kind != 'cells')
    if parent is None:
        raise ValueError('Receiver native parent conflict at apply time: ' + chain)
    key = op['path'][-1]
    if kind == 'cells':
        raw = parent.rows[key]
        todo = [dict(row=c['row'], col=c['col'], after=c['after'])
                for c, s in zip(op['cells'], status['cells']) if s['status'] == 'apply']
        parent.rows[key] = codec.csv_write_like(codec.rows_patch_cells(codec.csv_read(raw), todo, op.get('shape')), raw)
    else:
        parent.rows[key] = encode(op['value'] if kind == 'ensure' else op['after'])
    parent.children.pop(key, None)
    for item in chain:
        item.dirty = True


def _client_tables_2(common, payload):
    _keys(payload, ['format', 'baseline', 'target', 'tables'], [], 'client payload')
    if not isinstance(payload['tables'], dict):
        raise ValueError('Expected client tables')
    for logical, table in payload['tables'].items():
        if not isinstance(logical, str) or not logical.startswith('master/') or not logical.endswith('.orderedmap'):
            raise ValueError('Expected a native master table')
        _keys(table, ['operations'], ['create', 'ensure'], 'table ' + logical)
        if 'create' in table:
            _flag(table['create'], 'create')
        if not isinstance(table['operations'], list) or not isinstance(table.get('ensure', []), list):
            raise ValueError('Expected operation lists: ' + logical)
        ops = [('ensure', i, op) for i, op in enumerate(table.get('ensure', []))]
        ops += [('operations', i, op) for i, op in enumerate(table['operations'])]
        if not ops:
            raise ValueError('Table spec without operations: ' + logical)
        kinds = [_client_op_2(op, section, logical) for section, _i, op in ops]
        operations_checked([op for _s, _i, op in ops])
        path = checked_path(common, relative_path(logical))
        before = path.read_bytes() if path.exists() else None
        yield logical, table, path, before, [(s, i, op, k) for (s, i, op), k in zip(ops, kinds)]


def _client_evaluate(logical, table, before, ops):
    if before is None and not table.get('create', False):
        statuses = [dict(logical=logical, section=s, index=i, op=k, path=list(op['path']), line=op.get('line'),
                         status='conflict', matched=None, reason='receiver table is missing')
                    for s, i, op, k in ops]
        return None, statuses
    tree = _Map({} if before is None else codec.unpack(before))
    return tree, [_client_status(tree, op, k, s, i, logical) for s, i, op, k in ops]


def client_census(common, payload):
    payload = _load(payload)
    if payload.get('format') != CLIENT_FORMAT_2:
        raise ValueError('client_census reads wf-scoped-update-client-2 payloads only')
    statuses = []
    for logical, table, _path, before, ops in _client_tables_2(common, payload):
        statuses += _client_evaluate(logical, table, before, ops)[1]
    counts, sections, lines = _counts(statuses)
    return dict(kind='client', format=payload['format'], baseline=payload['baseline'], target=payload['target'],
                written=False, ready=counts['conflict'] == 0, counts=counts, by_section=sections, by_line=lines,
                operations=statuses)


def _client_plan_2(common, payload):
    planned, reports, everything = [], [], []
    staged = []
    for logical, table, path, before, ops in _client_tables_2(common, payload):
        tree, statuses = _client_evaluate(logical, table, before, ops)
        everything += statuses
        staged.append((logical, table, path, before, ops, tree, statuses))
    _raise_conflicts('native', everything)
    for logical, table, path, before, ops, tree, statuses in staged:
        for (s, i, op, kind), status in zip(ops, statuses):
            if status['status'] == 'apply':
                _client_apply(tree, op, kind, status)
        after = before if before is not None and not tree.dirty else (codec.pack(tree.rows) if not tree.dirty else tree.raw())
        item = entry(path, before, after, root='common', logical_path=logical,
                     owned_keys=sorted({op['path'][0] for _s, _i, op, _k in ops}))
        counts = _counts(statuses)[0]
        reports.append(describe(item) | dict(created=before is None, counts=counts))
        if before != after:
            planned.append(item)
    counts, sections, lines = _counts(everything)
    return planned, dict(kind='client', format=CLIENT_FORMAT_2, baseline=payload['baseline'], target=payload['target'],
                         files=reports, counts=counts, by_section=sections, by_line=lines, operations=everything)


# ---------------------------------------------------------------- builder helpers (client)

def native_diff(before_rows, after_rows, prefix=()):
    """Sub-key replace ops turning before_rows into after_rows (dicts of raw bytes, e.g. codec.unpack output).

    Nested tables are descended so no op replaces an existing nested node; semantically equal
    re-encodings are skipped; deletions and leaf<->table shape changes raise ValueError."""
    ops = []
    for key in before_rows:
        if key not in after_rows:
            raise ValueError('Deletion is not supported: ' + '/'.join(prefix + (key,)))
    for key, raw in after_rows.items():
        path = list(prefix) + [key]
        old = before_rows.get(key)
        if old == raw:
            continue
        if old is None:
            ops.append(dict(path=path, before=None, after=codec.node(raw)))
            continue
        old_map, new_map = _is_map(old), _is_map(raw)
        if old_map and new_map:
            ops += native_diff(codec.unpack(old), codec.unpack(raw), tuple(path))
        elif old_map or new_map:
            raise ValueError('Leaf/table shape change is not supported: ' + '/'.join(path))
        else:
            b, a = codec.node(old), codec.node(raw)
            if semantic(b) != semantic(a):
                ops.append(dict(path=path, before=b, after=a))
    return ops


def cells_operation(op):
    """Convert a CSV-leaf replace op into a cells op (same shape only); None when not convertible."""
    before, after = op.get('before'), op.get('after')
    if not before or not after or 'csv' not in before or 'csv' not in after:
        return None
    cells = codec.cells_diff(before['csv'], after['csv'])
    if not cells:
        return None
    result = dict(path=list(op['path']), shape=codec.csv_shape(before['csv']), cells=cells)
    if op.get('line') is not None:
        result['line'] = op['line']
    return result


# =============================================================== server format 2

def _safe_server_name(name):
    if not isinstance(name, str) or not name.endswith('.json') or '\\' in name or ':' in name:
        raise ValueError('Unsafe server file name: %r' % (name,))
    parts = PurePosixPath(name).parts
    if (PurePosixPath(name).is_absolute() or not 1 <= len(parts) <= 2
            or any(p in ('', '.', '..') or p.startswith('.') for p in parts) or '/'.join(parts) != name):
        raise ValueError('Unsafe server file name: ' + name)
    return name


def _allowed(payload, allowlist):
    declared = payload['allowlist']
    if (not isinstance(declared, list) or not all(isinstance(n, str) for n in declared)
            or len(set(declared)) != len(declared)):
        raise ValueError('Payload allowlist must be a list of unique names')
    package = SERVER_FILES_2 if allowlist is None else list(allowlist)
    if not all(isinstance(n, str) for n in package):
        raise ValueError('Package allowlist must list file names')
    package = frozenset(package)
    for name in set(declared) | package:
        _safe_server_name(name)
    extra = set(declared) - package
    if extra:
        raise ValueError('Payload allowlist exceeds the package allowlist: ' + ', '.join(sorted(extra)))
    for relative in payload['files']:
        if relative not in declared or relative not in package:
            raise ValueError('Server file is not in the update allowlist: ' + str(relative))


def _scalar(value):
    return (type(value) is int) or isinstance(value, str)


def _server_op_2(op, section, relative):
    label = _label(op, relative)
    kind = op.get('op', 'set')
    if kind == 'list_add':
        _keys(op, ['op', 'path', 'items'], ['line'], 'list_add ' + label)
        path, items = op['path'], op['items']
        if not isinstance(items, list) or not items or not all(_scalar(v) for v in items):
            raise ValueError('list_add items must be ints or strings: ' + label)
        if any(codec.json_same(a, b) for i, a in enumerate(items) for b in items[i + 1:]):
            raise ValueError('duplicate list_add item: ' + label)
    elif kind == 'set' and section == 'ensure':
        _keys(op, ['path', 'value'], ['op', 'create_parents', 'line'], 'ensure ' + label)
        path = op['path']
    elif kind == 'set':
        _keys(op, ['path', 'after'], ['op', 'before_exists', 'before', 'before_any', 'create_parents', 'line'], 'op ' + label)
        path = op['path']
        if 'before_any' in op:
            if 'before_exists' in op or 'before' in op:
                raise ValueError('op needs before_exists/before or before_any, not both: ' + label)
            if not isinstance(op['before_any'], list) or not op['before_any']:
                raise ValueError('before_any must be a non-empty list: ' + label)
            for alt in op['before_any']:
                if _flag(_keys(alt, ['exists'], ['value'], 'before_any ' + label)['exists'], 'exists') != ('value' in alt):
                    raise ValueError('before_any entry: value is required exactly when exists: ' + label)
        else:
            _keys(op, ['path', 'after', 'before_exists', 'before'], ['op', 'create_parents', 'line'], 'op ' + label)
            _flag(op['before_exists'], 'before_exists')
    else:
        raise ValueError('Unknown server op: %r (%s)' % (kind, label))
    if not isinstance(path, list) or any(not isinstance(k, str) or not k for k in path) or (kind == 'set' and not path):
        raise ValueError('Invalid claimed key path: ' + label)
    if 'create_parents' in op:
        _flag(op['create_parents'], 'create_parents')
    _line(op)
    return kind


def _server_paths_checked(ops, label):
    """No claimed path may be a prefix of another; list_add ops may share a list if their items are disjoint."""
    seen = []
    for _s, _i, op, kind in ops:
        key = tuple(op['path'])
        for other, other_kind, other_op in seen:
            if key[:len(other)] == other or other[:len(key)] == key:
                if kind == other_kind == 'list_add' and key == other:
                    if any(codec.json_same(a, b) for a in op['items'] for b in other_op['items']):
                        raise ValueError('Overlapping list_add items: ' + label)
                    continue
                raise ValueError('Overlapping claimed key paths: ' + label)
        seen.append((key, kind, op))


def _walk(value, path):
    """('ok', container) | ('missing', depth) | ('schema', depth) for the parent of path[-1]; path may be []"""
    current = value
    for depth, key in enumerate(path):
        if not isinstance(current, dict):
            return 'schema', depth
        if key not in current:
            return 'missing', depth
        current = current[key]
    return 'ok', current


def _server_status(value, op, kind, section, index, relative):
    status = dict(file=relative, section=section, index=index, op=kind, path=list(op['path']),
                  line=op.get('line'), status='conflict', matched=None, reason=None)
    path = op['path']
    if kind == 'list_add':
        state, target = _walk(value, path)
        if state != 'ok':
            status['reason'] = 'list parent %s at %s' % (state, '/'.join(path[:target + 1]) or '<root>')
        elif not isinstance(target, list):
            status['reason'] = 'target is not a list'
        else:
            missing = [v for v in op['items'] if not any(codec.json_same(v, x) for x in target)]
            status['missing'] = missing
            if missing:
                status.update(status='apply', matched='list')
            else:
                status.update(status='already', matched='after')
        return status
    state, parent = _walk(value, path[:-1])
    create = op.get('create_parents', False)
    if state == 'schema' or (state == 'ok' and not isinstance(parent, dict)):
        status['reason'] = 'parent is not an object'
        return status
    if state == 'missing':
        if not create:
            status['reason'] = 'parent missing: ' + '/'.join(path[:parent + 1])
            return status
        status['creates_parents'] = True
        present, current = False, None
    else:
        present = path[-1] in parent
        current = parent.get(path[-1])
    after = op['value'] if section == 'ensure' else op['after']
    if present and codec.json_same(current, after):
        status.update(status='already', matched='after')
        return status
    if section == 'ensure':
        accepted = [dict(exists=False)]
    elif 'before_any' in op:
        accepted = op['before_any']
    else:
        accepted = [dict(exists=op['before_exists'], value=op['before'])] if op['before_exists'] else [dict(exists=False)]
    for i, alt in enumerate(accepted):
        if alt['exists'] == present and (not present or codec.json_same(current, alt['value'])):
            status.update(status='apply', matched='before_any[%d]' % i if 'before_any' in op else 'before')
            return status
    status.update(reason='receiver value differs from every accepted pre-value' if present else 'receiver key is absent',
                  current_exists=present, current=current)
    return status


def _server_apply(value, op, kind, status):
    path = op['path']
    if kind == 'list_add':
        target = _walk(value, path)[1]
        target.extend(copy.deepcopy(status['missing']))
        return value
    current = value
    for key in path[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    current[path[-1]] = copy.deepcopy(op['value'] if status['section'] == 'ensure' else op['after'])
    return value


def _server_files_2(assets, payload, allowlist):
    _keys(payload, ['format', 'baseline', 'target', 'allowlist', 'files'], [], 'server payload')
    if not isinstance(payload['files'], dict):
        raise ValueError('Expected server files')
    _allowed(payload, allowlist)
    for relative, spec in payload['files'].items():
        _keys(spec, ['operations'], ['create', 'ensure'], 'server file ' + relative)
        if not isinstance(spec['operations'], list) or not isinstance(spec.get('ensure', []), list):
            raise ValueError('Expected operation lists: ' + relative)
        if 'create' in spec:
            _keys(spec['create'], ['init', 'style'], [], 'create ' + relative)
            if spec['create']['init'] not in ({}, []) or type(spec['create']['init']) not in (dict, list):
                raise ValueError('create.init must be {} or []: ' + relative)
            codec._checked_style(spec['create']['style'])
        ops = [('ensure', i, op) for i, op in enumerate(spec.get('ensure', []))]
        ops += [('operations', i, op) for i, op in enumerate(spec['operations'])]
        if not ops:
            raise ValueError('Server file spec without operations: ' + relative)
        ops = [(s, i, op, _server_op_2(op, s, relative)) for s, i, op in ops]
        _server_paths_checked(ops, relative)
        path = checked_path(assets, relative)
        before = path.read_bytes() if path.exists() else None
        yield relative, spec, path, before, ops


def _server_evaluate(relative, spec, before, ops):
    if before is None:
        if 'create' not in spec:
            return None, [dict(file=relative, section=s, index=i, op=k, path=list(op['path']), line=op.get('line'),
                               status='conflict', matched=None, reason='receiver file is missing')
                          for s, i, op, k in ops]
        value = copy.deepcopy(spec['create']['init'])
    else:
        value = codec.json_loads(before)
    return value, [_server_status(value, op, k, s, i, relative) for s, i, op, k in ops]


def _server_merge(value, ops, statuses):
    """Apply every 'apply' op in place; returns whether anything changed (an apply always changes)."""
    changed = False
    for (s, i, op, kind), status in zip(ops, statuses):
        if status['status'] == 'apply':
            _server_apply(value, op, kind, status)
            changed = True
    return changed


def _server_render(spec, before, merged, changed, format_fallback):
    if before is None:
        style = spec['create']['style']
        return codec._check_render(codec.json_render(merged, style), merged, style), dict(mode='created', style=style)
    if not changed:
        return before, dict(mode='unchanged')
    return codec.json_rewrite(before, merged, fallback=format_fallback)


def server_census(assets, payload, allowlist=None, format_fallback=None):
    payload = _load(payload)
    if payload.get('format') != SERVER_FORMAT_2:
        raise ValueError('server_census reads wf-scoped-update-server-2 payloads only')
    statuses, formats = [], {}
    for relative, spec, _path, before, ops in _server_files_2(assets, payload, allowlist):
        value, file_statuses = _server_evaluate(relative, spec, before, ops)
        statuses += file_statuses
        if value is None:
            formats[relative] = dict(mode='missing')
            continue
        changed = _server_merge(value, ops, file_statuses)
        try:
            formats[relative] = _server_render(spec, before, value, changed, format_fallback)[1]
        except ValueError as exc:
            formats[relative] = dict(mode='error', reason=str(exc))
    counts, sections, lines = _counts(statuses)
    format_errors = sorted(k for k, v in formats.items() if v['mode'] == 'error')
    return dict(kind='server', format=payload['format'], baseline=payload['baseline'], target=payload['target'],
                written=False, ready=counts['conflict'] == 0 and not format_errors, counts=counts,
                by_section=sections, by_line=lines, formats=formats, format_errors=format_errors, operations=statuses)


def _server_plan_2(assets, payload, allowlist, format_fallback):
    staged, everything = [], []
    for relative, spec, path, before, ops in _server_files_2(assets, payload, allowlist):
        value, statuses = _server_evaluate(relative, spec, before, ops)
        everything += statuses
        staged.append((relative, spec, path, before, ops, value, statuses))
    _raise_conflicts('JSON', everything)
    planned, reports = [], []
    for relative, spec, path, before, ops, value, statuses in staged:
        changed = _server_merge(value, ops, statuses)
        after, fmt = _server_render(spec, before, value, changed, format_fallback)
        item = entry(path, before, after, root='server', logical_path=relative)
        reports.append(describe(item) | dict(created=before is None, format=fmt, counts=_counts(statuses)[0]))
        if before != after:
            planned.append(item)
    counts, sections, lines = _counts(everything)
    return planned, dict(kind='server', format=SERVER_FORMAT_2, baseline=payload['baseline'], target=payload['target'],
                         files=reports, counts=counts, by_section=sections, by_line=lines, operations=everything)
