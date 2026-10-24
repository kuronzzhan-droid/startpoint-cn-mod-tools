"""原生风刃库存的收益/消费契约，与技能命中事件的连接。"""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import wf_mod_tool as core
import wf_philia_combo_stock as S
import wf_seasonal7_kit_philia as K
from wf_philia_wind_revision import revise_skill, revise_pf

ROOT = Path(__file__).resolve().parents[2]
PROTO = ROOT/K.PROTO_REL
PACKAGE = ROOT/'work/character_packs/s7-philia/package/roots/common'


class StockTests(unittest.TestCase):
    def rows(self):
        table = core.read_orderedmap_file_from_bytes((PACKAGE/K.ABILITY).read_bytes())
        return core.read_csv_lines(table['1599961']), core.read_csv_lines(table['1599964'])

    def test_abilities_preserve_other_effects_and_consume_before_reward(self):
        a1, a4 = self.rows()
        first, fourth = S.revise_abilities(a1, a4)
        self.assertEqual([r for r in first if r[45] != str(S.UID)],
                         [r for r in a1 if r[45] != str(S.UID)])
        self.assertEqual(fourth, [r for r in a4 if r[47] != '489'])
        row = first[-1]
        self.assertEqual((row[27], row[30], row[34], row[35]), ('26','100000','(None)','0'))
        self.assertEqual((row[39], row[40], row[42], row[43], row[45]),
                         ('2','0','100000','100000',str(S.UID)))
        self.assertEqual((row[47],row[51],row[52]), ('226','1500000','1500000'))
        self.assertEqual(K.row_problems('ability', row), [])
        self.assertEqual(S.revise_abilities(first, fourth), (first, fourth))

    def test_only_enhanced_active_blade_hit_grants_two_self_member_layers(self):
        for level in (1, 2):
            tree = revise_skill(json.loads((PROTO/f'skill_{level}.json').read_bytes()))
            swords = [c for c in K.cmds(tree,'CreateHitArea') if c[2] == -18]
            self.assertEqual(len(swords),10)
            for sword in swords:
                self.assertIn(S.grant_on_hit(), sword[23][1])
                self.assertNotIn(S.grant_on_hit(), sword[20][1])
                self.assertEqual(sword[18],['None'])
            self.assertEqual(K.dsl_gate_failures(K.dsl_gates(tree)), [])
            self.assertEqual(S.revise_skill(tree),tree)
        grant = S.grant_on_hit()[1]
        self.assertEqual(grant[:2], ['ConditionalsChangeSkillFlag',1])
        cc = K.cmds(grant[2],'CreateCondition')[0]
        self.assertTrue(cc[6], 'p5 must bypass ActionEvaluator per-cast condition dedup')
        self.assertEqual((cc[1],cc[10],cc[11]), (-17,1,K.slv(2,2)))
        self.assertEqual(grant[3],['Block',[]])
        for level in (1,2,3):
            pf = revise_pf(json.loads((PROTO/f'pf_lv{level}.json').read_bytes()))
            self.assertFalse(any(v[:2] == ['ACUnique',S.UID]
                                 for c in K.cmds(pf,'CreateCondition') for v in c[2]))

    def test_stock_is_persistent_and_never_expires_all_layers_after_two_flips(self):
        row = S.unique_row()[0]
        self.assertEqual(row[5:9],['(None)']*4)
        self.assertEqual(row[4],'2147483647')
        self.assertEqual(row[9:11],['false','true'])

    def test_repeated_hits_bypass_native_per_cast_condition_hash(self):
        # ActionEvaluator case21: params[5] false hashes the grant per recipient
        # and returns early after the first call, even with a large Unique cap.
        command = K.cmds(S.grant_on_hit(), 'CreateCondition')[0]
        def native_cast(repeat):
            seen, layers = set(), 0
            for _ in range(3):
                key = ('self-member', S.UID)
                if not repeat and key in seen:
                    continue
                seen.add(key)
                layers += command[11][0]['min']
            return layers
        self.assertEqual(native_cast(False), 2)  # reproduces the reported bug
        self.assertEqual(native_cast(command[6]), 6)
        tree = revise_skill(json.loads((PROTO/'skill_1.json').read_bytes()))
        for c in K.cmds(tree, 'CreateCondition'):
            if any(v[:2] == ['ACUnique', S.UID] for v in c[2]):
                c[6] = False
        fixed = S.revise_skill(tree)
        self.assertTrue(all(c[6] for c in K.cmds(fixed, 'CreateCondition')
                            if any(v[:2] == ['ACUnique', S.UID] for v in c[2])))

    def test_three_hits_pay_exactly_six_flips_and_can_gain_between_flips(self):
        # Native semantics: member Unique gains magnification per impact;
        # precontent consumes min(floor(stock/threshold), limit), then I226 pays.
        row = S.consumer_row(self.rows()[0][0])
        grant = K.cmds(S.grant_on_hit(),'CreateCondition')[0][11][0]['min']
        threshold = int(row[42])//100000
        combo = int(row[51])//100000
        stock = 3*grant
        rewards = []
        for _ in range(7):
            paid = min(stock//threshold,1)
            stock -= paid*threshold
            rewards.append(paid*combo)
        self.assertEqual(rewards,[15]*6+[0])
        stock = grant-1+grant
        self.assertEqual(stock,3)

    def test_new_description_is_idempotent_and_536_remains_concise(self):
        original = '向上射出10道贯穿风刃／提升连击数'
        old = original+'／强化时追加降低命中敌人的强化弹射伤害抗性'+S.DETAIL
        self.assertEqual(S.skill_description(S.skill_description(old)), original)
        self.assertEqual(K.text_rule_problems({K.CAS_CHANGE_SKILL:S.DESCRIPTION}),[])


if __name__ == '__main__':
    unittest.main()
