"""Ghandagoza native portion; adversity cap needs explicit client compatibility decision."""
from wf_gbf_duo_rows import row, RESONANCE, LEADER_WATER, set_fields
import wf_gbf_duo_dsl as D

CID = 129987
BREAK = 12998701


def build_rows(pack):
    def r(slot, effect, value=0, **kwargs):
        return row(CID, slot, effect, value, main=slot in (3,6), **kwargs)
    leader = [r(0, 'AttackPoint', 300, target=5, groups='Blue'),
              r(0, 'PowerFlipDamage', 300),
              r(0, 'EaseOfHeal', 10, target=5, groups='Blue', pre=[RESONANCE]),
              r(0, 'SkillGauge', 100, target=5, groups='Blue', pre=[RESONANCE])]
    abilities = {i: [] for i in range(1,7)}
    a = abilities
    for effect in ('AttackPoint', 'PowerFlipDamage'):
        a[1].append(r(1,effect,2,during=True,trigger='HpDecrease',threshold=.01,
                      target=2,pre=[LEADER_WATER],start=100000))
    a[1].append(r(1,'SkillGauge',30,trigger='SkillInvoke',threshold=1,target=2))
    # Enemy-sensitive checker receives the actual attacked enemy from the calculator.
    for effect,value in (('UniqueSlayer',10),('PowerFlipDamage',20)):
        a[2].append(r(2,effect,value,during=True,trigger='OneOfEnemyConditionAccumulationCountUnique',
                      threshold=1,uid=BREAK,limit=5,target=5,groups='Blue',
                      content_uid=BREAK if effect=='UniqueSlayer' else None))
    fracture = r(2,'TriggerEnemyConditionUnique',1,unit='count',
                 trigger='OneOfEnemyPowerFlipHitLvAny',threshold=1,
                 content_uid=BREAK,pre=[LEADER_WATER])
    set_fields(fracture,'instant_content', **{'frame.power1':9999900000,'frame.first_max':9999900000,
                                            'cancelable':1})
    a[2].append(fracture)
    opening = 'battle/action/skill/ability/ability_skill_ghandagoza_opening'
    a[3].append(r(3,'InvokeSkill',path=opening,pre=[RESONANCE]))
    a[3].append(r(3,'Barrier',50,trigger='InvokeGuts',threshold=1,puller=5,target=7))
    invincible = r(3,'ConditionInvincible',0,trigger='InvokeGuts',threshold=1,puller=5,target=7)
    set_fields(invincible,'instant_content', **{'frame.power1':48000000,'frame.first_max':48000000,
                                              'number.power1':100000,'number.first_max':100000})
    a[3].append(invincible)
    # Native SumOfPartyHpLow is boolean, not a percent counter. Explicit 1% bins
    # produce floor(missing party HP percent), with no permanent accumulating buff.
    for missing in range(1,101):
        for effect,value in (('AttackPoint',3),('PowerFlipDamage',3),('SeparatedTermPowerFlipDamage',1)):
            rr = r(3,effect,value,during=True,trigger='SumOfPartyHpLow',threshold=(100-missing)/100,
                   target=5,groups='Blue',limit=1)
            a[3].append(rr)
    a[4] = [r(4,'Stunify',300,target=5,groups='Blue'),
            r(4,'StunWinceSlayer',10,target=5,groups='Blue'),
            r(4,'ParalysisSlayer',10,target=5,groups='Blue')]
    for effect in ('AttackPoint','PowerFlipDamage'):
        a[5].append(r(5,effect,30,during=True,trigger='OneOfEnemyConditionCountDebuff',
                      threshold=1,limit=5,target=5,groups='Blue'))
    a[6] = [r(6,'ChangeSkillFlag')]
    programs = {opening: D.ghandagoza_opening()}
    return leader,a,programs
