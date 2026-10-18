"""Assert text edits in memory, then stage both client and server locally."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .json_patch import patch_columns
from .model import (ABILITY, ACTION_SKILL, CHARACTER, CHARACTER_TEXT, CUSTOM, LEADER, SERVER_TARGET,
                    SERVER_TARGETS, TextWorkspace, cells, custom_text, replace_cells, sha256)
from .rules import check_character
from wf.view.safety import local_output


def _change(old, operation, location):
    if not isinstance(operation, dict) or set(operation) != {"old", "new"}:
        raise ValueError(f"{location}: require exactly old and new")
    if not isinstance(operation["new"], str) or old != operation["old"]:
        raise ValueError(f"{location}: old-value assertion failed or new value is not text")
    return operation["new"]


def override_owners(workspace: TextWorkspace, key: str) -> list[str]:
    """Characters whose leader/ability rows carry the c0 that ``desc_override_<c0>`` = ``key`` names.

    The client shows ``desc_override_<row c0>`` instead of the generated row text, so these are
    exactly the characters a new override key would change.
    """
    import csv
    import io
    owners = []
    for cid, leaf in workspace.table(CHARACTER).items():
        row = cells(leaf)
        for logical, refs in ((LEADER, row[17:18]), (ABILITY, row[19:25])):
            names = set()
            for ref in refs:
                value = workspace.table(logical).get(ref, "")
                if isinstance(value, str) and value:
                    names.update(r[0] for r in csv.reader(io.StringIO(value, newline="")) if r)
            if key in {"desc_override_" + name for name in names if name}:
                owners.append(cid)
                break
    return owners


def _replace_row(original, row):
    return original if cells(original) == row else replace_cells(original, row)


def _encode(raw, before, after):
    """Retain every unchanged compressed leaf, including non-default zlib levels."""
    if before == after:
        return raw
    import wf_mod_tool as core
    import wf_quest_lib as codec
    if isinstance(after, str):
        return codec.build_node(after)
    parsed = core.read_orderedmap_raw_rows_from_bytes(raw, "text-edit")
    old_chunks = dict(zip(parsed.keys, parsed.rows))
    chunks = [_encode(old_chunks[k], before[k], v) if k in before else codec.build_node(v)
              for k, v in after.items()]
    return core.build_orderedmap_raw_rows(core.OrderedMap("text-edit", list(after), chunks, parsed.source_path))


def prepare_edit(workspace: TextWorkspace, edit: dict) -> dict:
    """No filesystem mutation. Invalid or partial edits return no usable package."""
    allowed = {"character_id", "snapshot_sha256", "action_skill", "character_text",
               "custom_ability_string", "desc_override"}
    if set(edit) - allowed:
        raise ValueError(f"unknown text-edit fields: {sorted(set(edit) - allowed)}")
    cid = str(edit["character_id"])
    original = workspace.read(cid)
    workspace.verify()
    if edit.get("snapshot_sha256") != original["snapshot_sha256"]:
        raise ValueError("text input snapshot changed; read it again before editing")
    tables = copy.deepcopy(workspace.tables)
    ct = cells(tables[CHARACTER_TEXT][cid])
    servers = copy.deepcopy(workspace.server_docs)
    for target in SERVER_TARGETS:
        if target not in servers:
            raise ValueError(f"explicit {Path(target).name} is required for synchronized edits")
        if cid not in servers[target]:
            continue  # The rank file is a sparse overlay, not a second full table.
        rows = servers[target][cid]
        if not isinstance(rows, list) or not rows or not isinstance(rows[0], list):
            raise ValueError(f"server character_text row is malformed: {target}")
        if len(rows[0]) != len(ct) or any(not isinstance(value, str) for value in rows[0]):
            raise ValueError(f"client/server character_text columns differ: {target}")
    if not any(cid in server for server in servers.values()):
        raise ValueError("character is missing from both server text mirrors")
    changes = []
    patched_columns = {}

    def sync(column, new, source):
        changes.append({"character_id": cid, "surface": source, "column": column,
                        "client_old": ct[column],
                        "server_old_by_target": {target: server[cid][0][column]
                                                 for target, server in servers.items() if cid in server},
                        "new": new})
        ct[column] = patched_columns[column] = new
        for server in servers.values():
            if cid in server:
                server[cid][0][column] = new

    skill_changes = edit.get("action_skill", {})
    tiers = original["action_skill"]
    if set(skill_changes) - set(tiers):
        raise ValueError("edit addresses an absent action_skill tier")
    for field in ("c0", "c1"):
        touched = {tier for tier, pair in skill_changes.items() if field in pair}
        if touched and touched != set(tiers):
            raise ValueError(f"{field}: provide old/new assertions for every existing skill tier")
    skill_key = original["skill_key"]
    if skill_changes:
        owners = [key for key, leaf in tables[CHARACTER].items()
                  if cells(leaf)[8] == skill_key]
        if owners != [cid]:
            raise ValueError(f"shared action_skill {skill_key} has owners {owners}; choose a separate key before editing")
    for tier, pair in skill_changes.items():
        if set(pair) - {"c0", "c1"}:
            raise ValueError("only action_skill c0/c1 are visible text")
        leaf = tables[ACTION_SKILL][skill_key][tier]
        fields = cells(leaf)
        for field, op in pair.items():
            column = int(field[1:])
            new = _change(fields[column], op, f"action_skill.{tier}.{field}")
            fields[column] = new
            sync(2 + 2 * int(tier) + column, new, f"action_skill.{tier}.{field}")
        tables[ACTION_SKILL][skill_key][tier] = _replace_row(leaf, fields)
    for key, op in edit.get("character_text", {}).items():
        column = int(key)
        if column < 0 or column >= len(ct) or 4 <= column <= 9:
            raise ValueError("skill mirrors c4..c9 must be edited through action_skill")
        new = _change(ct[column], op, f"character_text.{column}")
        sync(column, new, "character_text")
        if column == 10:  # Character row carries the leader name as well.
            leaf = tables[CHARACTER][cid]
            character = cells(leaf)
            character[18] = new
            tables[CHARACTER][cid] = _replace_row(leaf, character)
    for section in ("custom_ability_string", "desc_override"):
        for key, op in edit.get(section, {}).items():
            if (section == "desc_override" and key not in original[section] and isinstance(op, dict)
                    and set(op) == {"old", "new"} and op["old"] is None):
                # New override: old=null asserts the key is absent; it must name a row c0 of this
                # character's own leader/ability slot, and no other character may share that row.
                if key in tables[CUSTOM]:
                    raise ValueError(f"{section}.{key}: old=null but the key already exists")
                owners = override_owners(workspace, key)
                if owners != [cid]:
                    raise ValueError(f"{section}.{key}: a new override must name a row c0 owned only by "
                                     f"{cid}; owners={owners}")
                if not isinstance(op["new"], str) or not op["new"].strip():
                    raise ValueError(f"{section}.{key}: new override text is empty")
                tables[CUSTOM][key] = replace_cells("", [op["new"]])
                changes.append({"character_id": cid, "surface": section, "key": key, "old": None,
                                "new": op["new"], "created": True,
                                "server_mapping": "client-only surface; character_text.json has no ability-text columns"})
                continue
            if key not in original[section]:
                raise ValueError(f"{section}.{key} is not a referenced existing character text")
            owners = [owner for owner in tables[CHARACTER] if key in workspace.custom_keys(owner)]
            if owners != [cid]:
                raise ValueError(f"shared custom text {key} has owners {owners}; choose a separate key before editing")
            leaf = tables[CUSTOM][key]
            new = _change(custom_text(leaf), op, f"{section}.{key}")
            tables[CUSTOM][key] = _replace_row(leaf, [new])
            changes.append({"character_id": cid, "surface": section, "key": key,
                            "old": op["old"], "new": new,
                            "server_mapping": "client-only surface; character_text.json has no ability-text columns"})
    tables[CHARACTER_TEXT][cid] = _replace_row(tables[CHARACTER_TEXT][cid], ct)
    if not changes:
        raise ValueError("text edit has no operations")
    class EditedView:
        def read_raw(self, logical):
            return _encode(workspace.raw[logical], workspace.tables[logical], tables[logical]), "staged"
    staged = TextWorkspace(EditedView())
    server_bytes = {target: patch_columns(workspace.server_raws[target], cid, patched_columns)
                    if cid in servers[target] else workspace.server_raws[target]
                    for target in SERVER_TARGETS}
    staged.server_docs, staged.server_raws = servers, server_bytes
    staged.server, staged.server_raw = servers[SERVER_TARGET], server_bytes[SERVER_TARGET]
    document = staged.read(cid)
    findings = check_character(document)
    changed_locations = {f"action_skill.{tier}.{field}" for tier, pair in skill_changes.items() for field in pair}
    changed_locations |= {f"{section}.{key}" for section in ("custom_ability_string", "desc_override") for key in edit.get(section, {})}
    changed_locations |= {f"character_text.{column}" for column in edit.get("character_text", {})}
    if "3" in edit.get("character_text", {}):
        changed_locations.add("title")
    # Cross-field findings are located on action_skill even when the edit was
    # made to its custom/override enhancement. Compare before/after findings,
    # and also follow their explicit source key rather than only the location.
    identity = lambda finding: json.dumps(finding, ensure_ascii=False, sort_keys=True)
    previous_problems = {identity(f) for f in check_character(original) if f["state"] == "问题"}
    changed_keys = set(edit.get("custom_ability_string", {})) | set(edit.get("desc_override", {}))
    violations = [f for f in findings if f["state"] == "问题" and (
        f["location"] in changed_locations or identity(f) not in previous_problems
        or f["evidence"].get("key") in changed_keys)]
    if violations:
        raise ValueError("text rules failed: " + json.dumps(violations, ensure_ascii=False))
    client = {logical: _encode(workspace.raw[logical], workspace.tables[logical], value)
              for logical, value in tables.items() if value != workspace.tables[logical]}
    if not client:
        raise ValueError("text edit has no actual client changes")
    return {"client": client, "server": server_bytes[SERVER_TARGET], "servers": server_bytes, "changes": changes,
            "before": {logical: sha256(raw) for logical, raw in workspace.raw.items()},
            "server_before": sha256(workspace.server_raw), "document": document,
            "server_before_by_target": {target: sha256(raw) for target, raw in workspace.server_raws.items()},
            "checks": findings, "_workspace": workspace}


def stage_edit(prepared: dict, output: Path, metadata: dict) -> Path:
    """Write a new local output directory only, with both sides in one change set."""
    output = local_output(output)
    if output.exists():
        raise FileExistsError(f"text output already exists: {output}")
    required = {"id", "name", "from_version", "to_version", "slug", "created_at"}
    if set(metadata) != required:
        raise ValueError(f"metadata requires exactly {sorted(required)}")
    prepared["_workspace"].verify()
    payloads = {}
    members = []
    for index, (logical, data) in enumerate(sorted(prepared["client"].items())):
        relative = f"payload/client-{index}.orderedmap"
        payloads[relative] = data
        members.append({"root": "common", "logical_path": logical, "source": relative,
                        "sha256": sha256(data), "before_sha256": prepared["before"][logical]})
    server_changes = []
    for target, data in prepared["servers"].items():
        source = "server/" + Path(target).name
        payloads[source] = data
        server_changes.append({"target": target, "source": source, "sha256": sha256(data),
                               "before_sha256": prepared["server_before_by_target"][target]})
    change_set = {"schema": "wf-change-set/1", **metadata, "local_test_only": True,
                  "experimental": False, "capabilities": [], "members": members,
                  "server_changes": server_changes,
                  "changes": prepared["changes"]}
    from wf.deliver.changeset import validate_document
    validate_document(change_set, "change-set.schema.json")
    if tuple(map(int, metadata["from_version"].split("."))) >= tuple(map(int, metadata["to_version"].split("."))):
        raise ValueError("text change-set version must move forward")
    output.mkdir(parents=True)
    for relative, data in payloads.items():
        target = local_output(output / relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    target = output / "changeset.json"
    target.write_text(json.dumps(change_set, ensure_ascii=False, indent=2) + "\n", "utf-8")
    return target
