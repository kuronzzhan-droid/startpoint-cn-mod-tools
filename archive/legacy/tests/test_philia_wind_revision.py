import copy
import json
from pathlib import Path
import unittest

import wf_seasonal7_kit_philia as K
from wf_character_revision import encode_tree
from wf_philia_wind_revision import revise_skill, revise_pf, SKILL_STOP, skill_description

ROOT = Path(__file__).resolve().parents[2]
PROTO = ROOT / K.PROTO_REL


@unittest.skipUnless((PROTO/'skill_2.json').is_file(), 'official-derived prototype fixture absent')
class WindRevisionTest(unittest.TestCase):
    def proto(self, name):
        return json.loads((PROTO/name).read_text(encoding='utf-8'))

    def test_skill_slows_but_preserves_count_damage_and_range(self):
        old = self.proto('skill_2.json')
        new = revise_skill(old)
        self.assertEqual(K.cmds(new, 'CreateNormalAttack'), K.cmds(old, 'CreateNormalAttack'))
        self.assertEqual(len(K.cmds(new, 'MoveHitArea')), 10)
        self.assertEqual({m[4] for m in K.cmds(new, 'MoveHitArea')}, {12})
        launch = next(e for e in K.events(new) if e[:2] == ['Wait', 20])
        self.assertEqual([e[1][1] for e in launch[3][1]], [24*i for i in range(10)])
        self.assertEqual(SKILL_STOP, 15)
        self.assertLess(SKILL_STOP, 20)
        self.assertEqual(18*100, 12*150)

    def test_skill_world_up_pierces_each_enemy_and_rain_snapshots_each_hit(self):
        for level in (1, 2):
            new = revise_skill(self.proto(f'skill_{level}.json'))
            self.assertEqual(K.cmds(new, 'FindNearSubjects'), [])
            swords = [c for c in K.cmds(new, 'CreateHitArea') if c[2] == -18]
            self.assertEqual(len(swords), 10)
            for c in swords:
                self.assertEqual((c[3], c[6], c[18]), (['AB'], 0, ['None']))
                self.assertEqual(c[15], ['Some', K.slv(1, 1)])
                self.assertEqual([m[2:5] for m in K.cmds(c[20], 'MoveHitArea')], [[['AB'], 0, 12]])
                rain = next(r for r in K.cmds(c[23], 'CreateReferencePoint') if 200 <= r[10] < 240)
                self.assertEqual(rain[1], c[21])
                self.assertFalse(rain[6])
                self.assertEqual([f[6] for f in K.cmds(c[20], 'ShowEffect') if f[3] == -18], [['AB']])

    def test_description_preserves_other_effects(self):
        old = '射出10把追踪光剑，并在命中位置降下剑雨，造成光属性伤害／其他效果'
        new = skill_description(old)
        self.assertEqual(new, '向上射出10道贯穿风刃，并在各命中位置降下剑雨，造成光属性伤害／其他效果')
        self.assertEqual(skill_description(new), new)
        with self.assertRaises(ValueError):
            skill_description('unknown description')

    def test_pf_collision_launch_is_local_and_five_way_straight_piercing(self):
        old = self.proto('pf_lv3.json')
        new = revise_pf(old)
        collision = next(e for e in K.events(new) if e[0] == 'CollisionOfBallAndEnemy')
        burst = next(c for c in K.cmds(collision[5], 'CreateReferencePoint') if c[10] == 1)
        self.assertEqual(burst[1], collision[4])
        swords = [c for c in K.cmds(burst[11], 'CreateHitArea') if 200 <= c[19] < 225]
        self.assertEqual(sorted(c[6] for c in swords), sorted(K.PF_LAUNCH_DIRS))
        for c in swords:
            self.assertEqual(c[18], ['None'])
            self.assertEqual(c[15], ['Some', K.slv(1, 1)])
            self.assertEqual(K.cmds(c[20], 'FindNearSubjects'), [])
            self.assertEqual([m[2] for m in K.cmds(c[20], 'MoveHitArea')], [['CD']])
            rain = next(r for r in K.cmds(c[23], 'CreateReferencePoint') if 300 <= r[10] < 320)
            self.assertEqual(rain[1], c[21])
            self.assertFalse(rain[6])
        self.assertEqual(K.cmds(new, 'CreateNormalAttack'), K.cmds(old, 'CreateNormalAttack'))

    def test_all_levels_pass_native_gates_and_roundtrip_idempotently(self):
        for name, transform in [(f'skill_{n}.json', revise_skill) for n in (1, 2)] + [
                (f'pf_lv{n}.json', revise_pf) for n in (1, 2, 3)]:
            new = transform(self.proto(name))
            self.assertEqual(K.dsl_gate_failures(K.dsl_gates(new)), [], name)
            self.assertEqual(transform(new), new, name)
            encode_tree(new)

    def test_collision_binding_cannot_escape_event(self):
        new = revise_pf(self.proto('pf_lv1.json'))
        burst = next(c for c in K.cmds(new, 'CreateReferencePoint') if c[10] == 1)
        new[11][1].append(['Command', copy.deepcopy(burst)])
        self.assertTrue(any('CreateReferencePoint[1]=0 unbound' in p for p in K.scope_problems(new)))

    def test_unknown_speed_or_hit_policy_is_not_overwritten(self):
        bad = self.proto('skill_1.json')
        K.cmds(bad, 'MoveHitArea')[0][4] = 99
        with self.assertRaises(ValueError):
            revise_skill(bad)
        bad = self.proto('pf_lv1.json')
        next(c for c in K.cmds(bad, 'CreateHitArea') if c[19] == 200)[18] = ['Some', 3]
        with self.assertRaises(ValueError):
            revise_pf(bad)


if __name__ == '__main__':
    unittest.main()
