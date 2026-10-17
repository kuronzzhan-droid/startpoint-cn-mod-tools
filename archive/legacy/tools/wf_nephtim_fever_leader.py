"""校园奈芙提姆队长原生表行；特殊PF程序与文本由PF模块提供。"""
from copy import deepcopy
import wf_nephtim_ball_hit_count as ball_hit_count

from wf_nephtim_fever_abilities import (CHANGE_SKILL_STRING_ID, CODE, LEADER_PIERCING_GROWTH_STRENGTH,
                                        PIERCING_EXTENSION_STRENGTH, PIERCING_PERIOD_FRAMES,
                                        _instant, _percent, _set, enhance_row, piercing_growth_rows)

PF_ID = CODE + "_fever"
PF_STRING_ID = PF_ID + "_powerflip"
# 每 35 连击暗队 Fever 获得量（I50）的永久成长：原 20_000（+20%）；作者 2026-09-27 第二批
# 无上限成长原位放缓，3 分钟实际触发 ≥30 次 → 1/10：+2%。
# 作者 2026-09-27 第三轮（c，成长复核：「1/10 砍太多了」→「砍到4/5」「数值尽量取5的倍数」）：暗队 Fever
# 获得量只能靠这条成长 → 4/5 档，20×4/5=16 就近取 15%（wf_balance_20260927c_nephtim）。
FEVER_GAIN_GROWTH_STRENGTH = 15_000


def leader_rows(source, *, piercing_extension="dark_resonance",
                power_flip_id=PF_ID, power_flip_string_id=PF_STRING_ID):
    """返回124列队长行；贯穿延时采用作者确认的暗共鸣常驻方案（2026-09-27 起由能力2承载）。"""
    if piercing_extension != "dark_resonance":
        raise ValueError("piercing_extension must be the approved dark_resonance strategy")
    pf = _instant(source, 722, pre="dark")
    _set(pf, {82: power_flip_id, 83: "1,2,3", 84: power_flip_string_id})
    # 作者 2026-09-27（方案B）：只把 I536 技能强化开关从能力1搬进队长，紧跟 I722；
    # 召唤/清理行（T232/528/187/77 在官方队长表零先例）留在能力1。
    enhance = enhance_row(source)
    direct = _instant(source, 33, 400_000, pre="dark", target=5)
    attack = _instant(source, 32, 200_000, pre="dark", target=5)
    # 作者 2026-09-27：Fever 中技能槽上限+10%（during 124）与 I190 贯穿延时 20% 移出队长，
    # 由能力2承载（贯穿合并为单行 40%）。
    # Native T12 crosses multiples of the current combo; I50 permanently adds
    # the general Fever gain modifier. Both I50/I56 exist in LeaderAbilityValues.
    growth = _instant(source, 50, FEVER_GAIN_GROWTH_STRENGTH, pre="dark", target=5,
                      trigger=12, threshold=35)
    duration = _instant(source, 56, 100_000, pre="dark")
    removal_charge = _instant(source, 211, 5_000, pre="dark", target=5,
                              trigger=194, threshold=1)
    rows = [pf, enhance, direct, attack, growth, duration, removal_charge]
    # 作者 2026-09-27 第二批：能力3「贯穿每累计2秒 → 暗队攻击力/直击伤害」的无上限部分搬进队长，
    # 追加在 9/25 的 ball_hit_count 行之后（第9、10行），强度 1%/次、不限次；能力3 保留有上限的弱化版。
    # 同日第三轮（c）：强度回调到 7%/次（LEADER_PIERCING_GROWTH_STRENGTH）。
    moved = piercing_growth_rows(source, LEADER_PIERCING_GROWTH_STRENGTH, LEADER_PIERCING_GROWTH_STRENGTH)
    convert = lambda row: [CODE, "0", ""] + deepcopy(row[5:])
    return [convert(row) for row in rows] + [ball_hit_count.leader_row(source)] + [convert(row) for row in moved]


def flat_string_rows():
    # I722's single string dependency belongs to the combined-PF module.
    return {}


def metadata():
    return {
        "required_client_capabilities": [],
        "power_flip_id": PF_ID, "power_flip_string_id": PF_STRING_ID,
        "dark_direct_damage_percent": 400, "dark_attack_percent": 200,
        "skill_enhancement_flag": {"content": 536, "string_id": CHANGE_SKILL_STRING_ID,
                                   "requires_dark_resonance": True, "position": "after I722",
                                   "official_leader_precedent": "121189#3",
                                   "moved_from": "ability1 2026-09-27"},
        "fever_gain_growth": {"combo_step": 35, "increase_percent": _percent(FEVER_GAIN_GROWTH_STRENGTH),
                              "target": "dark party", "requires_fever": False,
                              "trigger_limit": None, "persists_after_combo_reset": True,
                              "counter": "native T12 current-combo multiples; remainder resets on combo reset",
                              "slowed": "2026-09-27 batch 2: 20% -> 2% (>=30 triggers per 3 minutes)",
                              "revised": "2026-09-27 batch c: 2% -> 15% (4/5 of the original 20%, rounded to 5)"},
        "piercing_growth": {"trigger": 235, "period_frames": PIERCING_PERIOD_FRAMES,
                            "attack_percent": _percent(LEADER_PIERCING_GROWTH_STRENGTH),
                            "direct_damage_percent": _percent(LEADER_PIERCING_GROWTH_STRENGTH),
                            "target": "dark party", "requires_dark_resonance": True, "requires_fever": True,
                            "trigger_limit": None, "rows": [9, 10],
                            "moved_from": "ability3 rows 3-4 (2026-09-27 batch 2; ability3 keeps a capped copy)",
                            "leader_precedents": {"T235": "live 169999#7-9", "pre12": "live 149989#4-6"}},
        "fever_duration_percent": 100,
        "multiball_removal_charge": {"trigger": 194, "content": 211,
            "per_multiball_percent": 5, "target": "dark party",
            "requires_dark_resonance": True, "requires_fever": False,
            "trigger_limit": None, "cooldown_frames": 0,
            "event": "native MultiballRemove; temporary inactive transition does not count"},
        "ball_hit_count": ball_hit_count.metadata(),
        "piercing_extension": {"strategy": "dark_resonance", "target": "party",
                               "leader_rows": 0, "location": "ability2",
                               "requires_fever": False, "trigger": 0, "content": 190,
                               "ability2_percent": _percent(PIERCING_EXTENSION_STRENGTH)},
    }
