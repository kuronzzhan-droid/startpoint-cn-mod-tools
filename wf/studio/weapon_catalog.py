"""Quest-independent, read-only weapon catalog from native client/server rows."""
from __future__ import annotations

import json
from pathlib import Path

import wf_quest_lib as codec
from wf.boss import schema as s
from wf.boss.links import record
from wf.boss.reader import BossReader
from wf.boss.shop_model import ITEM, ENH, equipment
from wf.boss.weapon_rules import AWAKENING
from .weapon_references import references

ELEMENTS = "assets/equipment_element.json"
CUSTOM = "master/string/custom_ability_string.orderedmap"


def _number(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _server(source, target, server_dir):
    """Prefer the candidate's server overlay, then explicit local input files."""
    if callable(getattr(getattr(source, "view", None), "server", None)):
        source = source.view
    if target in getattr(source, "servers", {}):
        document = json.loads(source.servers[target])
    elif callable(getattr(source, "server", None)) and getattr(source, "server_dir", None):
        document = source.server(target, required=False)
        if source.server_original.get(target) is None:
            return {}, False
    else:
        if server_dir is None:
            return {}, False
        root = Path(server_dir).resolve()
        filename = (root / target).resolve()
        if not filename.is_relative_to(root):
            raise ValueError("server input escapes input root")
        if not filename.is_file():
            return {}, False
        document = json.loads(filename.read_bytes())
    if not isinstance(document, dict):
        raise ValueError(f"server input must be an object: {target}")
    return document, True


def _official(source):
    # Only an explicitly available official baseline proves a new MOD key.
    # A patch-layer origin or a large/reserved numeric ID is not that evidence.
    while not hasattr(source, "_official") and hasattr(source, "source"):
        source = source.source
    if not hasattr(source, "_official"):
        return None
    raw = source.raw(s.EQUIPMENT, official=True)
    if raw is None:
        return None
    baseline = codec.parse_node(raw)
    return baseline if isinstance(baseline, dict) else None


def _card(tables, identity, row, elements, official):
    element = elements.get(identity)
    if type(element) is not int or element not in range(-1, 6):
        element = None
    max_level = _number(s.cell(row, 8))
    return {"id": identity, "name": s.cell(row, 1), "rarity": _number(s.cell(row, 11)),
            "element": element, "icon": s.cell(row, 6), "soulId": s.cell(row, 10),
            "isMod": identity not in official if official is not None else None,
            "hasEnhancement": identity in tables.table(ENH),
            "hasAwakening": max_level > 1 if max_level is not None else None}


def _query(query, name, default=""):
    value = query.get(name, [default])
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], str):
        raise ValueError(f"{name} must occur once")
    return value[0]


def listing(source, query, *, server_dir=None):
    text = _query(query, "q").strip().casefold()
    filters = {}
    for name, valid in (("element", range(-1, 6)), ("rarity", range(1, 6))):
        value = _query(query, name)
        if value:
            number = _number(value)
            if number not in valid:
                raise ValueError(f"invalid {name}")
            filters[name] = number
    limit = _number(_query(query, "limit", "200"))
    if limit is None or not 1 <= limit <= 2000:
        raise ValueError("limit must be between 1 and 2000")
    tables = BossReader(source)
    elements, element_known = _server(source, ELEMENTS, server_dir)
    official, items = _official(source), []
    for path, raw in s.iter_leaves(tables.table(s.EQUIPMENT)):
        rows = s.parse_rows(raw)
        if len(path) != 1 or not rows:
            continue
        row, identity = rows[0], path[0]
        card = _card(tables, identity, row, elements, official)
        if text and not any(text in value.casefold() for value in (identity, card["name"], s.cell(row, 0))):
            continue
        if any(card[name] != value for name, value in filters.items()):
            continue
        items.append(card)
    items.sort(key=lambda item: (not item["id"].isdigit(), _number(item["id"]) or 0, item["id"]))
    notes = ["属性来自服务端 equipment_element 分类，不推导能力的属性限制。"]
    if official is None:
        notes.append("官方装备基线不可用，isMod=null；未按 ID 段猜测新增 MOD。")
    if not element_known:
        notes.append("服务端属性分类输入不可用，element=null。")
    return {"schema": "wf-studio-weapons/1", "version": tables.version, "items": items[:limit],
            "total": len(items), "count": min(len(items), limit), "limit": limit, "notes": notes}


def _curve(rows):
    points = [{"level": _number(entry["level"]), "hp": _number(s.cell(entry["row"], 0)),
               "attack": _number(s.cell(entry["row"], 1))} for entry in rows]
    points.sort(key=lambda point: point["level"] if point["level"] is not None else -1)
    return {"count": len(points), "first": points[0] if points else None,
            "last": points[-1] if points else None}


def _material_costs(tables, costs):
    result = []
    for cost in costs:
        item = record(tables, ITEM, [cost["itemId"]])
        row = item["row"] if item else []
        # Native item c2 is its display name; c3 is the image logical path.
        # c4 names an atlas member and must not be invented as a PNG path.
        name, icon = s.cell(row, 2), s.cell(row, 3)
        result.append({**cost, "name": name if s.present(name) else None,
                       "icon": icon if s.present(icon) else None})
    return result


def _awakening(tables, source, identity, row, server_dir):
    document, available = _server(source, AWAKENING, server_dir)
    material_map, rarities = document.get("materialByEquipment", {}), document.get("rarityOverrides", {})
    if not isinstance(material_map, dict) or not isinstance(rarities, dict):
        raise ValueError("awakening materialByEquipment and rarityOverrides must be objects")
    material = material_map.get(identity)
    custom = record(tables, CUSTOM, ["awakening_material_" + identity])
    # Return native applicability fields instead of inventing a default rule.
    standard = [record(tables, ITEM, path) for path, text in s.iter_leaves(tables.table(ITEM))
                if any(s.cell(r, 6) == "6" for r in s.parse_rows(text))]
    return {"maxLevel": _number(s.cell(row, 8)), "serverInputAvailable": available,
            "materialId": str(material) if material is not None else None,
            "material": record(tables, ITEM, [str(material)]) if material is not None else None,
            "clientMaterial": custom, "rarityOverride": rarities.get(identity),
            "standardMaterials": standard,
            "note": "列出本机觉醒限制、客户端覆盖与原生觉醒素材行；不证明服务端实际扣费。"}


def detail(source, identifier, *, server_dir=None):
    identity = str(identifier)
    tables = BossReader(source)
    main = record(tables, s.EQUIPMENT, [identity])
    if not main:
        return None
    elements, element_known = _server(source, ELEMENTS, server_dir)
    model = equipment(tables, identity)
    card = _card(tables, identity, main["row"], elements, _official(source))
    refs, coverage = references(tables, source, identity, card["soulId"], server_dir, _server)
    return {"schema": "wf-studio-weapon/1", "version": tables.version, **model, **card,
            "enhancement_chain": [{**stage, "costs": _material_costs(tables, stage["costs"])}
                                  for stage in model["enhancement_chain"]],
            "materials_to_120": _material_costs(tables, model["materials_to_120"]),
            "curves": {"base": _curve(model["status"]), "enhancement": _curve(model["enhancement_status"])},
            "awakening": _awakening(tables, source, identity, main["row"], server_dir),
            "references": refs, "referenceCoverage": coverage,
            "elementInputAvailable": element_known,
            "note": "读取当前客户端视图与显式本机服务端输入；引用不证明开放获取或线上运行。"}
