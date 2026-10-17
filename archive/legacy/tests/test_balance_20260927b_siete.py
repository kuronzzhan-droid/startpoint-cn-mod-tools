"""希耶提 149995 2026-09-27 第二批：629「剑界回响」削韧 10→1（5 刃 p13 2.0→0.2；友技触发无间隔保证 ⇒ ≤1）。"""
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
import wf_balance_20260927b_siete as B
import wf_balance_20260927b_gray3 as G3
import wf_balance_20260927c_seofonart as SEOFONART
import wf_client_legality as legality
import wf_dsl
from wf_character_revision import encode_tree
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems
from wf_midautumn_kitlib import panel_problems

FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_siete.json'
WORKSPACE = ROOT / 'work/character_packs' / B.PACKAGES[0]
GENERATOR = WORKSPACE / 'seofon_dsl.py'
ECHO = B.ECHO_PROGRAM
#: 5 刃：RP → Wait(10/15/20/25/30) → Wait 10 → CreateHitArea onHit 第 2 条（ShakeCamera 之后）的 p13。
P13_PATHS = [[11, 1, 1, 1, 11, 1, k, 1, 3, 1, 1, 1, 3, 1, 0, 1, 23, 1, 1, 1, 13] for k in range(5)]


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


def p13_leaves():
    return [(*p, 0, side) for p in P13_PATHS for side in ('min', 'max')]


class SieteBatch2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(FIXTURE.read_bytes())
        cls.inputs, cls.raw_sha, cls.context = data['inputs'], data['dsl_raw_sha256'], data['context']
        cls.out = B.revise(cls.read_from(cls.inputs))

    @staticmethod
    def read_from(inputs):
        return lambda kind, key: inputs[kind][_key(kind, key)]

    def tree(self):
        return self.inputs['dsl'][ECHO]

    def invoke_row(self):
        return self.inputs['ability'][B.INVOKE_KEY][B.INVOKE_ROW]

    # ---------------------------------------------------------------- 基线与输出形状

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(2, len(B.BEFORE))
        for (kind, key), want in B.BEFORE.items():
            self.assertEqual(want, B.digest(self.inputs[kind][_key(kind, key)]), (kind, key))

    def test_only_the_echo_tree_is_returned(self):
        self.assertEqual({'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl',
                          'server_text', 'new_programs', 'notes'}, set(self.out))
        for kind in ('ability', 'leader', 'cas', 'text', 'table', 'action', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)
        self.assertEqual({ECHO}, set(self.out['dsl']))
        self.assertEqual([], self.out['new_programs'])

    # ---------------------------------------------------------------- 改动前后值

    def test_echo_detoughness_10_to_1(self):
        old, new = self.tree(), self.out['dsl'][ECHO]
        self.assertEqual(10, B.detoughness(old))
        self.assertEqual(1, B.detoughness(new))
        for path in P13_PATHS:
            self.assertEqual([{'min': 2.0, 'max': 2.0}], at(old, path))
            self.assertEqual([{'min': 0.2, 'max': 0.2}], at(new, path))
            area = at(new, path[:-5])
            self.assertEqual(('CreateHitArea', 9, ['AB'], ['CalculatedUsingMaxNumOfHits', 1], 0),
                             (area[0], area[2], area[3], area[14], area[24]))
        self.assertEqual([10.0, 1.0], self.out['notes']['echo']['detoughness'])

    def test_only_the_five_p13_leaves_move(self):
        old, new = self.tree(), self.out['dsl'][ECHO]
        self.assertEqual(p13_leaves(), leaf_diff(old, new))
        restored = deepcopy(new)
        for path in P13_PATHS:
            at(restored, path)[0] = deepcopy(at(old, path)[0])
        self.assertEqual(json.dumps(old), json.dumps(restored))
        for path in P13_PATHS:
            attack = at(new, path[:-1])
            self.assertEqual([{'min': 20.0, 'max': 20.0}], attack[6])  # 每刃倍率不动
            self.assertIs(float, type(at(new, path)[0]['max']))       # 原值 2.0 是 float，新值同型

    def test_invoke_trigger_is_any_other_member_skill_without_ct(self):
        row = self.invoke_row()
        self.assertEqual(('629', ECHO, 'ability_skill_seofon_wind_echo'), (row[47], row[71], row[70]))
        self.assertEqual(('23', '4', '(None)', '100000', '(None)', '0'),
                         (row[27], row[28], row[29], row[30], row[34], row[35]))
        self.assertEqual(1, B.invoke_cap(row))
        self.assertEqual(1, self.out['notes']['echo']['per_call_cap'])
        self.assertLessEqual(B.detoughness(self.out['dsl'][ECHO]), 1)

    def test_invoke_row_drift_forces_a_ct_recheck(self):
        for col, value in ((35, '600'), (28, '0'), (27, '20'), (34, '10'), (29, 'Green'),
                           (71, 'battle/action/skill/action/ability_skill/other$other')):
            row = deepcopy(self.invoke_row())
            row[col] = value
            with self.assertRaisesRegex(ValueError, 're-check CT rule'):
                B.invoke_cap(row)

    def test_design_value_2_5_would_exceed_the_fast_cap(self):
        # 设计稿 2→0.5（10→2.5）只满足「每次 ≤3」；本触发按 CT 核对是 ≤1。
        tree = deepcopy(self.tree())
        for path in P13_PATHS:
            at(tree, path)[0] = {'min': 0.5, 'max': 0.5}
        self.assertEqual(2.5, B.detoughness(tree))
        self.assertGreater(B.detoughness(tree), B.INVOKE_CAP_FAST)

    # ---------------------------------------------------------------- 门禁

    def test_tree_passes_dsl_gates_and_roundtrip(self):
        tree = self.out['dsl'][ECHO]
        self.assertEqual([], B.dsl_problems(tree))
        self.assertEqual([], kit_dsl_problems(tree, element=None))
        self.assertEqual([], legality.action_dsl_element_problems(tree, 3))
        rt = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))['tree']
        self.assertEqual(json.dumps(tree), json.dumps(rt))

    def test_unchanged_invoke_row_stays_legal(self):
        cas_keys = set(self.context['cas'])
        row = self.invoke_row()
        self.assertEqual([], legality.client_legality_problems('ability', row))
        self.assertEqual([], legality.declared_block_field_problems('ability', row))
        self.assertEqual([], legality.invoke_skill_string_problems(row, cas_keys, 'ability'))

    def test_panel_text_carries_no_detoughness_numbers(self):
        text = self.context['cas']['ability_skill_seofon_wind_echo'][0][0]
        self.assertEqual('发动技能「剑界回响」', text)
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

    def test_output_is_detached_from_inputs(self):
        out = B.revise(self.read_from(self.inputs))
        at(out['dsl'][ECHO], P13_PATHS[0])[0]['max'] = 99
        self.assertEqual([{'min': 2.0, 'max': 2.0}], at(self.tree(), P13_PATHS[0]))

    def test_own_output_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live['dsl'].update(deepcopy(self.out['dsl']))
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            B.revise(self.read_from(live))
        with self.assertRaisesRegex(ValueError, 'p13 preimage drift'):
            B.revise_echo_tree(self.out['dsl'][ECHO])

    def test_structure_guards(self):
        tree = deepcopy(self.tree())
        at(tree, P13_PATHS[2][:-5])[14] = ['CalculatedUsingMaxNumOfHits', 2]
        with self.assertRaisesRegex(ValueError, 'blade 3: hit area drift'):
            B.revise_echo_tree(tree)
        tree = deepcopy(self.tree())
        at(tree, P13_PATHS[4][:-1])[6] = [{'min': 25.0, 'max': 25.0}]
        with self.assertRaisesRegex(ValueError, 'blade 5: CreateNormalAttack'):
            B.revise_echo_tree(tree)
        tree = deepcopy(self.tree())
        del at(tree, [11, 1, 1, 1, 11, 1])[4]                        # 少一刃
        with self.assertRaisesRegex(ValueError, 'must hold 5 blades'):
            B.revise_echo_tree(tree)
        tree = deepcopy(self.tree())
        tree[1] = 1
        with self.assertRaisesRegex(ValueError, 'root header'):
            B.revise_echo_tree(tree)

    def test_revise_is_deterministic(self):
        again = B.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(self.out, sort_keys=True), json.dumps(again, sort_keys=True))

    # ---------------------------------------------------------------- 接口常量

    def test_module_contract_constants(self):
        self.assertEqual(('149995', 'seofon_wind'), (B.CID, B.CODE))
        self.assertEqual(['seofon_wind'], B.PACKAGES)
        self.assertEqual({'seofon_wind': '1.0.2'}, B.PACKAGE_VERSION)
        self.assertEqual([], B.CAPABILITIES)
        self.assertEqual({}, B.REVIEWED_DRIFT)
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)

    # ---------------------------------------------------------------- 生成器 / 候选 / live（本机）

    @unittest.skipUnless(GENERATOR.is_file() and (WORKSPACE / 'source_refs').is_dir(),
                         'package kit source required')
    def test_generator_differs_only_by_the_pending_p13_constant(self):
        """包内 seofon_dsl.build_ability_skill_tree()（纯函数）：未同步时只差 5 处 p13（=改前 2.0），同步后逐字相同。"""
        spec = importlib.util.spec_from_file_location('seofon_dsl_b2_probe', GENERATOR)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        generated = module.build_ability_skill_tree()
        diff = leaf_diff(generated, self.out['dsl'][ECHO])
        if diff:
            self.assertEqual(p13_leaves(), diff)
            self.assertEqual(json.dumps(self.tree()), json.dumps(generated))   # 未同步 == 改前 live
        else:
            self.assertEqual(json.dumps(self.out['dsl'][ECHO]), json.dumps(generated))

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
        logical = wf_dsl.dsl_logical(ECHO)
        in_candidate = wf_dsl.parse_dsl(zlib.decompress(candidate.read('common', logical), -15))['tree']
        if meta['snapshot'].get('revision_20260927b') is not None:
            # 作者 09-27 用灰服版替换本角色（wf_balance_20260927b_gray3，同一 snapshot 键）会把候选再升一版；
            # 作者 09-27 又接受灰版美术（wf_balance_20260927c_seofonart，1.0.3 → 1.0.4）。
            # 本模块改的树不在灰服压缩包里、也不是美术，候选里仍是本模块输出。
            self.assertIn(meta['package_version'],
                          {B.PACKAGE_VERSION[B.PACKAGES[0]], G3.SPECS['149995']['version']['seofon_wind'],
                           SEOFONART.PACKAGE_VERSION['seofon_wind']})
            self.assertEqual(json.dumps(self.out['dsl'][ECHO]), json.dumps(in_candidate))
            return
        self.assertLess(tuple(map(int, meta['package_version'].split('.'))),
                        tuple(map(int, B.PACKAGE_VERSION[B.PACKAGES[0]].split('.'))))
        self.assertEqual(json.dumps(self.tree()), json.dumps(in_candidate))
        candidate.emit('common', logical, encode_tree(self.out['dsl'][ECHO]))
        evidence = candidate.finish({'dry_run': True}, apply=False)
        self.assertFalse(evidence['applied'])
        changed = {item['logical_path']: item['before_sha256'] for item in evidence['changed_files']}
        self.assertEqual({logical: self.raw_sha[ECHO]}, changed)
        self.assertEqual(before, manifest.read_bytes())

    @unittest.skipUnless((ROOT / 'mod-tools/profiles.json').is_file(), 'local live store required')
    def test_live_is_either_the_baseline_or_this_output(self):
        import wf_mod_tool as core
        store = Path(core.resolve_active_store())
        path = core.table_path(store, wf_dsl.dsl_logical(ECHO))
        if not path.is_file():
            self.skipTest('live store DSL not present')
        live = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))['tree']
        self.assertIn(B.digest(live), {B.BEFORE['dsl', ECHO], B.digest(self.out['dsl'][ECHO])})


if __name__ == '__main__':
    unittest.main()
