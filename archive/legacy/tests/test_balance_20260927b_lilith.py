"""雷皇女 莉莉丝 2026-09-27 第二批：PF 剑段削韧顶到 15/20/25，629 突袭 15→2.5。"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)
import wf_balance_20260927b_lilith as B
import wf_dsl
from wf_character_revision import encode_tree
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems
from wf_midautumn_kitlib import panel_problems

FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_lilith.json'
WORKSPACE = ROOT / 'work/character_packs' / B.PACKAGES[0]
PF1, PF2, PF3 = (B.PF_PROGRAMS[level] for level in B.PF_LEVELS)
SWORD_P13_PATH = [11, 1, 1, 1, 23, 1, 0, 1, 13]   # body[1] 剑段 onHit 首条 CreateNormalAttack 的 p13
BURST_P13_PATH = [11, 1, 0, 1, 23, 1, 0, 1, 13]


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


class LilithBatch2Test(unittest.TestCase):
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
        self.assertEqual(6, len(B.BEFORE))
        for (kind, key), want in B.BEFORE.items():
            self.assertEqual(want, B.digest(self.inputs[kind][_key(kind, key)]), (kind, key))

    def test_only_the_four_trees_are_returned(self):
        self.assertEqual({'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl',
                          'server_text', 'new_programs', 'notes'}, set(self.out))
        for kind in ('ability', 'leader', 'cas', 'text', 'table', 'action', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)
        self.assertEqual({PF1, PF2, PF3, B.BURST_PROGRAM}, set(self.out['dsl']))
        self.assertEqual([], self.out['new_programs'])  # 四棵树都已在候选 roots / skills 里

    # ---------------------------------------------------------------- PF 覆盖树

    def test_pf_detoughness_is_capped_at_15_20_25(self):
        for program, before, after in ((PF1, 16.5, 15), (PF2, 23, 20), (PF3, 35, 25)):
            self.assertEqual(before, B.detoughness(self.tree(program)), program)
            self.assertEqual(after, B.detoughness(self.out['dsl'][program]), program)
        self.assertEqual({1: 15, 2: 20, 3: 25}, B.PF_CAP)

    def test_pf_sword_p13_before_after(self):
        for level, old, new in ((1, 1.5, 1), (2, 2, 1.25), (3, 3, 1)):
            program = B.PF_PROGRAMS[level]
            area = at(self.out['dsl'][program], SWORD_P13_PATH[:4])
            self.assertEqual(('CreateHitArea', -18, ['AB']), (area[0], area[2], area[3]))
            self.assertEqual(['CalculatedUsingMaxNumOfHits', level + 2], area[14])
            self.assertEqual([{'min': old, 'max': old}], at(self.tree(program), SWORD_P13_PATH))
            self.assertEqual([{'min': new, 'max': new}], at(self.out['dsl'][program], SWORD_P13_PATH))

    def test_pf_only_the_sword_p13_leaf_moves(self):
        for program in (PF1, PF2, PF3):
            old, new = self.tree(program), self.out['dsl'][program]
            self.assertEqual([(*SWORD_P13_PATH, 0, 'min'), (*SWORD_P13_PATH, 0, 'max')],
                             leaf_diff(old, new), program)
            restored = deepcopy(new)
            at(restored, SWORD_P13_PATH)[0] = deepcopy(at(old, SWORD_P13_PATH)[0])
            self.assertEqual(json.dumps(old), json.dumps(restored), program)

    def test_fists_and_finisher_keep_their_detoughness(self):
        for level, fists, finish in ((1, 3, 10.5), (2, 4, 13), (3, 6, 17)):
            areas = B.hit_areas(self.out['dsl'][B.PF_PROGRAMS[level]])
            self.assertEqual(1 + fists + 1, len(areas))
            kept = [(n, [a[13] for a in attacks]) for _, n, attacks in areas[1:]]
            self.assertEqual([(1, [[{'min': 0.5, 'max': 0.5}]])] * fists
                             + [(1, [[{'min': finish, 'max': finish}]])], kept, level)

    def test_new_p13_number_types(self):
        # 整数值写 AMF3 integer：官方 fighter 终结段 p13 13/17 就是整数（同一棵树里现成先例）。
        finishers = [B.hit_areas(self.tree(B.PF_PROGRAMS[level]))[-1][2][0][13][0]['max']
                     for level in (2, 3)]
        self.assertEqual([int, int], [type(v) for v in finishers])
        got = [type(at(self.out['dsl'][p], SWORD_P13_PATH)[0]['max']) for p in (PF1, PF2, PF3)]
        self.assertEqual([int, float, int], got)
        self.assertIs(float, type(at(self.out['dsl'][B.BURST_PROGRAM], BURST_P13_PATH)[0]['max']))

    # ---------------------------------------------------------------- 629 突袭

    def test_burst_detoughness_15_to_2_5(self):
        old, new = self.tree(B.BURST_PROGRAM), self.out['dsl'][B.BURST_PROGRAM]
        self.assertEqual(15, B.detoughness(old))
        self.assertEqual(2.5, B.detoughness(new))
        self.assertEqual([{'min': 3, 'max': 3}], at(old, BURST_P13_PATH))
        self.assertEqual([{'min': 0.5, 'max': 0.5}], at(new, BURST_P13_PATH))
        self.assertEqual([(*BURST_P13_PATH, 0, 'min'), (*BURST_P13_PATH, 0, 'max')],
                         leaf_diff(old, new))
        self.assertEqual(['ActionDsl', 1, ['None'], *[False] * 7, 133], new[:11])  # 第一批 PF3 结算保持
        attack = at(new, BURST_P13_PATH[:-1])
        self.assertEqual([{'min': 11.7, 'max': 11.7}], attack[6])  # 倍率不动

    def test_burst_trigger_cooltime_is_over_3_seconds(self):
        row = self.inputs['ability'][B.INVOKE_KEY][B.INVOKE_ROW]
        self.assertEqual(('629', B.BURST_PROGRAM), (row[47], row[71]))
        self.assertEqual(('144', '1000000', '(None)', '300'), (row[27], row[30], row[34], row[35]))
        self.assertEqual(B.BURST_CT_FRAMES, int(row[35]))
        self.assertGreater(int(row[35]), B.FAST_CT_FRAMES)
        self.assertEqual(3, B.invoke_cap(row))
        self.assertEqual(3, self.out['notes']['burst']['per_call_cap'])
        self.assertLessEqual(B.detoughness(self.out['dsl'][B.BURST_PROGRAM]), 3)

    def test_fast_trigger_would_cap_the_burst_at_1(self):
        row = deepcopy(self.inputs['ability'][B.INVOKE_KEY][B.INVOKE_ROW])
        row[35] = '180'
        self.assertEqual(1, B.invoke_cap(row))
        with self.assertRaisesRegex(ValueError, r'burst detoughness 2\.5 > 629 cap 1'):
            B.revise_burst_tree(self.tree(B.BURST_PROGRAM), B.invoke_cap(row))
        row[71] = 'battle/action/skill/action/ability_skill/other$other'
        with self.assertRaisesRegex(ValueError, 'no longer invokes'):
            B.invoke_cap(row)

    # ---------------------------------------------------------------- 门禁

    def test_trees_pass_dsl_gates_and_roundtrip(self):
        for program, tree in self.out['dsl'].items():
            self.assertEqual([], B.dsl_problems(tree), program)
            self.assertEqual([], kit_dsl_problems(tree, element=None), program)
            rt = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))['tree']
            self.assertEqual(json.dumps(tree), json.dumps(rt), program)  # 连 int/float 一起往返

    def test_panel_texts_carry_no_detoughness_numbers(self):
        # 面板与 629 文案都不写削韧数值 ⇒ 本批无文案同步；现有文案过面板规则。
        for key, rows in self.context['cas'].items():
            text = rows[0][0]
            self.assertEqual([], panel_problems(text), key)
            self.assertFalse(any(ch.isdigit() for ch in text.replace('Lv3', '')), key)
            for word in ('虚弱', '削韧', '眩晕', '击破'):
                self.assertNotIn(word, text, key)

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
        for level in B.PF_LEVELS:
            with self.assertRaisesRegex(ValueError, 'sword p13 preimage drift'):
                B.revise_pf_tree(self.out['dsl'][B.PF_PROGRAMS[level]], level)
        with self.assertRaisesRegex(ValueError, 'burst p13 preimage drift'):
            B.revise_burst_tree(self.out['dsl'][B.BURST_PROGRAM])

    def test_structure_guards(self):
        tree = deepcopy(self.tree(PF3))
        at(tree, [11, 1, 4, 1, 5, 1, 10, 1, 3, 1, 3, 1, 23, 1, 0, 1, 13])[0]['max'] = 16
        with self.assertRaisesRegex(ValueError, 'fist/finisher preimage drift'):
            B.revise_pf_tree(tree, 3)
        tree = deepcopy(self.tree(PF2))
        tree[11][1][1][1][14] = ['CalculatedUsingMaxNumOfHits', 5]
        with self.assertRaisesRegex(ValueError, 'sword hit count drift'):
            B.revise_pf_tree(tree, 2)
        with self.assertRaisesRegex(ValueError, 'sword hit count drift'):
            B.revise_pf_tree(self.tree(PF1), 3)  # 档位错配
        tree = deepcopy(self.tree(PF1))
        at(tree, SWORD_P13_PATH)[0] = {'min': 1.5, 'max': 1.4}
        with self.assertRaisesRegex(ValueError, 'sword p13 preimage drift'):
            B.revise_pf_tree(tree, 1)
        tree = deepcopy(self.tree(B.BURST_PROGRAM))
        tree[10] = 0
        with self.assertRaisesRegex(ValueError, 'burst root header'):
            B.revise_burst_tree(tree)

    def test_revise_is_deterministic(self):
        again = B.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(self.out, sort_keys=True), json.dumps(again, sort_keys=True))

    # ---------------------------------------------------------------- 接口常量

    def test_module_contract_constants(self):
        self.assertEqual(('139997', 'resistance_princess_ex'), (B.CID, B.CODE))
        self.assertEqual(['resistance_princess_ex'], B.PACKAGES)
        self.assertEqual({'resistance_princess_ex': '0.1.2'}, B.PACKAGE_VERSION)
        self.assertEqual(['damage-type-rules-v1'], B.CAPABILITIES)
        self.assertEqual({}, B.REVIEWED_DRIFT)
        self.assertEqual([[PF1, PF2, PF3]],
                         self.inputs['table']['master/skill/power_flip_action.orderedmap|'
                                              'resistance_princess_ex_pf'])
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)
        self.assertEqual({'lv1': [16.5, 15], 'lv2': [23, 20], 'lv3': [35, 25]},
                         self.out['notes']['pf_detoughness'])

    # ---------------------------------------------------------------- 候选 / live（本机）

    @unittest.skipUnless((WORKSPACE / 'package/manifest.json').is_file()
                         and (ROOT / 'mod-tools/profiles.json').is_file(),
                         'local candidate workspace required')
    def test_candidate_is_clean_and_splices_dry(self):
        from wf_character_revision import RevisionCandidate
        manifest = WORKSPACE / 'package/manifest.json'
        before = manifest.read_bytes()
        meta = json.loads(before)
        kwargs = dict(character_id=B.CID, code_name=B.CODE, snapshot_key='revision_20260927b',
                      package_version=B.PACKAGE_VERSION[B.PACKAGES[0]],
                      baseline_factory=lambda *a, **k: None)
        candidate = RevisionCandidate(ROOT, WORKSPACE, reviewed_input_drift=B.REVIEWED_DRIFT,
                                      **kwargs)

        def tree_in_candidate(program):
            raw = candidate.read('common', wf_dsl.dsl_logical(program))
            return wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']

        if meta['snapshot'].get('revision_20260927b') is not None:
            # 主会话暂存回写之后：候选四棵树 = 本模块输出。
            self.assertEqual(B.PACKAGE_VERSION[B.PACKAGES[0]], meta['package_version'])
            for program, tree in self.out['dsl'].items():
                self.assertEqual(json.dumps(tree), json.dumps(tree_in_candidate(program)), program)
            return
        self.assertLess(tuple(map(int, meta['package_version'].split('.'))),
                        tuple(map(int, B.PACKAGE_VERSION[B.PACKAGES[0]].split('.'))))
        for program in self.out['dsl']:
            self.assertEqual(json.dumps(self.tree(program)), json.dumps(tree_in_candidate(program)),
                             program)
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
