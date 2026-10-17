"""光杰拉德真实两档技能的单主体比例结算与其他内容保护。"""

from wf.paths import root_path
from copy import deepcopy
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
import wf_gerald_percent_skill as skill
import wf_gerald_percent_revision as revision


def nodes(tree, name):
    return [node for _path, node in skill._walk(tree) if node and node[0] == name]


def apply_native_once(command, enemies):
    """独立转录 findNear(slice N) 与 HP>= 分支，数组元素代表敌人主体。

    即使主体含多个受击部位，最近主体的 RatioAttack 也只写入一次。
    模拟不替代原生引擎；几何、伤害 cap 和阶段规则另由证据限定。
    """
    find = command[1]
    selected = sorted(enemies, key=lambda enemy: enemy['distance'])[:find[2]]
    attacks = []
    for target in selected:
        payload = find[6][1][0][1]
        if payload[0] == 'ConditionalsHealthPointRatioOf':
            branch = 3 if target['hp'] * 100 >= payload[2] * target['max_hp'] else 4
            payload = payload[branch][1][0][1]
        attacks.append((target['id'], int(target['hp'] * payload[3][0]['min'])))
    return attacks


class GeraldPercentHelperTests(unittest.TestCase):
    def test_nearest_body_once_empty_target_and_strict_threshold(self):
        command = skill.nearest_percent_attack(.05, execute_below_percent=5)
        self.assertEqual(apply_native_once(command, []), [])
        for hp, expected in ((49, 49), (50, 2), (51, 2), (1000, 50)):
            enemies = [dict(id='far', distance=10, hp=1000, max_hp=1000, parts=1),
                       dict(id='boss', distance=1, hp=hp, max_hp=1000, parts=12)]
            self.assertEqual(apply_native_once(command, enemies), [('boss', expected)])

    def test_reusable_two_percent_without_execute_or_extra_callback(self):
        command = skill.nearest_percent_attack(.02, target_subject=302)
        self.assertEqual(command[1][1:6], [-18, 1, 49, ['DoNothing'], 302])
        self.assertEqual(nodes(command, 'CreateRatioAttack'),
                         [['CreateRatioAttack', 302, 1, [{'min': .02, 'max': .02}]]])
        self.assertFalse(nodes(command, 'CreateHitArea'))
        self.assertFalse(nodes(command, 'ConditionalsHealthPointRatioOf'))

    def test_rejects_invalid_rates_thresholds_and_bindings(self):
        for rate in (True, 0, -.01, 1.01, float('nan'), float('inf')):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                skill.nearest_percent_attack(rate)
        for threshold in (True, 0, 101, 5.5):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                skill.nearest_percent_attack(.05, execute_below_percent=threshold)
        for binding in (True, -1, 0, 1.5):
            with self.subTest(binding=binding), self.assertRaises(ValueError):
                skill.nearest_percent_attack(.05, target_subject=binding)

    def test_metadata_does_not_claim_uncapped_execute_or_new_apk(self):
        meta = skill.metadata()
        self.assertEqual(meta['native_damage_cap'], 9_999_999_999)
        self.assertFalse(meta['unconditional_execute_guaranteed'])
        self.assertTrue(meta['native_cap_and_phase_rules_preserved'])
        self.assertFalse(meta['requires_new_apk'])
        self.assertNotIn('acceptance_pending', meta)

    def test_description_changes_only_old_percent_effect_and_rejects_drift(self):
        prefix = '强化演出及领域保持＋'
        self.assertEqual(revision.description(prefix + revision.OLD_EFFECT),
                         prefix + revision.NEW_EFFECT)
        for text in ('changed', revision.OLD_EFFECT * 2, revision.NEW_EFFECT):
            with self.assertRaises(ValueError):
                revision.description(text)


class GeraldPercentLiveFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(os.environ.get('WF_GERALD_SOURCE_ROOT',
            ('${WF_ROOT}/startpoint-cn/work/character_packs/white_wolf_gerald/package/roots/common'.replace("${WF_ROOT}", str(root_path())))))
        if not source.is_dir():
            raise unittest.SkipTest('reviewed Gerald source assets required; set WF_GERALD_SOURCE_ROOT')
        cls.raw = {level: (source / logical).read_bytes() for level, logical in skill.ACTIVE_PATHS.items()}
        cls.before = {level: wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']
                      for level, raw in cls.raw.items()}
        cls.after = {level: skill.rewrite_skill(tree) for level, tree in cls.before.items()}

    def test_baseline_hash_and_all_native_signatures_roundtrip_bindings(self):
        for level, tree in self.after.items():
            self.assertEqual(hashlib.sha256(self.raw[level]).hexdigest(), skill.SOURCE_SHA256[level])
            encoded = skill.patch_skill_bytes(self.raw[level], level)
            self.assertEqual(wf_dsl.parse_dsl(zlib.decompress(encoded, -15))['tree'], tree)
            self.assertEqual(legality.action_dsl_element_problems(tree, character_element=4), [])
            self.assertEqual(legality.action_dsl_subject_binding_problems(tree), [])
            self.assertEqual(legality.action_dsl_hit_area_target_problems(tree), [])
            for _path, node in skill._walk(tree):
                if node and node[0] in ('Command', 'Event'):
                    registry = sig.COMMANDS if node[0] == 'Command' else sig.EVENTS
                    self.assertEqual(len(node[1])-1, len(registry[node[1][0]]), node[1][0])

    def test_inverse_change_exactly_restores_entire_tree(self):
        for level, tree in self.after.items():
            restored = deepcopy(tree)
            target = [(p, n) for p, n in skill._walk(restored)
                      if n and n[0] == 'FindNearSubjects' and n[5] == skill.TARGET_SUBJECT]
            self.assertEqual(len(target), 1)
            path, _find = target[0]
            siblings = skill._at(restored, path[:-2])
            previous = siblings[path[-2]-1][1]
            self.assertEqual(previous[0], 'CreateHitArea')
            self.assertEqual(previous[9][0], 'Rectangle')
            self.assertEqual(previous[13], ['SpecifyHitAreaLifetimeDirectly', 5])
            previous[23][1].insert(1, ['Command', ['CreateRatioAttack', 2, 1,
                                                   [{'min': .05, 'max': .05}]]])
            siblings.pop(path[-2])
            self.assertEqual(restored, self.before[level])
            self.assertEqual(skill.rewrite_skill(self.before[level]), tree)

    def test_once_only_enhanced_branch_no_ratio_inside_any_hit_area(self):
        for tree in self.after.values():
            flag = nodes(tree, 'ConditionalsChangeSkillFlag')[0]
            self.assertEqual(flag[1], 1)
            self.assertEqual(len(nodes(flag[2], 'CreateRatioAttack')), 2)
            self.assertFalse(nodes(flag[3], 'CreateRatioAttack'))
            for area in nodes(tree, 'CreateHitArea'):
                self.assertFalse(nodes(area, 'CreateRatioAttack'))
            find = next(n for n in nodes(tree, 'FindNearSubjects') if n[5] == skill.TARGET_SUBJECT)
            self.assertEqual(find[2], 1)
            self.assertFalse(nodes(find, 'Wait'))
            self.assertFalse(nodes(find, 'Event'))

    def test_source_drift_or_second_application_rejected(self):
        with self.assertRaises(ValueError):
            skill.patch_skill_bytes(self.raw[1] + b'changed', 1)
        for tree in self.after.values():
            with self.assertRaises(ValueError):
                skill.rewrite_skill(tree)
        changed = deepcopy(self.before[1])
        nodes(changed, 'CreateRatioAttack')[0][3][0]['min'] = .1
        with self.assertRaises(ValueError):
            skill.rewrite_skill(changed)


if __name__ == '__main__':
    unittest.main()
