import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from wf.tools.rogue import rogue_build as rb
from wf.tools.rogue import rogue_element_channel as channel

class QuestElementChannelCase(unittest.TestCase):
    def test_removing_only_element_script_leaves_native_empty_list(self):
        # Floor 2 originally carried only this generated element script.
        original={};rb.apply_picks(original,[{'name':'雷减半','text':'雷减半','element_resistance':[(3,1,False)]}])
        old,_,new,_=channel.replacement_program(original)
        self.assertIsNone(new)
        encoded=channel.rewrite_pre_action_programs(old,{old:new})
        self.assertEqual(encoded,'')
        self.assertEqual(channel.pre_action_programs(encoded),[])
        # Reproduce GeneralBossValues' parsing after actual CSV compression.
        import csv,io,zlib
        row=['']*162;row[109]=encoded;row[110]='true'
        stream=io.StringIO(newline='');csv.writer(stream).writerow(row)
        decoded=next(csv.reader(io.StringIO(zlib.decompress(zlib.compress(stream.getvalue().encode())).decode())))
        native_paths=[] if decoded[109]=='' else decoded[109].split(',')
        self.assertEqual(native_paths,[])
        self.assertEqual(decoded[110],'true')

    def test_pre_action_gate_rejects_former_missing_asset_reference(self):
        for cell in ['(None)','native/pre,(None)','native/pre,']:
            with self.assertRaises(ValueError):channel.pre_action_programs(cell)
        with self.assertRaises(ValueError):
            channel.rewrite_pre_action_programs('old',{'old':'(None)'})

    def test_pre_action_migration_preserves_native_and_damage_scripts(self):
        self.assertEqual(channel.rewrite_pre_action_programs(
            'native/pre,old/element,native/pre2,old/mixed',
            {'old/element':None,'old/mixed':'new/damage'}),
            'native/pre,native/pre2,new/damage')

    def test_encoder_preserves_fixed_point_and_all_legal_subsets(self):
        for mask in range(1,63):
            values={i+1:999.0 for i in range(6) if mask & (1<<i)}
            self.assertEqual(channel.decode(channel.encode(values)),values)
        for r in [0,0.01,0.4,1,9,99,999,999.12345,999999]:
            self.assertAlmostEqual(channel.decode(channel.encode({1:r}))[1],r,places=5)
        with self.assertRaises(ValueError):channel.encode({i:999 for i in range(1,7)})
        self.assertEqual(len(channel.decode(channel.encode({i:9 for i in range(1,7)}))),6)

    def test_no_boss_can_receive_independent_element_channel(self):
        original={}
        rb.apply_picks(original,[{'name':'直击偏转','text':'直击耐性40%','cond':[['1','0.4']]}])
        original['capability_profile']={'effective':{'soft_quest_condition':True,'hard_element_resistance':False}}
        before=copy.deepcopy(original)
        final,block,receipt=channel.finalize_curse(original,46454236,1)
        self.assertEqual(original,before)
        self.assertEqual(final['conds'],original['conds'])
        self.assertEqual(len(receipt['final_banned']),2)
        self.assertEqual(len(channel.decode(block)),2)

    def test_original_three_to_five_bans_survive(self):
        for count in range(3,6):
            original={};rb.apply_picks(original,[{'name':'原有元素卡','text':'保留','element_resistance':[(i,99,False) for i in range(1,count+1)]}])
            final,_,receipt=channel.finalize_curse(original,1,1)
            self.assertEqual(final['picks'],original['picks'])
            self.assertEqual(len(receipt['final_banned']),count)
            self.assertEqual(receipt['added_banned'],[])

    def test_preserve_weak_resistance_and_remove_only_generated_element_program(self):
        original={};rb.apply_picks(original,[{'name':'混合','text':'混合','damage_resistance':[(1,99,False)],'element_resistance':[(1,9,False)]}])
        old,old_tree,new,new_tree=channel.replacement_program(original)
        self.assertNotEqual(old,new)
        self.assertIn('ACToleranceOfElement',json.dumps(old_tree))
        self.assertNotIn('ACToleranceOfElement',json.dumps(new_tree))
        self.assertIn('ACDirectAttackDamageResistance',json.dumps(new_tree))
        self.assertEqual(rb.wf_dsl.parse_dsl(__import__('zlib').decompress(rb.build_immunity_dsl_blob(new_tree),-15))['tree'],new_tree)

    def test_native_element_rule_remains_non_cancelable(self):
        original={};rb.apply_picks(original,[{'name':'可驱散','text':'test','element_resistance':[(1,99,True)]}])
        final,_,_=channel.finalize_curse(original,1,1)
        self.assertTrue(all(not atom[2] for atom in final['element_resistance']))
        self.assertEqual(final['picks'][0],original['picks'][0])

if __name__ == '__main__':unittest.main()
