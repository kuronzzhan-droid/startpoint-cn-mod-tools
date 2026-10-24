"""Strict public contract for the read-only gray-server reward snapshot."""
from __future__ import annotations

import json
import re
from datetime import datetime

PREFIX = "window.WF_WIKI_REWARDS="
SAFE_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
PUBLIC_ID = re.compile(r"[cw][0-9a-f]{12}\Z")
PRIVATE_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|file://|/(?:Users|home)/)")
KINDS = {"item", "equipment", "character", "beads", "mana", "exp", "degree", "unknown"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def obj(value, required, optional=()):
    require(isinstance(value, dict), "Expected an object")
    require(set(required) <= set(value) <= set(required) | set(optional), "Unexpected or missing public field")


def text(value, limit=2000, empty=False):
    require(isinstance(value, str) and (empty or bool(value)) and len(value) <= limit, "Invalid text")
    require(not PRIVATE_PATH.search(value) and "\x00" not in value, "Private path in public text")


def array(value, limit):
    require(isinstance(value, list) and len(value) <= limit, "Invalid array")


def identifier(value):
    require(isinstance(value, str) and len(value) <= 80 and SAFE_ID.fullmatch(value), "Invalid identifier")


def notes(value):
    array(value, 120)
    for note in value:
        text(note)


def date(value, nullable=True):
    if value is None and nullable:
        return
    text(value, 40)
    require("T" in value and (value.endswith("Z") or re.search(r"[+-]\d\d:\d\d$", value)), "ISO date required")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid ISO date") from exc


def rewards(value, equipment_ids=None, character_ids=None):
    array(value, 2000)
    for reward in value:
        obj(reward, {"kind", "name", "amountText"}, {"equipmentId", "characterId", "probabilityText"})
        require(reward["kind"] in KINDS, "Unknown reward kind")
        text(reward["name"], 240)
        text(reward["amountText"], 500)
        if "probabilityText" in reward:
            text(reward["probabilityText"], 800)
        require(not ("equipmentId" in reward and "characterId" in reward), "Conflicting reward links")
        for field, kind, prefix, allowed in (("equipmentId", "equipment", "w", equipment_ids),
                                             ("characterId", "character", "c", character_ids)):
            if field in reward:
                value = reward[field]
                require(reward["kind"] == kind and isinstance(value, str) and PUBLIC_ID.fullmatch(value)
                        and value.startswith(prefix), "Invalid public reward link")
                require(allowed is None or value in allowed, "Reward link absent from Wiki")


def validate_payload(payload, *, dungeon_ids=None, equipment_ids=None, character_ids=None):
    """Validate all public fields and references; never executes a script."""
    obj(payload, {"schemaVersion", "source", "dungeons", "shops"})
    require(type(payload["schemaVersion"]) is int and payload["schemaVersion"] == 1, "Unsupported schema")
    source = payload["source"]
    obj(source, {"label", "status", "checkedAt"})
    text(source["label"], 240)
    require(source["status"] == "gray-snapshot", "A real gray snapshot is required")
    date(source["checkedAt"], False)
    dungeons = payload["dungeons"]
    require(isinstance(dungeons, dict) and len(dungeons) <= 2000, "Invalid dungeon map")
    for key, dungeon in dungeons.items():
        identifier(key)
        require(dungeon_ids is None or key in dungeon_ids, "Unknown dungeon reference")
        obj(dungeon, {"quests", "shopIds", "notes"})
        notes(dungeon["notes"])
        array(dungeon["quests"], 2000)
        array(dungeon["shopIds"], 100)
        require(len(set(dungeon["shopIds"])) == len(dungeon["shopIds"]), "Duplicate shop reference")
        for shop_id in dungeon["shopIds"]:
            identifier(shop_id)
        for quest in dungeon["quests"]:
            obj(quest, {"name", "difficulty", "firstClear", "sPlus", "drops", "notes"})
            text(quest["name"], 240)
            text(quest["difficulty"], 100, True)
            notes(quest["notes"])
            for field in ("firstClear", "sPlus", "drops"):
                rewards(quest[field], equipment_ids, character_ids)
    array(payload["shops"], 2000)
    shop_map = {}
    for shop in payload["shops"]:
        obj(shop, {"id", "title", "dungeonIds", "notes", "items"})
        identifier(shop["id"])
        require(shop["id"] not in shop_map, "Duplicate shop")
        shop_map[shop["id"]] = shop
        text(shop["title"], 240)
        notes(shop["notes"])
        array(shop["dungeonIds"], 2000)
        require(len(set(shop["dungeonIds"])) == len(shop["dungeonIds"]), "Duplicate dungeon reference")
        for dungeon_id in shop["dungeonIds"]:
            require(dungeon_id in dungeons, "Shop refers to unknown dungeon")
            require(shop["id"] in dungeons[dungeon_id]["shopIds"], "Shop link is not reciprocal")
        array(shop["items"], 10000)
        for item in shop["items"]:
            obj(item, {"rewards", "costs", "stock", "availableFrom", "availableUntil", "notes"})
            for field in ("rewards", "costs"):
                rewards(item[field], equipment_ids, character_ids)
            require(item["stock"] is None or type(item["stock"]) is int and -1 <= item["stock"] <= 10**12,
                    "Invalid configured stock")
            date(item["availableFrom"])
            date(item["availableUntil"])
            notes(item["notes"])
    for key, dungeon in dungeons.items():
        for shop_id in dungeon["shopIds"]:
            require(shop_id in shop_map and key in shop_map[shop_id]["dungeonIds"], "Unknown or one-sided shop link")
    return payload


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def read_payload(path, **kwargs):
    raw = path.read_bytes()
    require(len(raw) <= 25 * 1024 * 1024, "Reward snapshot too large")
    script = raw.decode("utf-8-sig").strip()
    require(script.startswith(PREFIX) and script.endswith(";"), "Invalid reward assignment")
    payload = json.loads(script[len(PREFIX):-1], object_pairs_hook=unique_object,
                         parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON number")))
    return validate_payload(payload, **kwargs)
