"""风刃余势：每次强化技能风刃命中存2次，每次弹射消费1次并增加15连击。"""
from copy import deepcopy

CID = '159996'
CODE = 'wind_oracle_yukata'
UID = 15999601
NAME = '风刃余势'
UNIQUE = 'master/character/unique_condition.orderedmap'
ICON = f'battle/common/unique_condition/unique_{CODE}_wind_stock'
DESCRIPTION = ('强化『绣球光剑·夏夜花火』的剑雨效果，追加「强化弹射伤害抗性降低效果」，'
               '风刃命中敌人时积蓄「风刃余势」（可累积弹射次数）')
DETAIL = '／强化风刃每命中一个敌人获得2次「风刃余势」，每次弹射消耗1次并增加15连击'


def unique_row():
    # Same native stock mechanism as wind_spgirl_campus; no automatic flip expiry.
    return [[CODE+'_wind_stock', NAME, ICON, '99999999', '2147483647',
             '(None)', '(None)', '(None)', '(None)', 'false', 'true',
             '0', '0', 'false', '(None)']]


def grant_on_hit():
    import wf_seasonal7_kit_philia as K
    # -17 is the caster MEMBER. Unique does not fit the shared ball slot, so
    # simultaneous enemy hits all accumulate (ball-only same-frame dedup does not apply).
    grant = ['Command', ['CreateCondition', -17, [['ACUnique', UID, K.slv(1, 1)]],
             K.slv(1, 1), ['None'], False, True, '', None, False, 1, K.slv(2, 2), True]]
    return ['Command', ['ConditionalsChangeSkillFlag', K.RESONANCE_FLAG_INDEX,
                       ['Block', [grant]], ['Block', []]]]


def revise_skill(tree):
    import wf_seasonal7_kit_philia as K
    out = deepcopy(tree)
    swords = [c for c in K.cmds(out, 'CreateHitArea') if c[2] == -18]
    if len(swords) != 10:
        raise ValueError('stock requires ten active-skill blades')
    for sword in swords:
        existing = [c for c in K.cmds(sword[23], 'CreateCondition')
                    if any(v[:2] == ['ACUnique', UID] for v in c[2])]
        wanted = grant_on_hit()
        if existing:
            old = deepcopy(wanted)
            K.cmds(old, 'CreateCondition')[0][6] = False
            if len(existing) != 1 or not any(v in sword[23][1] for v in (old, wanted)):
                raise ValueError('stock grant drift')
            # ActionEvaluator's per-cast conditionChanges hash otherwise blocks
            # every later hit on the same recipient. Unique's stacking cap alone
            # cannot bypass that earlier gate. p5 permits repeated application.
            existing[0][6] = True
        else:
            sword[23][1].append(wanted)
    return out


def consumer_row(template):
    if len(template) != 126 or template[47] != '211':
        raise ValueError('A1 opening gauge template drift')
    row = list(template)
    # Native T26 = each ball flip; I226 = AddCombo. Precontent 2 consumes exactly
    # one Unique layer from Myself BEFORE activation. Empty stock returns 0 and
    # suppresses the reward. This adds duration credits, never +30/+45 per flip.
    row[5] = '0'
    row[6:27] = ['0','','','','','',''] * 3
    row[27:47] = [''] * 20
    row[47:85] = [''] * 38
    for column, value in {27:26, 30:100000, 31:100000, 34:'(None)', 35:0,
                          39:2, 40:0, 42:100000, 43:100000, 45:UID, 46:0,
                          47:226, 51:1500000, 52:1500000}.items():
        row[column] = str(value)
    return row


def revise_abilities(a1, a4):
    first, fourth = deepcopy(a1), deepcopy(a4)
    wanted = consumer_row(first[0])
    consumers = [r for r in first if r[45] == str(UID)]
    if consumers and consumers != [wanted]:
        raise ValueError('stock consumer drift')
    if not consumers:
        first.append(wanted)
    old = [r for r in fourth if r[47] == '489']
    if len(old) > 1 or (old and (old[0][27] != '23' or old[0][11] != 'White')):
        raise ValueError('A4 skill-triggered combo boost drift')
    if old:
        fourth.remove(old[0])
    if not fourth or fourth[0][97] != '31':
        raise ValueError('A4 Flying attack bonus must be preserved')
    return first, fourth


def skill_description(text):
    return text.replace('／强化时追加降低命中敌人的强化弹射伤害抗性', '').replace(DETAIL, '')
