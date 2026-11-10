import copy
import json
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wf.tools.rogue import abyss_modes as policy
from wf.tools.core import mod_tool as core

class AbyssModesTests(unittest.TestCase):
    def test_ex_additional_rewards_cover_every_server_result_reference(self):
        try:
            root=core.resolve_server_dir()
        except ValueError as error:
            self.skipTest(f"configured server reward mirror unavailable: {error}")
        for name in ('rogue_event.json','rogue_event_cnmod.json'):
            if not (root/'assets'/name).is_file():
                self.skipTest(f"configured server is missing assets/{name}")
        config=json.loads((root/'assets/rogue_event.json').read_text('utf-8'))['events']['700100']
        ext=json.loads((root/'assets/rogue_event_cnmod.json').read_text('utf-8'))['events'].get('700100',{})
        config.update(ext)
        groups=policy.additional_reward_rows(config)
        self.assertIn('237010000',groups)
        self.assertEqual(set(groups['237010000']),{str(i) for i in range(1,11)})
        for drop in config['per_round_drops']:
            start=drop['additional_reward_index_start']
            for index in range(start,start+drop.get('slots',1)):
                row=groups[str(drop['additional_reward_group_id'])][str(index)].split(',')
                self.assertEqual(row[1:3],['0',str(drop['id'])])
                self.assertEqual(row[-1],'1')


    def test_health_and_attack_boundaries(self):
        self.assertEqual(policy.base_hp('normal',2),2_000_000_000)
        self.assertEqual(policy.base_hp('normal',30),10_000_000_000)
        for floor in range(1,31):
            expected=round(20e9+(floor-1)*15e9/29)*(2 if floor==30 else 1)
            self.assertEqual(policy.base_hp('ex',floor), expected)
        self.assertEqual(policy.attack_factor('ex',30),1.2)

    def test_first_boss_donor_cannot_hide_the_first_ex_stage(self):
        row=['unchanged']*104
        row[9:14]=['16','700007','','1','700007001']
        policy.set_finite_quest_prerequisite(row,700100,1)
        self.assertEqual(row[9:14],['(None)','','','','(None)'])
        self.assertTrue(all(v=='unchanged' for v in row[:9]+row[14:]))
        for floor in range(2,31):
            policy.set_finite_quest_prerequisite(row,700100,floor)
            self.assertEqual(row[9:14],['16','700100','',str(floor-1),str(700100000+floor-1)])

    def test_random_lanes_preserve_native_viable_intersection(self):
        for seed in range(200):
            for floor in (1,10,11,20,21,30):
                native={(2,0),(6,2)}
                result=policy.roll_ex_lanes(random.Random(seed),floor,native)
                self.assertIn(len(result['blocked_elements']),(3,4))
                self.assertEqual(len(result['immune_damage']),2)
                element,damage=result['open_lane']
                self.assertIn((element,damage),native)
                self.assertNotIn(element,result['blocked_elements'])
                self.assertNotIn(damage,result['immune_damage'])
        with self.assertRaises(ValueError):
            policy.roll_ex_lanes(random.Random(1),30,set())

    def test_cloned_five_boss_donor_is_not_hidden_by_renaming(self):
        self.assertTrue(policy.is_five_boss_source('mod_rogue_f30',['mod_rogue_boss30'],['mod_five_boss_var_s1_direct_a']))
        self.assertFalse(policy.is_five_boss_source('orochi_ex',['orochi_ex','orochi_ex_head1']))

    def test_five_boss_v2_and_v3_are_excluded_through_source_entries(self):
        cases = (
            ('mod_fb2_fd_1099033', (), ()),
            ('mod_rogue_f6', ('mod_fb2_033_water_w00',), ()),
            ('mod_rogue_f6', ('mod_rogue_boss6',), ('mod_fb2_fd_1099033',)),
            ('mod_rogue_f6', ('mod_fb3_administrator_light_multi_80',), ()),
            ('mod_rogue_f6', ('mod_rogue_boss6',), ('mod_fb3_yokai_emaki_middle_boss_multi',)),
        )
        for field, bosses, provenance in cases:
            with self.subTest(field=field, bosses=bosses, provenance=provenance):
                self.assertTrue(policy.is_five_boss_source(field, bosses, provenance))
        self.assertFalse(policy.is_five_boss_source('mod_fb20_unrelated'))

    def test_rewards_use_original_baseline_and_keep_fractional_expected_tokens(self):
        baseline={'config':{'per_round_drops':[
            {'type':'item','id':policy.TOKEN,'count':1,'slots':5,'guaranteed_slots':3,'chance':.3,'rounds':[2,10]},
            {'type':'item','id':999013,'count':1,'slots':1,'guaranteed_slots':0,'chance':.2,'rounds':[1,29]}],
            'folder_clear_chance':[{'type':0,'id':999014,'count':1,'chance':.1}],
            'folder_clear_random':[{'pool':[2370101],'pick':[1,1],'count':[1,3],'chance':.6}]},
            'fixed':[{'type':0,'id':policy.TOKEN,'count':100},{'type':0,'id':99,'count':1000}]}
        before=copy.deepcopy(baseline)
        result=policy.split_rewards(baseline)
        self.assertEqual(baseline,before)
        token_rows=[row for row in result['normal']['per_round_drops'] if row['id']==policy.TOKEN]
        expected=sum(row['count']*(row['guaranteed_slots']+(row['slots']-row['guaranteed_slots'])*row['chance']) for row in token_rows)
        self.assertAlmostEqual(expected,(3+2*.3)*.7)
        self.assertEqual(result['normal']['per_round_drops'][-1]['chance'],.14)
        self.assertEqual(result['ex']['per_round_drops'][0]['count'],2)
        self.assertEqual(result['ex_fixed'][0]['count'],200)
        self.assertEqual(result['normal_fixed'][0]['count'],70)
        self.assertEqual(result['normal_fixed'][1],{'type':0,'id':99,'count':800})
        self.assertFalse(any(99 in row['pool'] for row in result['normal']['folder_clear_random']))
        self.assertEqual(result['normal']['folder_clear_chance'][0]['chance'],.07)
        self.assertEqual(result['ex']['folder_clear_chance'][0]['count'],2)
        self.assertEqual(len(result['ex']['folder_clear_random']),1)
        self.assertFalse(any(2370101 in row['pool'] for row in result['normal']['folder_clear_random']))

if __name__=='__main__':
    unittest.main()
