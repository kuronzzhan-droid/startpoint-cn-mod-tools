"""克劳斯 129997：作者 2026-09-27 小重做（在第二批 live 1.4.1051 之上）。

技能 5×+100% 独立攻击 buff / 25 倍按直击 / 2 层淬毒 / 水耐性 -10%；PF 泡泡 2/4/6 个 × 15 段、总量守恒；
队长 T77→629「每 2 层淬毒直击判定 +1」；能力2 合行、能力3 117 一行、能力6 删淬毒行；面板与 8 处技能描述。
"""

from wf.paths import root_path
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock
import zlib

ROOT = Path(__file__).resolve().parents[2]
pass  # Imports resolve from this checkout/package, not external source copies.
sys.setrecursionlimit(10000)
import wf_balance_20260927b_claus_rework as M
import wf_balance_20260927b_klaus as B2
import wf_client_legality as L
import wf_dsl
import wf_dsl_sig
from wf_character_revision import encode_tree
from wf_midautumn_kit_hibiki import dsl_problems as kit_dsl_problems
from wf_midautumn_kitlib import panel_problems as kit_panel_problems

FIXTURE = Path(__file__).parent / 'fixtures/balance_20260927b_claus_rework.json'
WORKSPACE = ROOT / 'work/character_packs' / M.PACKAGES[0]
S1, S2 = M.SKILL_PROGRAMS[1], M.SKILL_PROGRAMS[2]
PF = M.PF_PROGRAMS
HITS = M.POISON_HITS_PROGRAM
ABIL = 'master/ability/ability.orderedmap'
LEAD = 'master/ability/leader_ability.orderedmap'
CAS = 'master/string/custom_ability_string.orderedmap'
ACT = 'master/skill/action_skill.orderedmap'
TXT = 'master/character/character_text.orderedmap'


def _key(kind, key):
    return '|'.join(key) if kind == 'table' else key


def slv(value):
    return [{'min': value, 'max': value}]


def cmd(node):
    assert node[0] in ('Command', 'Event'), node[:1]
    return node[1]


def names(block):
    return [cmd(n)[0] for n in block]


def dumps(value):
    return json.dumps(value, ensure_ascii=False)


class ClausReworkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = json.loads(FIXTURE.read_bytes())
        cls.inputs, cls.context = data['inputs'], data['context']
        cls.out = M.revise(cls.read_from(cls.inputs))

    @staticmethod
    def read_from(inputs):
        return lambda kind, key: inputs[kind][_key(kind, key)]

    def old(self, kind, key):
        return self.inputs[kind][_key(kind, key)]

    # ================================================================ 基线与输出形状

    def test_fixture_is_the_reviewed_baseline(self):
        self.assertEqual(14, len(M.BEFORE))
        for (kind, key), want in M.BEFORE.items():
            self.assertEqual(want, M.digest(self.old(kind, key)), (kind, key))
        for kind, key in M.NEW_KEYS:
            self.assertIsNone(self.old(kind, key), (kind, key))
        self.assertEqual([[PF[1], PF[2], PF[3]]], self.old('table', M.PF_ACTION))
        # 淬毒固有：上限 20、不可驱散、不强制付与（技能 onHit「每次施放每敌只 +2 层」依赖 c10='false'）。
        unique = self.old('table', M.UNIQUE)[0]
        self.assertEqual(('unique_claude_wolf_poison', '1200', '20', 'false', 'false'),
                         (unique[0], unique[3], unique[4], unique[9], unique[10]))
        # 第二批 PF 削韧已生效：9 / 19.8 / 25。
        self.assertEqual([9, 19.8, 25], [B2.detoughness(self.old('dsl', PF[lv])) for lv in M.PF_LEVELS])

    def test_output_shape(self):
        out = self.out
        self.assertEqual({'ability', 'leader', 'cas', 'text', 'table', 'action', 'dsl', 'server_text',
                          'new_programs', 'notes'}, set(out))
        self.assertEqual({'1299972', '1299973', '1299976'}, set(out['ability']))
        self.assertEqual({'129997'}, set(out['leader']))
        self.assertEqual({M.POISON_HITS_KEY, M.A2_OVERRIDE_KEY}, set(out['cas']))
        self.assertEqual({'129997'}, set(out['text']))
        self.assertEqual({'129997'}, set(out['server_text']))
        self.assertEqual({M.CODE}, set(out['action']))
        self.assertEqual({S1, S2, PF[1], PF[2], PF[3], HITS}, set(out['dsl']))
        self.assertEqual({}, out['table'])
        self.assertEqual([HITS], out['new_programs'])

    # ================================================================ 技能

    def skill(self, program, tree=None):
        return M.skill_parts(tree if tree is not None else self.out['dsl'][program])

    def test_skill_field_counts_as_direct_and_hits_25x(self):
        for level, program in ((1, S1), (2, S2)):
            old, new = self.skill(program, self.old('dsl', program)), self.skill(program)
            self.assertEqual((0, 4), (old['area'][24], new['area'][24]))
            attack = cmd(new['on_hit'][0])
            lo, hi = M.SKILL_MULT[level][1]
            self.assertEqual([{'min': lo, 'max': hi}], attack[6])
            self.assertEqual((slv(2), slv(2.5), True), (attack[13], attack[14], attack[16]))
            self.assertEqual((['CalculatedUsingMaxNumOfHits', 10], ['Some', slv(10)]),
                             (new['area'][14], new['area'][15]))
            self.assertLessEqual(B2.detoughness(self.out['dsl'][program]), 30)
            self.assertEqual(20, B2.detoughness(self.out['dsl'][program]))
        self.assertAlmostEqual(25.0, M.skill_damage_total(self.out['dsl'][S2]), places=9)
        self.assertAlmostEqual(25.0, 10 * 2.5)
        self.assertAlmostEqual(15 / 7 * 10, 10 * 1.5 * 25 / 17.5)                  # SLv1 同比例
        self.assertAlmostEqual(50 / 3, M.skill_damage_total(self.out['dsl'][S1]), places=6)
        # _1 与 _2 满级的原比例（11.67 / 17.5）保持：16.67 / 25。
        self.assertAlmostEqual(M.skill_damage_total(self.old('dsl', S1)) / M.skill_damage_total(self.old('dsl', S2)),
                               M.skill_damage_total(self.out['dsl'][S1]) / M.skill_damage_total(self.out['dsl'][S2]),
                               places=6)

    def test_skill_gives_five_independent_attack_buffs(self):
        precedent = cmd(self.context['ruin_lady_meteor23_1_atk_block'])
        precedent_conds = [cmd(n) for n in precedent[9][1]]
        self.assertEqual(['攻撃力アップ1', '攻撃力アップ2'], [c[7] for c in precedent_conds])
        for program in (S1, S2):
            parts = self.skill(program)
            atk_blocks = [f for f in parts['fas'] if f[2] == 113]
            self.assertEqual(1, len(atk_blocks))
            block = atk_blocks[0]
            self.assertEqual(precedent[1:9], block[1:9])                     # FindAllSubjects(3,113,[2]) 同官方先例
            conds = [cmd(n) for n in block[9][1]]
            self.assertEqual(list(M.ATK_KEYS), [c[7] for c in conds])
            self.assertEqual(5, len({c[7] for c in conds}))
            old_cond = cmd(self.skill(program, self.old('dsl', program))['fas'][0][9][1][0])
            for c in conds:
                self.assertEqual([['ACAttackPoint', slv(1200), slv(1.0), slv(1)]], c[2])
                self.assertIs(float, type(c[2][0][2][0]['max']))
                # 其余位与改前逐字相同，且与官方先例同形（p10=1 Member、p6=false、区分键不同）。
                self.assertEqual(old_cond[:2] + old_cond[3:7] + old_cond[8:], c[:2] + c[3:7] + c[8:])
                self.assertEqual(precedent_conds[0][3:7] + precedent_conds[0][8:], c[3:7] + c[8:])
            all_atk = [c for c in wf_dsl.iter_dsl_commands(self.out['dsl'][program], 'CreateCondition')
                       if c[2][0][0] == 'ACAttackPoint']
            self.assertEqual(5, len(all_atk))
            self.assertEqual(3, len([c for c in wf_dsl.iter_dsl_commands(self.old('dsl', program), 'CreateCondition')
                                     if c[2][0][0] == 'ACAttackPoint' and c[7] == '']))

    def test_skill_adds_two_poison_stacks_on_hit(self):
        precedent = self.context['ice_dragon_2_unique_condition']
        for program in (S1, S2):
            old, new = self.skill(program, self.old('dsl', program)), self.skill(program)
            self.assertEqual(['CreateNormalAttack', 'CreateCondition', 'ShakeCamera'], names(old['on_hit']))
            self.assertEqual(['CreateNormalAttack', 'CreateCondition', 'ShakeCamera', 'CreateCondition'],
                             names(new['on_hit']))
            self.assertEqual(dumps(old['on_hit'][1:3]), dumps(new['on_hit'][1:3]))     # 官方中毒 ACPoison 原样
            unique = cmd(new['on_hit'][3])
            self.assertEqual([['ACUnique', 129997, slv(2)]], unique[2])
            self.assertEqual(new['area'][22], unique[1])                             # 命中对象
            self.assertEqual(precedent[3:], unique[3:])                               # ice_dragon 同写法
            self.assertEqual(1, len(unique[2]))                                       # 单独一条
        self.assertEqual('false', self.old('table', M.UNIQUE)[0][10])

    def test_skill_water_resist_minus_ten_percent(self):
        for program in (S1, S2):
            old, new = self.skill(program, self.old('dsl', program)), self.skill(program)
            self.assertEqual(dumps(old['fas'][3][:9]), dumps(new['fas'][1][:9]))
            old_c, new_c = cmd(old['fas'][3][9][1][0]), cmd(new['fas'][1][9][1][0])
            self.assertEqual(slv(-0.15), old_c[2][0][3])
            self.assertEqual(slv(-0.1), new_c[2][0][3])
            self.assertEqual(old_c[2][0][:3] + old_c[2][0][4:], new_c[2][0][:3] + new_c[2][0][4:])
            self.assertEqual(old_c[3:], new_c[3:])                                   # forceApply 等不动

    def test_skill_other_nodes_are_verbatim(self):
        """把已知改动逐项还原，应当逐字（连 int/float 类型）回到改前。"""
        for level, program in ((1, S1), (2, S2)):
            old = self.old('dsl', program)
            restored = deepcopy(self.out['dsl'][program])
            parts = M.skill_parts(restored)
            parts['area'][24] = 0
            lo, hi = M.SKILL_MULT[level][0]
            cmd(parts['on_hit'][0])[6] = [{'min': lo, 'max': hi}]
            parts['on_hit'].pop()
            cmd(parts['fas'][1][9][1][0])[2][0][3] = slv(-0.15)
            old_parts = M.skill_parts(old)
            parts['body'][3] = deepcopy(old[11][1][3])
            parts['body'].insert(4, deepcopy(old[11][1][4]))
            parts['body'].insert(5, deepcopy(old[11][1][5]))
            self.assertEqual(dumps(old), dumps(restored), program)
            self.assertEqual(4, len(old_parts['fas']))

    # ================================================================ 强化弹射（泡泡）

    def test_pf_bubble_count_and_timeline(self):
        for level in M.PF_LEVELS:
            old, new = M.pf_timeline(self.old('dsl', PF[level])), M.pf_timeline(self.out['dsl'][PF[level]])
            self.assertEqual({1: [1], 2: [1, 8, 15], 3: [1, 7, 13, 19, 25]}[level], [t for t, _, _ in old['bubbles']])
            self.assertEqual({1: [1, 8], 2: [1, 8, 15, 22], 3: [1, 7, 13, 19, 25, 31]}[level],
                             [t for t, _, _ in new['bubbles']])
            self.assertEqual(({1: 19, 2: 33, 3: 43}[level], {1: 26, 2: 40, 3: 49}[level]), (old['notify'], new['notify']))
            self.assertEqual(new['bubbles'][-1][0] + 18, new['notify'])
            tree = self.out['dsl'][PF[level]]
            self.assertEqual([['SetPowerFilpSuppress', 20]], list(wf_dsl.iter_dsl_commands(tree, 'SetPowerFilpSuppress')))
            self.assertEqual([['NotifyPowerflipEnd', -18]], list(wf_dsl.iter_dsl_commands(tree, 'NotifyPowerflipEnd')))

    def test_pf_each_bubble_hits_15_times_as_direct(self):
        strength = {1: 5000000, 2: 15000000, 3: 25000000}
        effect = {1: 'one', 2: 'two', 3: 'three'}
        for level in M.PF_LEVELS:
            mult, p13, fever = M.PF_SEG_AFTER[level]
            for _, args, _ in M.pf_timeline(self.out['dsl'][PF[level]])['bubbles']:
                self.assertEqual(('*', -18, ['EF'], False, False, ['Rectangle', slv(180), slv(4000)], 4),
                                 (args[1], args[2], args[3], args[7], args[8], args[9], args[24]))
                self.assertEqual(['SpecifyHitAreaLifetimeDirectly', 72], args[13])
                self.assertEqual(['CalculatedUsingMaxNumOfHits', 15], args[14])
                self.assertEqual(['Some', slv(15)], args[15])
                self.assertEqual(15, B2._area_hits(args))
                # 最小间隔 = 寿命 / (N − 0.5)（ActionHitAreaGroup.as:112-128）：第 15 段落在寿命内。
                self.assertLess(14 * 72 / 14.5, 72)
                self.assertEqual(['ShowEffect', 'ShakeCamera'], names(args[20][1]))
                self.assertTrue(cmd(args[20][1][0])[2][1].endswith(f'powerflip_attack_special_{effect[level]}'))
                self.assertEqual(['ShakeCamera', 1], cmd(args[20][1][1]))
                self.assertEqual(['CreateNormalAttack', 'CreateCondition'], names(args[23][1]))
                attack, poison = cmd(args[23][1][0]), cmd(args[23][1][1])
                self.assertEqual((slv(mult), slv(p13), slv(fever), True), (attack[6], attack[13], attack[14], attack[16]))
                self.assertEqual([['ACPoison', slv(2400), slv(strength[level]), slv(1)]], poison[2])

    def test_pf_totals_conserved_and_toughness_within_caps(self):
        for level in M.PF_LEVELS:
            old, new = self.old('dsl', PF[level]), self.out['dsl'][PF[level]]
            for a, b in zip(M.pf_bubble_totals(old), M.pf_bubble_totals(new)):
                self.assertAlmostEqual(a, b, places=6)                              # 倍率 / Fever 每目标总量不变
            self.assertEqual(M.PF_BUBBLE_TOTAL[level], tuple(round(x, 6) for x in M.pf_bubble_totals(new)))
            total = B2.detoughness(new)
            self.assertLessEqual(total, {1: 15, 2: 20, 3: 25}[level])
            self.assertAlmostEqual({1: 15, 2: 19.998, 3: 24.994}[level], total, places=6)
        # 不降 p13 会是 90 / 132 / 145（上限的 6 倍左右），所以必须降。
        self.assertEqual([90, 132, 145], [round(n * 15 * p, 6) + (1 if lv == 3 else 0) for lv, n, p in
                                          ((1, 2, 3), (2, 4, 2.2), (3, 6, 1.6))])

    def test_pf_lv3_opener_and_support_segment_kept(self):
        old, new = self.old('dsl', PF[3]), self.out['dsl'][PF[3]]
        self.assertEqual(dumps(old[11][1][:4]), dumps(new[11][1][:4]))     # 演出、全屏 1 段、辅助 buff、Suppress
        opener = B2.hit_areas(new)[0]
        self.assertEqual((-1, ['AB'], ['CalculatedUsingMaxNumOfHits', 1]), (opener[0][2], opener[0][3], opener[0][14]))
        for level in (1, 2):
            o, n = self.old('dsl', PF[level])[11][1], self.out['dsl'][PF[level]][11][1]
            self.assertEqual(dumps(o[0]), dumps(n[0]))
            self.assertEqual(3, len(M._support_p5_ints(o)))
            self.assertEqual([], M._support_p5_ints(n))
            fixed = deepcopy(n[1])
            for c in cmd(fixed)[9][1]:
                self.assertIs(True, cmd(c)[5])
                cmd(c)[5] = 6
            self.assertEqual(dumps(o[1]), dumps(fixed))                       # 只有 p5 6 → true
        self.assertEqual([], M._support_p5_ints(old[11][1]))

    def test_pf_other_nodes_are_verbatim(self):
        """去掉新增泡泡、把泡泡字段与 ShakeCamera 还原、p5 还原成 6 → 应逐字回到改前。"""
        for level in M.PF_LEVELS:
            old = self.old('dsl', PF[level])
            restored = deepcopy(self.out['dsl'][PF[level]])
            line = M.pf_timeline(restored)
            _, _, second_last_block = line['bubbles'][-2] if len(line['bubbles']) > 1 else (None, None, None)
            notify_wait = line['bubbles'][-1][2][1]
            second_last_block[1] = notify_wait
            mult, p13, fever = M.PF_SEG_BEFORE[level]
            for _, args, _ in M.pf_timeline(restored)['bubbles']:
                args[13] = ['SpecifyHitAreaLifetimeDirectly', 20]
                args[14] = ['CalculatedUsingMaxNumOfHits', 3]
                args[15] = ['None']
                args[23][1].insert(1, args[20][1].pop())
                attack = cmd(args[23][1][0])
                attack[6], attack[13], attack[14] = slv(mult), slv(p13), slv(fever)
            if level in (1, 2):
                for c in cmd(restored[11][1][1])[9][1]:
                    cmd(c)[5] = 6
            self.assertEqual(dumps(old), dumps(restored), level)

    # ================================================================ 队长：每 2 层淬毒直击判定 +1

    def test_leader_row_is_appended_with_nephtim_shape(self):
        old, new = self.old('leader', '129997'), self.out['leader']['129997']
        self.assertEqual(10, len(new))
        self.assertEqual(dumps(old), dumps(new[:9]))
        row = new[9]
        self.assertEqual(M.poison_hits_leader_row(), row)
        self.assertEqual(124, len(row))
        nephtim = self.context['leader_169989_row7']
        self.assertEqual(('77', '1000000', '629'), (nephtim[25], nephtim[28], nephtim[45]))
        diff = {i for i, (a, b) in enumerate(zip(nephtim, row)) if a != b}
        self.assertEqual({0, 5, 9, 68, 69}, diff)
        self.assertEqual(old[7][4:11], row[4:11])                             # 本表水共鸣门
        self.assertEqual((M.CODE, 'Blue', M.POISON_HITS_KEY, HITS), (row[0], row[9], row[68], row[69]))
        self.assertEqual(f'battle/action/skill/action/ability_skill/{M.CODE}${row[68]}', row[69])
        keys = set(self.out['cas'])
        self.assertEqual([], L.client_legality_problems('leader_ability', row))
        self.assertEqual([], L.declared_block_field_problems('leader_ability', row))
        self.assertEqual([], L.invoke_skill_string_problems(row, keys, 'leader_ability'))
        self.assertTrue(L.invoke_skill_string_problems(row, set(), 'leader_ability'))   # 文案键必须同批写进 CAS
        self.assertEqual([], L.required_client_capabilities('leader_ability', row))

    def test_poison_hits_tree(self):
        tree = self.out['dsl'][HITS]
        self.assertEqual(M.poison_hits_tree(), tree)
        self.assertEqual(['ActionDsl', 1, ['None'], *[False] * 7, 0], tree[:11])
        enemies = cmd(tree[11][1][0])
        self.assertEqual(['FindAllSubjects', 10, 49, [], [], [], [], [], ['DoNothing']], enemies[:9])
        bind, water = (cmd(n) for n in enemies[9][1])
        self.assertEqual(['BindConditionAccumulationVariable', 10, 1, ['DCUnique', 129997], 2, 9], bind)
        self.assertEqual(['int', 'int', 'DeletionalConditionKind', 'int', 'Number'],
                         wf_dsl_sig.COMMANDS['BindConditionAccumulationVariable'])
        self.assertEqual(len(wf_dsl_sig.COMMANDS['BindConditionAccumulationVariable']), len(bind) - 1)
        self.assertEqual(['FindAllSubjects', 11, 113, [2], [], [], [], [], ['DoNothing']], water[:9])
        grant = cmd(water[9][1][0])
        self.assertEqual(len(wf_dsl_sig.COMMANDS['CreateCondition']), len(grant) - 1)
        ada = grant[2][0]
        self.assertEqual('ACAdditionalDirectAttack', ada[0])
        self.assertEqual(4, len(ada) - 1)
        # 段数写法同 live 凯尔（Bind + vlv），读的是敌方主体、除数 2、上限 9（零先例，需真机）。
        kyle_bind = cmd(self.context['kyle_moon_pierce_tree'][11][1][0])
        kyle_ada = cmd(self.context['kyle_moon_pierce_tree'][11][1][1])[2][0]
        self.assertEqual(('BindConditionAccumulationVariable', -17, 1, 'DCUnique', 1, 10),
                         (kyle_bind[0], kyle_bind[1], kyle_bind[2], kyle_bind[3][0], kyle_bind[4], kyle_bind[5]))
        self.assertEqual(len(kyle_bind), len(bind))
        self.assertEqual(kyle_ada[2], ada[2])
        self.assertEqual((slv(20), slv(1.0), slv(1)), (ada[1], ada[3], ada[4]))
        # 刷新写法同 live 奈芙（隐形、None 特效、不可驱散、强制付与、TTL = 2 × 周期 20 帧）；
        # 差别：p6=true（每个敌人都付与）、空键（不同段数各占一条，引擎取段数最多的）。
        nephtim = cmd(cmd(self.context['nephtim_ball_hit_count_tree'][11][1][1])[3][1][0])
        self.assertEqual(nephtim[2][0][1], ada[1])
        self.assertEqual(nephtim[3:6] + nephtim[8:], grant[3:6] + grant[8:])
        self.assertEqual((True, ''), (grant[6], grant[7]))
        self.assertEqual(2 * 10, M.POISON_HITS_TTL)

    def test_poison_hits_segments_by_stack_count(self):
        want = [1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 10]
        self.assertEqual(want, [M.poison_hits_segments(n) for n in range(21)])
        self.assertEqual(10, M.poison_hits_segments(20))                      # 作者：满 20 层每人直击 10 下

    def test_new_names_fit_namespace_and_path_budget(self):
        self.assertTrue(M.POISON_HITS_KEY.startswith(M.CODE))
        self.assertTrue(M.A2_OVERRIDE_KEY.startswith(f'desc_override_{M.CODE}'))
        logical = wf_dsl.dsl_logical(HITS)
        package_path = f'{root_path().as_posix()}/startpoint-cn/work/character_packs/{M.PACKAGES[0]}/package/roots/common/{logical}'
        self.assertLess(len(package_path) + len('-pre-rebase-') + 32, 260)          # package-pre-rebase-<32hex>

    # ================================================================ 能力

    def test_ability2_three_pf_rows_merge_into_one(self):
        old, new = self.old('ability', '1299972'), self.out['ability']['1299972']
        self.assertEqual(['63', '64', '65', ''], [r[27] for r in old])
        self.assertEqual(2, len(new))
        self.assertEqual({27, 51, 52}, {i for i, (a, b) in enumerate(zip(old[0], new[0])) if a != b})
        self.assertEqual(('2', '', '100000', '100000', '(None)', '413', '300000', '300000', '129997'),
                         (new[0][27], new[0][28], new[0][30], new[0][31], new[0][34], new[0][47], new[0][51],
                          new[0][52], new[0][68]))
        self.assertEqual(old[3], new[1])                                          # 每层淬毒特攻 +50%（限 20）

    def test_ability3_pf_separated_terms_become_one_poison_slayer_row(self):
        old, new = self.old('ability', '1299973'), self.out['ability']['1299973']
        self.assertEqual(['713'] * 3, [r[47] for r in old[5:]])
        self.assertEqual(6, len(new))
        self.assertEqual(dumps(old[:5]), dumps(new[:5]))
        self.assertEqual({47, 51, 52}, {i for i, (a, b) in enumerate(zip(old[3], new[5])) if a != b})
        self.assertEqual(('117', '15000', '15000', '202', '5', 'Blue', 'true'),
                         (new[5][47], new[5][51], new[5][52], new[5][6], new[5][48], new[5][49], new[5][1]))
        for key, official in self.context['official_ability_117_rows'].items():
            self.assertEqual(('117', '5', 'Blue'), (official[47], official[48], official[49]), key)
            self.assertEqual(official[27:47], new[5][27:47], key)             # 常驻瞬发（trigger 0）
        self.assertFalse([r for r in new if r[47] == '713'])

    def test_ability6_drops_the_skill_poison_row(self):
        old, new = self.old('ability', '1299976'), self.out['ability']['1299976']
        self.assertEqual(('23', '413', '200000'), (old[2][27], old[2][47], old[2][51]))
        self.assertEqual(dumps([old[0], old[1], old[3], old[4]]), dumps(new))
        self.assertEqual(['252', '264'], [r[47] for r in new[2:]])            # 技能发动时 100 倍 / 30 倍能力伤害保留

    def test_changed_rows_pass_client_legality(self):
        keys = set(self.out['cas'])
        for key, rows in self.out['ability'].items():
            for i, row in enumerate(rows):
                self.assertEqual(126, len(row))
                self.assertEqual([], L.client_legality_problems('ability', row), (key, i))
                self.assertEqual([], L.declared_block_field_problems('ability', row), (key, i))
                self.assertEqual([], L.invoke_skill_string_problems(row, keys, 'ability'), (key, i))
                self.assertEqual([], L.required_client_capabilities('ability', row), (key, i))
        self.assertEqual([], M.row_problems('leader_ability', self.out['leader']['129997'], keys))

    # ================================================================ 面板与描述

    def test_skill_description_is_unified_in_eight_places(self):
        places = []
        for inner, fields in self.out['action'][M.CODE]:
            places.append(fields[1])
            old = dict(self.old('action', M.CODE))[inner]
            self.assertEqual(old[:1] + old[2:], list(fields[:1]) + list(fields[2:]), inner)
        text, old_text = self.out['text']['129997'][0], self.old('text', '129997')[0]
        server, old_server = self.out['server_text']['129997'][0], self.old('server_text', '129997')[0]
        for row, old in ((text, old_text), (server, old_server)):
            places += [row[5], row[7], row[9]]
            self.assertEqual({5, 7, 9}, {i for i, (a, b) in enumerate(zip(old, row)) if a != b})
            self.assertEqual(len(old), len(row))
        self.assertEqual([M.NEW_SKILL_DESC] * 8, places)
        self.assertEqual(1, len(self.out['server_text']['129997']))
        self.assertNotIn('引爆', M.NEW_SKILL_DESC)
        self.assertIn('引爆', M.OLD_SKILL_DESC)
        for word in ('5个攻击力提升', '直接攻击伤害判定', '2层「淬毒」', '水属性抗性', '水属性角色'):
            self.assertIn(word, M.NEW_SKILL_DESC)
        self.assertEqual([], kit_panel_problems(M.NEW_SKILL_DESC))

    def test_panel_texts(self):
        for key, rows in self.out['cas'].items():
            self.assertEqual(1, len(rows))
            self.assertEqual(1, len(rows[0]))                                  # live desc_override 全是 1 行 1 列
            self.assertEqual([], kit_panel_problems(rows[0][0]), key)
            self.assertEqual([], M.panel_problems(key, rows[0][0]), key)
        leader_text = self.out['cas'][M.POISON_HITS_KEY][0][0]
        # 客户端会先拼本行前置（水共鸣）再接文案，文案本身不能再写「水属性共鸣时，」，否则面板重复。
        self.assertFalse(leader_text.startswith('水属性共鸣时'))
        self.assertTrue(leader_text.startswith('敌人身上每有2层「淬毒」'))
        self.assertIn('每有2层「淬毒」', leader_text)
        self.assertIn('最多10次', leader_text)
        override = self.out['cas'][M.A2_OVERRIDE_KEY][0][0].split('\n')
        self.assertEqual(3, len(override))
        self.assertEqual('强化中毒：技能与强化弹射附加的中毒伤害大幅提升', override[2])
        self.assertNotIn('不同来源', '\n'.join(override))
        self.assertEqual({'true'}, {r[1] for r in self.out['ability']['1299972']})   # 非主位：不带主位图标
        self.assertFalse(any('<icon' in line or '／' in line for line in override))
        # 覆盖文案的数值与行一致：3 层、每层 +50%、最多 20 层。
        merged, slayer = self.out['ability']['1299972']
        self.assertEqual(3, int(merged[51]) // 100000)
        self.assertIn('3层', override[0])
        self.assertEqual(50, int(slayer[113]) // 1000)
        self.assertIn('+50%', override[1])
        self.assertEqual('20', slayer[102])
        self.assertIn('（最多20层）', override[1])
        # 面板覆盖行需要 V14 面板覆盖补丁；629/117/413 行本身不需要补丁。
        self.assertEqual('panel-description-override-v2', L.panel_override_capability(M.A2_OVERRIDE_KEY))
        self.assertIsNone(L.panel_override_capability(M.POISON_HITS_KEY))
        self.assertEqual(sorted(M.CAPABILITIES), M.required_capabilities(self.out))
        self.assertEqual([], kit_panel_problems(self.context['cas']['override_string_claude_wolf_assassin_ex'][0][0]))

    # ================================================================ DSL 门禁

    def test_trees_pass_dsl_gates_and_roundtrip(self):
        for program, tree in self.out['dsl'].items():
            self.assertEqual([], M.dsl_problems(tree), program)
            rt = wf_dsl.parse_dsl(zlib.decompress(encode_tree(tree), -15))['tree']
            self.assertEqual(json.dumps(tree), json.dumps(rt), program)
        # 包内 kit 门禁（签名 / 作用域 / 主体 id 唯一）：技能树与新 629 树全净；
        # PF 串联泡泡 bound id 0/1/2 重复是 live Lv2/Lv3 既有写法（各泡泡的绑定只在自身子块可见），Lv1 加泡泡后同形。
        for program in (S1, S2, HITS):
            self.assertEqual([], kit_dsl_problems(self.out['dsl'][program], element=None), program)
        for level in M.PF_LEVELS:
            self.assertEqual(['duplicate bound subject ids: [0, 1, 2]'],
                             kit_dsl_problems(self.out['dsl'][PF[level]], element=None), level)
        # 改前 Lv1/Lv2 的 p5 整数签名问题已消除。
        self.assertTrue(any('signature' in p for p in kit_dsl_problems(self.old('dsl', PF[1]), element=None)))

    # ================================================================ fail closed

    def test_live_drift_is_rejected_and_inputs_are_not_mutated(self):
        original = deepcopy(self.inputs)
        M.revise(self.read_from(self.inputs))
        self.assertEqual(dumps(original), dumps(self.inputs))
        for kind, key in M.BEFORE:
            drifted = deepcopy(self.inputs)
            value = drifted[kind][_key(kind, key)]
            if kind == 'dsl':
                value[10] = 4
            elif kind == 'action':
                value[0][1][2] = value[0][1][2] + 'x'
            else:
                value[0][-1] = value[0][-1] + 'x'
            with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
                M.revise(self.read_from(drifted))
            missing = deepcopy(self.inputs)
            missing[kind][_key(kind, key)] = None
            with self.assertRaises(ValueError):
                M.revise(self.read_from(missing))

    def test_new_keys_must_not_exist_yet(self):
        for kind, key in M.NEW_KEYS:
            taken = deepcopy(self.inputs)
            taken[kind][_key(kind, key)] = [['x']]
            with self.assertRaisesRegex(ValueError, 'already exists'):
                M.revise(self.read_from(taken))
        gone = deepcopy(self.inputs)
        del gone['cas'][M.POISON_HITS_KEY]                                    # live 读不到 = KeyError，同样放行
        M.revise(self.read_from(gone))

    def test_unique_force_apply_guard(self):
        forced = deepcopy(self.inputs)
        row = forced['table'][_key('table', M.UNIQUE)][0]
        row[10] = 'true'
        with mock.patch.dict(M.BEFORE, {('table', M.UNIQUE): M.digest(forced['table'][_key('table', M.UNIQUE)])}):
            with self.assertRaisesRegex(ValueError, 'unique_condition'):
                M.revise(self.read_from(forced))

    def test_own_output_is_not_revised_twice(self):
        live = deepcopy(self.inputs)
        live['dsl'].update(deepcopy({k: v for k, v in self.out['dsl'].items() if k != HITS}))
        with self.assertRaisesRegex(ValueError, 'unreviewed live baseline'):
            M.revise(self.read_from(live))
        for level in M.PF_LEVELS:
            with self.assertRaisesRegex(ValueError, 'preimage drift'):
                M.revise_pf_tree(self.out['dsl'][PF[level]], level)
        for level, program in ((1, S1), (2, S2)):
            with self.assertRaisesRegex(ValueError, 'drift'):
                M.revise_skill_tree(self.out['dsl'][program], level)
        with self.assertRaisesRegex(ValueError, 'drift'):
            M.revise_ability2(self.out['ability']['1299972'])
        with self.assertRaisesRegex(ValueError, 'drift'):
            M.revise_ability3(self.out['ability']['1299973'])
        with self.assertRaisesRegex(ValueError, 'drift'):
            M.revise_ability6(self.out['ability']['1299976'])
        with self.assertRaisesRegex(ValueError, 'drift'):
            M.revise_leader(self.out['leader']['129997'])

    def test_structure_guards(self):
        with self.assertRaisesRegex(ValueError, 'drift'):
            M.revise_pf_tree(self.old('dsl', PF[2]), 3)                      # 档位错配
        with self.assertRaisesRegex(ValueError, 'drift'):
            M.revise_skill_tree(self.old('dsl', S2), 1)
        tree = deepcopy(self.old('dsl', PF[1]))
        cmd(tree[11][1][2])[1] = 30                                            # Suppress 变了
        with self.assertRaisesRegex(ValueError, 'suppress'):
            M.revise_pf_tree(tree, 1)
        tree = deepcopy(self.old('dsl', S2))
        M.skill_parts(tree)['fas'][1][9][1][0][1][7] = 'x'                     # 三个攻击 buff 块不再相同
        with self.assertRaisesRegex(ValueError, 'drift|identical'):
            M.revise_skill_tree(tree, 2)

    def test_revise_is_deterministic(self):
        again = M.revise(self.read_from(self.inputs))
        self.assertEqual(json.dumps(self.out, sort_keys=True, default=list),
                         json.dumps(again, sort_keys=True, default=list))

    # ================================================================ 接口常量

    def test_module_contract_constants(self):
        self.assertEqual(('129997', 'claude_wolf_assassin_ex'), (M.CID, M.CODE))
        self.assertEqual(['claude_wolf_assassin_ex'], M.PACKAGES)
        self.assertEqual({'claude_wolf_assassin_ex': '0.1.2'}, M.PACKAGE_VERSION)
        self.assertEqual(['panel-description-override-v2'], M.CAPABILITIES)
        self.assertEqual(B2.REVIEWED_DRIFT, M.REVIEWED_DRIFT)
        self.assertFalse(self.out['notes']['runtime_verified'])
        json.dumps(self.out['notes'], ensure_ascii=False)
        self.assertTrue(self.out['notes']['zero_precedent_needs_device'])

    # ================================================================ 候选 / live（本机）

    @unittest.skipUnless((WORKSPACE / 'package/manifest.json').is_file()
                         and (ROOT / 'mod-tools/profiles.json').is_file(),
                         'local candidate workspace required')
    def test_candidate_splices_dry(self):
        import wf_mod_tool as core
        from wf_character_revision import RevisionCandidate
        manifest = WORKSPACE / 'package/manifest.json'
        before = manifest.read_bytes()
        meta = json.loads(before)
        if meta['package_version'] == M.PACKAGE_VERSION[M.PACKAGES[0]]:
            # 已由暂存脚本回写：技能两档已重封（无既有漂移），全部输出树都在候选里且等于 revise() 输出。
            candidate = RevisionCandidate(ROOT, WORKSPACE, reviewed_input_drift={},
                                          character_id=M.CID, code_name=M.CODE,
                                          snapshot_key='revision_20260927b_claus_rework',
                                          package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                                          baseline_factory=lambda *a, **k: None)
            for program, tree in self.out['dsl'].items():
                raw = candidate.read('common', wf_dsl.dsl_logical(program))
                self.assertEqual(json.dumps(tree), json.dumps(wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']),
                                 program)
            claims = {t['logical_path']: set(t['outer_keys']) for t in candidate.manifest['tables']}
            self.assertLessEqual({M.POISON_HITS_KEY, M.A2_OVERRIDE_KEY}, claims[CAS])
            self.assertEqual(before, manifest.read_bytes())
            return
        self.assertLess(tuple(map(int, meta['package_version'].split('.'))),
                        tuple(map(int, M.PACKAGE_VERSION[M.PACKAGES[0]].split('.'))))
        candidate = RevisionCandidate(ROOT, WORKSPACE, reviewed_input_drift=M.REVIEWED_DRIFT,
                                      character_id=M.CID, code_name=M.CODE,
                                      snapshot_key='revision_20260927b_claus_rework',
                                      package_version=M.PACKAGE_VERSION[M.PACKAGES[0]],
                                      baseline_factory=lambda *a, **k: None)
        for kind, logical in (('ability', ABIL), ('leader', LEAD), ('cas', CAS), ('text', TXT)):
            candidate.splice(logical, self.out[kind])
        candidate.splice(ACT, {M.CODE: core.encode_action_skill_row(self.out['action'][M.CODE])},
                         codec='action_nested')
        for program, tree in self.out['dsl'].items():
            candidate.emit('common', wf_dsl.dsl_logical(program), encode_tree(tree))
        candidate.server_character_row('cdndata/character_text.json', self.out['server_text'][M.CID])
        evidence = candidate.finish({'dry_run': True}, apply=False)
        self.assertFalse(evidence['applied'])
        changed = {item['logical_path']: item['before_sha256'] for item in evidence['changed_files']}
        self.assertIsNone(changed[wf_dsl.dsl_logical(PF[1])])                  # Lv1 第一次进包
        self.assertIsNone(changed[wf_dsl.dsl_logical(HITS)])                   # 新 629 树
        for program in (S1, S2, PF[2], PF[3]):
            self.assertIsNotNone(changed[wf_dsl.dsl_logical(program)], program)
        claims = {t['logical_path']: set(t['outer_keys']) for t in candidate.manifest['tables']}
        self.assertLessEqual({M.POISON_HITS_KEY, M.A2_OVERRIDE_KEY}, claims[CAS])
        self.assertEqual(before, manifest.read_bytes())

    @unittest.skipUnless((ROOT / 'mod-tools/profiles.json').is_file(), 'local live store required')
    def test_live_is_either_the_baseline_or_this_output(self):
        import wf_mod_tool as core
        store = Path(core.resolve_active_store())
        for program, tree in self.out['dsl'].items():
            path = core.table_path(store, wf_dsl.dsl_logical(program))
            if program == HITS and not path.is_file():
                continue
            if not path.is_file():
                self.skipTest('live store DSL not present')
            live = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))['tree']
            allowed = {M.digest(tree)} | ({M.BEFORE['dsl', program]} if ('dsl', program) in M.BEFORE else set())
            self.assertIn(M.digest(live), allowed, program)


if __name__ == '__main__':
    unittest.main()
