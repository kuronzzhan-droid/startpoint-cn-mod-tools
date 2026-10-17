"""盾牌座队长突进、A5全场追击和收集最近目标追击；触发门槛由表负责。"""
from wf_character_revision import encode_tree
from wf_scutum_skill import CODE, SUFFIX, action, block, command, condition, find, value

RETALIATION = f'battle/action/skill/action/ability_skill/{CODE}${CODE}_retaliation'
PIERCING_CHASE = f'battle/action/skill/action/ability_skill/{CODE}${CODE}_piercing_chase'
COLLECT_CHASE = f'battle/action/skill/action/ability_skill/{CODE}${CODE}_collect_chase'
PROGRAM_PATHS = (RETALIATION, PIERCING_CHASE, COLLECT_CHASE)


def retaliation():
    # 空场仍赋予贯穿；有目标时保留直击，30帧沿原生 GH 朝向突进。
    return action(find(211, 82, block(condition(211, ['ACPiercing', value(300)]))),
        find(214, 86, block(condition(214, ['ACPiercing', value(300)]))),
        command('FindNearSubjects', -18, 1, 49, ['DoNothing'], 212,
                block(command('MoveBall', -18, ['GH', 212], 0, 30, 40, ['KeepGoing'], False))))


def piercing_chase():
    # 原生I629保留能力来源；buffTargetAs=4切换主加成，不能许诺全部直击乘区。
    hit = command('CreateNormalAttack', 213, 4, [], [], 0, value(35), value(0),
                  False, False, False, False, False, value(0), value(0), ['Coarse'], True)
    return action(find(213, 49, block(hit)), buff_target=4)


def collect_chase():
    # 作者已确认最近目标方案；这里不能宣称锁定直击时的原受击者。
    hit = command('CreateNormalAttack', 215, 4, [], [], 0, value(5), value(0),
                  False, False, False, False, False, value(0), value(0), ['Coarse'], True)
    return action(command('FindNearSubjects', -18, 1, 49, ['DoNothing'], 215,
                          block(hit)), buff_target=4)


def assets():
    return {('common', RETALIATION + SUFFIX): encode_tree(retaliation()),
            ('common', PIERCING_CHASE + SUFFIX): encode_tree(piercing_chase()),
            ('common', COLLECT_CHASE + SUFFIX): encode_tree(collect_chase())}


def metadata():
    return dict(retaliation_duration_frames=30, retaliation_speed=40,
                retaliation_suppresses_direct_attack=False, piercing_seconds=5,
                chase_multiplier=35, chase_dsl_element=4, chase_buff_target_as=4,
                collect_target='nearest enemy, not original direct-hit target',
                collect_multiplier=5, collect_target_count=1,
                native_ability_source_preserved=True, required_capabilities=[])
