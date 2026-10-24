"""校园希尔媞队长与特殊PF资产；仅生成数据，不写候选或live。"""
from __future__ import annotations

from copy import deepcopy
import zlib

import wf_dsl
from wf_campus_bianca_data import validate_row
from wf_celtie_fever_abilities import _stock_gain_bonus
from wf_celtie_fever_icons import gain_icon_bytes, stock_icon_bytes
from wf_celtie_fever_skill import ability_damage_reference
from wf_celtie_fever_stock import (
    ABILITY_STOCK_ACTION_PATH, GAIN_ICON, GAIN_NAME, GAIN_STRING_ID, GAIN_UID,
    LEADER_SPEND_ACTION_PATH, LEADER_SPEND_STRING_ID, SPEND_MARKERS,
    STOCK_ACTION_PATH, STOCK_ICON, STOCK_NAME,
    STOCK_STRING_ID, STOCK_UID, spend_action_tree, spend_unique_rows, stock_action_tree,
)

CID = "149989"
CODE = "wind_spgirl_campus"
PF_ID = CODE + "_fever"
PF_STRING_ID = PF_ID + "_powerflip"
PF_PROGRAM_PATHS = tuple(
    "battle/action/skill/action/power_flip/campus_celtie_fever/campus_celtie_fever_lv" + str(level)
    for level in (1, 2, 3))
PF_SOURCE_PATHS = tuple(
    "battle/action/power_flip/action/override/override_wind_spgirl_4anv$override_wind_spgirl_4anv_lv" + str(level)
    for level in (1, 2, 3))
PF_SOURCE_EFFECT = "wind_spgirl_4anv"
PF_EFFECT = "campus_celtie_fever"
#: 2026-09-27 第二批（口径 A2/A3/A5）：能力3「每层星风心得」原为无上限 25%/层，搬进队长并放缓
#: 到 1/10（口径 A2 按实际步数：每层一步，3 分钟 Fever 中风队施技约 13–20 次、每次 +3 层 ⇒
#: 约 40–60 层 ≥30）：风队能力伤害、攻击力各 2.5%/层，不设限（c100 (None)）。
#: 队长里没有同触发/同 kind 的行，按口径另起两行（第 7、8 行）；
#: 技能 DSL 心得倍率封顶 10 层后，超出部分的逐层成长也由这两行承担（视为已合并）。
#: 2026-09-27 第三轮（c，作者「砍到2/3」「数值尽量取5的倍数」，口径 D1）：原 25% 的 2/3 档
#: 取 20%（17.5% 不是 5 的倍数、15% 低于 2/3 下限），两行同值。
GAIN_GROWTH_STRENGTH = {154: 20_000, 0: 20_000}


def _set(row, values):
    for column, value in values.items():
        row[column] = str(value)
    return row


def _base(source, content, strength=None):
    row = deepcopy(source["1110211"][0])
    if len(row) != 126:
        raise ValueError("ability donor must have 126 columns")
    row[27:39] = [""] * 12
    row[47:85] = [""] * 38
    _set(row, {27: 0, 47: content})
    if strength is not None:
        _set(row, {51: strength, 52: strength})
    return [CODE, "0", ""] + row[5:]


def _resonance(row, fever=False):
    row[4:11] = ["2", "", "", "600000", "600000", "Green", ""]
    if fever:
        row[11:18] = ["12", "", "", "", "", "", ""]
    return row


def _trigger(row, trigger, *, wind=False):
    _set(row, {25: trigger, 28: 100000, 29: 100000, 32: "(None)", 33: 0})
    if wind:
        _set(row, {26: 7, 27: "Green"})
    return row


def gain_growth_row(ability_source, content):
    """能力3 心得行按口径 A3 转成队长行：``[CODE, '0', ''] + 能力行[5:]``（列号 −2），不设限。"""
    row = _stock_gain_bonus(ability_source, content, GAIN_GROWTH_STRENGTH[content], limit=None)
    return [CODE, "0", ""] + row[5:]


def leader_rows(ability_source, leader_source):
    """库存加2；主球发射时同步消费1，倍率固定1，因此连击始终+7。"""
    attack = _set(_base(ability_source, 32, 200000), {46: 5, 47: "Green"})
    damage = _set(_base(ability_source, 388, 400000), {46: 5, 47: "Green"})
    overrides = [r for r in leader_source["141201"] if r[45] == "722"]
    if len(overrides) != 1 or len(overrides[0]) != 124:
        raise ValueError("expected latest Celtie native I722 donor")
    special_pf = deepcopy(overrides[0])
    _set(special_pf, {0: CODE, 80: PF_ID, 81: "1,2,3", 82: PF_STRING_ID})
    _resonance(special_pf)
    pf_hit = _trigger(_resonance(_base(ability_source, 254, 1000000), True), 2)
    _set(pf_hit, {46: 0, 67: "(None)"})
    acquire = _trigger(_resonance(_base(ability_source, 629), True), 23, wind=True)
    _set(acquire, {68: STOCK_STRING_ID, 69: STOCK_ACTION_PATH})
    consume = _trigger(_resonance(_base(ability_source, 629), True), 26)
    _set(consume, {37: 2, 38: 0, 40: 100000, 41: 100000, 43: STOCK_UID})
    _set(consume, {68: LEADER_SPEND_STRING_ID, 69: LEADER_SPEND_ACTION_PATH})
    growth = [gain_growth_row(ability_source, content) for content in (154, 0)]
    result = [attack, damage, special_pf, pf_hit, acquire, consume, *growth]
    for row in result:
        validate_row(row, "leader_ability")
    return result


def unique_rows():
    # 本场库存含倒下期间保留；Fever门只控制取得/消费，不给状态自动弹射过期。
    result = {str(uid): [[string_id, name, icon,
        "99999999", "2147483647", "(None)", "(None)", "(None)", "(None)",
        "false", "true", "0", "0", "false", "(None)"]]
        for uid, string_id, name, icon in (
            (STOCK_UID, STOCK_STRING_ID, STOCK_NAME, STOCK_ICON),
            (GAIN_UID, GAIN_STRING_ID, GAIN_NAME, GAIN_ICON))}
    result.update(spend_unique_rows())
    return result


def flat_string_rows():
    return {
        STOCK_STRING_ID: [["获得2次「星风快门」（次数可累积；每次弹射消耗1次并增加7连击；非共鸣或非Fever期间保留剩余次数）"]],
        LEADER_SPEND_STRING_ID: [["成功消耗1层星风快门时，增加7连击"]],
        PF_STRING_ID: [["将强化弹射变为星之剑圣的特殊剑士型强化弹射，"
                       "造成风属性伤害（伤害量以能力伤害加成判定）"]],
    }


def power_flip_rows():
    return {PF_ID: [list(PF_PROGRAM_PATHS)]}


def _encoded(tree):
    raw = wf_dsl.encode_amf3(tree)
    if wf_dsl.parse_dsl(raw)["tree"] != tree:
        raise ValueError("AMF3 roundtrip mismatch")
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)
    return compressor.compress(raw) + compressor.flush()


def _decoded(raw):
    return wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]


def _remap(value):
    if isinstance(value, str):
        return value.replace(PF_SOURCE_EFFECT, PF_EFFECT)
    if isinstance(value, list):
        return [_remap(item) for item in value]
    if isinstance(value, dict):
        return {key: _remap(item) for key, item in value.items()}
    return value


def action_assets(official_bytes_loader):
    """复制官方三档几何/时序与像素；仅将伤害主加成选择为能力。"""
    files = {("common", STOCK_ACTION_PATH + ".action.dsl.amf3.deflate"):
             _encoded(stock_action_tree()),
             ("common", ABILITY_STOCK_ACTION_PATH + ".action.dsl.amf3.deflate"):
             _encoded(stock_action_tree(1)),
             ("common", STOCK_ICON + ".png"): stock_icon_bytes(),
             ("common", GAIN_ICON + ".png"): gain_icon_bytes()}
    for uid, _, path in SPEND_MARKERS:
        files["common", path + ".action.dsl.amf3.deflate"] = _encoded(spend_action_tree(uid))
    for source, target in zip(PF_SOURCE_PATHS, PF_PROGRAM_PATHS):
        tree = _remap(_decoded(official_bytes_loader(source + ".action.dsl.amf3.deflate")))
        tree = ability_damage_reference(tree)
        files["common", target + ".action.dsl.amf3.deflate"] = _encoded(tree)
    prefix = "battle/effect/powerflip/" + PF_SOURCE_EFFECT + "/"
    paths = [prefix + PF_SOURCE_EFFECT + suffix for suffix in (".png", ".atlas.amf3.deflate")]
    for level in ("one", "two", "three"):
        stem = prefix + PF_SOURCE_EFFECT + "_powerflip_" + level
        for variant in ("", "_hit_0", "_hit_90", "_hit_180", "_hit_270"):
            paths.extend(stem + variant + suffix for suffix in
                         (".parts.amf3.deflate", ".timeline.amf3.deflate"))
    for source in paths:
        raw = official_bytes_loader(source)
        if source.endswith(".amf3.deflate"):
            raw = _encoded(_remap(_decoded(raw)))
        files["common", _remap(source)] = raw
    return files


def metadata():
    return {"required_client_capabilities": [],
            "power_flip_programs": list(PF_PROGRAM_PATHS),
            "power_flip_geometry_source": "141201 override_wind_spgirl_4anv",
            "power_flip_damage_source": "native PowerFlip with ability-damage main bonuses",
            "buff_target_as": 2, "requires_new_apk": False,
            "native_limits": "PowerFlip resistance and independent terms remain; ability-only terms do not apply",
            "stock_unique_id": STOCK_UID, "stock_per_skill": 2, "stock_cost_per_flip": 1,
            "combo_per_flip": 7, "stock_pauses_outside_fever_or_resonance": True,
            "stock_retained_until_battle_end": True, "stock_trigger": "T26 MySelfFlip",
            "spend_marker_lifetime": "created and deleted in the same impact phase",
            "spend_feedback": "native buff_reset effect; no persistent HUD marker",
            "gain_growth": {"rows": [6, 7], "trigger": "During D134 Starwind Insight layers",
                            "ability_damage_per_layer_percent": GAIN_GROWTH_STRENGTH[154] / 1000,
                            "attack_per_layer_percent": GAIN_GROWTH_STRENGTH[0] / 1000,
                            "target": "wind party", "only_fever": True, "limit": None,
                            "source": "balance 2026-09-27 batch 2: moved from ability 3 (A3)"}}
