"""Strict native orderedmap/CSV codec plus format-preserving JSON text codec; no filesystem side effects.

API (all pure functions; bytes in, bytes out):

Native tables (unchanged since wf-scoped-update-client-1)
  unpack(raw) -> {key: raw_bytes}          orderedmap bytes -> ordered dict of row bytes
  pack(rows) -> bytes                      inverse of unpack (row bytes copied verbatim)
  csv_read(raw) -> [[str]]                 zlib CSV leaf -> rows
  csv_write(rows) -> bytes                 rows -> zlib CSV leaf ('\\n' terminator, trailing newline)
  node(raw) -> NODE                        payload node: {'raw','csv'} | {'raw':'','empty':True} | {'children':{k:NODE}}
  leaf_raw(NODE) -> bytes                  validated leaf bytes (csv must equal the decoded raw)

CSV cell helpers (wf-scoped-update-client-2 'cells' operations)
  csv_shape(rows) -> [int]                 per-record column counts, e.g. [126] or [126, 126]
  cells_diff(before_rows, after_rows) -> [{'row','col','before','after'}] | None   (None: shapes differ)
  rows_patch_cells(rows, cells, shape=None) -> new rows
      cells = [{'row': int, 'col': int, 'after': str}, ...]; out-of-range, duplicate cells and
      a declared shape that differs from csv_shape(rows) raise ValueError. Input rows are not mutated.
  csv_write_like(rows, template_raw) -> bytes
      like csv_write, but keeps the template leaf's line terminator and trailing-newline convention;
      the result is read back and must equal rows.

JSON text codec (wf-scoped-update-server-2)
  STYLE = {'indent': None|int|'\\t', 'separators': [item_sep, key_sep], 'ensure_ascii': bool,
           'newline': '\\n'|'\\r\\n', 'final_newline': bool, 'bom': bool}
  json_loads(raw) -> value                 strict: duplicate keys, NaN/Infinity and invalid UTF-8 rejected
  json_same(a, b, ordered=False) -> bool   type-strict equality (1 != 1.0 != True); ordered also compares key order
  json_style(raw) -> STYLE | None          the single json.dumps style that reproduces raw byte-for-byte
  json_render(value, STYLE) -> bytes
  json_rewrite(raw, value, fallback=None) -> (bytes, info)
      Writes value back in raw's own formatting.  info['mode']:
        'canonical' - raw has one whole-document style; value re-rendered in it and round-trip checked
                      (render(load(out)) == out and load(out) == value, key order included);
        'splice'    - mixed-style documents (e.g. server gacha.json): untouched members keep their exact
                      bytes, new members/list items are inserted in the style of the nearest sibling,
                      changed values are re-rendered in their own (or a sibling's) style; load(out) == value;
        'fallback-indent2' - only when fallback='indent2' and neither mode can preserve the format.
      Otherwise raises ValueError('Receiver JSON format cannot be preserved: ...').
"""
import base64
import csv
import io
import json
import re
import struct
import zlib


def unpack(raw):
    if len(raw) < 4:
        raise ValueError('short orderedmap')
    size = struct.unpack_from('<I', raw)[0]
    if size > len(raw)-4:
        raise ValueError('orderedmap index out of range')
    index = zlib.decompress(raw[4:4+size])
    if len(index) < 4:
        raise ValueError('short index')
    count = struct.unpack_from('<I', index)[0]
    if 4+8*count > len(index):
        raise ValueError('short index pairs')
    names, data = index[4+8*count:], raw[4+size:]
    result = {}; prev_key = prev_row = 0
    for n in range(count):
        key_end, row_end = struct.unpack_from('<II', index, 4+8*n)
        if not prev_key < key_end <= len(names) or not prev_row <= row_end <= len(data):
            raise ValueError('invalid orderedmap offsets')
        key = names[prev_key:key_end].decode('utf-8')
        if key in result:
            raise ValueError('duplicate orderedmap key: '+key)
        result[key] = data[prev_row:row_end]
        prev_key, prev_row = key_end, row_end
    if prev_key != len(names) or prev_row != len(data):
        raise ValueError('trailing orderedmap bytes')
    return result


def pack(rows):
    names = bytearray(); data = bytearray(); pairs = bytearray()
    for key, raw in rows.items():
        names.extend(key.encode('utf-8')); data.extend(raw)
        pairs.extend(struct.pack('<II', len(names), len(data)))
    index = zlib.compress(struct.pack('<I',len(rows))+pairs+names)
    return struct.pack('<I',len(index))+index+data


def csv_read(raw):
    return list(csv.reader(io.StringIO(zlib.decompress(raw).decode('utf-8'))))


def csv_write(rows):
    stream = io.StringIO(newline='')
    csv.writer(stream, lineterminator='\n').writerows(rows)
    return zlib.compress(stream.getvalue().encode('utf-8'))


def node(raw):
    if raw == b'':
        return {'raw':'', 'empty':True}
    try:
        text = zlib.decompress(raw).decode('utf-8')
    except (zlib.error, UnicodeDecodeError):
        return {'children':{key:node(value) for key,value in unpack(raw).items()}}
    return {'raw':base64.b64encode(raw).decode('ascii'),
            'csv':list(csv.reader(io.StringIO(text)))}


def leaf_raw(value):
    raw = base64.b64decode(value['raw'], validate=True)
    if value.get('empty'):
        if raw != b'': raise ValueError('invalid empty node')
    elif csv_read(raw) != value['csv']:
        raise ValueError('payload leaf text differs from binary')
    return raw


# ---------------------------------------------------------------- CSV cell helpers

def csv_shape(rows):
    return [len(row) for row in rows]


def _cell_index(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError('invalid cell ' + name)
    return value


def cells_diff(before_rows, after_rows):
    """Cell-level difference of two CSV leaves with identical shape, or None when shapes differ."""
    if csv_shape(before_rows) != csv_shape(after_rows):
        return None
    return [dict(row=r, col=c, before=a, after=b)
            for r, (x, y) in enumerate(zip(before_rows, after_rows))
            for c, (a, b) in enumerate(zip(x, y)) if a != b]


def rows_patch_cells(rows, cells, shape=None):
    if shape is not None and csv_shape(rows) != list(shape):
        raise ValueError('CSV shape differs: %s != %s' % (csv_shape(rows), list(shape)))
    out = [list(row) for row in rows]
    seen = set()
    for cell in cells:
        r, c = _cell_index(cell['row'], 'row'), _cell_index(cell['col'], 'col')
        if (r, c) in seen:
            raise ValueError('duplicate cell %d/%d' % (r, c))
        seen.add((r, c))
        if r >= len(out) or c >= len(out[r]):
            raise ValueError('cell out of range %d/%d' % (r, c))
        if not isinstance(cell['after'], str):
            raise ValueError('cell value must be a string')
        out[r][c] = cell['after']
    return out


def csv_write_like(rows, template):
    text = zlib.decompress(template).decode('utf-8')
    terminator = '\r\n' if '\r\n' in text else '\n'
    stream = io.StringIO(newline='')
    csv.writer(stream, lineterminator=terminator).writerows(rows)
    out = stream.getvalue()
    if rows and text and not text.endswith(('\n', '\r')):
        out = out[:-len(terminator)]
    raw = zlib.compress(out.encode('utf-8'))
    if csv_read(raw) != [list(row) for row in rows]:
        raise ValueError('CSV leaf write-back differs from rows')
    return raw


# ---------------------------------------------------------------- JSON text codec

_BOM = '﻿'
_WS = re.compile(r'[ \t\n\r]*')
_NON_ASCII_ESCAPE = re.compile(r'\\u(?:00[89a-fA-F][0-9a-fA-F]|0[1-9a-fA-F][0-9a-fA-F]{2}|[1-9a-fA-F][0-9a-fA-F]{3})')
_INLINE_SEPARATORS = [(', ', ': '), (',', ':'), (',', ': '), (', ', ':')]
_BLOCK_SEPARATORS = [(',', ': '), (', ', ': ')]
_FRAGMENT_STYLES = ([(None, s) for s in _INLINE_SEPARATORS]
                    + [(n, s) for n in (0, 1, 2, 3, 4, '\t') for s in _BLOCK_SEPARATORS])


def _pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValueError('duplicate JSON key: ' + key)
        result[key] = value
    return result


def _invalid(value):
    raise ValueError('invalid JSON number ' + value)


_DECODER = json.JSONDecoder(object_pairs_hook=_pairs, parse_constant=_invalid)


class _SpliceError(ValueError):
    pass


def _json_text(raw):
    """(text with LF newlines and no BOM, bom, newline); mixed newlines raise _SpliceError."""
    text = raw.decode('utf-8') if isinstance(raw, (bytes, bytearray)) else raw
    bom = text.startswith(_BOM)
    if bom:
        text = text[1:]
    if '\r' in text:
        if text.count('\r') != text.count('\r\n') or text.count('\n') != text.count('\r\n'):
            raise _SpliceError('mixed newlines')
        return text.replace('\r\n', '\n'), bom, '\r\n'
    return text, bom, '\n'


def _strict(text):
    start = _WS.match(text, 0).end()
    value, end = _DECODER.raw_decode(text, start)
    if _WS.match(text, end).end() != len(text):
        raise ValueError('trailing JSON data')
    return value


def json_loads(raw):
    try:
        text = _json_text(raw)[0]
    except _SpliceError:
        text = (raw.decode('utf-8') if isinstance(raw, (bytes, bytearray)) else raw).lstrip(_BOM)
    return _strict(text)


def json_same(a, b, ordered=False):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        if (list(a) != list(b)) if ordered else (a.keys() != b.keys()):
            return False
        return all(json_same(a[k], b[k], ordered) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(json_same(x, y, ordered) for x, y in zip(a, b))
    return a == b


def _dumps(value, indent, separators, ensure_ascii):
    return json.dumps(value, indent=indent, separators=tuple(separators), ensure_ascii=ensure_ascii)


def json_style(raw):
    try:
        text, bom, newline = _json_text(raw)
    except _SpliceError:
        return None
    value = _strict(text)
    final = text.endswith('\n')
    body = text[:-1] if final else text
    if not body or body != body.strip(' \t\n'):
        return None
    ascii_options = [False, True] if body.isascii() else [False]
    if '\n' in body:
        match = re.match(r'[\[{]\n([ \t]*)', body)
        if not match:
            return None
        ws = match.group(1)
        if ws == '\t':
            indent = '\t'
        elif set(ws) <= {' '}:
            indent = len(ws)
        else:
            return None
        candidates = [(indent, s) for s in _BLOCK_SEPARATORS]
    else:
        candidates = [(None, s) for s in _INLINE_SEPARATORS]
    for ensure_ascii in ascii_options:
        for indent, separators in candidates:
            if _dumps(value, indent, separators, ensure_ascii) == body:
                return dict(indent=indent, separators=list(separators), ensure_ascii=ensure_ascii,
                            newline=newline, final_newline=final, bom=bom)
    return None


def _checked_style(style):
    if not isinstance(style, dict) or set(style) != {'indent', 'separators', 'ensure_ascii', 'newline', 'final_newline', 'bom'}:
        raise ValueError('invalid JSON style declaration')
    indent = style['indent']
    if not (indent is None or indent == '\t' or (type(indent) is int and 0 <= indent <= 8)):
        raise ValueError('invalid JSON style indent')
    separators = tuple(style['separators'])
    if separators not in _INLINE_SEPARATORS:
        raise ValueError('invalid JSON style separators')
    if style['newline'] not in ('\n', '\r\n') or not all(type(style[k]) is bool for k in ('ensure_ascii', 'final_newline', 'bom')):
        raise ValueError('invalid JSON style flags')
    return style


def json_render(value, style):
    style = _checked_style(style)
    text = _dumps(value, style['indent'], style['separators'], style['ensure_ascii'])
    if style['final_newline']:
        text += '\n'
    if style['newline'] == '\r\n':
        text = text.replace('\n', '\r\n')
    return ((_BOM if style['bom'] else '') + text).encode('utf-8')


def _check_render(out, value, style):
    loaded = json_loads(out)
    if not json_same(loaded, value, ordered=True) or json_render(loaded, style) != out:
        raise ValueError('JSON round-trip check failed')
    return out


# ---- splice writer: edits only the changed spans of a mixed-style document

def _ws(text, index):
    return _WS.match(text, index).end()


def _line_indent(text, index):
    start = text.rfind('\n', 0, index) + 1
    return _WS.match(text, start).group(0).split('\n')[-1] if start < index else ''


def _object_members(text, start):
    members = []
    i = _ws(text, start + 1)
    if text[i] == '}':
        return members
    while True:
        if text[i] != '"':
            raise _SpliceError('unexpected object member')
        key, key_end = json.decoder.scanstring(text, i + 1)
        colon = _ws(text, key_end)
        if text[colon] != ':':
            raise _SpliceError('unexpected object member')
        value_start = _ws(text, colon + 1)
        value, value_end = _DECODER.raw_decode(text, value_start)
        members.append((key, i, key_end, value_start, value_end, value))
        k = _ws(text, value_end)
        if text[k] == '}':
            return members
        if text[k] != ',':
            raise _SpliceError('unexpected object separator')
        i = _ws(text, k + 1)


def _array_items(text, start):
    items = []
    i = _ws(text, start + 1)
    if text[i] == ']':
        return items
    while True:
        value, end = _DECODER.raw_decode(text, i)
        items.append((i, end, value))
        k = _ws(text, end)
        if text[k] == ']':
            return items
        if text[k] != ',':
            raise _SpliceError('unexpected array separator')
        i = _ws(text, k + 1)


def _fragment_style(text, spans, ensure_ascii):
    for start, end in spans[:64]:
        value, stop = _DECODER.raw_decode(text, start)
        if stop != end or not isinstance(value, (dict, list)) or not value:
            continue
        base, source = _line_indent(text, start), text[start:end]
        matches = [(indent, seps) for indent, seps in _FRAGMENT_STYLES
                   if _render_fragment(value, indent, seps, ensure_ascii, base) == source]
        if len(matches) == 1:
            return matches[0]
    return None


def _render_fragment(value, indent, separators, ensure_ascii, base):
    text = _dumps(value, indent, separators, ensure_ascii)
    return text.replace('\n', '\n' + base) if indent is not None else text


def _fragment(text, value, spans, base, ensure_ascii):
    if not isinstance(value, (dict, list)) or not value:
        return json.dumps(value, ensure_ascii=ensure_ascii)
    style = _fragment_style(text, spans, ensure_ascii)
    if style is None:
        raise _SpliceError('no unambiguous sibling style for an inserted value')
    return _render_fragment(value, style[0], style[1], ensure_ascii, base)


def _separator(text, previous_end, next_start, open_index, first_start, kind, hint=None):
    if previous_end is not None:
        sep = text[previous_end:next_start]
    else:
        lead = text[open_index + 1:first_start]
        if lead:
            sep = ',' + lead
        elif hint is not None:
            sep = ', ' if hint.endswith(' ') else ','
        else:
            raise _SpliceError('ambiguous separator in a single-item ' + kind)
    if not re.fullmatch(r'[ \t\n]*,[ \t\n]*', sep):
        raise _SpliceError('unexpected ' + kind + ' separator')
    return sep, (sep.rsplit('\n', 1)[1] if '\n' in sep else None)


def _splice_value(text, start, end, old, new, context, ensure_ascii):
    """Text for new at old's span.  context = fallback style spans (siblings, then ancestors)."""
    if json_same(old, new, ordered=True):
        return text[start:end]
    own = [(start, end)] + context
    if isinstance(old, dict) and isinstance(new, dict) and list(new)[:len(old)] == list(old):
        members = _object_members(text, start)
        spans = [(m[3], m[4]) for m in members]
        out, cursor = [], start
        for index, (key, _ks, _ke, vs, ve, value) in enumerate(members):
            if not json_same(value, new[key], ordered=True):
                near = sorted((j for j in range(len(spans)) if j != index), key=lambda j: abs(j - index))
                out.append(text[cursor:vs])
                out.append(_splice_value(text, vs, ve, value, new[key], [spans[j] for j in near] + own, ensure_ascii))
                cursor = ve
        added = list(new)[len(old):]
        if added:
            if not members:
                raise _SpliceError('cannot infer the layout of an empty object')
            last = members[-1]
            sep, base = _separator(text, members[-2][4] if len(members) > 1 else None, last[1],
                                   start, members[0][1], 'object', text[last[2]:last[3]])
            key_sep = text[last[2]:last[3]]
            if not re.fullmatch(r'[ \t\n]*:[ \t\n]*', key_sep):
                raise _SpliceError('unexpected key separator')
            base = _line_indent(text, last[1]) if base is None else base
            out.append(text[cursor:last[4]])
            cursor = last[4]
            for key in added:
                out.append(sep + json.dumps(key, ensure_ascii=ensure_ascii) + key_sep
                           + _fragment(text, new[key], spans[::-1] + own, base, ensure_ascii))
        out.append(text[cursor:end])
        return ''.join(out)
    if (isinstance(old, list) and isinstance(new, list) and len(new) > len(old)
            and all(json_same(a, b, ordered=True) for a, b in zip(old, new))):
        items = _array_items(text, start)
        if not items:
            raise _SpliceError('cannot infer the layout of an empty array')
        last = items[-1]
        sep, base = _separator(text, items[-2][1] if len(items) > 1 else None, last[0], start, items[0][0], 'array')
        base = _line_indent(text, last[0]) if base is None else base
        spans = [(s, e) for s, e, _v in items][::-1] + own
        tail = ''.join(sep + _fragment(text, value, spans, base, ensure_ascii) for value in new[len(old):])
        return text[start:last[1]] + tail + text[last[1]:end]
    return _fragment(text, new, own, _line_indent(text, start), ensure_ascii)


def _splice_document(text, value):
    start = _ws(text, 0)
    old, end = _DECODER.raw_decode(text, start)
    body = text[:-1] if text.endswith('\n') else text
    ensure_ascii = body.isascii() and bool(_NON_ASCII_ESCAPE.search(body))
    return text[:start] + _splice_value(text, start, end, old, value, [], ensure_ascii) + text[end:]


def json_rewrite(raw, value, fallback=None):
    if fallback not in (None, 'indent2'):
        raise ValueError('unknown JSON format fallback')
    style = json_style(raw)
    if style is not None:
        return _check_render(json_render(value, style), value, style), dict(mode='canonical', style=style)
    try:
        text, bom, newline = _json_text(raw)
        spliced = _splice_document(text, value)
    except _SpliceError as exc:
        if fallback != 'indent2':
            raise ValueError('Receiver JSON format cannot be preserved: ' + str(exc)) from None
        style = dict(indent=2, separators=[',', ': '], ensure_ascii=False, newline='\n', final_newline=True, bom=False)
        return _check_render(json_render(value, style), value, style), dict(mode='fallback-indent2', reason=str(exc), style=style)
    if newline == '\r\n':
        spliced = spliced.replace('\n', '\r\n')
    out = ((_BOM if bom else '') + spliced).encode('utf-8')
    if not json_same(json_loads(out), value, ordered=True):
        raise ValueError('JSON splice round-trip check failed')
    return out, dict(mode='splice')
