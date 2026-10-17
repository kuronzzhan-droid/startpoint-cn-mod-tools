"""稻穗 139995 2026-09-27 第二批：余辉每层队长行 ×1/5、能力4 雷队眩晕蓄积 300%→50%、双段 PF 削韧顶到 15/20/25。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_balance_20260927b_inaho as M
import wf_describe
import wf_dsl
import wf_mod_tool as core
import wf_share_update_codec as X
from wf_character_revision import encode_tree
from wf_client_description_legality import description_compatibility_problems
from wf_client_legality import (CUSTOM_ABILITY_STRING_KIND, PANEL_OVERRIDE_V1,
                                action_dsl_element_problems, action_dsl_hit_area_target_problems,
                                action_dsl_lookup_scope_problems, action_dsl_subject_binding_problems,
                                client_legality_problems, declared_block_field_problems,
                                invoke_skill_string_problems, required_client_capabilities)
from wf_midautumn_kitlib import panel_problems

FIXTURE = Path(__file__).parent / 'fixtures/balance_20260927b_inaho.json'
WORKSPACE = ROOT / 'work/character_packs' / M.PACKAGES[0]
LEADER_TABLE = 'master/ability/leader_ability.orderedmap'
ABILITY_TABLE = 'master/ability/ability.orderedmap'
CAS_TABLE = 'master/string/custom_ability_string.orderedmap'
SNAPSHOT = 'revision_20260927b'
PROGRAMS = [M.PF_PROGRAMS[level] for level in (1, 2, 3)]
UNTOUCHED_LEADER_ROWS = (0, 2, 3, 7, 8, 10)


def _key(kind, key):
    return '|'.join(key) if kind == 'table' else key


def _diff(a, b):
    return {c: (x, y) for c, (x, y) in enumerate(zip(a, b)) if x != y}


def _json_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


class InahoBalance20260927bTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(FIXTURE.read_bytes())
        cls.inputs, cls.donors = data['inputs'], data['donors']
        cls.out = M.revise(cls.read_from(cls.inputs))
        cls.old_leader = cls.inputs['leader'][M.LEADER]
        cls.new_leader = cls.out['leader'][M.LEADER]
        cls.old_a4 = cls.inputs['ability'][M.ABILITY4]
        cls.new_a4 = cls.out['ability'][M.ABILITY4]

    @staticmethod
    def read_from(inputs):
        return lambda kind, key: inputs[kind][_key(kind, key)]

    # ------------------------------------------------------------ 基线与输出形状

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(want, M.digest(self.inputs[kind][_key(kind, key)]), (kind, key))
        self.assertEqual({'leader', 'ability', 'cas', 'table', 'dsl'}, set(self.inputs))
        self.assertEqual('2', self.donors['character:139995'][0][3])  # 雷（0 基）
        self.assertEqual(2, M.ELEMENT)

    def test_only_reviewed_cells_change(self):
        self.assertEqual({'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl',
                          'server_text', 'new_programs', 'notes'}, set(self.out))
        self.assertEqual({M.ABILITY4}, set(self.out['ability']))
        self.assertEqual({M.LEADER}, set(self.out['leader']))
        self.assertEqual({M.PANEL}, set(self.out['cas']))
        self.assertEqual(set(PROGRAMS), set(self.out['dsl']))
        for kind in ('text', 'table', 'action', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)
        self.assertEqual([], self.out['new_programs'])
        seen = {i: _diff(a, b) for i, (a, b) in enumerate(zip(self.old_leader, self.new_leader))
                if a != b}
        self.assertEqual({
            1: {111: ('40000', '8000'), 112: ('40000', '8000')},
            4: {111: ('160000', '32000'), 112: ('160000', '32000')},
            5: {111: ('160000', '32000'), 112: ('160000', '32000')},
            6: {111: ('160000', '32000'), 112: ('160000', '32000')},
            9: {111: ('5000', '1000'), 112: ('5000', '1000')},
        }, seen)
        seen = {i: _diff(a, b) for i, (a, b) in enumerate(zip(self.old_a4, self.new_a4)) if a != b}
        self.assertEqual({1: {113: ('300000', '50000'), 114: ('300000', '50000')}}, seen)
        self.assertEqual((11, 2), (len(self.new_leader), len(self.new_a4)))

    # ------------------------------------------------------------ 成长（口径 A）

    def test_afterglow_per_layer_rows_are_slowed_to_one_fifth_in_place(self):
        per_layer = [i for i, r in enumerate(self.new_leader)
                     if r[3] == '1' and r[95] == '134' and r[102] == M.AFTERGLOW]
        self.assertEqual([1, 4, 5, 6, 9], per_layer)
        for index, (kind, target, token, old, new) in M.GROWTH.items():
            row = self.new_leader[index]
            with self.subTest(row=index + 1):
                self.assertEqual((kind, target, token), (row[107], row[108], row[109]))
                self.assertEqual([new, new], row[111:113])
                self.assertEqual(int(old), int(new) * 5)
                # 仍是永久、不封顶的队长成长：只改强度，不加限次/层上限。
                self.assertEqual(('(None)', M.AFTERGLOW, '100000'), (row[100], row[102], row[98]))
                self.assertEqual(self.old_leader[index][:111], row[:111])
                self.assertEqual(self.old_leader[index][113:], row[113:])
        lines = wf_describe.describe_rows(self.new_leader, 'leader_ability')
        self.assertTrue(lines[1].endswith('赋予全队(雷) Fever点 8%'), lines[1])
        self.assertTrue(lines[4].endswith('自身 强化弹射伤害 32%'), lines[4])
        self.assertTrue(lines[5].endswith('赋予全队(雷) 攻击力 32%'), lines[5])
        self.assertTrue(lines[6].endswith('赋予全队(雷) 能力伤害 32%'), lines[6])
        self.assertTrue(lines[9].endswith('自身 独立乘区强化弹射伤害 1%'), lines[9])

    def test_three_minute_totals_follow_the_design(self):
        # 设计稿：原按 18 层（每层 160%）→ 2880%；新按约 16 层（每层 32%）→ 512%。
        self.assertEqual(18 * 160, 2880)
        self.assertEqual(16 * int(self.new_leader[5][111]) // 1000, 512)
        self.assertEqual(16 * int(self.new_leader[1][111]) // 1000, 128)   # 雷队 Fever 获得量
        self.assertEqual(16 * int(self.new_leader[9][111]) // 1000, 16)    # 独立 PF

    def test_layer_sources_behind_the_frequency_estimate(self):
        # 当队长：每次进 Fever，队长行11 与能力1 行4 各给余辉 +1（同 unique 相加）⇒ 每次 +2。
        leader_gain = self.new_leader[10]
        self.assertEqual(('8', '461', M.AFTERGLOW, '100000'),
                         (leader_gain[25], leader_gain[45], leader_gain[66], leader_gain[57]))
        ability_gain = self.donors['ability:1399951'][3]
        self.assertEqual(('8', '461', M.AFTERGLOW, '100000'),
                         (ability_gain[27], ability_gain[47], ability_gain[68], ability_gain[59]))
        # 余辉层上限 99（unique_condition c4），属口径 A.1「层上限 ≥99」的无上限成长。
        self.assertEqual('99', self.donors['unique_condition:1399952'][0][4])
        # 能力6 行2：余辉≥10 且非 Fever、队长时 PF → Fever 槽 +15%，阈值门控资源，不属成长。
        gate = self.donors['ability:1399956'][1]
        self.assertEqual(('186', '144', '1000000', M.AFTERGLOW, '42', '724', '15000'),
                         (gate[6], gate[13], gate[16], gate[19], gate[20], gate[47], gate[51]))

    def test_untouched_leader_rows_are_verbatim(self):
        for index in UNTOUCHED_LEADER_ROWS:
            self.assertEqual(self.old_leader[index], self.new_leader[index], index)
        # 充能暂缓：行3（进 Fever 雷队技能槽 20%，CT0）、行4（245）原样。
        self.assertEqual(('8', '0', '211', '20000'), tuple(self.new_leader[2][i] for i in (25, 33, 45, 49)))
        self.assertEqual(('722', M.PF_KEY), (self.new_leader[7][45], self.new_leader[7][80]))

    # ------------------------------------------------------------ Down（口径 B）

    def test_ability4_team_stun_accumulation_is_capped_at_fifty_percent(self):
        row = self.new_a4[M.STUN_ROW]
        self.assertEqual(('1', '4', '19', '5', 'Yellow'), tuple(row[i] for i in (5, 97, 109, 110, 111)))
        self.assertEqual(['50000', '50000'], row[113:115])
        self.assertEqual(self.old_a4[0], self.new_a4[0])
        lines = wf_describe.describe_rows(self.new_a4, 'ability')
        self.assertEqual('持续·Fever → 赋予全队(雷) 眩晕蓄积 50%', lines[1])
        self.assertEqual(wf_describe.describe_rows(self.old_a4, 'ability')[0], lines[0])

    def test_dual_pf_single_target_down_hits_the_caps_exactly(self):
        for level in (1, 2, 3):
            old = self.inputs['dsl'][M.PF_PROGRAMS[level]]
            new = self.out['dsl'][M.PF_PROGRAMS[level]]
            with self.subTest(level=level):
                self.assertAlmostEqual(M.PF_DOWN_LIVE[level], M.max_single_target_down(old))
                self.assertAlmostEqual(M.PF_DOWN_CAP[level], M.max_single_target_down(new))
        self.assertEqual({1: 15, 2: 20, 3: 25}, M.PF_DOWN_CAP)

    def test_every_new_p13_is_at_most_live_and_rises_with_level(self):
        collision = []
        for level in (1, 2, 3):
            beam, (c_old, c_new) = M.PF_DOWN[level]
            self.assertLessEqual(c_new, c_old)
            for old, new in beam:
                self.assertLessEqual(new, old)
            collision.append(c_new)
        self.assertEqual([2.1, 2.5, 3.0], collision)
        self.assertEqual(sorted(collision), collision)
        # 射击 4 段（Lv2/Lv3 同一段）新值一致；Lv3 另两段与 live 相同（未改）。
        self.assertEqual(M.PF_DOWN[2][0][1][1], M.PF_DOWN[3][0][2][1])
        self.assertEqual([(0.75, 0.75), (0.5, 0.5)], list(M.PF_DOWN[3][0][:2]))

    def test_dual_pf_changes_only_create_normal_attack_p13(self):
        for level in (1, 2, 3):
            old = self.inputs['dsl'][M.PF_PROGRAMS[level]]
            new = self.out['dsl'][M.PF_PROGRAMS[level]]
            with self.subTest(level=level):
                old_attacks = list(wf_dsl.iter_dsl_commands(old, 'CreateNormalAttack'))
                new_attacks = list(wf_dsl.iter_dsl_commands(new, 'CreateNormalAttack'))
                self.assertEqual(len(old_attacks), len(new_attacks))
                for a, b in zip(old_attacks, new_attacks):
                    self.assertEqual({c for c in range(len(a)) if a[c] != b[c]} - {13}, set())
                    self.assertEqual(1, len(b[13]))
                    self.assertEqual(b[13][0]['min'], b[13][0]['max'])  # SLv {min,max} 同改
                restored = deepcopy(new)
                for attack, original in zip(wf_dsl.iter_dsl_commands(restored, 'CreateNormalAttack'),
                                            old_attacks):
                    attack[13] = deepcopy(original[13])
                self.assertEqual(_json_sha(old), _json_sha(restored))  # 其余节点逐字保留（含数值类型）
                changed = sum(a[13] != b[13] for a, b in zip(old_attacks, new_attacks))
                self.assertEqual({1: 9, 2: 10, 3: 9}[level], changed)

    def test_dual_pf_trees_pass_the_four_dsl_gates_and_roundtrip(self):
        for program in PROGRAMS:
            tree = self.out['dsl'][program]
            with self.subTest(program=program):
                self.assertEqual([], M.dsl_problems(tree))
                self.assertEqual([], action_dsl_element_problems(tree, M.ELEMENT))
                self.assertEqual([], action_dsl_subject_binding_problems(tree))
                self.assertEqual([], action_dsl_lookup_scope_problems(tree))
                self.assertEqual([], action_dsl_hit_area_target_problems(tree))
                raw = encode_tree(tree)
                back = wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']
                self.assertEqual(_json_sha(tree), _json_sha(back))

    # ------------------------------------------------------------ 面板

    def test_leader_panel_numbers_follow_the_rows(self):
        text = self.out['cas'][M.PANEL][0][0]
        self.assertEqual([[M.NEW_PANEL]], self.out['cas'][M.PANEL])
        lines = text.split('\n')
        self.assertEqual(6, len(lines))
        last = lines[-1]
        leader = self.new_leader
        self.assertIn(f'FEVER获得量提升{int(leader[1][111]) // 1000}％', last)
        self.assertIn(f'、强化弹射伤害提升{int(leader[4][111]) // 1000}％', last)
        self.assertIn(f'独立乘区的强化弹射伤害提升{int(leader[9][111]) // 1000}％', last)
        self.assertEqual(int(leader[5][111]), int(leader[6][111]))
        self.assertIn(f'攻击力与能力伤害提升{int(leader[5][111]) // 1000}％', last)
        self.assertEqual(['8', '32', '1', '32'], re.findall(r'(\d+)％', last))
        # 其余行的数字不变：160（行1）、20/20（行3/行4）、99（余辉上限）、10/15（行… 724 门）。
        self.assertEqual(M.OLD_PANEL_LINES[0], lines[0])
        self.assertEqual(M.OLD_PANEL_LINES[2:4], tuple(lines[3:5]))
        self.assertEqual(M.OLD_PANEL_LINES[1].split('／'), [lines[1], '首次进入时技能槽最大值提升20％'])
        self.assertEqual('雷属性共鸣时，首次进入FEVER模式时雷属性角色的技能槽最大值提升20％', lines[2])

    def test_leader_panel_obeys_the_panel_rules(self):
        text = M.NEW_PANEL
        self.assertEqual([], panel_problems(text))
        self.assertNotIn('／', text)
        self.assertNotIn('/', text)
        for word in ('可无限', '无上限', '自身为队长时', '觉醒后', '生命值100%以下'):
            self.assertNotIn(word, text)
        for line in text.split('\n'):
            self.assertTrue(line.startswith('雷属性共鸣时，'), line)  # 共鸣写法
        self.assertIn('（最多99层）', text)  # 本角色现有上限写法保留
        self.assertEqual([PANEL_OVERRIDE_V1],
                         required_client_capabilities(CUSTOM_ABILITY_STRING_KIND, [M.PANEL]))
        self.assertEqual([PANEL_OVERRIDE_V1], M.CAPABILITIES)

    # ------------------------------------------------------------ 门禁

    def test_every_returned_row_passes_client_gates(self):
        for kind, rows in (('leader_ability', self.new_leader), ('ability', self.new_a4)):
            for index, row in enumerate(rows):
                with self.subTest(kind=kind, row=index + 1):
                    self.assertEqual([], client_legality_problems(kind, row))
                    self.assertEqual([], declared_block_field_problems(kind, row))
                    self.assertEqual([], invoke_skill_string_problems(row, set(), kind))
                    self.assertEqual([], description_compatibility_problems(kind, row))
                    self.assertEqual([], required_client_capabilities(kind, row))
                    self.assertEqual([], M.row_problems(kind, row))

    def test_live_drift_is_rejected_and_inputs_are_not_mutated(self):
        original = deepcopy(self.inputs)
        M.revise(self.read_from(self.inputs))
        self.assertEqual(original, self.inputs)
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.inputs)
            value = drifted[kind][_key(kind, key)]
            if kind == 'dsl':
                value[10] = 4
            else:
                value[0][-1] += 'x'
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                M.revise(self.read_from(drifted))
            missing = deepcopy(self.inputs)
            missing[kind][_key(kind, key)] = None
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                M.revise(self.read_from(missing))

    def test_already_revised_live_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live['leader'].update(deepcopy(self.out['leader']))
        live['ability'].update(deepcopy(self.out['ability']))
        live['cas'].update(deepcopy(self.out['cas']))
        live['dsl'].update(deepcopy(self.out['dsl']))
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            M.revise(self.read_from(live))
        # 纯函数层面同样拒绝自身输出。
        with self.assertRaises(ValueError):
            M.leader_rows(self.new_leader)
        with self.assertRaises(ValueError):
            M.ability4_rows(self.new_a4)
        with self.assertRaises(ValueError):
            M.panel_rows(self.out['cas'][M.PANEL])
        for level in (1, 2, 3):
            with self.assertRaises(ValueError):
                M.pf_tree(self.out['dsl'][M.PF_PROGRAMS[level]], level)

    def test_row_and_tree_preimage_guards_fail_closed(self):
        leader_cases = {'strength': (1, 111, '30000'), 'target': (4, 108, '5'),
                        'layer cap added': (5, 100, '10'), 'other unique': (6, 102, '1399951'),
                        'precondition': (9, 4, '0'), 'pf override moved': (7, 45, '')}
        for name, (index, col, value) in leader_cases.items():
            rows = deepcopy(self.old_leader)
            rows[index][col] = value
            with self.subTest(name), self.assertRaises(ValueError):
                M.leader_rows(rows)
        with self.assertRaises(ValueError):
            M.leader_rows(self.old_leader[:10])
        for col, value in ((113, '100000'), (110, '0'), (97, '1'), (1, 'false')):
            rows = deepcopy(self.old_a4)
            rows[M.STUN_ROW][col] = value
            with self.subTest(ability4=col), self.assertRaises(ValueError):
                M.ability4_rows(rows)
        with self.assertRaises(ValueError):
            M.panel_rows([[M.OLD_PANEL + '\n']])
        tree = deepcopy(self.inputs['dsl'][M.PF_PROGRAMS[2]])
        next(wf_dsl.iter_dsl_commands(tree, 'CreateNormalAttack'))[13] = [{'min': 5, 'max': 4}]
        with self.assertRaisesRegex(ValueError, 'collision p13 drift'):
            M.pf_tree(tree, 2)
        tree = deepcopy(self.inputs['dsl'][M.PF_PROGRAMS[3]])
        tree[11][1].append(deepcopy(tree[11][1][4]))
        with self.assertRaisesRegex(ValueError, 'top-level nodes'):
            M.pf_tree(tree, 3)
        for kind, fn, arg in (('leader', M.leader_rows, self.old_leader),
                              ('ability', M.ability4_rows, self.old_a4)):
            before = deepcopy(arg)
            fn(arg)
            self.assertEqual(before, arg, kind)
        before = deepcopy(self.inputs['dsl'])
        for level in (1, 2, 3):
            M.pf_tree(self.inputs['dsl'][M.PF_PROGRAMS[level]], level)
        self.assertEqual(before, self.inputs['dsl'])

    # ------------------------------------------------------------ 生成器

    def test_generator_is_this_module_and_old_generators_stay_locked(self):
        # 本模块的纯函数就是这些键的现行生成源。
        self.assertEqual(M.leader_rows(self.old_leader), self.new_leader)
        self.assertEqual(M.ability4_rows(self.old_a4), self.new_a4)
        self.assertEqual(M.panel_rows(self.inputs['cas'][M.PANEL]), self.out['cas'][M.PANEL])
        for level in (1, 2, 3):
            self.assertEqual(M.pf_tree(self.inputs['dsl'][M.PF_PROGRAMS[level]], level),
                             self.out['dsl'][M.PF_PROGRAMS[level]])
        # 历史链：双段 PF 的 R3 对 live 是 no-op（已完成态），对本模块输出拒绝（不会回退）。
        import wf_newchars_r3_data as r3
        for level in (1, 2, 3):
            live = self.inputs['dsl'][M.PF_PROGRAMS[level]]
            self.assertEqual(live, r3.inaho_power_flip(live, level))
            with self.assertRaises(ValueError):
                r3.inaho_power_flip(self.out['dsl'][M.PF_PROGRAMS[level]], level)
        # 队长 / 能力4 的历史生成器都锁输入哈希：新旧两态都不在锁定集合里。
        import wf_inaho_fever_growth_data
        import wf_inaho_growth_detail_data
        import wf_inaho_native_pf_r2
        import wf_inaho_pf3_balance
        for rows in (self.old_leader, self.new_leader):
            with self.assertRaises(ValueError):
                r3.inaho_leader(core.write_csv_lines(rows))
        leader_locked = {wf_inaho_native_pf_r2.LEADER_BASE, *r3.LEADER_HASHES,
                         wf_inaho_fever_growth_data.OLD['139995'], wf_inaho_fever_growth_data.NEW['139995'],
                         wf_inaho_growth_detail_data.OLD['139995'], wf_inaho_growth_detail_data.NEW['139995']}
        ability_locked = {wf_inaho_pf3_balance.BASE_HASHES['1399954']}
        for rows, locked in ((self.old_leader, leader_locked), (self.new_leader, leader_locked),
                             (self.old_a4, ability_locked), (self.new_a4, ability_locked)):
            text = core.write_csv_lines(rows)
            for variant in (text, text.rstrip('\n'), text.replace('\n', '\r\n')):
                self.assertNotIn(hashlib.sha256(variant.encode()).hexdigest(), locked)
        # 队长覆盖文案在 mod-tools 下没有生成源（唯一登记是 offline_content 的键名门禁）。
        # 第三轮 wf_balance_20260927c_inaho 以本模块输出为输入改末行数值，是其后的现行写入源（其测试核对）。
        for path in (ROOT / 'mod-tools').glob('*.py'):
            if path.name in ('wf_balance_20260927b_inaho.py', 'wf_balance_20260927c_inaho.py'):
                continue
            self.assertNotIn('「余辉」每1层', path.read_text(encoding='utf-8', errors='ignore'), path.name)

    def test_module_contract_constants(self):
        self.assertEqual(('139995', 'fox_oracle_autumn'), (M.CID, M.CODE))
        self.assertEqual(['fox_oracle_autumn'], M.PACKAGES)
        self.assertEqual({'fox_oracle_autumn': '0.20260927.1'}, M.PACKAGE_VERSION)
        self.assertEqual({}, M.REVIEWED_DRIFT)
        self.assertEqual('desc_override_fox_oracle_autumn', M.PANEL)
        self.assertTrue(M.PANEL.startswith('desc_override_' + M.CODE))
        self.assertEqual([[p for p in PROGRAMS]], self.inputs['table'][_key('table', M.PF_ACTION)])
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)

    # ------------------------------------------------------------ 候选（本机工作区）

    @unittest.skipUnless((WORKSPACE / 'package/manifest.json').is_file()
                         and (ROOT / 'mod-tools/profiles.json').is_file(),
                         'local candidate workspace required')
    def test_candidate_splices_only_the_reviewed_keys_dry(self):
        from wf_character_revision import RevisionCandidate
        manifest = WORKSPACE / 'package/manifest.json'
        before = manifest.read_bytes()
        current = json.loads(before)
        mine = M.PACKAGE_VERSION[M.PACKAGES[0]]
        kwargs = dict(character_id=M.CID, code_name=M.CODE, snapshot_key=SNAPSHOT,
                      package_version=mine, baseline_factory=lambda *a, **k: None)
        candidate = RevisionCandidate(ROOT, WORKSPACE, reviewed_input_drift=M.REVIEWED_DRIFT, **kwargs)
        common = {t: X.unpack(candidate.read('common', t)) for t in (LEADER_TABLE, ABILITY_TABLE, CAS_TABLE)}
        if SNAPSHOT in current.get('snapshot', {}):
            # 已回写：候选 = 本模块输出。
            # 作者 09-27 追加（wf_balance_20260927b_inaho2，只动 1399951/1399953）同快照键继续回写，
            # 版本在本模块之上递增（0.20260927.1 → 0.20260927.2）。
            self.assertLessEqual(tuple(map(int, mine.split('.'))),
                                 tuple(map(int, current['package_version'].split('.'))))
            self.assertLessEqual(set(M.CAPABILITIES), set(current['required_capabilities']))
            # 第三轮（wf_balance_20260927c_inaho，以本模块输出为输入回调余辉每层 5 行与面板末行）回写后候选 = 第三轮输出。
            import wf_balance_20260927c_inaho as M3
            want_leader, want_panel = self.new_leader, self.out['cas'][M.PANEL]
            if X.csv_read(common[LEADER_TABLE][M.LEADER]) == M3.leader_rows(self.new_leader):
                want_leader, want_panel = M3.leader_rows(self.new_leader), M3.panel_rows(want_panel)
                self.assertLessEqual(tuple(map(int, M3.PACKAGE_VERSION[M.PACKAGES[0]].split('.'))),
                                     tuple(map(int, current['package_version'].split('.'))))
            self.assertEqual(want_leader, X.csv_read(common[LEADER_TABLE][M.LEADER]))
            self.assertEqual(self.new_a4, X.csv_read(common[ABILITY_TABLE][M.ABILITY4]))
            self.assertEqual(want_panel, X.csv_read(common[CAS_TABLE][M.PANEL]))
            for program, tree in self.out['dsl'].items():
                raw = candidate.read('common', wf_dsl.dsl_logical(program))
                self.assertEqual(_json_sha(tree),
                                 _json_sha(wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']))
            self.assertEqual(before, manifest.read_bytes())
            return
        self.assertGreater(tuple(map(int, mine.split('.'))),
                           tuple(map(int, current['package_version'].split('.'))))
        # 暂存前：ability4 / cas / 三棵 PF 树与 live 前像逐字相同；leader 候选多 1.4.864 已删的行1。
        self.assertEqual(self.old_a4, X.csv_read(common[ABILITY_TABLE][M.ABILITY4]))
        self.assertEqual(self.inputs['cas'][M.PANEL], X.csv_read(common[CAS_TABLE][M.PANEL]))
        cand_leader = X.csv_read(common[LEADER_TABLE][M.LEADER])
        self.assertEqual(12, len(cand_leader))
        self.assertEqual(self.old_leader, cand_leader[1:])
        self.assertEqual(('23', '211', '4000'), (cand_leader[0][25], cand_leader[0][45], cand_leader[0][49]))
        for program in PROGRAMS:
            raw = candidate.read('common', wf_dsl.dsl_logical(program))
            self.assertEqual(self.inputs['dsl'][program],
                             wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree'])
        candidate.splice(LEADER_TABLE, self.out['leader'])
        candidate.splice(ABILITY_TABLE, self.out['ability'])
        # cas：队长覆盖键存在于候选表但不在 claim 里，暂存脚本按命名空间认领（desc_override_<code>）。
        claim = next(t for t in candidate.manifest['tables'] if t['logical_path'] == CAS_TABLE)
        self.assertNotIn(M.PANEL, claim['outer_keys'])
        cas = X.unpack(candidate.read('common', CAS_TABLE))
        spliced = dict(cas)
        spliced.update({k: X.csv_write(v) for k, v in self.out['cas'].items()})
        candidate.emit('common', CAS_TABLE, X.pack(spliced))
        for program, tree in self.out['dsl'].items():
            candidate.emit('common', wf_dsl.dsl_logical(program), encode_tree(tree))
        for table, key in ((LEADER_TABLE, M.LEADER), (ABILITY_TABLE, M.ABILITY4), (CAS_TABLE, M.PANEL)):
            new = X.unpack(candidate.read('common', table))
            self.assertEqual({k: v for k, v in common[table].items() if k != key},
                             {k: v for k, v in new.items() if k != key}, table)
        self.assertEqual(self.new_leader, X.csv_read(X.unpack(candidate.read('common', LEADER_TABLE))[M.LEADER]))
        evidence = candidate.finish({'dry_run': True}, apply=False)
        self.assertFalse(evidence['applied'])
        self.assertEqual({LEADER_TABLE, ABILITY_TABLE, CAS_TABLE,
                          *(wf_dsl.dsl_logical(p) for p in PROGRAMS)},
                         {f['logical_path'] for f in evidence['changed_files']})
        self.assertEqual(before, manifest.read_bytes())


if __name__ == '__main__':
    unittest.main()
