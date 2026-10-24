"""校园奈芙候选的真实资源检查；没有本地资源时跳过集成用例。"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_campus_nephtim_common as C
import wf_campus_nephtim_kit as kit
import wf_campus_nephtim_manifest as manifest_builder
import wf_character_flow as flow
import wf_character_pack as pack
import wf_character_workspace as workspace
import wf_dsl


class CampusNephtimTransforms(unittest.TestCase):
    def test_bootstrap_refuses_completed_art_before_scanning_or_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp)
            target = package / 'manifest.json'
            original = json.dumps({
                'snapshot': {'campus_art': {'sources': ['portrait-0.png', 'portrait-1.png']}},
                'skills': {'programs': ['campus.action.dsl.amf3.deflate']},
                'unique_condition': {'existing': True},
                'tables': [{'root': 'common', 'logical_path': 'master/art.orderedmap'}],
            }, indent=2).encode('utf-8')
            target.write_bytes(original)
            with patch.object(C, 'PKG', package), patch.object(manifest_builder, 'scan_roots') as scan:
                with self.assertRaisesRegex(ValueError, 'bootstrap-only.*snapshot'):
                    manifest_builder.build()
                scan.assert_not_called()
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(list(package.iterdir()), [target])

    def test_recursive_path_replacement_preserves_numbers_and_input(self):
        tree = ['ShowEffect', {'path': 'battle/old/picture', 'scale': 1.0}, 60, True]
        before = copy.deepcopy(tree)
        changed = kit.replace_strings(tree, {'battle/old/': 'battle/new/'})
        self.assertEqual(tree, before)
        self.assertEqual(changed[1]['path'], 'battle/new/picture')
        self.assertIs(type(changed[1]['scale']), float)
        self.assertEqual(changed[2:], [60, True])


@unittest.skipUnless(C.PKG.is_dir() and C.STORE.is_dir(), 'requires local candidate and native source store')
class CampusNephtimCandidate(unittest.TestCase):
    def test_both_real_skills_resolve_dark_party_without_stale_switch_or_freeze(self):
        for level in ['1', '2']:
            tree = kit.make_skill(level)
            commands = [x for x in kit.walk(tree) if x and isinstance(x[0], str)]
            self.assertEqual(wf_dsl.player_side_dsl_problems(tree), [])
            self.assertFalse(any(x[0] in ['ConditionalsChangeSkillFlag', 'ACFrozen'] for x in commands))
            own_targets = [x for x in commands if x[0] == 'FindAllSubjects' and x[1] == 70]
            self.assertEqual(len(own_targets), 1)
            self.assertEqual(own_targets[0][3], [6])
            self.assertTrue(any(x[0] == 'ACAdditionalDirectAttack' for x in commands))
            self.assertTrue(any(x[0] == 'ACPiercing' for x in commands))

    def test_every_skill_effect_texture_resolves(self):
        report = flow.master_reference_report(C.PKG, tuple(C.STORES.values()))
        self.assertTrue(report['release_ready'], report)
        self.assertEqual(len(report['runtime_texture_checks']), 3)
        self.assertGreater(sum(x['texture_reference_count'] for x in report['runtime_texture_checks']), 50)

    def test_complete_assets_and_three_layer_identity(self):
        state = workspace.workspace_status(workspace.load_workspace(C.WS))
        self.assertEqual(state.requirement_report['required_present'], 37)
        self.assertTrue(state.three_layer_claim_status['consistent'])
        manifest = json.loads((C.PKG / 'manifest.json').read_text('utf-8'))
        self.assertEqual(pack.validate_manifest(manifest, C.PKG, require_referenced_assets=True), [])
        owned = {(x['root'], x['logical_path']) for x in manifest['tables']}
        for name, entries in manifest['roots'].items():
            for entry in entries:
                path = entry['logical_path']
                if path.endswith('.orderedmap') or name == 'server':
                    self.assertIn((name, path), owned)


if __name__ == '__main__':
    unittest.main()
