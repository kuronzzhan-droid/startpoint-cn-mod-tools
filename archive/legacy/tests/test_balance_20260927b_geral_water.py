"""杰拉尔（水）129992 2026-09-27 第二批：技能鱼叉削韧 12×1.5→12×1（两档 36→30）；1.5 批能力倍率不回退。"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)
import wf_balance_20260927b_geral_water as B
import wf_client_legality as legality
import wf_dsl
from wf_character_revision import encode_tree
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems
from wf_midautumn_kitlib import panel_problems

FIXTURE = Path(__file__).parent / 'fixtures/balance_20260927b_geral_water.json'
WORKSPACE = ROOT / 'work/character_packs' / B.PACKAGES[0]
PROGRAMS = B.SKILL_PROGRAMS
LANCE_P13 = [11, 1, 2, 1, 6, 1, 1, 1, 23, 1, 0, 1, 13]
COMBO_P13 = [11, 1, 3, 1, 3, 1, 1, 1, 6, 1, 1, 1, 11, 1, 2, 1, 23, 1, 0, 1, 13]
FINISH_P13 = [11, 1, 3, 1, 3, 1, 1, 1, 6, 1, 1, 1, 11, 1, 3, 1, 3, 1, 1, 1, 23, 1, 0, 1, 13]


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


class GeralWaterBatch2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(FIXTURE.read_bytes())
        cls.inputs, cls.raw_sha, cls.context = data['inputs'], data['dsl_raw_sha256'], data['context']
        cls.out = B.revise(cls.read_from(cls.inputs))

    @staticmethod
    def read_from(inputs):
        return lambda kind, key: inputs[kind][_key(kind, key)]

    def tree(self, level):
        return self.inputs['dsl'][PROGRAMS[level]]

    # ---------------------------------------------------------------- 基线与输出形状

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(3, len(B.BEFORE))
        for (kind, key), want in B.BEFORE.items():
            self.assertEqual(want, B.digest(self.inputs[kind][_key(kind, key)]), (kind, key))

    def test_only_the_two_skill_trees_are_returned(self):
        self.assertEqual({'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl',
                          'server_text', 'new_programs', 'notes'}, set(self.out))
        for kind in ('ability', 'leader', 'cas', 'text', 'table', 'action', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)
        self.assertEqual(set(PROGRAMS.values()), set(self.out['dsl']))
        self.assertEqual([], self.out['new_programs'])

    def test_batch15_keys_are_not_read_or_written(self):
        # 1.5 批（4980e206 wf_balance_20260927_waterab）改的是能力键与追击树；本模块既不读也不返回它们。
        # 1.5 批只把两棵技能树当只读审计输入（BEFORE 摘要与本模块相同 ⇒ 1.5 批没改过它们），
        # 它的输出（能力键、追击串、追击树）与本模块输出（两棵技能树）不相交。
        import wf_balance_20260927_waterab as W
        batch15 = next(u for u in W.UNITS if u['CID'] == B.CID)
        self.assertEqual(['unicorn_lancer_rose'], batch15['PACKAGES'])
        self.assertEqual('0.1.14', batch15['PACKAGE_VERSION']['unicorn_lancer_rose'])   # 本批 0.1.15 在其上递增
        shared = set(batch15['BEFORE']) & set(B.BEFORE)
        self.assertEqual({('dsl', p) for p in PROGRAMS.values()}, shared)
        for key in shared:
            self.assertEqual(batch15['BEFORE'][key], B.BEFORE[key], key)
        fixture = json.loads((Path(__file__).parent / 'fixtures/balance_20260927_waterab.json').read_bytes())
        batch15_out = batch15['revise'](lambda kind, key: fixture[kind][key])
        self.assertEqual(set(), set(batch15_out['dsl']) & set(self.out['dsl']))
        self.assertIn(W.generator.STRIKE_PROGRAM, batch15_out['dsl'])                    # 追击树归 1.5 批
        for kind in ('ability', 'leader', 'cas', 'text', 'action', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)

    # ---------------------------------------------------------------- 改动前后值

    def test_skill_detoughness_36_to_30(self):
        for level in B.LEVELS:
            old, new = self.tree(level), self.out['dsl'][PROGRAMS[level]]
            self.assertEqual(36, B.detoughness(old), level)
            self.assertEqual(30, B.detoughness(new), level)
            self.assertLessEqual(B.detoughness(new), B.SKILL_CAP)
            self.assertEqual([{'min': 1.5, 'max': 1.5}], at(old, LANCE_P13))
            self.assertEqual([{'min': 1, 'max': 1}], at(new, LANCE_P13))
            self.assertEqual([{'min': 1, 'max': 1}], at(new, COMBO_P13))       # 连突不动
            self.assertEqual([{'min': 10, 'max': 10}], at(new, FINISH_P13))    # 收尾不动
            lance = at(new, LANCE_P13[:-5])
            self.assertEqual(('CreateHitArea', -18, ['GH', 1], ['CalculatedUsingMaxNumOfHits', 12]),
                             (lance[0], lance[2], lance[3], lance[14]))
        self.assertEqual({'lv1': [36.0, 30.0], 'lv2': [36.0, 30.0]}, self.out['notes']['skill_detoughness'])

    def test_only_the_lance_p13_leaf_moves(self):
        for level in B.LEVELS:
            old, new = self.tree(level), self.out['dsl'][PROGRAMS[level]]
            self.assertEqual([(*LANCE_P13, 0, 'min'), (*LANCE_P13, 0, 'max')], leaf_diff(old, new), level)
            restored = deepcopy(new)
            at(restored, LANCE_P13)[0] = deepcopy(at(old, LANCE_P13)[0])
            self.assertEqual(json.dumps(old), json.dumps(restored), level)
            # 新值 1 写 AMF3 integer：同一棵树里连突段 p13 1 就是整数（现成先例）。
            self.assertIs(int, type(at(old, COMBO_P13)[0]['max']))
            self.assertIs(int, type(at(new, LANCE_P13)[0]['max']))
            attack = at(new, LANCE_P13[:-1])
            self.assertIs(True, attack[8])                                     # 连击加成不动

    def test_multipliers_match_the_skill_descriptions(self):
        # 倍率不动：lv1 合计 60 倍（1.5×12 + 3×8 + 18），lv2 满级 75 倍（1.875×12 + 3.75×8 + 22.5）。
        for level, total in (('1', 60), ('2', 75)):
            new = self.out['dsl'][PROGRAMS[level]]
            hits = sum(n * at(new, path[:-1])[6][0]['max']
                       for n, path in ((12, LANCE_P13), (8, COMBO_P13), (1, FINISH_P13)))
            self.assertAlmostEqual(total, hits)
            self.assertIn(f'合计{total}倍', dict(self.inputs['action'][B.ACTION_KEY])[level][1])

    # ---------------------------------------------------------------- 门禁

    def test_trees_pass_dsl_gates_and_roundtrip(self):
        for program, tree in self.out['dsl'].items():
            self.assertEqual([], B.dsl_problems(tree), program)
            self.assertEqual([], kit_dsl_problems(tree, element=None), program)
            self.assertEqual([], legality.action_dsl_element_problems(tree, 1), program)
            rt = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))['tree']
            self.assertEqual(json.dumps(tree), json.dumps(rt), program)

    def test_skill_descriptions_carry_no_detoughness_numbers(self):
        texts = [f[1] for _, f in self.inputs['action'][B.ACTION_KEY]]
        texts += [row[i] for row in self.context['text']['129992'] for i in (5, 7)]
        texts += [row[i] for row in self.context['server_text']['129992'] for i in (5, 7)]
        self.assertEqual(6, len(texts))
        for text in texts:
            self.assertEqual([], panel_problems(text))
            for word in ('虚弱', '削韧', '眩晕', '击破'):
                self.assertNotIn(word, text)
            digits = ''.join(ch if ch.isdigit() else ' ' for ch in text).split()
            self.assertIn(digits, (['60'], ['75']), text)                     # 只有倍率数字

    # ---------------------------------------------------------------- fail closed

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
                value[0][1][1] = value[0][1][1] + 'x'
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                B.revise(self.read_from(drifted))
            missing = deepcopy(self.inputs)
            missing[kind][_key(kind, key)] = None
            with self.assertRaises(ValueError):
                B.revise(self.read_from(missing))

    def test_output_is_detached_from_inputs(self):
        out = B.revise(self.read_from(self.inputs))
        at(out['dsl'][PROGRAMS['2']], LANCE_P13)[0]['max'] = 99
        self.assertEqual([{'min': 1.5, 'max': 1.5}], at(self.tree('2'), LANCE_P13))

    def test_own_output_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live['dsl'].update(deepcopy(self.out['dsl']))
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            B.revise(self.read_from(live))
        for level in B.LEVELS:
            with self.assertRaisesRegex(ValueError, 'lance p13 preimage drift'):
                B.revise_skill_tree(self.out['dsl'][PROGRAMS[level]], level)

    def test_structure_guards(self):
        tree = deepcopy(self.tree('1'))
        at(tree, FINISH_P13)[0] = {'min': 7, 'max': 7}
        with self.assertRaisesRegex(ValueError, 'finisher p13 preimage drift'):
            B.revise_skill_tree(tree, '1')
        tree = deepcopy(self.tree('1'))
        at(tree, COMBO_P13[:-5])[14] = ['CalculatedUsingMaxNumOfHits', 9]
        with self.assertRaisesRegex(ValueError, 'combo hit area drift'):
            B.revise_skill_tree(tree, '1')
        tree = deepcopy(self.tree('2'))
        at(tree, LANCE_P13[:-1])[8] = False
        with self.assertRaisesRegex(ValueError, 'lance CreateNormalAttack'):
            B.revise_skill_tree(tree, '2')
        tree = deepcopy(self.tree('2'))
        tree[3] = False
        with self.assertRaisesRegex(ValueError, 'root header'):
            B.revise_skill_tree(tree, '2')

    def test_revise_is_deterministic(self):
        again = B.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(self.out, sort_keys=True), json.dumps(again, sort_keys=True))

    # ---------------------------------------------------------------- 接口常量

    def test_module_contract_constants(self):
        self.assertEqual(('129992', 'unicorn_lancer_rose'), (B.CID, B.CODE))
        self.assertEqual(['unicorn_lancer_rose'], B.PACKAGES)
        self.assertEqual({'unicorn_lancer_rose': '0.1.15'}, B.PACKAGE_VERSION)
        self.assertEqual([], B.CAPABILITIES)
        self.assertEqual({}, B.REVIEWED_DRIFT)
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)

    # ---------------------------------------------------------------- 历史生成器不会回退

    def test_historic_skill_transforms_fail_closed_on_the_new_trees(self):
        """wf_gerald_r2_data / wf_gerald_self_flying_fix 按旧树哈希拒绝本批输出 ⇒ 重跑不会把 p13 改回 1.5。"""
        import wf_gerald_r2_data as r2
        import wf_gerald_self_flying_fix as flying
        for level in B.LEVELS:
            new = self.out['dsl'][PROGRAMS[level]]
            with self.assertRaisesRegex(ValueError, 'unrecognized Gerald 1.4.764'):
                r2.revise_tree(new, level)
            with self.assertRaisesRegex(ValueError, 'unknown Gerald 1.4.768'):
                flying.fix_tree(new, int(level))

    # ---------------------------------------------------------------- 候选 / live（本机）

    @unittest.skipUnless((WORKSPACE / 'package/manifest.json').is_file()
                         and (ROOT / 'mod-tools/profiles.json').is_file(),
                         'local candidate workspace required')
    def test_candidate_is_clean_and_splices_dry(self):
        from wf_character_revision import RevisionCandidate
        manifest = WORKSPACE / 'package/manifest.json'
        before = manifest.read_bytes()
        meta = json.loads(before)
        candidate = RevisionCandidate(ROOT, WORKSPACE, reviewed_input_drift=B.REVIEWED_DRIFT,
                                      character_id=B.CID, code_name=B.CODE,
                                      snapshot_key='revision_20260927b',
                                      package_version=B.PACKAGE_VERSION[B.PACKAGES[0]],
                                      baseline_factory=lambda *a, **k: None)

        def tree_in_candidate(program):
            raw = candidate.read('common', wf_dsl.dsl_logical(program))
            return wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']

        if meta['snapshot'].get('revision_20260927b') is not None:
            # 第三轮（wf_balance_20260927c_panels，技能强化条目规范）暂存回写后候选再升一版；本批的 DSL 不受其影响。
            import wf_balance_20260927c_panels as P3
            want = P3.staged_version(meta, B.PACKAGES[0]) or B.PACKAGE_VERSION[B.PACKAGES[0]]
            self.assertEqual(want, meta['package_version'])
            for program, tree in self.out['dsl'].items():
                self.assertEqual(json.dumps(tree), json.dumps(tree_in_candidate(program)), program)
            return
        self.assertLess(tuple(map(int, meta['package_version'].split('.'))),
                        tuple(map(int, B.PACKAGE_VERSION[B.PACKAGES[0]].split('.'))))
        for program in self.out['dsl']:
            self.assertEqual(json.dumps(self.inputs['dsl'][program]), json.dumps(tree_in_candidate(program)))
        for program, tree in self.out['dsl'].items():
            candidate.emit('common', wf_dsl.dsl_logical(program), encode_tree(tree))
        evidence = candidate.finish({'dry_run': True}, apply=False)
        self.assertFalse(evidence['applied'])
        changed = {item['logical_path']: item['before_sha256'] for item in evidence['changed_files']}
        self.assertEqual({wf_dsl.dsl_logical(p): sha for p, sha in self.raw_sha.items()}, changed)
        self.assertEqual(before, manifest.read_bytes())

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
