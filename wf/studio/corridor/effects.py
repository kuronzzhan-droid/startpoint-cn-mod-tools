"""Relic/event effect registry and a faithful port of the trial server's normalizers.

The port mirrors proto-server ``rogue-corridor-v1.js`` (normalizeRelicEffect / validateRelics /
normalizeEventEffect / validateEvents) and ``rogue-effects-v3.js``. The server silently drops a
relic or event it cannot normalize, so the editor must know exactly what it would accept.
"""
from __future__ import annotations

import math
import re

RARITIES = ("common", "rare", "boss")
ELEMENTS = (1, 2, 3, 4, 5, 6)
ELEMENT_NAMES = {1: "火", 2: "水", 3: "雷", 4: "风", 5: "光", 6: "暗"}
RARITY_NAMES = {"common": "普通", "rare": "稀有", "boss": "首领"}

# Server-settled relic kinds (RELIC_EFFECT_TYPES).
RELIC_EFFECT_TYPES = {
    "max_lives_up": "int", "rest_heal_bonus": "int", "battle_gold_pct": "pct", "shop_discount_pct": "pct",
    "flawless_gold_bonus": "int", "first_fall_free": "flag", "level_up_discount_pct": "pct",
    "chest_extra_choice": "flag", "elite_extra_weapon": "flag", "battle_life_cost": "int", "gold_on_pickup": "int",
}
BUILTIN_RELIC_ALIASES = {
    "max_lives": "max_lives_up", "max_life": "max_lives_up", "max_life_up": "max_lives_up", "max_lives_plus": "max_lives_up",
    "max_hp": "max_lives_up", "max_hp_up": "max_lives_up", "lives_max_up": "max_lives_up", "life_max_up": "max_lives_up",
    "max_lives_bonus": "max_lives_up", "increase_max_lives": "max_lives_up", "max_lives_down": "-max_lives_up",
    "max_lives_minus": "-max_lives_up", "lose_max_lives": "-max_lives_up", "max_life_down": "-max_lives_up",
    "rest_heal": "rest_heal_bonus", "rest_heal_plus": "rest_heal_bonus", "rest_heal_extra": "rest_heal_bonus",
    "rest_extra_heal": "rest_heal_bonus", "extra_rest_heal": "rest_heal_bonus", "rest_bonus": "rest_heal_bonus",
    "battle_gold": "battle_gold_pct", "battle_gold_bonus": "battle_gold_pct", "battle_gold_percent": "battle_gold_pct",
    "gold_bonus_pct": "battle_gold_pct", "gold_pct": "battle_gold_pct", "gold_gain_pct": "battle_gold_pct",
    "battle_gold_up": "battle_gold_pct",
    "shop_discount_percent": "shop_discount_pct", "shop_sale": "shop_discount_pct",
    "shop_price_up_pct": "-shop_discount_pct", "shop_markup_pct": "-shop_discount_pct",
    "flawless_gold": "flawless_gold_bonus", "no_death_gold": "flawless_gold_bonus", "no_fallen_gold": "flawless_gold_bonus",
    "no_fallen_gold_bonus": "flawless_gold_bonus", "perfect_gold": "flawless_gold_bonus",
    "zero_fallen_gold": "flawless_gold_bonus", "clean_clear_gold": "flawless_gold_bonus",
    "flawless_bonus_gold": "flawless_gold_bonus",
    "first_death_free": "first_fall_free", "first_fallen_free": "first_fall_free", "ignore_first_fallen": "first_fall_free",
    "first_fall_no_life_loss": "first_fall_free", "first_death_no_penalty": "first_fall_free",
    "death_shield": "first_fall_free", "first_fallen_no_cost": "first_fall_free",
    "enhance_all_weapons": "enhance_all_on_pickup", "enhance_all": "enhance_all_on_pickup",
    "upgrade_all_weapons": "enhance_all_on_pickup", "weapons_enhance_all": "enhance_all_on_pickup",
    "enhance_all_weapons_on_pickup": "enhance_all_on_pickup",
    "level_up_discount": "level_up_discount_pct", "levelup_discount": "level_up_discount_pct",
    "level_up_half_price": "level_up_discount_pct", "character_upgrade_discount": "level_up_discount_pct",
    "upgrade_discount": "level_up_discount_pct", "level_up_discount_percent": "level_up_discount_pct",
    "chest_extra_option": "chest_extra_choice", "chest_extra": "chest_extra_choice", "chest_choices_plus": "chest_extra_choice",
    "extra_chest_choice": "chest_extra_choice", "chest_extra_choices": "chest_extra_choice",
    "elite_weapon_drop": "elite_extra_weapon", "elite_extra_drop": "elite_extra_weapon",
    "elite_bonus_weapon": "elite_extra_weapon", "elite_extra_weapons": "elite_extra_weapon",
    "lose_lives_per_battle": "battle_life_cost", "battle_lives_cost": "battle_life_cost",
    "life_cost_per_battle": "battle_life_cost",
    "gain_gold": "gold_on_pickup", "gold": "gold_on_pickup",
    "battle_gold_multiplier": "battle_gold_pct|multiplier_bonus", "gold_multiplier": "battle_gold_pct|multiplier_bonus",
    "shop_discount": "shop_discount_pct|price_multiplier", "shop_price_multiplier": "shop_discount_pct|price_multiplier",
    "character_upgrade_cost_multiplier": "level_up_discount_pct|price_multiplier",
    "level_up_cost_multiplier": "level_up_discount_pct|price_multiplier",
    "upgrade_cost_multiplier": "level_up_discount_pct|price_multiplier",
    "flawless_battle_gold_bonus": "flawless_gold_bonus", "ignore_first_death_per_battle": "first_fall_free",
    "ignore_first_death": "first_fall_free", "elite_extra_weapon_drop": "elite_extra_weapon",
}
# rogue-effects-v3.js: battle effects the server only forwards (runtime="client_pending").
COMBAT_UNITS = {
    "skill_charge_speed_pct": "percent", "skill_damage_range_pct": "percent", "combo_recharge_pct": "percent",
    "healing_received_pct": "percent", "skill_invincibility_ms": "milliseconds", "fever_damage_pct": "percent",
    "power_flip_damage_pct": "percent", "direct_damage_pct": "percent", "skill_damage_pct": "percent",
    "element_damage_pct": "percent",
}
EVENT_EFFECT_TYPES = ("lose_lives", "gain_lives", "gain_gold", "lose_gold", "gamble_gold", "gain_relic", "swap_relic",
                      "extract_soul", "enhance_weapon", "gain_character", "gain_weapon", "fight_elite", "leave")
BUILTIN_EVENT_ALIASES = {
    "lose_life": "lose_lives", "gain_life": "gain_lives", "heal": "gain_lives", "heal_lives": "gain_lives",
    "pay_gold": "lose_gold", "spend_gold": "lose_gold", "gold": "gain_gold", "gamble": "gamble_gold",
    "relic": "gain_relic", "gain_rare_relic": "gain_relic", "trade_relic": "swap_relic", "exchange_relic": "swap_relic",
    "enhance": "enhance_weapon", "upgrade_weapon": "enhance_weapon", "character": "gain_character",
    "recruit": "gain_character", "fight": "fight_elite", "battle_elite": "fight_elite", "elite_battle": "fight_elite",
    "nothing": "leave", "exit": "leave",
}
VALUE_KEYS = ("value", "amount", "count", "free_deaths", "enhance_step", "step", "steps", "percent", "pct", "multiplier")

# ---------------------------------------------------------------- UI registry
RELIC_KINDS = {
    "max_lives_up": {"label": "生命上限（获得时）", "unit": "点", "value": "int", "min": -20, "max": 20},
    "rest_heal_bonus": {"label": "休息额外回复", "unit": "点", "value": "int", "min": -20, "max": 20},
    "battle_gold_pct": {"label": "战斗金币加成", "unit": "%", "value": "number", "min": 0, "max": 300},
    "shop_discount_pct": {"label": "商店折扣", "unit": "%（20=八折）", "value": "number", "min": 0, "max": 90},
    "flawless_gold_bonus": {"label": "无人阵亡额外金币", "unit": "金币", "value": "int", "min": 0, "max": 2000},
    "first_fall_free": {"label": "每场首个阵亡不扣生命", "unit": "次", "value": "int", "min": 1, "max": 1},
    "level_up_discount_pct": {"label": "角色强化折扣", "unit": "%", "value": "number", "min": 0, "max": 95},
    "chest_extra_choice": {"label": "宝箱多一个选项", "unit": "", "value": "int", "min": 1, "max": 1},
    "elite_extra_weapon": {"label": "精英额外武器", "unit": "", "value": "int", "min": 1, "max": 1},
    "battle_life_cost": {"label": "每场战斗额外扣生命", "unit": "点", "value": "int", "min": 0, "max": 20},
    "gold_on_pickup": {"label": "获得时金币", "unit": "金币", "value": "int", "min": 0, "max": 10000},
    "skill_charge_speed_pct": {"label": "技能充能速度", "unit": "%", "value": "number", "min": 0, "max": 300, "combat": True},
    "skill_damage_range_pct": {"label": "技能伤害范围", "unit": "%", "value": "number", "min": 0, "max": 300, "combat": True},
    "combo_recharge_pct": {"label": "连击充能", "unit": "%", "value": "number", "min": 0, "max": 100, "combat": True,
                           "extra": {"combo_threshold": {"label": "每多少连击", "value": "int", "min": 1, "max": 9999}}},
    "healing_received_pct": {"label": "受到回复量", "unit": "%", "value": "number", "min": 0, "max": 300, "combat": True},
    "skill_invincibility_ms": {"label": "技能无敌延长", "unit": "毫秒", "value": "int", "min": 0, "max": 10000, "combat": True},
    "fever_damage_pct": {"label": "Fever 伤害", "unit": "%", "value": "number", "min": 0, "max": 300, "combat": True},
    "power_flip_damage_pct": {"label": "强化弹射伤害", "unit": "%", "value": "number", "min": 0, "max": 300, "combat": True},
    "direct_damage_pct": {"label": "直击伤害", "unit": "%", "value": "number", "min": 0, "max": 300, "combat": True},
    "skill_damage_pct": {"label": "技能伤害", "unit": "%", "value": "number", "min": 0, "max": 300, "combat": True},
    "element_damage_pct": {"label": "属性伤害", "unit": "%", "value": "number", "min": 0, "max": 300, "combat": True,
                           "extra": {"element": {"label": "属性", "value": "element"}}},
}
EVENT_KINDS = {
    "lose_lives": {"label": "失去生命", "value": "int", "min": 1, "max": 20},
    "gain_lives": {"label": "回复生命", "value": "int", "min": 1, "max": 20},
    "gain_gold": {"label": "获得金币", "value": "int", "min": 1, "max": 100000},
    "lose_gold": {"label": "支付金币", "value": "int", "min": 1, "max": 100000},
    "gamble_gold": {"label": "赌金币", "value": "gamble"},
    "gain_relic": {"label": "获得遗物（按稀有度）", "value": "relic"},
    "swap_relic": {"label": "交换一件遗物", "value": "swap"},
    "enhance_weapon": {"label": "强化一把武器至满", "value": None},
    "extract_soul": {"label": "提取武器魂珠（武器保留）", "value": None},
    "gain_weapon": {"label": "获得武器", "value": "tier_element"},
    "gain_character": {"label": "获得角色", "value": "tier_element"},
    "fight_elite": {"label": "精英战（胜利后结算其余效果）", "value": "true"},
    "leave": {"label": "离开", "value": None},
}


def registry() -> dict:
    return {"relic_kinds": RELIC_KINDS, "event_kinds": EVENT_KINDS, "rarities": RARITY_NAMES,
            "elements": {str(k): v for k, v in ELEMENT_NAMES.items()},
            "requires": {"min_gold": "至少持有金币", "min_lives": "至少剩余生命", "min_relics": "至少持有遗物",
                         "max_roster_below": "名单人数少于"}}


# ---------------------------------------------------------------- JS value semantics
def _is_record(v) -> bool:
    return isinstance(v, dict)


def _is_number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _js_number(v) -> float:
    if v is True:
        return 1.0
    if v is False or v is None:
        return 0.0 if v is False else math.nan
    if _is_number(v):
        return float(v)
    if isinstance(v, str):
        text = v.strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return math.nan
    return math.nan


def _to_int(v):
    if isinstance(v, str) and re.fullmatch(r"-?\d{1,15}", v.strip()):
        v = int(v.strip())
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if isinstance(v, float):
        if not v.is_integer():
            return None
        v = int(v)
    return v if abs(v) <= 2 ** 53 - 1 else None


def _js_round(v: float) -> int:
    return math.floor(v + 0.5)


def _numeric_of(v):
    if v is True:
        return True
    if _is_number(v) or isinstance(v, str):
        return _js_number(v)
    if _is_record(v):
        for k in VALUE_KEYS:
            if v.get(k) is not None:
                return _numeric_of(v[k])
    return None


def _first(*values):
    for v in values:
        if v is not None:
            return v
    return None


# ---------------------------------------------------------------- relics
def normalize_combat(e):
    if not _is_record(e) or e.get("type") not in COMBAT_UNITS:
        return None
    v = e.get("value")
    if not _is_number(v) or not math.isfinite(v) or v < 0 or v > 10000:
        return {"error": "invalid combat effect value"}
    effect = {"type": e["type"], "value": v, "unit": COMBAT_UNITS[e["type"]], "scope": "party", "runtime": "client_pending"}
    if e["type"] == "element_damage_pct":
        el = e.get("element")
        if isinstance(el, bool) or not isinstance(el, int) or el not in ELEMENTS:
            return {"error": "invalid effect element"}
        effect["element"] = el
    if e["type"] == "combo_recharge_pct":
        th = e.get("combo_threshold")
        if isinstance(th, bool) or not isinstance(th, int) or th < 1:
            return {"error": "invalid combo threshold"}
        effect["combo_threshold"] = th
    return {"effects": [effect]}


def normalize_relic_effect(e, aliases=None):
    aliases = BUILTIN_RELIC_ALIASES if aliases is None else aliases
    combat = normalize_combat(e) if e else None
    if combat:
        return combat
    if not _is_record(e):
        return {"error": "effect is not an object"}
    raw_type = str(_first(e.get("type"), e.get("kind"), e.get("effect")) or "").strip().lower()
    kind_type, negate, transform = raw_type, False, None
    if kind_type not in RELIC_EFFECT_TYPES:
        alias = aliases.get(kind_type)
        if not isinstance(alias, str):
            return {"error": f'unknown effect type "{raw_type}"'}
        target, _, tf = alias.partition("|")
        negate = target.startswith("-")
        kind_type = target[1:] if negate else target
        transform = tf or None
        if kind_type not in RELIC_EFFECT_TYPES:
            return {"error": f'alias of "{raw_type}" points to unknown "{alias}"'}
    kind = RELIC_EFFECT_TYPES[kind_type]
    value = e.get("value")
    container = value if _is_record(value) else e
    if _is_record(value):
        v = _numeric_of(value)
    else:
        v = _numeric_of(_first(value, e.get("amount"), e.get("count"), e.get("percent"), e.get("pct")))
    if (v is None or v is True) and kind == "flag":
        v = 1
    v = _js_number(v) if v is not None else math.nan
    if not math.isfinite(v):
        return {"error": f"effect {raw_type} has no numeric value"}
    if transform == "price_multiplier":
        v = (1 - v) * 100 if 0 < v < 1 else v
    elif transform == "multiplier_bonus":
        v = (v - 1) * 100 if v >= 1 else v * 100
    elif transform:
        return {"error": f"alias transform {transform} unknown"}
    elif kind == "pct" and v != 0 and abs(v) < 1:
        v *= 100
    if negate:
        v = -v
    if abs(v) > 1000:
        return {"error": f"effect {kind_type} value {v} out of range"}
    if kind_type == "shop_discount_pct" and v > 90:
        return {"error": "shop_discount_pct > 90"}
    if kind_type == "level_up_discount_pct" and (v < 0 or v > 100):
        return {"error": "level_up_discount_pct out of 0..100"}
    v = _js_round(v * 100) / 100 if kind == "pct" else _js_round(v)
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    effects = [{"type": kind_type, "value": v}]
    penalty_type = _first(container.get("penalty_type"), e.get("penalty_type"))
    if penalty_type is not None:
        pen = normalize_relic_effect({"type": penalty_type,
                                      "value": _first(container.get("penalty_value"), e.get("penalty_value"))}, aliases)
        if "error" in pen:
            return {"error": f"penalty: {pen['error']}"}
        effects.extend(pen["effects"])
    return {"effects": effects}


def relic_raw_effects(r: dict) -> list:
    raws = []

    def take(v):
        if isinstance(v, list):
            raws.extend(v)
        elif v is not None:
            raws.append(v)
    effect = r.get("effect")
    if _is_record(effect):
        main = {k: v for k, v in effect.items() if k not in ("cost", "costs", "drawback", "drawbacks", "penalty")}
        raws.append(main)
        for k in ("cost", "costs", "drawback", "drawbacks", "penalty"):
            take(effect.get(k))
    else:
        take(effect)
    for k in ("effects", "cost", "costs", "drawback", "drawbacks", "penalty"):
        take(r.get(k))
    return raws


def relic_aliases(rules: dict) -> dict:
    extra = {str(k).lower(): v for k, v in (rules.get("relic_effect_aliases") or {}).items() if not str(k).startswith("_")}
    return {**BUILTIN_RELIC_ALIASES, **extra}


def event_aliases(rules: dict) -> dict:
    extra = {str(k).lower(): v for k, v in (rules.get("event_effect_aliases") or {}).items() if not str(k).startswith("_")}
    return {**BUILTIN_EVENT_ALIASES, **extra}


def server_relic(r, aliases) -> dict:
    """{"ok": True, "effects": [...]} as the server would load it, or {"ok": False, "reason": ...}."""
    if not _is_record(r):
        return {"ok": False, "reason": "not an object"}
    rid = _first(r.get("relic_id"), r.get("id"))
    rid = str(rid) if _is_number(rid) else rid
    if not isinstance(rid, str) or not rid.strip():
        return {"ok": False, "reason": "bad relic_id"}
    rarity = str(r.get("rarity") or "").lower()
    if rarity not in RARITIES:
        return {"ok": False, "reason": f"bad rarity {r.get('rarity')}"}
    if not isinstance(r.get("name"), str) or not r["name"].strip():
        return {"ok": False, "reason": "missing name"}
    raws = relic_raw_effects(r)
    if not raws:
        return {"ok": False, "reason": "has no effect"}
    effects = []
    for e in raws:
        n = normalize_relic_effect(e, aliases)
        if "error" in n:
            return {"ok": False, "reason": n["error"]}
        effects.extend(n["effects"])
    return {"ok": True, "relic_id": rid, "rarity": rarity, "effects": effects}


# ---------------------------------------------------------------- events
def normalize_event_effect(e, aliases=None):
    aliases = BUILTIN_EVENT_ALIASES if aliases is None else aliases
    if isinstance(e, str):
        e = {"type": e}
    if not _is_record(e):
        return {"error": "effect is not an object"}
    etype = str(_first(e.get("type"), e.get("kind")) or "").strip().lower()
    if etype not in EVENT_EFFECT_TYPES:
        alias = aliases.get(etype)
        if not isinstance(alias, str) or alias not in EVENT_EFFECT_TYPES:
            return {"error": f'unknown event effect "{etype}"'}
        etype = alias
    value = e.get("value")
    vrec = value if _is_record(value) else {}

    def amount():
        raw = value if (_is_number(value) or isinstance(value, str)) else _first(e.get("amount"), e.get("count"),
                                                                               vrec.get("amount"), vrec.get("value"))
        n = _to_int(raw)
        return n if n is not None and 0 <= n <= 1_000_000 else None

    if etype in ("leave", "fight_elite", "extract_soul", "enhance_weapon"):
        return {"effect": {"type": etype}}
    if etype == "swap_relic":
        return {"effect": {"type": etype, "match_rarity": _first(e.get("match_rarity"), vrec.get("match_rarity")) is not False}}
    if etype in ("lose_lives", "gain_lives", "gain_gold", "lose_gold"):
        n = amount()
        return {"error": f"{etype} needs a non-negative integer value"} if n is None else {"effect": {"type": etype, "value": n}}
    if etype == "gamble_gold":
        p = _js_number(value if _is_number(value) else _first(e.get("probability"), e.get("win_chance"),
                                                              vrec.get("probability"), vrec.get("win_chance"), 0.5))
        if not (0 < p < 1):
            return {"error": "gamble_gold probability must be in (0,1)"}
        lose_mult = _first(e.get("lose_multiplier"), vrec.get("lose_multiplier"))
        win = _js_number(_first(e.get("win_multiplier"), vrec.get("win_multiplier"), 2))
        lose = (1 - _js_number(lose_mult)) if lose_mult is not None else _js_number(
            _first(e.get("lose_fraction"), vrec.get("lose_fraction"), 0.5))
        if not (1 <= win <= 10) or not (0 <= lose <= 1):
            return {"error": "gamble_gold multipliers out of range"}
        return {"effect": {"type": etype, "value": p, "win_multiplier": win, "lose_fraction": lose}}
    if etype == "gain_relic":
        rarity = value if isinstance(value, str) else _first(e.get("rarity"), vrec.get("rarity"))
        if rarity is not None and rarity != "any":
            rarity = str(rarity).lower()
        if rarity in ("any", "random", None):
            rarity = None
        if rarity is not None and rarity not in RARITIES:
            return {"error": f"gain_relic bad rarity {rarity}"}
        return {"effect": {"type": etype, "rarity": rarity}}
    if etype in ("gain_weapon", "gain_character"):
        raw_tier = _first(e.get("tier"), vrec.get("tier"), value if _is_number(value) else 2)
        tier = _to_int(re.sub(r"^t", "", raw_tier, flags=re.I) if isinstance(raw_tier, str) else raw_tier)
        element = _first(e.get("element"), vrec.get("element"), "random")
        if _is_number(element):
            if element not in ELEMENTS:
                return {"error": "gain_character element must be 1..6"}
        elif str(element) not in ("random", "choose", "preferred"):
            return {"error": "gain_character element must be random|choose|preferred|1..6"}
        if tier is None or tier < 1 or tier > 4:
            return {"error": "gain_character tier must be 1..4"}
        return {"effect": {"type": etype, "tier": tier, "element": element}}
    return {"error": f"unhandled {etype}"}


def server_event(ev, aliases) -> dict:
    if not _is_record(ev):
        return {"ok": False, "reason": "not an object"}
    eid = _first(ev.get("event_id"), ev.get("id"))
    eid = str(eid) if _is_number(eid) else eid
    if not isinstance(eid, str) or not eid.strip():
        return {"ok": False, "reason": "bad event_id"}
    if not isinstance(ev.get("title"), str) or not ev["title"].strip() or not isinstance(ev.get("text"), str):
        return {"ok": False, "reason": "needs title and text"}
    options = ev.get("options")
    if not isinstance(options, list) or not 1 <= len(options) <= 6:
        return {"ok": False, "reason": "needs 1..6 options"}
    out = []
    for j, o in enumerate(options):
        if not _is_record(o) or not isinstance(o.get("label"), str) or not o["label"].strip():
            return {"ok": False, "reason": f"option {j} needs a label"}
        raw = o["effects"] if isinstance(o.get("effects"), list) else ([o["effect"]] if "effect" in o else None)
        if not raw:
            return {"ok": False, "reason": f"option {j} has no effects"}
        effects = []
        for e in raw:
            n = normalize_event_effect(e, aliases)
            if "error" in n:
                return {"ok": False, "reason": f"option {j}: {n['error']}"}
            effects.append(n["effect"])
        if sum(1 for e in effects if e["type"] == "fight_elite") > 1:
            return {"ok": False, "reason": f"option {j} has two fight_elite"}
        out.append(effects)
    return {"ok": True, "event_id": eid, "options": out}


# ---------------------------------------------------------------- human text
def describe_settled(effect: dict) -> str:
    t, v = effect.get("type"), effect.get("value")
    label = RELIC_KINDS.get(t, {}).get("label", t)
    unit = RELIC_KINDS.get(t, {}).get("unit", "")
    if t in ("first_fall_free", "chest_extra_choice", "elite_extra_weapon"):
        return label
    if t == "element_damage_pct":
        return f"{ELEMENT_NAMES.get(effect.get('element'), '?')}{label} +{v}%"
    if t == "combo_recharge_pct":
        return f"每 {effect.get('combo_threshold')} 连击{label} +{v}%"
    sign = "+" if isinstance(v, (int, float)) and v >= 0 and t not in ("shop_discount_pct", "level_up_discount_pct") else ""
    return f"{label} {sign}{v}{unit.split('（')[0]}"


# ---------------------------------------------------------------- templates
RELIC_TEMPLATES = [
    {"id": "gold_on_pickup", "label": "获得时金币", "rarity": "common", "effects": [{"type": "gold_on_pickup", "value": 50}],
     "zh": ("新遗物", "获得时获得50金币。"), "en": ("", "")},
    {"id": "max_lives_up", "label": "生命上限", "rarity": "common", "effects": [{"type": "max_lives_up", "value": 3}],
     "zh": ("新遗物", "获得时，玩家生命值上限+3。"), "en": ("", "")},
    {"id": "battle_gold_pct", "label": "战斗金币加成", "rarity": "common", "effects": [{"type": "battle_gold_pct", "value": 20}],
     "zh": ("新遗物", "所有战斗结算获得的金币+20%。"), "en": ("", "")},
    {"id": "shop_discount_pct", "label": "商店折扣", "rarity": "rare", "effects": [{"type": "shop_discount_pct", "value": 20}],
     "zh": ("新遗物", "商店价格八折（-20%）。"), "en": ("", "")},
    {"id": "trade_off", "label": "收益+代价（复合）", "rarity": "boss",
     "effects": [{"type": "gold_on_pickup", "value": 100}, {"type": "max_lives_up", "value": -3}],
     "zh": ("新遗物", "获得时金币+100，但生命上限-3。"), "en": ("", "")},
    {"id": "combat_skill_damage", "label": "战斗：技能伤害（客户端效果）", "rarity": "rare",
     "effects": [{"type": "skill_damage_pct", "value": 20, "scope": "party", "runtime": "client_pending"}],
     "zh": ("新遗物", "技能伤害+20%。"), "en": ("", "")},
    {"id": "combat_element", "label": "战斗：属性伤害（客户端效果）", "rarity": "rare",
     "effects": [{"type": "element_damage_pct", "value": 25, "element": 1, "scope": "party", "runtime": "client_pending"}],
     "zh": ("新遗物", "火属性伤害+25%。"), "en": ("", "")},
]
EVENT_TEMPLATES = [
    {"id": "gold_or_leave", "label": "获得金币 / 离开",
     "zh": ("新事件", "事件叙述正文。"), "options": [
         {"zh": "获得30金币", "effects": [{"type": "gain_gold", "value": 30}]},
         {"zh": "离开", "effects": [{"type": "leave"}]}]},
    {"id": "pay_for_relic", "label": "付金币换遗物",
     "zh": ("新事件", "商人兜售一件遗物。"), "options": [
         {"zh": "支付80金币获得一件稀有遗物", "requires": {"min_gold": 80},
          "effects": [{"type": "lose_gold", "value": 80}, {"type": "gain_relic", "value": {"rarity": "rare"}}]},
         {"zh": "离开", "effects": [{"type": "leave"}]}]},
    {"id": "blood_for_power", "label": "生命换遗物",
     "zh": ("新事件", "祭坛要求以血为代价。"), "options": [
         {"zh": "失去3点生命，获得一件稀有遗物", "requires": {"min_lives": 4},
          "effects": [{"type": "lose_lives", "value": 3}, {"type": "gain_relic", "value": {"rarity": "rare"}}]},
         {"zh": "离开", "effects": [{"type": "leave"}]}]},
    {"id": "ambush", "label": "伏击（精英战+遗物）",
     "zh": ("新事件", "黑暗里冲出一群敌人。"), "options": [
         {"zh": "迎战", "effects": [{"type": "fight_elite", "value": True}, {"type": "gain_relic", "value": {"rarity": "random"}}]}]},
    {"id": "recruit", "label": "招募同伴",
     "zh": ("新事件", "深渊里有人迷了路。"), "options": [
         {"zh": "带上随机属性同伴", "effects": [{"type": "gain_character", "value": {"tier": "T2", "element": "random"}}]},
         {"zh": "离开", "effects": [{"type": "leave"}]}]},
]


def templates() -> dict:
    return {"relics": [{k: v for k, v in t.items()} for t in RELIC_TEMPLATES],
            "events": [{k: v for k, v in t.items()} for t in EVENT_TEMPLATES]}
