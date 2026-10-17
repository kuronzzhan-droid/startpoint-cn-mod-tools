"""拉夫马诺（光龙）151159 2026-09-27 第二批：技能 8 段 p13 15→2，每次施放削韧 120→16。"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)
import wf_balance_20260927b_goldendragon as B
import wf_dsl
from wf_character_revision import encode_tree
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems

FIXTURE = Path(__file__).parent / 'fixtures/balance_20260927b_goldendragon.json'
SK1, SK2 = (B.SKILL_PROGRAMS[level] for level in B.SKILL_LEVELS)
HIT_P13 = [11, 1, 6, 1, 3, 1, 0, 1, 23, 1, 0, 1, 13]        # Wait(100) 伤害判定区（8 段）
HIT_AREA = HIT_P13[:-5]                                     # 伤害判定区 CreateHitArea 参数
DEBUFF_AREA = [11, 1, 4, 1, 3, 1, 0, 1]                     # Wait(55) 减益判定区（无攻击）


def _key(kind, key):
    return '|'.join(key) if kind == 'table' else key


def leaf_diff(a, b, path=()):
    """两棵树逐叶比对（含 int/float 类型），返回不同处的路径。"""
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [p for i, (x, y) in enumerate(zip(a, b)) for p in leaf_diff(x, y, (*path, i))]
    if isinstance(a, dict) and isinstance(b, dict) and a.keys() == b.keys():
        return [p for k in a for p in leaf_diff(a[k], b[k], (*path, k))]
    return [] if (type(a) is type(b) and a == b) else [path]


def at(tree, path):
    for step in path:
        tree = tree[step]
    return tree


def slv(value):
    return [{'min': value, 'max': value}]


class GoldenDragonBatch2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(FIXTURE.read_bytes())
        cls.inputs, cls.raw_sha, cls.context = data['inputs'], data['dsl_raw_sha256'], data['context']
        cls.out = B.revise(cls.read_from(cls.inputs))

    @staticmethod
    def read_from(inputs):
        return lambda kind, key: inputs[kind][_key(kind, key)]

    def tree(self, program):
        return self.inputs['dsl'][program]

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(3, len(B.BEFORE))
        for (kind, key), want in B.BEFORE.items():
            self.assertEqual(want, B.digest(self.inputs[kind][_key(kind, key)]), (kind, key))
        self.assertEqual({'1': SK1, '2': SK2},
                         {inner: fields[7] for inner, fields in self.inputs['action'][B.CODE]})

    def test_only_the_two_skill_trees_are_returned(self):
        self.assertEqual({'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl',
                          'server_text', 'new_programs', 'notes'}, set(self.out))
        for kind in ('ability', 'leader', 'cas', 'text', 'table', 'action', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)
        self.assertEqual({SK1, SK2}, set(self.out['dsl']))
        self.assertEqual([], self.out['new_programs'])
        self.assertTrue(all(p.startswith('battle/action/skill/action/rare5/golden_dragon_jr$')
                            for p in self.out['dsl']))   # 不碰暗龙 darkness_dragon

    def test_skill_detoughness_120_to_16(self):
        for program in (SK1, SK2):
            self.assertEqual(120, B.detoughness(self.tree(program)), program)
            self.assertEqual(16, B.detoughness(self.out['dsl'][program]), program)
            self.assertLessEqual(B.detoughness(self.out['dsl'][program]), 30)
            self.assertEqual({15: 1}, B.p13_census(self.tree(program)))
            self.assertEqual({2: 1}, B.p13_census(self.out['dsl'][program]))

    def test_hit_area_shape_and_p13_before_after(self):
        for program in (SK1, SK2):
            old, new = self.tree(program), self.out['dsl'][program]
            area = at(new, HIT_AREA)
            self.assertEqual(('CreateHitArea', -1, ['SpecifyHitAreaLifetimeDirectly', 120],
                              ['CalculatedUsingMaxNumOfHits', 8], ['None']),
                             (area[0], area[2], area[13], area[14], area[15]))
            self.assertEqual(slv(15), at(old, HIT_P13))
            self.assertEqual(slv(2), at(new, HIT_P13))
            self.assertIs(int, type(at(new, HIT_P13)[0]['max']))
            self.assertEqual([{'min': 15, 'max': 15}], at(new, HIT_P13[:-1])[6])   # 倍率不动
            self.assertEqual(json.dumps(at(old, DEBUFF_AREA)), json.dumps(at(new, DEBUFF_AREA)))

    def test_only_the_p13_leaf_moves(self):
        for program in (SK1, SK2):
            old, new = self.tree(program), self.out['dsl'][program]
            self.assertEqual([(*HIT_P13, 0, 'min'), (*HIT_P13, 0, 'max')], leaf_diff(old, new), program)
            restored = deepcopy(new)
            at(restored, HIT_P13)[0] = deepcopy(at(old, HIT_P13)[0])
            self.assertEqual(json.dumps(old), json.dumps(restored), program)

    def test_trees_pass_dsl_gates_and_roundtrip(self):
        for program, tree in self.out['dsl'].items():
            self.assertEqual([], B.dsl_problems(tree), program)
            self.assertEqual([], kit_dsl_problems(tree, element=None), program)
            rt = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))['tree']
            self.assertEqual(json.dumps(tree), json.dumps(rt), program)

    def test_texts_carry_no_down_numbers(self):
        descs = [fields[1] for _, fields in self.inputs['action'][B.CODE]]
        descs += [self.context['text'][B.CID][0][5], self.context['text'][B.CID][0][7]]
        descs += [self.context['server_text'][B.CID][0][5], self.context['server_text'][B.CID][0][7]]
        for desc in descs:   # 唯一的数字是「消除1个强化效果」，与削韧无关
            self.assertEqual(['1'], [ch for ch in desc if ch.isdigit()], desc)
            for word in ('虚弱', '削韧', '眩晕', '击破', 'Down'):
                self.assertNotIn(word, desc)

    def test_live_drift_is_rejected_and_inputs_are_not_mutated(self):
        original = deepcopy(self.inputs)
        B.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(original), json.dumps(self.inputs))
        for kind, key in B.BEFORE:
            drifted = deepcopy(self.inputs)
            value = drifted[kind][_key(kind, key)]
            if kind == 'dsl':
                value[10] = 4
            else:
                value[0][1][4] = '581'
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                B.revise(self.read_from(drifted))
            missing = deepcopy(self.inputs)
            missing[kind][_key(kind, key)] = None
            with self.assertRaises(ValueError):
                B.revise(self.read_from(missing))

    def test_own_output_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live['dsl'].update(deepcopy(self.out['dsl']))
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            B.revise(self.read_from(live))
        for level in B.SKILL_LEVELS:
            with self.assertRaisesRegex(ValueError, 'hit-area / p13 preimage drift'):
                B.revise_skill_tree(self.out['dsl'][B.SKILL_PROGRAMS[level]], level)

    def test_structure_guards(self):
        tree = deepcopy(self.tree(SK1))
        at(tree, HIT_AREA)[14] = ['CalculatedUsingMaxNumOfHits', 9]
        with self.assertRaisesRegex(ValueError, 'hit-area / p13 preimage drift'):
            B.revise_skill_tree(tree, 1)
        tree = deepcopy(self.tree(SK2))
        tree[10] = 3
        with self.assertRaisesRegex(ValueError, 'root header drift'):
            B.revise_skill_tree(tree, 2)
        live = deepcopy(self.inputs)
        live['action'][B.CODE][0][1][7] = 'battle/action/skill/action/rare4/darkness_dragon$darkness_dragon_1'
        drifted_digest = B.digest(live['action'][B.CODE])
        self.assertNotEqual(B.BEFORE['action', B.CODE], drifted_digest)
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            B.revise(self.read_from(live))

    def test_revise_is_deterministic(self):
        again = B.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(self.out, sort_keys=True), json.dumps(again, sort_keys=True))

    def test_module_contract_constants(self):
        self.assertEqual(('151159', 'golden_dragon_jr'), (B.CID, B.CODE))
        self.assertEqual([], B.PACKAGES)          # reworked_official，无 flow 包
        self.assertEqual({}, B.PACKAGE_VERSION)
        self.assertEqual([], B.CAPABILITIES)
        self.assertEqual({}, B.REVIEWED_DRIFT)
        self.assertEqual(4, B.ELEMENT)
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)
        self.assertEqual({'lv1': [120, 16], 'lv2': [120, 16]}, self.out['notes']['skill_detoughness'])

    @unittest.skipUnless((ROOT / 'mod-tools/profiles.json').is_file(), 'local live store required')
    def test_live_is_either_the_baseline_or_this_output(self):
        import wf_mod_tool as core
        store = Path(core.resolve_active_store())
        for program, tree in self.out['dsl'].items():
            path = core.table_path(store, wf_dsl.dsl_logical(program))
            if not path.is_file():
                self.skipTest('live store DSL not present')
            live = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))['tree']
            self.assertIn(B.digest(live), {B.BEFORE['dsl', program], B.digest(tree)}, program)


if __name__ == '__main__':
    unittest.main()
