"""Route visible fields through wf text, including both server mirrors."""
from __future__ import annotations

import copy
from pathlib import Path

from wf.balance.rows import column_index
from wf.text.edit import prepare_edit
from wf.text.model import CHARACTER, CHARACTER_TEXT, SERVER_TARGETS, TextWorkspace


def _retain_separators(before, after):
    from wf.balance.rows import join_leaf, split_leaf
    if isinstance(before, str) and isinstance(after, str):
        return join_leaf(before, split_leaf(after, "text"))
    if isinstance(before, dict) and isinstance(after, dict):
        return {key: _retain_separators(before[key], value) if key in before else value
                for key, value in after.items()}
    return after


def load_mirrors(state, server_dir=None, *, server_text=None, server_rank=None):
    if state.server_original:
        return
    paths = (server_text, server_rank)
    if server_dir is not None:
        paths = tuple(Path(server_dir) / target for target in SERVER_TARGETS)
    if any(path is None for path in paths):
        raise ValueError("文本修改需要显式指定两份服务端镜像（server_dir 或 server_text/server_rank）")
    # TextWorkspace validates distinct inputs and JSON shape without writing them.
    workspace = TextWorkspace(state, *map(Path, paths))
    state.server_original = dict(workspace.server_raws)
    state.servers = dict(workspace.server_raws)


def workspace_for(state):
    from wf.text.json_patch import parse_mirror
    workspace = TextWorkspace(state)
    workspace.server_raws = dict(state.servers)
    workspace.server_docs = {key: parse_mirror(value) for key, value in state.servers.items()}
    workspace.server_raw = workspace.server_raws.get(SERVER_TARGETS[0])
    workspace.server = workspace.server_docs.get(SERVER_TARGETS[0])
    return workspace


def split_operations(operations):
    """Keep numerical edits in the balance path; collect tier assertions together."""
    numeric, text = [], {}
    for operation in operations:
        if operation["op"] != "set_cells" or operation["table"] != "action_skill":
            numeric.append(operation)
            continue
        visible, other = [], []
        for cell in operation["cells"]:
            (visible if column_index("action_skill", cell["column"]) < 2 else other).append(cell)
        if visible:
            if operation["row"] != 0 or operation["row_count"] != 1:
                raise ValueError("action_skill 文本要求每档一行，且 row=0、row_count=1")
            pair = text.setdefault(operation["level"], {})
            for cell in visible:
                field = f"c{column_index('action_skill', cell['column'])}"
                if field in pair:
                    raise ValueError(f"duplicate visible cell: {operation['level']}/{field}")
                pair[field] = {"old": cell["old"], "new": cell["new"]}
        if other:
            numeric.append({**operation, "cells": other})
    return numeric, text


def apply_text(state, cid, sections, *, shared_ok=False):
    """Reuse the exact panel rules; explicit shared edits synchronize every owner.

    wf text's single-character entry point rejects shared keys. Here ownership is
    checked before projection, each owner is processed independently against the
    same pre-edit client view, and only those computed leaf changes are merged.
    This retains its text validation and byte-preserving JSON patcher.
    """
    from wf.balance.ownership import owner_index
    import wf_quest_lib as codec
    from wf.text.model import cells
    from .text_panel import custom_owners

    workspace = workspace_for(state)
    document = workspace.read(cid)
    all_characters = state.table(CHARACTER)
    recipients = {cid: copy.deepcopy(sections)}
    shared = {}
    if sections.get("action_skill"):
        owners = sorted(owner_index(state)["action_skill"].get(document["skill_key"], set()))
        shared["action_skill/" + document["skill_key"]] = owners
        for owner in owners:
            recipients.setdefault(owner, {})["action_skill"] = copy.deepcopy(sections["action_skill"])
    for section in ("custom_ability_string", "desc_override"):
        for key, change in sections.get(section, {}).items():
            # Same owners as scanning every character's custom_keys, prefiltered.
            owners = sorted(custom_owners(workspace, [key])[key])
            shared[section + "/" + key] = owners
            for owner in owners:
                recipients.setdefault(owner, {}).setdefault(section, {})[key] = change
    for key, owners in shared.items():
        if cid not in owners:
            raise ValueError(f"{key}: character {cid} is not an owner; owners={owners}")
        if len(owners) > 1 and not shared_ok:
            raise ValueError(f"{key}: shared key owners={owners}; declare shared_ok: true explicitly")

    before = dict(state.client)
    merged = {}
    # Each owner's skill old values refer to the same original client fields.
    for owner, owner_sections in sorted(recipients.items()):
        class OwnerView:
            def read_raw(self, logical):
                if logical == CHARACTER:
                    return codec.build_node({owner: all_characters[owner]}), "owner-projection"
                return before.get(logical, state.read_raw(logical)[0]), "text-before"
        projected = TextWorkspace(OwnerView())
        projected.server_raws = dict(state.servers)
        from wf.text.json_patch import parse_mirror
        projected.server_docs = {target: parse_mirror(raw) for target, raw in state.servers.items()}
        projected.server_raw = projected.server_raws[SERVER_TARGETS[0]]
        projected.server = projected.server_docs[SERVER_TARGETS[0]]
        snapshot = projected.read(owner)["snapshot_sha256"]
        prepared = prepare_edit(projected, {"character_id": owner, "snapshot_sha256": snapshot,
                                            **owner_sections})
        for logical, raw in prepared["client"].items():
            original = projected.tables[logical]
            updated = codec.parse_node(raw)
            target = merged.setdefault(logical, state.table(logical))
            for key, value in updated.items():
                if value != original.get(key):
                    target[key] = _retain_separators(original.get(key), value)
        state.servers = prepared["servers"]
        state.changes.extend(prepared["changes"])
        state.checks.extend({"rule": f["rule"], "status": f["state"], "message": f["message"],
                             "blocking": False, "character": owner}
                            for f in prepared["checks"])
    for logical, table in merged.items():
        state.write_table(logical, table)
    state.changes.append({"op": "text_sync", "character": cid, "owners": shared})


def sync_skill_structure(state, owners):
    """Structural tier edits also replace/clear all six visible mirror cells.

    The ordinary wf text edit API intentionally cannot insert/delete tiers.
    Reuse its parser, column patcher, effective-text rules and sparse-rank
    behavior after the tier rows have passed complete old-cell assertions.
    """
    import json
    from wf.balance.rows import join_leaf
    from wf.text.json_patch import patch_columns
    from wf.text.model import cells
    from wf.text.rules import check_character

    for cid in sorted(set(owners)):
        workspace = workspace_for(state)
        doc = workspace.read(cid)
        old_leaf = state.table(CHARACTER_TEXT)[cid]
        row = cells(old_leaf)
        if len(row) < 10:
            raise ValueError(f"character_text/{cid}: lacks skill mirror columns")
        if not any(cid in server for server in workspace.server_docs.values()):
            raise ValueError("character is missing from both server text mirrors")
        patches = {2 + 2 * int(level) + column: doc["action_skill"].get(level, {}).get(f"c{column}", "")
                   for level in ("1", "2", "3") for column in (0, 1)}
        for target, server in workspace.server_docs.items():
            if cid in server:
                if len(server[cid][0]) != len(row):
                    raise ValueError(f"client/server character_text columns differ: {target}")
                state.servers[target] = patch_columns(state.servers[target], cid, patches)
        for column, value in patches.items():
            row[column] = value
        table = state.table(CHARACTER_TEXT)
        table[cid] = join_leaf(old_leaf, [row])
        state.write_table(CHARACTER_TEXT, table)
        checks = check_character(workspace_for(state).read(cid))
        issues = [entry for entry in checks if entry["state"] == "问题" and
                  (entry["location"].startswith("action_skill") or entry["rule"].startswith("text.effective"))]
        if issues:
            raise ValueError("text rules failed: " + json.dumps(issues, ensure_ascii=False))
        state.checks.extend({"rule": item["rule"], "status": item["state"], "message": item["message"],
                             "blocking": False, "character": cid} for item in checks)
        state.changes.append({"op": "skill_tier_text_sync", "character": cid, "columns": patches})
