# -*- coding: utf-8 -*-
"""稻穗 139995 2026-09-27 第三轮（成长复核）：余辉每层 5 条队长行回调到原值的 4/5、7/10，队长覆盖文案末行同步。

fixture = live 输入快照（``fixtures/balance_20260927c_inaho.json``，链尾 1.4.1053 只读取数），驱动 ``revise()``：
改动的前后值、档位与取整、未改行/其余列逐字保留、面板数字 == 行值、BEFORE 漂移拒绝、不改输入、对自身输出重跑拒绝、
合法性门禁为空；live 输入 == 第二批（inaho / inaho2）输出（链式核对）；秋水 soriz 的 donor 不受影响；
候选工作区干跑拼接（缺时跳过）。``_context`` 是 revise() 不读取的 live 参照（文案、能力6）。
面板同条件合并 / 共鸣省略：终稿逐字、数值稿 → 终稿过 ``mod-tools/wf_panel_merge_check.check``（仓库内校验器，硬依赖，
不跳过）、「余辉」全部来源带雷共鸣（共鸣省略依据）；``ability_fox_oracle_autumn_fever_growth`` 只刷新来源登记在 notes
（``_context.dsl`` 核对树形）。能力6 面板按主会话口径 3 把「雷属性共鸣时：」+ 换行并成一行「雷属性共鸣时，…」，
校验前在测试里显式规范化 live 原文。队长第 6 行按口径 1 扩到同形写法（A）把「FEVER获得量提升30％、强化弹射伤害」
改「，」，校验前同样在测试里显式规范化数值稿。
"""
from copy import deepcopy
import json
from pathlib import Path
import re
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_balance_20260927b_inaho as B2
import wf_balance_20260927b_inaho2 as B22
import wf_balance_20260927c_inaho as M
import wf_describe
from wf_client_description_legality import description_compatibility_problems
from wf_client_legality import (CUSTOM_ABILITY_STRING_KIND, PANEL_OVERRIDE_V1, client_legality_problems,
                                declared_block_field_problems, invoke_skill_string_problems,
                                required_client_capabilities)
from wf_midautumn_kitlib import panel_problems
from wf_panel_merge_check import check as check_merge

FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927c_inaho.json'
B2_FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_inaho.json'
B22_FIXTURE = Path(__file__).resolve().parents[3] / "private-assets/tests/fixtures" / 'balance_20260927b_inaho2.json'
WORKSPACE = ROOT / 'work/character_packs' / M.PACKAGES[0]
LEADER_TABLE = 'master/ability/leader_ability.orderedmap'
CAS_TABLE = 'master/string/custom_ability_string.orderedmap'
UNTOUCHED_LEADER_ROWS = (0, 2, 3, 7, 8, 10)
FINAL_PANEL_LINES = [
    '雷属性共鸣时，战斗开始时自身FEVER获得量提升160％',
    '雷属性共鸣时，FEVER模式开始时雷属性角色的技能槽增加20％',
    '雷属性共鸣时，首次进入FEVER模式时雷属性角色的技能槽最大值提升20％',
    '雷属性共鸣时，每进入一次FEVER模式「余辉」累积1层（最多99层）',
    '「余辉」10层以上且非FEVER模式中，强化弹射时FEVER槽增加15％',
    '「余辉」每1层：雷属性角色的FEVER获得量提升30％，强化弹射伤害提升110％、独立乘区的强化弹射伤害提升3.5％、'
    '雷属性角色的攻击力与能力伤害提升130％',
]
PANEL6 = 'desc_override_fox_oracle_autumn_6'
FINAL_PANEL6 = '雷属性共鸣时，FEVER模式中，独立乘区的强化弹射伤害提升30％'
FEVER_GROWTH = ('battle/action/skill/action/ability_skill/ability_fox_oracle_autumn_fever_growth'
                '$ability_fox_oracle_autumn_fever_growth')


def normalize_pf_damage_join(text):
    """主会话口径 1 扩到同形写法 A（测试侧独立写出）：带对象的效果后面「、强化弹射伤害」→「，强化弹射伤害」。
    稻穗队长只有第 6 行「FEVER获得量提升30％、强化弹射伤害」这一处；「、独立乘区的强化弹射伤害」前一项不带对象，不动。"""
    return text.replace('FEVER获得量提升30％、强化弹射伤害', 'FEVER获得量提升30％，强化弹射伤害')


def normalize_resonance_colon(text):
    """主会话口径 3（测试侧独立写出）：「X属性共鸣时：」后换行接效果的并成一行，其余「X属性共鸣时：」改「，」。"""
    text = re.sub(r'([火水雷风光暗]属性共鸣时)[：:]\n', r'\1，', text)
    return re.sub(r'([火水雷风光暗]属性共鸣时)[：:]', r'\1，', text)


def load():
    data = json.loads(FIXTURE.read_text(encoding='utf-8'))
    return {k: v for k, v in data.items() if not k.startswith('_')}, data['_context']


def reader(inputs):
    def read(kind, key):
        if key not in inputs.get(kind, {}):
            raise KeyError(f'{kind}:{key}')
        return inputs[kind][key]
    return read


def _diff(a, b):
    return {c: (x, y) for c, (x, y) in enumerate(zip(a, b)) if x != y}


def version(text):
    return tuple(map(int, text.split('.')))


class InahoBalance20260927cTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs, cls.context = load()
        cls.out = M.revise(reader(deepcopy(cls.inputs)))
        cls.old_leader = cls.inputs['leader'][M.LEADER]
        cls.new_leader = cls.out['leader'][M.LEADER]

    # ------------------------------------------------------------ 基线与输出形状

    def test_fixture_is_the_reviewed_baseline(self):
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(want, M.digest(self.inputs[kind][key]), (kind, key))
        self.assertEqual({(kind, key) for kind, keys in self.inputs.items() for key in keys}, set(M.BEFORE))

    def test_live_input_is_the_batch2_output(self):
        """链式核对：live 1.4.1053 的队长/面板 == 第二批 inaho 输出，能力3 == inaho2 输出。"""
        data = json.loads(B2_FIXTURE.read_bytes())['inputs']
        b2 = B2.revise(lambda kind, key: data[kind]['|'.join(key) if kind == 'table' else key])
        self.assertEqual(self.old_leader, b2['leader'][M.LEADER])
        self.assertEqual(self.inputs['cas'][M.PANEL], b2['cas'][M.PANEL])
        data2 = json.loads(B22_FIXTURE.read_bytes())['inputs']
        b22 = B22.revise(reader(data2))
        self.assertEqual(self.inputs['ability'][M.ABILITY3], b22['ability'][M.ABILITY3])
        self.assertEqual(self.old_leader, data2['leader'][M.LEADER])       # inaho2 只读队长，未改

    def test_only_reviewed_cells_change(self):
        self.assertEqual({M.LEADER}, set(self.out['leader']))
        self.assertEqual({M.PANEL, M.PANEL6}, set(self.out['cas']))
        self.assertEqual(PANEL6, M.PANEL6)
        for kind in ('ability', 'text', 'table', 'action', 'dsl', 'server_text'):
            self.assertEqual({}, self.out[kind], kind)
        self.assertEqual([], self.out['new_programs'])
        seen = {i: _diff(a, b) for i, (a, b) in enumerate(zip(self.old_leader, self.new_leader)) if a != b}
        self.assertEqual({
            1: {111: ('8000', '30000'), 112: ('8000', '30000')},
            4: {111: ('32000', '110000'), 112: ('32000', '110000')},
            5: {111: ('32000', '130000'), 112: ('32000', '130000')},
            6: {111: ('32000', '130000'), 112: ('32000', '130000')},
            9: {111: ('1000', '3500'), 112: ('1000', '3500')},
        }, seen)
        self.assertEqual(11, len(self.new_leader))
        for index in UNTOUCHED_LEADER_ROWS:
            self.assertEqual(self.old_leader[index], self.new_leader[index], index)

    # ------------------------------------------------------------ 档位与取整

    def test_tiers_and_rounding_follow_the_table(self):
        want = {1: ('40000', (4, 5), '30000'), 4: ('160000', (7, 10), '110000'),
                5: ('160000', (4, 5), '130000'), 6: ('160000', (4, 5), '130000'),
                9: ('5000', (7, 10), '3500')}
        for index, (original, factor, new) in want.items():
            with self.subTest(row=index):
                self.assertEqual((original, factor, new),
                                 (M.GROWTH[index][0], M.GROWTH[index][3], M.GROWTH[index][2]))
                self.assertEqual(new, M.rounded_growth(original, factor))
                self.assertGreaterEqual(int(new) * 3, int(original) * 2)          # 不低于 2/3
                self.assertEqual(B2.GROWTH[index][3], original)                   # 第二批前原值
                self.assertEqual(B2.GROWTH[index][4], M.GROWTH[index][1])         # 第二批 live 值
                if int(original) >= 20000:
                    self.assertEqual(0, int(new) % 5000)                          # 5 的倍数
                else:
                    self.assertEqual(0, int(new) % 500)                           # <10% 取 0.5（口径 D2）

    def test_rows_keep_their_afterglow_shape(self):
        for index, (kind, target, token, _old, _new) in B2.GROWTH.items():
            row = self.new_leader[index]
            with self.subTest(row=index):
                self.assertEqual((kind, target, token), (row[107], row[108], row[109]))
                self.assertEqual([M.GROWTH[index][2]] * 2, row[111:113])
                self.assertEqual(('(None)', M.AFTERGLOW, '100000', '134'), (row[100], row[102], row[98], row[95]))
                self.assertEqual(('2', '600000', 'Yellow'), (row[4], row[7], row[9]))    # 雷编成≥6，不新增前置
                self.assertEqual(self.old_leader[index][:111], row[:111])
                self.assertEqual(self.old_leader[index][113:], row[113:])
        lines = wf_describe.describe_rows(self.new_leader, 'leader_ability')
        self.assertTrue(lines[1].endswith('赋予全队(雷) Fever点 30%'), lines[1])
        self.assertTrue(lines[4].endswith('自身 强化弹射伤害 110%'), lines[4])
        self.assertTrue(lines[5].endswith('赋予全队(雷) 攻击力 130%'), lines[5])
        self.assertTrue(lines[6].endswith('赋予全队(雷) 能力伤害 130%'), lines[6])
        self.assertTrue(lines[9].endswith('自身 独立乘区强化弹射伤害 3.5%'), lines[9])

    def test_afterglow_sources_are_leader10_and_ability3_last_row(self):
        """数值表 L#1 触发描述已过期（能力1#3 已搬到能力3 末行）；两源相加 ⇒ 当队长每次进 Fever +2。"""
        a3 = self.inputs['ability'][M.ABILITY3]
        self.assertEqual(['leader#10', f'{M.ABILITY3}#8'], M.afterglow_sources(self.old_leader, a3))
        self.assertEqual(9, len(a3))
        gain = a3[M.A3_GAIN_ROW]
        self.assertEqual(('8', '461', M.AFTERGLOW, '2', 'Yellow'), (gain[27], gain[47], gain[68], gain[6], gain[11]))
        self.assertEqual(self.out['notes']['afterglow_sources']['rows'], ['leader#10', f'{M.ABILITY3}#8'])
        # 能力6 #1（余辉≥10、非 Fever、仅队长）只读门槛，不属成长，不动。
        gate = self.context['ability']['1399956'][1]
        self.assertEqual(('42', '724', M.AFTERGLOW), (gate[20], gate[47], gate[19]))

    def test_three_minute_totals_follow_the_table(self):
        totals = self.out['notes']['three_minutes_16_layers']
        self.assertEqual({'original': '640%', 'batch2': '128%', 'batch3': '480%'}, totals['#1'])
        self.assertEqual('1760%', totals['#4']['batch3'])
        self.assertEqual('2080%', totals['#5']['batch3'])
        self.assertEqual('56%', totals['#9']['batch3'])

    # ------------------------------------------------------------ 面板

    def test_leader_panel_numbers_follow_the_rows(self):
        old = self.inputs['cas'][M.PANEL][0][0].split('\n')
        new = self.out['cas'][M.PANEL][0][0].split('\n')
        self.assertEqual(6, len(new))
        self.assertEqual(old[:4], new[:4])                                    # 前 4 行逐字不变
        self.assertEqual(old[4], M.RESONANCE_PREFIX + new[4])                 # 第 5 行只删共鸣前缀
        self.assertEqual(list(M.NUMERIC_PANEL_LINES[:5]), old[:5])            # 数值稿：只换末行
        leader = self.new_leader
        pct = lambda value: f'{int(value) / 1000:g}'                          # noqa: E731
        last = new[-1]
        self.assertIn(f'FEVER获得量提升{pct(leader[1][111])}％', last)
        self.assertIn(f'，强化弹射伤害提升{pct(leader[4][111])}％', last)            # 口径 1（A）：「，」不补对象
        self.assertIn(f'独立乘区的强化弹射伤害提升{pct(leader[9][111])}％', last)
        self.assertEqual(leader[5][111], leader[6][111])
        self.assertIn(f'攻击力与能力伤害提升{pct(leader[5][111])}％', last)
        self.assertEqual(['30', '110', '3.5', '130'], re.findall(r'(\d+(?:\.\d+)?)％', last))
        self.assertEqual(old[-1], B2.NEW_PANEL_LINES[-1])
        self.assertEqual([[M.NEW_PANEL]], self.out['cas'][M.PANEL])

    def test_leader_panel_obeys_the_panel_rules(self):
        text = M.NEW_PANEL
        self.assertEqual([], panel_problems(text))
        self.assertEqual([], M.panel_gate_problems(text))
        for word in ('／', '/', '可无限', '无上限', '自身为队长时', '觉醒后', '生命值100%以下'):
            self.assertNotIn(word, text)
        for index, line in enumerate(text.split('\n')):
            if index in M.PREFIX_DROP_LINES:                                  # 「余辉」效果行：共鸣省略
                self.assertFalse(line.startswith('雷属性共鸣时'), line)
                self.assertTrue(line.startswith('「余辉」'), line)
            else:
                self.assertTrue(line.startswith('雷属性共鸣时，'), line)
        self.assertNotIn('共鸣时：', text)
        self.assertIn('（最多99层）', text)
        self.assertEqual([PANEL_OVERRIDE_V1], required_client_capabilities(CUSTOM_ABILITY_STRING_KIND, [M.PANEL]))
        self.assertEqual([PANEL_OVERRIDE_V1], M.CAPABILITIES)

    def test_texts_do_not_carry_the_growth_numbers(self):
        texts = [cell for row in self.context['text'][M.CID] for cell in row]
        texts += [cell for row in self.context['server_text'][M.CID] for cell in row]
        texts += [fields[1] for _k, fields in self.context['action'][M.CODE]]
        for text in texts:
            for word in ('余辉', '30％', '110％', '130％', '3.5％'):
                self.assertNotIn(word, text)

    # ------------------------------------------------------------ 面板同条件合并 / 共鸣省略

    def test_final_panel_is_verbatim(self):
        self.assertEqual(FINAL_PANEL_LINES, self.out['cas'][M.PANEL][0][0].split('\n'))
        self.assertEqual(tuple(FINAL_PANEL_LINES), M.NEW_PANEL_LINES)
        # 终稿 = 数值稿逐行，只在第 5/6 行删行首「雷属性共鸣时，」、第 6 行按口径 1（A）改一个「、」为「，」，
        # 其余字面逐字保留、行序不变。
        for index, (numeric, final) in enumerate(zip(M.NUMERIC_PANEL_LINES, FINAL_PANEL_LINES)):
            want = numeric[len('雷属性共鸣时，'):] if index in (4, 5) else numeric
            if index == 5:
                want = normalize_pf_damage_join(want)
            self.assertEqual(want, final, index)
        # 第 4 行（余辉获取行）保留共鸣；「累积1层」照旧（非队长 1 层 / 队长 2 层是作者确认的设计）。
        self.assertEqual(M.NUMERIC_PANEL_LINES[3], FINAL_PANEL_LINES[3])
        self.assertIn('「余辉」累积1层（最多99层）', FINAL_PANEL_LINES[3])

    def test_resonance_omission_basis(self):
        """「余辉」全部获取来源（队长 #10、能力3 #8，全表 + DSL 扫描无其他来源）都带雷共鸣；删前缀的两行效果依赖「余辉」。"""
        a3 = self.inputs['ability'][M.ABILITY3]
        self.assertEqual({M.AFTERGLOW}, set(M.RESONANCE_OMISSION))
        basis = M.RESONANCE_OMISSION[M.AFTERGLOW]
        self.assertEqual(('余辉', 'Yellow'), (basis['name'], basis['resonance']))
        self.assertEqual([f'leader_ability:{M.LEADER}#10', f'ability:{M.ABILITY3}#8'], basis['sources'])
        self.assertEqual(['leader#10', f'{M.ABILITY3}#8'], M.afterglow_sources(self.new_leader, a3))
        self.assertEqual(['Yellow'], M.resonance_tokens(self.new_leader[M.LEADER_GAIN_ROW], 'leader'))
        self.assertEqual(['Yellow'], M.resonance_tokens(a3[M.A3_GAIN_ROW], 'ability'))
        self.assertEqual([], M.resonance_basis_problems(self.new_leader, a3))
        # 第 6 行的数据：队长 #1/#4/#5/#6/#9 全部「持续·余辉每层」。
        self.assertEqual([1, 4, 5, 6, 9], [i for i, row in enumerate(self.new_leader) if row[102] == M.AFTERGLOW])
        # 第 5 行的数据：能力6 #1（非 Fever 且 余辉≥10 且 队长）——门槛 uid 在前置 2。
        gate = self.context['ability']['1399956'][1]
        self.assertEqual(('144', M.AFTERGLOW, '42'), (gate[13], gate[19], gate[20]))
        self.assertEqual(wf_describe.describe_rows([gate], 'ability')[0],
                         '非Fever 且 状态累积计数固有≥10[固有1399952] 且 队长 时: 强化弹射≥1 → 自身 Fever槽增减(上限比例) 15%')
        # 负对照：任一来源丢掉雷共鸣，共鸣省略不再成立，revise() 拒绝。
        sources = (('leader', M.LEADER, M.LEADER_GAIN_ROW, 4), ('ability', M.ABILITY3, M.A3_GAIN_ROW, 6))
        for table, key, index, col in sources:
            drifted = deepcopy(self.inputs)
            drifted[table][key][index][col] = '0'
            reviewed = {(table, key): M.digest(drifted[table][key])}
            with self.subTest(table=table), mock.patch.dict(M.BEFORE, reviewed):
                with self.assertRaisesRegex(ValueError, 'not gated on thunder resonance'):
                    M.revise(reader(drifted))

    def test_panel_passes_check_merge(self):
        """仓库内校验器 wf_panel_merge_check（硬依赖）。队长数值稿没有「共鸣时：」，无需口径 3 规范化；
        先按口径 1（A）显式规范化数值稿第 6 行的一个标点，再与终稿比对（第 5/6 行 = 仅删前缀）。"""
        check = check_merge
        self.assertNotIn('共鸣时：', M.NUMERIC_PANEL)
        normalized = normalize_pf_damage_join(M.NUMERIC_PANEL)
        self.assertEqual(1, sum(a != b for a, b in zip(M.NUMERIC_PANEL.split('\n'), normalized.split('\n'))))
        drops = [dict(line=5, resonance='Yellow'), dict(line=6, resonance='Yellow')]
        result = check(normalized, M.NEW_PANEL, drops)
        self.assertTrue(result['ok'], result['errors'])
        self.assertEqual([], result['warnings'])
        self.assertEqual({5: 'prefix_drop', 6: 'prefix_drop'},
                         {k: v for k, v in result['columns'][0]['kinds'].items() if v != 'verbatim'})
        # 负对照：未授权删第 4 行（获取行）的共鸣会被拒。
        bad = M.NEW_PANEL.replace('雷属性共鸣时，每进入一次', '每进入一次')
        self.assertFalse(check(normalized, bad, drops)['ok'])

    def test_pf_damage_join_follows_rule_a(self):
        """口径 1 扩到同形写法（A）：带对象的效果后面「、强化弹射伤害」→「，」；不补「自身」；413 项与带对象的后一项不动。"""
        last_before, last_after = M.DROPPED_PANEL_LINES[5], M.NEW_PANEL_LINES[5]
        self.assertEqual(last_before.replace('30％、强化弹射伤害', '30％，强化弹射伤害'), last_after)
        self.assertEqual(1, sum(a != b for a, b in zip(last_before, last_after)))          # 只动一个字符
        self.assertIn('110％、独立乘区的强化弹射伤害提升3.5％、雷属性角色的攻击力', last_after)
        self.assertNotIn('自身强化弹射伤害', last_after)
        self.assertTrue(M.pf_damage_join_problems(last_before))
        self.assertEqual([], M.pf_damage_join_problems(M.NEW_PANEL))
        self.assertEqual([], M.pf_damage_join_problems(M.NEW_PANEL6))
        # 数据：「，」前 #1 = kind 18 全队雷（带对象），后 #4 = during 23 自身（面板不补对象）；#9 = 413。
        self.assertEqual([], M.pf_damage_join_basis_problems(self.new_leader))
        self.assertEqual(('18', '5', 'Yellow'), tuple(self.new_leader[1][107:110]))
        self.assertEqual(('23', '', ''), tuple(self.new_leader[4][107:110]))
        self.assertEqual('413', self.new_leader[9][107])
        drifted = deepcopy(self.new_leader)
        drifted[4][107] = '55'
        self.assertTrue(M.pf_damage_join_basis_problems(drifted))
        # 负对照：门禁拒绝残留的「对象效果、强化弹射伤害」写法。
        self.assertTrue(M.panel_gate_problems('\n'.join(M.DROPPED_PANEL_LINES)))
        self.assertEqual({'L6'}, set(self.out['notes']['panel_merge']['pf_damage_join']['lines']))

    # ------------------------------------------------------------ 能力6 面板：口径 3（共鸣冒号 + 换行 → 一行）

    def test_ability6_panel_joins_the_resonance_colon_line(self):
        old = self.inputs['cas'][PANEL6]
        self.assertEqual([['雷属性共鸣时：\nFEVER模式中，独立乘区的强化弹射伤害提升30％']], old)
        self.assertEqual([[FINAL_PANEL6]], self.out['cas'][PANEL6])
        # 只动共鸣标点与换行：删掉「：\n」换成「，」即 live 原文，其余字面逐字不变。
        self.assertEqual(old[0][0].replace('雷属性共鸣时：\n', '雷属性共鸣时，'), FINAL_PANEL6)
        self.assertEqual(normalize_resonance_colon(old[0][0]), FINAL_PANEL6)
        self.assertEqual(M.normalize_resonance_colon(old[0][0]), FINAL_PANEL6)
        self.assertEqual(1, len(FINAL_PANEL6.split('\n')))
        self.assertTrue(FINAL_PANEL6.startswith('雷属性共鸣时，'))
        self.assertNotIn('共鸣时：', FINAL_PANEL6)
        self.assertEqual([], panel_problems(FINAL_PANEL6))
        self.assertEqual([], M.panel6_gate_problems(FINAL_PANEL6))
        self.assertEqual([PANEL_OVERRIDE_V1], required_client_capabilities(CUSTOM_ABILITY_STRING_KIND, [PANEL6]))
        # 数据：能力6 #0 雷编成≥6、持续·Fever、自身独立乘区强化弹射伤害（满级 30%，文案写单一数值）。
        row = self.context['ability']['1399956'][0]
        self.assertEqual(wf_describe.describe_rows([row], 'ability')[0],
                         '雷·编成≥6 时: 持续·Fever → 自身 独立乘区强化弹射伤害 15%→30%')
        self.assertEqual(['Yellow'], M.resonance_tokens(row, 'ability'))
        self.assertIn('30％', FINAL_PANEL6)

    def test_ability6_panel_passes_check_merge_after_explicit_normalization(self):
        """校验前先按口径 3 规范化 live 原文（冒号 + 换行 → 「，」一行），规范化后与终稿逐字相同。"""
        old = self.inputs['cas'][PANEL6][0][0]
        normalized = normalize_resonance_colon(old)
        result = check_merge(normalized, self.out['cas'][PANEL6][0][0], [])
        self.assertTrue(result['ok'], result['errors'])
        self.assertEqual([], result['warnings'])
        self.assertEqual({1: 'verbatim'}, result['columns'][0]['kinds'])
        # 负对照：顺手删掉共鸣 / 改数值都会被拒。
        self.assertFalse(check_merge(normalized, FINAL_PANEL6[len('雷属性共鸣时，'):], [])['ok'])
        self.assertFalse(check_merge(normalized, FINAL_PANEL6.replace('30％', '35％'), [])['ok'])

    def test_fever_growth_is_a_refresh_only_afterglow_source(self):
        """总核对 minor：ability_fox_oracle_autumn_fever_growth 的授予只在 ConditionExist(余辉) 成立支内，登记在 notes。"""
        registered = self.out['notes']['panel_merge']['resonance_omission_refresh_only']
        self.assertEqual(M.RESONANCE_REFRESH_ONLY, registered)
        entry, = registered[M.AFTERGLOW]
        self.assertEqual(FEVER_GROWTH, entry['program'])
        self.assertIn('无任何行引用', entry['callers'])
        self.assertNotIn(FEVER_GROWTH, [s for s in M.RESONANCE_OMISSION[M.AFTERGLOW]['sources']])
        tree = self.context['dsl'][FEVER_GROWTH]
        self.assertEqual(entry['tree_digest'], M.digest(tree))
        commands = tree[11][1]
        self.assertEqual(1, len(commands))
        exist = commands[0][1]
        self.assertEqual(['ConditionalsConditionExist', -17, ['DCUnique', int(M.AFTERGLOW)]], exist[:3])
        then_block, else_block = exist[3], exist[4]
        self.assertEqual(['Block', []], else_block)
        names = [c[1][0] for c in then_block[1]]
        self.assertEqual(['BindConditionAccumulationVariable', 'CreateCondition'], names)
        self.assertEqual(['ACUnique', int(M.AFTERGLOW)], then_block[1][1][1][2][0][:2])
        # 调用方：fixture 里的能力3 / 队长行都不引用该程序（全表扫描见 notes）。
        for rows in (self.inputs['ability'][M.ABILITY3], self.inputs['leader'][M.LEADER],
                     self.context['ability']['1399956']):
            self.assertFalse(any('fever_growth' in cell for row in rows for cell in row))

    # ------------------------------------------------------------ 门禁

    def test_every_leader_row_passes_client_gates(self):
        for index, row in enumerate(self.new_leader):
            with self.subTest(row=index):
                self.assertEqual([], client_legality_problems('leader_ability', row))
                self.assertEqual([], declared_block_field_problems('leader_ability', row))
                self.assertEqual([], invoke_skill_string_problems(row, set(), 'leader_ability'))
                self.assertEqual([], description_compatibility_problems('leader_ability', row))
                self.assertEqual([], required_client_capabilities('leader_ability', row))
                self.assertEqual([], M.row_problems('leader_ability', row))

    # ------------------------------------------------------------ fail closed

    def test_live_drift_is_rejected_and_inputs_are_not_mutated(self):
        original = deepcopy(self.inputs)
        out = M.revise(reader(self.inputs))
        self.assertEqual(original, self.inputs)
        out['leader'][M.LEADER][1][111] = 'mutated'
        out['cas'][M.PANEL][0][0] = 'mutated'
        out['cas'][M.PANEL6][0][0] = 'mutated'
        self.assertEqual(original, self.inputs)
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.inputs)
            drifted[kind][key][0][-1] += 'x'
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                M.revise(reader(drifted))
            missing = deepcopy(self.inputs)
            missing[kind][key] = None
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                M.revise(reader(missing))

    def test_already_revised_live_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live['leader'].update(deepcopy(self.out['leader']))
        live['cas'].update(deepcopy(self.out['cas']))
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            M.revise(reader(live))
        with self.assertRaises(ValueError):
            M.leader_rows(self.new_leader)
        with self.assertRaises(ValueError):
            M.panel_rows(self.out['cas'][M.PANEL])
        # 第二批前（×1/5 之前）的旧态同样拒绝。
        pre = deepcopy(self.old_leader)
        for index, (original, _live, _new, _factor) in M.GROWTH.items():
            pre[index][111] = pre[index][112] = original
        with self.assertRaises(ValueError):
            M.leader_rows(pre)
        with self.assertRaises(ValueError):
            M.panel_rows([[B2.OLD_PANEL]])
        with self.assertRaises(ValueError):
            M.panel_rows([[M.NUMERIC_PANEL]])                                 # 数值稿同样拒绝
        with self.assertRaises(ValueError):
            M.panel6_rows(self.out['cas'][M.PANEL6])                          # 能力6 已并成一行，拒绝再改

    def test_row_preimage_guards_fail_closed(self):
        cases = {'strength': (1, 111, '9000'), 'target': (4, 108, '5'), 'layer cap added': (5, 100, '10'),
                 'other unique': (6, 102, '1399951'), 'precondition': (9, 4, '0'),
                 'pf override moved': (7, 45, ''), 'gain row moved': (10, 45, '211')}
        for name, (index, col, value) in cases.items():
            rows = deepcopy(self.old_leader)
            rows[index][col] = value
            with self.subTest(name), self.assertRaises(ValueError):
                M.leader_rows(rows)
        with self.assertRaises(ValueError):
            M.leader_rows(self.old_leader[:10])
        before = deepcopy(self.old_leader)
        M.leader_rows(self.old_leader)
        self.assertEqual(before, self.old_leader)
        # 余辉来源漂移（能力3 末行不再给余辉）也要拒绝。
        drifted = deepcopy(self.inputs)
        drifted['ability'][M.ABILITY3][M.A3_GAIN_ROW][47] = '211'
        with self.assertRaises(ValueError), mock.patch.dict(
                M.BEFORE, {('ability', M.ABILITY3): M.digest(drifted['ability'][M.ABILITY3])}):
            M.revise(reader(drifted))

    # ------------------------------------------------------------ 生成器 / 跨单元

    def test_module_is_the_only_generator_of_the_panel(self):
        """面板在 mod-tools 下只有第二批与本轮两个写入源；历史链全部哈希锁定（第二批测试核对）。"""
        owners = sorted(path.name for path in (ROOT / 'mod-tools').glob('*.py')
                        if '「余辉」每1层' in path.read_text(encoding='utf-8', errors='ignore'))
        self.assertEqual(['wf_balance_20260927b_inaho.py', 'wf_balance_20260927c_inaho.py'], owners)
        self.assertEqual(M.leader_rows(self.old_leader), self.new_leader)
        self.assertEqual(M.panel_rows(self.inputs['cas'][M.PANEL]), self.out['cas'][M.PANEL])

    def test_module_is_the_only_writer_of_the_ability6_panel(self):
        """能力6 面板是 2026-09-09/10 回写的固定文案；mod-tools 下只有本模块写它（无可重跑的生成器）。"""
        owners = sorted(path.name for path in (ROOT / 'mod-tools').glob('*.py')
                        if '独立乘区的强化弹射伤害提升30' in path.read_text(encoding='utf-8', errors='ignore'))
        self.assertEqual(['wf_balance_20260927c_inaho.py'], owners)

    def test_soriz_donor_lookup_is_unaffected(self):
        """本轮不移行、不改能力1：秋水按内容取 1399951 的 724 行，与本轮无关。"""
        import wf_gbf_kit_soriz as S
        self.assertIn('key="1399951", mode="I", ck=724', Path(S.__file__).read_text(encoding='utf-8'))
        self.assertEqual({}, self.out['ability'])

    def test_module_contract_constants(self):
        self.assertEqual(('139995', 'fox_oracle_autumn'), (M.CID, M.CODE))
        self.assertEqual(['fox_oracle_autumn'], M.PACKAGES)
        self.assertEqual({'fox_oracle_autumn': '0.20260927.3'}, M.PACKAGE_VERSION)   # 候选现值 0.20260927.2
        self.assertEqual({}, M.REVIEWED_DRIFT)
        self.assertTrue(M.PANEL.startswith('desc_override_' + M.CODE))
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)

    # ------------------------------------------------------------ 候选（本机工作区）

    @unittest.skipUnless((WORKSPACE / 'package/manifest.json').is_file()
                         and (ROOT / 'mod-tools/profiles.json').is_file(),
                         'local candidate workspace required')
    def test_candidate_splices_only_the_reviewed_keys_dry(self):
        import wf_share_update_codec as X
        from wf_character_revision import RevisionCandidate
        manifest = WORKSPACE / 'package/manifest.json'
        before = manifest.read_bytes()
        current = version(json.loads(before)['package_version'])
        mine = M.PACKAGE_VERSION[M.PACKAGES[0]]
        candidate = RevisionCandidate(ROOT, WORKSPACE, character_id=M.CID, code_name=M.CODE,
                                      snapshot_key='revision_20260927c_growth', package_version=mine,
                                      reviewed_input_drift=M.REVIEWED_DRIFT,
                                      baseline_factory=lambda *a, **k: None)
        common = {t: X.unpack(candidate.read('common', t)) for t in (LEADER_TABLE, CAS_TABLE)}
        cand_leader = X.csv_read(common[LEADER_TABLE][M.LEADER])
        cand_panels = {key: X.csv_read(common[CAS_TABLE][key]) for key in self.out['cas']}
        if cand_leader == self.new_leader:
            # 已回写：候选 = 本轮输出。
            self.assertEqual(self.out['cas'], cand_panels)
            self.assertGreaterEqual(current, version(mine))
        else:
            # 暂存前：候选 = live 输入。
            self.assertEqual(self.old_leader, cand_leader)
            self.assertEqual({key: self.inputs['cas'][key] for key in self.out['cas']}, cand_panels)
            self.assertGreater(version(mine), current)
        # 能力6 面板键在候选表里、但不在候选 claim 里（2026-09-09/10 回写的固定文案）：暂存脚本
        # stage_batch.Plan.splice 会把返回的 desc_override_* 键并入 claim；RevisionCandidate.splice 拒绝接管未认领的
        # 既有键，干跑前按同样规则认领（只改内存 manifest，不落盘，末尾核对 manifest 字节不变）。
        claim = next(t for t in candidate.manifest['tables']
                     if t['root'] == 'common' and t['logical_path'] == CAS_TABLE)
        if M.PANEL6 not in claim['outer_keys']:
            self.assertIn(M.PANEL6, common[CAS_TABLE])
            claim['outer_keys'] = sorted(set(claim['outer_keys']) | set(self.out['cas']))
        candidate.splice(LEADER_TABLE, self.out['leader'])
        candidate.splice(CAS_TABLE, self.out['cas'])
        for table, keys in ((LEADER_TABLE, {M.LEADER}), (CAS_TABLE, set(self.out['cas']))):
            new = X.unpack(candidate.read('common', table))
            self.assertEqual({k: v for k, v in common[table].items() if k not in keys},
                             {k: v for k, v in new.items() if k not in keys}, table)
        self.assertEqual(self.out['cas'][M.PANEL6],
                         X.csv_read(X.unpack(candidate.read('common', CAS_TABLE))[M.PANEL6]))
        self.assertEqual(self.new_leader, X.csv_read(X.unpack(candidate.read('common', LEADER_TABLE))[M.LEADER]))
        evidence = candidate.finish({'dry_run': True}, apply=False)
        self.assertFalse(evidence['applied'])
        self.assertEqual({LEADER_TABLE, CAS_TABLE}, {f['logical_path'] for f in evidence['changed_files']})
        self.assertEqual(before, manifest.read_bytes())


if __name__ == '__main__':
    unittest.main()
