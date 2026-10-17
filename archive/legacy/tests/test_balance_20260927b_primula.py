"""普莉姆拉·浴衣 169992 2026-09-27 第二批：技能烟花削韧 20→14（两档 36→30）；kit 与设计镜像同步。"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)
import wf_balance_20260927b_primula as B
import wf_client_legality as legality
import wf_dsl
from wf_character_revision import encode_tree
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems
from wf_midautumn_kitlib import panel_problems

FIXTURE = Path(__file__).parent / 'fixtures/balance_20260927b_primula.json'
WORKSPACE = ROOT / 'work/character_packs' / B.PACKAGES[0]
PROGRAMS = B.SKILL_PROGRAMS
GARDEN_P13 = [11, 1, 1, 1, 6, 1, 0, 1, 11, 1, 2, 1, 3, 1, 0, 1, 23, 1, 1, 1, 13]   # 花园 onHit 第 2 条
FINALE_P13 = [11, 1, 1, 1, 6, 1, 0, 1, 11, 1, 4, 1, 3, 1, 1, 1, 23, 1, 0, 1, 13]   # 烟花 onHit 第 1 条


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


def _pack():
    """与 test_seasonal7_kit_primula 同法：关掉来源登记，保证测试不写 workspace 证据。"""
    try:
        import wf_seasonal7_common as C
        import wf_seasonal7_kit_primula as K
        import wf_seasonal7_specs as S
        pack = C.S7Pack(S.get_spec("primula"))
        if pack.official_read(K.ABILITY, "common") is None:
            return None
        pack._record_source = lambda *a, **k: None
        return pack
    except Exception:            # noqa: BLE001
        return None


class PrimulaBatch2Test(unittest.TestCase):
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

    def test_action_rows_point_at_the_trees(self):
        rows = dict((k, f) for k, f in self.inputs['action'][B.ACTION_KEY])
        self.assertEqual({'1': PROGRAMS['1'], '2': PROGRAMS['2']}, {k: f[7] for k, f in rows.items()})
        self.assertEqual({'1': ['540', '540'], '2': ['540', '490']}, self.out['notes']['skill_energy'])

    # ---------------------------------------------------------------- 改动前后值

    def test_skill_detoughness_36_to_30(self):
        for level in B.LEVELS:
            old, new = self.tree(level), self.out['dsl'][PROGRAMS[level]]
            self.assertEqual(36, B.detoughness(old), level)
            self.assertEqual(30, B.detoughness(new), level)
            self.assertLessEqual(B.detoughness(new), B.SKILL_CAP)
            self.assertEqual([{'min': 20, 'max': 20}], at(old, FINALE_P13))
            self.assertEqual([{'min': 14, 'max': 14}], at(new, FINALE_P13))
            self.assertEqual([{'min': 2, 'max': 2}], at(new, GARDEN_P13))     # 花园不动
            garden = at(new, GARDEN_P13[:-5])
            self.assertEqual((['SpecifyHitAreaLifetimeDirectly', 160], ['SpecifyMinHitIntervalDirectly', 20],
                              ['Some', [{'min': 8, 'max': 8}]]), tuple(garden[13:16]))
            self.assertEqual(8, B.area_hits(garden))
            finale = at(new, FINALE_P13[:-5])
            self.assertEqual(['CalculatedUsingMaxNumOfHits', 1], finale[14])
        self.assertEqual({'lv1': [36.0, 30.0], 'lv2': [36.0, 30.0]}, self.out['notes']['skill_detoughness'])

    def test_only_the_finale_p13_leaf_moves(self):
        for level in B.LEVELS:
            old, new = self.tree(level), self.out['dsl'][PROGRAMS[level]]
            self.assertEqual([(*FINALE_P13, 0, 'min'), (*FINALE_P13, 0, 'max')], leaf_diff(old, new), level)
            restored = deepcopy(new)
            at(restored, FINALE_P13)[0] = deepcopy(at(old, FINALE_P13)[0])
            self.assertEqual(json.dumps(old), json.dumps(restored), level)
            self.assertIs(int, type(at(new, FINALE_P13)[0]['max']))  # 原值 20 为 AMF3 integer，新值同型
            attack = at(new, FINALE_P13[:-1])
            self.assertEqual({'vid': 2, 'min': 0, 'max': 0.6}, attack[6][0]['vlv'][0])  # 夜百合成长不动

    # ---------------------------------------------------------------- 门禁

    def test_trees_pass_dsl_gates_and_roundtrip(self):
        for program, tree in self.out['dsl'].items():
            self.assertEqual([], B.dsl_problems(tree), program)
            self.assertEqual([], kit_dsl_problems(tree, element=None), program)
            self.assertEqual([], legality.action_dsl_element_problems(tree, 5), program)
            rt = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))['tree']
            self.assertEqual(json.dumps(tree), json.dumps(rt), program)

    def test_skill_descriptions_carry_no_detoughness_numbers(self):
        texts = [f[1] for _, f in self.inputs['action'][B.ACTION_KEY]]
        texts += [row[i] for row in self.context['text']['169992'] for i in (5, 7)]
        texts += [row[i] for row in self.context['server_text']['169992'] for i in (5, 7)]
        self.assertEqual(6, len(texts))
        for text in texts:
            self.assertEqual([], panel_problems(text))
            self.assertFalse(any(ch.isdigit() for ch in text), text)
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
                value[0][1][1] = value[0][1][1] + 'x'
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                B.revise(self.read_from(drifted))
            missing = deepcopy(self.inputs)
            missing[kind][_key(kind, key)] = None
            with self.assertRaises(ValueError):
                B.revise(self.read_from(missing))

    def test_output_is_detached_from_inputs(self):
        out = B.revise(self.read_from(self.inputs))
        at(out['dsl'][PROGRAMS['1']], FINALE_P13)[0]['max'] = 99
        self.assertEqual([{'min': 20, 'max': 20}], at(self.tree('1'), FINALE_P13))

    def test_own_output_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live['dsl'].update(deepcopy(self.out['dsl']))
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            B.revise(self.read_from(live))
        for level in B.LEVELS:
            with self.assertRaisesRegex(ValueError, 'finale p13 preimage drift'):
                B.revise_skill_tree(self.out['dsl'][PROGRAMS[level]], level)

    def test_structure_guards(self):
        tree = deepcopy(self.tree('2'))
        at(tree, GARDEN_P13)[0] = {'min': 3, 'max': 3}
        with self.assertRaisesRegex(ValueError, 'garden p13 drift'):
            B.revise_skill_tree(tree, '2')
        tree = deepcopy(self.tree('2'))
        at(tree, GARDEN_P13[:-5])[15] = ['Some', [{'min': 9, 'max': 9}]]
        with self.assertRaisesRegex(ValueError, 'garden hit area drift'):
            B.revise_skill_tree(tree, '2')
        tree = deepcopy(self.tree('1'))
        at(tree, FINALE_P13[:-5])[14] = ['CalculatedUsingMaxNumOfHits', 2]
        with self.assertRaisesRegex(ValueError, 'finale hit area drift'):
            B.revise_skill_tree(tree, '1')
        tree = deepcopy(self.tree('1'))
        tree[1] = 3
        with self.assertRaisesRegex(ValueError, 'root header'):
            B.revise_skill_tree(tree, '1')

    def test_revise_is_deterministic(self):
        again = B.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(self.out, sort_keys=True), json.dumps(again, sort_keys=True))

    # ---------------------------------------------------------------- 接口常量

    def test_module_contract_constants(self):
        self.assertEqual(('169992', 'blackflower_wiz_yukata'), (B.CID, B.CODE))
        self.assertEqual(['s7-primula'], B.PACKAGES)
        self.assertEqual({'s7-primula': '1.0.1'}, B.PACKAGE_VERSION)
        self.assertEqual([], B.CAPABILITIES)
        self.assertEqual({}, B.REVIEWED_DRIFT)
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)

    # ---------------------------------------------------------------- 生成器 / 镜像

    def test_kit_constant_matches_this_module(self):
        import wf_seasonal7_kit_primula as K
        self.assertEqual(([{'min': 20, 'max': 20}], [{'min': 14, 'max': 14}]), K.FINALE_DETOUGHNESS)
        self.assertEqual(tuple(B._p13(v) for v in B.FINALE_P13), K.FINALE_DETOUGHNESS)

    def test_mirror_tree_is_idempotent(self):
        for level in B.LEVELS:
            new = self.out['dsl'][PROGRAMS[level]]
            self.assertEqual(json.dumps(new), json.dumps(B.mirror_tree(self.tree(level), level)))
            self.assertEqual(json.dumps(new), json.dumps(B.mirror_tree(new, level)))
        tree = deepcopy(self.tree('1'))
        at(tree, FINALE_P13)[0] = {'min': 17, 'max': 17}
        with self.assertRaisesRegex(ValueError, 'finale p13 preimage drift'):
            B.mirror_tree(tree, '1')

    @unittest.skipUnless(all((ROOT / B.MIRRORS[level]).is_file() for level in B.LEVELS),
                         'design mirror required')
    def test_design_mirrors_equal_revise(self):
        self.assertEqual([], B.sync_mirrors(ROOT, write=False))
        for level in B.LEVELS:
            mirror = json.loads((ROOT / B.MIRRORS[level]).read_bytes())
            self.assertEqual(json.dumps(self.out['dsl'][PROGRAMS[level]]), json.dumps(mirror), level)

    def test_kit_compose_equals_revise(self):
        pack = _pack()
        if pack is None:
            self.skipTest('official baseline / live store required for the seasonal7 kit')
        import wf_seasonal7_common as C
        import wf_seasonal7_kit_primula as K
        families = []
        for fam in K.EFFECT_FAMILIES:
            dst = f"battle/effect/skill_unique/{K.CODE}_{fam['dst_subdir']}"
            families.append({"src_dir": fam["src_dir"], "dst_dir": dst, "donor": fam["src_dir"].rsplit("/", 1)[-1],
                             "dst_name": dst.rsplit("/", 1)[-1], "copied_bases": sorted(fam["fx_names"])})
        for level in B.LEVELS:
            tree, log = K.compose_tree(pack, level)
            for fam in families:
                tree, _ = C.rewrite_effect_refs(tree, fam, strict=True)
            self.assertEqual(json.dumps(self.out['dsl'][PROGRAMS[level]]), json.dumps(tree), level)
            self.assertEqual(1, sum(1 for e in log if e['param'] == 'p12'))

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
            self.assertEqual(B.PACKAGE_VERSION[B.PACKAGES[0]], meta['package_version'])
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
