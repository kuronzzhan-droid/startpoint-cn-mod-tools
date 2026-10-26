"""Local ID availability is an evidence query, never an allocation or reservation."""
import re

from .drafts import DraftError, default_root
from .id_catalog import TABLES, collect_server, collect_tables
from .id_drafts import collect_drafts

DEFAULTS = {"character": 199000, "multiball": 1990001, "weapon": 5950001,
            "soul_item": 5950001, "unique_condition": 199000,
            "string_id": "studio_1", "mana_node": 199000, "enhancement_shop": 595000101,
            "enhancement_category": 9, "exchange_category": 97, "exchange_product": 991000000}
LIMITS = {"character": 999999999, "weapon": 21474835, "mana_node": (2147483647 - 999) // 2000}


def allocate_available(kind, occupied, *, requested=None, near=1):
    """Allocate against a caller's snapshot-bound view/server/draft evidence."""
    occupied = set(map(str, occupied))
    candidate = canonical(kind, requested if requested is not None else near)
    if requested is not None and candidate in occupied:
        raise DraftError(f"{kind} ID collision: {candidate}")
    while candidate in occupied:
        candidate = canonical(kind, int(candidate) + 1)
    return candidate


def canonical(kind, value):
    if kind not in TABLES:
        raise DraftError("未知 ID kind: " + str(kind))
    value = str(value)
    if kind == "string_id":
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.:-]{0,127}", value):
            raise DraftError("string_id 需要 1–128 位字母、数字或 _ . : -")
    elif not re.fullmatch(r"[1-9][0-9]*", value) or int(value) > LIMITS.get(kind, 2147483647):
        raise DraftError(f"{kind} ID 超出合法正整数范围")
    return value


def collect_occupancy(source, drafts_root=None, server_dir=None):
    result = {kind: {} for kind in TABLES}

    def add(kind, identity, owner, source_kind, location):
        entry = {"owner": owner, "source": source_kind, "location": location}
        items = result[kind].setdefault(identity, [])
        if entry not in items:
            items.append(entry)

    try:
        collect_tables(source, add)
        collect_server(server_dir, add)
        collect_drafts(default_root() if drafts_root is None else drafts_root, add,
                       known_strings=result["string_id"], source=source)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise DraftError(f"无法完成 ID 来源查询: {exc}") from exc
    return result


def check_id(source, kind, identity, *, drafts_root=None, server_dir=None, occupancy=None):
    identity = canonical(kind, identity)
    occupied = occupancy if occupancy is not None else collect_occupancy(source, drafts_root, server_dir)
    owners = occupied[kind].get(identity, [])
    result = {"kind": kind, "id": identity, "available": not owners, "owners": owners,
              "viewVersion": source.version, "serverChecked": server_dir is not None,
              "reserved": False}
    if kind == "mana_node":
        start = int(identity) * 2000
        result["segment"] = {"characterId": identity, "start": str(start), "end": str(start + 999)}
    return result


def next_id(source, kind, near=None, *, drafts_root=None, server_dir=None):
    candidate = canonical(kind, DEFAULTS.get(kind) if near is None else near)
    occupied = collect_occupancy(source, drafts_root, server_dir)
    skipped = []
    while candidate in occupied[kind]:
        skipped.append({"id": candidate, "owners": occupied[kind][candidate]})
        if kind == "string_id":
            match = re.fullmatch(r"(.*?)([0-9]+)", candidate)
            candidate = match[1] + str(int(match[2]) + 1) if match else candidate + "_1"
        else:
            candidate = str(int(candidate) + 1)
        candidate = canonical(kind, candidate)
    return {**check_id(source, kind, candidate, server_dir=server_dir, occupancy=occupied), "skipped": skipped}
