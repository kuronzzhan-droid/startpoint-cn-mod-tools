"""奈芙队长：按当前协力球数量刷新自身直击判定，不增加伤害倍率。"""
from wf_bianca_dragon_skill import block, command, value

STRING_ID = 'ruin_girl_campus_ball_hit_count'
ACTION_PATH = 'battle/action/skill/action/ability_skill/ruin_girl_campus$' + STRING_ID
DESCRIPTION = '暗属性共鸣时，每有1个协力球存在，自身直击判定次数+1。'
# 作者 2026-09-27 多人卡顿修复（方案1，K=10）：队长 T77 行由每 1 帧改为每 10 帧执行本程序；
# 隐形状态持续帧 = 2 × 周期（原 1 帧/2 帧），相邻两次刷新之间留一个周期余量不断档。
UPDATE_PERIOD_FRAMES = 10
TTL_FRAMES = 2 * UPDATE_PERIOD_FRAMES


def action_tree():
    # Native FloatArray sums its entries; count remains dynamic in this one scope.
    def condition(base, bonus):
        times = [{'min': base, 'max': base}, {'min': 1, 'max': 1, 'mul': 1}]
        return command('CreateCondition', -17,
            [['ACAdditionalDirectAttack', value(TTL_FRAMES), times, value(bonus), value(1)]],
            value(1), ['None'], False, False, STRING_ID, None, True, 3, value(1), True)
    return ['ActionDsl', 1, ['None'], False, False, False, False, False, False,
            False, 0, block(
                command('MultiballNumberVariable', 1, False, None, [], 1, 2147483647),
                # The helper is invisible; this query sees the ordinary skill buff only,
                # so it cannot feed back into itself and tracks that buff's expiry.
                command('ConditionalsConditionExist', -17, ['DCAdditionalDirectAttack'],
                        block(condition(2, 1)), block(condition(1, 0))))]


def leader_row(source):
    from wf_nephtim_fever_abilities import CODE, _instant, _set
    r = _instant(source, 629, pre='dark', trigger=77, threshold=UPDATE_PERIOD_FRAMES)
    _set(r, {70: STRING_ID, 71: ACTION_PATH})
    return [CODE, '0', ''] + r[5:]


def metadata():
    return {
        "string_id": STRING_ID, "action_path": ACTION_PATH, "location": "leader_ability (last row)",
        "trigger": 77, "update_period_frames": UPDATE_PERIOD_FRAMES,
        "condition_duration_frames": TTL_FRAMES, "condition_key": STRING_ID, "invisible": True,
        "refresh_delay_frames_max": UPDATE_PERIOD_FRAMES,
        "skill_buff_alignment": "base hit count follows the visible skill buff at the next refresh (<= period)",
        "gate_closed_tail_frames_max": TTL_FRAMES,
    }
