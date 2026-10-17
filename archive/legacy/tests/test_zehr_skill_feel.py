"""短停球不得更改伤害、事件或后续动画。"""
from copy import deepcopy
from pathlib import Path
import unittest
import zlib

import wf_dsl
from wf_seasonal7_kit_philia import cmds, dsl_gates, dsl_gate_failures
from wf_character_revision import encode_tree
from wf_zehr_skill_feel import revise_skill

ROOT = Path(__file__).resolve().parents[2]
CODE = 'guildknight_leader_tavern'


class ZehrSkillFeelTest(unittest.TestCase):
    def test_both_levels_only_change_stop_duration(self):
        for level in (1, 2):
            path = ROOT/f'work/character_packs/s7-zehr/package/roots/common/battle/action/skill/action/rare5/{CODE}${CODE}_{level}.action.dsl.amf3.deflate'
            old = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))['tree']
            # Keep the regression effective after the candidate has been upgraded.
            cmds(old, 'StopBall')[0][2] = 60
            fixed = revise_skill(old)
            self.assertEqual(cmds(fixed, 'StopBall')[0][2], 15)
            restored = deepcopy(fixed)
            cmds(restored, 'StopBall')[0][2] = 60
            self.assertEqual(restored, old)
            self.assertEqual(revise_skill(fixed), fixed)
            self.assertEqual(dsl_gate_failures(dsl_gates(fixed)), [])
            encode_tree(fixed)

    def test_unknown_stop_is_rejected(self):
        with self.assertRaises(ValueError):
            revise_skill(['StopBall', -18, 99])


if __name__ == '__main__':
    unittest.main()
