"""Conservative native charging metadata; never execute game or public JS code."""
from __future__ import annotations

import hashlib
import json
import math
import re
from fractions import Fraction
from pathlib import Path

POINTS_PER_SECOND = 20
TICKS_PER_SECOND = 20
PERCENT = r"([\d.]+)(?:%→([\d.]+))?%"
INITIAL = re.compile(r"自身 技能槽 " + PERCENT)
SPEED = re.compile(r"自身 技能槽充能 " + PERCENT)
REFUND = re.compile(r"技能发动≥1(?:\(限(\d+)次\))?(?:\(CT([\d.]+)秒\))? → 自身 技能槽 " + PERCENT)


def _require(condition, message):
    if not condition:
        raise ValueError("Native charge: " + message)


def _json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=unique)


def _ratio(first, last=None):
    value = float(last or first) / 100
    _require(math.isfinite(value) and 0 <= value <= 10, "invalid percentage")
    return value


def _supported_restrictions(value):
    return (isinstance(value, dict) and value.get("operator") == "AND"
            and isinstance(value.get("items"), list)
            and all(isinstance(item, dict) and item.get("kind") == "main" for item in value["items"]))


def cooldown_seconds(gauge, speed=0):
    ticks = math.ceil(Fraction(gauge * TICKS_PER_SECOND, POINTS_PER_SECOND) / (1 + Fraction(str(speed))))
    value = ticks / TICKS_PER_SECOND
    return int(value) if value.is_integer() else value


def charge_metadata(detail):
    """Return runtime fields plus a build-only audit of included/excluded rows.

    This game treats every deployed unit as a main unit. Only full-line native
    descriptions and empty/main-only AND restrictions are supported. The source
    contains other battle engines' events; none become unconditional bonuses.
    """
    main = [skill for skill in detail.get("skills", []) if skill.get("kind") == "main"]
    _require(main and all(re.fullmatch(r"[1-9]\d*", str(s.get("level", ""))) for s in main),
             "missing or invalid main skill level")
    top = max(int(s["level"]) for s in main)
    selected = [s for s in main if int(s["level"]) == top]
    _require(len(selected) == 1, "ambiguous highest main skill")
    gauge = selected[0].get("gauge")
    _require(type(gauge) is int and 1 <= gauge <= 10000, "invalid native gauge")
    initial, speed, refund, audit = 0, 0, None, []
    for group in [detail.get("leader", {}), *detail.get("abilities", [])]:
        for row in group.get("rows", []):
            description = row.get("description", "")
            if not re.search("技能槽|充能|技能能量", description):
                continue
            record = {"ability": group.get("name", ""), "index": row.get("index"),
                      "description": description, "adopted": None,
                      "reason": "unsupported condition, target, trigger or second gauge"}
            audit.append(record)
            if group is detail.get("leader") or not _supported_restrictions(row.get("restrictions")):
                record["reason"] = "leader or unsupported restrictions"
                continue
            if match := INITIAL.fullmatch(description):
                initial += _ratio(*match.groups())
                record.update(adopted="initial", reason="exact self opening gauge; first deployment only")
            elif match := SPEED.fullmatch(description):
                speed += _ratio(*match.groups())
                record.update(adopted="chargeSpeed", reason="exact self passive charging rate")
            elif match := REFUND.fullmatch(description):
                _require(refund is None, "multiple refund rules need separate semantics")
                limit, ct, first, last = match.groups()
                refund = {"ratio": _ratio(first, last), "ct": float(ct or 0)}
                _require(math.isfinite(refund["ct"]) and 0 <= refund["ct"] <= 3600,
                         "invalid refund CT")
                if refund["ct"].is_integer():
                    refund["ct"] = int(refund["ct"])
                if limit:
                    refund["limit"] = int(limit)
                    _require(refund["limit"] > 0, "invalid refund limit")
                record.update(adopted="refund", reason="exact self cast refund; retain CT and limit")
    _require(speed <= 10, "charging rate outside supported range")
    speed = round(speed, 6)
    result = {"gauge": gauge, "cooldown": cooldown_seconds(gauge, speed)}
    if initial:
        result["initial"] = min(1, round(initial, 6))
    if speed:
        result["chargeSpeed"] = round(speed, 6)
    if refund and refund["ratio"]:
        result["refund"] = refund
    return result, audit


def read_native_skills(site_root, character_ids):
    """Verify manifest identity/hash and parse the existing frozen JSON chunks."""
    site = Path(site_root).resolve()
    match = re.fullmatch(r"\s*window\.WF_WIKI\s*=\s*(\{.*\})\s*;?\s*",
                         (site / "data.js").read_text(encoding="utf-8-sig"), re.S)
    _require(match is not None, "invalid public catalog assignment")
    chunks = _json(match[1]).get("dataManifest", {}).get("chunks", {})
    result = {}
    for cid in character_ids:
        _require(isinstance(cid, str) and re.fullmatch(r"c[0-9a-f]{12}", cid), "invalid public ID")
        entry = chunks.get("character:" + cid, {})
        url = entry.get("url", "")
        _require(isinstance(url, str) and re.fullmatch(r"data/character-" + cid + r"-[0-9a-f]{16}\.js", url),
                 "missing or invalid frozen character path")
        path = site / url
        _require(path.resolve().is_relative_to(site) and not path.is_symlink(), "character path escapes site")
        raw = path.read_bytes()
        _require(len(raw) == entry.get("bytes") and hashlib.sha256(raw).hexdigest() == entry.get("sha256"),
                 "frozen character snapshot hash mismatch")
        pattern = (r"\s*window\.WF_WIKI_CHUNKS\s*=\s*window\.WF_WIKI_CHUNKS\s*\|\|\s*\{\}\s*;\s*"
                   r'window\.WF_WIKI_CHUNKS\["character:' + cid + r'"\]\s*=\s*(\{.*\})\s*;?\s*')
        match = re.fullmatch(pattern, raw.decode("utf-8-sig"), re.S)
        _require(match is not None, "invalid frozen character JSON assignment")
        detail = _json(match[1])
        _require(detail.get("id") == cid, "character identity mismatch")
        result[cid] = charge_metadata(detail)[0]
    return result
