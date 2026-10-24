"""校园奈芙提姆的官方模板面板文字；纯文本工厂，不改战斗表行。"""
from copy import deepcopy
from wf_featured_main_ability import main_description

from wf_nephtim_fever_abilities import (CID, CODE, CHANGE_SKILL_DESCRIPTION,
                                        CHANGE_SKILL_STRING_ID, COMBO_STRENGTH,
                                        LEADER_PIERCING_GROWTH_STRENGTH,
                                        PIERCING_CAPPED_ATTACK_STRENGTH, PIERCING_CAPPED_DIRECT_STRENGTH,
                                        PIERCING_CAPPED_LIMIT, PIERCING_EXTENSION_STRENGTH,
                                        PIERCING_PERIOD_FRAMES,
                                        SKILL_GAUGE_MAXIMUM_STRENGTH, SKILL_NAME,
                                        SPAWN_DESCRIPTION, SPAWN_STRING_ID,
                                        SUMMON_PERIOD_FRAMES, _percent)
from wf_nephtim_fever_leader import FEVER_GAIN_GROWTH_STRENGTH, PF_STRING_ID
import wf_nephtim_fever_skill as skill
import wf_nephtim_multiball_direct as multiball_direct
import wf_nephtim_ball_hit_count as ball_hit_count

REQUIRED_CAPABILITY = "panel-description-override-v2"
FLAT_STRING_TABLE = "master/string/custom_ability_string.orderedmap"
PIERCING_POLICIES = ("dark_resonance",)
MAIN_ICON = " <icon id='main'>  "
# 面板数字一律从战斗侧真源取，避免文案与实际强度漂移。
COMBO_PERCENT = _percent(COMBO_STRENGTH)
# 作者 2026-09-27 第二批：贯穿成长能力3 为有上限弱化版，无上限部分在队长（文案只写到效果为止）。
PIERCING_ATTACK_PERCENT = _percent(PIERCING_CAPPED_ATTACK_STRENGTH)
PIERCING_DIRECT_PERCENT = _percent(PIERCING_CAPPED_DIRECT_STRENGTH)
LEADER_PIERCING_PERCENT = _percent(LEADER_PIERCING_GROWTH_STRENGTH)
FEVER_GAIN_PERCENT = _percent(FEVER_GAIN_GROWTH_STRENGTH)
_PIERCING_PERIOD = PIERCING_PERIOD_FRAMES / 60
PIERCING_PERIOD_SECONDS = int(_PIERCING_PERIOD) if _PIERCING_PERIOD.is_integer() else _PIERCING_PERIOD
LEADER_PIERCING_LINE = (
    f"暗属性共鸣时，Fever 模式中，处于贯穿效果的时间每累计{PIERCING_PERIOD_SECONDS}秒，"
    f"暗属性角色攻击力+{LEADER_PIERCING_PERCENT}%、直接攻击伤害+{LEADER_PIERCING_PERCENT}%。"
)
BALL_PERCENT = multiball_direct.per_ball_percent()
OVERFLOW_PERCENT = skill.overflow_attack_percent()
PIERCING_EXTENSION_PERCENT = _percent(PIERCING_EXTENSION_STRENGTH)
SKILL_GAUGE_MAXIMUM_PERCENT = _percent(SKILL_GAUGE_MAXIMUM_STRENGTH)
_PERIOD = SUMMON_PERIOD_FRAMES / 60
SUMMON_PERIOD_SECONDS = int(_PERIOD) if _PERIOD.is_integer() else _PERIOD
# I536「技能强化」条目：作者 2026-09-27 起随强化开关移入队长。
# 文案规则2：只写强化了什么，不写数字与时间。
# 2026-09-27 第三轮（wf_balance_20260927c_nephtim，作者「技能都强化效果只在队长技或者能力里面按照格式写」）：
# 同一条 I536 强化（队长 L#1，暗共鸣）面板只写一行 =「暗属性共鸣时，」+ 条目原文（与 change_skill 串同文）。
ENHANCEMENT_LINES = (
    f"暗属性共鸣时，{CHANGE_SKILL_DESCRIPTION}。",
)

# 2026-09-27 第三轮面板同条件合并（wf_balance_20260927c_nephtim）：数据条件逐格相同的行并成一行，
# 效果原措辞与数值保留、只省略重复对象名，合并行放在组首行位置。
# 队长 L#2/L#3（直击 400%、攻击 200%）与 L#5（Fever 时间 100%）同为暗共鸣常驻 ⇒ 原第4行与第6行并成一行；
LEADER_BASE_LINE = "暗属性共鸣时，暗属性角色攻击力+200%、直接攻击伤害+400%，Fever 时间+100%。"
# 能力2 #0（贯穿延时）与 #1（暗队直击 250%）同为暗共鸣常驻 ⇒ 第1行与第2行并成一行（见 panel_descriptions）。
A2_DIRECT_CLAUSE = "暗属性角色直接攻击伤害+250%"

_TEXTS = {
    "active": (
        "赋予参战者及协力球贯穿效果，提升队伍内角色及协力球的直接攻击伤害。\n"
        "Fever 模式中，使暗属性角色的直接攻击分为多次，并提高总伤害。"
    ),
    # 第2行是 I536「技能强化」条目（2026-09-27 起由队长承载；第三轮起两行并一行）。
    "leader": "\n".join((
        "暗属性共鸣时，强化弹射变为特殊型与辅助型组合。",
        *ENHANCEMENT_LINES,
        LEADER_BASE_LINE,
        f"暗属性共鸣时，每达成35连击，暗属性角色获得的 Fever 槽上升量+{FEVER_GAIN_PERCENT}%。",
        "暗属性共鸣时，每有1个协力球消失时，暗属性角色技能槽+5%。",
    )),
    # 召唤/溢出/清理仍在主位限制的能力1；强化开关已移入队长。
    # 2026-09-27 第三轮（wf_balance_20260927c_nephtim，主会话统一口径 6）：星夜茶会只能经技能旗号分支获得，
    # 旗号唯一来源是带暗共鸣的队长 536 行 ⇒ 视为获取带暗共鸣，依赖持有星夜茶会的召唤/溢出两行不再写「暗属性共鸣时，」。
    "a1": (
        "战斗开始时，自身技能槽+50%。\n"
        f"Fever 模式中，持有「星夜茶会」时，每经过{SUMMON_PERIOD_SECONDS}秒交替召唤1个光、暗属性协力球，各持续25秒且无法回复生命值，协力球最多同时存在9个；再次发动技能不会延长已有协力球的存在时间。\n"
        f"Fever 模式中，持有「星夜茶会」时，协力球已达9个时，该次召唤改为自身攻击力+{OVERFLOW_PERCENT}%，持续20秒，可叠加。\n"
        "Fever 结束或自身倒下时，「星夜茶会」解除。"
    ),
    # 首行「贯穿延时＋直击」由 panel_descriptions 按已确认策略拼成（2026-09-27 起在能力2；第三轮同条件合并为一行）。
    "a2": f"暗属性共鸣时，Fever 模式中，暗属性角色技能槽上限+{SKILL_GAUGE_MAXIMUM_PERCENT}%。",
    # 文案规则1：没有上限的成长写到效果为止，后面什么都不跟（不写「无上限」）；有上限写「（最多N次）」。
    "a3": "\n".join(MAIN_ICON + line for line in (
        f"暗属性共鸣时，Fever 模式中，当前每有1连击，暗属性角色直接攻击造成的伤害+{COMBO_PERCENT}%（独立乘区）、攻击力+{COMBO_PERCENT}%。",
        f"暗属性共鸣时，Fever 模式中，处于贯穿效果的时间每累计{PIERCING_PERIOD_SECONDS}秒，暗属性角色攻击力+{PIERCING_ATTACK_PERCENT}%、直接攻击伤害+{PIERCING_DIRECT_PERCENT}%（最多{PIERCING_CAPPED_LIMIT}次）。",
        "暗属性共鸣时，暗属性角色合计每直接攻击45次，Fever 槽+15%。",
        f"暗属性共鸣时，每有1个协力球存在时，全队及协力球对敌人造成的直接攻击伤害+{BALL_PERCENT}%（独立乘区）。",
    )),
    "a4": "暗属性共鸣时，Fever 模式中，暗属性角色及协力球直接攻击造成的伤害+50%（独立乘区）。",
    "a5": (
        "非 Fever 模式中，每经过10秒，赋予全队贯穿效果，持续3秒。\n"
        "Fever 模式中，每经过5秒，赋予全队贯穿效果，持续3秒。"
    ),
    "a6": "暗属性共鸣时，暗属性角色直接攻击伤害+100%。",
}


def _piercing_clause(policy):
    if policy == "dark_resonance":
        return f"全队贯穿效果时间+{PIERCING_EXTENSION_PERCENT}%"
    raise ValueError(f"piercing_extension must be one of {PIERCING_POLICIES}: {policy!r}")


def panel_descriptions(*, piercing_extension="dark_resonance"):
    """返回主动、队长和六能力；贯穿延时使用已确认的常驻暗共鸣条件（2026-09-27 起在能力2）。"""
    texts = deepcopy(_TEXTS)
    texts["a1"] = main_description(texts["a1"])
    # 能力2 第1行：贯穿延时与暗队直击同条件（暗共鸣常驻）⇒ 一行写完（第三轮同条件合并）。
    texts["a2"] = (f"暗属性共鸣时，{_piercing_clause(piercing_extension)}，{A2_DIRECT_CLAUSE}。\n"
                   + texts["a2"])
    # 行序与队长表一致：9/25 的 ball_hit_count 行之后是 2026-09-27 第二批搬来的贯穿成长（第9、10行合一句）。
    texts["leader"] += "\n" + ball_hit_count.DESCRIPTION + "\n" + LEADER_PIERCING_LINE
    return texts


def active_description():
    """同步到 action_skill / character_text 的主动说明，不含具体数值。"""
    return _TEXTS["active"]


def panel_rows(ability_rows, leader_rows, *, piercing_extension="dark_resonance"):
    """检查各组实际首行 c0，返回七条 v2 覆盖；不改变原行或觉醒字段。"""
    texts = panel_descriptions(piercing_extension=piercing_extension)
    groups = {"leader": leader_rows}
    groups.update({f"a{slot}": ability_rows.get(CID + str(slot), [])
                   for slot in range(1, 7)})
    result = {}
    for slot, rows in groups.items():
        expected = CODE if slot == "leader" else CODE + "_" + slot[1:]
        if not rows or not rows[0] or rows[0][0] != expected:
            raise ValueError(f"{CID} {slot}: first-row string_id must be {expected}")
        result["desc_override_" + expected] = [[texts[slot]]]
    return result


def native_flat_string_rows():
    """保留实际 I536/I629/I722 字符串依赖，比较面板也使用可读说明。"""
    return {
        CHANGE_SKILL_STRING_ID: [[CHANGE_SKILL_DESCRIPTION]],
        SPAWN_STRING_ID: [[SPAWN_DESCRIPTION]],
        PF_STRING_ID: [["强化弹射变为特殊型与辅助型组合"]],
    }


def metadata(*, piercing_extension="dark_resonance"):
    _piercing_clause(piercing_extension)
    return {
        "character_id": CID,
        "required_client_capabilities": [REQUIRED_CAPABILITY],
        "leader_piercing_extension": piercing_extension,
        "piercing_extension_panel": "a2",
        "override_key_source": "first ability/leader row c0 (string_id)",
        "combat_rows_modified": False,
        "numeric_text": "fixed authored values at all ability levels",
        "coverage": "character ability and leader panels; comparison and disabled-reason text remain native",
    }
