"""已审阅旧候选漂移不得变成全包豁免或自动封口。"""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import json
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wf_character_revision as revision


class ReviewedDriftTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        root = self.repo / 'work/character_packs/sample'
        self.ws = SimpleNamespace(root=root, package_dir=root / 'package',
                                  evidence_dir=root / 'evidence',
                                  character_id=149999, code_name='white_wolf_gerald')
        self.key = ('common', 'battle/test.action.dsl.amf3.deflate')
        self.asset = self.ws.package_dir / 'roots' / self.key[0] / self.key[1]
        self.asset.parent.mkdir(parents=True)
        self.asset.write_bytes(b'existing user WIP')
        self.ws.evidence_dir.mkdir()
        manifest = {'roots': {'common': [{'logical_path': self.key[1],
                     'sha256': revision.digest(b'old'), 'size': 3}]},
                    'tables': [], 'snapshot': {}, 'qa': {}}
        (self.ws.package_dir / 'manifest.json').write_text(json.dumps(manifest))
        (self.repo / 'mod-tools').mkdir()
        (self.repo / 'mod-tools/profiles.json').write_text(
            json.dumps({'profiles': {'cn': {'store': 'store'}}}))
        self.loader = patch.object(revision.workspace, 'load_workspace', return_value=self.ws)
        self.loader.start()
        self.addCleanup(self.loader.stop)

    def candidate(self, reviewed=None):
        return revision.RevisionCandidate(
            self.repo, self.ws.root, character_id='149999', code_name='white_wolf_gerald',
            package_version='test', snapshot_key='test', baseline_factory=lambda *a, **k: None,
            reviewed_input_drift=reviewed)

    def test_default_and_wrong_hash_still_reject(self):
        for reviewed in (None, {self.key: revision.digest(b'wrong')}):
            with self.assertRaisesRegex(ValueError, 'candidate drift'):
                self.candidate(reviewed)

    def test_exact_review_preserves_untouched_manifest_and_bytes(self):
        raw = self.asset.read_bytes()
        candidate = self.candidate({self.key: revision.digest(raw)})
        old_entry = dict(candidate.index[self.key])
        evidence = candidate.finish({'scoped': True}, apply=True)
        actual = json.loads((self.ws.package_dir / 'manifest.json').read_bytes())
        self.assertEqual(actual['roots']['common'][0], old_entry)
        self.assertEqual(self.asset.read_bytes(), raw)
        self.assertEqual(len(evidence['reviewed_input_drift']), 1)
        self.assertFalse(actual['qa']['release_ready'])

    def test_unrelated_or_stale_review_is_rejected(self):
        reviewed = {self.key: revision.digest(self.asset.read_bytes())}
        with self.assertRaisesRegex(ValueError, 'unrelated'):
            self.candidate({**reviewed, ('common', 'other'): 'bad'})
        manifest_path = self.ws.package_dir / 'manifest.json'
        manifest = json.loads(manifest_path.read_bytes())
        manifest['roots']['common'][0].update(
            sha256=reviewed[self.key], size=len(self.asset.read_bytes()))
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError, 'drift changed'):
            self.candidate(reviewed)

    def test_review_does_not_disable_concurrent_write_guard(self):
        candidate = self.candidate({self.key: revision.digest(self.asset.read_bytes())})
        candidate.emit(*self.key, b'authorized replacement')
        self.asset.write_bytes(b'concurrent edit')
        with self.assertRaisesRegex(ValueError, 'changed after plan'):
            candidate.finish({}, apply=True)
        self.assertEqual(self.asset.read_bytes(), b'concurrent edit')


if __name__ == '__main__':
    unittest.main()
