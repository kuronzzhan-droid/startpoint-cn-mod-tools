"""Regression coverage for Studio/native integration boundaries."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from wf_studio_bridge import native_timeline, selected_portraits


class SelectedPortraitTests(unittest.TestCase):
    def test_no_selection_keeps_uploaded_project_default(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(selected_portraits(folder))

    def test_pinned_pair_is_read_and_hash_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            entries = []
            for level in range(2):
                raw = f'original-{level}'.encode()
                name = f'{level}.png'
                (root/name).write_bytes(raw)
                entries.append(dict(file=name, sha256=hashlib.sha256(raw).hexdigest(),
                                    landmarks={'face': [level, 1]}))
            selection = root/'portrait-selection.json'
            selection.write_text(json.dumps({'states': entries}))
            self.assertEqual(selected_portraits(root)[1], (b'original-1', {'face': [1, 1]}))
            (root/'0.png').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'hash changed'):
                selected_portraits(root)
            entries[0]['file'] = '../outside.png'
            selection.write_text(json.dumps({'states': entries}))
            with self.assertRaisesRegex(ValueError, 'inside candidate'):
                selected_portraits(root)


class TimelineTests(unittest.TestCase):
    def test_battle_anchors_have_native_names_timing_and_inactive_slots(self):
        names = ['neutral', 'walk_front', 'walk_back', 'skill_ready', 'kachidoki',
                 'into_coffin', 'ghost_raise', 'ghost_neutral', 'revive']
        source = {'sequences': [dict(name=n, begin=i*20+1, end=i*20+20, kind='loop')
                                for i, n in enumerate(names)]}
        before = copy.deepcopy(source)
        result = native_timeline(source, special=False)
        self.assertEqual(source, before)
        self.assertEqual(result['sequences'], source['sequences'])
        self.assertEqual(result['points'][0]['path'], 'hp_gauge')
        frames = result['circles'][0]['frames']
        self.assertEqual([x['begin'] for x in frames], [i*20+2 for i in range(9)])
        self.assertTrue(all(x['data'] for x in frames[:3]))
        self.assertTrue(all(not x['data'] for x in frames[3:]))

    def test_special_requires_both_native_ui_sequences(self):
        with self.assertRaisesRegex(ValueError, 'special_pose'):
            native_timeline({'sequences': [dict(name='special_land')]}, special=True)
        source = {'sequences': [dict(name='special_land'), dict(name='special_pose')]}
        result = native_timeline(source, special=True)
        self.assertEqual(result['circles'], [])
        self.assertEqual(result['points'], [])


if __name__ == '__main__':
    unittest.main()
