"""骰运满六层时翻倍本次抽中的六类奖励，保留抽签概率及次数。"""
from copy import deepcopy
import wf_dsl

UID = 13999101
TEXT = '「骰运」达到6层时，上述抽取奖励翻倍（攻击力／直击伤害＋1000%、Fever增加量翻倍、贯穿30秒、连击＋1000、队长技能槽＋30%；攻击力／直击伤害仍持续15秒）'


def doubled(statement):
    out = deepcopy(statement)
    c = out[1]
    if c[0] == 'CreateCondition':
        ac, = c[2]
        index = 1 if ac[0] == 'ACPiercing' else 2
        if ac[0] not in ('ACPiercing', 'ACAttackPoint', 'ACDirectDamage'):
            raise ValueError('unexpected roulette condition')
        for value in ac[index]:
            for key in ('min', 'max'):value[key] *= 2
    elif c[0] in ('AddFeverPoint', 'AddCombo'):
        for value in c[1]:
            for key in ('min', 'max'):value[key] *= 2
    elif c[0] == 'FindAllSubjects':
        add, = list(wf_dsl.iter_dsl_commands(c, 'AddSkillPoint'))
        if c[2] != 34:raise ValueError('roulette target is not leader')
        for value in add[2]:
            for key in ('min', 'max'):value[key] *= 2
    else:
        raise ValueError('unexpected roulette reward')
    return out


def apply(tree):
    out = deepcopy(tree)
    wheels = list(wf_dsl.iter_dsl_commands(out, 'ConditionalsProbability'))
    if len(wheels) != 6:raise ValueError('expected six roulette wheels')
    for wheel in wheels:
        if len(wheel[1][1]) != 6:raise ValueError('expected six equal options')
        for option in wheel[1][1]:
            weight, block = option[1]
            if weight != ['Command', ['ProbabilityWeight', 1]]:
                raise ValueError('roulette probability changed')
            reward, = block[1]
            block[1] = [['Command', ['ConditionalsConditionAccumulationNumber',
                ['DCUnique', UID], 6, ['Block', [doubled(reward)]], ['Block', [reward]]]]]
    if wf_dsl.parse_dsl(wf_dsl.encode_amf3(out))['tree'] != out:
        raise ValueError('roulette roundtrip failed')
    return out
