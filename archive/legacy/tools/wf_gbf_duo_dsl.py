"""Native skill building blocks for the two authored GBF projects."""
from copy import deepcopy

import wf_seasonal7_common as C


def v(value):
    return [{'min': value, 'max': value}]


def cmd(name, *args):
    return ['Command', [name, *args]]


def block(*nodes):
    return ['Block', list(nodes)]


def tree(*nodes):
    return ['ActionDsl', 1, ['None'], False, False, False, False, False, False, False, 0, block(*nodes)]


def find(subject, kind, *nodes, elements=()):
    return cmd('FindAllSubjects', subject, kind, list(elements), [], [], [], [], ['DoNothing'], block(*nodes))


def condition(subject, *conditions, key='', cancelable=True, target_kind=3):
    # 下标 10 = 付与对象种类。FindAllSubjects 33/34/35/49/82 下官方一律 3（Member），
    # 97（球）才是 2，113/145 才是 1；错配 = 施法 C16102（记忆卡 wf-createcondition-target-kind）。
    return cmd('CreateCondition', subject, list(conditions), v(1), ['GenericConditionHitEffect'],
               cancelable, False, key, None, False, target_kind, v(1), False)


def buff(kind, amount, frames=900):
    return [kind, v(frames), v(amount), v(1)]


def effect(code, eid, subject=-18, scale=1):
    return cmd('ShowEffect', f'{code}_{eid}',
               ['SpecifyEffectDirectly', f'battle/effect/skill_unique/{code}/{eid}/effect'],
               subject, ['ForesideOfCharacter'], ['PlayOnlyFirstSequence'], ['AB'], 0, 0, 0,
               True, False, ['Some', v(scale)])


def wait(frames, *nodes):
    return ['Event', ['Wait', frames, '*', block(*nodes)]]


def native_attack(pack, subject, multiplier):
    donor = pack.template_dsl('battle/action/skill/action/rare5/waterdragon_kunfu$waterdragon_kunfu_2')
    node = deepcopy(next(n for n in C.walk(donor) if isinstance(n, list) and n and n[0] == 'CreateNormalAttack'))
    node[1], node[2], node[6] = subject, 2, v(multiplier)
    return ['Command', node]


def ghandagoza_skill():
    enemy = find(0, 49,
        cmd('DeleteCondition', 0, ['DCAll', 2], 3, 0, '', ['Default']),
        condition(0, ['ACParalysis', v(600)], ['ACToleranceOfElement', v(900), 2, v(-.3), v(1)]))
    def ally(enhanced):
        # 35 = 「除自身外」的队伍角色；含自身的己方全体是 33（官方文案实证）。
        amount, chase = (2.5, .5) if enhanced else (1.5, .25)
        return find(1, 33,
            condition(1, buff('ACAttackPoint', amount), buff('ACPowerFlipDamage', amount),
                      ['ACAdversity', v(900), v(.5), v(1.5), v(1)],
                      ['ACDamageOfElement', v(900), 2, v(chase), v(1)]),
            cmd('CreateBarrier', 1, v(.25), ['GenericBarrierHitEffect']),
            # ConditionalsHealthPointRatioOf is HP >= threshold: low branch is last.
            cmd('ConditionalsHealthPointRatioOf', 1, 20, block(), block(
                *[wait(t, cmd('CreateRatioHeal', 1, 2, v(.03), [], v(0), ['GenericHealHitEffect']))
                  for t in range(120, 721, 120)])), elements=(2,))
    return tree(cmd('StopBall', -18, 10, ['RestoreToSpeedBeforeActionExecution'], ['EF'], 0),
                effect('ghandagoza', 'a68b8280c4ea', scale=.55), enemy,
                cmd('ConditionalsChangeSkillFlag', 1, block(ally(True)), block(ally(False))))


def soriz_skill(pack):
    donor = pack.template_dsl('battle/action/skill/action/rare5/waterdragon_kunfu$waterdragon_kunfu_2')
    area = deepcopy(C.commands(donor, 'CreateHitArea')[0])
    # Reuse the official nearby-enemy collision, one hit per enemy. Do not
    # substitute an all-enemy selector, which also damages distant targets.
    area[4:6], area[21:23] = [0, 0], [10, 11]
    area[23] = block(effect('soriz', '04164345c46a', subject=11, scale=.8), native_attack(pack, 11, 40))
    hit = ['Command', area]
    return tree(cmd('StopBall', -18, 10, ['RestoreToSpeedBeforeActionExecution'], ['EF'], 0),
        find(0, 1, cmd('CreateRatioAttack', 0, 2, v(.25)),
             condition(0, buff('ACAttackPoint', 2), buff('ACPowerFlipDamage', 2)),
             condition(0, ['ACUnique', 12998601, v(3)], cancelable=False)),
        # 33 = 己方全体（含自身）；35 是「除自身外」，贯通/二连击必须包含索利兹本人。
        find(1, 33, condition(1, ['ACPiercing', v(900)],
                            ['ACAdditionalDirectAttack', v(900), v(2), v(1), v(1)]), elements=(2,)),
        wait(15, hit))


def ghandagoza_opening():
    return tree(find(0, 33, cmd('CreateRatioAttack', 0, 1, v(1)),
                     wait(1, cmd('CreateBarrier', 0, v(1), ['GenericBarrierHitEffect']),
                          condition(0, ['ACGuts', v(1)], cancelable=False))))
