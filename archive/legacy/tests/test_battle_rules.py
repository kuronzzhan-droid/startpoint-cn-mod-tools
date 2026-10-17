import copy
from pathlib import Path
import sys
import unittest
from unittest import mock

pass  # Imports resolve from this checkout/package, not external source copies.
import wf_battle_rules as rules
import wf_client_legality as legality
import wf_client_patch_scope as scope
import wf_describe
from test_client_legality import _base_row

# client-patch/equipment-rules README「R3 行」：EA 表 c109/c110/c111/c118，魂表所有块列号 −3。
# 测试写死 README 的列号，再与布局表互证，避免两边一起错。
EQUIPMENT_GAUGE_COLUMNS = {
    'equipment_enhancement_ability': (109, 110, 111, 118),
    'ability_soul': (106, 107, 108, 115),
}
EQUIPMENT_TABLES = tuple(EQUIPMENT_GAUGE_COLUMNS)
DURING = legality.TRIGGER_MODE_BLOCKS['1']
INSTANT = legality.TRIGGER_MODE_BLOCKS['0']


def _equipment_gauge_row(table, code='8', uid='5910199'):
    """README 推荐形状：持续触发 134「自身持有固有状态」+ 423 目标 ExceptMyself、组 (None)。"""
    row = _base_row(table, '1')
    trigger = wf_describe.layout(table)['blocks']['during_trigger']
    row[trigger], row[trigger+1], row[trigger+5], row[trigger+7] = '134', '0', '1', uid
    kind, target, groups, mask = EQUIPMENT_GAUGE_COLUMNS[table]
    row[kind], row[target], row[groups], row[mask] = '423', '1', '(None)', code
    return row


class BattleRulesTest(unittest.TestCase):
    def test_fluffy_and_orthogonal_source_selections(self):
        self.assertEqual(12, rules.gauge_mask(['skill', 'ability']))
        self.assertEqual(1064, rules.gauge_mask(['ability', 'skill_triggered_ability'], origins=['weapon']))
        self.assertNotEqual(rules.gauge_mask(['skill'], owners=['other']),
                            rules.gauge_mask(['skill_triggered_ability'], owners=['self'], triggers=['other']))

    def test_invalid_or_impossible_masks_rejected(self):
        # 8|128 / 8|8192 / 8|2**30：带合法加槽位 + 未知标记位，只有未知位分支能拒
        for code in (0, -1, True, 1.5, 128, 1024, 2|1024, 2|16384, 2**30, 8|128, 8|8192, 8|2**30):
            with self.subTest(code=code), self.assertRaises(ValueError):
                rules.validate_code(423, code)
        with self.assertRaises(ValueError):
            rules.gauge_mask(['typo'])

    def test_all_damage_pairs_and_segment_encoding(self):
        for source in rules.SOURCES:
            for target in rules.DESTINATIONS:
                rules.validate_code(424, rules.damage_rule(source, target))
        self.assertEqual(104, rules.damage_rule('skill', 'direct'))
        self.assertEqual(401, rules.damage_rule('direct', 'skill'))
        self.assertEqual(133, rules.segment_override('pf3'))
        for code in (0, 103, 331, 501):
            if code == 331:  # PF -> PF1 is legal.
                continue
            with self.assertRaises(ValueError):
                rules.validate_code(424, code)

    def test_supported_targets_and_no_mutation(self):
        donor = _base_row('ability', '1')
        donor[100], donor[101] = '80000', '80000'
        old = copy.deepcopy(donor)
        for target in rules.TARGETS:
            row = rules.make_row(donor, 'battle_rule', 423, 12, target=target, groups='Green')
            self.assertEqual('Green', row[111])
            self.assertEqual(['0', '0'], row[100:102])
            self.assertEqual([], legality.client_legality_problems('ability', row))
            self.assertEqual([rules.GAUGE_CAP], legality.required_client_capabilities('ability', row))
        self.assertEqual(old, donor)

    def test_parser_scope_tables_and_residue_is_ignored(self):
        supported = {423: {'ability', *EQUIPMENT_TABLES}, 424: {'ability'}}
        for table in ('ability', 'leader_ability', 'ability_soul', 'equipment_enhancement_ability', 'ex_ability'):
            for kind, code, capability in ((423, 12, rules.GAUGE_CAP), (424, 104, rules.DAMAGE_CAP)):
                with self.subTest(table=table, kind=kind):
                    row = _base_row(table, '1')
                    blocks = wf_describe.layout(table)['blocks']
                    col = blocks['during_content']
                    row[col], row[col+9] = str(kind), str(code)
                    errors = legality.client_legality_problems(table, row)
                    parser_caps = scope.patch_parser_capabilities(table, row, blocks, DURING)
                    if table == 'ability':
                        self.assertEqual([], errors)
                        self.assertEqual([capability], legality.required_client_capabilities(table, row))
                        self.assertEqual([], parser_caps)
                    elif table in supported[kind]:
                        self.assertEqual([], errors)
                        self.assertIn(capability, legality.required_client_capabilities(table, row))
                        self.assertEqual([scope.EQUIPMENT_GAUGE_CAP], parser_caps)
                    else:
                        self.assertTrue(any('未被当前补丁扩展' in x for x in errors), errors)
                        self.assertEqual([], legality.required_client_capabilities(table, row))
                        self.assertEqual([], parser_caps)
                    row[blocks['precondition1']-1] = '0'
                    self.assertEqual([], legality.required_client_capabilities(table, row))
                    self.assertEqual([], scope.patch_parser_capabilities(table, row, blocks, INSTANT))

    def test_equipment_gauge_columns_match_layout(self):
        fields = {name: int(offset) for offset, name, _label
                  in wf_describe.enum_map()['block_fields']['during_content']}
        for table, columns in EQUIPMENT_GAUGE_COLUMNS.items():
            base = wf_describe.layout(table)['blocks']['during_content']
            self.assertEqual(columns, (base, base+fields['target'],
                                       base+fields['target.character_groups'], base+fields['unique_condition_id']))
        ea, soul = (EQUIPMENT_GAUGE_COLUMNS[t] for t in EQUIPMENT_TABLES)
        self.assertEqual([3]*4, [a-b for a, b in zip(ea, soul)])

    def test_equipment_tables_accept_recommended_gauge_rule(self):
        mask = rules.gauge_mask(['ability'])
        self.assertEqual(8, mask)
        for table in EQUIPMENT_TABLES:
            with self.subTest(table=table):
                row = _equipment_gauge_row(table, str(mask))
                blocks = wf_describe.layout(table)['blocks']
                self.assertEqual([], legality.client_legality_problems(table, row))
                self.assertEqual([], rules.row_problems(table, row, blocks))
                self.assertIn(rules.GAUGE_CAP, legality.required_client_capabilities(table, row))
                self.assertEqual([scope.EQUIPMENT_GAUGE_CAP],
                                 scope.patch_parser_capabilities(table, row, blocks, DURING))
        # ability 表的 423 只需要运行时能力，不因装备扩展多出依赖
        row = _base_row('ability', '1')
        row[109], row[118] = '423', str(mask)
        self.assertEqual([rules.GAUGE_CAP], legality.required_client_capabilities('ability', row))
        blocks = wf_describe.layout('ability')['blocks']
        self.assertEqual([], scope.patch_parser_capabilities('ability', row, blocks, DURING))

    def test_legality_reports_equipment_parser_capability(self):
        """装备两表的 423 除运行时能力 gauge-gain-rules-v1（1047 已有）外，还要求解析器扩展 equipment-gauge-gain-rules-v1。"""
        for table in EQUIPMENT_TABLES:
            self.assertEqual([rules.GAUGE_CAP, scope.EQUIPMENT_GAUGE_CAP],
                             legality.required_client_capabilities(table, _equipment_gauge_row(table)))

    def test_equipment_gauge_rule_negative_controls(self):
        for table in EQUIPMENT_TABLES:
            kind, _target, _groups, mask = EQUIPMENT_GAUGE_COLUMNS[table]
            blocks = wf_describe.layout(table)['blocks']
            # 坏规则码：报在该表自己的规则码列（EA c118 / 魂 c115）
            for code in ('0', '', '12.0', '-1', '128', '1024', str(2 | 1024),
                         str(8 | 128), str(8 | 8192), str(8 | 2**30)):
                with self.subTest(table=table, code=code):
                    errors = legality.client_legality_problems(table, _equipment_gauge_row(table, code))
                    self.assertTrue(any(x.startswith(f'c{mask} 战斗规则编码错误') for x in errors), errors)
            # 424 未扩到装备表：解析器范围报 C7050，规则码校验不重复报
            row = _equipment_gauge_row(table)
            row[kind] = '424'
            errors = legality.client_legality_problems(table, row)
            self.assertTrue(any(f'c{kind} during_content=424' in x and '未被当前补丁扩展' in x for x in errors), errors)
            self.assertEqual([], rules.row_problems(table, row, blocks))
            self.assertEqual([], legality.required_client_capabilities(table, row))
            self.assertEqual([], scope.patch_parser_capabilities(table, row, blocks, DURING))
            # 瞬发模式下 c109/c106 残留 423 不解析，也不要求装备能力
            row = _equipment_gauge_row(table)
            row[blocks['precondition1']-1] = '0'
            self.assertEqual([], legality.required_client_capabilities(table, row))
            self.assertEqual([], scope.patch_parser_capabilities(table, row, blocks, INSTANT))
        # 规则码写错列：魂表照抄 EA 的 c118，c115 为空即报错
        row = _equipment_gauge_row('ability_soul')
        row[115], row[118] = '', '8'
        self.assertTrue(any(x.startswith('c115 战斗规则编码错误')
                            for x in legality.client_legality_problems('ability_soul', row)))
        # 队长/EX 表仍未扩展 423
        for table in ('leader_ability', 'ex_ability'):
            with self.subTest(table=table):
                row = _base_row(table, '1')
                blocks = wf_describe.layout(table)['blocks']
                col = blocks['during_content']
                row[col], row[col+1], row[col+2], row[col+9] = '423', '1', '(None)', '8'
                errors = legality.client_legality_problems(table, row)
                self.assertTrue(any('未被当前补丁扩展' in x for x in errors), errors)
                self.assertEqual([], scope.patch_parser_capabilities(table, row, blocks, DURING))
        # 变异：装备表回退为未扩展时，同一推荐行必须被拒
        with mock.patch.dict(scope.PATCH_PARSER_TABLES, {('during_content', '423'): frozenset({'ability'})}):
            for table in EQUIPMENT_TABLES:
                errors = legality.client_legality_problems(table, _equipment_gauge_row(table))
                self.assertTrue(any('未被当前补丁扩展' in x for x in errors), errors)

    def test_unfiltered_party_uses_native_none_sentinel(self):
        donor = _base_row('ability', '1')
        for content, code in ((423, 12), (424, 104)):
            for target in ('party', 'others'):
                for kwargs in ({}, {'groups': ''}, {'groups': '(None)'}):
                    row = rules.make_row(donor, 'rule', content, code,
                                         target=target, **kwargs)
                    self.assertEqual('(None)', row[111])

    def test_table_invalid_code_is_not_only_an_enum_check(self):
        for content, code in ((423, '0'), (423, '12.0'), (423, '-1'), (423, str(8 | 128)), (424, '103')):
            row = _base_row('ability', '1')
            row[109], row[118] = str(content), code
            self.assertTrue(any('战斗规则编码' in x for x in legality.client_legality_problems('ability', row)))


if __name__ == '__main__':
    unittest.main()
