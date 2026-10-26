"""索利兹的早期草稿行与状态搬运。

**已被 ``wf_gbf_kit_soriz`` 取代**（完成态 kit 直接按 design/soriz.json 装配）。
保留在这里只作为草稿证据与老契约测试的夹具；``transfer`` 已按 D15 修掉「同帧先删目标」。
"""
from wf_gbf_duo_rows import row, RESONANCE, unique_pre, set_fields
import wf_gbf_duo_dsl as D

CID = 129986
CROWS, VETERAN, GUTS, HEAT, ACTIVE_HEAT = range(12998601,12998606)
FEVER, NO_FEVER = ('Fever','','','',None), ('NotFever','','','',None)


def transfer(source, destination, *, cap=10, clear_source=False):
    # 同帧结算顺序固定「赋予(8) → 删除(9)」：先删目标会把本帧刚叠上的层数清零（D15 / 报告 08 §5-①）。
    # 目标固有在上一段流程里已经删净，进来必然是 0 层，不需要也不允许先删。
    body = []
    for count in range(1,cap+1):
        body.append(D.cmd('ConditionalsConditionAccumulationNumber',['DCUnique',source],count,
                         D.block(D.condition(0,['ACUnique',destination,D.v(1)],cancelable=False)),D.block()))
    if clear_source:
        body.append(D.cmd('DeleteCondition',0,['DCUnique',source],99,0,'',['Default']))
    return D.find(0,1,*body)


def build_rows(pack):
    def r(slot,effect,value=0,**kwargs):
        return row(CID,slot,effect,value,main=slot==3,**kwargs)
    def invoke(slot,name,trigger,**kwargs):
        return r(slot,'InvokeSkill',trigger=trigger,threshold=1,
                 path=f'battle/action/skill/ability/ability_skill_soriz_{name}',**kwargs)
    def grant(slot,uid,trigger,threshold=1,**kwargs):
        return r(slot,'ConditionUnique',1,unit='count',content_uid=uid,
                 trigger=trigger,threshold=threshold,**kwargs)
    leader = [r(0,'AttackPoint',100,target=5,groups='Blue'),r(0,'PowerFlipDamage',100),
              r(0,'PowerFlipDamage',300,during=True,trigger='Fever',pre=[RESONANCE]),
              r(0,'AddCombo',16,unit='count',trigger='BallFlip',threshold=1,pre=[RESONANCE,FEVER]),
              r(0,'Barrier',15,target=5,groups='Blue',trigger='PowerFlip',threshold=1,pre=[RESONANCE,FEVER]),
              invoke(0,'fever_begin','Fever',pre=[RESONANCE]),
              invoke(0,'fever_end','FeverEnd',pre=[RESONANCE])]
    for effect,value in (('AttackPoint',5),('PowerFlipDamage',10)):
        leader.append(r(0,effect,value,during=True,trigger='HpDecrease',threshold=.01,start=100000))
    a = {i:[] for i in range(1,7)}
    a[1] = [r(1,'SkillGauge',100,target=5,groups='Blue',pre=[RESONANCE]),
            r(1,'SecondSkillGauge',30,target=5,groups='Blue',pre=[RESONANCE]),
            r(1,'FeverPoint',50,target=5,groups='Blue',pre=[RESONANCE])]
    for trigger,value,limit in [('PowerFlipLv3',350,None),('SkillInvoke',650,None),('SkillInvoke',1500,1)]:
        a[1].append(r(1,'AddFeverPoint',value,unit='count',trigger=trigger,threshold=1,limit=limit))
    a[2] = [grant(2,VETERAN,'PowerFlipLv3',3),
            r(2,'AttackPoint',200,during=True,pre=[unique_pre(VETERAN)]),
            r(2,'PowerFlipDamage',300,during=True,pre=[unique_pre(VETERAN)]),
            r(2,'AddCombo',8,unit='count',trigger='BallFlip',threshold=1,pre=[unique_pre(VETERAN,2),NO_FEVER]),
            r(2,'InvokeSkill',trigger='PowerFlipLv3',threshold=3,pre=[unique_pre(VETERAN,2)],
              path='battle/action/skill/ability/ability_skill_soriz_next99'),
            r(2,'PowerFlipLv3DamageSlayer',15,during=True,pre=[unique_pre(VETERAN,5)])]
    for missing in range(1,101):
        a[2].append(r(2,'PowerFlipDamage',20,during=True,trigger='SumOfPartyHpLow',
                      threshold=(100-missing)/100,limit=1,pre=[unique_pre(VETERAN,3)]))
    adversity = r(2,'ConditionAdversity',25,target=5,groups='Blue',
                  trigger='ConditionAccumulationCountUnique',threshold=4,uid=VETERAN,limit=1)
    set_fields(adversity,'instant_content', **{'strength2.power1':50000,'strength2.first_max':50000,
        'frame.power1':9999900000,'frame.first_max':9999900000})
    a[2].append(adversity)
    a[3] = [grant(3,CROWS,'Fever')]
    for effect,value in [('AttackPoint',100),('PowerFlipDamage',100),('SeparatedTermPowerFlipDamage',3)]:
        a[3].append(r(3,effect,value,during=True,trigger='ConditionAccumulationCountUnique',threshold=1,uid=CROWS))
    a[4] = [r(4,'SkillGaugeCharging',10,during=True,trigger='HpLowExcludesThreshold',threshold=.5,
              target=5,groups='Blue')]
    a[5] = [r(5,'PowerFlipDamage',100,trigger='Fever',threshold=1,limit=10,pre=[RESONANCE])]
    for effect,value in [('AttackPoint',5),('PowerFlipDamage',10)]:
        a[5].append(r(5,effect,value,during=True,trigger='HpDecrease',threshold=.01,start=100000))
    a[6] = [invoke(6,'heat_end','FeverEnd'),invoke(6,'heat_begin','Fever')]
    for uid,pre,effect,value in [(HEAT,NO_FEVER,'PowerFlipDamage',30),(HEAT,NO_FEVER,'FeverPoint',15),
                                (ACTIVE_HEAT,FEVER,'PowerFlipDamage',50)]:
        a[6].append(r(6,effect,value,during=True,trigger='ConditionAccumulationCountUnique',
                      threshold=1,uid=uid,pre=[pre]))
    fever_begin = D.tree(D.find(0,35,D.condition(0,['ACHealRejection',D.v(99999999)],
                                               key='soriz_fever_no_heal',cancelable=False),elements=(2,)))
    fever_end = D.tree(D.find(0,35,D.cmd('DeleteCondition',0,['DCHealRejection'],99,0,
                                       'soriz_fever_no_heal',['Default']),elements=(2,)),
                      D.find(1,1,D.cmd('DeleteCondition',1,['DCUnique',GUTS],99,0,'',['Default'])))
    programs = {
        'fever_begin':fever_begin,'fever_end':fever_end,
        'next99':D.tree(D.find(0,97,D.condition(0,['ACComboBoost',D.v(1),D.v(99)]))),
        'heat_end':D.tree(transfer(CROWS,HEAT)),
        'heat_begin':D.tree(transfer(HEAT,ACTIVE_HEAT,clear_source=True)),
    }
    return leader,a,{f'battle/action/skill/ability/ability_skill_soriz_{name}':t for name,t in programs.items()}
