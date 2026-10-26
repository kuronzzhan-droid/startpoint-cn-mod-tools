"""Official-only skill donors, independent of the editable patch-chain view."""
from __future__ import annotations

import copy
import hashlib
import zlib
from urllib.parse import quote

import wf_dsl

from .skill_template_core import damage_nodes, effect_families, effect_paths
from .skill_template_validation import validate_tree


class OfficialSource:
    """Adapter for asset tools: every read explicitly requests the official archive."""
    def __init__(self, source):
        self.source = source

    def raw(self, logical):
        return self.source.raw(logical, official=True)

    def table(self, name):
        return self.source.table(name, official=True)


def _skills(source):
    skills = source.table("skill", official=True)
    if not skills:
        raise ValueError("官方 action_skill 基线不可用；不能用当前改版视图冒充官方母本")
    return skills


def resolve_key(source, selection):
    """Resolve {key} or {characterId,key?}; both always refer to official tables."""
    if isinstance(selection, str):
        key = selection
    elif isinstance(selection, dict):
        key = selection.get("key")
        if selection.get("characterId") is not None:
            cid = str(selection["characterId"])
            rows = source.table("character", official=True).get(cid)
            if not rows or len(rows[0]) <= 8:
                raise ValueError("官方角色不存在：" + cid)
            character_key = rows[0][8]
            if key and key != character_key:
                raise ValueError("source.key 与官方角色主技能不一致")
            key = character_key
    else:
        key = None
    if not isinstance(key, str) or key not in _skills(source):
        raise ValueError("官方 action_skill 键不存在：" + str(key))
    return key


def _characters(source):
    grouped = {}
    texts = source.table("text", official=True)
    for cid, rows in source.table("character", official=True).items():
        if not rows or len(rows[0]) <= 8:
            continue
        row = rows[0]
        text = texts.get(cid, [[]])
        name = text[0][0] if text and text[0] else row[0]
        grouped.setdefault(row[8], []).append({"id": cid, "code": row[0], "name": name,
                                              "element": int(row[3]) if row[3].isdigit() else None})
    return grouped


def _previews(source, paths):
    """Existing effect endpoints use current assets; advertise only identical art."""
    from .effect_render import bake, effect_files
    result = []
    for effect in paths:
        files = effect_files(effect)
        available = True
        issues = []
        for name in ("parts", "timeline", "png", "atlas"):
            logical = files[name]
            official = source.raw(logical, official=True)
            if official is None or source.raw(logical) != official:
                available = False
                break
        if available:
            try:
                metadata, png = bake(source, effect)
                available = bool(metadata.get("ok") and png and any(metadata.get("cells", [])))
                issues = list(metadata.get("issues", []))
            except (ValueError, KeyError, TypeError, OSError, IndexError, zlib.error) as exc:
                available = False
                issues = [str(exc)]
        result.append({"path": effect, "family": effect.rpartition("/")[0],
                       "previewUrl": "/api/studio/effect.png?path=" + quote(effect, safe="") if available else None,
                       "previewIssues": issues})
    return result


def template_detail(source, key, *, include_tree=True, previews=True, context_element=None):
    key = resolve_key(source, key)
    characters = _characters(source).get(key, [])
    elements = {character["element"] for character in characters}
    context_element = context_element if context_element is not None else next(iter(elements)) if len(elements) == 1 else None
    tiers = []
    for level, records in sorted(_skills(source)[key].items(), key=lambda item: int(item[0])):
        if len(records) != 1 or len(records[0]) < 8:
            raise ValueError(f"action_skill/{key}/{level}: 需要单行且含程序路径的官方档位")
        row = copy.deepcopy(records[0])
        if not row[7].startswith(("battle/action/", "character/")) or ".." in row[7] or "\\" in row[7]:
            raise ValueError(f"action_skill/{key}/{level}: 非法程序逻辑路径")
        logical = wf_dsl.dsl_logical(row[7])
        raw = source.raw(logical, official=True)
        if raw is None:
            raise ValueError("官方技能 DSL 缺失：" + logical)
        tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
        if not isinstance(tree, list) or len(tree) != 12 or tree[0] != "ActionDsl":
            raise ValueError("官方技能不是完整 ActionDsl：" + logical)
        tier = {"level": str(level), "row": row, "name": row[0], "logical": logical,
                "program": row[7], "inputSha256": hashlib.sha256(raw).hexdigest(),
                "damageNodes": damage_nodes(tree), "effectFamilies": [], "effectPaths": []}
        try:
            tier.update(effectFamilies=effect_families(tree, context_element), effectPaths=effect_paths(tree, context_element))
            tier["checks"] = validate_tree(tree)
            tier["cloneable"] = True
        except ValueError as exc:
            tier["checks"] = [{"level": "error", "code": "skill_template.dsl", "message": str(exc)}]
            tier["cloneable"] = False
        if include_tree:
            tier.update(tree=tree, raw=raw)
        tiers.append(tier)
    paths = sorted({path for tier in tiers for path in tier["effectPaths"]})
    return {"key": key, "officialOnly": True, "provenance": "official-archive",
            "characters": characters, "contextElement": context_element, "tiers": tiers,
            "cloneable": all(tier["cloneable"] for tier in tiers),
            "damageNodeCount": sum(len(tier["damageNodes"]) for tier in tiers),
            "effectFamilies": sorted({family for tier in tiers for family in tier["effectFamilies"]}),
            "effects": _previews(source, paths) if previews else []}


def public_detail(source, key):
    return template_detail(source, key, include_tree=False)


def list_templates(source, query=""):
    characters = _characters(source)
    needle = query.casefold().strip()
    result, skipped = [], []
    for key, tiers in sorted(_skills(source).items()):
        names = [records[0][0] for records in tiers.values() if records and records[0]]
        search = " ".join([key, *names, *(str(v) for c in characters.get(key, []) for v in c.values())])
        if needle and needle not in search.casefold():
            continue
        try:
            detail = template_detail(source, key, include_tree=False, previews=False)
            if not detail["cloneable"]:
                skipped.append({"key": key, "reason": "；".join(
                    f"档位 {tier['level']}: {check['message']}" for tier in detail["tiers"]
                    for check in tier["checks"] if check["level"] == "error")})
                continue
            result.append({"key": key, "characters": characters.get(key, []), "names": names,
                           "cloneable": True,
                           "tiers": [tier["level"] for tier in detail["tiers"]],
                           "damageNodeCount": detail["damageNodeCount"], "effectFamilies": detail["effectFamilies"]})
        except (ValueError, IndexError, TypeError, zlib.error) as exc:
            skipped.append({"key": key, "reason": str(exc)})
    return {"templates": result, "count": len(result), "officialOnly": True,
            "provenance": "official-archive", "unavailable": skipped}
