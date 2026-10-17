"""十五小Boss第二版六能力的两表精确候选；无发布、整包回放或live写入。"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import zlib

import wf_dsl
import wf_mod_tool as core
from wf_content_revision_patch import PatchResult, _safe_path
from wf_miniboss_kits import build_abilities
from wf_miniboss_roster import ROSTER
from wf_miniboss_text import ability_panel_rows

ABILITY = "master/ability/ability.orderedmap"
STRINGS = "master/string/custom_ability_string.orderedmap"
UNIQUE = "master/character/unique_condition.orderedmap"
PROTECTED = ("master/ability/leader_ability.orderedmap",
             "master/skill/action_skill.orderedmap", core.STATUS_LOGICAL, UNIQUE)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def replace_existing(raw, replacements):
    """只替换已安装的声明键；所有其他行原压缩字节及键序保持。"""
    table = core.read_orderedmap_raw_rows_from_bytes(raw)
    original = dict(zip(table.keys, table.rows))
    missing = replacements.keys() - original.keys()
    if missing:
        raise ValueError("missing installed keys: " + str(sorted(missing)))
    changed, entries = [], {}
    for index, key in enumerate(table.keys):
        if key not in replacements:
            continue
        rows = replacements[key]
        text = core.write_csv_lines(rows).rstrip("\n").encode("utf-8")
        after = zlib.compress(text)
        # Equal CSV semantics retain the installed compression and whitespace.
        if core.read_csv_lines(zlib.decompress(original[key]).decode("utf-8")) == rows:
            after = original[key]
        if after != original[key]:
            table.rows[index] = after
            changed.append(key)
            entries[key] = {"before_sha256": sha(original[key]), "after_sha256": sha(after)}
    output = core.build_orderedmap_raw_rows(table) if changed else raw
    readback = core.read_orderedmap_raw_rows_from_bytes(output)
    final = dict(zip(readback.keys, readback.rows))
    if readback.keys != table.keys or any(final[k] != v for k, v in original.items() if k not in changed):
        raise ValueError("unrelated table row or ordering changed")
    return output, {"changed_keys": changed, "rows": entries,
                    "preserved_row_count": len(original) - len(changed)}


def _walk(value):
    if isinstance(value, list):
        yield value
        for child in value:
            yield from _walk(child)
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)


def plan(repo, output):
    repo = _safe_path(Path(repo))
    snapshots = {}

    def read(path):
        path = _safe_path(path)
        if path not in snapshots:
            snapshots[path] = path.read_bytes()
        return snapshots[path]

    profile = json.loads(read(repo / "mod-tools/profiles.json"))["profiles"]["cn"]
    store = Path(profile["store"])
    store = store if store.is_absolute() else repo / store
    files, tables, replacements, budgets, helpers = {}, [], {ABILITY: {}, STRINGS: {}}, {}, {}
    protected = {p: sha(read(core.table_path(store, p))) for p in PROTECTED}
    unique = core.read_orderedmap_file_from_bytes(read(core.table_path(store, UNIQUE)))
    states = {}
    for char in ROSTER:
        state = core.read_csv_lines(unique[str(char.uid)])[0]
        if int(state[4]) != char.layers:
            raise ValueError(f"installed unique accumulation drift: {char.cid}")
        states[str(char.uid)] = {"duration_frames": state[3], "maximum_layers": state[4],
                                "raw_row": state}
        abilities, budget = build_abilities(char.cid)
        budgets[char.cid] = budget
        replacements[ABILITY].update(abilities)
        replacements[STRINGS].update(ability_panel_rows(char.cid, abilities))
        for rows in abilities.values():
            for row in rows:
                if row[5] != "0" or row[47] != "629":
                    continue
                logical = row[71] + ".action.dsl.amf3.deflate"
                raw = read(core.table_path(store, logical))
                tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
                # Existing hit geometry may remain; helpers must not hide extra buffs.
                for node in _walk(tree):
                    if (node and isinstance(node[0], str) and node[0].startswith("AC")
                            and node[0] not in {"ACFrozen", "ACPoison", "ACParalysis"}):
                        raise ValueError(f"unbudgeted helper condition: {logical}:{node[0]}")
                helpers[logical] = sha(raw)
    for logical, selected in replacements.items():
        before = read(core.table_path(store, logical))
        after, details = replace_existing(before, selected)
        if details["changed_keys"]:
            files["common", logical] = after
        tables.append({"root": "common", "logical_path": logical,
                       "before_sha256": sha(before), "after_sha256": sha(after),
                       "authorized_keys": sorted(selected), **details})
    report = {"kind": "miniboss-six-ability-revision-v2", "flow_certified": False,
              "release_path": "existing-character exact table maintenance",
              "writes_live": False, "character_ids": [c.cid for c in ROSTER],
              "tables": tables, "budgets": budgets, "retained_unique_states": states,
              "protected_tables_sha256": protected, "protected_helpers_sha256": helpers,
              "protected_scope": ["leader", "active DSL and description", "HP/ATK",
                                  "unique master", "gacha", "all presentation and voice assets"],
              "acceptance": "native fields, stored-byte scope and static tests; not device gameplay"}
    return PatchResult(repo, Path(output), files, report, snapshots)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidate = plan(args.repo, args.output)
    candidate.write()
    print(json.dumps({"output": str(candidate.output), "files": len(candidate.files),
                      "changed_keys": {t["logical_path"]: len(t["changed_keys"])
                                       for t in candidate.report["tables"]}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
