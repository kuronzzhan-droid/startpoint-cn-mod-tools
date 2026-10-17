"""贝尔赛蒂亚 129952 作者 2026-09-27 小重做：环爆 629 由能力4 移到能力3（自身直击 50 次、CT 10 秒）、能力4/6 去主位；
环爆树不改（削韧保持每次 1，复核裁定）。"""
import ast
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any
import unittest
from unittest import mock
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)
import wf_balance_20260927b_witch_move as M
import wf_client_legality as legality
import wf_describe
import wf_dsl
from wf_character_revision import encode_tree
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems
from wf_midautumn_kitlib import panel_problems

FIXTURE = Path(__file__).parent / 'fixtures/balance_20260927b_witch_move.json'
WORKSPACE = ROOT / 'work/character_packs' / M.PACKAGES[0]
GENERATOR = WORKSPACE / 'build_workspace.py'
RING = M.RING_PROGRAM
A3, A4, A5, A6 = (M.ABILITY[slot] for slot in (3, 4, 5, 6))
#: 环爆树唯一 CreateNormalAttack 的 p13（Wait 44 → CreateHitArea onHit 第 2 条命令）；本次不改，只核对。
P13_PATH = [11, 1, 1, 1, 3, 1, 0, 1, 23, 1, 1, 1, 13]
#: 环爆行搬家时允许变化的格：c0 / 触发 / 阈值 ×2 / CT。
MOVED_COLS = {0: ('dimension_witch_smr20_ex_4', 'dimension_witch_smr20_ex_3'), 27: ('23', '20'),
              30: ('100000', '5000000'), 31: ('100000', '5000000'), 35: ('0', '600')}


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


def load_generator_subset() -> dict:
    """只执行包内 kit 的纯常量与纯函数（不 import 整个脚本：它顶层 import wf_gui，会起后台线程、读 live）。

    取顶层全部 def（定义不执行函数体）＋ 生成行 / 能力技能树需要的常量赋值。
    """
    keep = {'CHARACTER_ID', 'CODE_NAME', 'ABILITY_SKILL_DIR', 'AB_SKILL', 'ENUM_MAP', 'BLOCK_FIELDS',
            'BLOCK_KIND', 'SID', 'AB_KEY', 'BLUE', 'EFFECT_DIR', 'OFFICIAL_BEAM', 'OFFICIAL_RING',
            'RANDOM_DEBUFF_POOL', 'RANDOM_DEBUFF_MISS_WEIGHT', 'AB_SKILL_PARAMS'}
    module = ast.parse(GENERATOR.read_text(encoding='utf-8'))
    body = []
    for node in module.body:
        if isinstance(node, ast.FunctionDef):
            body.append(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = {t.id for t in targets if isinstance(t, ast.Name)}
            if names & keep or any(name.startswith('TRIG_') for name in names):
                body.append(node)
    namespace = {'json': json, 'Path': Path, 'Any': Any, 'MOD_TOOLS': ROOT / 'mod-tools',
                 '__name__': 'thunder_witch_ex_generator_subset'}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(GENERATOR), 'exec'), namespace)
    return namespace


def generator_precedent_keys() -> set:
    """stage_kit 里 PRECEDENT 字典的键 ((AB_KEY 下标, 记录号))，AST 只读。"""
    module = ast.parse(GENERATOR.read_text(encoding='utf-8'))
    func, = [n for n in ast.walk(module) if isinstance(n, ast.FunctionDef) and n.name == 'stage_kit']
    table, = [n.value for n in ast.walk(func) if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'PRECEDENT' for t in n.targets)]
    keys = set()
    for key in table.keys:
        sub, idx = key.elts
        keys.add((ast.literal_eval(sub.slice), ast.literal_eval(idx)))
    return keys


class WitchMoveTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(FIXTURE.read_bytes())
        cls.inputs, cls.absent = data['inputs'], data['absent']
        cls.raw_sha, cls.context = data['dsl_raw_sha256'], data['context']
        cls.out = M.revise(cls.read_from(cls.inputs, cls.absent))

    @staticmethod
    def read_from(inputs, absent=None):
        def read(kind, key):
            if kind in inputs and key in inputs[kind]:
                return inputs[kind][key]
            raise KeyError((kind, key))          # 与 stage_batch.make_read 对缺失键的行为一致
        return read

    def live(self, key):
        return self.inputs['ability'][key]

    def tree(self):
        return self.inputs['dsl'][RING]

    # ---------------------------------------------------------------- 基线与输出形状

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(7, len(M.BEFORE))
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(want, M.digest(self.inputs[kind][key]), (kind, key))
        self.assertEqual({(kind, key) for kind, keys in self.inputs.items() for key in keys}, set(M.BEFORE))
        self.assertEqual(sorted(M.AUTO_PANEL_KEYS), sorted(self.absent['cas']))

    def test_only_abilities_3_4_6_are_returned(self):
        self.assertEqual({'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl',
                          'server_text', 'new_programs', 'notes'}, set(self.out))
        for kind in ('leader', 'cas', 'text', 'table', 'action', 'dsl', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)           # 环爆树不改 ⇒ 不返回（只返回有变化的键）
        self.assertEqual({A3, A4, A6}, set(self.out['ability']))
        self.assertEqual([], self.out['new_programs'])

    # ---------------------------------------------------------------- 词条行前后值

    def test_ring_row_moves_to_ability3_with_new_trigger(self):
        old3, old4, new3 = self.live(A3), self.live(A4), self.out['ability'][A3]
        self.assertEqual(3, len(new3))
        self.assertEqual(old3[0], new3[0])                   # 252（直击 6 次，CT 6 秒）逐字保留
        self.assertEqual(old3[1], new3[1])                   # 穿刺 629（PF 3 次，限 10）逐字保留
        ring_old, ring_new = old4[2], new3[2]
        self.assertEqual(('629', M.RING_KEY, M.RING_PROGRAM), (ring_old[47], ring_old[70], ring_old[71]))
        changed = {col: (a, b) for col, (a, b) in enumerate(zip(ring_old, ring_new)) if a != b}
        self.assertEqual(MOVED_COLS, changed)
        # 未动格：主位 false / special / 自身 puller 0 / 限次 (None) / precontent (None) / 629 两列
        self.assertEqual(('false', 'special', '0', '(None)', '(None)', '629'),
                         (ring_new[1], ring_new[2], ring_new[28], ring_new[34], ring_new[39], ring_new[47]))
        self.assertEqual(126, len(ring_new))

    def test_ability4_keeps_two_rows_and_opens_the_unison_slot(self):
        old, new = self.live(A4), self.out['ability'][A4]
        self.assertEqual(3, len(old))
        self.assertEqual(2, len(new))
        for index in (0, 1):
            diff = {col: (a, b) for col, (a, b) in enumerate(zip(old[index], new[index])) if a != b}
            self.assertEqual({1: ('false', 'true')}, diff, index)
        self.assertEqual(['391', '394'], [row[47] for row in new])
        self.assertNotIn('629', [row[47] for row in new])

    def test_ability6_opens_the_unison_slot(self):
        old, new = self.live(A6), self.out['ability'][A6]
        self.assertEqual(2, len(new))
        for index in (0, 1):
            diff = {col: (a, b) for col, (a, b) in enumerate(zip(old[index], new[index])) if a != b}
            self.assertEqual({1: ('false', 'true')}, diff, index)
        self.assertEqual(['46', '410'], [row[109] for row in new])

    def test_ability5_is_already_open_and_untouched(self):
        rows = self.live(A5)
        self.assertEqual(['true'] * 3, [row[1] for row in rows])
        self.assertNotIn(A5, self.out['ability'])

    def test_unison_and_main_slot_rules(self):
        after = {**self.out['ability'], A5: self.live(A5)}
        self.assertEqual({A3: {'false'}, A4: {'true'}, A5: {'true'}, A6: {'true'}},
                         {key: {row[1] for row in rows} for key, rows in after.items()})
        for key, rows in after.items():
            for row in rows:
                self.assertFalse({'202', '203'} & {row[6], row[13], row[20]}, key)
                if row[47] == '629':
                    self.assertEqual('false', row[1], key)   # 629 副位禁
        self.assertEqual(2, sum(row[47] == '629' for row in after[A3]))
        self.assertEqual(13, sum(len(rows) for rows in after.values())
                         + sum(len(self.context['ability'][M.ABILITY[s]]) for s in (1, 2)))

    def test_rows_pass_client_legality_gates(self):
        self.assertEqual([], M.row_problems(self.out['ability']))
        cas_keys = set(self.inputs['cas'])
        for key, rows in self.out['ability'].items():
            for index, row in enumerate(rows):
                self.assertEqual([], legality.client_legality_problems('ability', row), (key, index))
                self.assertEqual([], legality.declared_block_field_problems('ability', row), (key, index))
                self.assertEqual([], legality.invoke_skill_string_problems(row, cas_keys, 'ability'), (key, index))
        with_missing = deepcopy(self.out['ability'][A3][2])
        with_missing[70] = 'ability_skill_witch_ex_missing'
        self.assertTrue(legality.invoke_skill_string_problems(with_missing, cas_keys, 'ability'))

    def test_auto_panel_renders_the_new_trigger(self):
        line = wf_describe.describe_line(self.out['ability'][A3][2], 'ability')
        self.assertIn('直接攻击≥50', line)
        self.assertIn('CT10秒', line)
        self.assertIn(M.RING_KEY, line)
        for key, rows in self.out['ability'].items():
            for row in rows:
                self.assertNotIn('100%以下', wf_describe.describe_line(row, 'ability'), key)
        text = self.inputs['cas'][M.RING_KEY][0][0]
        self.assertEqual([], panel_problems(text))
        self.assertFalse(any(ch.isdigit() for ch in text))   # 629 文案不写触发 / 削韧数值 ⇒ 无需同步
        for word in ('发动技能时', '虚弱', '削韧', '眩晕'):
            self.assertNotIn(word, text)

    # ---------------------------------------------------------------- 环爆树

    def test_ring_detoughness_stays_1_within_the_ct10_cap(self):
        tree = self.tree()
        self.assertNotIn(RING, self.out['dsl'])
        self.assertEqual(1, M.batch2.detoughness(tree))
        self.assertEqual([{'min': 1, 'max': 1}], at(tree, P13_PATH))
        area = at(tree, P13_PATH[:-5])
        self.assertEqual(('CreateHitArea', ['CalculatedUsingMaxNumOfHits', 1], ['Some', [{'min': 1, 'max': 1}]], 4),
                         (area[0], area[14], area[15], area[24]))
        # 计算：CT 600 帧 > 180 ⇒ B.3 每次 ≤3；1 次命中 × p13 1 = 1 ≤ 3（也 ≤ 快档 1）⇒ 不上调
        cap = M.ring_invoke_cap(self.out['ability'][A3][2])
        self.assertEqual(3, cap)
        self.assertEqual(1, M.RING_HITS * M.RING_P13)
        self.assertEqual(1.0, M.check_ring_tree(tree, cap))
        self.assertEqual(1.0, M.check_ring_tree(tree, M.INVOKE_CAP_FAST))
        notes = self.out['notes']['ring_detoughness']
        self.assertEqual((1.0, 3, 600), (notes['detoughness'], notes['per_call_cap'], notes['row_ct_frames']))
        self.assertIn('保持每次 1', notes['decision'])

    def test_ring_tree_is_read_only(self):
        tree = deepcopy(self.tree())
        M.check_ring_tree(tree, M.INVOKE_CAP)
        self.assertEqual([], leaf_diff(self.tree(), tree))
        attack = at(tree, P13_PATH[:-1])
        self.assertEqual([{'min': 6.0, 'max': 9.0}], attack[6])       # 倍率不动
        self.assertEqual([{'min': 1, 'max': 1}], attack[14])          # Fever 点不动
        self.assertIs(int, type(at(tree, P13_PATH)[0]['max']))

    def test_ring_p13_drift_or_cap_overflow_is_rejected(self):
        for value in (3, 0.25):
            tree = deepcopy(self.tree())
            at(tree, P13_PATH)[0].update(min=value, max=value)
            with self.assertRaisesRegex(ValueError, 'ring p13 drift'):
                M.check_ring_tree(tree, M.INVOKE_CAP)
            live = deepcopy(self.inputs)
            live['dsl'][RING] = tree
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                M.revise(self.read_from(live))
        with self.assertRaisesRegex(ValueError, r'ring detoughness 1\.0 > 629 cap 0'):
            M.check_ring_tree(self.tree(), 0)
        # revise() 真的用新触发行的 CT 上限核对环爆树（不是只靠 BEFORE 摘要）。
        with mock.patch.object(M, 'INVOKE_CAP', 0):
            with self.assertRaisesRegex(ValueError, r'ring detoughness 1\.0 > 629 cap 0'):
                M.revise(self.read_from(self.inputs))

    def test_ring_row_drift_forces_a_ct_recheck(self):
        for col, value in ((35, '180'), (27, '23'), (30, '100000'), (34, '10'), (28, '7'), (1, 'true'),
                           (71, 'battle/action/skill/action/ability_skill/other$other')):
            row = deepcopy(self.out['ability'][A3][2])
            row[col] = value
            with self.assertRaisesRegex(ValueError, 're-check CT rule'):
                M.ring_invoke_cap(row)

    def test_unchanged_ring_tree_still_passes_dsl_gates_and_roundtrip(self):
        # 本次不改环爆树；这里只证明它在新触发下仍是一棵合法、可往返的树（不是改动门禁）。
        tree = self.tree()
        self.assertEqual([], M.batch2.dsl_problems(tree))
        self.assertEqual([], kit_dsl_problems(tree, element=None))
        self.assertEqual([], legality.action_dsl_element_problems(tree, 1))
        self.assertEqual([], legality.action_dsl_subject_binding_problems(tree))
        self.assertEqual([], legality.action_dsl_lookup_scope_problems(tree))
        self.assertEqual([], legality.action_dsl_hit_area_target_problems(tree))
        rt = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))['tree']
        self.assertEqual(json.dumps(tree), json.dumps(rt))   # 连 int/float 一起往返

    # ---------------------------------------------------------------- fail closed

    def test_live_drift_is_rejected_and_inputs_are_not_mutated(self):
        original = deepcopy(self.inputs)
        M.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(original), json.dumps(self.inputs))
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.inputs)
            value = drifted[kind][key]
            if kind == 'dsl':
                value[10] = 4
            else:
                value[0][-1] = value[0][-1] + 'x'
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                M.revise(self.read_from(drifted))
            missing = deepcopy(self.inputs)
            missing[kind][key] = None
            with self.assertRaises(ValueError):
                M.revise(self.read_from(missing))

    def test_panel_override_appearing_is_rejected(self):
        for key in M.AUTO_PANEL_KEYS:
            live = deepcopy(self.inputs)
            live['cas'][key] = [['x']]
            with self.assertRaisesRegex(ValueError, 'no longer auto-generated'):
                M.revise(self.read_from(live))

    def test_output_is_detached_from_inputs(self):
        out = M.revise(self.read_from(self.inputs))
        out['ability'][A3][2][35] = '1'
        out['ability'][A3][0][0] = 'x'
        out['ability'][A4][0][1] = 'x'
        self.assertEqual('0', self.live(A4)[2][35])
        self.assertEqual('false', self.live(A4)[0][1])
        self.assertEqual('dimension_witch_smr20_ex_3', self.live(A3)[0][0])

    def test_own_output_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live['ability'].update(deepcopy(self.out['ability']))
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            M.revise(self.read_from(live))
        with self.assertRaisesRegex(ValueError, 'records'):
            M.ability_rows({A3: self.out['ability'][A3], A4: self.out['ability'][A4],
                            A5: self.live(A5), A6: self.out['ability'][A6]})

    def test_structure_guards(self):
        rows = deepcopy(self.live(A4))
        rows[2][32] = '1'                                   # 非空的额外格
        with self.assertRaisesRegex(ValueError, 'reviewed ring 629 row'):
            M.moved_ring_row(rows[2])
        abilities = {key: deepcopy(self.live(key)) for key in (A3, A4, A5, A6)}
        abilities[A5][1][1] = 'false'
        with self.assertRaisesRegex(ValueError, 'ability 5 must already be open'):
            M.ability_rows(abilities)
        abilities = {key: deepcopy(self.live(key)) for key in (A3, A4, A5, A6)}
        abilities[A6][0][6] = '202'
        with self.assertRaisesRegex(ValueError, 'unexpected precondition'):
            M.ability_rows(abilities)
        tree = deepcopy(self.tree())
        at(tree, P13_PATH[:-5])[14] = ['CalculatedUsingMaxNumOfHits', 2]
        with self.assertRaisesRegex(ValueError, 'ring hit area drift'):
            M.check_ring_tree(tree, M.INVOKE_CAP)
        tree = deepcopy(self.tree())
        tree[0] = 'ActionDslX'
        with self.assertRaisesRegex(ValueError, 'root header'):
            M.check_ring_tree(tree, M.INVOKE_CAP)
        tree = deepcopy(self.tree())
        onhit = at(tree, P13_PATH[:-3])
        onhit.append(deepcopy(onhit[1]))
        with self.assertRaisesRegex(ValueError, 'one CreateNormalAttack'):
            M.check_ring_tree(tree, M.INVOKE_CAP)

    def test_revise_is_deterministic(self):
        again = M.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(self.out, sort_keys=True), json.dumps(again, sort_keys=True))

    # ---------------------------------------------------------------- 接口常量

    def test_module_contract_constants(self):
        self.assertEqual(('129952', 'dimension_witch_smr20_ex'), (M.CID, M.CODE))
        self.assertEqual(['thunder_witch_ex'], M.PACKAGES)
        self.assertEqual({'thunder_witch_ex': '0.1.2'}, M.PACKAGE_VERSION)
        self.assertEqual([], M.CAPABILITIES)
        self.assertEqual({}, M.REVIEWED_DRIFT)
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)

    def test_notes_describe_self_count_and_staging(self):
        notes = self.out['notes']
        self.assertIn('Myself', notes['panel_text'])
        self.assertIn('自身直击 50 次', notes['panel_text'])
        self.assertIn('revision_20260927c', notes['staging'])

    # ---------------------------------------------------------------- 生成器 / 候选 / live（本机）

    @unittest.skipUnless(GENERATOR.is_file(), 'package kit source required')
    def test_generator_matches_revise(self):
        gen = load_generator_subset()
        self.assertEqual({'kind': 20, 'trigger_puller': 0, 'threshold.power1': 5000000,
                          'threshold.first_max': 5000000, 'trigger_limit': '(None)', 'cooltime': 600},
                         gen['TRIG_DIRECT50_CD'])
        rows = gen['build_ability_rows']()
        want = {**{M.ABILITY[s]: self.context['ability'][M.ABILITY[s]] for s in (1, 2)},
                A5: self.live(A5), **self.out['ability']}
        self.assertEqual(want, rows)
        self.assertEqual(13, sum(len(v) for v in rows.values()))
        self.assertIn('共 13 条记录', gen['build_ability_rows'].__doc__)
        self.assertEqual(json.dumps(self.tree()), json.dumps(gen['build_ability_skill_tree'](2)))   # 环爆树 == live
        pierce = M.PIERCE_PROGRAM
        self.assertEqual(json.dumps(self.context['dsl'][pierce]), json.dumps(gen['build_ability_skill_tree'](1)))

    @unittest.skipUnless(GENERATOR.is_file(), 'package kit source required')
    def test_generator_precedent_table_follows_the_move(self):
        keys = generator_precedent_keys()
        self.assertIn((3, 2), keys)
        self.assertNotIn((4, 2), keys)
        self.assertEqual({(1, 0), (2, 0), (2, 1), (3, 0), (3, 1), (3, 2), (4, 0), (4, 1),
                          (5, 0), (5, 1), (5, 2), (6, 0), (6, 1)}, keys)

    @unittest.skipUnless((WORKSPACE / 'package/manifest.json').is_file()
                         and (ROOT / 'mod-tools/profiles.json').is_file(),
                         'local candidate workspace required')
    def test_candidate_splices_dry(self):
        from wf_character_revision import RevisionCandidate
        import wf_mod_tool as core
        manifest = WORKSPACE / 'package/manifest.json'
        before = manifest.read_bytes()
        meta = json.loads(before)
        candidate = RevisionCandidate(ROOT, WORKSPACE, reviewed_input_drift=M.REVIEWED_DRIFT,
                                      character_id=M.CID, code_name=M.CODE,
                                      snapshot_key='revision_20260927b_witch_move_dryrun',
                                      package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                                      baseline_factory=lambda *a, **k: None)
        ring_logical = wf_dsl.dsl_logical(RING)
        ability_logical = 'master/ability/ability.orderedmap'
        in_candidate = wf_dsl.parse_dsl(zlib.decompress(candidate.read('common', ring_logical), -15))['tree']
        table = core.read_orderedmap_file_from_bytes(candidate.read('common', ability_logical))
        rows = {key: core.read_csv_lines(table[key]) for key in (A3, A4, A6)}
        # 环爆树任何时候都与 live 逐字节一致（本模块不改它）。
        self.assertEqual(json.dumps(self.tree()), json.dumps(in_candidate))
        self.assertEqual(self.raw_sha[RING], hashlib.sha256(candidate.read('common', ring_logical)).hexdigest())
        if rows == self.out['ability']:
            # 主会话暂存回写之后：候选 = 本模块输出。
            self.assertEqual(M.PACKAGE_VERSION[M.PACKAGES[0]], meta['package_version'])
            return
        self.assertLess(tuple(map(int, meta['package_version'].split('.'))),
                        tuple(map(int, M.PACKAGE_VERSION[M.PACKAGES[0]].split('.'))))
        self.assertEqual({key: self.live(key) for key in (A3, A4, A6)}, rows)
        claim = next(item for item in meta['tables'] if item['logical_path'] == ability_logical)
        self.assertTrue({A3, A4, A6} <= set(claim['outer_keys']))
        cas_claim = next(item for item in meta['tables']
                         if item['logical_path'] == 'master/string/custom_ability_string.orderedmap')
        self.assertTrue(M.INVOKE_STRINGS <= set(cas_claim['outer_keys']))
        candidate.splice(ability_logical, self.out['ability'])
        evidence = candidate.finish({'dry_run': True}, apply=False)
        self.assertFalse(evidence['applied'])
        changed = {item['logical_path'] for item in evidence['changed_files']}
        self.assertEqual({ability_logical}, changed)                 # 只动 ability 表，环爆树不在改动集
        self.assertEqual(before, manifest.read_bytes())

    @unittest.skipUnless((ROOT / 'mod-tools/profiles.json').is_file(), 'local live store required')
    def test_live_is_either_the_baseline_or_this_output(self):
        import wf_mod_tool as core
        store = Path(core.resolve_active_store())
        path = core.table_path(store, wf_dsl.dsl_logical(RING))
        if not path.is_file():
            self.skipTest('live store DSL not present')
        live = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))['tree']
        self.assertEqual(M.BEFORE['dsl', RING], M.digest(live))      # 环爆树不改：live 只能是基线
        table = core.read_orderedmap_file_from_bytes(
            core.table_path(store, 'master/ability/ability.orderedmap').read_bytes())
        for key in (A3, A4, A6):
            rows = core.read_csv_lines(table[key])
            self.assertIn(M.digest(rows), {M.BEFORE['ability', key], M.digest(self.out['ability'][key])}, key)


if __name__ == '__main__':
    unittest.main()
