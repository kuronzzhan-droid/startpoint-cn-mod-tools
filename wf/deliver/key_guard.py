"""Protect shared-table contents against the exact, manifest-selected baseline.

The legacy publish guard discovers the global CDN chain. Local deliveries must
instead use their locked view, while sharing its orderedmap/claims inspection.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import wf_publish_guard as publish_guard

from wf.boss.shop_model import ENH_SHOP, ENH_CATEGORY, SERVER_ENH, SERVER_SHOP, SERVER_MAP, WEAPON_TABLES
from wf.boss.schema import SHOP, SHOP_CATEGORY
from wf.caps.requirements import parse_table
from .prepush_base import View

CUSTOM = "master/string/custom_ability_string.orderedmap"
AWAKENING = "assets/equipment_awakening_material.json"
SHARED_TABLES = {*WEAPON_TABLES, ENH_SHOP, ENH_CATEGORY, SHOP, SHOP_CATEGORY, CUSTOM}
SERVER_MAPS = {"assets/" + name + ".json" for name in (
    "equipment_lookup", "equipment_max_level", "equipment_element", "item_sale", "item_lookup")}
SERVER_MAPS.update({SERVER_ENH, AWAKENING, SERVER_SHOP, SERVER_MAP})
SERVER_MAPS.add("assets/equipment_dissolve.json")
SERVER_MAPS.add("assets/continue_cost.json")
CHARACTER_MAPS = {"character.json", "cdndata/character.json", "cdndata/character_text.json",
                  "cdndata/character_text_rank_p5b.json", "mana_node.json", "mana_board.json"}
# Character delivery accepts either a server repository or its assets directory.
SERVER_MAPS.update(CHARACTER_MAPS | {"assets/" + name for name in CHARACTER_MAPS})
SERVER_LISTS = {"assets/equipment_ids.json", "assets/item_ids.json"}


def _shop_deletions(logical, old, changes):
    """Only the supported Boss shop_delete operation has a deletion contract."""
    if logical != SHOP:
        return set()
    baseline = parse_table(old, logical)
    current, broken = {}, set()
    for change in changes:
        if (not isinstance(change, dict) or change.get("table") != SHOP
                or not isinstance(change.get("path"), list) or len(change["path"]) != 1
                or not isinstance(change["path"][0], str) or change["path"][0] not in baseline):
            continue
        key = change["path"][0]
        if ("old" not in change or "new" not in change
                or change["old"] != current.get(key, baseline[key])):
            broken.add(key)
        current[key] = change.get("new", False)
    return {key for key, value in current.items() if value is None and key not in broken}


def _nested_keys(old, new, label):
    if not isinstance(old, dict):
        return []
    if not isinstance(new, dict):
        return [f"{label}: nested baseline table became a leaf"]
    errors = []
    for key, child in old.items():
        if key not in new:
            errors.append(f"{label}/{key}: lost nested baseline key")
        else:
            errors += _nested_keys(child, new[key], f"{label}/{key}")
    return errors


def _record_count(payload):
    # The publish guard's text probe excludes nested orderedmap binary chunks.
    # CSV parsing counts quoted multiline descriptions as one record.
    if publish_guard._row_lines(payload) is None:
        return None
    try:
        return sum(bool(row) for row in csv.reader(io.StringIO(payload.decode("utf-8")), strict=True))
    except csv.Error:
        return None


def _table_problems(logical, old, new, protected, version, changes=()):
    old_rows, new_rows = publish_guard._rows_of(old), publish_guard._rows_of(new)
    if old_rows is None or new_rows is None:
        return [f"{logical}: cannot inspect orderedmap; refusing whole-table replacement"], []
    lost = sorted(set(old_rows) - set(new_rows) - _shop_deletions(logical, old, changes))
    errors = [f"{logical}: lost baseline outer keys: {lost[:12]}"] if lost else []
    claimed = sorted((set(old_rows) & protected) - set(new_rows))
    if claimed:
        errors.append(f"{logical}: lost protected character-pack claims: {claimed[:12]}")
    if logical in SHARED_TABLES and logical != SHOP:
        errors += _nested_keys(parse_table(old, logical), parse_table(new, logical), logical)
    for key in sorted(set(old_rows) & set(new_rows)):
        before = _record_count(old_rows[key])
        after = _record_count(new_rows[key])
        if before is not None and after is None:
            errors.append(f"{logical}[{key}]: flat baseline record became non-text/binary data")
        if before is not None and after is not None and after < before:
            errors.append(f"{logical}[{key}]: baseline record count shrank {before} -> {after}")
    return errors, publish_guard.content_notes(logical, version, old, new)


def _map_keys(before, after, label):
    if not isinstance(before, dict) or not isinstance(after, dict):
        return [f"{label}: shared JSON map must remain an object"]
    lost = sorted(set(before) - set(after))
    return [f"{label}: lost baseline JSON keys: {lost[:12]}"] if lost else []


def _server_problems(target, old, new, deleted=()):
    if old is None:
        return [f"{target}: missing complete server baseline; refusing partial shared file"]
    try:
        before, after = json.loads(old), json.loads(new)
    except (ValueError, UnicodeError) as error:
        return [f"{target}: invalid shared JSON: {error}"]
    if target in SERVER_LISTS:
        if not isinstance(before, list) or not isinstance(after, list):
            return [f"{target}: shared ID list must remain an array"]
        lost = [value for value in before if value not in after]
        return [f"{target}: lost baseline IDs: {lost[:12]}"] if lost else []
    if target == SERVER_MAP and isinstance(before, dict):
        before = {k: v for k, v in before.items() if k not in deleted}
    if target == SERVER_SHOP and isinstance(before, dict) and isinstance(after, dict):
        required = {k: v for k, v in before.items()
                    if not isinstance(v, dict) or not v or set(v) - set(deleted)}
        errors = _map_keys(required, after, target)
        for category, products in before.items():
            if not isinstance(products, dict):
                errors.append(f"{target}/{category}: shop category must be an object")
                continue
            retained = {k: v for k, v in products.items() if k not in deleted}
            # Deleting the last product may remove its now-empty category.
            if retained:
                errors += _map_keys(retained, after.get(category), f"{target}/{category}")
        return errors
    errors = _map_keys(before, after, target)
    if target == AWAKENING and isinstance(before, dict) and isinstance(after, dict):
        for section in ("materialByEquipment", "rarityOverrides", "officialCrystals"):
            if section not in before:
                continue
            original, candidate = before[section], after.get(section)
            if isinstance(original, dict):
                errors += _map_keys(original, candidate, f"{target}/{section}")
            elif isinstance(original, list) and (not isinstance(candidate, list)
                    or any(value not in candidate for value in original)):
                errors.append(f"{target}/{section}: lost baseline entries")
    return errors


def check_shared_keys(members, server_changes, *, baseline=None, base_store=None,
                      server_dir=None, protected=None, changes=(), no_baseline_i_know=False):
    """Check retention, never silently merge a stale payload into a newer file.

    JSON leaf values (e.g. material costs/userCost) may change. Only inventory
    keys and ID lists are protected; arbitrary leaf fields are not frozen.
    """
    guarded = publish_guard.protected_keys() if protected is None else protected
    errors, notes, checked, deleted = [], [], [], set()
    for name, (raw, entry) in members.items():
        logical = entry["logical_path"]
        if not logical.endswith(".orderedmap"):
            continue
        try:
            parse_table(raw, logical)
        except (ValueError, TypeError, IndexError, UnicodeError, AssertionError) as error:
            errors.append(f"{logical}: cannot inspect candidate orderedmap: {error}")
            continue
        try:
            if baseline is not None:
                old = baseline.read_member(name)[0]
            elif base_store is not None:
                filename = View([], base_store)._base_file(name)
                old = filename.read_bytes() if filename is not None else None
            else:
                old = None
        except FileNotFoundError:
            old = None
        if old is None:
            waived = baseline is None and base_store is None and no_baseline_i_know
            if logical in SHARED_TABLES and not waived:
                errors.append(f"{logical}: missing complete client baseline; refusing partial shared table")
            if waived:
                notes.append(f"{logical}: explicit no-baseline waiver; key preservation is unverified")
            continue
        problems, content = _table_problems(logical, old, raw, guarded.get(logical, set()),
                                            baseline.tip if baseline is not None else "base store", changes)
        errors += problems
        notes += content
        checked.append(logical)
        if logical == SHOP:
            deleted.update(_shop_deletions(logical, old, changes))
    server_checked = []
    for target, raw in server_changes.items():
        if target not in SERVER_MAPS | SERVER_LISTS:
            continue
        filename = Path(server_dir) / target if server_dir is not None else None
        old = filename.read_bytes() if filename is not None and filename.is_file() else None
        errors += _server_problems(target, old, raw, deleted)
        server_checked.append(target)
    return {"baseline": baseline.tip if baseline is not None else None,
            "client_tables": checked, "server_targets": server_checked,
            "protected_claims_checked": bool(checked), "errors": errors, "notes": notes}
