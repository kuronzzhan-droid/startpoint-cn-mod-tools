"""通用战斗补丁的配置编码；纯函数，不登记设备能力、不发布数据。"""
from __future__ import annotations

from wf_client_patch_scope import patch_parser_supported

GAUGE_CAP = 'gauge-gain-rules-v1'
DAMAGE_CAP = 'damage-type-rules-v1'
GAINS = {'opening': 1, 'movement': 2, 'skill': 4, 'ability': 8,
         'combo_ability': 16, 'skill_triggered_ability': 32, 'other_action': 64}
ORIGINS = {'character': 256, 'leader': 512, 'weapon': 1024,
           'soul': 2048, 'ex': 4096}
OWNERS = {'self': 16384, 'other': 32768}
TRIGGERS = {'self': 65536, 'other': 131072}
SOURCES = {'any': 0, 'skill': 1, 'ability': 2, 'power_flip': 3, 'direct': 4}
DESTINATIONS = {'skill': 1, 'ability': 2, 'direct': 4, 'pf1': 31, 'pf2': 32, 'pf3': 33}
TARGETS = {'self': 0, 'others': 1, 'leader': 2, 'second': 3, 'third': 4, 'party': 5}
GROUP_MASKS = (127, 7936, 49152, 196608)
KNOWN_MASK = sum(GROUP_MASKS)


def _flags(values, mapping):
    result = 0
    for value in values:
        if value not in mapping:
            raise ValueError(f'unknown selection: {value}')
        result |= mapping[value]
    return result


def gauge_mask(gains, *, origins=(), owners=(), triggers=()):
    """同组任选其一，组间同时满足；关系均相对于实际收到加槽的角色。"""
    mask = (_flags(gains, GAINS) | _flags(origins, ORIGINS)
            | _flags(owners, OWNERS) | _flags(triggers, TRIGGERS))
    validate_code(423, mask)
    return mask


def damage_rule(source, destination):
    if source not in SOURCES or destination not in DESTINATIONS:
        raise ValueError('unknown source/destination damage type')
    return SOURCES[source]*100 + DESTINATIONS[destination]


def segment_override(destination):
    if destination not in DESTINATIONS:
        raise ValueError('unknown destination damage type')
    return 100 + DESTINATIONS[destination]


#: 强化弹射段覆盖 131-133（segment_override pf1..pf3）的命中会驱动哪些瞬发触发。
#: 依据（静态）：damage.py 的 wfConvertNormalAttack 挂在 ImpactSourceContent.NormalAttack 构造入口，
#: 早于命中计数，把 buffTargetAs 131-133 改写成 createdByPowerFlipAction=true、powerFlipChargeLv=1..3；
#: EnemyImpl.as:5655-5664 随之计 OneOfEnemyBattle LvAny 与对应等级（瞬发触发 183 与 180/181/182，
#: InstantAbilityTriggerMasterValueTools.as:553-564），countUpPowerFlipHitLvHighAbilityTrigger(lv)
#: （EnemyImpl.as:4466-4480）计 battle Count 15..14+lv（瞬发触发 15/16/17 PowerFlipHitLv1/2/3High，
#: InstantAbilityTriggerMasterValueTools.as:65-72）。用这些触发去触发打出这类命中的 629 树 = 自我连锁。
PF_SEGMENT_HIT_TRIGGERS = {
    100 + DESTINATIONS['pf1']: frozenset({'183', '180', '15'}),
    100 + DESTINATIONS['pf2']: frozenset({'183', '181', '15', '16'}),
    100 + DESTINATIONS['pf3']: frozenset({'183', '182', '15', '16', '17'}),
}


def dsl_segment_overrides(tree):
    """DSL 里显式写的伤害段覆盖（buffTargetAs ≥100）：根头 tree[10] 与每个 CreateHitArea 的
    buffTargetAs（命令名之后第 23 个参数）。0 = 继承外层，不算覆盖。"""
    found = []
    if isinstance(tree, list) and len(tree) > 10 and type(tree[10]) is int and tree[10] >= 100:
        found.append(tree[10])
    stack = [tree]
    while stack:
        node = stack.pop()
        if not isinstance(node, list):
            continue
        if (len(node) > 1 and node[0] == 'Command' and isinstance(node[1], list)
                and node[1] and node[1][0] == 'CreateHitArea' and len(node[1]) > 24):
            value = node[1][24]
            if type(value) is int and value >= 100:
                found.append(value)
        stack.extend(reversed(node))
    return found


def dsl_capabilities(tree):
    """段覆盖需要 damage-type-rules-v1；未装补丁时 Environment.getBuffTargetAs 的 default 分支
    返回空值（读成 0），按技能伤害结算，不崩，但伤害归属不对（语义级）。"""
    return [DAMAGE_CAP] if dsl_segment_overrides(tree) else []


def pf_hit_triggers_driven_by(tree):
    """这棵 DSL 的命中会驱动的「强化弹射命中」类瞬发触发（见 PF_SEGMENT_HIT_TRIGGERS）。"""
    out = set()
    for value in dsl_segment_overrides(tree):
        out |= PF_SEGMENT_HIT_TRIGGERS.get(value, frozenset())
    return frozenset(out)


def validate_code(content, code):
    if type(code) is not int or code < 0:
        raise ValueError('规则必须为非负整数，不能使用 Decimal 倍率')
    if content == 423:
        if not code & GROUP_MASKS[0] or code & ~KNOWN_MASK:
            raise ValueError('加槽限制必须选择至少一种加槽类型，且不能含未知标记位')
        if code & 2 and code & (KNOWN_MASK ^ 127):
            raise ValueError('移动充能没有武器或施技者来源；请拆成独立规则')
    elif content == 424:
        if code//100 not in SOURCES.values() or code % 100 not in DESTINATIONS.values():
            raise ValueError('伤害映射必须是 source*100+destination 的单次转换')
    else:
        raise ValueError('unsupported battle rule content')


def row_problems(table, row, blocks):
    """规则码列 = during_content 块起点 +9：ability/EA c118、ability_soul c115。"""
    col = blocks.get('during_content')
    if col is None or len(row) <= col or row[blocks['precondition1']-1] != '1':
        return []
    # 表范围以解析器补丁为准（423 含装备两表，424 仅 ability）；越界由 patch_parser_scope_problems 报 C7050
    if row[col] not in ('423', '424') or not patch_parser_supported(table, 'during_content', row[col]):
        return []
    try:
        text = row[col+9]
        if not text.isascii() or not text.isdigit():
            raise ValueError('规则编码必须为十进制整数')
        validate_code(int(row[col]), int(text))
    except (ValueError, IndexError) as exc:
        return [f'c{col+9} 战斗规则编码错误：{exc}']
    return []


def make_row(donor, string_id, content, code, *, target='self', groups='(None)'):
    """复用持续能力母行，清除 HP 门槛；只在 ability 表写入新词条。"""
    validate_code(content, code)
    if len(donor) != 126 or donor[5] != '1' or donor[85] != '(None)' or donor[97] != '0':
        raise ValueError('需要 126 列、无累积触发、始终生效的 ability 母行')
    if any(donor[i] != '0' for i in (6, 13, 20)) or target not in TARGETS:
        raise ValueError('母行不能带前置条件；目标必须为受支持的成员范围')
    # Native parseAt111 maps an empty string to Some([]), which matches nobody.
    # Only the literal (None) means an unrestricted party/others target.
    groups = groups or '(None)'
    row = list(donor)
    # During kind 0 is HpHigh, not Always: discard the donor's HP threshold.
    row[98], row[99], row[100], row[101] = '0', '', '0', '0'
    row[113], row[114] = '0', '0'
    row[0], row[109], row[110], row[111], row[118] = (
        string_id, str(content), str(TARGETS[target]), groups, str(code))
    row[108] = 'false'
    return row
