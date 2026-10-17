"""玛格诺斯「燎原之炎」119996 2026-09-27 第二批：眩晕蓄积 600%→100%、PF 剑士扫击削韧归零（15/20/25）、技能 34→29.2。"""
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
import wf_balance_20260927b_lionreborn as B
import wf_dsl
from wf_character_revision import encode_tree
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems
from wf_midautumn_kitlib import panel_problems

FIXTURE = Path(__file__).parent / 'fixtures/balance_20260927b_lionreborn.json'
WORKSPACE = ROOT / 'work/character_packs/lion_swordman_reborn'
PF1, PF2, PF3 = (B.PF_PROGRAMS[level] for level in B.PF_LEVELS)
SK1, SK2 = (B.SKILL_PROGRAMS[level] for level in B.SKILL_LEVELS)
SWEEP_P13 = [11, 1, 1, 1, 23, 1, 0, 1, 13]                               # PF body[1] 剑士扫击
BURST_P13 = [11, 1, 4, 1, 5, 1, 4, 1, 11, 1, 1, 1, 23, 1, 0, 1, 13]       # 撞敌后特殊爆裂
SLAM_P13 = [11, 1, 2, 1, 11, 1, 0, 1, 3, 1, 2, 1, 23, 1, 0, 1, 13]        # 猛击地面（官方母本）
BLAST_P13 = [11, 1, 5, 1, 3, 1, 0, 1, 23, 1, 1, 1, 13]                    # 爆炸 8 段
FIELD_P13 = [11, 1, 6, 1, 11, 1, 0, 1, 3, 1, 0, 1, 23, 1, 0, 1, 13]       # 灼烧领域 16 段
RELOCATED_FX = ('battle/effect/skill_unique/fire_dragon_zenith/fire_dragon_zenith_explosion_',
                'battle/effect/skill_unique/lion_swordman_reborn/zenith_explosion/explosion_')


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


def load_script(name):
    """只导入包内历史 kit 的纯函数（不调 main）；不在工作区留字节码缓存。"""
    spec = importlib.util.spec_from_file_location(f'lion_reborn_{name}', WORKSPACE / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    saved, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = saved
    return module


class LionRebornBatch2Test(unittest.TestCase):
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
        self.assertEqual(8, len(B.BEFORE))
        for (kind, key), want in B.BEFORE.items():
            self.assertEqual(want, B.digest(self.inputs[kind][_key(kind, key)]), (kind, key))
        self.assertEqual(set(B.PF_PROGRAMS.values()) | set(B.SKILL_PROGRAMS.values()), set(self.raw_sha))

    def test_only_ability5_and_five_trees_are_returned(self):
        self.assertEqual({'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl',
                          'server_text', 'new_programs', 'notes'}, set(self.out))
        for kind in ('leader', 'cas', 'text', 'table', 'action', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)
        self.assertEqual({'1199965'}, set(self.out['ability']))
        self.assertEqual({PF1, PF2, PF3, SK1, SK2}, set(self.out['dsl']))
        self.assertEqual([], self.out['new_programs'])

    def test_pf_and_skill_programs_belong_to_the_character(self):
        leader = self.context['leader'][B.CID]
        pf_rows = [r for r in leader if r[45] == '722']
        self.assertEqual(1, len(pf_rows))
        self.assertEqual(('lion_swordman_reborn_pf', '1,2,3'), (pf_rows[0][80], pf_rows[0][81]))
        self.assertEqual([[PF1, PF2, PF3]],
                         self.inputs['table']['master/skill/power_flip_action.orderedmap|lion_swordman_reborn_pf'])
        self.assertEqual({'1': SK1, '2': SK2},
                         {inner: fields[7] for inner, fields in self.inputs['action'][B.CODE]})

    # ---------------------------------------------------------------- 眩晕蓄积（B.4）

    def test_self_stunify_600_to_100(self):
        old, new = self.inputs['ability']['1199965'], self.out['ability']['1199965']
        self.assertEqual(2, len(new))
        self.assertEqual(('51', '0', '600000', '600000'), (old[1][47], old[1][48], old[1][51], old[1][52]))
        self.assertEqual(('51', '0', '100000', '100000'), (new[1][47], new[1][48], new[1][51], new[1][52]))
        self.assertEqual([i for i in range(126) if old[1][i] != new[1][i]], [51, 52])
        self.assertEqual(old[0], new[0])     # 行1 Fever 点 200% 逐字保留
        self.assertEqual(('188', '100000', '100000', B.CID), (new[1][6], new[1][9], new[1][10], new[1][12]))

    def test_ability_rows_pass_legality_gates(self):
        for i, row in enumerate(self.out['ability']['1199965']):
            self.assertEqual([], B.row_problems(row), i)

    # ---------------------------------------------------------------- 强化弹射（B.2）

    def test_pf_detoughness_is_capped_at_15_20_25(self):
        for program, before, after in ((PF1, 19.5, 15), (PF2, 28, 20), (PF3, 40, 25)):
            self.assertEqual(before, B.detoughness(self.tree(program)), program)
            self.assertEqual(after, B.detoughness(self.out['dsl'][program]), program)
        self.assertEqual({1: 15, 2: 20, 3: 25}, B.PF_CAP)

    def test_pf_sweep_p13_to_zero_and_burst_kept(self):
        for level, old, burst in ((1, 1.5, 5), (2, 2, 5), (3, 3, 6.25)):
            program = B.PF_PROGRAMS[level]
            area = at(self.out['dsl'][program], SWEEP_P13[:4])
            self.assertEqual(('CreateHitArea', -18, ['AB'], ['CalculatedUsingMaxNumOfHits', level + 2]),
                             (area[0], area[2], area[3], area[14]))
            self.assertEqual(slv(old), at(self.tree(program), SWEEP_P13))
            self.assertEqual(slv(0.0), at(self.out['dsl'][program], SWEEP_P13))
            self.assertEqual(slv(burst), at(self.out['dsl'][program], BURST_P13))
            self.assertEqual(at(self.tree(program), BURST_P13), at(self.out['dsl'][program], BURST_P13))

    def test_pf_only_the_sweep_p13_leaf_moves(self):
        for program in (PF1, PF2, PF3):
            old, new = self.tree(program), self.out['dsl'][program]
            self.assertEqual([(*SWEEP_P13, 0, 'min'), (*SWEEP_P13, 0, 'max')], leaf_diff(old, new), program)
            restored = deepcopy(new)
            at(restored, SWEEP_P13)[0] = deepcopy(at(old, SWEEP_P13)[0])
            self.assertEqual(json.dumps(old), json.dumps(restored), program)

    # ---------------------------------------------------------------- 技能（B.1）

    def test_skill_detoughness_34_to_29_2(self):
        for program in (SK1, SK2):
            self.assertEqual(34, B.detoughness(self.tree(program)), program)
            self.assertEqual(29.2, B.detoughness(self.out['dsl'][program]), program)
            self.assertLessEqual(B.detoughness(self.out['dsl'][program]), 30)
            self.assertEqual({10: 1, 0.8: 2}, B.p13_census(self.out['dsl'][program]))

    def test_skill_only_blast_and_field_p13_move(self):
        for program in (SK1, SK2):
            old, new = self.tree(program), self.out['dsl'][program]
            self.assertEqual(slv(10), at(old, SLAM_P13))
            self.assertEqual(slv(10), at(new, SLAM_P13))                      # 官方母本猛击不动
            for path in (BLAST_P13, FIELD_P13):
                self.assertEqual(slv(1.0), at(old, path))
                self.assertEqual(slv(0.8), at(new, path))
            self.assertEqual(sorted([(*BLAST_P13, 0, 'min'), (*BLAST_P13, 0, 'max'),
                                     (*FIELD_P13, 0, 'min'), (*FIELD_P13, 0, 'max')]),
                             sorted(leaf_diff(old, new)), program)
            hits = [(args[14], n) for args, n, _ in B.hit_areas(new)]
            self.assertEqual([(['CalculatedUsingMaxNumOfHits', 1], 1), (['CalculatedUsingMaxNumOfHits', 8], 8),
                              (['SpecifyMinHitIntervalDirectly', 50], 16)], hits)

    def test_new_p13_number_types(self):
        for program in (PF1, PF2, PF3):
            self.assertIs(float, type(at(self.out['dsl'][program], SWEEP_P13)[0]['max']))
        for program in (SK1, SK2):
            self.assertIs(int, type(at(self.out['dsl'][program], SLAM_P13)[0]['max']))
            for path in (BLAST_P13, FIELD_P13):
                self.assertIs(float, type(at(self.out['dsl'][program], path)[0]['max']))

    # ---------------------------------------------------------------- 门禁

    def test_trees_pass_dsl_gates_and_roundtrip(self):
        for program, tree in self.out['dsl'].items():
            self.assertEqual([], B.dsl_problems(tree), program)
            rt = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))['tree']
            self.assertEqual(json.dumps(tree), json.dumps(rt), program)  # 连 int/float 一起往返
            # 包内 kit 门禁：p13 改值不新增问题（技能树 bound id 4/5 重复是 live 既有，与本批无关）。
            self.assertEqual(kit_dsl_problems(self.tree(program), element=None),
                             kit_dsl_problems(tree, element=None), program)

    def test_texts_carry_no_down_numbers(self):
        # 能力5 无 desc_override（客户端按数值生成）；PF 文案、技能描述都不写削韧/眩晕数值 ⇒ 无文案同步。
        text = self.context['cas']['override_string_lion_swordman_reborn'][0][0]
        self.assertEqual([], panel_problems(text))
        self.assertFalse(any(ch.isdigit() for ch in text))
        descs = [fields[1] for _, fields in self.inputs['action'][B.CODE]]
        descs += [self.context['text'][B.CID][0][5], self.context['text'][B.CID][0][7]]
        descs += [self.context['server_text'][B.CID][0][5], self.context['server_text'][B.CID][0][7]]
        for desc in descs:
            self.assertFalse(any(ch.isdigit() for ch in desc), desc)
            for word in ('虚弱', '削韧', '眩晕', '击破', 'Down'):
                self.assertNotIn(word, desc)

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
            elif kind == 'action':
                value[0][1][4] = '551'
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
        live['ability'].update(deepcopy(self.out['ability']))
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            B.revise(self.read_from(live))
        for level in B.PF_LEVELS:
            with self.assertRaisesRegex(ValueError, 'sweep/burst preimage drift'):
                B.revise_pf_tree(self.out['dsl'][B.PF_PROGRAMS[level]], level)
        for level in B.SKILL_LEVELS:
            with self.assertRaisesRegex(ValueError, 'p13 preimage drift'):
                B.revise_skill_tree(self.out['dsl'][B.SKILL_PROGRAMS[level]], level)
        with self.assertRaisesRegex(ValueError, 'unexpected preimage for ability5 row2'):
            B.ability5_rows(self.out['ability']['1199965'])

    def test_structure_guards(self):
        with self.assertRaisesRegex(ValueError, 'body\\[1\\] is not the 5-hit'):
            B.revise_pf_tree(self.tree(PF1), 3)                      # 档位错配
        tree = deepcopy(self.tree(PF2))
        at(tree, BURST_P13)[0] = {'min': 5, 'max': 4}
        with self.assertRaisesRegex(ValueError, 'CreateNormalAttack p13 shape'):
            B.revise_pf_tree(tree, 2)
        tree = deepcopy(self.tree(PF3))
        at(tree, BURST_P13)[0] = {'min': 7, 'max': 7}
        with self.assertRaisesRegex(ValueError, 'sweep/burst preimage drift'):
            B.revise_pf_tree(tree, 3)
        tree = deepcopy(self.tree(SK1))
        at(tree, SLAM_P13)[0] = {'min': 1.0, 'max': 1.0}
        with self.assertRaisesRegex(ValueError, 'p13 preimage drift'):
            B.revise_skill_tree(tree, 1)
        tree = deepcopy(self.tree(SK2))
        tree[11][1][6][1][11][1][0][1][3][1][0][1][15] = ['Some', slv(18)]   # 领域上限 16→18 ⇒ 17 段、35
        with self.assertRaisesRegex(ValueError, 'detoughness preimage'):
            B.revise_skill_tree(tree, 2)
        rows = deepcopy(self.inputs['ability']['1199965'])
        rows[1][6] = '2'
        with self.assertRaisesRegex(ValueError, 'ability5 row2'):
            B.ability5_rows(rows)
        rows = deepcopy(self.inputs['ability']['1199965'])
        rows.append(list(rows[1]))
        with self.assertRaisesRegex(ValueError, 'ability5 shape drift'):
            B.ability5_rows(rows)

    def test_revise_is_deterministic(self):
        again = B.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(self.out, sort_keys=True), json.dumps(again, sort_keys=True))

    # ---------------------------------------------------------------- 接口常量

    def test_module_contract_constants(self):
        self.assertEqual(('119996', 'lion_swordman_reborn'), (B.CID, B.CODE))
        self.assertEqual([], B.PACKAGES)          # 无 flow 包（工作区未被 active.json 引用）
        self.assertEqual({}, B.PACKAGE_VERSION)
        self.assertEqual([], B.CAPABILITIES)
        self.assertEqual({}, B.REVIEWED_DRIFT)
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)
        self.assertEqual({'lv1': [19.5, 15], 'lv2': [28, 20], 'lv3': [40, 25]},
                         self.out['notes']['pf_detoughness'])
        self.assertEqual([34, 29.2], self.out['notes']['skill_detoughness'])

    # ---------------------------------------------------------------- 生成器 / live（本机）

    @unittest.skipUnless((WORKSPACE / 'build_pf.py').is_file() and (WORKSPACE / 'build_skill_dsl.py').is_file()
                         and (ROOT / 'mod-tools/profiles.json').is_file(), 'local workspace kit required')
    def test_generators_equal_revise_output(self):
        pf = load_script('build_pf')
        for level in B.PF_LEVELS:
            self.assertEqual(0.0, pf.KNIGHT[level]['c1'])
            self.assertEqual(json.dumps(self.out['dsl'][B.PF_PROGRAMS[level]][11][1][1]),
                             json.dumps(pf.spin_hit_area(level)), level)
        skill = load_script('build_skill_dsl')
        self.assertEqual(0.8, skill.TICK_DETOUGHNESS)
        for level in B.SKILL_LEVELS:
            tree = self.out['dsl'][B.SKILL_PROGRAMS[level]]
            self.assertEqual(json.dumps(tree[11][1][6]), json.dumps(skill.build_field(level)), level)
            # build_blast 的两条爆炎特效路径在该脚本之后被搬进 skill_unique/lion_swordman_reborn/（改前就不等）。
            blast = json.dumps(skill.build_blast(level)).replace(*RELOCATED_FX)
            self.assertEqual(json.dumps(tree[11][1][5]), blast, level)

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
