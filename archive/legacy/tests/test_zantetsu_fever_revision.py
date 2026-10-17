import unittest
from copy import deepcopy
import wf_zantetsu_fever_revision as rev


def attack():
    return ['CreateNormalAttack', 0, 4, 0, 0, 0, [{'min': 20, 'max': 20}], 0, False]


def source_tree():
    commands=[]
    for _ in range(3):
        normal=attack();boosted=deepcopy(normal);boosted[8]=True
        commands.append(rev.command('ConditionalsChangeSkillFlag',1,
            rev.block(['Command',boosted]),rev.block(['Command',normal])))
    return ['ActionDsl',2,['None'],False,False,False,False,False,False,False,0,
            rev.block(*commands)]


def evaluate(node, flags, fever):
    if not isinstance(node,list) or not node:return []
    if node[0]=='ConditionalsChangeSkillFlag':return evaluate(node[2 if node[1] in flags else 3],flags,fever)
    if node[0]=='ConditionalsFeverMode':return evaluate(node[1 if fever else 2],flags,fever)
    if node[0] in ('CreateNormalAttack','CreateCondition'):return [node]
    return [value for child in node for value in evaluate(child,flags,fever)]


class ZantetsuFeverTest(unittest.TestCase):
    def test_fever_resonance_and_unlock_truth_table(self):
        tree=rev.revise_tree(source_tree())
        for flags in (set(),{1},{2},{1,2}):
            for fever in (False,True):
                active=evaluate(tree,flags,fever)
                attacks=[n for n in active if n[0]=='CreateNormalAttack']
                buffs=[n for n in active if n[0]=='CreateCondition']
                self.assertEqual(len(attacks),3)
                self.assertEqual([n[8] for n in attacks],[1 in flags or (2 in flags and fever)]*3)
                self.assertEqual(len(buffs),int(2 in flags and fever))
                if buffs:self.assertEqual(buffs[0][2],[['ACPiercing',[{'min':900,'max':900}]]])

    def test_old_main_bonus_not_doubled_and_damage_unchanged(self):
        before=source_tree();saved=deepcopy(before);after=rev.revise_tree(before)
        self.assertEqual(before,saved)
        self.assertEqual(evaluate(before,{1},True),
            [n for n in evaluate(after,{1,2},True) if n[0]=='CreateNormalAttack'])

    def test_unexpected_or_already_revised_tree_rejected(self):
        with self.assertRaises(ValueError):rev.revise_tree(rev.revise_tree(source_tree()))
        tree=source_tree();tree[11][1].pop()
        with self.assertRaises(ValueError):rev.revise_tree(tree)

    def test_table_drift_rejected(self):
        with self.assertRaises(ValueError):rev.revise_rows([],[])


if __name__=='__main__':unittest.main()
