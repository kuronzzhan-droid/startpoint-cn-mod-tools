"""Official-row-derived wind Fever ability kit for university photographer Celtie."""
from copy import deepcopy

import wf_client_legality as legality
import wf_describe
import wf_campus_celtie_common as C

TITLE = '定格星风的剑圣'
LEADER_NAME = '追逐光影的课后时光'
SKILL_NAME = '风中快门·星空牙'
SKILL_DESC = ('向最近的敌人突进，以神速剑技对命中的敌人及其周围造成风属性伤害／'
    '赋予自身攻击力提升效果／队长为风属性时，赋予队伍贯穿与最大速度固定效果／'
    '非FEVER状态下发动时，增加FEVER槽。')
BIO = ('以大学摄影社学生身份体验另一种日常的星之剑圣。她依然不擅长在人群中寒暄，'
    '却渐渐习惯举起相机，认真记录朋友与校园的光影。追风挥剑的手，如今也能温柔地按下快门。'
    '「别动……这次，我想把你的笑容留下。」')


def character():
    logical = 'master/character/character.orderedmap'
    row = C.core.read_csv_lines(C.official_flat(logical)[C.TEMPLATE_ID])[0]
    for i in (0, 8):
        row[i] = C.CODE
    row[17], row[18] = C.CID, LEADER_NAME
    row[19:25] = [C.CID+str(i) for i in range(1,7)]
    row[27] = C.CID
    row[26] = 'Attacker'
    row[36] = '6,6,6,6,6,6'
    assert row[2:4] == ['5','3']
    if legality.character_stance_problems(row):
        raise ValueError('invalid character stance')
    return row


def character_text():
    row = C.core.read_csv_lines(C.official_flat(
        'master/character/character_text.orderedmap')[C.TEMPLATE_ID])[0]
    row[2:8] = [BIO, TITLE, SKILL_NAME, SKILL_DESC, SKILL_NAME+'＋', SKILL_DESC]
    row[8:10] = ['(None)', '(None)']
    row[10] = LEADER_NAME
    return row


def _row(table, key, index=0, **patch):
    row = deepcopy(C.official_rows(table,key)[index])
    row = ['Green' if value in ('White','Yellow','Blue','Red','Black') else value for value in row]
    for column,value in patch.items():
        row[int(column[1:])] = str(value)
    return row


def build_kit():
    # I253 -> I254 changes only the native elemental ability-damage enum.
    leader = [
        _row('leader_ability','141201',c49=100000,c50=150000),
        _row('leader_ability','151001',1,c49=10000,c50=20000),
        _row('leader_ability','151009',0,c107=154,c111=75000,c112=100000),
    ]
    slots = {
        1: [
            _row('ability','1412011'),
            _row('ability','1310131',0,c48=5,c51=25000,c52=50000),
        ],
        2: [
            _row('ability','1310202',0,c35=600,c47=254),
            _row('ability','1510013',0,c109=154,c110=0,c111='',c113=50000,c114=100000),
        ],
        3: [
            _row('ability','1310203',0,c35=1200,c51=25000,c52=50000),
            _row('ability','1310202',0,c27=8,c28='',c29='',c35=1200,c47=254,c51=2500000,c52=5000000),
        ],
        4: [_row('ability','1412014')],
        5: [
            _row('ability','1510451',1,c51=10000,c52=20000),
            _row('ability','1510011',0,c51=5000,c52=10000),
        ],
        6: [
            _row('ability','1510013',0,c109=154,c113=30000,c114=60000),
            _row('ability','1310133',2,c51=7500,c52=15000),
        ],
    }
    panels=[]
    for row in leader:
        row[0] = C.CODE
        _validate(row,'leader_ability')
        panels.append('队长：'+wf_describe.describe_line(row,'leader_ability'))
    result={}
    for slot,rows in slots.items():
        for row in rows:
            row[0],row[1],row[2] = C.CODE+'_'+str(slot), ('false' if slot<=3 else 'true'), 'attack_green'
            row[3:5] = ['0','']
            _validate(row,'ability')
            panels.append(f'能力{slot}：'+wf_describe.describe_line(row,'ability'))
        result[C.CID+str(slot)] = rows
    return leader,result,panels


def _validate(row, table):
    problems = (legality.client_legality_problems(table,row)
        + legality.declared_block_field_problems(table,row)
        + legality.ability_element_column_problems(table,row,3))
    if problems:
        raise ValueError(f'{table}: {problems}')


def source_notes():
    return {
        'portrait_and_pixel_template': {'id':141201,'code':'wind_spgirl_4anv','title':'星之剑圣'},
        'official_versions': [
            {'id':141001,'code':'wind_spgirl','title':'可爱剑鬼'},
            {'id':141021,'code':'wind_spgirl_1anv','title':'星之少女骑士'},
            {'id':161135,'code':'wind_spgirl_hw22','title':'恋爱的吸血剑鬼'},
            {'id':141201,'code':'wind_spgirl_4anv','title':'星之剑圣'},
        ],
        'excluded_local_variant': {'id':149996,'reason':'苍蓝疾光为既有自制变体，未作为官方来源'},
        'skill_donors': ['141201星之剑圣：完整剑技生命周期','131013夏日伊路米：AddFeverPoint'],
        'ability_donors': ['141201星之剑圣','131020一周年雷吉斯','131013夏日伊路米',
            '151001奈芙提姆','151009庆典奈芙提姆','151045夏日莉莉丝'],
        'damage_system':'主动剑阵维持原生技能伤害；风队技能和FEVER触发的追加伤害为原生能力伤害I254',
        'description_safety':'无Unique、自定义说明、InvokeSkill或FeverEnd增殖；全部由官方原生行重组',
        'acceptance':'静态候选；须客户端观察剑阵、FEVER触发频率与实际伤害',
    }
