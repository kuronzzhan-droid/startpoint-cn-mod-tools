"""Receiver guarantees that matter across unknown installation baselines."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf_share_asset_index import digest_file, inspect, relative_path
from wf_share_assets_receive import apply_plan
import wf_share_assets_receive as receiver


class ReceiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.package = self.root / 'package'
        self.store = self.root / 'production' / 'upload'
        self.package.mkdir()
        (self.package / 'assets').mkdir()

    def fixture(self, classes=('owned', 'dependency')):
        rows, parts = [], []
        for number, classification in enumerate(classes):
            logical = f'character/example/voice/{number}.mp3'
            relative = relative_path(logical)
            member = 'production/upload/' + relative
            payload = f'audio-{number}'.encode()
            rows.append(dict(root='common', logical=logical, relative=relative,
                             member=member, classification=classification, size=len(payload),
                             sha256=hashlib.sha256(payload).hexdigest()))
            path = self.package / 'assets' / f'{number}.zip'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr(member, payload)
            parts.append(dict(path=f'assets/{number}.zip', sha256=digest_file(path)))
        self.manifest = dict(schema_version=2, assets=rows, archives=parts)
        self.save_manifest()
        return rows

    def save_manifest(self):
        (self.package / 'asset-manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def install(self, row, data):
        path = self.store / row['relative']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_owned_updates_backed_up_and_unrelated_files_preserved(self):
        rows = self.fixture()
        target = self.install(rows[0], b'prior-owned-version')
        extra = self.store / 'unrelated'
        extra.write_bytes(b'receiver-only')
        output = self.root / 'receipt'
        receipt = apply_plan(inspect(self.package, self.store), output)
        self.assertTrue(receipt['complete'])
        self.assertFalse(receipt['published'])
        self.assertEqual(target.read_bytes(), b'audio-0')
        self.assertEqual((output / 'before/common' / rows[0]['relative']).read_bytes(), b'prior-owned-version')
        self.assertEqual(extra.read_bytes(), b'receiver-only')
        again = apply_plan(inspect(self.package, self.store), self.root / 'again')
        self.assertEqual(again['applied'], [])

    def test_later_dependency_conflict_prevents_all_target_writes(self):
        rows = self.fixture()
        old = self.install(rows[0], b'old-owned')
        self.install(rows[1], b'other-official-version')
        plan = inspect(self.package, self.store)
        self.assertEqual(len(plan['conflicts']), 1)
        with self.assertRaisesRegex(ValueError, 'dependency conflicts'):
            apply_plan(plan, self.root / 'receipt')
        self.assertEqual(old.read_bytes(), b'old-owned')
        self.assertFalse((self.root / 'receipt').exists())

    def test_later_corrupt_zip_is_rejected_without_writes(self):
        self.fixture()
        path = self.package / self.manifest['archives'][1]['path']
        path.write_bytes(b'corrupt')
        with self.assertRaisesRegex(ValueError, 'Archive hash'):
            inspect(self.package, self.store)
        self.assertFalse(self.store.exists())

    def test_approved_dependency_preimage_updates_with_backup_and_keeps_ownership(self):
        row, = self.fixture(('dependency',))
        old = b'reviewed-complete-atlas'
        row['approved_before_sha256'] = hashlib.sha256(old).hexdigest()
        self.save_manifest()
        target = self.install(row, old)
        plan = inspect(self.package, self.store)
        self.assertEqual(plan['conflicts'], [])
        self.assertEqual(plan['entries'][0]['classification'], 'dependency')
        self.assertEqual(plan['entries'][0]['before_sha256'], row['approved_before_sha256'])
        output = self.root / 'receipt'
        receipt = apply_plan(plan, output)
        self.assertTrue(receipt['complete'])
        self.assertEqual(target.read_bytes(), b'audio-0')
        self.assertEqual((output/'before/common'/row['relative']).read_bytes(), old)
        again = apply_plan(inspect(self.package, self.store), self.root/'again')
        self.assertEqual(again['applied'], [])

    def test_unrecognized_dependency_preimage_still_conflicts_before_any_write(self):
        rows = self.fixture()
        rows[1]['approved_before_sha256'] = hashlib.sha256(b'reviewed-atlas').hexdigest()
        self.save_manifest()
        first = self.install(rows[0], b'old-first')
        other = self.install(rows[1], b'unknown-atlas')
        plan = inspect(self.package, self.store)
        self.assertEqual(len(plan['conflicts']), 1)
        with self.assertRaisesRegex(ValueError, 'dependency conflicts'):
            apply_plan(plan, self.root/'receipt')
        self.assertEqual(first.read_bytes(), b'old-first')
        self.assertEqual(other.read_bytes(), b'unknown-atlas')
        self.assertFalse((self.root/'receipt').exists())

    def test_approved_dependency_preimage_drift_still_blocks_all_writes(self):
        rows = self.fixture()
        old = b'reviewed-atlas'
        rows[1]['approved_before_sha256'] = hashlib.sha256(old).hexdigest()
        self.save_manifest()
        first = self.install(rows[0], b'old-first')
        target = self.install(rows[1], old)
        plan = inspect(self.package, self.store)
        self.assertEqual(plan['conflicts'], [])
        target.write_bytes(b'concurrent-edit')
        with self.assertRaisesRegex(ValueError, 'Receiver changed'):
            apply_plan(plan, self.root/'receipt')
        self.assertEqual(first.read_bytes(), b'old-first')
        self.assertEqual(target.read_bytes(), b'concurrent-edit')
        self.assertFalse((self.root/'receipt').exists())

    def test_malformed_approved_preimage_is_rejected_without_receiver_writes(self):
        row, = self.fixture(('dependency',))
        valid = hashlib.sha256(b'reviewed-atlas').hexdigest()
        for value in (None, '', 'a'*63, 'a'*65, 'g'*64, valid.upper(), valid+'\n',
                      123, [valid], {'sha256': valid}):
            with self.subTest(value=value):
                row['approved_before_sha256'] = value
                self.save_manifest()
                with self.assertRaisesRegex(ValueError, 'approved dependency preimage'):
                    inspect(self.package, self.store)
                self.assertFalse(self.store.exists())
        row['approved_before_sha256'] = valid
        row['classification'] = 'owned'
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'approved dependency preimage'):
            inspect(self.package, self.store)

    def test_preimage_drift_prevents_earlier_asset_write(self):
        rows = self.fixture(('owned', 'owned'))
        first = self.install(rows[0], b'old-first')
        last = self.install(rows[1], b'old-last')
        plan = inspect(self.package, self.store)
        last.write_bytes(b'concurrent-edit')
        with self.assertRaisesRegex(ValueError, 'Receiver changed'):
            apply_plan(plan, self.root / 'receipt')
        self.assertEqual(first.read_bytes(), b'old-first')
        self.assertEqual(last.read_bytes(), b'concurrent-edit')

    def test_cumulative_update_accepts_only_enumerated_prior_media(self):
        row, = self.fixture(('dependency',))
        versions = (b'1045', b'1046')
        row['approved_before_sha256s'] = [hashlib.sha256(v).hexdigest() for v in versions]
        self.save_manifest()
        for number, raw in enumerate(versions):
            target = self.install(row, raw)
            plan = inspect(self.package, self.store)
            self.assertEqual([], plan['conflicts'])
            receipt = apply_plan(plan, self.root / str(number))
            self.assertTrue(receipt['complete'])
            self.assertEqual(b'audio-0', target.read_bytes())
        self.assertEqual([], inspect(self.package, self.store)['conflicts'])
        self.install(row, b'receiver edit')
        self.assertEqual(1, len(inspect(self.package, self.store)['conflicts']))

    def test_malformed_preimage_list_is_rejected(self):
        row, = self.fixture(('dependency',))
        valid = hashlib.sha256(b'old').hexdigest()
        for value in (None, '', valid, [], [None], [valid, valid], ['g'*64], [valid+'\n']):
            with self.subTest(value=value):
                row['approved_before_sha256s'] = value
                self.save_manifest()
                with self.assertRaisesRegex(ValueError, 'approved dependency preimage'):
                    inspect(self.package, self.store)
        row.update(classification='owned', approved_before_sha256s=[valid])
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'approved dependency preimage'):
            inspect(self.package, self.store)

    def test_archive_drift_after_plan_prevents_any_write(self):
        self.fixture()
        plan = inspect(self.package, self.store)
        (self.package / 'assets/1.zip').write_bytes(b'drift')
        with self.assertRaisesRegex(ValueError, 'Archive drift'):
            apply_plan(plan, self.root / 'receipt')
        self.assertFalse(self.store.exists())

    def test_extra_zip_member_is_rejected_even_with_updated_archive_hash(self):
        self.fixture()
        path = self.package / 'assets/0.zip'
        with zipfile.ZipFile(path, 'a') as archive:
            archive.writestr('../escape', b'not-listed')
        self.manifest['archives'][0]['sha256'] = digest_file(path)
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'Unexpected'):
            inspect(self.package, self.store)

    def test_partial_io_failure_retains_exact_preimages_and_durable_journal(self):
        rows = self.fixture(('owned', 'owned'))
        first = self.install(rows[0], b'old-first')
        last = self.install(rows[1], b'old-last')
        plan = inspect(self.package, self.store)
        original = receiver.replace
        def fail_second(source, destination):
            if destination == last:
                raise OSError('injected storage failure')
            return original(source, destination)
        output = self.root / 'receipt'
        with patch.object(receiver, 'replace', side_effect=fail_second):
            with self.assertRaisesRegex(OSError, 'injected storage'):
                apply_plan(plan, output)
        self.assertEqual(first.read_bytes(), b'audio-0')
        self.assertEqual(last.read_bytes(), b'old-last')
        receipt = json.loads((output / 'transaction.json').read_bytes())
        self.assertFalse(receipt['complete'])
        self.assertEqual(receipt['applied'], [rows[0]['member']])
        self.assertEqual(receipt['attempted'], rows[1]['member'])
        journal = [json.loads(line) for line in (output / 'journal.jsonl').read_text().splitlines()]
        self.assertEqual([row['phase'] for row in journal], ['attempted', 'applied', 'attempted'])
        self.assertEqual((output / 'before/common' / rows[0]['relative']).read_bytes(), b'old-first')
        self.assertEqual((output / 'before/common' / rows[1]['relative']).read_bytes(), b'old-last')

    def test_duplicate_mapping_and_unsafe_logical_rejected(self):
        self.fixture()
        self.manifest['assets'].append(dict(self.manifest['assets'][0]))
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'duplicate resource'):
            inspect(self.package, self.store)
        for logical in ('/foo', '../foo', 'a/../b', 'a\\b', 'C:/foo', 'a//b'):
            with self.subTest(logical=logical), self.assertRaises(ValueError):
                relative_path(logical)

    def test_asset_under_symlink_rejected(self):
        rows = self.fixture()
        outside = self.root / 'outside'
        outside.mkdir()
        self.store.mkdir(parents=True)
        try:
            (self.store / rows[0]['relative'].split('/')[0]).symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest(str(exc))
        with self.assertRaisesRegex(ValueError, 'alias or escape'):
            inspect(self.package, self.store)


if __name__ == '__main__':
    unittest.main()
