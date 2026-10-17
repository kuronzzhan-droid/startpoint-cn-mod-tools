"""wf_share_update_codec: CSV cell helpers and the format-preserving JSON text codec."""
import json
from pathlib import Path
import sys
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_share_update_codec as codec


def gacha_like():
    """Mixed style like server gacha.json: default separators at the top, compact pools inside."""
    first = json.dumps({'type': 0, 'pool': [{'id': 1, 'odds': 5, 'rarity': 8.086253}]})
    second = json.dumps({'type': 1, 'pool': [{'id': 2, 'odds': 7, 'rarity': 0.0}]}, separators=(',', ':'))
    return ('{"1": ' + first + ', "990002": ' + second + '}').encode('utf-8')


class CellTests(unittest.TestCase):
    def test_cells_diff_same_shape_and_shape_change(self):
        a = [['1', 'x', 'y'], ['2', 'p', 'q']]
        b = [['1', 'x', 'Y'], ['2', 'P', 'q']]
        self.assertEqual(codec.cells_diff(a, b), [dict(row=0, col=2, before='y', after='Y'),
                                                  dict(row=1, col=1, before='p', after='P')])
        self.assertIsNone(codec.cells_diff(a, b[:1]))
        self.assertIsNone(codec.cells_diff([['1', 'x']], [['1', 'x', '']]))

    def test_rows_patch_cells_only_touches_declared_cells(self):
        rows = [['a', 'b', 'c']]
        out = codec.rows_patch_cells(rows, [dict(row=0, col=1, after='B')], shape=[3])
        self.assertEqual(out, [['a', 'B', 'c']])
        self.assertEqual(rows, [['a', 'b', 'c']])

    def test_rows_patch_cells_rejects_bad_cells(self):
        rows = [['a', 'b']]
        for cells, shape, message in [
                ([dict(row=0, col=2, after='x')], None, 'out of range'),
                ([dict(row=1, col=0, after='x')], None, 'out of range'),
                ([dict(row=0, col=0, after='x'), dict(row=0, col=0, after='y')], None, 'duplicate'),
                ([dict(row=0, col=0, after=1)], None, 'string'),
                ([dict(row=True, col=0, after='x')], None, 'invalid cell'),
                ([dict(row=0, col=0, after='x')], [3], 'shape')]:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                codec.rows_patch_cells(rows, cells, shape)

    def test_csv_write_like_keeps_terminator_and_missing_final_newline(self):
        rows = [['1', 'a,b', 'x'], ['2', '', 'q"q']]
        plain = zlib.compress(b'1,old\n2,old')
        out = zlib.decompress(codec.csv_write_like(rows, plain)).decode()
        self.assertFalse(out.endswith('\n'))
        self.assertEqual(codec.csv_read(codec.csv_write_like(rows, plain)), rows)
        crlf = zlib.compress(b'1,old\r\n')
        out = zlib.decompress(codec.csv_write_like(rows, crlf)).decode()
        self.assertTrue(out.endswith('\r\n'))
        self.assertEqual(out.count('\r\n'), 2)
        self.assertEqual(codec.csv_write_like(rows, codec.csv_write([['x']])), codec.csv_write(rows))


class JsonStyleTests(unittest.TestCase):
    VALUE = {'1': {'name': '老旧短剑', 'rarity': '0'}, '2': [1, 2]}

    def styles(self):
        v = self.VALUE
        yield 'compact-default noLF', json.dumps(v, ensure_ascii=False).encode()
        yield 'compact , : ', json.dumps(v, ensure_ascii=False, separators=(',', ':')).encode()
        yield 'indent0 noLF', json.dumps(v, ensure_ascii=False, indent=0).encode()
        yield 'indent1 noLF', json.dumps(v, ensure_ascii=False, indent=1).encode()
        yield 'indent2 +LF', (json.dumps(v, ensure_ascii=False, indent=2) + '\n').encode()
        yield 'indent2 CRLF', (json.dumps(v, ensure_ascii=False, indent=2) + '\n').replace('\n', '\r\n').encode()
        yield 'tab', json.dumps(v, ensure_ascii=False, indent='\t').encode()
        yield 'ascii', json.dumps(v, indent=2).encode()
        yield 'bom', '﻿'.encode() + json.dumps(v, ensure_ascii=False).encode()

    def test_every_single_style_round_trips_byte_for_byte(self):
        for name, raw in self.styles():
            with self.subTest(name):
                style = codec.json_style(raw)
                self.assertIsNotNone(style)
                self.assertEqual(codec.json_render(codec.json_loads(raw), style), raw)

    def test_detected_style_fields(self):
        raw = (json.dumps(self.VALUE, ensure_ascii=False, indent=2) + '\n').replace('\n', '\r\n').encode()
        self.assertEqual(codec.json_style(raw), dict(indent=2, separators=[',', ': '], ensure_ascii=False,
                                                     newline='\r\n', final_newline=True, bom=False))
        self.assertTrue(codec.json_style(json.dumps(self.VALUE).encode())['ensure_ascii'])

    def test_mixed_documents_have_no_whole_style(self):
        self.assertIsNone(codec.json_style(gacha_like()))
        self.assertIsNone(codec.json_style(b'{"a": 1.0E5, "b": 2}'))
        self.assertIsNone(codec.json_style(b'{\n  "a": 1\n}\r\n'))

    def test_strict_loading(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            codec.json_loads(b'{"a": 1, "a": 2}')
        with self.assertRaisesRegex(ValueError, 'invalid JSON number'):
            codec.json_loads(b'{"a": NaN}')
        with self.assertRaises(UnicodeDecodeError):
            codec.json_loads(b'{"a": "\xff"}')

    def test_json_same_is_type_strict(self):
        self.assertFalse(codec.json_same(1, 1.0))
        self.assertFalse(codec.json_same(1, True))
        self.assertFalse(codec.json_same({'a': [1]}, {'a': [1.0]}))
        self.assertTrue(codec.json_same({'a': 1, 'b': 2}, {'b': 2, 'a': 1}))
        self.assertFalse(codec.json_same({'a': 1, 'b': 2}, {'b': 2, 'a': 1}, ordered=True))


class JsonRewriteTests(unittest.TestCase):
    def test_canonical_insert_keeps_indent1_without_final_newline(self):
        old = {'5900101': {'name': '死神', 'rarity': '5'}}
        raw = json.dumps(old, ensure_ascii=False, indent=1).encode()
        new = dict(old, **{'5910101': {'name': '诅咒', 'rarity': '5'}})
        out, info = codec.json_rewrite(raw, new)
        self.assertEqual(info['mode'], 'canonical')
        self.assertEqual(out, json.dumps(new, ensure_ascii=False, indent=1).encode())
        self.assertTrue(out.startswith(raw[:-2]))

    def test_canonical_crlf_file_stays_crlf(self):
        old = {'99': {'990099001': {'stock': 1}}}
        raw = (json.dumps(old, indent=2) + '\n').replace('\n', '\r\n').encode()
        new = {'99': {'990099001': {'stock': 1}, '990099032': {'stock': 60}}}
        out, info = codec.json_rewrite(raw, new)
        self.assertEqual(info['mode'], 'canonical')
        self.assertNotIn(b'\n', out.replace(b'\r\n', b''))
        self.assertTrue(out.endswith(b'}\r\n'))
        self.assertEqual(codec.json_loads(out), new)

    def test_splice_mixed_document_does_not_balloon(self):
        raw = gacha_like()
        old = codec.json_loads(raw)
        new = dict(old, **{'990003': {'type': 1, 'pool': [{'id': 3, 'odds': 456, 'rarity': 8.5}]}})
        out, info = codec.json_rewrite(raw, new)
        self.assertEqual(info['mode'], 'splice')
        fragment = ', "990003": ' + json.dumps(new['990003'], separators=(',', ':'))
        self.assertEqual(out, raw[:-1] + fragment.encode() + b'}')
        self.assertEqual(len(out) - len(raw), len(fragment))
        self.assertTrue(codec.json_same(codec.json_loads(out), new, ordered=True))

    def test_splice_keeps_untouched_bytes_and_rebases_indentation(self):
        raw = (b'{\n  "keep": {"odd":1.0E5},\n  "grow": {\n    "a": 1,\n    "b": 2\n  },\n'
               b'  "list": [1, 2]\n}\n')
        old = codec.json_loads(raw)
        new = {'keep': old['keep'], 'grow': {'a': 1, 'b': 2, 'c': {'x': [1, 2]}}, 'list': [1, 2, 3],
               'added': {'y': 1, 'z': 2}}
        out, info = codec.json_rewrite(raw, new)
        self.assertEqual(info['mode'], 'splice')
        self.assertEqual(out, (b'{\n  "keep": {"odd":1.0E5},\n  "grow": {\n    "a": 1,\n    "b": 2,\n'
                               b'    "c": {\n      "x": [\n        1,\n        2\n      ]\n    }\n  },\n'
                               b'  "list": [1, 2, 3],\n  "added": {\n    "y": 1,\n    "z": 2\n  }\n}\n'))

    def test_splice_replaces_changed_value_in_its_own_style(self):
        raw = b'{"a": {"k":1,"v":[1,2]}, "b": 1.0E5}'
        out, info = codec.json_rewrite(raw, {'a': {'k': 2, 'v': [1, 2]}, 'b': 1.0E5})
        self.assertEqual(info['mode'], 'splice')
        self.assertEqual(out, b'{"a": {"k":2,"v":[1,2]}, "b": 1.0E5}')

    def test_unpreservable_format_is_rejected_unless_fallback(self):
        raw = b'{"x": 1.0E5, "one": {}}'
        new = {'x': 1.0E5, 'one': {}, 'n': {'a': 1, 'b': 2}}
        with self.assertRaisesRegex(ValueError, 'cannot be preserved'):
            codec.json_rewrite(raw, new)
        out, info = codec.json_rewrite(raw, new, fallback='indent2')
        self.assertEqual(info['mode'], 'fallback-indent2')
        self.assertEqual(out, (json.dumps(new, indent=2, ensure_ascii=False) + '\n').encode())
        with self.assertRaisesRegex(ValueError, 'cannot be preserved'):
            codec.json_rewrite(b'{"a": 1}\r\n\n', {'a': 1, 'b': [1, 2]})

    def test_render_rejects_invalid_style(self):
        with self.assertRaisesRegex(ValueError, 'style'):
            codec.json_render({}, dict(indent=2))
        with self.assertRaisesRegex(ValueError, 'separators'):
            codec.json_render({}, dict(indent=2, separators=[';', '='], ensure_ascii=False, newline='\n',
                                      final_newline=False, bom=False))


if __name__ == '__main__':
    unittest.main()
