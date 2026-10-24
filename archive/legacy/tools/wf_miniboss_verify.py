"""小Boss候选独立字节审查：非本角色表行、展示素材、DSL不得改变。"""
import json
import zlib
from pathlib import Path

import wf_dsl
import wf_mod_tool as core
from wf_miniboss_budget import audit
from wf_miniboss_roster import BY_ID


def changed_keys(before, after):
    left = core.read_orderedmap_raw_rows_from_bytes(before)
    right = core.read_orderedmap_raw_rows_from_bytes(after)
    a, b = dict(zip(left.keys, left.rows)), dict(zip(right.keys, right.rows))
    if set(a) - set(b):
        raise ValueError("candidate removed an existing table key")
    return {key for key in b if key not in a or b[key] != a[key]}


def _walk(value):
    if isinstance(value, list):
        yield value
        for child in value:
            yield from _walk(child)
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk(child)


def verify(repo, workspace, cid):
    repo, workspace = Path(repo), Path(workspace)
    char = BY_ID[str(cid)]
    source = repo / "work/character_packs" / char.package_id / "package"
    package = workspace / "package"
    manifest = json.loads((package / "manifest.json").read_bytes())
    profile = json.loads((repo / "mod-tools/profiles.json").read_bytes())["profiles"]["cn"]
    store = Path(profile["store"])
    store = store if store.is_absolute() else repo / store
    allow = {
        "master/ability/ability.orderedmap": {char.cid + str(n) for n in range(1, 7)},
        "master/ability/leader_ability.orderedmap": {char.cid},
        "master/string/custom_ability_string.orderedmap": {
            "desc_override_" + char.code, *("desc_override_" + char.code + f"_{n}" for n in range(1, 7))},
        "master/skill/action_skill.orderedmap": {char.code},
        "master/character/character_text.orderedmap": {char.cid},
        core.STATUS_LOGICAL: {char.cid},
    }
    changed, assets, dsl_count = {}, 0, 0
    for tier, entries in manifest["roots"].items():
        for entry in entries:
            logical = entry["logical_path"]
            raw = (package / "roots" / tier / logical).read_bytes()
            if tier == "common" and logical.startswith("master/"):
                keys = changed_keys(core.table_path(store, logical).read_bytes(), raw)
                if keys - allow.get(logical, set()):
                    raise ValueError(f"unrelated live table rows differ: {logical}: {sorted(keys)}")
                changed[logical] = sorted(keys)
            elif tier == "server":
                before, after = json.loads((repo / "assets" / logical).read_bytes()), json.loads(raw)
                keys = {key for key in before.keys() | after.keys() if before.get(key) != after.get(key)}
                if keys - ({char.cid} if logical == "cdndata/character_text.json" else set()):
                    raise ValueError(f"unrelated server mirror rows differ: {logical}")
                changed["server:" + logical] = sorted(keys)
            else:
                if raw != (source / "roots" / tier / logical).read_bytes():
                    raise ValueError(f"protected installed asset changed: {tier}:{logical}")
                assets += 1
                if logical.endswith(".action.dsl.amf3.deflate"):
                    dsl_count += 1
                    tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
                    if any(node and isinstance(node[0], str) and "SeparatedTerm" in node[0]
                           for node in _walk(tree)):
                        raise ValueError("retained DSL contains an unaudited independent term")
    ab = package / "roots/common/master/ability/ability.orderedmap"
    all_abilities = core.read_orderedmap_file_from_bytes(ab.read_bytes())
    own = {n: core.read_csv_lines(all_abilities[char.cid + str(n)]) for n in range(1, 7)}
    budget = audit(own)
    # Every invoked ability action is audited separately from active skills.
    helpers = []
    allowed_conditions = {"ACFrozen", "ACPoison", "ACParalysis"}
    for rows in own.values():
        for row in rows:
            if row[5] != "0" or row[47] != "629":
                continue
            logical = row[71] + ".action.dsl.amf3.deflate"
            path = package / "roots/common" / logical
            raw = path.read_bytes() if path.exists() else core.table_path(store, logical).read_bytes()
            tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
            for node in _walk(tree):
                if node and isinstance(node[0], str) and node[0].startswith("AC") and node[0] not in allowed_conditions:
                    raise ValueError(f"unbudgeted ability helper condition: {logical}:{node[0]}")
            helpers.append(logical)
    return {"character_id": char.cid, "changed_table_keys": changed,
            "protected_assets_identical": assets, "dsl_programs_identical": dsl_count,
            "ability_helpers_without_hidden_damage_buffs": sorted(set(helpers)),
            "budget_from_candidate_rows": budget, "writes_live": False}
