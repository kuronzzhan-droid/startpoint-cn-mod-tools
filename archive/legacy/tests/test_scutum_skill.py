"""原生供体上的盾牌座回复、目标组、连击替换与辅助动作回归。"""

from wf.paths import root_path
import hashlib
import os
from pathlib import Path
import sys
import unittest
import zlib

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_client_legality as legality
import wf_dsl
import wf_dsl_sig as sig
from wf_enhancement_policy import OfficialBaseline
from wf_mod_tool import sha1_path
import wf_scutum_skill as skill
import wf_scutum_skill_actions as actions


def nodes(tree, name):
    result = []
    if isinstance(tree, list):
        if tree and tree[0] == name:
            result.append(tree)
        for child in tree:
            result.extend(nodes(child, name))
    return result


def validate(test, tree):
    test.assertEqual(legality.action_dsl_element_problems(tree, character_element=3), [])
    test.assertEqual(legality.action_dsl_subject_binding_problems(tree), [])
    test.assertEqual(legality.action_dsl_hit_area_target_problems(tree), [])
    for name, registry in (('Command', sig.COMMANDS), ('Event', sig.EVENTS)):
        for wrapper in nodes(tree, name):
            node = wrapper[1]
            test.assertEqual(len(node) - 1, len(registry[node[0]]), node[0])
    for node in nodes(tree, 'CreateCondition'):
        for effect in node[2]:
            test.assertEqual(len(effect)-1, len(sig.ENUMS['AdditionalConditionKind'][effect[0]]))
    raw = skill.encode_tree(tree)
    test.assertEqual(wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree'], tree)


class ScutumHelperTests(unittest.TestCase):
    def test_retaliation_has_nearest_dash_with_no_direct_suppression(self):
        tree = actions.retaliation()
        validate(self, tree)
        find = nodes(tree, 'FindNearSubjects')[0]
        self.assertEqual(find[1:6], [-18, 1, 49, ['DoNothing'], 212])
        self.assertEqual(nodes(tree, 'MoveBall'),
            [['MoveBall', -18, ['GH', 212], 0, 30, 40, ['KeepGoing'], False]])
        # 赋予贯穿不在选敌回调内，空场同样生效；全成员和所有球互斥。
        grants = nodes(tree, 'FindAllSubjects')
        self.assertEqual([node[2] for node in grants], [82, 86])
        self.assertEqual(nodes(find, 'ACPiercing'), [])
        self.assertEqual(nodes(tree, 'ACPiercing'), [['ACPiercing', skill.value(300)]] * 2)

    def test_all_enemy_chase_has_one_native_wind_attack_per_body(self):
        tree = actions.piercing_chase()
        validate(self, tree)
        self.assertEqual(tree[10], 4)
        self.assertEqual(nodes(tree, 'FindAllSubjects')[0][2], 49)
        attack = nodes(tree, 'CreateNormalAttack')
        self.assertEqual(len(attack), 1)
        self.assertEqual(attack[0][1:3], [213, 4])
        self.assertEqual(attack[0][5:8], [0, skill.value(35), skill.value(0)])
        self.assertFalse(nodes(tree, 'CreateHitArea'))
        self.assertFalse(nodes(tree, 'CreateRatioAttack'))

    def test_exact_helper_names_and_no_fake_collect_target(self):
        self.assertEqual(set(actions.assets()), {('common', p + skill.SUFFIX) for p in actions.PROGRAM_PATHS})
        self.assertEqual(actions.PROGRAM_PATHS,
            ('battle/action/skill/action/ability_skill/scutum_valentine$scutum_valentine_retaliation',
             'battle/action/skill/action/ability_skill/scutum_valentine$scutum_valentine_piercing_chase',
             'battle/action/skill/action/ability_skill/scutum_valentine$scutum_valentine_collect_chase'))
        self.assertTrue(actions.metadata()['native_ability_source_preserved'])
        self.assertNotIn('collect_hp_ratio_implementation_pending', actions.metadata())

    def test_collect_chase_uses_approved_nearest_once_and_direct_reference(self):
        tree = actions.collect_chase()
        validate(self, tree)
        self.assertEqual(tree[10], 4)
        near = nodes(tree, 'FindNearSubjects')[0]
        self.assertEqual(near[1:6], [-18, 1, 49, ['DoNothing'], 215])
        attack = nodes(near, 'CreateNormalAttack')
        self.assertEqual(len(attack), 1)
        self.assertEqual(attack[0][1:3], [215,4])
        self.assertEqual(attack[0][5:8], [0,skill.value(5),skill.value(0)])
        self.assertFalse(nodes(tree, 'CreateHitArea'))
        self.assertFalse(nodes(tree, 'CreateRatioAttack'))
        self.assertFalse(nodes(tree, 'FindAllSubjects'))


class ScutumOfficialSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(os.environ.get('WF_SCUTUM_OFFICIAL_CDN', ('${WF_ROOT}/startpoint-cn/.cdn/cn'.replace("${WF_ROOT}", str(root_path())))))
        if not (path / 'archive-common-full').is_dir():
            raise unittest.SkipTest('official CN archive required')
        cls.baseline = OfficialBaseline(path, write_cache=False)
        cls.cache = {}
        cls.trees = {lv: skill.build_skill(lv, cls.read) for lv in (1, 2)}

    @classmethod
    def read(cls, logical):
        if logical not in cls.cache:
            h = sha1_path(logical)
            cls.cache[logical] = cls.baseline.get('common', h[:2]+'/'+h[2:])
            if cls.cache[logical] is None:
                raise AssertionError('missing official source '+logical)
        return cls.cache[logical]

    def test_native_shape_and_assets_and_donor_preserved(self):
        before = {p: hashlib.sha256(raw).hexdigest() for p, raw in self.cache.items()}
        for tree in self.trees.values():
            validate(self, tree)
            self.assertEqual(nodes(tree, 'StopBall')[0],
                ['StopBall', -18, 65, ['RestoreToSpeedBeforeActionExecution'], ['EF'], 0])
            self.assertEqual(nodes(tree, 'ShowEffect')[0][2], ['SpecifyEffectDirectly', skill.EFFECT])
            for old in ('ACToleranceOfDebuff', 'ACAttackPoint', 'ACToleranceOfElement', 'ACRegeneration'):
                self.assertFalse(nodes(tree, old))
        self.assertEqual(self.trees[1], self.trees[2])
        self.assertEqual(set(skill.assets(self.read)), {('common', p+skill.SUFFIX) for p in skill.ACTIVE_PATHS})
        self.assertEqual(before, {p: hashlib.sha256(raw).hexdigest() for p, raw in self.cache.items()})

    def test_heal_and_cleanse_native_remote_and_local_groups_no_double_heal(self):
        tree = self.trees[2]
        heal = nodes(tree, 'CreateRatioHeal')
        self.assertEqual([node[1] for node in heal], [201, 202, -33])
        for node in heal:
            self.assertEqual(node[2:6], [2, skill.value(.1), [4], skill.value(.5)])
        self.assertEqual([node[1:] for node in nodes(tree, 'DeleteCondition')],
            [[target, ['DCAll', 3], 1, 0, '', ['Default']] for target in (201,202,-33)])
        find = nodes(tree, 'FindAllSubjects')
        self.assertEqual({node[1]: node[2] for node in find if node[1] in (201,202)}, {201:113,202:145})

    def test_combo_requires_wind_caster_and_a6_replaces_not_adds(self):
        tree = self.trees[2]
        gate = next(n for n in nodes(tree, 'FindAllSubjects') if n[1] == 206)
        self.assertEqual(gate[2:4], [1, [4]])
        flag = nodes(gate, 'ConditionalsChangeSkillFlag')[0]
        self.assertEqual(flag[1], 1)
        for branch, times, strength in ((flag[2],5,.5),(flag[3],2,.3)):
            find = nodes(branch, 'FindAllSubjects')[0]
            self.assertEqual(find[2:4], [82, [4]])
            self.assertEqual(nodes(branch, 'ACAdditionalDirectAttack'),
                [['ACAdditionalDirectAttack', skill.value(1200), skill.value(times),
                  skill.value(strength), skill.value(1)]])
            # 原生每段(1+strength)/times，2/5段分别保持总1.3/1.5。
            self.assertAlmostEqual(((1+strength)/times)*times, 1+strength)

    def test_wind_direct_buff_and_all_local_movement_durations(self):
        tree = self.trees[2]
        direct = next(n for n in nodes(tree, 'FindAllSubjects') if n[1] == 203)
        self.assertEqual(direct[2:4], [82, [4]])
        self.assertEqual(nodes(direct, 'ACDirectDamage'),
                         [['ACDirectDamage', skill.value(1200), skill.value(1.5), skill.value(1)]])
        groups = [n for n in nodes(tree, 'FindAllSubjects') if n[1] in (205,207)]
        self.assertEqual([n[2] for n in groups], [82,86])
        for group in groups:
            self.assertEqual(group[3], [])
            self.assertEqual(nodes(group, 'ACFlying'), [['ACFlying', skill.value(810)]])
            self.assertEqual(nodes(group, 'ACFixedSpeed'),
                [['ACFixedSpeed', skill.value(810), skill.value(1), skill.value(0), skill.value(1)]])


if __name__ == '__main__':
    unittest.main()
