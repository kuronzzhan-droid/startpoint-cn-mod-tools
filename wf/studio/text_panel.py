"""Read-only panel-text view for the studio: per-field wf text findings.

Writing still goes through ``AbilityEditor.apply`` with an ``abilityRequest``
``text`` section (wf text, both server mirrors). This module only projects the
current draft state, optionally with proposed values, and runs the same rules.
"""
from __future__ import annotations

import copy
import csv
import io
import re

from wf.text.effective import effective_rows
from wf.text.model import ABILITY, CHARACTER, CUSTOM, LEADER, cells
from wf.text.rules import check_character
from wf.text.standard import coverage, rule_catalog

# Author house rules, surfaced next to each field. They map to wf text rule ids;
# ``studio.leader-self`` is an editor-side addition (see below).
HOUSE_RULES = [
    {"id": "house.tautology", "title": "不写恒真条件",
     "requirement": "不写「生命值100%以下」这类恒真条件；删掉条件或写出真实阈值",
     "rules": ["text.tautology", "text.standard.tautology"],
     "surfaces": ["desc_override", "custom_ability_string", "action_skill"]},
    {"id": "house.leader-self", "title": "覆盖文案不写「自身为队长时」",
     "requirement": "desc_override 不写「自身为队长时」；队长槽自带语境，能力里带队长前置的效果移入队长技",
     "rules": ["text.standard.leader-slot", "text.standard.leader-relocation", "studio.leader-self"],
     "surfaces": ["desc_override"]},
    {"id": "house.skill-no-enhance", "title": "技能描述不重复强化效果",
     "requirement": "技能 c1 只写本体；强化写在队长技/能力（强化『技能名』：定性说明），技能描述不再重复",
     "rules": ["text.duplicate_enhancement", "text.enhancement_overlap", "text.standard.skill-body"],
     "surfaces": ["action_skill"]},
    {"id": "house.core-name", "title": "不用「…之核」命名",
     "requirement": "称号、技能名和引号里的名称不得采用「…之核」",
     "rules": ["text.core_name", "text.standard.skill-name"],
     "surfaces": ["desc_override", "custom_ability_string", "action_skill", "action_skill_name"]},
    {"id": "house.main-icon", "title": "主位限定行带主位图标",
     "requirement": "主位限定的槽（能力 c1≠true）每行以「 <icon id='main'>  」开头（前 1 个空格、后 2 个空格）；"
                    "不写字面「Ⓜ」",
     "rules": ["studio.main-icon"], "surfaces": ["desc_override"]},
    {"id": "house.awaken-dual", "title": "不写「X%（觉醒后 Y%）」双值",
     "requirement": "覆盖文案只写单一数值：数值两列是词条等级低/满，面板只显示当前一个值，"
                    "写「X%（觉醒后 Y%）」会前后不一致（要一致就把两列拉平）",
     "rules": ["studio.awaken-dual", "text.standard.max-level"], "surfaces": ["desc_override"]},
    {"id": "house.no-slash", "title": "不用「／」挤一行",
     "requirement": "一行写一条效果，不用「／」把两条效果挤在同一行（换行分开）",
     "rules": ["studio.no-slash"], "surfaces": ["desc_override", "custom_ability_string"]},
]

_LEADER_SELF = re.compile(r"自身为队长时")
MAIN_ICON = " <icon id='main'>  "
_ICON = re.compile(r"<icon id='main'>")
_AWAKEN_DUAL = re.compile(r"[（(]\s*觉醒后|觉醒后\s*[+＋]?\s*\d")
_SLASH = re.compile(r"[／]")


def override_slots(character, leader, ability, custom, owners=None) -> list[dict]:
    """Exact panel-override mapping (C5): the panel shows ``desc_override_<c0>`` for a slot whose
    rows carry that c0 (the client looks the key up by the row's c0), when the key exists.

    ``main``: "all" when every row of an ability slot is main-limited (c1 ≠ true, wf_describe Ⓜ),
    "some" for a mix, "none" otherwise (leader skills are never main-limited).
    """
    owners = owners or {}
    slots = []
    groups = [("leader_ability", "队长技", 0, character[17] if len(character) > 17 else "")]
    groups += [("ability", f"能力 {i}", i, key) for i, key in enumerate(character[19:25], 1)]
    for table, label, number, key in groups:
        if not key or key == "(None)":
            continue
        leaf = (leader if table == "leader_ability" else ability).get(key)
        rows = [r for r in csv.reader(io.StringIO(leaf, newline="")) if r] if isinstance(leaf, str) and leaf else []
        names = list(dict.fromkeys(r[0] for r in rows if r[0]))
        limited = sum(1 for r in rows if table == "ability" and (len(r) < 2 or r[1].strip().lower() != "true"))
        keys = ["desc_override_" + name for name in names]
        slots.append({"label": label, "table": table, "slot": number, "key": key, "names": names,
                      "overrideKeys": keys, "existing": [k for k in keys if k in custom],
                      "main": "all" if rows and limited == len(rows) else "some" if limited else "none",
                      "owners": sorted(owners.get(table, {}).get(key, ())), "rows": len(rows)})
    return slots


def slot_of(key: str, slots: list[dict]) -> dict | None:
    return next((s for s in slots if key in s["overrideKeys"]), None)


def _house_extra(rule_id, text, slot):
    """Editor-side author rules (D4) that wf text does not check yet; [] = 满足."""
    lines = [line for line in str(text).split("\n")]
    if rule_id == "house.main-icon":
        hits = []
        if "Ⓜ" in text:
            hits.append("写了字面「Ⓜ」：用 <icon id='main'>")
        for number, line in enumerate(lines, 1):
            if _ICON.search(line) and not line.startswith(MAIN_ICON):
                hits.append(f"第 {number} 行主位图标位置或空格不对（应为行首「 <icon id='main'>  」）")
        if slot and slot["main"] == "all":
            missing = [n for n, line in enumerate(lines, 1) if line.strip() and not line.startswith(MAIN_ICON)]
            if missing:
                hits.append(f"{slot['label']} 是主位限定槽：第 {'、'.join(map(str, missing))} 行缺主位图标")
        elif slot and slot["main"] == "none" and any(_ICON.search(line) for line in lines):
            hits.append(f"{slot['label']} 不是主位限定槽，却写了主位图标")
        return hits
    if rule_id == "house.awaken-dual":
        return [f"第 {n} 行写了觉醒后的第二个数值（面板只显示一个值）" for n, line in enumerate(lines, 1)
                if _AWAKEN_DUAL.search(line)]
    if rule_id == "house.no-slash":
        return [f"第 {n} 行用「／」把效果挤在一行" for n, line in enumerate(lines, 1) if _SLASH.search(line)]
    return []


def _record_tokens(leaf):
    tokens = set()
    if isinstance(leaf, str) and leaf:
        for record in csv.reader(io.StringIO(leaf, newline="")):
            tokens.update(record)
            for value in record:
                tokens.update(re.findall(r"[A-Za-z0-9_]+", value))
    return tokens


def custom_owners(workspace, keys):
    """Exactly ``[o for o in characters if key in workspace.custom_keys(o)]``.

    ``custom_keys`` matches a key either by reference (a token of the owner's
    leader/ability rows) or by ``prefix + name`` where name is the owner's code,
    skill key or a row's c0. Both imply a cheap necessary condition, so only the
    surviving candidates run the exact (slow) ``custom_keys``.
    """
    from .perf import leaf_tokens
    keys = list(keys)
    characters = workspace.table(CHARACTER)
    leader, ability = workspace.table(LEADER), workspace.table(ABILITY)
    candidates = {key: [] for key in keys}
    for owner, leaf in characters.items():
        row = cells(leaf)
        names = {row[0], row[8]}
        tokens = set()
        for table, refs in ((leader, row[17:18]), (ability, row[19:25])):
            for ref in refs:
                value = table.get(ref, "")
                if isinstance(value, str) and value:
                    found, row_names = leaf_tokens(value)  # memoized per leaf text
                    tokens |= found
                    names |= row_names
        names.discard("")
        for key in keys:
            if key in tokens or any(name in key for name in names):
                candidates[key].append(owner)
    exact = {}
    result = {}
    for key, owners in candidates.items():
        found = []
        for owner in owners:
            if owner not in exact:
                exact[owner] = set(workspace.custom_keys(owner))
            if key in exact[owner]:
                found.append(owner)
        result[key] = found
    return result


def _project(document, text, slots=None):
    """Apply proposed ``text`` sections to a copy; mirrors follow wf text sync.

    A new override (``old`` null) is accepted only for ``desc_override_<c0>`` of one of the
    character's slots (exact slot detection) — the same rule wf text applies when writing.
    """
    doc = copy.deepcopy(document)
    if not text:
        return doc
    for section in ("desc_override", "custom_ability_string"):
        for key, pair in (text.get(section) or {}).items():
            if key not in doc[section]:
                creatable = (section == "desc_override" and pair.get("old") is None
                             and slots is not None and slot_of(key, slots) is not None)
                if not creatable:
                    raise ValueError(f"{section}.{key} 不是该角色已引用的文本键")
            doc[section][key] = pair["new"]
    server_rows = [doc.get("server_character_text"), doc.get("server_character_text_rank_p5b")]

    def sync(column, value):
        doc["character_text"][str(column)] = value
        for rows in server_rows:
            if isinstance(rows, list) and rows and isinstance(rows[0], list) and len(rows[0]) > column:
                rows[0][column] = value

    for tier, pair in (text.get("action_skill") or {}).items():
        if tier not in doc["action_skill"]:
            raise ValueError(f"技能档位 {tier} 不存在")
        for field, change in pair.items():
            doc["action_skill"][tier][field] = change["new"]
            sync(2 + 2 * int(tier) + int(field[1:]), change["new"])
    for column, change in (text.get("character_text") or {}).items():
        sync(int(column), change["new"])
    return doc


def _surface_of(location):
    if location.startswith("action_skill.") and location.endswith(".c0"):
        return "action_skill_name"
    return location.split(".", 1)[0]


def _field_rules(surface, findings):
    """Panel-standard rules this field hits (C4: only hits; the 「只查列举写法」 caveat is said once)."""
    surfaces = {rule["id"]: set(rule["surfaces"]) for rule in rule_catalog()["rules"]}
    # coverage() widens action_skill to its name surface; a field is one surface.
    return [record for record in coverage([surface], findings)
            if record["state"] == "问题" and surface in surfaces[record["rule"]]]


def _standard_count(surface):
    surfaces = {rule["id"]: set(rule["surfaces"]) for rule in rule_catalog()["rules"]}
    return sum(1 for record in coverage([surface], []) if record["state"] != "不适用"
               and surface in surfaces[record["rule"]])


def _house(surface, text, findings, slot=None):
    out = []
    for rule in HOUSE_RULES:
        if surface not in rule["surfaces"]:
            continue
        hits = [f for f in findings if f["rule"] in rule["rules"]]
        if surface == "desc_override" and rule["id"] == "house.leader-self":
            matches = _LEADER_SELF.findall(text)
            if matches and not any(f["state"] == "问题" for f in hits):
                where = f"（{slot['label']}）" if slot else ""
                hits.append({"rule": "studio.leader-self", "state": "问题", "message": rule["requirement"] + where,
                             "evidence": {"matches": matches},
                             "source": "作者裁决：覆盖文案规则（编辑台按「desc_override_<槽行 c0>」精确判定槽位）"})
        for message in _house_extra(rule["id"], text, slot):
            hits.append({"rule": rule["rules"][0], "state": "问题", "message": message,
                         "source": "作者规则（编辑台检查；wf text 尚未收录）"})
        state = ("问题" if any(f["state"] == "问题" for f in hits)
                 else "待验证" if any(f["state"] == "待验证" for f in hits) else "满足")
        out.append({"id": rule["id"], "title": rule["title"], "requirement": rule["requirement"],
                    "state": state, "findings": hits})
    return out


def _findings_for(location, key, findings):
    own = [f for f in findings if f.get("location") == location]
    if location.startswith("action_skill.") and location.endswith(".c1"):
        # Cross-tier wording findings are located on the whole skill.
        own += [f for f in findings if f.get("location") == "action_skill"]
    if key:
        # Cross-field duplicate findings sit on action_skill but cite this key.
        own += [f for f in findings if f.get("location") != location
                and (f.get("evidence") or {}).get("key") == key and f["state"] != "满足"]
    return own


def _server_compare(document):
    base, rank = document.get("server_character_text"), document.get("server_character_text_rank_p5b")
    rows, source = effective_rows(base, rank)
    client = document["character_text"]
    result = []
    for column, label in ((4, "技能名 1 档"), (5, "技能文案 1 档"), (6, "技能名 2 档"), (7, "技能文案 2 档"),
                          (8, "技能名 3 档"), (9, "技能文案 3 档"), (10, "队长名")):
        client_value = client.get(str(column))
        server_value = rows[0][column] if isinstance(rows, list) and rows and len(rows[0]) > column else None
        if not client_value and not server_value:
            continue
        result.append({"column": column, "label": label, "client": client_value, "server": server_value,
                       "match": client_value == server_value})
    return {"effectiveSource": source, "rankOverridesBase": rank is not None,
            "inBase": base is not None, "inRank": rank is not None, "columns": result,
            "rule": "content-master.ts: cdnCharacterTexts = {...base, ...rankP5b}（p5b 整行覆盖 base）"}


def panel(document, *, owners, base_document=None, character=None, text=None, slots=None):
    """Build the per-field view from a wf text document (optionally projected).

    ``slots`` (:func:`override_slots`) gives the exact slot of every override key; overrides
    that no slot's row c0 names are reported as 「未挂接」.
    """
    doc = _project(document, text, slots)
    findings = check_character(doc)
    fields = []
    slots = slots or []

    def add(surface, location, key, value, **extra):
        base_value = None
        if base_document is not None:
            if surface in ("desc_override", "custom_ability_string"):
                base_value = base_document[surface].get(key)
            else:
                tier, column = extra["tier"], extra["field"]
                base_value = base_document["action_skill"].get(tier, {}).get(column)
        own = _findings_for(location, key if surface in ("desc_override", "custom_ability_string") else None, findings)
        rule_surface = "action_skill_name" if extra.get("field") == "c0" else surface
        rules = _field_rules(rule_surface, own) if surface != "custom_ability_string" else []
        slot = extra.pop("slotInfo", None)
        house = _house(rule_surface, value, own, slot)
        problems = sum(1 for h in house if h["state"] == "问题") + sum(
            1 for f in own if f["state"] == "问题" and not any(f in h["findings"] for h in house))
        fields.append({"surface": surface, "location": location, "key": key, "value": value,
                       "original": document_value(document, surface, key, extra),
                       "base": base_value, "owners": owners.get(key, []) if key else [],
                       "enhancement": surface == "custom_ability_string" and key.startswith("change_skill_"),
                       "findings": own, "rules": rules, "house": house, "problems": problems,
                       "standardChecked": _standard_count(rule_surface) if surface != "custom_ability_string" else 0,
                       **({"main": slot["main"], "slotKey": slot["key"]} if slot else {}), **extra})

    for tier, pair in sorted(doc["action_skill"].items()):
        for field in ("c0", "c1"):
            add("action_skill", f"action_skill.{tier}.{field}", doc["skill_key"], pair[field], tier=tier, field=field)
    for key, value in doc["desc_override"].items():
        slot = slot_of(key, slots)
        add("desc_override", f"desc_override.{key}", key, value,
            slot=slot["label"] if slot else "未挂接", slotInfo=slot, created=key not in document["desc_override"])
    for key, value in doc["custom_ability_string"].items():
        add("custom_ability_string", f"custom_ability_string.{key}", key, value)
    general = [f for f in findings if f["state"] != "满足"
               and f.get("rule") not in {"text.server_effective", "text.standard.coverage"}
               and not any(f is g for field in fields for g in field["findings"])]
    leader = doc["character_text"].get("10")
    present = set(doc["desc_override"])
    return {"characterId": doc["character_id"], "skillKey": doc["skill_key"], "snapshot": document["snapshot_sha256"],
            "skillOwners": owners.get(doc["skill_key"], []),
            "leaderName": {"characterText": leader, "character": character[18] if character else None},
            "fields": fields, "general": general, "server": _server_compare(doc),
            "slots": [{**s, "existing": [k for k in s["overrideKeys"] if k in present]} for s in slots],
            "houseRules": [{k: v for k, v in r.items() if k != "surfaces"} for r in HOUSE_RULES],
            "standard": {"version": rule_catalog()["version"], "name": rule_catalog()["standard"],
                         "scope": rule_catalog()["scope_note"],
                         "note": "面板规范只自动检查列举出的写法：下面只列命中的条目；没命中不代表全面符合，"
                                 "语义、数值与效果保留仍需人工看"},
            "mainIcon": MAIN_ICON, "runtime": "未执行"}


def document_value(document, surface, key, extra):
    if surface in ("desc_override", "custom_ability_string"):
        return document[surface].get(key)
    return document["action_skill"].get(extra["tier"], {}).get(extra["field"])
