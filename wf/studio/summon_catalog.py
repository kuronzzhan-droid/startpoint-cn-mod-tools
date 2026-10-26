"""Read-only template cards for the summon workshop."""
from .drafts import DraftError
from .summon_tables import BALL, CHAR, CUSTOM, LEVEL, STATUS, TEXT, Tables, ball_skill, single, skill


def templates(source, q=""):
    tables, items, query = Tables(source), [], q.casefold().strip()
    for kind, logical in (("character", CHAR), ("multiball", BALL)):
        for identity, value in tables.table(logical).items():
            try:
                row = single(value, logical, 37 if kind == "character" else 28)
                element, pf_type = int(row[3]), int(row[6])
                if element not in range(6) or pf_type not in range(5):
                    continue
                if kind == "character":
                    text = tables.table(TEXT, required=False).get(identity)
                    name = single(text, TEXT)[0] if isinstance(text, str) else row[0]
                    active = skill(tables, row[8])[0]
                    image = row[0]
                    panel = identity in tables.table(STATUS)
                else:
                    text = tables.table(CUSTOM).get(row[0])
                    name = single(text, CUSTOM)[0] if isinstance(text, str) else row[0]
                    active = ball_skill(tables, row, {})[0]
                    image, panel = row[1], identity in tables.table(LEVEL)
                item = {"kind": kind, "id": identity, "name": name, "imagePrefix": image,
                        "element": element, "pfType": pf_type, "skill": active, "panelAvailable": panel}
                if not query or query in " ".join(map(str, (identity, name, image, active["name"], active["key"]))).casefold():
                    items.append(item)
            except (DraftError, ValueError, IndexError):
                continue  # A malformed donor is not advertised as cloneable.
    return {"schema": "wf-studio-summon-templates/1", "version": source.version,
            "items": items, "total": len(items), "count": len(items)}
