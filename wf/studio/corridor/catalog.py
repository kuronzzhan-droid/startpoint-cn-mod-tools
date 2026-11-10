"""Read-only master data (full tier_table + soul catalog) and the derived pool view.

The pool view replays what the trial server does at load time (rogue-rules-v3f.js applyPool and
rogue-start-packs-v2.js), so the editor shows the real effective tier, pool membership, starter
eligibility and earliest act for every character.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

from . import jsonio
from .effects import ELEMENT_NAMES

CHAR_CATEGORIES = ("common", "rare", "legendary", "enhanced")
WEAPON_CATEGORIES = ("common", "rare", "epic", "legendary")
CHAR_TIER_NAMES = {1: "普通", 2: "稀有", 3: "传说", 4: "强化传说"}
WEAPON_TIER_NAMES = {1: "普通", 2: "稀有", 3: "史诗", 4: "传说"}


@dataclass
class Master:
    tier_raw: bytes | None
    soul_raw: bytes | None
    tier_table: dict | None = None
    souls: dict | None = None
    error: list[str] = field(default_factory=list)

    @property
    def tier_sha(self):
        return jsonio.sha256(self.tier_raw) if self.tier_raw is not None else None

    @property
    def soul_sha(self):
        return jsonio.sha256(self.soul_raw) if self.soul_raw is not None else None

    def characters(self):
        return (self.tier_table or {}).get("characters", [])

    def excluded_characters(self):
        return (self.tier_table or {}).get("excluded_characters", [])

    def weapons(self):
        return (self.tier_table or {}).get("weapons", [])

    def pending_weapons(self):
        return (self.tier_table or {}).get("weapons_pending_element_policy", [])

    def excluded_weapons(self):
        return (self.tier_table or {}).get("excluded_weapons", [])

    def soul_list(self):
        return (self.souls or {}).get("souls", [])


_cache: dict[tuple, Master] = {}
_lock = threading.Lock()


def load_master(tier_path: Path, soul_path: Path) -> Master:
    """Parse once per (path, size, mtime); hashes always come from the bytes."""
    def stamp(p):
        try:
            st = p.stat()
            return (str(p), st.st_size, st.st_mtime_ns)
        except OSError:
            return (str(p), None, None)
    key = (stamp(tier_path), stamp(soul_path))
    with _lock:
        if key in _cache:
            return _cache[key]
    tier_raw = tier_path.read_bytes() if tier_path.is_file() else None
    soul_raw = soul_path.read_bytes() if soul_path.is_file() else None
    master = Master(tier_raw, soul_raw)
    if tier_raw is None:
        master.error.append("tier_table.json 不存在")
    else:
        try:
            master.tier_table = jsonio.parse(tier_raw)
        except ValueError as exc:  # a truncated sample must never pass as the full table
            master.error.append(f"tier_table.json 不是合法 JSON：{exc}")
    if soul_raw is None:
        master.error.append("rules_v3_metadata.json（魂珠目录）不存在")
    else:
        try:
            master.souls = jsonio.parse(soul_raw)
        except ValueError as exc:
            master.error.append(f"rules_v3_metadata.json 不是合法 JSON：{exc}")
    tt = master.tier_table
    if tt is not None and (tt.get("schema_version") != 2 or not isinstance(tt.get("characters"), list)
                           or not isinstance(tt.get("weapons"), list)):
        master.error.append("tier_table.json 不是 schema_version=2 的完整分档表")
    sc = master.souls
    if sc is not None and (sc.get("schema_version") != 3 or not isinstance(sc.get("souls"), list)):
        master.error.append("rules_v3_metadata.json 不是 schema_version=3 的魂珠目录")
    with _lock:
        _cache.clear()
        _cache[key] = master
    return master


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def character_pool(master: Master, rules: dict, overlay: dict, policy: dict) -> list[dict]:
    """Every master character (admitted + excluded) with the server's effective pool state."""
    v3f = (rules.get("v3f") or {})
    bp_cfg = v3f.get("boss_playable") or {}
    bp_enabled = bp_cfg.get("enabled", True) is not False
    min_act = bp_cfg.get("min_act", 2)
    prices = ((rules.get("shop") or {}).get("character_prices") or {})
    overrides = ((overlay.get("tier_overrides") or {}).get("characters") or {})
    boss_list = {int(c["id"]): c for c in ((overlay.get("boss_playable") or {}).get("characters") or [])
                 if isinstance(c, dict) and _int(c.get("id"))}
    pol = policy.get("characters") or {}
    out = []

    def base(row, admitted):
        cid = str(row.get("id"))
        return {"id": cid, "name": row.get("name"), "code": row.get("code"), "element": row.get("element"),
                "element_name": ELEMENT_NAMES.get(row.get("element"), "无"), "rarity": row.get("rarity"),
                "official": row.get("official"), "source_tier": row.get("tier"), "rule_tier": row.get("rule_tier"),
                "category": row.get("category"), "pool_check_ok": bool((row.get("pool_check") or {}).get("ok")),
                "pool_check_reasons": list((row.get("pool_check") or {}).get("reasons") or []),
                "first_seen": row.get("first_seen"), "is_new": row.get("is_new"), "release_date": row.get("release_date"),
                "starter_role": ((row.get("starter_profile") or {}).get("role")), "admitted": admitted}

    excluded = {str(r.get("id")): r for r in master.excluded_characters()}
    for row in master.characters():
        item = base(row, True)
        ov = overrides.get(item["id"])
        if ov is not None and ov.get("tier") is None:
            item.update(in_pool=False, effective_tier=None, override="disabled", boss_playable=False)
        else:
            tier = ov.get("tier") if ov else row.get("tier")
            item.update(in_pool=True, effective_tier=tier, override="tier" if ov and tier != row.get("tier") else None,
                        boss_playable=_int(item["id"]) in boss_list)
        item["override_reason"] = (ov or {}).get("reason")
        out.append(item)
    for cid, row in excluded.items():
        item = base(row, False)
        ov = overrides.get(cid)
        entry = boss_list.get(_int(cid))
        reasons = item["pool_check_reasons"]
        if entry is not None:
            blocked = ov is not None and ov.get("tier") is None
            allowed = set(entry.get("previous_exclusion") or [])
            stale = [r for r in reasons if r not in allowed]
            ok = bp_enabled and not blocked and not stale
            item.update(in_pool=ok, effective_tier=4 if ok else None, boss_playable=True,
                        override="disabled" if blocked else None, boss_playable_stale=stale,
                        excluded_reason=None if ok else ("已在叠加层禁用" if blocked else
                                                         ("v3f.boss_playable.enabled=false" if not bp_enabled else "；".join(stale))))
        else:
            item.update(in_pool=False, effective_tier=None, boss_playable=False, override=None,
                        excluded_reason="；".join(reasons) or "tier_table 排除")
        item["override_reason"] = (ov or {}).get("reason")
        out.append(item)
    for item in out:
        p = pol.get(item["id"]) or {}
        tier = item["effective_tier"]
        derived_starter = bool(item["in_pool"] and tier is not None and tier <= 3 and not item["boss_playable"])
        item["starter_derived"] = derived_starter
        item["starter_eligible"] = derived_starter and p.get("starter_eligible", True) is not False
        item["min_act_derived"] = (min_act if item["boss_playable"] else 1) if item["in_pool"] else None
        item["min_act"] = p.get("min_act", item["min_act_derived"])
        item["shop_price"] = prices.get(str(tier)) if tier else None
        item["policy"] = p
        item["tier_name"] = CHAR_TIER_NAMES.get(tier) if tier else None
    out.sort(key=lambda c: (_int(c["id"]) or 0))
    return out


def weapon_pool(master: Master, rules: dict, policy: dict) -> list[dict]:
    prices = ((rules.get("shop") or {}).get("weapon_prices") or {})
    souls = master.souls or {}
    to_soul = souls.get("equipment_to_soul") or {}
    no_soul = {str(x.get("equipment_id")): x.get("reason") for x in souls.get("excluded_soul_weapons") or []}
    pol = policy.get("weapons") or {}
    out = []
    for group, rows in (("pool", master.weapons()), ("pending_element", master.pending_weapons()),
                        ("excluded", master.excluded_weapons())):
        for row in rows:
            wid = str(row.get("id"))
            p = pol.get(wid) or {}
            tier = row.get("tier")
            in_pool = group == "pool"
            item = {"id": wid, "name": row.get("name"), "code": row.get("code"), "element": row.get("element"),
                    "element_name": ELEMENT_NAMES.get(row.get("element"), "通用/待定"), "rarity": row.get("rarity"),
                    "official": row.get("official"), "source_tier": tier, "category": row.get("category"),
                    "tier_name": WEAPON_TIER_NAMES.get(tier), "group": group, "in_pool": in_pool,
                    "level_min": row.get("level_min"), "level_max": row.get("level_max"),
                    "awakening_max": row.get("awakening_max"), "enhancement_cap": row.get("enhancement_cap"),
                    "pool_check_ok": bool((row.get("pool_check") or {}).get("ok")),
                    "pool_check_reasons": list((row.get("pool_check") or {}).get("reasons") or []),
                    "soul_id": to_soul.get(wid), "soul_excluded_reason": no_soul.get(wid),
                    "starter_derived": in_pool and tier is not None and tier <= 2,
                    "shop_price": prices.get(str(tier)) if in_pool and tier else None, "policy": p}
            if group == "pending_element":
                item["excluded_reason"] = "通用/未分类属性：属性政策未定，不入池"
            elif group == "excluded":
                item["excluded_reason"] = "；".join(item["pool_check_reasons"]) or "tier_table 排除"
            out.append(item)
    out.sort(key=lambda w: (_int(w["id"]) or 0))
    return out


def soul_pool(master: Master, policy: dict) -> list[dict]:
    pol = policy.get("souls") or {}
    out = []
    for s in master.soul_list():
        sid = str(s.get("ability_soul_id"))
        out.append({"id": sid, "name": s.get("name"), "element": s.get("element"),
                    "element_name": ELEMENT_NAMES.get(s.get("element"), "通用"),
                    "source_equipment_ids": [str(x) for x in s.get("source_equipment_ids") or []],
                    "level_max": s.get("level_max"), "in_pool": True, "policy": pol.get(sid) or {}})
    for x in (master.souls or {}).get("excluded_soul_weapons") or []:
        out.append({"id": str(x.get("soul_id")), "name": None, "element": None, "element_name": "—",
                    "source_equipment_ids": [str(x.get("equipment_id"))], "level_max": None, "in_pool": False,
                    "excluded_reason": x.get("reason"), "policy": pol.get(str(x.get("soul_id"))) or {}})
    out.sort(key=lambda s: (_int(s["id"]) or 0))
    return out


def filter_page(items: list[dict], query: dict, fields=("id", "name", "code")) -> dict:
    """Server-side search/filter/sort/paging; ids stay strings."""
    def arg(name, default=""):
        return (query.get(name) or [default])[0]
    text = arg("q").strip().lower()
    element, tier, status = arg("element"), arg("tier"), arg("status")
    result = items
    if text:
        terms = text.split()
        result = [i for i in result if all(any(t in str(i.get(f) or "").lower() for f in fields) for t in terms)]
    if element:
        result = [i for i in result if str(i.get("element")) == element]
    if tier:
        result = [i for i in result if str(i.get("effective_tier", i.get("source_tier"))) == tier]
    if status:
        checks = {"in_pool": lambda i: i.get("in_pool"), "excluded": lambda i: not i.get("in_pool"),
                  "boss_playable": lambda i: i.get("boss_playable"), "override": lambda i: i.get("override"),
                  "starter": lambda i: i.get("starter_eligible", i.get("starter_derived")),
                  "policy": lambda i: bool({k for k in (i.get("policy") or {}) if k != "notes"})}
        check = checks.get(status)
        if check:
            result = [i for i in result if check(i)]
    try:
        page = max(1, int(arg("page", "1")))
        size = max(1, min(500, int(arg("size", "100"))))
    except ValueError:
        page, size = 1, 100
    total = len(result)
    return {"total": total, "page": page, "size": size, "items": result[(page - 1) * size: page * size]}
