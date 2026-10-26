"""稻穗 139995 2026-09-27 第二批追加（作者 09-27 追加）：能力1 #5 加 CT 5 秒；能力1 #3（进 Fever 余辉+1）与
#2（Fever 中 PF Lv3 → 雷队技能槽，加雷共鸣）搬到能力3 末尾。

跨单元：全仓扫描按 live 行号读 1399951 / 1399953 的 donor 引用，发布后行内容会变的必须登记在
``INDEXED_LIVE_REFERENCES`` 并写进 notes（修复轮：补登泽赫尔 plan.json 的 ``ability LIVE:1399951#2``；
第二修复轮：秋水 soriz 改为键内按内容取后扫描不到、移出登记表，泽赫尔那条由 kit 冻结行钉住、改登 ``pinned``）。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_balance_20260927b_inaho2 as M
import wf_describe
import wf_mod_tool as core
from wf_client_description_legality import description_compatibility_problems
from wf_client_legality import (client_legality_problems, declared_block_field_problems,
                                invoke_skill_string_problems, required_client_capabilities)

FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_inaho2.json'
BATCH1_FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927_inaho.json'
BATCH2_FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_inaho.json'
WORKSPACE = ROOT / 'work/character_packs' / M.PACKAGES[0]
ABILITY_TABLE = 'master/ability/ability.orderedmap'
SNAPSHOT = 'revision_20260927b'   # stage_batch 第二批统一快照键
A1, A3, A6 = M.ABILITY1, M.ABILITY3, M.ABILITY6
FORBIDDEN = ('自身为队长时', '觉醒后', '生命值100%以下', '无上限', '无限叠加', '不设上限', '可无限')


def _diff(a, b):
    return {c: (x, y) for c, (x, y) in enumerate(zip(a, b)) if x != y}


def _read_from(inputs):
    def read(kind, key):
        return inputs[kind][key]
    return read


def _text_hashes(rows):
    text = core.write_csv_lines(rows)
    return {hashlib.sha256(v.encode()).hexdigest() for v in (text, text.rstrip('\n'), text.replace('\n', '\r\n'))}


# ---- 跨单元：按 live 行号读 1399951 / 1399953 的引用扫描
_K = f'{M.ABILITY1}|{M.ABILITY3}'
_PY_REFS = [re.compile(p) for p in (
    rf"key\s*=\s*[\"']({_K})[\"']\s*,\s*idx\s*=\s*(\d+)",                          # gbf kit: dict(src="store", key=, idx=)
    rf"\(\s*[\"'](?:store|live|LIVE)[\"']\s*,\s*[\"']({_K})[\"']\s*,\s*(\d+)",     # seasonal7: ('store', key, idx, …)
    rf"\(\s*[\"']({_K})[\"']\s*,\s*(\d+)\s*[,)]",                                  # (key, idx, …)
    rf"(?:LIVE|store|live):(?:ability\[)?({_K})\]?#(\d+)",                         # donor 字符串
)]
_TAGGED = re.compile(rf"(?:LIVE|store|live):(?:ability\[)?({_K})\]?#(\d+)")
_BARE = re.compile(rf"(?:LIVE|store|live):(?:ability\[)?({_K})\]?$")
#: 本角色自己的链（历史哈希锁定生成器 / 第一、二批稻穗模块 / 本模块）由各自测试覆盖，不算跨单元。
_OWN_CHAIN = re.compile(r'^mod-tools/wf_(inaho_.*|balance_20260927b?_inaho\d*)\.py$')
_JSON_SKIP = ('/_tmp/', '/review', '/evidence/', '/backup/', '/_inspect/', '/package/', '/frozen/')


def _scan_indexed_references():
    refs = set()
    for path in sorted((ROOT / 'mod-tools').glob('*.py')):
        rel = path.relative_to(ROOT).as_posix()
        if _OWN_CHAIN.match(rel):
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        for pattern in _PY_REFS:
            refs.update((rel, m.group(1), int(m.group(2))) for m in pattern.finditer(text))

    def walk(node, rel):
        if isinstance(node, dict):
            for value in node.values():
                if isinstance(value, str):
                    refs.update((rel, m.group(1), int(m.group(2))) for m in _TAGGED.finditer(value))
                    bare = _BARE.search(value)
                    if bare:     # "donor": "store:<key>" + "row_index": n
                        index = next((node[f] for f in ('row_index', 'donor_row_index', 'idx', 'index')
                                      if isinstance(node.get(f), int)), None)
                        refs.add((rel, bare.group(1), index))
                else:
                    walk(value, rel)
        elif isinstance(node, list):
            for value in node:
                walk(value, rel)

    files = {p for pattern in ('work/character_packs/**/design/*.json', 'work/character_packs/**/plan.json')
             for p in ROOT.glob(pattern)}
    for path in sorted(files):
        rel = path.relative_to(ROOT).as_posix()
        if not any(skip in '/' + rel for skip in _JSON_SKIP):
            walk(json.loads(path.read_bytes()), rel)
    return refs


class InahoAppend20260927bTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(FIXTURE.read_bytes())
        cls.inputs, cls.donors = data['inputs'], data['donors']
        cls.out = M.revise(_read_from(cls.inputs))
        cls.old_a1, cls.old_a3 = cls.inputs['ability'][A1], cls.inputs['ability'][A3]
        cls.new_a1, cls.new_a3 = cls.out['ability'][A1], cls.out['ability'][A3]

    # ------------------------------------------------------------ 基线与输出形状

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(want, M.digest(self.inputs[kind][key]), (kind, key))
        self.assertEqual({('ability', A1), ('ability', A3), ('ability', A6), ('leader', M.LEADER)}, set(M.BEFORE))
        self.assertEqual({'ability', 'leader', 'cas'}, set(self.inputs))
        self.assertEqual({}, self.inputs['cas'])   # 覆盖文案键在 live 不存在（见 donors 的 live 键表）
        self.assertEqual('2', self.donors['character:139995'][0][3])  # 雷（0 基）
        self.assertEqual(2, M.ELEMENT)

    def test_only_reviewed_cells_change(self):
        self.assertEqual({'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl',
                          'server_text', 'new_programs', 'notes'}, set(self.out))
        self.assertEqual({A1, A3}, set(self.out['ability']))
        for kind in ('leader', 'cas', 'text', 'table', 'action', 'dsl', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)
        self.assertEqual([], self.out['new_programs'])
        self.assertEqual((6, 4), (len(self.old_a1), len(self.new_a1)))
        self.assertEqual((7, 9), (len(self.old_a3), len(self.new_a3)))
        # 能力1：#0/#1/#4 逐字保留，#5 只改 CT，#2/#3 删除。
        self.assertEqual([self.old_a1[i] for i in (0, 1, 4)], self.new_a1[:3])
        self.assertEqual({35: ('0', '300')}, _diff(self.old_a1[5], self.new_a1[3]))
        # 能力3：原 7 行逐字保留，末尾依次追加原能力1 #2、#3。
        self.assertEqual(self.old_a3, self.new_a3[:7])
        self.assertEqual({0: ('fox_oracle_autumn_1', 'fox_oracle_autumn_3'), 1: ('true', 'false'),
                          6: ('12', '2'), 9: ('', '600000'), 10: ('', '600000'), 11: ('', 'Yellow'),
                          13: ('0', '12')},
                         _diff(self.old_a1[2], self.new_a3[7]))
        self.assertEqual({0: ('fox_oracle_autumn_1', 'fox_oracle_autumn_3'), 1: ('true', 'false')},
                         _diff(self.old_a1[3], self.new_a3[8]))
        self.assertTrue(all(len(r) == 126 for r in self.new_a1 + self.new_a3))

    # ------------------------------------------------------------ 三处改动

    def test_ally_skill_gauge_row_gets_a_five_second_cooltime(self):
        row = self.new_a1[3]
        # 雷共鸣 + Fever，自身施技（trigger 23 / puller 0）→ 除自身全员（c48=1、组不限）技能槽 5%。
        self.assertEqual(('2', 'Yellow', '12', '23', '0', '300'),
                         tuple(row[i] for i in (6, 11, 13, 27, 28, 35)))
        self.assertEqual(['211', '1', '(None)', '', '5000', '5000'], row[47:53])
        self.assertEqual('雷·编成≥6 且 Fever 时: 技能发动≥1(CT5秒) → 赋予除自身全员 技能槽 5%',
                         wf_describe.describe_rows(self.new_a1, 'ability')[3])
        # CT 单位 = 帧：第一批能力3 #3 的 600 渲染为 10 秒，本行 300 = 5 秒。
        self.assertEqual('600', self.old_a3[3][35])
        self.assertIn('(CT10秒)', wf_describe.describe_rows(self.old_a3, 'ability')[3])
        # 官方同型：自身施技（trigger 23 / puller 0）→ 211 带非零 CT。
        for name in ('official:2510085#0', 'official:2310442#0'):
            official = self.donors[name]
            self.assertEqual(('23', '0', '211'), (official[27], official[28], official[47]), name)
            self.assertNotEqual('0', official[35], name)

    def test_pf3_charge_row_moves_to_ability3_with_thunder_resonance(self):
        row = self.new_a3[7]
        self.assertEqual(('fox_oracle_autumn_3', 'false', 'attack_yellow'), tuple(row[:3]))
        # 触发 / 内容 / 数值逐格保留。
        self.assertEqual(self.old_a1[2][27:], row[27:])
        self.assertEqual(('65', '211', '5', 'Yellow', '2500', '5000'),
                         tuple(row[i] for i in (27, 47, 48, 49, 51, 52)))
        # 共鸣写法：前置块 c6–c26 与同角色 live 雷共鸣 + Fever 行（改后能力1 #3）逐字相同。
        self.assertEqual(self.new_a1[3][6:27], row[6:27])
        self.assertEqual(['2', '', '', '600000', '600000', 'Yellow', ''], row[6:13])
        self.assertEqual(['12', '', '', '', '', '', ''], row[13:20])
        self.assertEqual('0', row[20])
        # 官方同形：c1=false、c6=2 共鸣、c13=12 Fever。
        for name in ('official:1511713#1', 'official:1511593#1', 'official:1511593#2', 'official:1511473#2'):
            official = self.donors[name]
            self.assertEqual(('false', '2', '600000', '600000', '12'),
                             (official[1], official[6], official[9], official[10], official[13]), name)
        self.assertEqual('雷·编成≥6 且 Fever 时: 强化弹射Lv3≥1 → 赋予全队(雷) 技能槽 2.5%→5%',
                         wf_describe.describe_rows(self.new_a3, 'ability')[7])

    def test_afterglow_gain_row_moves_verbatim(self):
        row = self.new_a3[8]
        self.assertEqual(self.old_a1[3][2:], row[2:])
        self.assertEqual(('8', '461', '0', M.AFTERGLOW, '1', '100000'),
                         tuple(row[i] for i in (27, 47, 48, 68, 74, 59)))
        self.assertEqual(('2', '600000', 'Yellow'), (row[6], row[9], row[11]))
        self.assertEqual('雷·编成≥6 时: Fever≥1 → 自身 状态固有 100%×1次',
                         wf_describe.describe_rows(self.new_a3, 'ability')[8])
        for rows in (self.new_a1, self.new_a3[:7]):
            self.assertFalse([r for r in rows if r[47] == '461'])

    def test_ability3_stays_main_only_and_keeps_batch1_rows(self):
        self.assertEqual({('fox_oracle_autumn_3', 'false')}, {(r[0], r[1]) for r in self.new_a3})
        self.assertEqual({('fox_oracle_autumn_1', 'true')}, {(r[0], r[1]) for r in self.new_a1})
        self.assertEqual(['56', '55', '388', '211', '', '226', '32', '211', '461'],
                         [r[47] for r in self.new_a3])
        old_lines = wf_describe.describe_rows(self.old_a3, 'ability')
        self.assertEqual(old_lines, wf_describe.describe_rows(self.new_a3, 'ability')[:7])

    # ------------------------------------------------------------ 余辉依赖（语义不变）

    def test_afterglow_dependents_are_leader_gated(self):
        leader = self.inputs['leader'][M.LEADER]
        a6 = self.inputs['ability'][A6]
        deps = M.afterglow_dependencies(leader, a6, self.new_a1, self.new_a3)
        self.assertEqual(['leader#10', f'{A3}#8'], deps['gains'])
        self.assertEqual([('leader#1', True), ('leader#4', True), ('leader#5', True), ('leader#6', True),
                          ('leader#9', True), (f'{A6}#1', True)], deps['consumers'])
        # 改前来源：队长 #10 + 能力1 #3（同 unique 两源相加，当队长每次 Fever +2 层）。
        before = M.afterglow_dependencies(leader, a6, self.old_a1, self.old_a3)
        self.assertEqual(['leader#10', f'{A1}#3'], before['gains'])
        self.assertEqual(before['consumers'], deps['consumers'])
        # 队长每层行：during 134 读余辉层数（只在当队长时存在）；队长 #10：进 Fever 余辉 +1。
        for index in (1, 4, 5, 6, 9):
            self.assertEqual(('1', '134', M.AFTERGLOW), (leader[index][3], leader[index][95], leader[index][102]))
        self.assertEqual(('8', '461', M.AFTERGLOW), (leader[10][25], leader[10][45], leader[10][66]))
        # 能力6 #1：非 Fever + 余辉≥10 + 仅队长（前置 42）。
        gate = a6[1]
        self.assertEqual(('186', '144', '1000000', M.AFTERGLOW, '42', '724'),
                         (gate[6], gate[13], gate[16], gate[19], gate[20], gate[47]))
        # 其余能力键不引用余辉；余辉层上限 99。
        for key in ('1399952', '1399954', '1399955'):
            self.assertFalse([r for r in self.donors[f'ability:{key}'] if M.AFTERGLOW in r], key)
        self.assertEqual('99', self.donors['unique_condition:1399952'][0][4])
        # 队长覆盖文案的「每进入一次FEVER模式「余辉」累积1层」描述队长 #10，未动。
        self.assertEqual({}, self.out['leader'])

    def test_afterglow_guard_rejects_an_unguarded_consumer(self):
        a6 = deepcopy(self.inputs['ability'][A6])
        a6[1][20] = '0'
        deps = M.afterglow_dependencies(self.inputs['leader'][M.LEADER], a6, self.new_a1, self.new_a3)
        self.assertIn((f'{A6}#1', False), deps['consumers'])

    # ------------------------------------------------------------ 面板

    def test_panels_stay_client_generated(self):
        live_keys = self.donors['live_cas_desc_override_keys']
        self.assertEqual(['desc_override_fox_oracle_autumn', 'desc_override_fox_oracle_autumn_2',
                          'desc_override_fox_oracle_autumn_6'], live_keys)
        for key in M.AUTO_PANEL_KEYS:
            self.assertNotIn(key, live_keys)
        self.assertEqual(('desc_override_fox_oracle_autumn_1', 'desc_override_fox_oracle_autumn_3'),
                         M.AUTO_PANEL_KEYS)
        for key in M.AUTO_PANEL_KEYS:
            live = deepcopy(self.inputs)
            live['cas'][key] = [['覆盖']]
            with self.assertRaisesRegex(ValueError, 'no longer auto-generated'):
                M.revise(_read_from(live))
        for rows in (self.new_a1, self.new_a3):
            for line in wf_describe.describe_rows(rows, 'ability'):
                for word in FORBIDDEN:
                    self.assertNotIn(word, line)

    # ------------------------------------------------------------ 门禁

    def test_every_returned_row_passes_client_gates(self):
        gated = []
        for key, rows in self.out['ability'].items():
            for index, row in enumerate(rows):
                with self.subTest(key=key, row=index):
                    self.assertEqual([], client_legality_problems('ability', row))
                    self.assertEqual([], declared_block_field_problems('ability', row))
                    self.assertEqual([], invoke_skill_string_problems(row, set(), 'ability'))
                    self.assertEqual([], description_compatibility_problems('ability', row))
                    self.assertEqual([], M.row_problems('ability', row))
                    gated += [(f'{key}#{index}', cap) for cap in required_client_capabilities('ability', row)]
        # 只有能力1 的 724（Fever 中 PF 扣槽，#4 → #2）需要补丁；搬走的两行不需要。
        self.assertEqual([(f'{A1}#2', 'kyubi-fever-ratio-v1')], gated)
        self.assertEqual(['kyubi-fever-ratio-v1'], M.CAPABILITIES)

    def test_live_drift_is_rejected_and_inputs_are_not_mutated(self):
        original = deepcopy(self.inputs)
        M.revise(_read_from(self.inputs))
        self.assertEqual(original, self.inputs)
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.inputs)
            drifted[kind][key][0][-1] += 'x'
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                M.revise(_read_from(drifted))
            missing = deepcopy(self.inputs)
            missing[kind][key] = None
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                M.revise(_read_from(missing))

    def test_already_revised_live_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live['ability'].update(deepcopy(self.out['ability']))
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            M.revise(_read_from(live))
        with self.assertRaises(ValueError):
            M.ability_rows(self.new_a1, self.new_a3)
        with self.assertRaises(ValueError):          # 只搬了一半也拒绝
            M.ability_rows(self.old_a1, self.new_a3)

    def test_row_preimage_guards_fail_closed(self):
        a1_cases = {'ally cooltime set': (5, 35, '300'), 'ally target': (5, 48, '5'),
                    'pf3 trigger': (2, 27, '2'), 'pf3 already resonant': (2, 13, '2'),
                    'pf3 strength': (2, 52, '10000'), 'glow unique': (3, 68, '1399951'),
                    'glow trigger': (3, 27, '184'), 'kept row kind': (4, 47, '213'),
                    'unisonable flag': (0, 1, 'false')}
        for name, (index, col, value) in a1_cases.items():
            rows = deepcopy(self.old_a1)
            rows[index][col] = value
            with self.subTest(name), self.assertRaises(ValueError):
                M.ability_rows(rows, self.old_a3)
        for name, (index, col, value) in {'a3 main flag': (0, 1, 'true'),
                                          'a3 content': (3, 47, '213')}.items():
            rows = deepcopy(self.old_a3)
            rows[index][col] = value
            with self.subTest(name), self.assertRaises(ValueError):
                M.ability_rows(self.old_a1, rows)
        with self.assertRaises(ValueError):
            M.ability_rows(self.old_a1[:5], self.old_a3)
        with self.assertRaises(ValueError):
            M.ability_rows(self.old_a1, self.old_a3[:6])
        before = deepcopy((self.old_a1, self.old_a3))
        M.ability_rows(self.old_a1, self.old_a3)
        self.assertEqual(before, (self.old_a1, self.old_a3))
        with self.assertRaises(ValueError):
            M.moved_row(self.new_a3[7], add_resonance=True)

    # ------------------------------------------------------------ 生成器

    def test_generator_is_this_module_and_the_chain_is_consistent(self):
        # 本模块的纯函数就是这两个键的现行生成源。
        self.assertEqual((self.new_a1, self.new_a3), M.ability_rows(self.old_a1, self.old_a3))
        # 链：live 1399953 == 第一批输出；live 队长 == 第二批输出（按当前 live 推导）。
        import wf_balance_20260927_inaho as B1
        import wf_balance_20260927b_inaho as B2
        batch1 = json.loads(BATCH1_FIXTURE.read_bytes())['inputs']
        self.assertEqual(self.old_a3, B1.revise(_read_from(batch1))['ability'][A3])
        self.assertEqual(self.old_a3, B1.ability3_rows(batch1['ability'][A3]))
        batch2 = json.loads(BATCH2_FIXTURE.read_bytes())['inputs']
        b2_read = lambda kind, key: batch2[kind]['|'.join(key) if kind == 'table' else key]  # noqa: E731
        self.assertEqual(self.inputs['leader'][M.LEADER], B2.revise(b2_read)['leader'][M.LEADER])
        # 第一批对现 live / 本模块输出都拒绝（不会回退本次追加）。
        for a3 in (self.old_a3, self.new_a3):
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                B1.revise(_read_from({'ability': {A3: a3}}))
            with self.assertRaises(ValueError):
                B1.ability3_rows(a3)

    def test_historical_generators_stay_hash_locked(self):
        import wf_inaho_fever_growth_data
        import wf_inaho_fever_revision
        import wf_inaho_growth_detail_data
        import wf_inaho_native_pf_r2
        import wf_inaho_pf3_balance
        locked = {
            A1: {*wf_inaho_fever_revision.HASHES[A1], wf_inaho_pf3_balance.BASE_HASHES[A1],
                 wf_inaho_fever_growth_data.OLD[A1], wf_inaho_fever_growth_data.NEW[A1],
                 wf_inaho_growth_detail_data.OLD[A1], wf_inaho_growth_detail_data.NEW[A1]},
            A3: {*wf_inaho_fever_revision.HASHES[A3], wf_inaho_pf3_balance.BASE_HASHES[A3],
                 wf_inaho_native_pf_r2.ABILITY_BASE, wf_inaho_native_pf_r2.ABILITY_AFTER},
        }
        for key, old, new in ((A1, self.old_a1, self.new_a1), (A3, self.old_a3, self.new_a3)):
            for rows in (old, new):
                self.assertFalse(_text_hashes(rows) & locked[key], key)
        with self.assertRaises(ValueError):
            wf_inaho_fever_revision.transform({A1: core.write_csv_lines(self.new_a1),
                                               A3: core.write_csv_lines(self.new_a3),
                                               '1399955': ''})
        with self.assertRaises(ValueError):
            wf_inaho_pf3_balance.revise_native({A1: core.write_csv_lines(self.new_a1),
                                                A3: core.write_csv_lines(self.new_a3),
                                                '1399954': core.write_csv_lines(self.donors['ability:1399954'])})

    # ------------------------------------------------------------ 跨单元（按 live 行号取 donor 的别的 kit）

    def _row_changes(self, key, index):
        before, after = self.inputs['ability'][key], self.out['ability'][key]
        if index is None:
            return True
        return (index < len(before)) != (index < len(after)) or (index < len(before) and before[index] != after[index])

    @unittest.skipUnless((ROOT / 'work/character_packs').is_dir(), 'local work/ tree required')
    def test_every_indexed_live_reference_that_changes_is_registered(self):
        refs = _scan_indexed_references()
        # 扫描器自检：已知不受影响的引用（yuki 带哈希的 store:1399951#1）必须能扫到。
        self.assertIn(('mod-tools/wf_seasonal7_kit_yuki.py', A1, 1), refs)
        changed = {ref for ref in refs if self._row_changes(ref[1], ref[2])}
        self.assertEqual(set(M.INDEXED_LIVE_REFERENCES), changed)
        self.assertLessEqual(set(M.INDEXED_LIVE_REFERENCES.values()), {'edit', 'pinned', 'reference_only'})
        # 秋水 soriz 的 A3#8 donor 已改为键内按内容取：kit 与设计镜像都不再按行号引用 1399951 / 1399953。
        self.assertEqual(set(), {ref for ref in refs if 'soriz' in ref[0]})
        # 行号不变的引用（1399951 #0/#1、1399953 #0–#6）逐字不变。
        self.assertEqual(self.old_a1[:2], self.new_a1[:2])

    def test_zehr_donor_matches_only_the_pre_publish_row(self):
        old_values = M.ZEHR_DONOR_OLD_VALUES
        mismatch = lambda row: {c for c, v in old_values.items() if row[c] != v}  # noqa: E731
        self.assertEqual(set(), mismatch(self.old_a1[2]))            # 当前 live：回放通过
        self.assertIn(49, mismatch(self.new_a1[2]))                  # 发布后 #2 = 724 行（c49 '' ≠ 'Yellow'）
        self.assertEqual('724', self.new_a1[2][M.CONTENT])
        # 改指搬走后的 1399953#7 也不行：c0 / c6 / c9–c11 已变（Fever 挪到 c13）。
        self.assertEqual({0, 6, 9, 10, 11}, mismatch(self.new_a3[7]))
        self.assertEqual(self.old_a1[2][27:], self.new_a3[7][27:])
        plan = ROOT / 'work/character_packs/seasonal7-20260916/revision-20260916/zehr/plan.json'
        if plan.is_file():
            entry = json.loads(plan.read_bytes())['tables']['ability']['keys']['1599975'][1]
            self.assertEqual(f'ability LIVE:{A1}#2', entry['donor'])
            self.assertEqual({str(c): v for c, v in old_values.items()}, entry['old_values'])

    def test_content_donor_sees_the_same_724_row_before_and_after(self):
        # 秋水 soriz 在 1399951 内按内容取「第一条 ck=724」：发布前后都只有这一条，逐字相同（行号 #4 → #2）。
        rows_724 = lambda rows: [(i, row) for i, row in enumerate(rows) if row[M.CONTENT] == '724']  # noqa: E731
        (old_i, old_row), = rows_724(self.old_a1)
        (new_i, new_row), = rows_724(self.new_a1)
        self.assertEqual((4, 2), (old_i, new_i))
        self.assertEqual(old_row, new_row)

    def test_pinned_references_are_frozen_in_their_kit(self):
        import wf_seasonal7_kit_zehr as Z
        pinned = [ref for ref, status in M.INDEXED_LIVE_REFERENCES.items() if status == 'pinned']
        self.assertEqual([('work/character_packs/seasonal7-20260916/revision-20260916/zehr/plan.json', A1, 2)], pinned)
        donor = f'ability LIVE:{A1}#2'
        spec = Z.FROZEN_DONORS[Z.parse_donor(donor)]
        frozen = Z.frozen_donor_row(spec, donor)          # 核对 sha256
        self.assertEqual(self.old_a1[2], frozen)           # 冻结行 = 发布前 live #2（本模块基线）
        self.assertNotEqual(self.new_a1[2], frozen)        # 发布后 #2 已是 724 行 ⇒ 必须钉，不能读 live

    def test_notes_list_every_cross_unit_edit(self):
        notes = self.out['notes']
        cross = notes['cross_unit_after_publish']
        soriz = [v for k, v in cross.items() if k.startswith('wf_gbf_kit_soriz.py')]
        zehr = [v for k, v in cross.items() if k.startswith('wf_seasonal7_kit_zehr.py') and 'zehr/plan.json' in k]
        self.assertEqual(1, len(soriz))
        self.assertEqual(1, len(zehr))
        self.assertIn('{mode=I,ck=724}', soriz[0])                     # 已改按内容取
        self.assertIn('FROZEN_DONORS', zehr[0])                        # 已钉冻结行
        self.assertIn('1399953#7', zehr[0])                            # 明确不能改指
        # 「edit」= 须与本单元发布同批改的引用，必须一一列进 needed_edits_elsewhere；现无。
        needed = notes['needed_edits_elsewhere']
        edits = [path for (path, _, _), status in M.INDEXED_LIVE_REFERENCES.items() if status == 'edit']
        self.assertEqual(bool(edits), bool(needed))
        listed_needed = json.dumps(needed, ensure_ascii=False)
        listed_cross = json.dumps(cross, ensure_ascii=False)
        for (path, key, index), status in M.INDEXED_LIVE_REFERENCES.items():
            name = path.rsplit('/', 1)[-1]
            if status == 'edit':
                self.assertIn(name, listed_needed, path)
            elif status == 'pinned':
                self.assertIn(name, listed_cross, path)
            else:
                self.assertTrue(any(name in k for k in notes['reference_only']), path)
        self.assertIn('INDEXED_LIVE_REFERENCES', notes['cross_unit_landing'])
        self.assertIn('revision-20260927b.json', notes['staging'])     # 暂存会覆盖第二批稻穗回写证据

    def test_module_contract_constants(self):
        self.assertEqual(('139995', 'fox_oracle_autumn'), (M.CID, M.CODE))
        self.assertEqual(['fox_oracle_autumn'], M.PACKAGES)
        self.assertEqual({'fox_oracle_autumn': '0.20260927.2'}, M.PACKAGE_VERSION)
        self.assertEqual({}, M.REVIEWED_DRIFT)
        self.assertEqual(('1399951', '1399953', '1399956', '139995'), (A1, A3, A6, M.LEADER))
        blocks = wf_describe.layout('ability')['blocks']
        self.assertEqual((M.PRE1, M.PRE2, M.PRE3, M.TRIGGER, M.CONTENT),
                         (blocks['precondition1'], blocks['precondition2'], blocks['precondition3'],
                          blocks['instant_trigger'], blocks['instant_content']))
        self.assertEqual(M.TRIGGER + 8, M.COOLTIME)
        notes = self.out['notes']
        self.assertFalse(notes['runtime_verified'])
        self.assertIn('作者 2026-09-27 追加', notes['spec'])
        json.dumps(notes, ensure_ascii=False)

    # ------------------------------------------------------------ 候选（本机工作区）

    @unittest.skipUnless((WORKSPACE / 'package/manifest.json').is_file()
                         and (ROOT / 'mod-tools/profiles.json').is_file(),
                         'local candidate workspace required')
    def test_candidate_splices_only_the_reviewed_keys_dry(self):
        from wf_character_revision import RevisionCandidate
        import wf_share_update_codec as X
        manifest = WORKSPACE / 'package/manifest.json'
        before = manifest.read_bytes()
        current = tuple(map(int, json.loads(before)['package_version'].split('.')))
        mine = M.PACKAGE_VERSION[M.PACKAGES[0]]
        candidate = RevisionCandidate(
            ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE, snapshot_key=SNAPSHOT,
            package_version=mine, reviewed_input_drift=M.REVIEWED_DRIFT, baseline_factory=lambda *a, **k: None)
        old_table = X.unpack(candidate.read('common', ABILITY_TABLE))
        cand_a1, cand_a3 = X.csv_read(old_table[A1]), X.csv_read(old_table[A3])
        if cand_a3 == self.new_a3:
            # 已回写：候选 = 本模块输出，版本不低于本模块。
            self.assertEqual(self.new_a1, cand_a1)
            self.assertGreaterEqual(current, tuple(map(int, mine.split('.'))))
        else:
            self.assertGreater(tuple(map(int, mine.split('.'))), current)
            # 暂存前：1399953 与 live 逐字相同；1399951 只差 1.4.864 未回写的 #5 c51/c52。
            self.assertEqual(self.old_a3, cand_a3)
            self.assertEqual(6, len(cand_a1))
            for index, (cand, live) in enumerate(zip(cand_a1, self.old_a1)):
                want = {51: ('10000', '5000'), 52: ('10000', '5000')} if index == 5 else {}
                self.assertEqual(want, _diff(cand, live), index)
        candidate.splice(ABILITY_TABLE, self.out['ability'])
        new_table = X.unpack(candidate.read('common', ABILITY_TABLE))
        self.assertEqual(self.new_a1, X.csv_read(new_table[A1]))
        self.assertEqual(self.new_a3, X.csv_read(new_table[A3]))
        self.assertEqual({k: v for k, v in old_table.items() if k not in (A1, A3)},
                         {k: v for k, v in new_table.items() if k not in (A1, A3)})
        evidence = candidate.finish({'dry_run': True}, apply=False)
        self.assertFalse(evidence['applied'])
        self.assertEqual([ABILITY_TABLE], [f['logical_path'] for f in evidence['changed_files']])
        self.assertEqual(before, manifest.read_bytes())


if __name__ == '__main__':
    unittest.main()
