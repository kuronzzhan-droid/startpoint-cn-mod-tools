"""校园奈芙提姆六能力：纯原生表行工厂，不读写角色包或 live。"""
from copy import deepcopy
import wf_nephtim_multiball_direct as multiball_direct
import wf_nephtim_multiball_fever as multiball_fever

CID = "169989"
CODE = "ruin_girl_campus"
SCALE = 100_000
SUMMON_UNIQUE_ID = 16998901
CHANGE_SKILL_STRING_ID = "change_skill_ruin_girl_campus_fever"
SKILL_NAME = "午后星轨·甜蜜续杯"
SPAWN_STRING_ID = CODE + "_fever_spawn"
SPAWN_ACTION_PATH = "battle/action/skill/action/ability_skill/" + CODE + "$" + SPAWN_STRING_ID
# 作者 2026-09-17：能力1/能力3 提供的攻击力、直击伤害与独立乘区一律减半，机制不动。
# 千分之一为单位的强度列：2_500 = 2.5%，10_000 = 10%。
COMBO_STRENGTH = 2_500          # 每 1 连击的独立乘区直击与攻击力（原 5_000）
# 贯穿每累计 2 秒（T235，暗共鸣 + Fever）的攻击力/直击伤害成长：2026-09-17 减半 20% → 10%；
# 作者 2026-09-27 第二批（无上限成长搬队长）：能力3 两行原位改成有上限的弱化版（各限 10 次），
# 无上限部分搬进队长并按 3 分钟实际触发次数（≥30 次）放缓 1/10：10% → 1%。
# 作者 2026-09-27 第三轮（c，成长复核：「1/10 砍太多了」→「可以砍到2/3」「数值尽量取5的倍数」）：
# 队长两行回调到 2/3 档，10×2/3=6.67 向上取 7%（wf_balance_20260927c_nephtim）；能力3 封顶版不动。
PIERCING_PERIOD_FRAMES = 120
PIERCING_CAPPED_ATTACK_STRENGTH = 5_000    # 能力3：暗队攻击力 +5%/次（最多 10 次 = +50%）
PIERCING_CAPPED_DIRECT_STRENGTH = 10_000   # 能力3：暗队直击伤害 +10%/次（最多 10 次 = +100%）
PIERCING_CAPPED_LIMIT = 10                 # 能力3 两行 c34 trigger_limit（原 (None)）
LEADER_PIERCING_GROWTH_STRENGTH = 7_000    # 队长：暗队攻击力/直击伤害 各 +7%/次（无上限；第二批 1%）
# 作者 2026-09-27：持有「星夜茶会」时的召唤间隔 1.5 秒 → 2 秒（T232 threshold2，单位帧）。
SUMMON_PERIOD_FRAMES = 120
# 作者 2026-09-27：队长的 I190 贯穿延时并入能力2，合计 +40%（原队长 20% + 能力2 20%，按行相加）。
PIERCING_EXTENSION_STRENGTH = 40_000
# 作者 2026-09-27：「Fever 中暗属性角色技能槽上限+10%」由队长移入能力2，不加主位限制。
SKILL_GAUGE_MAXIMUM_STRENGTH = 10_000
# I629 说明的唯一真源：面板模块也引用这一份，避免两处文案漂移。
SPAWN_DESCRIPTION = (
    "交替召唤1个光、暗属性协力球，持续25秒且无法回复生命值，协力球最多同时存在9个；"
    "已达9个时改为自身攻击力+25%，持续20秒，可叠加；"
    "再次发动技能不会延长已有协力球的存在时间"
)
# I536 说明的唯一真源。文案规则2：「技能强化」条目只写强化了什么，不写数字与时间。
CHANGE_SKILL_DESCRIPTION = (
    "强化『" + SKILL_NAME + "』：额外赋予暗属性角色及协力球攻击力提升效果；"
    "Fever 模式中发动时，自身获得或刷新「星夜茶会」，并赋予暗属性角色及协力球护盾"
)


def _percent(strength):
    """强度列（千分之一）转面板口径的百分比，整数就给整数。"""
    value = strength / 1000
    return int(value) if float(value).is_integer() else value


def _set(row, values):
    for column, value in values.items():
        row[column] = str(value)
    return row


def _pre(row, kind=None, *, offset=6):
    row[offset:offset + 7] = ["0", "", "", "", "", "", ""]
    if kind == "dark":
        row[offset] = "2"
        row[offset + 3:offset + 6] = ["600000", "600000", "Black"]
    elif kind in ("fever", "not_fever"):
        row[offset] = "12" if kind == "fever" else "186"
    elif kind is not None:
        raise ValueError(f"unsupported precondition {kind}")


def _instant(source, content, strength=None, *, pre=None, fever=None,
             target=None, trigger=0, threshold=1, threshold2=None,
             puller=None, group=None, limit=None):
    row = deepcopy(source["1110211"][0])
    if len(row) != 126:
        raise ValueError("official ability rows must have 126 columns")
    row[:6] = [CODE, "true", "attack_black", "0", "", "0"]
    row[27:39] = [""] * 12
    row[47:85] = [""] * 38
    _pre(row, pre)
    _pre(row, fever, offset=13)
    _pre(row, offset=20)
    _set(row, {27: trigger, 47: content})
    if trigger:
        _set(row, {30: threshold * SCALE, 31: threshold * SCALE,
                   34: "(None)" if limit is None else limit, 35: 0})
    if threshold2 is not None:
        _set(row, {32: threshold2 * SCALE, 33: threshold2 * SCALE})
    if puller is not None:
        row[28] = str(puller)
    if group is not None:
        row[29] = group
    if target is not None:
        row[48] = str(target)
        if target == 5:
            row[49] = "Black"
    if strength is not None:
        row[51:53] = [str(strength)] * 2
    return row


def _during(source, content, strength, *, target=5, combo=False):
    # Official original Nephtim A3 is the native 126-column Fever during donor.
    row = deepcopy(source["1510013"][0])
    if len(row) != 126:
        raise ValueError("official ability rows must have 126 columns")
    row[:6] = [CODE, "true", "attack_black", "0", "", "1"]
    row[97:109] = [""] * 12
    row[109:123] = [""] * 14
    _pre(row, "dark")
    _pre(row, "fever", offset=13)
    _pre(row, offset=20)
    _set(row, {97: 2 if combo else 4, 108: "false", 109: content,
               110: target, 113: strength, 114: strength})
    if target == 5:
        row[111] = "Black"
    if combo:
        _set(row, {100: SCALE, 101: SCALE, 102: "(None)"})
    return row


def _piercing(source, *, trigger, frames, fever):
    row = _instant(source, 26, fever=fever, trigger=trigger, threshold=frames)
    return _set(row, {57: 180 * SCALE, 58: 180 * SCALE,
                     59: SCALE, 60: SCALE, 62: "(None)", 63: "(None)",
                     64: "(None)", 65: "(None)", 67: 0, 72: "false"})


def _multiball_direct_rows(source):
    # One native surviving count feeds both party and balls. P13/D208 use a
    # different inactive-ball filter, so neither belongs to this added effect.
    # 作者 2026-09-27 多人卡顿修复：T77 周期 1 帧 → multiball_direct.UPDATE_PERIOD_FRAMES（10 帧）。
    pulse = _instant(source, 629, pre="dark", trigger=77,
                     threshold=multiball_direct.UPDATE_PERIOD_FRAMES)
    _set(pulse, {70: multiball_direct.STRING_ID, 71: multiball_direct.ACTION_PATH})
    return [pulse]


def piercing_growth_rows(source, attack_strength, direct_strength, *, limit=None):
    """贯穿每累计 2 秒（T235，暗共鸣 + Fever）→ 暗队攻击力（I32）、直击伤害（I33）两行（能力表126列形）。

    能力3 用带上限的弱化版（limit=PIERCING_CAPPED_LIMIT）；队长用同形无上限行
    （队长模块按 [CODE,'0',''] + row[5:] 转换，列号 −2；队长 T235 先例 live 169999#7-9，前置12 先例 live 149989#4-6）。"""
    return [_instant(source, content, strength, pre="dark", fever="fever", target=5,
                     trigger=235, threshold=1, threshold2=PIERCING_PERIOD_FRAMES, limit=limit)
            for content, strength in ((32, attack_strength), (33, direct_strength))]


def enhance_row(source):
    """I536 技能强化开关（能力表126列形）。

    作者 2026-09-27 起由队长承载（队长模块按列−2 搬迁，与官方队长 121189#3 同形）；
    召唤、溢出与清理三行仍留在主位限制的能力1。"""
    enhance = _instant(source, 536, pre="dark")
    enhance[70] = CHANGE_SKILL_STRING_ID
    return enhance


def ability_rows(source, *, summon_unique_id=SUMMON_UNIQUE_ID,
                 spawn_action_path=SPAWN_ACTION_PATH):
    """返回1699891..6；主动技能里的强化分支/召唤状态由DSL模块装配。"""
    opening_charge = _instant(source, 211, 50_000, target=0)
    # ConditionKeepFrame counts only frames actually holding at least one UID.
    summon = _instant(source, 629, pre="dark", fever="fever", trigger=232,
                      threshold=1, threshold2=SUMMON_PERIOD_FRAMES, puller=0)
    _set(summon, {37: summon_unique_id, 70: SPAWN_STRING_ID, 71: spawn_action_path})
    clear = _instant(source, 528, trigger=184, target=0)
    clear[68] = str(summon_unique_id)
    # Zone transitions can leave Fever without T184. Check the existing state
    # at native update boundaries; do not dispatch deletion when it is absent.
    reconcile = _instant(source, 528, fever="not_fever", trigger=77, target=0)
    _set(reconcile, {6: 187, 7: 0, 12: summon_unique_id, 68: summon_unique_id})

    # Piercing is a party state: I190 is natively Party(None), not a character target.
    # The Fever-only dark skill-gauge maximum (during 124) is a native member effect.
    a2 = [_instant(source, 190, PIERCING_EXTENSION_STRENGTH, pre="dark"),
          _instant(source, 33, 250_000, pre="dark", target=5),
          _during(source, 124, SKILL_GAUGE_MAXIMUM_STRENGTH, target=5)]
    combo = _during(source, 410, COMBO_STRENGTH, combo=True)
    combo_attack = _during(source, 0, COMBO_STRENGTH, combo=True)
    # 作者 2026-09-27 第二批：有上限的弱化版（攻击力 +5%、直击 +10%，各最多 10 次）；无上限部分在队长。
    piercing_attack, piercing_direct = piercing_growth_rows(
        source, PIERCING_CAPPED_ATTACK_STRENGTH, PIERCING_CAPPED_DIRECT_STRENGTH,
        limit=PIERCING_CAPPED_LIMIT)
    # Only AbilityValues parses I724 on the installed ratio-capable client.
    charge = _instant(source, 724, 15_000, pre="dark", trigger=20,
                      threshold=45, puller=7, group="Black")
    a3 = [combo, combo_attack, piercing_attack, piercing_direct, charge, *_multiball_direct_rows(source)]
    a4 = [_during(source, 410, 50_000, target=5),
          _during(source, 410, 50_000, target=8)]
    a5 = [_piercing(source, trigger=77, frames=600, fever="not_fever"),
          _piercing(source, trigger=248, frames=300, fever="fever")]
    a6 = [_instant(source, 33, 100_000, pre="dark", target=5)]
    result = {}
    for number, rows in enumerate(([opening_charge, summon, clear, reconcile], a2, a3, a4, a5, a6), 1):
        for row in rows:
            row[0] = f"{CODE}_{number}"
            row[1] = "false" if number in (1, 3) else "true"
        result[f"{CID}{number}"] = rows
    result[CID + "4"] = multiball_fever.replace_ball_row(result[CID + "4"])
    return result


def flat_string_rows():
    return {
        **multiball_direct.flat_string_rows(),
        **multiball_fever.flat_string_rows(),
        CHANGE_SKILL_STRING_ID: [[CHANGE_SKILL_DESCRIPTION]],
        SPAWN_STRING_ID: [[SPAWN_DESCRIPTION]],
    }


def metadata():
    return {
        "character_id": CID,
        "required_client_capabilities": ["kyubi-fever-ratio-v1"],
        "main_only_slots": [1, 3],
        "current_multiball_direct_bonus": multiball_direct.metadata(),
        "fever_multiball_direct_bonus": multiball_fever.metadata(),
        "direct_attack_fever": {"ability_slot": 3, "requires_ability_unlock": True,
                                "requires_self_leader": False, "requires_dark_resonance": True,
                                "dark_hits": 45, "percent_of_maximum": 15,
                                "requires_fever": False},
        "opening_skill_charge": {
            "content": 211, "target": "self", "initial_charge_percent": 50,
            "trigger": 0, "requires_resonance": False, "gauge_maximum_increase_percent": 0,
        },
        "skill_enhancement": {
            "string_id": CHANGE_SKILL_STRING_ID, "summon_unique_id": SUMMON_UNIQUE_ID,
            "flag_location": "leader_ability (I536, official leader precedent 121189#3)",
            "summon_location": "ability1 (main-only; idles unless the leader flag granted the state)",
            "spawn_action_path": SPAWN_ACTION_PATH, "attack_buff_percent": 250,
            "duration_frames": 1200, "per_ball_duration_frames": 1500,
            "period_frames": SUMMON_PERIOD_FRAMES,
            "timer": "T232 holding-Unique frames; fractional period retained",
            "fever_end_removes_only_summon_state": True,
            "state_remove_if_encoffin": True,
            "zone_transition_cleanup": {
                "trigger": 77, "period_frames": 1, "requires_existing_self_state": True,
                "only_outside_fever": True, "native_timing": "next living owner update and impact phase",
            },
        },
        "piercing_extension": {
            "ability_slot": 2, "content": 190, "increase_percent": _percent(PIERCING_EXTENSION_STRENGTH),
            "target": "party", "requires_dark_resonance": True, "requires_self_leader": False,
            "main_only": False, "note": "native party state; leader share merged into one row 2026-09-27",
        },
        "skill_gauge_maximum": {
            "ability_slot": 2, "content": 124, "during_trigger": 4,
            "increase_percent": _percent(SKILL_GAUGE_MAXIMUM_STRENGTH),
            "target": "dark party", "requires_dark_resonance": True, "requires_fever": True,
            "requires_self_leader": False, "main_only": False, "moved_from": "leader 2026-09-27",
        },
        "combo_bonus": {
            "source": "current combo", "per_combo_percent": _percent(COMBO_STRENGTH),
            "attack_percent_per_combo": _percent(COMBO_STRENGTH),
            "attack_uses_ordinary_additive_term": True,
            "target": "dark party", "independent_direct_damage_term": True,
            "trigger_limit": None, "falls_when_combo_falls": True,
        },
        "piercing_growth": {
            "period_frames": PIERCING_PERIOD_FRAMES,
            "attack_percent": _percent(PIERCING_CAPPED_ATTACK_STRENGTH),
            "direct_damage_percent": _percent(PIERCING_CAPPED_DIRECT_STRENGTH),
            "trigger_limit": PIERCING_CAPPED_LIMIT, "persists_after_fever": True,
            "uncapped_share": {"location": "leader", "percent_each": _percent(LEADER_PIERCING_GROWTH_STRENGTH),
                               "trigger_limit": None, "since": "2026-09-27 batch 2",
                               "revised": "2026-09-27 batch c: 1% -> 7% (2/3 of the original 10%)"},
            "timer": "T235 piercing frames admitted only during dark resonance and Fever; fractional period retained",
        },
        "periodic_piercing": {
            "non_fever": "T77 global battle 600-frame boundaries, skipped during Fever",
            "fever": "T248 every 300 cumulative Fever frames; fractional period retained",
            "duration_frames": 180, "requires_resonance": False,
        },
    }
