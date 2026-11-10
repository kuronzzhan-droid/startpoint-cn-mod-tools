"""Structured edit commands. A batch applies to a copy and commits all-or-nothing.

Commands never accept free-form paths outside the allowlists, scripts or expressions: effect
types must be registered, values must be plain JSON numbers/strings/booleans of the right shape.
"""
from __future__ import annotations

import copy

from . import jsonio, rulesfields
from .effects import BUILTIN_RELIC_ALIASES, COMBAT_UNITS, EVENT_EFFECT_TYPES, RARITIES, RELIC_KINDS, templates
from .workspace import (event_keys, new_option_id, next_id, option_key, relic_keys, remove_locale_keys,
                        replace_option_keys, set_locale)


class CommandError(Exception):
    pass


RELIC_TYPES = set(RELIC_KINDS) | set(BUILTIN_RELIC_ALIASES)
RELIC_EFFECT_KEYS = {"type", "value", "scope", "runtime", "element", "combo_threshold"}
EVENT_EFFECT_KEYS = {"type", "value"}
REQUIRE_KEYS = {"min_gold", "min_lives", "min_relics", "max_roster_below"}
CHAR_POLICY = {"starter_eligible", "min_act", "enabled", "notes"}
WEAPON_POLICY = {"enabled", "starter_eligible", "min_act", "tier_override", "soul_extractable", "notes"}
SOUL_POLICY = {"enabled", "min_act", "notes"}
RELIC_POLICY = {"enabled", "min_act", "reward_eligible", "shop_eligible", "notes"}
EVENT_POLICY = {"enabled", "min_act", "weight_multiplier", "notes"}
ENCOUNTER_POLICY = {"enabled", "min_act", "allowed_acts", "kind_override", "notes"}
ACT_POLICY = {"exclude_quest_ids", "exclude_rounds", "boss_quest_ids"}


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def _text(value, name, allow_empty=True):
    if not isinstance(value, str):
        raise CommandError(f"{name} 必须是文本")
    if not allow_empty and not value.strip():
        raise CommandError(f"{name} 不能为空")
    return value


def _ids(cmd, key="ids"):
    ids = cmd.get(key)
    if not isinstance(ids, list) or not ids or not all(isinstance(i, str) and i for i in ids):
        raise CommandError(f"{key} 必须是非空的字符串 ID 列表")
    if len(ids) > 2000:
        raise CommandError("一次批量最多 2000 条")
    return ids


def _policy_patch(entry: dict, fields: dict, allowed: set, *, acts=3) -> dict:
    """Apply policy fields; ``None`` clears a field (back to inherited behaviour)."""
    unknown = set(fields) - allowed
    if unknown:
        raise CommandError("不支持的字段：" + "、".join(sorted(unknown)))
    for key, value in fields.items():
        if value is None:
            entry.pop(key, None)
            continue
        if key in ("enabled", "starter_eligible", "reward_eligible", "shop_eligible", "soul_extractable"):
            if not isinstance(value, bool):
                raise CommandError(f"{key} 需要布尔值")
        elif key == "min_act":
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= acts:
                raise CommandError("min_act 只能是 1..3")
        elif key == "tier_override":
            if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 4:
                raise CommandError("tier_override 只能是 1..4")
        elif key == "weight_multiplier":
            if not _is_num(value) or not 0 <= value <= 100:
                raise CommandError("weight_multiplier 只能是 0..100")
        elif key == "notes":
            _text(value, "备注")
            if not value:
                entry.pop(key, None)
                continue
        elif key == "allowed_acts":
            if not isinstance(value, list) or not value or not all(isinstance(a, int) and 1 <= a <= acts for a in value):
                raise CommandError("allowed_acts 需要 1..3 的列表")
            value = sorted(set(value))
        elif key == "kind_override":
            if value not in ("normal", "elite", "boss"):
                raise CommandError("kind_override 只能是 normal/elite/boss")
        elif key in ("exclude_quest_ids", "boss_quest_ids"):
            if not isinstance(value, list) or not all(isinstance(q, str) and q.isdigit() for q in value):
                raise CommandError(f"{key} 需要 quest_id 字符串列表")
            value = sorted(set(value))
        elif key == "exclude_rounds":
            if not isinstance(value, list) or not all(isinstance(r, int) and not isinstance(r, bool) for r in value):
                raise CommandError("exclude_rounds 需要整数列表")
            value = sorted(set(value))
        entry[key] = value
    return entry


def _clean_policy(table: dict, key: str) -> None:
    if key in table and not table[key]:
        del table[key]


# ---------------------------------------------------------------- effects input
def relic_effect(raw) -> dict:
    if not isinstance(raw, dict):
        raise CommandError("效果必须是对象")
    unknown = set(raw) - RELIC_EFFECT_KEYS
    if unknown:
        raise CommandError("效果不接受字段：" + "、".join(sorted(unknown)))
    etype = raw.get("type")
    if etype not in RELIC_TYPES:
        raise CommandError(f"未登记的遗物效果类型：{etype!r}（只能从效果清单里选）")
    value = raw.get("value")
    if etype == "ignore_first_death_per_battle":
        if not isinstance(value, dict) or set(value) - {"free_deaths", "penalty_type", "penalty_value"}:
            raise CommandError("ignore_first_death_per_battle 需要 {free_deaths, penalty_type, penalty_value}")
        if not all(_is_num(v) or isinstance(v, str) for v in value.values()):
            raise CommandError("效果参数只能是数字或已登记的类型名")
    elif value is not None and not _is_num(value) and value is not True:
        raise CommandError(f"{etype} 的 value 必须是数字")
    out = {"type": etype}
    if "value" in raw:
        out["value"] = value
    if etype in COMBAT_UNITS:
        if etype == "element_damage_pct":
            el = raw.get("element")
            if not isinstance(el, int) or isinstance(el, bool) or not 1 <= el <= 6:
                raise CommandError("属性伤害需要属性 1..6")
            out["element"] = el
        if etype == "combo_recharge_pct":
            th = raw.get("combo_threshold")
            if not isinstance(th, int) or isinstance(th, bool) or th < 1:
                raise CommandError("连击充能需要连击阈值 ≥ 1")
            out["combo_threshold"] = th
        out["scope"] = "party"
        out["runtime"] = "client_pending"
    elif {"scope", "runtime", "element", "combo_threshold"} & set(raw):
        raise CommandError(f"{etype} 不接受 scope/runtime/element/combo_threshold")
    return out


def event_effect(raw) -> dict:
    if not isinstance(raw, dict):
        raise CommandError("效果必须是对象")
    unknown = set(raw) - EVENT_EFFECT_KEYS
    if unknown:
        raise CommandError("事件效果不接受字段：" + "、".join(sorted(unknown)))
    etype = raw.get("type")
    if etype not in EVENT_EFFECT_TYPES:
        raise CommandError(f"未登记的事件效果类型：{etype!r}")
    value = raw.get("value")
    out = {"type": etype}
    if etype in ("lose_lives", "gain_lives", "gain_gold", "lose_gold"):
        if not isinstance(value, int) or isinstance(value, bool):
            raise CommandError(f"{etype} 需要整数")
        out["value"] = value
    elif etype == "gamble_gold":
        if not isinstance(value, dict) or set(value) != {"win_chance", "win_multiplier", "lose_multiplier"} or \
                not all(_is_num(v) for v in value.values()):
            raise CommandError("赌金币需要 win_chance / win_multiplier / lose_multiplier 三个数字")
        out["value"] = value
    elif etype == "gain_relic":
        if not isinstance(value, dict) or set(value) - {"rarity", "relic_id"} or value.get("rarity") not in (*RARITIES, "random"):
            raise CommandError("获得遗物需要 rarity（common/rare/boss/random）")
        out["value"] = value
    elif etype == "swap_relic":
        if value is not None:
            if not isinstance(value, dict) or set(value) - {"match_rarity", "target"}:
                raise CommandError("交换遗物只接受 match_rarity/target")
            out["value"] = value
    elif etype in ("gain_weapon", "gain_character"):
        if not isinstance(value, dict) or set(value) - {"tier", "element"} or value.get("tier") not in ("T1", "T2", "T3", "T4"):
            raise CommandError("获得角色/武器需要 tier T1..T4 与 element")
        el = value.get("element", "random")
        if not (el in ("preferred", "random", "choose") or (isinstance(el, int) and not isinstance(el, bool) and 1 <= el <= 6)):
            raise CommandError("element 只能是 preferred/random/choose 或 1..6")
        out["value"] = value
    elif etype in ("fight_elite", "leave"):
        if value is not None:
            out["value"] = True
    elif value is not None:
        raise CommandError(f"{etype} 不需要参数")
    return out


def requires_of(raw):
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) - REQUIRE_KEYS:
        raise CommandError("条件只能是 " + "/".join(sorted(REQUIRE_KEYS)))
    for k, v in raw.items():
        if not isinstance(v, int) or isinstance(v, bool) or v < 0:
            raise CommandError(f"条件 {k} 需要非负整数")
    return dict(raw)


# ---------------------------------------------------------------- context
class Batch:
    def __init__(self, workspace: dict, master):
        self.ws = copy.deepcopy(workspace)
        self.master = master
        self.results: list[dict] = []
        self.next_revision = workspace["revision"] + 1

    @property
    def data(self):
        return self.ws["data"]

    @property
    def policy(self):
        return self.ws["policy"]

    @property
    def life(self):
        return self.ws["lifecycle"]

    def relic(self, rid):
        for r in self.data["relics"]:
            if r.get("relic_id") == rid:
                return r
        raise CommandError(f"没有遗物 {rid}")

    def event(self, eid):
        for e in self.data["events"]:
            if e.get("event_id") == eid:
                return e
        raise CommandError(f"没有事件 {eid}")

    def tombstone(self, kind, eid, reason):
        self.life["tombstones"].append({"kind": kind, "id": eid, "at_revision": self.next_revision,
                                        "reason": reason or "编辑台删除"})

    def reserve(self, key, value):
        if value not in self.life[key]:
            self.life[key].append(value)


# ---------------------------------------------------------------- handlers
def cmd_rules_set(b: Batch, cmd):
    path = cmd.get("path")
    field = rulesfields.BY_PATH.get(path)
    if field is None:
        raise CommandError(f"规则字段 {path!r} 不可编辑（只读或未登记）")
    value = cmd.get("value")
    problem = rulesfields.check_value(field, value)
    if problem:
        raise CommandError(f"{field['label']}：{problem}")
    parts = path.strip("/").split("/")
    node = b.data["rules"]
    for part in parts[:-1]:
        if isinstance(node, list):
            node = node[int(part)]
        else:
            if part not in node:
                if not field.get("optional"):
                    raise CommandError(f"规则里缺少 {path}")
                node[part] = {}
            node = node[part]
    last = parts[-1]
    old = node[int(last)] if isinstance(node, list) else node.get(last)
    if old is None and not field.get("optional") and not isinstance(node, list):
        raise CommandError(f"规则里缺少 {path}")
    new = jsonio.same_number_shape(old, value)
    if isinstance(node, list):
        node[int(last)] = new
    else:
        node[last] = new
    return {"path": path, "before": old, "after": new}


def _char_lookup(b: Batch):
    admitted = {str(c.get("id")): c for c in b.master.characters()}
    excluded = {str(c.get("id")): c for c in b.master.excluded_characters()}
    return admitted, excluded


def cmd_character_set(b: Batch, cmd):
    ids = _ids(cmd)
    admitted, excluded = _char_lookup(b)
    overlay = b.data["pool_overlay"]
    overrides = overlay.setdefault("tier_overrides", {}).setdefault("characters", {})
    boss = {str(c.get("id")) for c in (overlay.get("boss_playable") or {}).get("characters") or []}
    reason = cmd.get("reason")
    changed = []
    for cid in ids:
        row = admitted.get(cid) or excluded.get(cid)
        if row is None:
            raise CommandError(f"主数据里没有角色 {cid}（不能凭空造游戏 ID）")
        in_table = cid in admitted
        if "tier" in cmd:
            tier = cmd["tier"]
            if not in_table:
                raise CommandError(f"{cid} 不在 tier_table 入池名单，服务端不接受档位覆盖（boss 转可玩固定为强化传说）")
            if tier == "source":
                if cid in overrides and overrides[cid].get("tier") is not None:
                    del overrides[cid]
            elif isinstance(tier, int) and not isinstance(tier, bool) and 1 <= tier <= 4:
                current = overrides.get(cid)
                if current is not None and current.get("tier") is None:
                    raise CommandError(f"{cid} 已禁用入池，先启用再改档位")
                if tier == row.get("tier"):
                    overrides.pop(cid, None)
                else:
                    overrides[cid] = {"element": row.get("element"), "from_tier": row.get("tier"), "name": row.get("name"),
                                      "reason": _text(reason or f"编辑台 r{b.next_revision}：作者调整档位", "理由", False),
                                      "tier": tier}
            else:
                raise CommandError("tier 只能是 1..4 或 \"source\"（恢复主数据档位）")
        if "enabled" in cmd:
            enabled = cmd["enabled"]
            pol = b.policy["characters"].setdefault(cid, {})
            if not isinstance(enabled, bool):
                raise CommandError("enabled 需要布尔值")
            if in_table or cid in boss:
                pol.pop("enabled", None)
                if enabled:
                    if cid in overrides and overrides[cid].get("tier") is None:
                        del overrides[cid]
                else:
                    overrides[cid] = {"element": row.get("element"), "from_tier": row.get("tier"), "name": row.get("name"),
                                      "reason": _text(reason or f"编辑台 r{b.next_revision}：作者移出回廊池", "理由", False),
                                      "tier": None}
            else:
                # Excluded by master data: only a candidate mark (server cannot admit it; B-014 blocks publish).
                if enabled:
                    pol["enabled"] = True
                else:
                    pol.pop("enabled", None)
            _clean_policy(b.policy["characters"], cid)
        policy_fields = {k: cmd[k] for k in ("starter_eligible", "min_act", "notes") if k in cmd}
        if policy_fields:
            entry = b.policy["characters"].setdefault(cid, {})
            _policy_patch(entry, policy_fields, CHAR_POLICY)
            _clean_policy(b.policy["characters"], cid)
        changed.append(cid)
    overlay["tier_overrides"]["characters"] = dict(sorted(overrides.items(), key=lambda kv: kv[0]))
    return {"characters": changed}


def _policy_batch(b: Batch, cmd, table: str, allowed: set, known: set | None):
    ids = _ids(cmd)
    fields = {k: v for k, v in cmd.items() if k not in ("op", "ids")}
    if not fields:
        raise CommandError("没有要修改的字段")
    for item in ids:
        if known is not None and item not in known:
            raise CommandError(f"主数据里没有 {item}")
        entry = b.policy[table].setdefault(item, {})
        _policy_patch(entry, fields, allowed)
        _clean_policy(b.policy[table], item)
    return {table: ids}


def cmd_weapon_set(b, cmd):
    known = {str(w.get("id")) for w in b.master.weapons() + b.master.pending_weapons() + b.master.excluded_weapons()}
    return _policy_batch(b, cmd, "weapons", WEAPON_POLICY, known if known else None)


def cmd_soul_set(b, cmd):
    souls = b.master.souls or {}
    known = {str(s.get("ability_soul_id")) for s in souls.get("souls") or []} | \
        {str(s.get("soul_id")) for s in souls.get("excluded_soul_weapons") or []}
    return _policy_batch(b, cmd, "souls", SOUL_POLICY, known if known else None)


def cmd_encounter_policy(b, cmd):
    known = {str(e.get("quest_id")) for e in b.data["encounter_pool"].get("encounters") or []}
    cmd = {**cmd, "ids": cmd.get("ids") or cmd.get("quest_ids")}
    cmd.pop("quest_ids", None)
    return _policy_batch(b, cmd, "encounters", ENCOUNTER_POLICY, known)


def cmd_act_policy(b, cmd):
    act = str(cmd.get("act"))
    if act not in ("1", "2", "3"):
        raise CommandError("act 只能是 1..3")
    fields = {k: v for k, v in cmd.items() if k not in ("op", "act")}
    entry = b.policy["acts"].setdefault(act, {})
    _policy_patch(entry, fields, ACT_POLICY)
    return {"act": act}


def cmd_shop_override(b, cmd):
    kind = cmd.get("kind")
    item = cmd.get("id")
    shop = b.policy["shop"]
    fields = {k: v for k, v in cmd.items() if k not in ("op", "kind", "id")}
    if kind == "service":
        if item not in ("heal", "refresh", "upgrade_character", "upgrade_weapon", "extract_soul"):
            raise CommandError("服务只能是 heal/refresh/upgrade_character/upgrade_weapon/extract_soul")
        table = shop.setdefault("service_overrides", {})
        allowed = {"enabled", "price_override", "notes"}
    elif kind in ("character", "weapon", "relic", "soul"):
        table = shop.setdefault("item_overrides", {}).setdefault(kind, {})
        allowed = {"enabled", "price_override", "half_price_eligible", "notes"}
    else:
        raise CommandError("kind 只能是 character/weapon/relic/soul/service")
    if not isinstance(item, str) or not item:
        raise CommandError("id 必须是字符串")
    entry = table.setdefault(item, {})
    if set(fields) - allowed:
        raise CommandError("不支持的字段：" + "、".join(sorted(set(fields) - allowed)))
    for k, v in fields.items():
        if v is None:
            entry.pop(k, None)
        elif k == "price_override" and not (isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 10_000_000):
            raise CommandError("price_override 需要 0..10000000 的整数")
        elif k in ("enabled", "half_price_eligible") and not isinstance(v, bool):
            raise CommandError(f"{k} 需要布尔值")
        elif k == "notes" and not isinstance(v, str):
            raise CommandError("备注需要文本")
        else:
            entry[k] = v
    if not entry:
        table.pop(item, None)
    return {"shop": [kind, item]}


# -- relics -----------------------------------------------------------------
def _set_effects(relic: dict, effects: list):
    if not isinstance(effects, list) or not effects or len(effects) > 8:
        raise CommandError("遗物需要 1..8 个效果")
    old = relic["effects"] if isinstance(relic.get("effects"), list) else [relic.get("effect")]
    clean = []
    for j, raw in enumerate(effects):
        new = relic_effect(raw)
        prev = old[j] if j < len(old) else None
        clean.append(jsonio.same_number_shape(prev, new) if isinstance(prev, dict) and prev.get("type") == new["type"] else new)
    items = list(relic.items())
    single = "effect" in relic and len(clean) == 1
    key, value = ("effect", clean[0]) if single else ("effects", clean)
    at = next((i for i, (k, _) in enumerate(items) if k in ("effect", "effects")), None)
    items = [(k, v) for k, v in items if k not in ("effect", "effects")]
    if at is None:
        at = next((i for i, (k, _) in enumerate(items) if k == "name_key"), len(items))
    items.insert(at, (key, value))
    relic.clear()
    relic.update(items)


def _relic_texts(b: Batch, relic: dict, cmd: dict):
    locales = b.data["locales"]
    for field, lang, slot, raw_key in (("name", "zh", "name_key", "name"), ("desc", "zh", "desc_key", "desc"),
                                       ("name_en", "en", "name_key", "name_en"), ("desc_en", "en", "desc_key", "desc_en")):
        if field not in cmd:
            continue
        text = _text(cmd[field], field)
        set_locale(locales, lang, relic[slot], text)
        if lang == "zh" or raw_key in relic:
            relic[raw_key] = text


def cmd_relic_create(b: Batch, cmd):
    tpl = None
    if cmd.get("template"):
        tpl = next((t for t in templates()["relics"] if t["id"] == cmd["template"]), None)
        if tpl is None:
            raise CommandError(f"没有遗物模板 {cmd['template']}")
    rid = next_id("r", b.ws)
    name_key, desc_key = relic_keys(rid)
    rarity = cmd.get("rarity") or (tpl or {}).get("rarity") or "common"
    if rarity not in RARITIES:
        raise CommandError("rarity 只能是 common/rare/boss")
    zh_name, zh_desc = (tpl or {}).get("zh", ("新遗物", "（待写说明）"))
    effects = cmd.get("effects") or (tpl or {}).get("effects") or [{"type": "gold_on_pickup", "value": 50}]
    relic = {"relic_id": rid, "name": cmd.get("name") or zh_name, "rarity": rarity, "desc": cmd.get("desc") or zh_desc}
    if len(effects) == 1:
        relic["effect"] = effects[0]
    else:
        relic["effects"] = effects
    relic.update({"name_key": name_key, "desc_key": desc_key})
    _set_effects(relic, effects)
    b.data["relics"].append(relic)
    _relic_texts(b, relic, {"name": relic["name"], "desc": relic["desc"],
                            "name_en": cmd.get("name_en", ""), "desc_en": cmd.get("desc_en", "")})
    b.reserve("reserved_relic_ids", rid)
    return {"relic_id": rid}


def cmd_relic_update(b: Batch, cmd):
    relic = b.relic(cmd.get("relic_id"))
    if "rarity" in cmd:
        if cmd["rarity"] not in RARITIES:
            raise CommandError("rarity 只能是 common/rare/boss")
        relic["rarity"] = cmd["rarity"]
    if "effects" in cmd:
        _set_effects(relic, cmd["effects"])
    _relic_texts(b, relic, cmd)
    if "policy" in cmd:
        if not isinstance(cmd["policy"], dict):
            raise CommandError("policy 需要对象")
        entry = b.policy["relics"].setdefault(relic["relic_id"], {})
        _policy_patch(entry, cmd["policy"], RELIC_POLICY)
        _clean_policy(b.policy["relics"], relic["relic_id"])
    return {"relic_id": relic["relic_id"]}


def cmd_relic_duplicate(b: Batch, cmd):
    src = b.relic(cmd.get("relic_id"))
    locales = b.data["locales"]
    effects = copy.deepcopy(src.get("effects") if "effects" in src else [src.get("effect")])
    result = cmd_relic_create(b, {"rarity": src.get("rarity"), "effects": effects,
                                  "name": (src.get("name") or "") + "（副本）", "desc": src.get("desc") or "",
                                  "name_en": (locales.get("en") or {}).get(src.get("name_key"), ""),
                                  "desc_en": (locales.get("en") or {}).get(src.get("desc_key"), "")})
    return {**result, "from": src["relic_id"]}


def relic_references(ws: dict, rid: str) -> list[str]:
    refs = []
    for ev in ws["data"]["events"]:
        for i, opt in enumerate(ev.get("options") or []):
            for e in opt.get("effects") or []:
                value = e.get("value") if isinstance(e, dict) else None
                if isinstance(value, dict) and (value.get("relic_id") == rid or value.get("id") == rid):
                    refs.append(f"事件 {ev.get('event_id')} → 选项 {i} → {e.get('type')} → {rid}")
    if rid in ((ws["policy"]["shop"].get("item_overrides") or {}).get("relic") or {}):
        refs.append(f"商店单品覆盖 → {rid}")
    return refs


def cmd_relic_delete(b: Batch, cmd):
    rid = cmd.get("relic_id")
    relic = b.relic(rid)
    refs = relic_references(b.ws, rid)
    if refs:
        raise CommandError("遗物仍被引用，先取消引用：" + "；".join(refs))
    b.data["relics"].remove(relic)
    keys = {relic.get("name_key"), relic.get("desc_key"), *relic_keys(rid)}
    remove_locale_keys(b.data["locales"], lambda k: k in keys)
    b.policy["relics"].pop(rid, None)
    b.tombstone("relic", rid, cmd.get("reason"))
    b.reserve("reserved_relic_ids", rid)
    return {"relic_id": rid, "deleted": True}


# -- events -------------------------------------------------------------------
def _option_texts(b: Batch, ev: dict) -> list[dict]:
    loc = b.data["locales"]
    return [{"zh": (loc.get("zh") or {}).get(o.get("label_key"), o.get("label", "")),
             "en": (loc.get("en") or {}).get(o.get("label_key"), "")} for o in ev.get("options") or []]


def _relabel(b: Batch, ev: dict, texts: list[dict]):
    eid = ev["event_id"]
    for i, opt in enumerate(ev["options"]):
        opt["label_key"] = option_key(eid, i)
        opt["label"] = texts[i]["zh"]
    replace_option_keys(b.data["locales"], eid, texts)


def _option_ids(b: Batch, ev: dict) -> list[str]:
    ids = b.policy["event_option_ids"].setdefault(ev["event_id"], [])
    while len(ids) < len(ev.get("options") or []):
        oid = new_option_id()
        ids.append(oid)
        b.reserve("reserved_option_ids", oid)
    return ids


def _new_option(cmd: dict) -> tuple[dict, dict]:
    label = _text(cmd.get("label", "新选项"), "选项文本", False)
    effects = cmd.get("effects") or [{"type": "leave"}]
    if not isinstance(effects, list) or len(effects) > 8:
        raise CommandError("选项需要 1..8 个效果")
    option = {"label": label}
    req = requires_of(cmd.get("requires"))
    if req:
        option["requires"] = req
    option["effects"] = [event_effect(e) for e in effects]
    option["label_key"] = ""
    return option, {"zh": label, "en": _text(cmd.get("label_en", ""), "英文选项")}


def cmd_event_create(b: Batch, cmd):
    tpl = None
    if cmd.get("template"):
        tpl = next((t for t in templates()["events"] if t["id"] == cmd["template"]), None)
        if tpl is None:
            raise CommandError(f"没有事件模板 {cmd['template']}")
    eid = next_id("e", b.ws)
    title_key, text_key = event_keys(eid)
    zh_title, zh_text = (tpl or {}).get("zh", ("新事件", "事件叙述正文。"))
    ev = {"event_id": eid, "title": cmd.get("title") or zh_title, "text": cmd.get("text") or zh_text, "options": []}
    opts = cmd.get("options") or [{"label": o["zh"], "effects": o["effects"], "requires": o.get("requires")}
                                  for o in (tpl or {}).get("options", [])] or [{"label": "离开", "effects": [{"type": "leave"}]}]
    if len(opts) > 6:
        raise CommandError("服务端只接受 1..6 个选项")
    texts = []
    for raw in opts:
        option, text = _new_option(raw)
        ev["options"].append(option)
        texts.append(text)
    ev.update({"title_key": title_key, "text_key": text_key})
    b.data["events"].append(ev)
    loc = b.data["locales"]
    set_locale(loc, "zh", title_key, ev["title"])
    set_locale(loc, "en", title_key, _text(cmd.get("title_en", ""), "英文标题"))
    set_locale(loc, "zh", text_key, ev["text"])
    set_locale(loc, "en", text_key, _text(cmd.get("text_en", ""), "英文正文"))
    _relabel(b, ev, texts)
    _option_ids(b, ev)
    b.reserve("reserved_event_ids", eid)
    return {"event_id": eid}


def cmd_event_update(b: Batch, cmd):
    ev = b.event(cmd.get("event_id"))
    loc = b.data["locales"]
    for field, lang, slot in (("title", "zh", "title_key"), ("text", "zh", "text_key"),
                              ("title_en", "en", "title_key"), ("text_en", "en", "text_key")):
        if field in cmd:
            text = _text(cmd[field], field)
            set_locale(loc, lang, ev[slot], text)
            if lang == "zh":
                ev[field] = text
    if "policy" in cmd:
        if not isinstance(cmd["policy"], dict):
            raise CommandError("policy 需要对象")
        entry = b.policy["events"].setdefault(ev["event_id"], {})
        _policy_patch(entry, cmd["policy"], EVENT_POLICY)
        _clean_policy(b.policy["events"], ev["event_id"])
    return {"event_id": ev["event_id"]}


def _option_index(b: Batch, ev: dict, oid) -> int:
    ids = _option_ids(b, ev)
    if oid not in ids:
        raise CommandError(f"事件 {ev['event_id']} 没有选项 {oid}")
    return ids.index(oid)


def cmd_option_add(b: Batch, cmd):
    ev = b.event(cmd.get("event_id"))
    if len(ev["options"]) >= 6:
        raise CommandError("服务端只接受 1..6 个选项")
    texts = _option_texts(b, ev)
    ids = _option_ids(b, ev)
    option, text = _new_option(cmd)
    index = cmd.get("index", len(ev["options"]))
    if not isinstance(index, int) or not 0 <= index <= len(ev["options"]):
        raise CommandError("index 越界")
    ev["options"].insert(index, option)
    texts.insert(index, text)
    oid = new_option_id()
    ids.insert(index, oid)
    b.reserve("reserved_option_ids", oid)
    _relabel(b, ev, texts)
    return {"event_id": ev["event_id"], "option_id": oid}


def cmd_option_update(b: Batch, cmd):
    ev = b.event(cmd.get("event_id"))
    i = _option_index(b, ev, cmd.get("option_id"))
    texts = _option_texts(b, ev)
    opt = ev["options"][i]
    if "label" in cmd:
        texts[i]["zh"] = _text(cmd["label"], "选项文本", False)
    if "label_en" in cmd:
        texts[i]["en"] = _text(cmd["label_en"], "英文选项")
    if "effects" in cmd:
        effects = cmd["effects"]
        if not isinstance(effects, list) or not effects or len(effects) > 8:
            raise CommandError("选项需要 1..8 个效果")
        clean = []
        for j, raw in enumerate(effects):
            new = event_effect(raw)
            old = opt["effects"][j] if j < len(opt["effects"]) else None
            clean.append(jsonio.same_number_shape(old, new) if isinstance(old, dict) and old.get("type") == new["type"] else new)
        opt["effects"] = clean
    if "requires" in cmd:
        req = requires_of(cmd["requires"])
        items = [(k, v) for k, v in opt.items() if k != "requires"]
        if req or "requires" in opt:
            at = next((j for j, (k, _) in enumerate(items) if k == "effects"), len(items))
            items.insert(at, ("requires", req or {}))
        opt.clear()
        opt.update(items)
    _relabel(b, ev, texts)
    return {"event_id": ev["event_id"], "option_id": cmd.get("option_id")}


def cmd_option_delete(b: Batch, cmd):
    ev = b.event(cmd.get("event_id"))
    if len(ev["options"]) <= 1:
        raise CommandError("事件至少要有 1 个选项")
    oid = cmd.get("option_id")
    i = _option_index(b, ev, oid)
    texts = _option_texts(b, ev)
    del ev["options"][i]
    del texts[i]
    b.policy["event_option_ids"][ev["event_id"]].pop(i)
    b.tombstone("event_option", oid, cmd.get("reason") or f"{ev['event_id']} 选项删除")
    _relabel(b, ev, texts)
    return {"event_id": ev["event_id"], "option_id": oid, "deleted": True}


def cmd_option_move(b: Batch, cmd):
    ev = b.event(cmd.get("event_id"))
    oid = cmd.get("option_id")
    i = _option_index(b, ev, oid)
    to = cmd.get("to")
    if not isinstance(to, int) or not 0 <= to < len(ev["options"]):
        raise CommandError("目标位置越界")
    texts = _option_texts(b, ev)
    ids = b.policy["event_option_ids"][ev["event_id"]]
    for seq in (ev["options"], texts, ids):
        seq.insert(to, seq.pop(i))
    _relabel(b, ev, texts)
    return {"event_id": ev["event_id"], "option_id": oid, "to": to}


def cmd_event_duplicate(b: Batch, cmd):
    src = b.event(cmd.get("event_id"))
    loc = b.data["locales"]
    texts = _option_texts(b, src)
    opts = [{"label": t["zh"], "label_en": t["en"], "effects": copy.deepcopy(o["effects"]),
             "requires": copy.deepcopy(o.get("requires")) or None} for o, t in zip(src["options"], texts)]
    result = cmd_event_create(b, {"title": src["title"] + "（副本）", "text": src["text"],
                                  "title_en": (loc.get("en") or {}).get(src.get("title_key"), ""),
                                  "text_en": (loc.get("en") or {}).get(src.get("text_key"), ""), "options": opts})
    return {**result, "from": src["event_id"]}


def cmd_event_delete(b: Batch, cmd):
    eid = cmd.get("event_id")
    ev = b.event(eid)
    b.data["events"].remove(ev)
    remove_locale_keys(b.data["locales"], lambda k: k.startswith(f"rogue.event.{eid}."))
    for oid in b.policy["event_option_ids"].pop(eid, []):
        b.tombstone("event_option", oid, f"{eid} 随事件删除")
    b.policy["events"].pop(eid, None)
    b.tombstone("event", eid, cmd.get("reason"))
    b.reserve("reserved_event_ids", eid)
    return {"event_id": eid, "deleted": True}


def cmd_locale_set(b: Batch, cmd):
    key = cmd.get("key")
    if not isinstance(key, str) or not key.startswith("rogue."):
        raise CommandError("文本键必须以 rogue. 开头")
    loc = b.data["locales"]
    known = key in (loc.get("zh") or {}) or key in (loc.get("en") or {})
    if not known:
        raise CommandError(f"没有文本键 {key}（新键随遗物/事件创建自动生成）")
    for lang in ("zh", "en"):
        if lang in cmd:
            text = _text(cmd[lang], lang)
            set_locale(loc, lang, key, text)
            if lang == "zh":
                _sync_raw(b, key, text)
    return {"key": key}


def _sync_raw(b: Batch, key: str, text: str):
    """Keep the legacy zh fields (relic name/desc, event title/text/label) equal to locales.zh."""
    for r in b.data["relics"]:
        if r.get("name_key") == key:
            r["name"] = text
        if r.get("desc_key") == key:
            r["desc"] = text
    for ev in b.data["events"]:
        if ev.get("title_key") == key:
            ev["title"] = text
        if ev.get("text_key") == key:
            ev["text"] = text
        for opt in ev.get("options") or []:
            if opt.get("label_key") == key:
                opt["label"] = text


def cmd_source_relock(b: Batch, cmd):
    if b.master.tier_sha is None:
        raise CommandError("主数据不可读，不能重新锁定")
    old = {"tier": b.ws["source"]["tier_table_sha256"], "soul": b.ws["source"]["soul_catalog_sha256"]}
    b.ws["source"]["tier_table_sha256"] = b.master.tier_sha
    b.ws["source"]["soul_catalog_sha256"] = b.master.soul_sha
    b.ws["source"]["game_data_version"] = str(((b.master.tier_table or {}).get("meta") or {}).get("source_version") or "unknown")
    return {"before": old, "after": {"tier": b.master.tier_sha, "soul": b.master.soul_sha}}


HANDLERS = {
    "rules.set": cmd_rules_set,
    "character.set": cmd_character_set,
    "weapon.set": cmd_weapon_set,
    "soul.set": cmd_soul_set,
    "encounter.policy": cmd_encounter_policy,
    "act.policy": cmd_act_policy,
    "shop.override": cmd_shop_override,
    "relic.create": cmd_relic_create,
    "relic.update": cmd_relic_update,
    "relic.duplicate": cmd_relic_duplicate,
    "relic.delete": cmd_relic_delete,
    "event.create": cmd_event_create,
    "event.update": cmd_event_update,
    "event.duplicate": cmd_event_duplicate,
    "event.delete": cmd_event_delete,
    "event.option.add": cmd_option_add,
    "event.option.update": cmd_option_update,
    "event.option.delete": cmd_option_delete,
    "event.option.move": cmd_option_move,
    "locale.set": cmd_locale_set,
    "source.relock": cmd_source_relock,
}


def apply(workspace: dict, commands: list, master) -> tuple[dict, list[dict]]:
    if not isinstance(commands, list) or not commands:
        raise CommandError("commands 必须是非空列表")
    if len(commands) > 500:
        raise CommandError("一次最多 500 条命令")
    batch = Batch(workspace, master)
    for i, cmd in enumerate(commands):
        if not isinstance(cmd, dict) or cmd.get("op") not in HANDLERS:
            raise CommandError(f"第 {i + 1} 条：未知命令 {cmd.get('op') if isinstance(cmd, dict) else cmd!r}")
        try:
            batch.results.append({"op": cmd["op"], **(HANDLERS[cmd["op"]](batch, cmd) or {})})
        except CommandError as exc:
            raise CommandError(f"第 {i + 1} 条（{cmd['op']}）：{exc}") from None
    return batch.ws, batch.results
