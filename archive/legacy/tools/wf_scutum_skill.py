"""盾牌座主动技能：原生回复/净化、风直击增益及 A6 连击替换。"""
from copy import deepcopy
import zlib

import wf_dsl
from wf_character_revision import encode_tree

CODE = 'scutum_valentine'
SUFFIX = '.action.dsl.amf3.deflate'
ACTIVE_PATHS = tuple(f'battle/action/skill/action/rare5/{CODE}${CODE}_{lv}' for lv in (1, 2))
EFFECT = f'battle/effect/skill_unique/{CODE}/{CODE}'


def value(number):
    return [{'min': number, 'max': number}]


def command(name, *params):
    return ['Command', [name, *params]]


def block(*expressions):
    return ['Block', list(expressions)]


def action(*expressions, buff_target=0):
    return ['ActionDsl', 1, ['None'], False, False, False, False, False, False,
            False, buff_target, block(*expressions)]


def condition(target, *contents):
    return command('CreateCondition', target, list(contents), value(1),
                   ['GenericConditionHitEffect'], True, False, '', None, False,
                   3, value(1), False)


def find(target, selector, body, *, elements=()):
    return command('FindAllSubjects', target, selector, list(elements), [], [], [], [],
                   ['DoNothing'], body)


def heal_and_cleanse(target):
    return block(command('CreateRatioHeal', target, 2, value(.1), [4], value(.5),
                         ['GenericHealHitEffect']),
                 command('DeleteCondition', target, ['DCAll', 3], 1, 0, '', ['Default']))


def wind_combo(times, strength):
    return find(204, 82, block(condition(204,
        ['ACAdditionalDirectAttack', value(1200), value(times), value(strength), value(1)])),
        elements=(4,))


def build_skill(level, official_loader, *, fixed_speed_strength=1):
    if level not in (1, 2):
        raise ValueError('Scutum skill level must be 1 or 2')
    if fixed_speed_strength not in (0, 1, 2, 4):
        raise ValueError('fixed speed strength must be an explicit supported design value')
    path = f'battle/action/skill/action/rare5/prince_zero$prince_zero_{level}{SUFFIX}'
    tree = wf_dsl.parse_dsl(zlib.decompress(official_loader(path), -15))['tree']
    # 保留供体原生发招停球和一次完整演出，不继承其四项旧增益。
    opening = deepcopy(tree[11][1][:2])
    if opening[0][1] != ['StopBall', -18, 65, ['RestoreToSpeedBeforeActionExecution'], ['EF'], 0]:
        raise ValueError('prince_zero opening changed')
    effect = opening[1][1]
    if effect[0] != 'ShowEffect' or effect[2] != [
            'SpecifyEffectDirectly', 'battle/effect/skill_unique/prince_zero/prince_zero']:
        raise ValueError('prince_zero skill effect changed')
    effect[1], effect[2][1] = CODE + '_cast', EFFECT
    combo = command('ConditionalsChangeSkillFlag', 1,
                    block(wind_combo(5, .5)), block(wind_combo(2, .3)))
    def movement(target):
        return condition(target, ['ACFlying', value(810)],
                         ['ACFixedSpeed', value(810), value(fixed_speed_strength), value(0), value(1)])
    return action(*opening,
        # 与官方风奶相同的互斥目标组，避免本机成员被重复恢复。
        find(201, 113, heal_and_cleanse(201)),
        find(202, 145, heal_and_cleanse(202)),
        heal_and_cleanse(-33),  # 原生远端参战者通道。
        find(203, 82, block(condition(203,
             ['ACDirectDamage', value(1200), value(1.5), value(1)])), elements=(4,)),
        # selector1只选施法者；过滤后才给风主成员施加二选一连击。
        find(206, 1, block(combo), elements=(4,)),
        find(205, 82, block(movement(205))),
        find(207, 86, block(movement(207))))


def assets(official_loader, *, fixed_speed_strength=1):
    return {('common', path + SUFFIX): encode_tree(build_skill(lv, official_loader,
                fixed_speed_strength=fixed_speed_strength))
            for lv, path in enumerate(ACTIVE_PATHS, 1)}


def metadata(*, fixed_speed_strength=1):
    return dict(heal_max_hp_ratio=.1, wind_heal_bonus=.5, cleanse_count=1,
                wind_direct_damage=1.5, buff_seconds=20,
                self_wind_required_for_combo=True, basic_combo=[2, .3],
                learned_a6_combo=[5, .5], flying_and_fixed_speed_seconds=13.5,
                fixed_speed_strength=fixed_speed_strength, charging_penalty=0,
                required_capabilities=[])
