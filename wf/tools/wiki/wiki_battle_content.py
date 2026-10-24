"""Compile explicit, public-ID battle definitions from an exported Wiki snapshot."""
from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path

from wf_wiki_battle_native import cooldown_seconds, read_native_skills

THEMES = ("fire", "water", "thunder", "wind", "light", "dark")
ELEMENTS = dict(zip("火水雷风光暗", THEMES))
ORIGINS = {"新增MOD", "改版官方", "灰服独立角色资料"}
STATS = {
    "melee": dict(hp=900, basicAmount=60, skillPower=60, interval=1, range=1.1, deployCost=20),
    "ranged": dict(hp=600, basicAmount=45, skillPower=45, interval=1.1, range=3, deployCost=20),
    "healer": dict(hp=650, basicAmount=45, skillPower=40, interval=1.4, range=2.8, deployCost=20),
    "support": dict(hp=700, basicAmount=28, skillPower=40, interval=1.3, range=2.5, deployCost=20),
}
BUDGETS = {
    (20, 15): dict(damage=5, heal=.25, shield=.20, attackUp=.20, haste=.15, slow=.20),
    (24, 20): dict(damage=7, heal=.35, shield=.30, attackUp=.30, haste=.20, slow=.25),
    (30, 25): dict(damage=10, heal=.45, shield=.40, attackUp=.40, haste=.25, slow=.30),
}
EFFECTS = {"damage", "heal", "shield", "attackUp", "haste", "slow", "dot", "basicHits", "followup"}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _number(value, label, low=0, high=1_000_000):
    _require(type(value) in (int, float) and math.isfinite(value) and low <= value <= high,
             f"Invalid {label}: expected a finite number in [{low}, {high}]")
    return value


def _keys(value, allowed, required, label):
    _require(isinstance(value, dict) and set(value) <= set(allowed) and set(required) <= set(value),
             f"Invalid {label} fields")


def _text(value, label, limit=2000):
    _require(isinstance(value, str) and 0 < len(value) <= limit, f"Invalid {label}")
    return value


def _json(file):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, f"Duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(file).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def _catalog(site_root):
    text = (site_root / "data.js").read_text(encoding="utf-8-sig")
    match = re.fullmatch(r"\s*window\.WF_WIKI\s*=\s*(\{.*\})\s*;?\s*", text, re.S)
    _require(match is not None, "data.js must contain one JSON assignment")
    rows = json.loads(match[1]).get("characters")
    _require(isinstance(rows, list), "Missing public character catalog")
    result = {}
    for row in rows:
        cid = row.get("id")
        _require(isinstance(cid, str) and re.fullmatch(r"c[0-9a-f]{12}", cid), "Invalid public ID")
        _require(cid not in result, "Duplicate catalog ID")
        result[cid] = row
    return result


def _selector(value):
    _keys(value, ("team", "kind", "range", "elements", "preferBoss", "hpBelow"),
          ("team", "kind", "range"), "selector")
    _require(value["team"] in ("enemy", "ally") and value["kind"] in
             ("nearest", "lowestHp", "leader", "all", "self"), "Unsupported selector")
    _number(value["range"], "selector range", 0, 12)
    if "elements" in value:
        _require(isinstance(value["elements"], list) and value["elements"] and
                 len(value["elements"]) == len(set(value["elements"])) and
                 set(value["elements"]) <= set(THEMES), "Invalid element filter")
    if "preferBoss" in value:
        _require(type(value["preferBoss"]) is bool, "Invalid preferBoss")
    if "hpBelow" in value:
        _number(value["hpBelow"], "hpBelow", 0, 1)


def _geometry(value):
    _keys(value, ("kind", "center", "radius", "width", "length", "angle", "direction", "offsetX", "offsetY"),
          ("kind", "center"), "geometry")
    kind = value["kind"]
    _require(kind in ("single", "circle", "rect", "line", "fan", "cross", "all") and
             value["center"] in ("self", "target"), "Unsupported geometry")
    required = {"circle": ("radius",), "rect": ("width", "length"), "line": ("width", "length"),
                "fan": ("radius", "angle"), "cross": ("length", "width")}.get(kind, ())
    _require(all(key in value for key in required), "Incomplete geometry")
    for key in ("radius", "width", "length"):
        if key in value:
            _number(value[key], key, .01, 12)
    if "angle" in value:
        _number(value["angle"], "angle", 1, 360)
    for key in ("offsetX", "offsetY"):
        if key in value:
            _number(value[key], key, -7, 7)
    if "direction" in value:
        _require(value["direction"] in ("up", "down", "target"), "Invalid geometry direction")


def _effect(value, compiled):
    _keys(value, ("type", "amount", "ratio", "duration", "interval", "budgetShare",
                  "requiresCasterAlive", "hits", "maxProcs", "targetMode"), ("type",) if compiled else ("type", "budgetShare"), "effect")
    kind = value["type"]
    _require(kind in EFFECTS, "Unsupported effect")
    if "budgetShare" in value:
        _number(value["budgetShare"], "budgetShare", .000001, 1)
    for key in ("amount", "ratio", "duration", "interval"):
        if key in value:
            _number(value[key], key, .000001, 100000 if key == "amount" else 60 if key in ("duration", "interval") else 1)
    if kind in ("shield", "attackUp", "haste", "slow", "dot", "basicHits", "followup"):
        _require("duration" in value, "Timed effect requires duration")
    if kind == "dot" or kind == "heal" and "duration" in value:
        _require(value.get("targetMode") in ("attached", "area"), "Periodic effect requires explicit targetMode")
    else:
        _require("targetMode" not in value, "Unexpected targetMode on non-periodic effect")
    if "interval" in value:
        _require(kind in ("dot", "heal") and value.get("duration", 0) >= value["interval"], "Invalid tick interval")
    if "requiresCasterAlive" in value:
        _require(type(value["requiresCasterAlive"]) is bool, "Invalid effect lifetime")
    for kind_name, key, cap in (("basicHits", "hits", 6), ("followup", "maxProcs", 24)):
        if kind == kind_name:
            _require(type(value.get(key)) is int and 1 <= value[key] <= cap, f"Invalid {key}")
        elif key in value:
            raise ValueError(f"Unexpected {key}")
    if compiled:
        field = "amount" if kind in ("damage", "dot", "followup") else "ratio"
        _require(field in value, "Effect lacks compiled numeric amount")
    else:
        _require("amount" not in value and "ratio" not in value, "Source effects must use explicit shares")


def _skill(value, compiled=False):
    fields = ("name", "description", "cooldown", "phases")
    extra = ("gauge", "initial", "chargeSpeed", "refund") if compiled else ("cost",)
    _keys(value, (*fields, *extra), (*fields, "gauge" if compiled else "cost"), "skill")
    _text(value["name"], "skill name")
    _text(value["description"], "skill description")
    _number(value["cooldown"], "cooldown", .05 if compiled else 1, 500 if compiled else 60)
    if compiled:
        _require(type(value["gauge"]) is int and 1 <= value["gauge"] <= 10000, "Invalid native gauge")
        for key, limit in (("initial", 1), ("chargeSpeed", 10)):
            if key in value:
                _number(value[key], key, .000001, limit)
        expected = cooldown_seconds(value["gauge"], value.get("chargeSpeed", 0))
        _require(value["cooldown"] == expected, "Native charging duration mismatch")
        if "refund" in value:
            refund = value["refund"]
            _keys(refund, ("ratio", "ct", "limit"), ("ratio", "ct"), "refund")
            _number(refund["ratio"], "refund ratio", .000001, 1)
            _number(refund["ct"], "refund CT", 0, 3600)
            if "limit" in refund:
                _require(type(refund["limit"]) is int and 1 <= refund["limit"] <= 10000, "Invalid refund limit")
    else:
        _number(value["cost"], "cost", 1, 120)
        _require((value["cooldown"], value["cost"]) in BUDGETS, "Unsupported cost tier")
    phases = value["phases"]
    _require(isinstance(phases, list) and 1 <= len(phases) <= 32, "Invalid skill phase count")
    shares, previous_offset = [], -1
    for index, phase in enumerate(phases):
        _keys(phase, ("offset", "selector", "geometry", "effects", "requiresCasterAlive", "retarget", "requiresHit", "impactFrom", "impactMode", "refreshFrom", "hitTargetsFrom"),
              ("offset", "selector", "geometry", "effects", "requiresCasterAlive"), "phase")
        _number(phase["offset"], "offset", 0, 15)
        _require(phase["offset"] >= previous_offset, "Phases must be ordered")
        previous_offset = phase["offset"]
        _require(type(phase["requiresCasterAlive"]) is bool, "Invalid phase lifetime")
        if "retarget" in phase:
            _require(type(phase["retarget"]) is bool, "Invalid retarget")
        if "requiresHit" in phase:
            _require(type(phase["requiresHit"]) is int and 0 <= phase["requiresHit"] < index,
                     "requiresHit must reference an earlier phase")
        if "impactFrom" in phase or "impactMode" in phase:
            refs = phase.get("impactFrom")
            _require(isinstance(refs, list) and refs and all(type(i) is int and 0 <= i < index for i in refs)
                     and len(refs) == len(set(refs)) and phase.get("impactMode") in ("each", "farthest"),
                     "Invalid hit-position dependency")
        _selector(phase["selector"])
        _geometry(phase["geometry"])
        if "hitTargetsFrom" in phase:
            refs = phase["hitTargetsFrom"]
            _require(isinstance(refs, list) and refs and all(type(i) is int and 0 <= i < index for i in refs)
                     and len(refs) == len(set(refs)) and "impactFrom" not in phase and not phase.get("retarget")
                     and all(phases[i]["selector"]["team"] == phase["selector"]["team"]
                             and any(e["type"] == "damage" for e in phases[i]["effects"]) for i in refs),
                     "Invalid hit-target dependency")
        if "refreshFrom" in phase:
            ref = phase["refreshFrom"]
            _require(not compiled and type(ref) is int and 0 <= ref < index, "Invalid refresh reference")
            original = phases[ref]
            _require(phase["effects"] == [] and original["effects"] and
                     all(e["type"] in ("attackUp", "haste") or
                         e["type"] == "dot" and e.get("targetMode") == "attached"
                         and 0 <= phase["offset"] - original["offset"] < e.get("interval", 1)
                         for e in original["effects"]) and
                     phase["selector"] == original["selector"] and phase["geometry"] == original["geometry"],
                     "Invalid refresh source or target")
            continue
        _require(isinstance(phase["effects"], list) and 1 <= len(phase["effects"]) <= 6, "Invalid effects")
        for effect in phase["effects"]:
            _effect(effect, compiled)
            if "hitTargetsFrom" in phase:
                _require(effect["type"] == "dot" and effect.get("targetMode") == "attached",
                         "Hit-target dependency requires attached poison")
            shares.append(effect.get("budgetShare", 0))
    _require(sum(shares) <= 1.000001, "Skill budget is overallocated")


def _compile_skill(skill, stats):
    _skill(skill)
    result = copy.deepcopy(skill)
    budget = BUDGETS[(skill["cooldown"], skill["cost"])]
    for phase in result["phases"]:
        if "refreshFrom" in phase:
            phase["effects"] = copy.deepcopy(result["phases"][phase.pop("refreshFrom")]["effects"])
            continue
        area = phase["geometry"]["kind"] != "single" or phase["selector"]["kind"] == "all"
        for effect in phase["effects"]:
            kind, share = effect["type"], effect["budgetShare"]
            if kind in ("damage", "dot", "followup"):
                amount = stats["skillPower"] * budget["damage"] * share
                effect["amount"] = round(amount * (.65 if area else 1) /
                                         (effect["maxProcs"] if kind == "followup" else 1), 6)
            else:
                ratio = budget["attackUp" if kind == "basicHits" else kind] * share
                effect["ratio"] = round(ratio * (.65 if area and kind in ("heal", "shield") else 1), 6)
            del effect["budgetShare"]
    return result


def _url(value, site_root=None, kind="image"):
    _require(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_./-]+", value) and
             value.startswith("media/") and all(part not in ("", ".", "..") for part in value.split("/")),
             "Media URL must stay inside this site")
    extensions = (".mp3",) if kind == "audio" else (".webp", ".png", ".jpg", ".jpeg", ".gif")
    _require(Path(value).suffix in extensions, "Media URL has the wrong file type")
    if site_root is not None:
        _require((site_root / value).resolve().is_relative_to(site_root.resolve()), "Media path escapes site root")
    return value


def _image(value, site_root=None, depth=0):
    _require(depth < 2, "Nested posters are not supported")
    _keys(value, ("url", "width", "height", "anchorX", "anchorY", "duration", "animated", "poster"),
          ("url", "width", "height", "anchorX", "anchorY"), "image")
    _url(value["url"], site_root)
    for key in ("width", "height"):
        _number(value[key], key, 1, 4096)
    for key in ("anchorX", "anchorY"):
        _number(value[key], key, -4096, 8192)
    if "duration" in value:
        _number(value["duration"], "image duration", 0, 120)
    if "animated" in value:
        _require(type(value["animated"]) is bool, "Invalid animation flag")
    if "poster" in value:
        _image(value["poster"], site_root, depth + 1)


def _media(value, site_root=None):
    _keys(value, ("avatar", "actions", "voices", "missingCues", "seCues"), ("avatar", "actions", "voices", "missingCues"), "media")
    _url(value["avatar"], site_root)
    _keys(value["actions"], ("idle", "skill_ready"), ("idle", "skill_ready"), "actions")
    for image in value["actions"].values():
        _image(image, site_root)
    _keys(value["voices"], ("deploy", "ready", "cast", "death", "se"), ("deploy", "ready", "cast", "death", "se"), "voices")
    for pool in value["voices"].values():
        _require(isinstance(pool, list) and len(pool) <= 100, "Invalid voice pool")
        for url in pool:
            _url(url, site_root, "audio")
    _require(isinstance(value["missingCues"], list), "Invalid missing cue list")
    for cue in value["missingCues"]:
        _text(cue, "missing cue")
    if "seCues" in value:
        _keys(value["seCues"], ("deploy", "cast", "attack", "death"), (), "SE cues")
        for pool in value["seCues"].values():
            _require(isinstance(pool, list) and len(pool) <= 100, "Invalid SE cue pool")
            for url in pool:
                _url(url, site_root, "audio")


def validate_content(value):
    """Reject unknown executable/configuration fields and invalid runtime values."""
    _keys(value, ("schema", "characters", "stages", "endless", "media", "coffin"),
          ("schema", "characters", "stages", "endless", "media", "coffin"), "content")
    _require(type(value["schema"]) is int and value["schema"] == 1, "Unsupported content schema")
    chars = value["characters"]
    _require(isinstance(chars, dict) and chars, "Empty roster")
    for cid, char in chars.items():
        _keys(char, ("id", "name", "title", "theme", "aliases", "element", "role", "stats", "skill", "tag"),
              ("id", "name", "title", "theme", "aliases", "element", "role", "stats", "skill"), "character")
        _require(re.fullmatch(r"c[0-9a-f]{12}", cid) and char["id"] == cid, "Invalid character ID")
        for key in ("name", "title", "theme"):
            _text(char[key], key)
        _require(isinstance(char["aliases"], list) and all(isinstance(x, str) for x in char["aliases"]), "Invalid aliases")
        _require(char["role"] in STATS and char["element"] in THEMES, "Invalid role or element")
        _require(char.get("tag", "MOD") in ("MOD", "MOD改"), "Invalid character badge")
        _keys(char["stats"], STATS["melee"], STATS["melee"], "stats")
        for key, number in char["stats"].items():
            _number(number, key, .001)
        _skill(char["skill"], compiled=True)
    stages = value["stages"]
    _require(isinstance(stages, list) and len(stages) == 6, "Expected six stages")
    _require(len({s.get("id") for s in stages}) == 6, "Duplicate stage ID")
    for index, stage in enumerate(stages):
        _keys(stage, ("id", "name", "bossId", "theme", "difficulty"), ("id", "name", "bossId", "theme", "difficulty"), "stage")
        _text(stage["id"], "stage ID")
        _text(stage["name"], "stage name")
        _require(stage["bossId"] in chars and stage["theme"] == THEMES[index] and
                 chars[stage["bossId"]]["element"] == stage["theme"], "Invalid stage boss or theme")
        _number(stage["difficulty"], "difficulty", 1, 10)
    _keys(value["endless"], ("hpBase", "attackBase", "vanguardHp", "vanguardAttack"),
          ("hpBase", "attackBase", "vanguardHp", "vanguardAttack"), "endless")
    for number in value["endless"].values():
        _number(number, "endless base", 1)
    _require(isinstance(value["media"], dict) and set(value["media"]) == set(chars), "Media roster mismatch")
    for media in value["media"].values():
        _media(media)
    _image(value["coffin"])


def build_content(site_root: Path, definitions_root: Path, media_evidence: dict) -> dict:
    """Read a frozen public JSON assignment; never evaluate JS or original skill DSL."""
    site_root, definitions_root = Path(site_root), Path(definitions_root)
    catalog = _catalog(site_root)
    allowed = {cid for cid, row in catalog.items() if row.get("origin") in ORIGINS}
    native = read_native_skills(site_root, sorted(allowed))
    characters = {}
    for theme in THEMES:
        document = _json(definitions_root / f"characters-{theme}.json")
        _keys(document, ("characters",), ("characters",), "definitions")
        _require(isinstance(document["characters"], list), "Invalid definitions list")
        for row in document["characters"]:
            _keys(row, ("id", "role", "skill", "sourceSkill", "sourceExcerpt"),
                  ("id", "role", "skill", "sourceSkill", "sourceExcerpt"), "definition")
            cid = row["id"]
            _require(cid in allowed and cid not in characters, "Unknown, official or duplicate character")
            meta = catalog[cid]
            _require(row["role"] in STATS and ELEMENTS.get(meta.get("element")) == theme, "Role or file element mismatch")
            _text(row["sourceSkill"], "source skill")
            _text(row["sourceExcerpt"], "source excerpt")
            stats = copy.deepcopy(STATS[row["role"]])
            skill = _compile_skill(row["skill"], stats)
            del skill["cost"]
            skill.update(native[cid])
            characters[cid] = {"id": cid, **{key: meta.get(key, "") for key in ("name", "title", "theme")},
                               "aliases": meta.get("aliases", []), "element": theme, "role": row["role"],
                               "tag": "MOD改" if meta.get("origin") == "改版官方" else "MOD",
                               "stats": stats, "skill": skill}
    _require(set(characters) == allowed, "Definitions must cover the complete public MOD roster")
    stages = _json(definitions_root / "stages.json")
    _keys(stages, ("stages", "endless"), ("stages", "endless"), "stages document")
    result = {"schema": 1, "characters": characters, **stages,
              "media": copy.deepcopy(media_evidence.get("media")), "coffin": copy.deepcopy(media_evidence.get("coffin"))}
    validate_content(result)
    for media in result["media"].values():
        _media(media, site_root)
    _image(result["coffin"], site_root)
    return result
