"""墨斯伊克 149997 2026-09-27 第二批：PF 风刃削韧 10/25/50 → 10/20/25（Lv2/Lv3 正好顶到上限）。"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)
import wf_balance_20260927b_mosiyike as B
import wf_balance_20260927b_gray3 as G3
import wf_balance_20260927c_mosiyike as C3
import wf_dsl
from wf_character_revision import encode_tree
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems
from wf_midautumn_kitlib import panel_problems

FIXTURE = Path(__file__).parent / 'fixtures/balance_20260927b_mosiyike.json'
WORKSPACE = ROOT / 'work/character_packs' / B.PACKAGES[0]
PF1, PF2, PF3 = (B.PF_PROGRAMS[level] for level in B.PF_LEVELS)


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


def p13_paths(node, path=()):
    """树里每个 CreateNormalAttack 的 p13 路径（按树序）。"""
    if isinstance(node, list):
        if len(node) > 1 and node[0] == 'Command' and isinstance(node[1], list) \
                and node[1][0] == 'CreateNormalAttack':
            return [(*path, 1, 13)]
        return [p for i, child in enumerate(node) for p in p13_paths(child, (*path, i))]
    return []


def slv(value):
    return [{'min': value, 'max': value}]


class MosiyikeBatch2Test(unittest.TestCase):
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

    # ---------------------------------------------------------------- 基线与输出形状

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(4, len(B.BEFORE))
        for (kind, key), want in B.BEFORE.items():
            self.assertEqual(want, B.digest(self.inputs[kind][_key(kind, key)]), (kind, key))
        leader = self.context['leader'][B.CID]
        self.assertEqual([('mosiyike_pf', '1,2,3')], [(r[80], r[81]) for r in leader if r[45] == '722'])
        self.assertEqual([[PF1, PF2, PF3]],
                         self.inputs['table']['master/skill/power_flip_action.orderedmap|mosiyike_pf'])

    def test_only_lv2_and_lv3_are_returned(self):
        self.assertEqual({'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl',
                          'server_text', 'new_programs', 'notes'}, set(self.out))
        for kind in ('ability', 'leader', 'cas', 'text', 'table', 'action', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)
        self.assertEqual({PF2, PF3}, set(self.out['dsl']))       # Lv1 10 已在上限内，不返回
        self.assertEqual((2, 3), B.CHANGED_LEVELS)
        self.assertEqual([], self.out['new_programs'])

    # ---------------------------------------------------------------- 强化弹射（B.2）

    def test_pf_detoughness_10_20_25(self):
        self.assertEqual(10, B.detoughness(self.tree(PF1)))
        for program, before, after in ((PF2, 25, 20), (PF3, 50, 25)):
            self.assertEqual(before, B.detoughness(self.tree(program)), program)
            self.assertEqual(after, B.detoughness(self.out['dsl'][program]), program)
        for level in B.PF_LEVELS:
            final = self.out['dsl'].get(B.PF_PROGRAMS[level], self.tree(B.PF_PROGRAMS[level]))
            self.assertLessEqual(B.detoughness(final), B.PF_CAP[level], level)
        self.assertEqual({'lv1': [10, 10], 'lv2': [25, 20], 'lv3': [50, 25]}, self.out['notes']['pf_detoughness'])

    def test_wave_p13_before_after(self):
        for level, waves, new, kind in ((2, 5, 4, int), (3, 10, 2.5, float)):
            program = B.PF_PROGRAMS[level]
            paths = p13_paths(self.tree(program))
            self.assertEqual(waves, len(paths))
            for path in paths:
                area = at(self.out['dsl'][program], path[:-5])
                self.assertEqual(('CreateHitArea', -18, ['EF'], ['CalculatedUsingMaxNumOfHits', 1]),
                                 (area[0], area[2], area[3], area[14]))
                self.assertEqual(slv(5), at(self.tree(program), path))
                self.assertEqual(slv(new), at(self.out['dsl'][program], path))
                self.assertIs(kind, type(at(self.out['dsl'][program], path)[0]['max']))

    def test_only_the_wave_p13_leaves_move(self):
        for program in (PF2, PF3):
            old, new = self.tree(program), self.out['dsl'][program]
            paths = p13_paths(old)
            self.assertEqual(sorted((*p, 0, side) for p in paths for side in ('min', 'max')),
                             sorted(leaf_diff(old, new)), program)
            restored = deepcopy(new)
            for p in paths:
                at(restored, p)[0] = deepcopy(at(old, p)[0])
            self.assertEqual(json.dumps(old), json.dumps(restored), program)

    def test_lv1_is_left_unchanged(self):
        self.assertEqual(json.dumps(self.tree(PF1)), json.dumps(B.revise_pf_tree(self.tree(PF1), 1)))

    # ---------------------------------------------------------------- 门禁

    def test_trees_pass_dsl_gates_and_roundtrip(self):
        for program, tree in self.out['dsl'].items():
            self.assertEqual([], B.dsl_problems(tree), program)
            self.assertEqual([], kit_dsl_problems(tree, element=None), program)
            rt = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))['tree']
            self.assertEqual(json.dumps(tree), json.dumps(rt), program)

    def test_panel_text_carries_no_numbers(self):
        text = self.context['cas']['override_string_mosiyike'][0][0]
        self.assertEqual([], panel_problems(text))
        self.assertFalse(any(ch.isdigit() for ch in text))

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
                value[0][-1] = value[0][-1] + 'x'
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
        for level in B.CHANGED_LEVELS:
            with self.assertRaisesRegex(ValueError, 'wind-blade preimage drift'):
                B.revise_pf_tree(self.out['dsl'][B.PF_PROGRAMS[level]], level)

    def test_structure_guards(self):
        with self.assertRaisesRegex(ValueError, 'wind-blade preimage drift'):
            B.revise_pf_tree(self.tree(PF2), 3)                       # 档位错配（5 发 vs 10 发）
        tree = deepcopy(self.tree(PF3))
        at(tree, p13_paths(tree)[4])[0] = {'min': 6, 'max': 6}
        with self.assertRaisesRegex(ValueError, 'wind-blade preimage drift'):
            B.revise_pf_tree(tree, 3)
        tree = deepcopy(self.tree(PF2))
        at(tree, p13_paths(tree)[0][:-5])[14] = ['CalculatedUsingMaxNumOfHits', 2]
        with self.assertRaisesRegex(ValueError, 'wind-blade preimage drift'):
            B.revise_pf_tree(tree, 2)
        tree = deepcopy(self.tree(PF2))
        tree[1] = 2
        with self.assertRaisesRegex(ValueError, 'root header drift'):
            B.revise_pf_tree(tree, 2)

    def test_revise_is_deterministic(self):
        again = B.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(self.out, sort_keys=True), json.dumps(again, sort_keys=True))

    # ---------------------------------------------------------------- 接口常量

    def test_module_contract_constants(self):
        self.assertEqual(('149997', 'mosiyike'), (B.CID, B.CODE))
        self.assertEqual(['mosiyike'], B.PACKAGES)
        self.assertEqual({'mosiyike': '0.1.1'}, B.PACKAGE_VERSION)
        self.assertEqual([], B.CAPABILITIES)
        self.assertEqual(29, len(B.REVIEWED_DRIFT))
        self.assertTrue(all(logical not in {wf_dsl.dsl_logical(p) for p in B.PF_PROGRAMS.values()}
                            for _, logical in B.REVIEWED_DRIFT))      # PF 树本身不在已审漂移里
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)

    # ---------------------------------------------------------------- 生成器 / 候选 / live（本机）

    @unittest.skipUnless((WORKSPACE / 'build_pf.py').is_file() and (ROOT / 'mod-tools/profiles.json').is_file()
                         and (ROOT / '弹国服/bundle.zip').is_file(), 'local workspace kit required')
    def test_generator_equals_revise_output(self):
        spec = importlib.util.spec_from_file_location('mosiyike_build_pf', WORKSPACE / 'build_pf.py')
        kit = importlib.util.module_from_spec(spec)
        saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        try:
            spec.loader.exec_module(kit)       # 只用纯函数 build_level，不调 main（main 会写包）
        finally:
            sys.dont_write_bytecode = saved
        self.assertEqual({1: 5, 2: 4, 3: 2.5}, kit.DETOUGHNESS)
        # 第三轮（wf_balance_20260927c_mosiyike）把生成器倍率同步为灰服 15/30/45，由 c 测试断言；
        # 这里用第二批时的倍率重建，核对第二批输出。
        kit.TOTALS = {1: 25.0, 2: 41.4, 3: 64.4}
        for level in B.PF_LEVELS:
            want = self.out['dsl'].get(B.PF_PROGRAMS[level], self.tree(B.PF_PROGRAMS[level]))
            self.assertEqual(json.dumps(want), json.dumps(kit.build_level(level)), level)

    @unittest.skipUnless((WORKSPACE / 'package/manifest.json').is_file()
                         and (ROOT / 'mod-tools/profiles.json').is_file(),
                         'local candidate workspace required')
    def test_candidate_opens_with_reviewed_drift_and_splices_dry(self):
        from wf_character_revision import RevisionCandidate
        manifest = WORKSPACE / 'package/manifest.json'
        before = manifest.read_bytes()
        meta = json.loads(before)
        candidate = RevisionCandidate(ROOT, WORKSPACE, reviewed_input_drift=B.REVIEWED_DRIFT,
                                      character_id=B.CID, code_name=B.CODE,
                                      snapshot_key='revision_20260927b',
                                      package_version=B.PACKAGE_VERSION[B.PACKAGES[0]],
                                      baseline_factory=lambda *a, **k: None)
        with self.assertRaisesRegex(ValueError, 'candidate drift'):
            RevisionCandidate(ROOT, WORKSPACE, character_id=B.CID, code_name=B.CODE,
                              snapshot_key='probe', package_version='0.0.0',
                              baseline_factory=lambda *a, **k: None)

        def tree_in_candidate(program):
            raw = candidate.read('common', wf_dsl.dsl_logical(program))
            return wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']

        if meta['snapshot'].get('revision_20260927b') is not None:
            # 主会话暂存回写之后：候选 PF 树 = 本模块输出，Lv1 不变。
            # 作者 09-27 用灰服版替换本角色（wf_balance_20260927b_gray3，同一 snapshot 键）会把候选再升一版；
            # 本模块改的树不在灰服压缩包里，候选里仍是本模块输出。
            self.assertIn(meta['package_version'],
                          {B.PACKAGE_VERSION[B.PACKAGES[0]], G3.SPECS['149997']['version']['mosiyike'],
                           C3.PACKAGE_VERSION[C3.PACKAGES[0]]})
            if {p: B.digest(tree_in_candidate(p)) for p in (PF1, PF2, PF3)} == C3.AFTER:
                return      # 第三轮 wf_balance_20260927c_mosiyike（灰服倍率）回写后；精确相等由其测试断言
            for program, tree in self.out['dsl'].items():
                self.assertEqual(json.dumps(tree), json.dumps(tree_in_candidate(program)), program)
            self.assertEqual(json.dumps(self.tree(PF1)), json.dumps(tree_in_candidate(PF1)))
            return
        self.assertLess(tuple(map(int, meta['package_version'].split('.'))),
                        tuple(map(int, B.PACKAGE_VERSION[B.PACKAGES[0]].split('.'))))
        for program in (PF1, PF2, PF3):
            self.assertEqual(json.dumps(self.tree(program)), json.dumps(tree_in_candidate(program)), program)
        for program, tree in self.out['dsl'].items():
            candidate.emit('common', wf_dsl.dsl_logical(program), encode_tree(tree))
        evidence = candidate.finish({'dry_run': True}, apply=False)
        self.assertFalse(evidence['applied'])
        changed = {item['logical_path']: item['before_sha256'] for item in evidence['changed_files']}
        self.assertEqual({wf_dsl.dsl_logical(p): self.raw_sha[p] for p in self.out['dsl']}, changed)
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
            self.assertIn(B.digest(live), {B.BEFORE['dsl', program], B.digest(tree), C3.AFTER[program]}, program)


if __name__ == '__main__':
    unittest.main()
