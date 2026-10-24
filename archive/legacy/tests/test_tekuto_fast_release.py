import unittest

import wf_tekuto_fast_release as fast
import wf_tekuto_no_endlag_revision as revision
from tests.test_tekuto_no_endlag_revision import _current, LOGICALS


class FastReleaseTests(unittest.TestCase):
    def test_both_levels_keep_damage_commands_and_have_no_extra_hold(self):
        for logical in LOGICALS:
            before = _current(logical)
            self.assertIsNotNone(before)
            after = fast.final_tree(before)
            self.assertEqual(revision.hold_frames(after), 0)
            self.assertEqual(revision.commands(after, 'CreateNormalAttack'),
                             revision.commands(before, 'CreateNormalAttack'))
            self.assertEqual(after, fast.final_tree(after))
            beams = [x['frame'] for x in revision.timeline(after)
                     if x.get('name') == 'CreateHitArea' and x.get('shape') == 'Rectangle']
            self.assertEqual(min(beams), 36)


if __name__ == '__main__':
    unittest.main()
