"""wf-scoped-update-client-2: cells, before_any, create_parents, ensure, sub-key-only nesting."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_share_update_codec as codec
import wf_share_update_tables as update
from wf_share_asset_index import relative_path
from wf_share_update_io import apply_plans

LOGICAL = 'master/quest/boss_battle_quest.orderedmap'


def leaf(rows):
    return codec.csv_write(rows)


def node(rows):
    return codec.node(leaf(rows))


class Client2Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.receipts = 0

    def write(self, rows, logical=LOGICAL):
        path = self.root / relative_path(logical)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(codec.pack(rows))
        return path

    def payload(self, operations, logical=LOGICAL, **table):
        return dict(format='wf-scoped-update-client-2', baseline='gray-inferred', target='1.4.9999',
                    tables={logical: dict(operations=operations, **table)})

    def apply(self, payload):
        plans, report = update.client_plan(self.root, payload)
        self.receipts += 1
        apply_plans(plans, self.root / ('receipt-%d' % self.receipts))
        return plans, report

    def nested_fixture(self):
        """[1][98] sentinel, [1][99] with official 001 and foreign 9999, plus an unrelated top-level row."""
        inner = {'001': leaf([['1099001', 'official']]), '9999': leaf([['receiver-only']])}
        outer = {'98': codec.pack({'x': leaf([['sentinel']])}), '99': codec.pack(inner)}
        return self.write({'1': codec.pack(outer), 'other': leaf([['keep']])})

    def rows_at(self, path, *keys):
        rows = codec.unpack(path.read_bytes())
        for key in keys[:-1]:
            rows = codec.unpack(rows[key])
        return rows[keys[-1]]

    # ------------------------------------------------------------ nested sub-key ops

    def test_nested_add_preserves_siblings_and_replays_idempotently(self):
        path = self.nested_fixture()
        before = path.read_bytes()
        sentinel, foreign = self.rows_at(path, '1', '98'), self.rows_at(path, '1', '99', '9999')
        other = codec.unpack(before)['other']
        payload = self.payload([dict(path=['1', '99', '031'], before=None, after=node([['1099031', 'v2']])),
                                dict(path=['1', '99', '051'], before=None, after=node([['1099051', 'v2']]))])
        plans, report = self.apply(payload)
        self.assertEqual(len(plans), 1)
        self.assertEqual(report['counts'], dict(apply=2, already=0, conflict=0))
        self.assertEqual(self.rows_at(path, '1', '98'), sentinel)
        self.assertEqual(self.rows_at(path, '1', '99', '9999'), foreign)
        self.assertEqual(codec.unpack(path.read_bytes())['other'], other)
        self.assertEqual(codec.csv_read(self.rows_at(path, '1', '99', '031')), [['1099031', 'v2']])
        self.assertEqual(list(codec.unpack(self.rows_at(path, '1', '99'))), ['001', '9999', '031', '051'])
        after = path.read_bytes()
        plans, report = update.client_plan(self.root, payload)
        self.assertEqual(plans, [])
        self.assertEqual(report['counts'], dict(apply=0, already=2, conflict=0))
        self.assertEqual(path.read_bytes(), after)

    def test_missing_parent_is_conflict_by_default(self):
        path = self.write({'1': codec.pack({'98': codec.pack({})})})
        raw = path.read_bytes()
        payload = self.payload([dict(path=['1', '99', '031'], before=None, after=node([['x']]))])
        with self.assertRaisesRegex(ValueError, 'conflict.*parent missing: 1/99'):
            update.client_plan(self.root, payload)
        census = update.client_census(self.root, payload)
        self.assertFalse(census['ready'])
        self.assertEqual(census['operations'][0]['reason'], 'parent missing: 1/99')
        self.assertEqual(path.read_bytes(), raw)

    def test_create_parents_builds_only_the_declared_chain(self):
        path = self.write({'1': codec.pack({'98': codec.pack({'x': leaf([['s']])})})})
        payload = self.payload([dict(path=['1', '99', '031'], before=None, after=node([['x']]), create_parents=True)])
        census = update.client_census(self.root, payload)
        self.assertTrue(census['operations'][0]['creates_parents'])
        self.apply(payload)
        self.assertEqual(list(codec.unpack(self.rows_at(path, '1', '99'))), ['031'])
        self.assertEqual(codec.csv_read(self.rows_at(path, '1', '98', 'x')), [['s']])
        self.assertEqual(update.client_plan(self.root, payload)[0], [])

    def test_leaf_parent_is_conflict_even_with_create_parents(self):
        self.write({'1': leaf([['not', 'a', 'table']])})
        payload = self.payload([dict(path=['1', '99'], before=None, after=node([['x']]), create_parents=True)])
        with self.assertRaisesRegex(ValueError, 'parent is a CSV leaf: 1'):
            update.client_plan(self.root, payload)

    def test_whole_nested_row_replacement_is_refused(self):
        self.nested_fixture()
        old_nested = codec.node(codec.pack({'001': leaf([['1099001', 'official']])}))
        new_nested = codec.node(codec.pack({'001': leaf([['1099001', 'v2']])}))
        for op in [dict(path=['1', '99'], before=old_nested, after=new_nested),
                   dict(path=['1', '99'], before=node([['flat']]), after=new_nested),
                   dict(path=['1', '99'], before_any=[None, old_nested], after=node([['flat']]))]:
            with self.subTest(op=op['path']), self.assertRaisesRegex(ValueError, 'Nested whole-row replacement'):
                update.client_plan(self.root, self.payload([op]))

    def test_new_subtree_is_allowed_when_absent(self):
        path = self.nested_fixture()
        subtree = codec.node(codec.pack({'w01': leaf([['mod_fb2']]), 'w02': leaf([['mod_fb2b']])}))
        payload = self.payload([dict(path=['1', 'mod_fb2_052'], before=None, after=subtree)])
        self.apply(payload)
        self.assertEqual(update.semantic(codec.node(self.rows_at(path, '1', 'mod_fb2_052'))), update.semantic(subtree))
        self.assertEqual(update.client_plan(self.root, payload)[0], [])

    def test_existing_nested_value_differs_from_new_subtree_is_conflict(self):
        self.nested_fixture()
        subtree = codec.node(codec.pack({'001': leaf([['1099001', 'official']])}))
        with self.assertRaisesRegex(ValueError, 'conflict'):
            update.client_plan(self.root, self.payload([dict(path=['1', '99'], before=None, after=subtree)]))

    def test_all_ops_already_leave_nested_table_bytes_untouched(self):
        def pack_level(rows, level):
            raw = codec.pack(rows)
            size = int.from_bytes(raw[:4], 'little')
            index = zlib.compress(zlib.decompress(raw[4:4 + size]), level)
            return len(index).to_bytes(4, 'little') + index + raw[4 + size:]
        # The receiver's nested maps were written with another zlib level: bytes differ from a repack.
        outer = pack_level({'99': pack_level({'001': leaf([['a']])}, 1)}, 1)
        self.assertNotEqual(outer, codec.pack(codec.unpack(outer)))
        path = self.root / relative_path(LOGICAL)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(pack_level({'1': outer, 'x': leaf([['x']])}, 9))
        stored = path.read_bytes()
        self.assertNotEqual(stored, codec.pack(codec.unpack(stored)))
        payload = self.payload([dict(path=['1', '99', '001'], before=node([['old']]), after=node([['a']]))])
        plans, report = update.client_plan(self.root, payload)
        self.assertEqual(plans, [])
        self.assertEqual(report['files'][0]['after_sha256'], report['files'][0]['before_sha256'])
        self.assertEqual(path.read_bytes(), stored)

    # ------------------------------------------------------------ conflict / preservation / idempotence

    def test_top_level_conflict_is_read_only_and_census_lists_every_conflict(self):
        path = self.write({'a': leaf([['receiver-custom']]), 'b': leaf([['receiver-custom']]), 'c': leaf([['old']])})
        raw = path.read_bytes()
        payload = self.payload([dict(path=['a'], before=node([['old']]), after=node([['new']])),
                                dict(path=['b'], before=node([['old']]), after=node([['new']])),
                                dict(path=['c'], before=node([['old']]), after=node([['new']]))])
        with self.assertRaisesRegex(ValueError, r'Receiver native conflict: .*\|a: .*\(\+1 more conflicts\)'):
            update.client_plan(self.root, payload)
        census = update.client_census(self.root, payload)
        self.assertEqual(census['counts'], dict(apply=1, already=0, conflict=2))
        self.assertEqual([s['path'] for s in census['operations'] if s['status'] == 'conflict'], [['a'], ['b']])
        self.assertEqual(census['operations'][0]['cells_vs_after'], [dict(row=0, col=0, before='receiver-custom', after='new')])
        self.assertFalse(census['written'])
        self.assertEqual(path.read_bytes(), raw)

    def test_unclaimed_rows_keep_their_bytes(self):
        foreign = zlib.compress(b'foreign,row\n', 9)
        path = self.write({'foreign': foreign, 'mine': leaf([['old']])})
        self.apply(self.payload([dict(path=['mine'], before=node([['old']]), after=node([['new']]))]))
        rows = codec.unpack(path.read_bytes())
        self.assertEqual(rows['foreign'], foreign)
        self.assertEqual(list(rows), ['foreign', 'mine'])

    # ------------------------------------------------------------ before_any

    def test_before_any_accepts_each_listed_prevalue_and_rejects_others(self):
        official, spill = node([['envy', 'official']]), node([['envy', 'trial x3']])
        target = node([['envy', 'official-restored']])
        op = dict(path=['state'], before_any=[spill, official, None], after=target)
        for index, current in enumerate([spill, official, None]):
            with self.subTest(index=index):
                rows = {} if current is None else {'state': update.encode(current)}
                self.write(dict(rows, other=leaf([['x']])))
                census = update.client_census(self.root, self.payload([op]))
                self.assertEqual(census['operations'][0]['matched'], 'before_any[%d]' % index)
                self.apply(self.payload([op]))
                self.assertEqual(update.semantic(codec.node(self.rows_at(self.root / relative_path(LOGICAL), 'state'))),
                                 update.semantic(target))
        self.write({'state': leaf([['envy', 'receiver-own']])})
        census = update.client_census(self.root, self.payload([op]))
        self.assertEqual(census['operations'][0]['status'], 'conflict')
        with self.assertRaisesRegex(ValueError, 'conflict'):
            update.client_plan(self.root, self.payload([op]))

    def test_before_any_without_null_rejects_absent_key(self):
        self.write({'other': leaf([['x']])})
        op = dict(path=['state'], before_any=[node([['a']])], after=node([['b']]))
        with self.assertRaisesRegex(ValueError, 'receiver key is absent'):
            update.client_plan(self.root, self.payload([op]))

    # ------------------------------------------------------------ cells

    def test_cells_write_only_declared_cells_and_keep_receiver_columns(self):
        ours_before = [['139990', 'name', 'x', 'y', 'z', '']]
        receiver = [['139990', 'gray-renamed', 'x', 'gray-col3', 'z', '']]
        path = self.write({'139990': leaf(receiver), 'other': leaf([['o']])})
        op = dict(path=['139990'], shape=[6], cells=[dict(row=0, col=5, before='', after='tag_paradox')])
        self.apply(self.payload([op]))
        self.assertEqual(codec.csv_read(self.rows_at(path, '139990')),
                         [['139990', 'gray-renamed', 'x', 'gray-col3', 'z', 'tag_paradox']])
        self.assertEqual(update.client_plan(self.root, self.payload([op]))[0], [])
        self.assertNotEqual(receiver, ours_before)

    def test_cells_before_any_and_per_cell_status(self):
        rows = [['2370100', 'x', 'y', 'item/materials/mod/abyss/abyss_core', 'item/materials/mod/abyss/abyss_core']]
        path = self.write({'2370100': leaf(rows)})
        op = dict(path=['2370100'], cells=[
            dict(row=0, col=4, before_any=['item/materials/mod/abyss/abyss_core', 'item_icon/materials/mod/abyss/abyss_core'],
                 after='item_icon/materials/mod/abyss/abyss_core'),
            dict(row=0, col=1, before='old-x', after='x')])
        census = update.client_census(self.root, self.payload([op]))
        cells = census['operations'][0]['cells']
        self.assertEqual([(c['status'], c['matched']) for c in cells], [('apply', 'before_any[0]'), ('already', 'after')])
        self.apply(self.payload([op]))
        self.assertEqual(codec.csv_read(self.rows_at(path, '2370100'))[0][3:],
                         ['item/materials/mod/abyss/abyss_core', 'item_icon/materials/mod/abyss/abyss_core'])
        self.assertEqual(update.client_plan(self.root, self.payload([op]))[0], [])

    def test_cells_conflicts(self):
        self.write({'k': leaf([['a', 'b'], ['c', 'd']]), 'nested': codec.pack({'x': leaf([['1']])})})
        cases = [(dict(path=['k'], cells=[dict(row=0, col=1, before='zz', after='B')]), 'cell conflict at 0/1'),
                 (dict(path=['k'], cells=[dict(row=0, col=5, before='', after='B')]), 'cell conflict at 0/5'),
                 (dict(path=['k'], shape=[2], cells=[dict(row=0, col=1, before='b', after='B')]), 'shape differs'),
                 (dict(path=['missing'], cells=[dict(row=0, col=0, before='', after='B')]), 'cells target is absent'),
                 (dict(path=['nested'], cells=[dict(row=0, col=0, before='', after='B')]), 'not a CSV leaf')]
        for op, reason in cases:
            with self.subTest(reason=reason):
                census = update.client_census(self.root, self.payload([op]))
                self.assertIn(reason, census['operations'][0]['reason'])
                with self.assertRaisesRegex(ValueError, 'conflict'):
                    update.client_plan(self.root, self.payload([op]))

    def test_cells_keep_receiver_trailing_newline_convention(self):
        stripped = zlib.compress('139990,a,b'.encode())
        path = self.write({'139990': stripped})
        self.apply(self.payload([dict(path=['139990'], cells=[dict(row=0, col=2, before='b', after='c')])]))
        self.assertEqual(zlib.decompress(self.rows_at(path, '139990')), b'139990,a,c')

    # ------------------------------------------------------------ ensure / table create

    def test_ensure_adds_missing_skips_equal_and_conflicts_on_difference(self):
        path = self.write({'other': leaf([['x']])})
        category = node([['99', 'five boss shop']])
        payload = self.payload([dict(path=['990099032'], before=None, after=node([['032']]))],
                               ensure=[dict(path=['99'], value=category, line='closure')])
        plans, report = self.apply(payload)
        self.assertEqual(report['by_section']['ensure'], dict(apply=1, already=0, conflict=0))
        self.assertEqual(report['by_line']['closure'], dict(apply=1, already=0, conflict=0))
        self.assertEqual(update.client_census(self.root, payload)['by_section']['ensure']['already'], 1)
        self.write({'99': leaf([['99', 'gray category']])})
        census = update.client_census(self.root, payload)
        ensure = [s for s in census['operations'] if s['section'] == 'ensure'][0]
        self.assertEqual(ensure['status'], 'conflict')

    def test_missing_table_needs_create(self):
        logical = 'master/gacha_odds/cnmod_weapon_gacha_5.orderedmap'
        op = dict(path=['1'], before=None, after=node([['5910101', '456']]))
        with self.assertRaisesRegex(ValueError, 'receiver table is missing'):
            update.client_plan(self.root, self.payload([op], logical=logical))
        plans, report = self.apply(self.payload([op], logical=logical, create=True))
        self.assertTrue(report['files'][0]['created'])
        path = self.root / relative_path(logical)
        self.assertEqual(codec.csv_read(codec.unpack(path.read_bytes())['1']), [['5910101', '456']])
        self.assertEqual(update.client_plan(self.root, self.payload([op], logical=logical, create=True))[0], [])

    # ------------------------------------------------------------ payload validation

    def test_invalid_payloads(self):
        self.write({'a': leaf([['x']])})
        cases = [
            ([dict(path=['a'], before=None, after=node([['y']]))], dict(ensure=[dict(path=['a'], value=node([['y']]))]), 'Overlapping'),
            ([dict(path=['a'], before=None, before_any=[None], after=node([['y']]))], {}, 'exactly one'),
            ([dict(path=['a'], after=node([['y']]))], {}, 'exactly one'),
            ([dict(path=['a'], before=None, after=node([['y']]), typo=1)], {}, 'unknown'),
            ([dict(path=['a'], before_any=[], after=node([['y']]))], {}, 'non-empty'),
            ([dict(path=['a'], cells=[dict(row=0, col=0, before='x', after=1)])], {}, 'strings'),
            ([dict(path=['a'], cells=[dict(row=0, col=0, before='x', after='y'), dict(row=0, col=0, before='x', after='z')])], {}, 'duplicate'),
            ([dict(path=['a'], before=None, after=dict(raw='eJwDAAAAAAE=', csv=[['forged']]))], {}, 'differs'),
            ([dict(path=['a'], before=None, after=node([['y']]), create_parents='yes')], {}, 'boolean'),
            ([], {}, 'without operations'),
            (['not-an-op'], {}, 'Expected an operation object'),
            ([dict(path='a', before=None, after=node([['y']]))], {}, 'Invalid claimed key path'),
            ([dict(path=['a', 1], before=None, after=node([['y']]))], {}, 'Invalid claimed key path'),
        ]
        for operations, extra, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                update.client_plan(self.root, self.payload(operations, **extra))
        with self.assertRaisesRegex(ValueError, 'native master table'):
            update.client_plan(self.root, self.payload([dict(path=['a'], before=None, after=node([['y']]))],
                                                       logical='battle/x.orderedmap'))
        with self.assertRaisesRegex(ValueError, 'client-2 payloads only'):
            update.client_census(self.root, dict(format='wf-scoped-update-client-1', target='x', tables={}))

    # ------------------------------------------------------------ builder helpers

    def test_native_diff_descends_and_skips_pseudo_changes(self):
        before = {'1': codec.pack({'99': codec.pack({'001': leaf([['a']]), '002': leaf([['b']])})}),
                  'same': leaf([['s']]), 'recompressed': zlib.compress(b'r,1\n', 1)}
        after = {'1': codec.pack({'99': codec.pack({'001': leaf([['a']]), '002': leaf([['B']]), '031': leaf([['n']])})}),
                 'same': leaf([['s']]), 'recompressed': zlib.compress(b'r,1\n', 9), 'new': leaf([['n']])}
        ops = update.native_diff(before, after)
        self.assertEqual([op['path'] for op in ops], [['1', '99', '002'], ['1', '99', '031'], ['new']])
        self.assertEqual(ops[1]['before'], None)
        self.assertTrue(all('children' not in (op['before'] or {}) for op in ops))
        with self.assertRaisesRegex(ValueError, 'Deletion'):
            update.native_diff({'gone': leaf([['x']])}, {})
        with self.assertRaisesRegex(ValueError, 'shape change'):
            update.native_diff({'k': leaf([['x']])}, {'k': codec.pack({'a': leaf([['x']])})})

    def test_cells_operation_conversion_round_trips_through_plan(self):
        before, after = node([['139990', 'a', '']]), node([['139990', 'a', 'tag']])
        op = update.cells_operation(dict(path=['139990'], before=before, after=after, line='paradox'))
        self.assertEqual(op, dict(path=['139990'], shape=[3], cells=[dict(row=0, col=2, before='', after='tag')], line='paradox'))
        self.assertIsNone(update.cells_operation(dict(path=['k'], before=node([['a']]), after=node([['a', 'b']]))))
        self.assertIsNone(update.cells_operation(dict(path=['k'], before=None, after=after)))
        path = self.write({'139990': leaf([['139990', 'gray', '']])})
        self.apply(self.payload([op]))
        self.assertEqual(codec.csv_read(self.rows_at(path, '139990')), [['139990', 'gray', 'tag']])

    # ------------------------------------------------------------ format 1 unchanged

    def test_format1_still_creates_missing_parents_implicitly(self):
        self.write({})
        payload = dict(format='wf-scoped-update-client-1', target='1.4.1056', tables={LOGICAL: dict(
            operations=[dict(path=['1', '99', '031'], before=None, after=node([['x']]))])})
        plans, report = update.client_plan(self.root, copy.deepcopy(payload))
        self.assertEqual(set(report), {'kind', 'baseline', 'files'})
        self.assertEqual(report['baseline'], '1.4.1056')
        self.assertEqual(len(plans), 1)


if __name__ == '__main__':
    unittest.main()
