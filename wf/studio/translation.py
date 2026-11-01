"""Attribution for displayed Chinese; source provenance is not semantic proof."""
from __future__ import annotations


def attribution(source, uncertain=False, reason="", evidence=None):
    return {"source": source, "uncertain": uncertain, "reason": reason, "evidence": evidence or []}


def glossary_attribution(entry):
    if not entry.get("official"):
        return attribution("直译", True, "工具译名，未取得对应官方中文原文")
    original = entry["official"] == entry.get("officialTemplate") and not entry.get("officialArguments")
    matched = entry.get("officialBaselineMatch")
    if matched is False:
        return attribution("人工", True, "当前 ui_string 与官方基线不一致，作者来源未核实",
                           [entry["officialKey"], *entry.get("evidence", [])])
    uncertain = matched is not True or entry.get("mappingStatus") != "as3" or "…" in entry["official"]
    label = "官方原文" if original and matched is True else "人工" if original else "ui_string 拼接"
    return attribution(label, uncertain,
                       "官方基线不可用，来源待核实" if matched is None else
                       "映射或参数仍待核实" if uncertain else "来源已定位；不代表整句技能语义验证",
                       [entry["officialKey"], *entry.get("evidence", [])])


def _field_value(source, field, official=False):
    if field["surface"] == "action_skill":
        rows = source.table("skill", official).get(field["key"], {}).get(str(field["tier"]), [])
        return rows[0][int(field["field"][1:])] if rows else None
    rows = source.table("strings", official).get(field["key"], [])
    return rows[0][0] if rows else None


def _official_custom_keys(source, cid, character):
    """Reuse wf text ownership, including code prefixes and embedded tokens."""
    from wf.balance.rows import join_leaf
    from wf.text.model import ABILITY, CHARACTER, CUSTOM, LEADER, TextWorkspace
    workspace = TextWorkspace(None)
    workspace.tables[CHARACTER] = {key: join_leaf("", rows)
                                   for key, rows in source.table("character", True).items()}
    workspace.tables[CUSTOM] = dict.fromkeys(source.table("strings", True), "")
    for logical, name, slots in ((LEADER, "leader", character[17:18]),
                                 (ABILITY, "ability", character[19:25])):
        table = source.table(name, True)
        workspace.tables[logical] = {key: join_leaf("", table[key]) for key in slots if key in table}
    return set(workspace.custom_keys(cid))


def _official_owner(source, cid, field, custom_cache):
    rows = source.table("character", True).get(cid, [])
    if not rows:
        return False
    character = rows[0]
    if field["surface"] == "action_skill":
        return len(character) > 8 and character[8] == field["key"]
    if field["surface"] == "custom_ability_string":
        if "keys" not in custom_cache:
            custom_cache["keys"] = _official_custom_keys(source, cid, character)
        return field["key"] in custom_cache["keys"]
    # A matching string key alone is insufficient: it must belong to this
    # character's official leader/ability rows, before any draft reattachment.
    keys = set()
    for table, slots in (("leader", character[17:18]), ("ability", character[19:25])):
        for key in slots:
            for row in source.table(table, True).get(key, []):
                if row:
                    keys.add("desc_override_" + row[0])
    return field["key"] in keys


def annotate_panel(source, panel):
    """原文 requires an independent baseline, character ownership and exact text."""
    fields, custom_cache = [], {}
    for field in panel["fields"]:
        original = None
        try:
            if _official_owner(source, panel.get("characterId"), field, custom_cache):
                original = _field_value(source, field, True)
        except (AttributeError, TypeError, KeyError, IndexError, OSError, ValueError):
            pass
        if original is not None and original == field["value"] and not getattr(source, "baseline_error", None):
            provenance = attribution("官方原文", evidence=[field["location"]])
        else:
            edited = field.get("original") != field["value"] or (
                field.get("base") is not None and field["base"] != field["value"])
            provenance = attribution("人工", not edited,
                "草稿人工编辑" if edited else "当前文案未匹配到官方基线，作者来源未核实")
        fields.append({**field, "translation": provenance})
    return {**panel, "fields": fields}


def annotate_catalog(source, groups, skills, skill_key, *, cid, base_source=None):
    """Catalog-derived character details use the same attribution as the text editor."""
    fields, targets = [], []
    for group in groups:
        if not group.get("rows"):
            group.pop("translation", None)
            continue
        if group["descriptionSource"] != "游戏面板覆盖文案":
            group["translation"] = attribution("直译", True, "wf_describe 数据行解析，未证明为客户端原文")
            continue
        rows = group["rows"]
        key = "desc_override_" + rows[0]["values"][0] if rows else ""
        fields.append({"surface": "desc_override", "key": key, "location": key,
                       "value": group["description"], "original": group["description"]})
        targets.append(group)
    for skill in skills:
        if not skill_key or skill_key == "(None)" or not skill.get("raw"):
            skill.pop("translation", None)
            continue
        if skill["kind"] != "main":
            skill["translation"] = attribution("人工", True, "工具整理的技能路由说明")
            continue
        fields.append({"surface": "action_skill", "key": skill_key, "tier": skill["level"], "field": "c1",
                       "location": f"action_skill.{skill['level']}.c1", "value": skill["description"],
                       "original": skill["description"]})
        targets.append(skill)
    if base_source is not None:
        for field in fields:
            try:
                field["base"] = _field_value(base_source, field)
            except (AttributeError, TypeError, KeyError, IndexError, OSError, ValueError):
                pass
    for target, field in zip(targets, annotate_panel(source, {"characterId": cid, "fields": fields})["fields"]):
        target["translation"] = field["translation"]
