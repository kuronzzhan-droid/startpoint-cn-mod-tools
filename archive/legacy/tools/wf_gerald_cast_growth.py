"""光狼队长的施技成长：起手快照，每次强化技能递增当前HP比例（不封顶，强化只在当队长时打开）。"""
from copy import deepcopy
from wf_bianca_dragon_skill import block, command, value
from wf_wind_dragon_revision import nodes

CODE = 'white_wolf_gerald'
COUNTER_UID = 14999903
COUNTER_VARIABLE = 360
#: BindConditionAccumulationVariable 第 5 参 = 变量上限（ActionEvaluator case 101：
#: ``bindFloatVariable(vid, min(层数 / 第4参, 第5参))``）。2026-09-27 第二批（口径 A.5）
#: 曾把它 2147483647 → 10（最多 15%）；作者 09-27：成长移入队长技（只在当队长时强化）后不再封顶
#: ⇒ 撤回（wf_balance_20260927b_gerald2）。写成浮点：AMF3 29 位整数放不下 2147483647，编码本来就是
#: double、解码回 2147483647.0；浮点与整数字节相同，但浮点让输出与 live 解码树连类型一致。
#: 计数固有 14999903 本身的上限（counter_row c4）一直未封。
COUNTER_CAP = 2147483647.0
CONDITION_KEY = CODE + '_cast_growth'
#: 技能强化条目（队长 536 行 c68 文案）：不写数字与秒数，不写共鸣前缀（客户端按前置拼「光属性共鸣」）；
#: 比例伤害称「固定伤害」（作者 09-27）。2026-09-27 第三轮（wf_balance_20260927c_gerald_wolf，作者「技能里面
#: 不要重复描述强化后的效果」）：点明技能名「强化『月耀一闪』：…」；技能说明不再写强化后的效果与数字。
ENHANCEMENT_TEXT = '强化『月耀一闪』：追加按敌人当前生命值计算的固定伤害（随技能发动次数提高），并斩杀低生命值的敌人'


def relocate(a2, a3, leaders):
    """仅移Fever时空裂痕和白共鸣I536；时之刻印属于原PF门，保持原位。"""
    a2, a3, leaders = deepcopy((a2, a3, leaders))
    rifts = [r for r in a2 if r[6] == '12' and r[47] == '629'
             and r[70] == 'ability_skill_gerald_time_rift']
    flags = [r for r in a3 if r[47] == '536' and r[70] == 'change_skill_' + CODE]
    if len(rifts) != 1 or len(flags) != 1:
        raise ValueError('reviewed Gerald ability rows changed')
    for r in rifts + flags:
        leaders.append([leaders[0][0], '0', ''] + r[5:])
    return [r for r in a2 if r not in rifts], [r for r in a3 if r not in flags], leaders


def counter_row():
    return [[CONDITION_KEY, '时空侵蚀', 'battle/common/unique_condition/unique_gerald_time_seal',
             '99999999', '2147483647', '(None)', '(None)', '(None)', '(None)',
             'false', 'true', '0', '0', 'false', '(None)']]


def rewrite(tree):
    result = deepcopy(tree)
    flags = list(nodes(result, 'ConditionalsChangeSkillFlag'))
    if len(flags) != 1 or flags[0][1] != 1:
        raise ValueError('expected one enhanced skill branch')
    enhanced = flags[0][2]
    ratios = list(nodes(enhanced, 'CreateRatioAttack'))
    if len(ratios) != 2:
        raise ValueError('expected current-HP strike and execute branches')
    strike = next((r for r in ratios if r[3] == value(.05)), None)
    execution = next((r for r in ratios if r[3] == value(1)), None)
    if strike is None or execution is None or strike[2] != 1 or execution[2] != 1:
        raise ValueError('ratio baseline changed')
    if list(nodes(result, 'BindConditionAccumulationVariable')):
        raise ValueError('unexpected existing variable binding')
    strike[3] = [{'min': .05, 'max': .05}, {'min': .01, 'max': .01, 'mul': COUNTER_VARIABLE}]
    bind = command('BindConditionAccumulationVariable', -17, COUNTER_VARIABLE,
                   ['DCUnique', COUNTER_UID], 1, COUNTER_CAP)
    increment = command('CreateCondition', -17, [['ACUnique', COUNTER_UID, value(1)]],
                        value(1), ['None'], False, False, CONDITION_KEY, None, False, 3, value(1), True)
    # Snapshot before the increment; each evaluator retains its own prior-cast count.
    enhanced[1][0:0] = [bind, increment]
    return result
