"""Conservative ownership derived from typed references and asserted creation."""
import csv
import io

from wf.caps.requirements import parse_table

ABILITY_TABLES = {name: f"master/{'skill' if name == 'action_skill' else 'ability'}/{name}.orderedmap"
                  for name in ("ability", "leader_ability", "action_skill")}
CUSTOM = "master/string/custom_ability_string.orderedmap"
EQUIPMENT = "master/item/equipment.orderedmap"
ITEM = "master/item/item.orderedmap"


def table(view, logical):
    try:
        return parse_table(view.read_raw(logical)[0], logical)
    except (FileNotFoundError, KeyError):
        return {}


def rows(value):
    return list(csv.reader(io.StringIO(value, newline=""), strict=True)) if isinstance(value, str) else []


def ability_evidence(owner, view, changes):
    if owner.kind != "character":
        return
    tables = {logical: table(view, logical) for logical in ABILITY_TABLES.values()}
    # New keys must have asserted creation data and be absent from the baseline.
    # Attaching an existing or shared key is not an ownership declaration.
    requests = [request for change in changes if change.get("kind") == "ability_edit"
                for request in change.get("params", {}).get("requests", [])]
    for request in requests:
        for op in request.get("operations", []):
            logical, key = ABILITY_TABLES.get(op.get("table")), op.get("key")
            if (op.get("op") != "attach_key" or logical is None
                    or op.get("character", owner.identity) != owner.identity
                    or not ("rows" in op or "levels" in op) or key in tables[logical]
                    or owner.references.get((logical, key))):
                continue
            owner.explicit[logical].add(key)
            owner.references[logical, key].add(owner.identity)
            if "rows" in op:
                # Only c0 is needed for override ownership; no table replay here.
                names = [cell["new"] for row in op["rows"] for cell in row
                         if cell.get("column") in (0, "c0") and isinstance(cell.get("new"), str)]
                text = io.StringIO(newline="")
                csv.writer(text).writerows([name] for name in names)
                tables[logical][key] = text.getvalue()
    overrides = {}
    for (logical, key), owners in list(owner.references.items()):
        if logical not in tables or logical == ABILITY_TABLES["action_skill"]:
            continue
        for row in rows(tables[logical].get(key)):
            if row and row[0]:
                overrides.setdefault("desc_override_" + row[0], set()).update(owners)
    for key, owners in overrides.items():
        owner.references[CUSTOM, key].update(owners)


def weapon_icon_evidence(owner, view, changes):
    equipment = table(view, EQUIPMENT)
    souls = {}
    for wid, value in equipment.items():
        parsed = rows(value)
        if parsed and len(parsed[0]) > 10 and parsed[0][10] not in {"", "0", "(None)"}:
            souls.setdefault(parsed[0][10], set()).add(wid)
    for soul, owners in souls.items():
        if owner.identity in owners and owner.kind == "weapon":
            owner.references[ITEM, soul].update(owners)
    for change in changes:
        for request in change.get("params", {}).get("requests", []):
            spec = request.get("weapon", {})
            if request.get("operation") == "weapon_icon" and spec.get("kind") == "material":
                # Arbitrary item_id selects an edit target, not ownership.
                if spec.get("item_id"):
                    owner.unknown[ITEM].add(str(spec["item_id"]))
