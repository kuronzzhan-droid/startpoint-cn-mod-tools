from copy import deepcopy
import json
from pathlib import Path
import unittest

import wf_rolf_tracking_pf as R
import wf_seasonal7_kit_philia as K


class RolfTrackingTest(unittest.TestCase):
    def original(self, level):
        return json.loads((Path(__file__).parent/f'fixtures/rolf_pf_before_{level}.json').read_bytes())

    def test_all_levels_native_roundtrip_scopes_and_effects(self):
        for level in (1,2,3):
            with self.subTest(level=level):
                old = self.original(level)
                new = R.revise(old,level)
                self.assertEqual(K.dsl_gate_failures(R.validate(new,level)), [])
                self.assertEqual(list(K.spec_paths(old)),list(K.spec_paths(new)))
                self.assertEqual(K.cmds(old,'CreateNormalAttack'),K.cmds(new,'CreateNormalAttack'))
                # Buff/heal target bindings are renamed, all parameters stay.
                for name in ('CreateCondition','CreateRatioHeal'):
                    self.assertEqual([c[2:] for c in K.cmds(old,name)], [c[2:] for c in K.cmds(new,name)])
                self.assertEqual(R.revise(new,level),new)
                self.assertEqual(old,self.original(level))

    def test_ball_and_shot_target_bindings_are_native_and_local(self):
        t = R.revise(self.original(3),3)
        near = K.cmds(t,'FindNearSubjects')
        self.assertEqual([n[5] for n in near], [1000,1001])
        for n in near:
            self.assertEqual(n[1:5],[-18,1,49,['DoNothing']])
        self.assertEqual(K.cmds(near[0], 'MoveBall'), [])
        self.assertEqual(len(K.cmds(near[1], 'MoveBall')),1)
        for area in K.cmds(near[0],'CreateHitArea'):
            self.assertEqual(area[3],['GH',1000])
        for fx in K.cmds(near[0],'ShowEffect'):
            self.assertEqual(fx[6],['GH',1000])

    def test_tracking_ends_on_collision_or_timeout_even_without_enemy(self):
        for level in (1,2,3):
            t = R.revise(self.original(level),level)
            duration = K.cmds(t,'SetPowerFilpSuppress')[0][1]
            events = K.events(t)
            repeat = next(e for e in events if e[0]=='Repeat')
            collision = next(e for e in events if e[0]=='CollisionOfBallAndEnemy')
            self.assertLess(repeat[1]*(repeat[2]-1)+R.STEP,duration)
            self.assertIn(['RemoveEvent',R.CHASE_TAG],K.cmds(collision,'RemoveEvent'))
            ending = next(e for e in t[11][1] if e[0]=='Event' and e[1][:2]==['Wait',duration])
            self.assertEqual(K.cmds(ending,'NotifyPowerflipEnd'),[['NotifyPowerflipEnd',-18]])
            self.assertEqual(len(K.cmds(t,'NotifyPowerflipEnd')),1)
            self.assertFalse(K.cmds(ending,'FindNearSubjects'))

    def test_unexpected_source_does_not_silently_rebuild(self):
        t = self.original(1)
        K.cmds(t,'SetPowerFilpSuppress')[0][1] = 60
        with self.assertRaises(ValueError):R.revise(t,1)


if __name__ == '__main__':unittest.main()
