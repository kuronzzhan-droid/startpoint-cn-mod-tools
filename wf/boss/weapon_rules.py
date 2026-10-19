"""Profile-bound weapon kinds and source-specific awakening restrictions."""
import copy

import wf_describe
from wf.deliver.json_merge import _json_spans
from . import schema as s
from .edit_state import merge_keys
from .shop_model import SOUL, ENH_ABILITY

AWAKENING = "assets/equipment_awakening_material.json"


def check_ability_rows(table, text, *, client_profile=None, provides=None):
    import wf_client_legality
    from wf.apk.kinds import inspect_profile, inspect_provides, kind_supported
    from wf.caps.facts import table_signals
    from wf.caps.profiles import load_profiles, read_client
    if client_profile is False:
        raise ValueError("weapon kind validation requires a selected client profile or explicit provides")
    report = (inspect_provides(read_client(provides)) if provides is not None and client_profile is None
              else inspect_profile(client_profile or load_profiles()[0]))
    if report["mismatches"]:
        raise ValueError("weapon kind registry disagrees with actual SWF branches")
    logical = SOUL if table == "ability_soul" else ENH_ABILITY
    width = wf_describe.layout(table)["ncols"]
    for index, row in enumerate(s.parse_rows(text)):
        if len(row) != width:
            raise ValueError(f"{table} row {index} must have {width} columns")
        problems = wf_client_legality.client_legality_problems(table, row)
        if problems:
            raise ValueError(f"{table} row {index} kind/fields: {'; '.join(problems)}")
    for signal, value in table_signals(logical, ("candidate",), text):
        if signal == "kind_site" and not kind_supported(report, table, value["block"], value["kind"]):
            raise ValueError(f"weapon kind unsupported by real SWF: {table}.{value['block']}={value['kind']}")


def awakening_materials(state, source):
    document = state.server(AWAKENING, required=False)
    materials = document.get("materialByEquipment", {})
    if not isinstance(materials, dict):
        raise ValueError("awakening materialByEquipment must be an object")
    if (source.startswith("591") or source == "5920001") and source not in materials:
        raise ValueError(f"restricted weapon {source} lacks materialByEquipment awakening evidence")
    return materials


def clone_awakening(state, source, identity, materials):
    if source not in materials:
        return
    if identity in materials:
        raise ValueError(f"awakening materialByEquipment ID collision: {identity}")
    raw = state.servers.get(AWAKENING, state.server_original[AWAKENING])
    text, _, spans = _json_spans(raw)
    start, stop = spans["materialByEquipment"]
    changed = merge_keys(text[start:stop].encode("utf-8"), {identity: copy.deepcopy(materials[source])})
    state.servers[AWAKENING] = (text[:start] + changed.decode("utf-8") + text[stop:]).encode("utf-8")


def check_user_cost(cost):
    if cost is None:
        return
    if (isinstance(cost.get("type"), bool) or not isinstance(cost.get("type"), int)
            or cost.get("type") not in (1, 2)):
        raise ValueError("userCost type must be 1 or 2; type 0 paid beads are forbidden")
    amount = cost.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, int) or not 0 < amount <= 2147483647:
        raise ValueError("userCost amount must be a positive bounded integer")
