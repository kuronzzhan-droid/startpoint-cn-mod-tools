"""克劳斯 129997 2026-09-27 第二批：PF 爪击削韧 9/27/46 → 9/19.8/25（顶到 ≤15/20/25）。"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)
import wf_balance_20260927b_klaus as B
import wf_dsl
from wf_character_revision import encode_tree
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems
from wf_midautumn_kitlib import panel_problems

FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_klaus.json'
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


def rework_output():
    """作者 09-27 小重做（wf_balance_20260927b_claus_rework，在本批 1.4.1051 之上）又改了 PF 三档：
    live 与候选在它暂存/发布后是它的输出，而不是本模块的输出。按它的夹具重算，供本机断言放行。"""
    import wf_balance_20260927b_claus_rework as R
    data = json.loads((Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_claus_rework.json').read_bytes())
    inputs = data['inputs']
    return R, R.revise(lambda kind, key: inputs[kind]['|'.join(key) if kind == 'table' else key])


class KlausBatch2Test(unittest.TestCase):
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
        self.assertEqual([('claude_wolf_assassin_ex_pf', '1,2,3')],
                         [(r[80], r[81]) for r in leader if r[45] == '722'])
        self.assertEqual([[PF1, PF2, PF3]], self.inputs['table'][
            'master/skill/power_flip_action.orderedmap|claude_wolf_assassin_ex_pf'])

    def test_only_lv2_and_lv3_are_returned(self):
        self.assertEqual({'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl',
                          'server_text', 'new_programs', 'notes'}, set(self.out))
        for kind in ('ability', 'leader', 'cas', 'text', 'table', 'action', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)     # 队长行8 每次 PF 水队充能（充能，本批不动）
        self.assertEqual({PF2, PF3}, set(self.out['dsl']))
        self.assertEqual([], self.out['new_programs'])

    # ---------------------------------------------------------------- 强化弹射（B.2）

    def test_pf_detoughness_9_19_8_25(self):
        self.assertEqual(9, B.detoughness(self.tree(PF1)))
        for program, before, after in ((PF2, 27, 19.8), (PF3, 46, 25)):
            self.assertEqual(before, B.detoughness(self.tree(program)), program)
            self.assertEqual(after, B.detoughness(self.out['dsl'][program]), program)
        for level in B.PF_LEVELS:
            final = self.out['dsl'].get(B.PF_PROGRAMS[level], self.tree(B.PF_PROGRAMS[level]))
            self.assertLessEqual(B.detoughness(final), B.PF_CAP[level], level)
        # Lv2 9 段同一 p13：正好 20 需要 20/9，一位小数最多 2.2（19.8）；2.3 会超上限。
        self.assertGreater(9 * 2.3, B.PF_CAP[2])
        self.assertEqual({'lv1': [9, 9], 'lv2': [27, 19.8], 'lv3': [46, 25]}, self.out['notes']['pf_detoughness'])

    def test_claw_p13_before_after(self):
        for level, claws, new in ((2, 3, 2.2), (3, 5, 1.6)):
            program = B.PF_PROGRAMS[level]
            paths = p13_paths(self.tree(program))
            claw_paths = paths[1:] if level == 3 else paths
            self.assertEqual(claws, len(claw_paths))
            for path in claw_paths:
                area = at(self.out['dsl'][program], path[:-5])
                self.assertEqual(('CreateHitArea', -18, ['EF'], ['CalculatedUsingMaxNumOfHits', 3]),
                                 (area[0], area[2], area[3], area[14]))
                self.assertEqual(slv(3), at(self.tree(program), path))
                self.assertEqual(slv(new), at(self.out['dsl'][program], path))
                self.assertIs(float, type(at(self.out['dsl'][program], path)[0]['max']))
                on_hit = [c[1][0] for c in area[23][1]]
                self.assertEqual(['CreateNormalAttack', 'ShakeCamera', 'CreateCondition'], on_hit)  # 毒不动
        opener = p13_paths(self.tree(PF3))[0]
        area = at(self.out['dsl'][PF3], opener[:-5])
        self.assertEqual((-1, ['AB'], ['CalculatedUsingMaxNumOfHits', 1]), (area[2], area[3], area[14]))
        self.assertEqual(slv(1), at(self.out['dsl'][PF3], opener))

    def test_only_the_claw_p13_leaves_move(self):
        for level in (2, 3):
            program = B.PF_PROGRAMS[level]
            old, new = self.tree(program), self.out['dsl'][program]
            paths = p13_paths(old)[1:] if level == 3 else p13_paths(old)
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
            # 包内 kit 门禁：p13 改值不新增问题（CreateCondition p4 为 int、串联爪 bound id 重复是 live 既有）。
            self.assertEqual(kit_dsl_problems(self.tree(program), element=None),
                             kit_dsl_problems(tree, element=None), program)
            rt = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))['tree']
            self.assertEqual(json.dumps(tree), json.dumps(rt), program)

    def test_panel_text_carries_no_numbers(self):
        text = self.context['cas']['override_string_claude_wolf_assassin_ex'][0][0]
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
        for level in (2, 3):
            with self.assertRaisesRegex(ValueError, 'detoughness preimage'):
                B.revise_pf_tree(self.out['dsl'][B.PF_PROGRAMS[level]], level)

    def test_structure_guards(self):
        with self.assertRaisesRegex(ValueError, 'detoughness preimage'):
            B.revise_pf_tree(self.tree(PF2), 3)                       # 档位错配
        tree = deepcopy(self.tree(PF3))
        at(tree, p13_paths(tree)[0])[0] = {'min': 0, 'max': 0}        # 开头判定区 1→0：总量 45 ≠ 46
        with self.assertRaisesRegex(ValueError, 'detoughness preimage'):
            B.revise_pf_tree(tree, 3)
        tree = deepcopy(self.tree(PF3))
        at(tree, p13_paths(tree)[0][:-5])[2] = -2                     # 总量不变、开头判定区锚点变了
        with self.assertRaisesRegex(ValueError, 'claw preimage drift'):
            B.revise_pf_tree(tree, 3)
        tree = deepcopy(self.tree(PF2))
        tree[1] = 2
        with self.assertRaisesRegex(ValueError, 'root header drift'):
            B.revise_pf_tree(tree, 2)

    def test_revise_is_deterministic(self):
        again = B.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(self.out, sort_keys=True), json.dumps(again, sort_keys=True))

    # ---------------------------------------------------------------- 接口常量

    def test_module_contract_constants(self):
        self.assertEqual(('129997', 'claude_wolf_assassin_ex'), (B.CID, B.CODE))
        self.assertEqual(['claude_wolf_assassin_ex'], B.PACKAGES)
        self.assertEqual({'claude_wolf_assassin_ex': '0.1.1'}, B.PACKAGE_VERSION)
        self.assertEqual([], B.CAPABILITIES)
        self.assertEqual(2, len(B.REVIEWED_DRIFT))
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)

    # ---------------------------------------------------------------- 候选 / live（本机）

    @unittest.skipUnless((WORKSPACE / 'package/manifest.json').is_file()
                         and (ROOT / 'mod-tools/profiles.json').is_file(),
                         'local candidate workspace required')
    def test_candidate_opens_with_reviewed_drift_and_splices_dry(self):
        from wf_character_revision import RevisionCandidate
        manifest = WORKSPACE / 'package/manifest.json'
        before = manifest.read_bytes()
        meta = json.loads(before)
        R, rework = rework_output()
        if meta['package_version'] == R.PACKAGE_VERSION[R.PACKAGES[0]]:
            # 作者 09-27 小重做已回写候选：技能两档 DSL 已重封（无既有漂移），PF 三档是小重做的输出。
            candidate = RevisionCandidate(ROOT, WORKSPACE, reviewed_input_drift={},
                                          character_id=B.CID, code_name=B.CODE,
                                          snapshot_key='revision_20260927b',
                                          package_version=R.PACKAGE_VERSION[R.PACKAGES[0]],
                                          baseline_factory=lambda *a, **k: None)
            for program in (PF1, PF2, PF3):
                raw = candidate.read('common', wf_dsl.dsl_logical(program))
                tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']
                self.assertEqual(json.dumps(rework['dsl'][program]), json.dumps(tree), program)
            self.assertEqual(before, manifest.read_bytes())
            return
        candidate = RevisionCandidate(ROOT, WORKSPACE, reviewed_input_drift=B.REVIEWED_DRIFT,
                                      character_id=B.CID, code_name=B.CODE,
                                      snapshot_key='revision_20260927b',
                                      package_version=B.PACKAGE_VERSION[B.PACKAGES[0]],
                                      baseline_factory=lambda *a, **k: None)

        def tree_in_candidate(program):
            raw = candidate.read('common', wf_dsl.dsl_logical(program))
            return wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']

        if meta['snapshot'].get('revision_20260927b') is not None:
            # 已回写：Lv2/Lv3 作为新 root 条目进了候选且等于 revise() 输出；Lv1 本批不动、从未进包
            # （候选只认领 power_flip_action 表），仍只在 live —— 不能从候选读它。
            self.assertEqual(B.PACKAGE_VERSION[B.PACKAGES[0]], meta['package_version'])
            for program, tree in self.out['dsl'].items():
                self.assertIn(('common', wf_dsl.dsl_logical(program)), candidate.original, program)
                self.assertEqual(json.dumps(tree), json.dumps(tree_in_candidate(program)), program)
            self.assertNotIn(('common', wf_dsl.dsl_logical(PF1)), candidate.original)
            self.assertIn(('common', 'master/skill/power_flip_action.orderedmap'), candidate.original)
            self.assertEqual(before, manifest.read_bytes())
            return
        self.assertLess(tuple(map(int, meta['package_version'].split('.'))),
                        tuple(map(int, B.PACKAGE_VERSION[B.PACKAGES[0]].split('.'))))
        # 候选只认领 power_flip_action 表，PF 三档 DSL 从未进包（build_claw_pf 等直写 live）：
        # 暂存回写会把 Lv2/Lv3 作为新 root 条目加进候选（before_sha256=None），Lv1 仍只在 live。
        self.assertIn(('common', 'master/skill/power_flip_action.orderedmap'), candidate.original)
        for program in (PF1, PF2, PF3):
            self.assertNotIn(('common', wf_dsl.dsl_logical(program)), candidate.original, program)
        for program, tree in self.out['dsl'].items():
            candidate.emit('common', wf_dsl.dsl_logical(program), encode_tree(tree))
        evidence = candidate.finish({'dry_run': True}, apply=False)
        self.assertFalse(evidence['applied'])
        changed = {item['logical_path']: item['before_sha256'] for item in evidence['changed_files']}
        self.assertEqual({wf_dsl.dsl_logical(p): None for p in self.out['dsl']}, changed)
        roots = {entry['logical_path'] for entry in candidate.manifest['roots']['common']}
        self.assertLessEqual({wf_dsl.dsl_logical(p) for p in self.out['dsl']}, roots)
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
            # 作者 09-27 小重做发布后，live 是 wf_balance_20260927b_claus_rework 的输出。
            allowed = {B.BEFORE['dsl', program], B.digest(tree), B.digest(rework_output()[1]['dsl'][program])}
            self.assertIn(B.digest(live), allowed, program)


if __name__ == '__main__':
    unittest.main()
