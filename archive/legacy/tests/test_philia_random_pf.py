"""覆盖每一条原生随机分支，不以静态分支总数冒充实际发射数。"""
from copy import deepcopy
import json
from math import degrees, radians
from pathlib import Path
import unittest

import wf_seasonal7_kit_philia as K
import wf_philia_random_pf as R
from wf_philia_wind_revision import revise_pf as straight_pf
from wf_character_revision import encode_tree

PROTO = Path(__file__).resolve().parents[2] / K.PROTO_REL


@unittest.skipUnless((PROTO/'pf_lv1.json').is_file(), 'official-derived PF fixture absent')
class RandomPfTest(unittest.TestCase):
    def source(self, level):
        return straight_pf(json.loads((PROTO/f'pf_lv{level}.json').read_bytes()))

    def test_all_levels_all_branches_keep_damage_hit_policy_and_visuals(self):
        for level in (1, 2, 3):
            source = self.source(level)
            original = [n for n in R.launch_body(source) if n[0] == 'Command'
                        and n[1][0] == 'CreateHitArea' and 200 <= n[1][19] < 225]
            tree = R.revise_pf(source)
            self.assertEqual(set(K.spec_paths(tree)), set(K.spec_paths(source)))
            for name in ('NotifyPowerflipEnd', 'SetPowerFilpSuppress', 'CreateCondition'):
                self.assertEqual(K.cmds(tree, name), K.cmds(source, name))
            choice = K.cmds(tree, 'ConditionalsProbability')[0]
            for branch in choice[1][1]:
                for i, blade in enumerate(branch[1][1][1]):
                    # Undo only angle/art heading and subject remapping; exact tree equality
                    # proves no change to hit count, damage, speed, rain, or its timing.
                    reverse = {1: 1}
                    old_ids, new_ids = [], []
                    K.remap_subjects(deepcopy(original[i]), lambda n: old_ids.append(n) or n)
                    K.remap_subjects(deepcopy(blade), lambda n: new_ids.append(n) or n)
                    reverse.update(zip(new_ids, old_ids))
                    restored = deepcopy(blade)
                    K.remap_subjects(restored, reverse.__getitem__)
                    restored[1][6] = original[i][1][6]
                    attacks = K.cmds(restored, 'CreateNormalAttack')
                    original_damage = K.cmds(original[i], 'CreateNormalAttack')[0][6][0]['min']
                    self.assertEqual(attacks[0][6], K.slv(original_damage*1.25, original_damage*1.25))
                    attacks[0][6] = K.slv(original_damage, original_damage)
                    old_rain = K.cmds(original[i], 'CreateNormalAttack')[1][6][0]['min']
                    self.assertEqual(attacks[1][6], K.slv(R.RAIN_DAMAGE[old_rain], R.RAIN_DAMAGE[old_rain]))
                    attacks[1][6] = K.slv(old_rain, old_rain)
                    for a, b in zip(K.cmds(restored, 'ShowEffect'), K.cmds(original[i], 'ShowEffect')):
                        a[9] = b[9]
                    self.assertEqual(restored, original[i])
            self.assertEqual(R.revise_pf(tree), tree)
            self.assertEqual(straight_pf(tree), tree)
            encode_tree(tree)

    def test_one_draw_rotates_five_blades_with_72_degree_gaps(self):
        choices = K.cmds(R.revise_pf(self.source(3)), 'ConditionalsProbability')
        self.assertEqual(len(choices), 1)
        starts = []
        for branch in choices[0][1][1]:
            volley = branch[1][1][1]
            self.assertEqual(len(volley), 5)
            angles = [degrees(n[1][6]) for n in volley]
            starts.append(round(angles[0]))
            for i in range(5):
                self.assertAlmostEqual((angles[(i+1)%5]-angles[i]) % 360, 72)
        self.assertEqual(starts, list(range(0, 360, 10)))

    def test_migrates_independent_draws_to_same_result_as_generator(self):
        source = self.source(2)
        expected = R.revise_pf(source)
        legacy = deepcopy(expected)
        body = R.launch_body(legacy)
        node = next(n for n in body if n[0] == 'Command' and n[1][0] == 'ConditionalsProbability')
        independent = []
        for i in range(5):
            branches = []
            for j, branch in enumerate(node[1][1][1]):
                blade = deepcopy(branch[1][1][1][i])
                blade[1][6] = radians(j*10+i*2)
                K.cmds(blade, 'CreateNormalAttack')[0][6] = K.slv(1.0, 1.0)
                for fx in K.cmds(blade[1][20], 'ShowEffect'):
                    if fx[3] == 1 and fx[6] == ['AB']:
                        fx[9] = blade[1][6]
                branches.append(['Block', [['Command', ['ProbabilityWeight', 1.0]], ['Block', [blade]]]])
            independent.append(['Command', ['ConditionalsProbability', ['Block', branches]]])
        index = body.index(node)
        body[index:index+1] = independent
        self.assertEqual(R.revise_pf(legacy), expected)

    def test_invalid_random_payload_or_scope_is_rejected(self):
        tree = R.revise_pf(self.source(1))
        broken = deepcopy(tree)
        K.cmds(broken, 'ConditionalsProbability')[0][1][1][0][1].pop()
        with self.assertRaises(ValueError):
            R.validate(broken)

    def test_existing_even_volley_only_changes_rain_multiplier(self):
        for level, old, new in ((1, 2.5, 1.5), (2, 3.5, 2.5), (3, 5.5, 3.5)):
            expected = R.revise_pf(self.source(level))
            previous = deepcopy(expected)
            for branch in K.cmds(previous, 'ConditionalsProbability')[0][1][1]:
                for blade in branch[1][1][1]:
                    rain = K.cmds(blade, 'CreateNormalAttack')[1]
                    self.assertEqual(rain[6], K.slv(new, new))
                    rain[6] = K.slv(old, old)
            self.assertEqual(R.revise_pf(previous), expected)
        broken = deepcopy(expected)
        broken[10] = 2
        with self.assertRaisesRegex(ValueError, 'power flip damage bucket'):
            R.validate(broken)
        broken = deepcopy(expected)
        K.cmds(broken, 'ConditionalsProbability')[0][1][1][0][1][1][1][1][1][6] += 0.1
        with self.assertRaisesRegex(ValueError, 'direction'):
            R.validate(broken)
        broken = deepcopy(expected)
        K.cmds(broken, 'MoveHitArea')[-1][1] = 999999
        with self.assertRaises(ValueError):
            R.validate(broken)


if __name__ == '__main__':
    unittest.main()
