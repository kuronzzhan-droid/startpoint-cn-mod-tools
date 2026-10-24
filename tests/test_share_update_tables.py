import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_share_update_codec as codec
import wf_share_update_tables as update
from wf_share_asset_index import relative_path
from wf_share_update_io import apply_plans


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def leaf(self, value):
        return codec.node(codec.csv_write(value))

    def fixture(self):
        logical = 'master/ability/ability.orderedmap'
        before = self.leaf([['old', '10'], ['removed-effect', '99']])
        after = self.leaf([['new', '20']])
        path = self.root / relative_path(logical)
        path.parent.mkdir(parents=True)
        path.write_bytes(codec.pack({'owner': update.encode(before), 'foreign': codec.csv_write([['keep']])}))
        payload = dict(format='wf-scoped-update-client-1', target='1.4.926', tables={logical: dict(
            operations=[dict(path=['owner'], before=before, after=after)])})
        return path, payload

    def test_scoped_replace_preserves_foreign_bytes_and_drops_removed_effect(self):
        path, payload = self.fixture()
        foreign = codec.unpack(path.read_bytes())['foreign']
        plans, _ = update.client_plan(self.root, payload)
        apply_plans(plans, self.root/'receipt')
        rows = codec.unpack(path.read_bytes())
        self.assertEqual(rows['foreign'], foreign)
        self.assertEqual(codec.csv_read(rows['owner']), [['new', '20']])
        self.assertEqual(update.client_plan(self.root, payload)[0], [])

    def test_receiver_drift_is_read_only_conflict(self):
        path, payload = self.fixture()
        raw = codec.pack({'owner': codec.csv_write([['recipient-custom']])})
        path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'conflict'):
            update.client_plan(self.root, payload)
        self.assertEqual(path.read_bytes(), raw)

    def test_nested_siblings_survive(self):
        rows = {'outer': codec.pack({'own': codec.csv_write([['old']]), 'other': b'unchanged'})}
        update.patch_native(rows, ['outer', 'own'], self.leaf([['old']]), self.leaf([['new']]), 'test')
        self.assertEqual(codec.unpack(rows['outer'])['other'], b'unchanged')

    def test_new_identity_does_not_replace_existing(self):
        rows = {'cid': codec.csv_write([['foreign-character']])}
        with self.assertRaisesRegex(ValueError, 'conflict'):
            update.patch_native(rows, ['cid'], None, self.leaf([['ours']]), 'cid')

    def test_missing_nested_path_can_be_created(self):
        rows = {}
        update.patch_native(rows, ['new', '0'], None, self.leaf([['hello']]), 'test')
        self.assertEqual(codec.csv_read(codec.unpack(rows['new'])['0']), [['hello']])

    def test_overlap_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            update.operations_checked([dict(path=['a']), dict(path=['a', 'b'])])

    def test_json_preserves_unclaimed_fields(self):
        value = {'cid': {'attack': 10, 'receiver_only': 3}, 'other': 4}
        op = dict(path=['cid', 'attack'], before_exists=True, before=10, after=20)
        update.patch_json(value, op, 'test')
        self.assertEqual(value, {'cid': {'attack': 20, 'receiver_only': 3}, 'other': 4})
        update.patch_json(value, op, 'test')

    def test_json_null_is_not_missing(self):
        op = dict(path=['a'], before_exists=False, before=None, after=5)
        with self.assertRaisesRegex(ValueError, 'conflict'):
            update.patch_json({'a': None}, op, 'test')

    def test_server_file_escape_rejected(self):
        payload = dict(format='wf-scoped-update-server-1', target='x', files={'../.env': {'operations': []}})
        with self.assertRaisesRegex(ValueError, 'allowlist'):
            update.server_plan(self.root, payload)

    def test_spheal_reward_config_preserves_receiver_fields_and_rejects_drift(self):
        path = self.root/'abyss_spheal_degree_reward.json'
        path.write_text(json.dumps({'receiver_only': 'keep'}), encoding='utf-8')
        payload = dict(format='wf-scoped-update-server-1', target='1.4.1010', files={path.name: dict(
            operations=[dict(path=['character_id'], before_exists=False, before=None, after=129990),
                        dict(path=['degree_id'], before_exists=False, before=None, after=9911301)])})
        plans, _ = update.server_plan(self.root, payload)
        apply_plans(plans, self.root/'receipt')
        self.assertEqual(json.loads(path.read_bytes()), {
            'receiver_only': 'keep', 'character_id': 129990, 'degree_id': 9911301})
        self.assertEqual(update.server_plan(self.root, payload)[0], [])
        raw = json.dumps({'character_id': 123, 'receiver_only': 'keep'}).encode()
        path.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, 'conflict'):
            update.server_plan(self.root, payload)
        self.assertEqual(path.read_bytes(), raw)

    def test_gacha_list_replaces_only_when_baseline_matches(self):
        old = [{'id': 1, 'odds': 100}, {'id': 2, 'odds': 200}]
        new = [{'id': 2, 'odds': 150}, {'id': 1, 'odds': 150}]
        value = {'990001': {'pool': {'1': copy.deepcopy(old)}, 'extra': 5}}
        op = dict(path=['990001', 'pool', '1'], before_exists=True, before=old, after=new)
        update.patch_json(value, op, 'gacha')
        self.assertEqual(value['990001']['pool']['1'], new)
        self.assertEqual(value['990001']['extra'], 5)
        with self.assertRaisesRegex(ValueError, 'conflict'):
            update.patch_json({'990001': {'pool': {'1': old+[{'id': 3}]}}}, op, 'gacha')

    def test_cas_rejects_edit_after_planning(self):
        path, payload = self.fixture()
        plans, _ = update.client_plan(self.root, payload)
        path.write_bytes(b'recipient-edited-after-plan')
        with self.assertRaisesRegex(ValueError, 'drift'):
            apply_plans(plans, self.root/'receipt')
        self.assertFalse((self.root/'receipt').exists())


if __name__ == '__main__':
    unittest.main()
