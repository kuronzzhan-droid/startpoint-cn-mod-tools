"""wf-scoped-update-server-2: dual allowlist, list_add, created files, ensure, format round-trip."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_share_update_codec as codec
import wf_share_update_tables as update
from wf_share_update_io import apply_plans

INDENT2_LF = dict(indent=2, separators=[',', ': '], ensure_ascii=False, newline='\n', final_newline=True, bom=False)


class Server2Tests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.assets = self.root / 'assets'
        self.assets.mkdir()
        self.receipts = 0

    def put(self, relative, raw):
        path = self.assets / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        return path

    def payload(self, files, allowlist=None):
        return dict(format='wf-scoped-update-server-2', baseline='gray-inferred', target='1.4.9999',
                    allowlist=sorted(files) if allowlist is None else allowlist, files=files)

    def apply(self, payload, **kwargs):
        plans, report = update.server_plan(self.assets, payload, **kwargs)
        self.receipts += 1
        apply_plans(plans, self.root / ('receipt-%d' % self.receipts))
        return plans, report

    def snapshot(self):
        return {p.relative_to(self.assets).as_posix(): p.read_bytes() for p in self.assets.rglob('*') if p.is_file()}

    # ------------------------------------------------------------ allowlist

    def test_file_must_be_in_payload_and_package_allowlists(self):
        self.put('item_lookup.json', b'{}')
        op = dict(path=['1'], before_exists=False, before=None, after=1)
        files = {'item_lookup.json': dict(operations=[op])}
        with self.assertRaisesRegex(ValueError, 'not in the update allowlist'):
            update.server_plan(self.assets, self.payload(files, allowlist=['item_sale.json']))
        with self.assertRaisesRegex(ValueError, 'exceeds the package allowlist'):
            update.server_plan(self.assets, self.payload(files), allowlist=['item_sale.json'])
        with self.assertRaisesRegex(ValueError, 'exceeds the package allowlist: quest_entry_costs.json'):
            update.server_plan(self.assets, self.payload(files, allowlist=['item_lookup.json', 'quest_entry_costs.json']))
        self.assertEqual(len(update.server_plan(self.assets, self.payload(files))[0]), 1)
        self.assertEqual(len(update.server_plan(self.assets, self.payload(files), allowlist=['item_lookup.json'])[0]), 1)

    def test_unsafe_names_rejected(self):
        for name in ['../x.json', '.env.json', 'a/b/c.json', 'x.txt', '/abs.json', 'a\\b.json', 'c:x.json', 'cdndata/../x.json']:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'Unsafe|allowlist'):
                update.server_plan(self.assets, self.payload({name: dict(operations=[])}), allowlist=[name])

    def test_default_package_allowlist_covers_the_weapon_files(self):
        for name in ['item_ids.json', 'equipment_ids.json', 'equipment_lookup.json', 'equipment_element.json',
                     'equipment_max_level.json', 'equipment_enhancement_shop.json', 'equipment_awakening_material.json',
                     'boss_coin_shop.json', 'boss_coin_shop_item_category_map.json', 'gacha.json', 'item_sale.json']:
            self.assertIn(name, update.SERVER_FILES_2)
        self.assertTrue(update.SERVER_FILES <= update.SERVER_FILES_2)

    # ------------------------------------------------------------ list_add

    def test_list_add_appends_missing_ids_keeping_receiver_order_and_extras(self):
        path = self.put('item_ids.json', json.dumps([3, 1, 777001, 10000143]).encode())
        payload = self.payload({'item_ids.json': dict(
            ensure=[dict(op='list_add', path=[], items=[10000143, 10000146])],
            operations=[dict(op='list_add', path=[], items=[5910101, 999019, 1])])})
        plans, report = self.apply(payload)
        self.assertEqual(path.read_bytes(), b'[3, 1, 777001, 10000143, 10000146, 5910101, 999019]')
        self.assertEqual(report['files'][0]['format']['mode'], 'canonical')
        missing = [s['missing'] for s in report['operations']]
        self.assertEqual(missing, [[10000146], [5910101, 999019]])
        self.assertEqual(update.server_plan(self.assets, payload)[0], [])

    def test_list_add_indent0_file_keeps_its_format(self):
        path = self.put('equipment_ids.json', b'[\n100001,\n5900101\n]')
        self.apply(self.payload({'equipment_ids.json': dict(operations=[dict(op='list_add', path=[], items=[5910101, 5920001])])}))
        self.assertEqual(path.read_bytes(), b'[\n100001,\n5900101,\n5910101,\n5920001\n]')

    def test_list_add_items_overlap_and_type_rules(self):
        self.put('item_ids.json', b'[1]')
        bad = [dict(ensure=[dict(op='list_add', path=[], items=[5])], operations=[dict(op='list_add', path=[], items=[5, 6])]),
               dict(operations=[dict(op='list_add', path=[], items=[True])]),
               dict(operations=[dict(op='list_add', path=[], items=[1.5])]),
               dict(operations=[dict(op='list_add', path=[], items=[2, 2])])]
        for spec in bad:
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                update.server_plan(self.assets, self.payload({'item_ids.json': spec}))
        census = update.server_census(self.assets, self.payload({'item_ids.json': dict(
            operations=[dict(op='list_add', path=[], items=['1'])])}))
        self.assertEqual(census['operations'][0]['missing'], ['1'])

    def test_list_add_on_non_list_is_conflict(self):
        self.put('item_ids.json', b'{"1": 1}')
        with self.assertRaisesRegex(ValueError, 'not a list'):
            update.server_plan(self.assets, self.payload({'item_ids.json': dict(
                operations=[dict(op='list_add', path=[], items=[2])])}))

    # ------------------------------------------------------------ set / ensure / before_any

    def test_set_new_keys_preserve_receiver_fields_and_indent1_format(self):
        original = {'5900101': {'name': '死神', 'rarity': '5', 'receiver_only': 1}}
        path = self.put('equipment_lookup.json', json.dumps(original, ensure_ascii=False, indent=1).encode())
        new = {'name': '诅咒之剑', 'rarity': '5', 'category': '剑'}
        payload = self.payload({'equipment_lookup.json': dict(operations=[
            dict(path=['5910101'], before_exists=False, before=None, after=new)])})
        self.apply(payload)
        expected = dict(original, **{'5910101': new})
        self.assertEqual(path.read_bytes(), json.dumps(expected, ensure_ascii=False, indent=1).encode())
        self.assertEqual(update.server_plan(self.assets, payload)[0], [])

    def test_ensure_adds_missing_skips_equal_conflicts_on_difference(self):
        path = self.put('item_lookup.json', json.dumps({'10000143': {'name': 'ticket'}}).encode())
        ensure = [dict(path=['10000143'], value={'name': 'ticket'}), dict(path=['2370100'], value={'name': 'core'})]
        payload = self.payload({'item_lookup.json': dict(ensure=ensure, operations=[
            dict(path=['10000311'], before_exists=False, before=None, after={'name': 'star iron'})])})
        census = update.server_census(self.assets, payload)
        self.assertEqual(census['by_section']['ensure'], dict(apply=1, already=1, conflict=0))
        self.apply(payload)
        self.assertEqual(list(codec.json_loads(path.read_bytes())), ['10000143', '2370100', '10000311'])
        path.write_bytes(json.dumps({'10000143': {'name': 'gray renamed'}}).encode())
        census = update.server_census(self.assets, payload)
        self.assertEqual(census['operations'][0]['status'], 'conflict')
        with self.assertRaisesRegex(ValueError, 'Receiver JSON conflict'):
            update.server_plan(self.assets, payload)

    def test_before_any_accepts_listed_states_only(self):
        op = dict(path=['990099034'], before_any=[dict(exists=False), dict(exists=True, value={'stock': 9999})],
                  after={'stock': 60})
        for index, current in enumerate([None, {'stock': 9999}]):
            with self.subTest(index=index):
                self.put('boss_coin_shop.json', json.dumps({} if current is None else {'990099034': current}).encode())
                census = update.server_census(self.assets, self.payload({'boss_coin_shop.json': dict(operations=[op])}))
                self.assertEqual(census['operations'][0]['matched'], 'before_any[%d]' % index)
                self.apply(self.payload({'boss_coin_shop.json': dict(operations=[op])}))
        self.put('boss_coin_shop.json', json.dumps({'990099034': {'stock': 1}}).encode())
        with self.assertRaisesRegex(ValueError, 'differs from every accepted'):
            update.server_plan(self.assets, self.payload({'boss_coin_shop.json': dict(operations=[op])}))
        self.put('boss_coin_shop.json', json.dumps({'990099034': {'stock': 9999.0}}).encode())
        with self.assertRaisesRegex(ValueError, 'conflict'):
            update.server_plan(self.assets, self.payload({'boss_coin_shop.json': dict(operations=[op])}))

    def test_missing_parent_is_conflict_unless_create_parents(self):
        path = self.put('boss_coin_shop.json', b'{"1": {}}')
        op = dict(path=['99', '990099032'], before_exists=False, before=None, after={'stock': -1})
        with self.assertRaisesRegex(ValueError, 'parent missing: 99'):
            update.server_plan(self.assets, self.payload({'boss_coin_shop.json': dict(operations=[op])}))
        self.apply(self.payload({'boss_coin_shop.json': dict(operations=[dict(op, create_parents=True)])}))
        self.assertEqual(codec.json_loads(path.read_bytes()), {'1': {}, '99': {'990099032': {'stock': -1}}})
        self.put('boss_coin_shop.json', b'{"99": [1]}')
        with self.assertRaisesRegex(ValueError, 'parent is not an object'):
            update.server_plan(self.assets, self.payload({'boss_coin_shop.json': dict(operations=[dict(op, create_parents=True)])}))

    # ------------------------------------------------------------ created files

    def test_new_file_is_created_in_declared_style_and_replays(self):
        material = {'materialByEquipment': {'5910101': 10000311}, 'officialCrystals': [1, 2]}
        spec = dict(create=dict(init={}, style=INDENT2_LF), operations=[
            dict(path=[k], before_exists=False, before=None, after=v) for k, v in material.items()])
        payload = self.payload({'equipment_awakening_material.json': spec})
        plans, report = self.apply(payload)
        path = self.assets / 'equipment_awakening_material.json'
        self.assertEqual(path.read_bytes(), (json.dumps(material, indent=2) + '\n').encode())
        self.assertTrue(report['files'][0]['created'])
        self.assertEqual(report['files'][0]['format']['mode'], 'created')
        self.assertEqual(update.server_plan(self.assets, payload)[0], [])
        path.write_bytes(json.dumps({'materialByEquipment': {'5910101': 1}}).encode())
        census = update.server_census(self.assets, payload)
        self.assertEqual([s['status'] for s in census['operations']], ['conflict', 'apply'])

    def test_missing_file_without_create_is_conflict(self):
        with self.assertRaisesRegex(ValueError, 'receiver file is missing'):
            update.server_plan(self.assets, self.payload({'item_sale.json': dict(operations=[
                dict(path=['1'], before_exists=False, before=None, after=1)])}))

    # ------------------------------------------------------------ format round-trip

    def test_crlf_indent2_file_keeps_crlf_and_untouched_bytes(self):
        shop = {'1': {'200101': {'costs': [{'id': 40000, 'amount': 10}], 'stock': 5}},
                '99': {'990099001': {'costs': [], 'stock': 1}}}
        raw = (json.dumps(shop, indent=2) + '\n').replace('\n', '\r\n').encode()
        path = self.put('boss_coin_shop.json', raw)
        new = {'costs': [{'id': 590010000, 'amount': 500}], 'stock': 60}
        self.apply(self.payload({'boss_coin_shop.json': dict(operations=[
            dict(path=['99', '990099034'], before_exists=False, before=None, after=new)])}))
        out = path.read_bytes()
        self.assertEqual(out.count(b'\n'), out.count(b'\r\n'))
        head = raw[:raw.index(b'"990099001"')]
        self.assertTrue(out.startswith(head))
        shop['99']['990099034'] = new
        self.assertEqual(out, (json.dumps(shop, indent=2) + '\n').replace('\n', '\r\n').encode())

    def test_mixed_gacha_file_is_spliced_without_ballooning(self):
        pools = '{"1": {"type": 0, "pool": [{"id": 1, "odds": 5}]}, "990002": {"type":0,"pool":[{"id":2,"odds":7,"rarity":8.086253}]}}'
        raw = pools.encode()
        path = self.put('gacha.json', raw)
        pool = {'type': 1, 'pool': [{'id': 5910101, 'odds': 456, 'rarity': 8.086253}]}
        payload = self.payload({'gacha.json': dict(operations=[
            dict(path=['990003'], before_exists=False, before=None, after=pool)])})
        plans, report = self.apply(payload)
        self.assertEqual(report['files'][0]['format']['mode'], 'splice')
        fragment = ', "990003": ' + json.dumps(pool, separators=(',', ':'))
        self.assertEqual(path.read_bytes(), raw[:-1] + fragment.encode() + b'}')
        self.assertEqual(update.server_plan(self.assets, payload)[0], [])

    def test_unpreservable_format_refused_unless_fallback(self):
        raw = b'{"odd": 1.0E5, "e": {}}'
        path = self.put('item_sale.json', raw)
        payload = self.payload({'item_sale.json': dict(operations=[
            dict(path=['10000311'], before_exists=False, before=None, after={'category': 2, 'sellable': False})])})
        with self.assertRaisesRegex(ValueError, 'cannot be preserved'):
            update.server_plan(self.assets, payload)
        census = update.server_census(self.assets, payload)
        self.assertFalse(census['ready'])
        self.assertEqual(census['format_errors'], ['item_sale.json'])
        self.assertEqual(path.read_bytes(), raw)
        plans, report = self.apply(payload, format_fallback='indent2')
        self.assertEqual(report['files'][0]['format']['mode'], 'fallback-indent2')

    # ------------------------------------------------------------ conflicts are read-only, all listed

    def test_conflicts_write_nothing_and_census_lists_all(self):
        self.put('item_lookup.json', json.dumps({'999019': {'name': 'gray'}, '999020': {'name': 'gray'}}).encode())
        self.put('item_ids.json', b'{"not": "a list"}')
        before = self.snapshot()
        payload = self.payload({
            'item_lookup.json': dict(operations=[
                dict(path=['999019'], before_exists=False, before=None, after={'name': 'ticket'}),
                dict(path=['999020'], before_exists=False, before=None, after={'name': 'ten'}),
                dict(path=['10000301'], before_exists=False, before=None, after={'name': 'paradox'})]),
            'item_ids.json': dict(operations=[dict(op='list_add', path=[], items=[999019])])})
        with self.assertRaisesRegex(ValueError, r'\(\+2 more conflicts\)'):
            update.server_plan(self.assets, payload)
        census = update.server_census(self.assets, payload)
        self.assertEqual(census['counts'], dict(apply=1, already=0, conflict=3))
        self.assertEqual(self.snapshot(), before)

    def test_invalid_server_payloads(self):
        self.put('item_sale.json', b'{}')
        base = dict(path=['1'], before_exists=False, before=None, after=1)
        cases = [(dict(base, op='delete'), 'Unknown server op'),
                 (dict(base, before_any=[dict(exists=False)]), 'not both'),
                 (dict(path=['1'], before_any=[dict(exists=True)], after=1), 'exactly when exists'),
                 (dict(path=[], before_exists=False, before=None, after=1), 'Invalid claimed key path'),
                 (dict(base, extra=1), 'unknown'),
                 (dict(path=['1'], after=1), 'missing'),
                 (dict(path='1', before_exists=False, before=None, after=1), 'Invalid claimed key path'),
                 (['1'], 'Expected an operation object')]
        for op, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                update.server_plan(self.assets, self.payload({'item_sale.json': dict(operations=[op])}))
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            update.server_plan(self.assets, self.payload({'item_sale.json': dict(operations=[
                base, dict(base, path=['1', 'x'])])}))
        with self.assertRaisesRegex(ValueError, 'create.init'):
            update.server_plan(self.assets, self.payload({'item_sale.json': dict(
                create=dict(init={'x': 1}, style=INDENT2_LF), operations=[base])}))
        with self.assertRaisesRegex(ValueError, 'unique names'):
            update.server_plan(self.assets, self.payload({'item_sale.json': dict(operations=[base])},
                                                         allowlist=['item_sale.json', ['x']]))
        with self.assertRaisesRegex(ValueError, 'Package allowlist'):
            update.server_plan(self.assets, self.payload({'item_sale.json': dict(operations=[base])}),
                               allowlist=['item_sale.json', 3])
        with self.assertRaisesRegex(ValueError, 'server-2 payloads only'):
            update.server_census(self.assets, dict(format='wf-scoped-update-server-1', target='x', files={}))

    # ------------------------------------------------------------ format 1 unchanged

    def test_format1_keeps_indent2_rewrite_and_old_allowlist(self):
        path = self.put('item_sale.json', b'{"1": {"category": 2}}')
        payload = dict(format='wf-scoped-update-server-1', target='1.4.1056', files={'item_sale.json': dict(
            operations=[dict(path=['2'], before_exists=False, before=None, after={'category': 3})])})
        plans, report = self.apply(payload)
        self.assertEqual(path.read_bytes(), (json.dumps({'1': {'category': 2}, '2': {'category': 3}},
                                                        ensure_ascii=False, indent=2) + '\n').encode())
        self.assertEqual(set(report), {'kind', 'baseline', 'files'})
        with self.assertRaisesRegex(ValueError, 'allowlist'):
            update.server_plan(self.assets, dict(payload, files={'item_ids.json': dict(operations=[])}))


if __name__ == '__main__':
    unittest.main()
