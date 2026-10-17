"""浪涌充能三档技能；复用已染色的四星光束、五星激光和Fever光柱。

伤害归属已被 2026-09-27 平衡批次取代（``wf_balance_20260927_regis``：能力相关都换成技能伤害）。
本模块保持 0917 行为不变（``tests/test_surge_anchor_revision.py`` 依赖它），kit 在它之后叠加新修订；
不要为了重跑一次性脚本（``wf_surge_anchor_candidate.py`` / ``wf_regis_philia_pf_candidate.py``）
而放宽 :func:`validate` 或 412 查找——对已转换的候选重跑会在这里响亮失败，放宽就会把改动写回能力伤害版。
"""
from copy import deepcopy

from wf_seasonal7_kit_philia import cmds, dsl_gates, dsl_gate_failures, row_problems

CID = '139994'
CODE = 'rec_android_seaside'
UID = 13999401
DESCRIPTION = ('向最近的敌人发射光束，造成雷属性伤害（按能力伤害加成计算）'
               '／「浪涌充能」达到3层、5层时提升光束形态，基础威力依次为50、75、100倍，每层额外＋15倍'
               '／非FEVER模式中，增加FEVER槽并提升自身攻击力'
               '／提升雷属性角色能力伤害')


def command(name, *args):
    return ['Command', [name, *args]]


def revise_skill(source):
    tree = deepcopy(source)
    if len(list(cmds(tree, 'ConditionalsConditionAccumulationNumber'))) == 2:
        validate(tree)
        return tree
    top = tree[11][1]
    old = top[1][1]
    if old[0] != 'ConditionalsFeverMode':
        raise ValueError('expected original Fever skill split')
    fever, normal = old[1][1], old[2][1]
    high = [n for n in fever if n[1][0] == 'FindNearSubjects']
    lower = [n for n in normal if n[1][0] == 'FindNearSubjects']
    if len(high) != 1 or len(lower) != 2:
        raise ValueError('three original beam sources missing')
    branches = []
    for vid, base, node in zip((1, 2, 3), (100, 75, 50), (high[0], *lower)):
        attacks = list(cmds(node, 'CreateNormalAttack'))
        areas = list(cmds(node, 'CreateHitArea'))
        if len(attacks) != 1 or len(areas) != 1 or areas[0][14] != ['CalculatedUsingMaxNumOfHits', 10]:
            raise ValueError('beam hit budget drift')
        attacks[0][6] = [{'min': base / 10, 'max': base / 10,
                         'vlv': [{'vid': vid, 'min': 0.0, 'max': 1.5}]}]
        areas[0][24] = 2  # Native AbilityDamage buff reference; source is still Skill.
        branches.append(['Block', [command('BindConditionAccumulationVariable',
            -17, vid, ['DCUnique', UID], 1, 99.0), node]])
    choose = command('ConditionalsConditionAccumulationNumber', ['DCUnique', UID], 5,
        branches[0], command('ConditionalsConditionAccumulationNumber', ['DCUnique', UID],
                            3, branches[1], branches[2]))
    extras = [n for n in normal if n[1][0] in ('AddFeverPoint', 'CreateCondition')]
    if len(extras) != 2:
        raise ValueError('non-Fever support effects drift')
    top[1:2] = [choose, command('ConditionalsFeverMode', ['Block', []], ['Block', extras])]
    tree[10] = 2
    validate(tree)
    return tree


def validate(tree):
    failures = dsl_gate_failures(dsl_gates(tree, element=2))
    if failures:
        raise ValueError(failures)
    conditions = list(cmds(tree, 'ConditionalsConditionAccumulationNumber'))
    if [c[2] for c in conditions] != [5, 3] or any(c[1] != ['DCUnique', UID] for c in conditions):
        raise ValueError('stage thresholds drift')
    if tree[10] != 2 or any(a[24] != 2 for a in cmds(tree, 'CreateHitArea')):
        raise ValueError('ability damage reference drift')


def revise_rows(leader, third, first):
    leader, third = deepcopy(leader), deepcopy(third)
    for rows, offset in ((leader, 0), (third, 2)):
        targets = [r for r in rows if r[25+offset] == '8' and r[45+offset] == '211'
                   and r[46+offset] in ('', '0')]
        if len(targets) != 1 or targets[0][49+offset:51+offset] not in (
                ['50000', '50000'], ['25000', '25000']):
            raise ValueError('Regis self Fever gauge baseline drift')
        targets[0][49+offset:51+offset] = ['25000', '25000']
    grant = next(r for r in first if r[47] == '461' and r[68] == str(UID))
    end = [leader[0][0], *deepcopy(grant[3:])]
    end[25] = '184'  # Native FeverEnd; one event per completed Fever.
    if not any(r[25] == '184' and r[45] == '461' and r[66] == str(UID) for r in leader):
        leader.append(end)
    multiplier = next(r for r in third if r[109] == '412')
    skill = deepcopy(multiplier)
    skill[109] = '411'  # Skill source; disjoint from 412, so no double multiplier.
    skill[110:113] = ['0', '', '']  # Only Regis' skill, not unrelated allies' skills.
    if not any(r[109] == '411' for r in third):
        third.append(skill)
    for kind, rows in (('leader_ability', leader), ('ability', third)):
        for row in rows:
            if errors := row_problems(kind, row, element=2):
                raise ValueError(errors)
    return leader, third


def revise_text(slot, text):
    text = text.replace('自身技能槽＋50%', '自身技能槽＋25%')
    if slot == 0:
        extra = 'FEVER模式结束时，自身「浪涌充能」＋1层'
        return text if extra in text else text + '\n' + extra
    if slot == 3:
        return text.replace('雷属性角色能力伤害额外乘区＋25%（技能本体除外）',
                            '雷属性角色能力伤害、自身技能伤害额外乘区＋25%')
    raise ValueError(slot)
