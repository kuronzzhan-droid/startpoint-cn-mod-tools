"""特克托：半血重炮成长、自身技能刷新重炮，以及强化技能护盾。"""
from copy import deepcopy

from wf_seasonal7_kit_philia import cmds, row_problems, dsl_gates, dsl_gate_failures

CID = '139993'
CODE = 'super_robot_tailcoat'
ENGINE = '13999301'
CANNON = '13999302'
SHIELD_TEXT = '强化『多重爆破·礼装重炮』：扫描锁定的范围扩大，并赋予自身护盾'


def revise_rows(leader, third):
    leader, third = deepcopy(leader), deepcopy(third)
    old = [r for r in leader if r[25] == '23' and r[26] == '4' and r[45] in ('32','34')]
    if len(old) != 2:
        raise ValueError('expected the two ally-skill attack/skill growth rows')
    growth = deepcopy(next(r for r in old if r[45] == '34'))
    for row in old:
        leader.remove(row)
    # Three native AND preconditions: resonance + cannon active + HP <=50%.
    growth[18:25] = ['9', '0', '', '50000', '50000', '', '']
    growth[25:45] = ['77', '', '', '12000000', '12000000', '', '', '(None)',
                     '0', '', '', '', '(None)', '', '', '', '', '', '', '0']
    growth[49:51] = ['100000']*2
    leader.append(growth)
    source = next(r for r in third if r[47] == '461' and r[68] == ENGINE)
    engine = [leader[0][0], *deepcopy(source[3:])]
    engine[11:25] = ['9', '0', '', '50000', '50000', '', '', '0', '', '', '', '', '', '']
    engine[25:30] = ['23', '0', '', '100000', '100000']
    # number=2 creates a second discrimination key; native stack readers take
    # the maximum, not the sum. Add two layers to the shared instance instead.
    engine[57:59] = ['100000']*2
    engine[72] = '2'
    leader.append(engine)
    cannon = next(r for r in third if r[47] == '461' and r[68] == CANNON)
    cannon[13:27] = ['0','','','','','','','0','','','','','','']
    cannon[27:32] = ['23', '0', '', '100000', '100000']
    for kind, rows in (('leader_ability',leader),('ability',third)):
        for row in rows:
            if errors := row_problems(kind,row,element=2):
                raise ValueError(errors)
    return leader, third


def revise_unique(rows):
    rows = deepcopy(rows)
    if len(rows) != 1 or rows[0][3] not in ('720','900'):
        raise ValueError('cannon duration drift')
    rows[0][3] = '900'
    return rows


def revise_skill(source):
    tree = deepcopy(source)
    if list(cmds(tree,'CreateBarrier')):
        raise ValueError('unexpected existing skill barrier')
    # Native hasAbilityPower(2) is the exact slot enabled by ability3 kind704.
    # Keep this separate from slot1's enemy debuffs and grant once per cast.
    tree[11][1].append(['Command', ['ConditionalsChangeSkillFlag', 2,
        ['Command', ['CreateBarrier', -17, [{'min':0.15,'max':0.15}], ['GenericBarrierHitEffect']]],
        ['Block', []]]])
    if failures := dsl_gate_failures(dsl_gates(tree,element=2)):
        raise ValueError(failures)
    return tree
