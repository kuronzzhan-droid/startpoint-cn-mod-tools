"""风巨蜥的能力伤害与合击位回槽限制；只转换传入的自有行/DSL。"""
from copy import deepcopy

from wf_battle_rules import make_row, gauge_mask, segment_override, TARGETS

CID = '149998'
CODE = 'land_dragon_wind_playable'
BLOCK_TEXT = '作为合击角色编成时，全队无法因技能或能力效果增加技能槽（战斗开始时除外）'
ABILITY_TOTAL_EFFECT = 'battle/common/layer1/total_ability_damage_effect'


def main_only(rows):
    """原生可合击开关负责主位限制；移除重复/互斥的槽位前提。

    2026-09-25 曾用于能力 3、6；2026-09-27 第二批起只有 :data:`MAIN_ONLY_KEYS`（能力 3）仍是主位限制，
    能力 6 已由 :func:`open_slot` 解除（作者 09-27），不要再对能力 6 调用本函数。"""
    result = deepcopy(rows)
    for row in result:
        if len(row) != 126:
            raise ValueError('unexpected ability row width')
        row[1] = 'false'
        for col in (6, 13, 20):
            if row[col] in ('202', '203'):  # OwnerIsMain / OwnerIsUnison
                if any(row[col + 1:col + 7]):
                    raise ValueError('unexpected slot precondition arguments')
                row[col] = '0'
    return result


def _preload_ability_total(result):
    # ActionDslAssetResolver visits both IfThisCharacterIsBoss branches while
    # loading. MemberImpl.isBoss() is false, so this declaration never plays or
    # creates an effect in battle. It adds the native timeline AND view assets
    # absent from the default battle preload (only skill/PF totals are common).
    if result[11][0] != 'Block':
        raise ValueError('expected root Block')
    marker = 'wf/preload/ability_total'
    show = ['ShowEffect', marker, ['SpecifyEffectDirectly', ABILITY_TOTAL_EFFECT],
            0, ['ForesideOfCharacter'], ['SpecifyEffectLifetimeDirectly', 1],
            ['AB'], 0, 0, 0, False, False, ['None']]
    declaration = ['Command', ['IfThisCharacterIsBoss', -18,
                              ['Command', show], ['Block', []]]]
    existing = [x for x in nodes(result, 'ShowEffect') if x[1] == marker]
    if existing:
        if existing != [show] or result[11][1].count(declaration) != 1:
            raise ValueError('invalid ability damage preload declaration')
    else:
        result[11][1].insert(0, declaration)


def bonus_rows(rows, *, leader=False):
    """不改变倍率、持续时间、触发条件或充能速度等其它内容。"""
    result = deepcopy(rows)
    kind, instant, during = (3, 45, 107) if leader else (5, 47, 109)
    maps = ({'34': '388', '1': '486', '694': '695'},
            {'2': '154', '411': '412'})
    for row in result:
        if len(row) != (124 if leader else 126):
            raise ValueError('unexpected ability row width')
        col, mapping = (during, maps[1]) if row[kind] == '1' else (instant, maps[0])
        row[col] = mapping.get(row[col], row[col])
    return result


def add_unison_block(rows, donor, *, target='party'):
    result = deepcopy(rows)
    existing = [r for r in result if r[5] == '1' and r[109] == '423']
    if existing:
        if len(existing) != 1 or (existing[0][6], existing[0][110], existing[0][111], existing[0][118]) != ('203', str(TARGETS[target]), '(None)', '12'):
            raise ValueError('existing gauge rule differs')
        return result
    row = make_row(donor, result[0][0], 423, gauge_mask(['skill', 'ability']), target=target)
    row[:5] = result[0][:5]
    row[1] = 'true'
    row[6] = '203'  # OwnerIsUnison: evaluate the ability owner, not fused main.
    result.append(row)
    return result


def nodes(tree, name):
    if isinstance(tree, list):
        if tree and tree[0] == name:
            yield tree
        for child in tree:
            yield from nodes(child, name)


def ability_skill(tree):
    """真实来源转换覆盖普通/Fever随机分支，CreateNormalAttack[5]平加伤害不动。"""
    result = deepcopy(tree)
    if len(result) != 12 or result[0] != 'ActionDsl':
        raise ValueError('expected native ActionDsl')
    if not list(nodes(result, 'CreateNormalAttack')):
        raise ValueError('active skill contains no attacks')
    result[10] = segment_override('ability')
    for area in nodes(result, 'CreateHitArea'):
        if list(nodes(area[23], 'CreateNormalAttack')):
            area[24] = segment_override('ability')
    for condition in nodes(result, 'ACSkillDamage'):
        condition[0] = 'ACAbilityDamage'
    _preload_ability_total(result)
    return result


def remove_fox_direct_combo(rows):
    """删除指定Fever直击+10连击，保留其它Fever/弹射加连击。"""
    result = deepcopy(rows)
    matches = [r for r in result if r[5] == '0' and r[6] == '12'
               and r[27] == '20' and r[47] == '226'
               and r[30:32] == ['100000', '100000']
               and r[51:53] == ['1000000', '1000000']]
    if len(matches) > 1:
        raise ValueError('ambiguous fox direct-combo rows')
    return [r for r in result if r not in matches]


# ---------------------------------------------------------------- 2026-09-27 第二批（作者请求 (1)）
#
# 作者原话：「风恐龙能力1的boss负面标记也去掉,去掉风恐龙的能力1和2,4,5,6的主位限制,能力3的自身发动技能
# fever+3固定值改为+30%,CT不变,能力和队长技全部添加风属性共鸣条件,加成也变成风属性全队攻击力和能力加成」。
# 下列纯函数只转换传入的行（先 deepcopy），对自身输出重跑是空操作（不会回退本批改动）。
# 逐格改前/改后与 fail-closed 基线在 ``wf_balance_20260927b_winddino.py``，测试断言两者输出一致。

WIND = 'Green'
#: 风属性共鸣前置：kind 2（Member）+ 阈值 600000/600000（编成 6 人）+ 组 Green（官方数百行同形）。
RESONANCE = ('2', '600000', '600000', WIND)
RESONANCE_TEXT = '风属性共鸣时，'
ABILITY_PRE_SLOTS = (6, 13, 20)       # 前置 1-3 kind 列；槽内 +3/+4 阈值、+5 组
LEADER_PRE_SLOTS = (4, 11, 18)        # 队长表 = 能力列号 − 2
#: 全面限制（1.4.679–682 施工，44 只 boss 能力 1 各 7 行）的行 string_id；本角色 09-27 起整段删除。
BOSS_LIMIT_STRING_ID = 'cnmod_boss_limit'
BOSS_LIMIT_KEY = CID + '1'
#: 09-27 起唯一保留主位限制（整键 c1=false、无 202）的能力键。
MAIN_ONLY_KEYS = (CID + '3',)
#: 目标自身的攻击力/能力伤害加成 → 全队(风)：瞬发 32 攻击力 / 388 能力伤害；持续 0 攻击力 / 154 能力伤害 /
#: 412 独立乘区能力伤害。技能槽、充能、Fever 点、Fever 时间等不在此列。
PARTY_BONUS_INSTANT = frozenset({'32', '388'})
PARTY_BONUS_DURING = frozenset({'0', '154', '412'})
#: Fever 中自身施技追加 Fever 点（213）→ Fever 槽 +30%（724 AddFeverPointRatio，×100000，30000 = 上限 30%）。
FEVER_RATIO_KIND = '724'
FEVER_RATIO_VALUE = '30000'
A2_PANEL_KEY = f'desc_override_{CODE}_2'
A2_PANEL_LINES = (
    RESONANCE_TEXT + '非Fever状态下，每达成10连击，Fever槽+150；每达成15连击，Fever槽+300。',
    RESONANCE_TEXT + '每达成25连击，自身技能槽+5%。',
    BLOCK_TEXT + '。',
)


def _pre_kinds(row, slots=ABILITY_PRE_SLOTS):
    return tuple(row[c] for c in slots)


def drop_boss_limit(rows):
    """删除全面限制 7 行（常驻 4 + Revival 3，c0 = cnmod_boss_limit）；其余行逐字保留。"""
    return [deepcopy(r) for r in rows if r[0] != BOSS_LIMIT_STRING_ID]


def open_slot(rows):
    """解除主位限制：整键 c1=true，前置 202（OwnerIsMain）→ 0；203（合击位锁槽）不动。"""
    result = deepcopy(rows)
    for row in result:
        if len(row) != 126:
            raise ValueError('unexpected ability row width')
        row[1] = 'true'
        for col in ABILITY_PRE_SLOTS:
            if row[col] == '202':
                if any(row[col + 1:col + 7]):
                    raise ValueError('unexpected slot precondition arguments')
                row[col] = '0'
    return result


def is_unison_lock(row):
    """能力 2 末行：仅合击位（203）持续 423 全队禁回槽。属于限制，加共鸣会让非风队绕开。"""
    return row[5] == '1' and row[109] == '423' and '203' in _pre_kinds(row)


def add_wind_resonance(rows, *, leader=False, skip=None):
    """每行第一个空闲前置槽写入风共鸣；已带风共鸣的行不动；``skip(row)`` 为真的行不加。"""
    width, slots = (124, LEADER_PRE_SLOTS) if leader else (126, ABILITY_PRE_SLOTS)
    result = deepcopy(rows)
    for row in result:
        if len(row) != width:
            raise ValueError('unexpected row width')
        if skip is not None and skip(row):
            continue
        if any(row[c] == RESONANCE[0] and (row[c + 3], row[c + 4], row[c + 5]) == RESONANCE[1:]
               for c in slots):
            continue
        free = next((c for c in slots if row[c] == '0' and not any(row[c + 1:c + 7])), None)
        if free is None:
            raise ValueError(f'no free precondition slot for wind resonance: {row[0]}')
        row[free] = RESONANCE[0]
        row[free + 3], row[free + 4], row[free + 5] = RESONANCE[1:]
    return result


def party_bonus(rows):
    """目标自身（0）的攻击力/能力伤害加成 → 赋予全队(风)（5 + Green）；数值不变。"""
    result = deepcopy(rows)
    for row in result:
        if len(row) != 126:
            raise ValueError('unexpected ability row width')
        if row[5] == '0':
            kind_col, kinds = 47, PARTY_BONUS_INSTANT
        elif row[5] == '1':
            kind_col, kinds = 109, PARTY_BONUS_DURING
        else:
            continue
        if row[kind_col] in kinds and row[kind_col + 1] == '0':
            if row[kind_col + 2]:
                raise ValueError('self bonus row already carries a target group')
            row[kind_col + 1], row[kind_col + 2] = '5', WIND
    return result


def fever_ratio(rows):
    """Fever 中（前置 12）自身施技（触发 23）追加 Fever 点 213 → Fever 槽 724 +30%；触发、CT、前置不变。"""
    result = deepcopy(rows)
    for row in result:
        if len(row) != 126:
            raise ValueError('unexpected ability row width')
        if row[5] == '0' and row[47] == '213' and row[27] == '23' and '12' in _pre_kinds(row):
            if row[49]:
                raise ValueError('unexpected Fever point target group')
            row[47], row[48] = FEVER_RATIO_KIND, ''      # 724 不读目标列（live 先例 c48 皆空）
            row[51] = row[52] = FEVER_RATIO_VALUE
    return result


def revision_20260927b(abilities, leader):
    """作者请求 (1) 的生成器：``abilities`` = live 六个能力键的行，``leader`` = 队长键的行。

    返回 ``(abilities_after, leader_after)``；能力 3 保留主位（:data:`MAIN_ONLY_KEYS`），能力 2 合击位锁槽行不加共鸣，
    队长 722 强化弹射覆盖行照官方 141201#1 同形加共鸣。"""
    keys = [f'{CID}{slot}' for slot in range(1, 7)]
    if sorted(abilities) != keys:
        raise ValueError(f'expected ability keys {keys}')
    result = {}
    for key in keys:
        rows = deepcopy(abilities[key])
        if key == BOSS_LIMIT_KEY:
            rows = drop_boss_limit(rows)
        if key not in MAIN_ONLY_KEYS:
            rows = open_slot(rows)
        rows = add_wind_resonance(rows, skip=is_unison_lock)
        result[key] = fever_ratio(party_bonus(rows))
    return result, add_wind_resonance(leader, leader=True)


def a2_panel():
    """能力 2 面板覆盖（``desc_override_land_dragon_wind_playable_2``）：不限主位，无 Ⓜ。"""
    return [['\n'.join(A2_PANEL_LINES)]]
