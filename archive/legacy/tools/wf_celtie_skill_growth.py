"""星风心得的主动基础倍率成长；原生浮点绑定，不改伤害加成区。"""
from copy import deepcopy

from wf_celtie_fever_stock import GAIN_UID

GAIN_FLOAT_ID = 14998905
# 2026-09-27 第二批（口径 A5）：技能倍率只随前 10 层心得成长。原生 Bind 取
# min(层数/1, 上限)（ActionEvaluator.as case 101），官方 blackflower_wiz_smr22
# 两档技能即 Bind(-17, vid, DCUnique, 1, 10)。心得本身仍按固有上限 2147483647
# 累积，超过 10 层的逐层成长由队长「每层心得」两行承担。
GAIN_MAX_LAYERS = 10
MULTIPLIER_PER_LAYER = 10
# 2026-09-27 第三轮（c，作者「成长条件放到队长技里面带上对应共鸣条件」，口径 U5/U7）：
# 能力1 的 I704 开关行（前置42 仅队长 + 风共鸣）打开技能旗号 2；共鸣∧Fever 支按旗号 2
# 分两支——开支上限恢复第二批前的 2147483647（写成 float：AMF3 29 位整数装不下，
# 同 gerald2），关支保留第二批 10 层。旗号 1 已被能力1 的 I536 技能强化占用。
LEADER_FLAG = 2
LEADER_MAX_LAYERS = 2147483647.0


def _nodes(tree, kind):
    if isinstance(tree, list):
        if tree and tree[0] == kind:
            yield tree
        for child in tree:
            yield from _nodes(child, kind)


def _command(name, *args):
    return ['Command', [name, *args]]


def _block(*children):
    return ['Block', list(children)]


def with_starwind_growth(near):
    """在施技入口取心得快照，三个互斥子作用域各自绑定并执行动作。

    官方 blackflower_wiz_smr22 使用相同 Bind + SLvValue.vlv 写法（上限同为 10）。
    条件分支内绑定不会写回父 Environment，因此不能把 near 放在门槛外。
    无共鸣/非Fever用零上限绑定；没有心得时原生层数为零；共鸣且Fever时最多计 10 层。
    """
    template = deepcopy(near)
    attacks = list(_nodes(template, 'CreateNormalAttack'))
    if len(attacks) != 4:
        raise ValueError('expected four attacks across collision and timeout')
    for attack, weight in zip(attacks, (25, 45, 25, 45)):
        base = weight * 75 / 70
        if attack[6] != [{'min': base, 'max': base}]:
            raise ValueError('unexpected base multiplier before Starwind growth')
        attack[6][0]['vlv'] = [{'vid': GAIN_FLOAT_ID, 'min': 0,
                              'max': MULTIPLIER_PER_LAYER * weight / 70}]

    def branch(ceiling):
        return _block(_command('BindConditionAccumulationVariable', -17,
            GAIN_FLOAT_ID, ['DCUnique', GAIN_UID], 1, ceiling),
            _command(*deepcopy(template)))

    return _command('ConditionalsFeverMode',
        _block(_command('ConditionalsUnifyElement', 4, 6,
            branch(GAIN_MAX_LAYERS), branch(0))), branch(0))


def with_leader_uncapped_growth(tree):
    """整棵技能树（Boss 锁定之后）→ 共鸣∧Fever 支按技能旗号 2 分成不封顶 / 10 层两支。

    分支在新的局部环境里执行（ActionEvaluator.as case 86），Bind 写进当前环境、
    查找只向外层，所以整段「Bind + 其后路线」一起复制进开支；关支是原段本身，逐字不变。
    """
    result = deepcopy(tree)
    fever = result[11][1][1][1]
    if fever[0] != 'ConditionalsFeverMode':
        raise ValueError('second top command must be ConditionalsFeverMode')
    unify = fever[1][1][0][1]
    if unify[:3] != ['ConditionalsUnifyElement', 4, 6]:
        raise ValueError('Fever branch must gate wind resonance first')
    capped = unify[3]
    binding = capped[1][0][1]
    if (binding[:5] != ['BindConditionAccumulationVariable', -17, GAIN_FLOAT_ID,
                        ['DCUnique', GAIN_UID], 1] or binding[5] != GAIN_MAX_LAYERS
            or isinstance(binding[5], float)):
        raise ValueError('resonant branch must start with the capped Starwind binding')
    uncapped = deepcopy(capped)
    uncapped[1][0][1][5] = LEADER_MAX_LAYERS
    unify[3] = _block(_command('ConditionalsChangeSkillFlag', LEADER_FLAG, uncapped, capped))
    return result
