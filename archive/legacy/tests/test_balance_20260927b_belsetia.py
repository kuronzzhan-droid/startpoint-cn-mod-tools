"""贝尔赛蒂亚 129952 2026-09-27 第二批：629「宙域穿刺」削韧 8→2（p13 1→0.25）。"""
import ast
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)
import wf_balance_20260927b_belsetia as B
import wf_client_legality as legality
import wf_dsl
from wf_character_revision import encode_tree
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems
from wf_midautumn_kitlib import panel_problems

FIXTURE = Path(__file__).parent / 'fixtures/balance_20260927b_belsetia.json'
WORKSPACE = ROOT / 'work/character_packs' / B.PACKAGES[0]
GENERATOR = WORKSPACE / 'build_workspace.py'
PIERCE = B.PIERCE_PROGRAM
#: 穿刺树唯一 CreateNormalAttack 的 p13（FindNear → RP → Wait 4 → CreateHitArea onHit）。
P13_PATH = [11, 1, 1, 1, 6, 1, 0, 1, 11, 1, 1, 1, 3, 1, 0, 1, 23, 1, 0, 1, 13]


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


def generator_p13():
    """包内 kit build_ability_skill_tree(which == 1) 里穿刺 CreateNormalAttack 的 p13 字面量 ``_mm(a, b)``。

    不 import 该脚本（它顶层 import wf_gui，会起后台线程）；用 AST 只读源码常量。
    """
    tree = ast.parse(GENERATOR.read_text(encoding='utf-8'))
    func, = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'build_ability_skill_tree']
    found = []
    for node in ast.walk(func):
        if (isinstance(node, ast.List) and len(node.elts) == 17
                and isinstance(node.elts[0], ast.Constant) and node.elts[0].value == 'CreateNormalAttack'
                and isinstance(node.elts[1], ast.Constant) and node.elts[1].value == 4):
            call = node.elts[13]
            if not (isinstance(call, ast.Call) and getattr(call.func, 'id', None) == '_mm'):
                raise AssertionError('generator p13 is not an _mm(...) literal')
            found.append(tuple(ast.literal_eval(arg) for arg in call.args))
    return found


class BelsetiaBatch2Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(FIXTURE.read_bytes())
        cls.inputs, cls.raw_sha, cls.context = data['inputs'], data['dsl_raw_sha256'], data['context']
        cls.out = B.revise(cls.read_from(cls.inputs))

    @staticmethod
    def read_from(inputs):
        return lambda kind, key: inputs[kind][_key(kind, key)]

    def tree(self):
        return self.inputs['dsl'][PIERCE]

    def invoke_row(self):
        return self.inputs['ability'][B.INVOKE_KEY][B.INVOKE_ROW]

    # ---------------------------------------------------------------- 基线与输出形状

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(2, len(B.BEFORE))
        for (kind, key), want in B.BEFORE.items():
            self.assertEqual(want, B.digest(self.inputs[kind][_key(kind, key)]), (kind, key))

    def test_only_the_pierce_tree_is_returned(self):
        self.assertEqual({'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl',
                          'server_text', 'new_programs', 'notes'}, set(self.out))
        for kind in ('ability', 'leader', 'cas', 'text', 'table', 'action', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)
        self.assertEqual({PIERCE}, set(self.out['dsl']))
        self.assertEqual([], self.out['new_programs'])  # 穿刺树已在候选里

    # ---------------------------------------------------------------- 改动前后值

    def test_pierce_detoughness_8_to_2(self):
        old, new = self.tree(), self.out['dsl'][PIERCE]
        self.assertEqual(8, B.detoughness(old))
        self.assertEqual(2, B.detoughness(new))
        self.assertEqual([{'min': 1, 'max': 1}], at(old, P13_PATH))
        self.assertEqual([{'min': 0.25, 'max': 0.25}], at(new, P13_PATH))
        area = at(new, P13_PATH[:-5])
        self.assertEqual(('CreateHitArea', 1, ['GH', 0], ['CalculatedUsingMaxNumOfHits', 8], 4),
                         (area[0], area[2], area[3], area[14], area[24]))
        self.assertEqual([8.0, 2.0], self.out['notes']['pierce']['detoughness'])

    def test_only_the_p13_leaf_moves(self):
        old, new = self.tree(), self.out['dsl'][PIERCE]
        self.assertEqual([(*P13_PATH, 0, 'min'), (*P13_PATH, 0, 'max')], leaf_diff(old, new))
        restored = deepcopy(new)
        at(restored, P13_PATH)[0] = deepcopy(at(old, P13_PATH)[0])
        self.assertEqual(json.dumps(old), json.dumps(restored))
        attack = at(new, P13_PATH[:-1])
        self.assertEqual([{'min': 1.8, 'max': 2.5}], attack[6])       # 倍率不动
        self.assertEqual([{'min': 1.25, 'max': 1.25}], attack[14])    # 硬直不动
        self.assertIs(float, type(at(new, P13_PATH)[0]['max']))

    def test_invoke_row_is_untouched_and_over_3_seconds_by_event(self):
        row = self.invoke_row()
        self.assertEqual(('629', PIERCE, 'ability_skill_witch_ex_pierce'), (row[47], row[71], row[70]))
        self.assertEqual(('2', '', '300000', '300000', '10', '0'),
                         (row[27], row[28], row[30], row[31], row[34], row[35]))
        self.assertEqual(3, B.invoke_cap(row))
        self.assertEqual(3, self.out['notes']['pierce']['per_call_cap'])
        self.assertLessEqual(B.detoughness(self.out['dsl'][PIERCE]), 3)
        self.assertEqual('false', row[1])                              # 整键主位，行不改

    def test_invoke_row_drift_forces_a_ct_recheck(self):
        for col, value in ((35, '120'), (27, '23'), (30, '100000'), (34, '(None)'), (28, '4'),
                           (71, 'battle/action/skill/action/ability_skill/other$other')):
            row = deepcopy(self.invoke_row())
            row[col] = value
            with self.assertRaisesRegex(ValueError, 're-check CT rule'):
                B.invoke_cap(row)

    def test_fast_cap_would_reject_the_pierce_value(self):
        with self.assertRaisesRegex(ValueError, r'pierce detoughness 2\.0 > 629 cap 1'):
            B.revise_pierce_tree(self.tree(), B.INVOKE_CAP_FAST)

    # ---------------------------------------------------------------- 门禁

    def test_tree_passes_dsl_gates_and_roundtrip(self):
        tree = self.out['dsl'][PIERCE]
        self.assertEqual([], B.dsl_problems(tree))
        self.assertEqual([], kit_dsl_problems(tree, element=None))
        self.assertEqual([], legality.action_dsl_element_problems(tree, 1))
        rt = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))['tree']
        self.assertEqual(json.dumps(tree), json.dumps(rt))  # 连 int/float 一起往返

    def test_unchanged_invoke_row_stays_legal(self):
        cas_keys = set(self.context['cas'])
        row = self.invoke_row()
        self.assertEqual([], legality.client_legality_problems('ability', row))
        self.assertEqual([], legality.declared_block_field_problems('ability', row))
        self.assertEqual([], legality.invoke_skill_string_problems(row, cas_keys, 'ability'))

    def test_panel_text_carries_no_detoughness_numbers(self):
        text = self.context['cas']['ability_skill_witch_ex_pierce'][0][0]
        self.assertEqual([], panel_problems(text))
        self.assertFalse(any(ch.isdigit() for ch in text))
        for word in ('虚弱', '削韧', '眩晕', '击破'):
            self.assertNotIn(word, text)

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
        at(out['dsl'][PIERCE], P13_PATH)[0]['max'] = 99
        self.assertEqual([{'min': 1, 'max': 1}], at(self.tree(), P13_PATH))

    def test_own_output_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live['dsl'].update(deepcopy(self.out['dsl']))
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            B.revise(self.read_from(live))
        with self.assertRaisesRegex(ValueError, 'pierce p13 preimage drift'):
            B.revise_pierce_tree(self.out['dsl'][PIERCE])

    def test_structure_guards(self):
        tree = deepcopy(self.tree())
        at(tree, P13_PATH[:-5])[14] = ['CalculatedUsingMaxNumOfHits', 9]
        with self.assertRaisesRegex(ValueError, 'pierce hit area drift'):
            B.revise_pierce_tree(tree)
        tree = deepcopy(self.tree())
        tree[0] = 'ActionDslX'
        with self.assertRaisesRegex(ValueError, 'root header'):
            B.revise_pierce_tree(tree)
        tree = deepcopy(self.tree())
        at(tree, P13_PATH)[0] = {'min': 1, 'max': 2}
        with self.assertRaisesRegex(ValueError, 'p13'):
            B.revise_pierce_tree(tree)
        tree = deepcopy(self.tree())
        onhit = at(tree, P13_PATH[:-3])                              # onHit 的 Block 子列表
        onhit.append(deepcopy(onhit[0]))
        with self.assertRaisesRegex(ValueError, 'one CreateNormalAttack'):
            B.revise_pierce_tree(tree)

    def test_revise_is_deterministic(self):
        again = B.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(self.out, sort_keys=True), json.dumps(again, sort_keys=True))

    # ---------------------------------------------------------------- 接口常量

    def test_module_contract_constants(self):
        self.assertEqual(('129952', 'dimension_witch_smr20_ex'), (B.CID, B.CODE))
        self.assertEqual(['thunder_witch_ex'], B.PACKAGES)
        self.assertEqual({'thunder_witch_ex': '0.1.1'}, B.PACKAGE_VERSION)
        self.assertEqual([], B.CAPABILITIES)
        self.assertEqual({}, B.REVIEWED_DRIFT)
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)

    # ---------------------------------------------------------------- 生成器 / 候选 / live（本机）

    @unittest.skipUnless(GENERATOR.is_file(), 'package kit source required')
    def test_generator_differs_only_by_the_pending_p13_constant(self):
        """包内 kit 的穿刺 p13 常量：未同步 = (1, 1)（needed_edits_elsewhere 待办），同步后 = 本模块值。"""
        found = generator_p13()
        self.assertEqual(1, len(found), found)
        self.assertIn(found[0], {(1, 1), (0.25, 0.25)})
        if found[0] == (0.25, 0.25):
            self.assertEqual([{'min': 0.25, 'max': 0.25}], at(self.out['dsl'][PIERCE], P13_PATH))

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
        logical = wf_dsl.dsl_logical(PIERCE)
        in_candidate = wf_dsl.parse_dsl(zlib.decompress(candidate.read('common', logical), -15))['tree']
        if meta['snapshot'].get('revision_20260927b') is not None:
            # 主会话暂存回写之后：候选穿刺树 = 本模块输出。
            # 作者 09-27 小重做（wf_balance_20260927b_witch_move：环爆移到能力3、能力4/6 去主位；只改 ability 表）
            # 会在同一候选上再升一版（0.1.2）且不碰穿刺树 ⇒ 版本号只要求不低于第二批。
            self.assertGreaterEqual(tuple(map(int, meta['package_version'].split('.'))),
                                    tuple(map(int, B.PACKAGE_VERSION[B.PACKAGES[0]].split('.'))))
            self.assertEqual(json.dumps(self.out['dsl'][PIERCE]), json.dumps(in_candidate))
            return
        self.assertLess(tuple(map(int, meta['package_version'].split('.'))),
                        tuple(map(int, B.PACKAGE_VERSION[B.PACKAGES[0]].split('.'))))
        self.assertEqual(json.dumps(self.tree()), json.dumps(in_candidate))
        candidate.emit('common', logical, encode_tree(self.out['dsl'][PIERCE]))
        evidence = candidate.finish({'dry_run': True}, apply=False)
        self.assertFalse(evidence['applied'])
        changed = {item['logical_path']: item['before_sha256'] for item in evidence['changed_files']}
        self.assertEqual({logical: self.raw_sha[PIERCE]}, changed)
        self.assertEqual(before, manifest.read_bytes())

    @unittest.skipUnless((ROOT / 'mod-tools/profiles.json').is_file(), 'local live store required')
    def test_live_is_either_the_baseline_or_this_output(self):
        import wf_mod_tool as core
        store = Path(core.resolve_active_store())
        path = core.table_path(store, wf_dsl.dsl_logical(PIERCE))
        if not path.is_file():
            self.skipTest('live store DSL not present')
        live = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))['tree']
        self.assertIn(B.digest(live), {B.BEFORE['dsl', PIERCE], B.digest(self.out['dsl'][PIERCE])})


if __name__ == '__main__':
    unittest.main()
