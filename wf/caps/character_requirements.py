"""Map changed character content to the registry's documented APK dependencies."""
from __future__ import annotations

import zlib

from wf_dsl import parse_dsl
from wf.dsl.references import DSL_SUFFIX, program_logical

from .facts import CHARACTER, PF, SKILL, STRINGS, UNIQUE, dsl_signals, leaves, rows, table_signals

RELATED = {CHARACTER, PF, SKILL, STRINGS, UNIQUE,
           "master/ability/ability.orderedmap", "master/ability/leader_ability.orderedmap",
           "master/skill/switched_action_skill.orderedmap"}


def character_requirements(changed, *, read, table, registry):
    """Follow actual references; missing ownership inputs cannot prove no dependency."""
    owners = {cid for cap in registry.values() for cid in cap["data_surface"].get("character_ids", [])}
    relevant = {p: keys for p, keys in changed.items() if p in RELATED or
                p.startswith(("master/character/", "character/", "battle/"))}
    if not relevant:
        return [], []
    affected, unresolved = {}, []

    def missing(logical, key, cid=None):
        entry = {"logical_path": logical, "key": key,
                 "referenced_by": {"logical_path": CHARACTER, "key": cid,
                                   "reason": "角色专用 APK 依赖归属无法完整推导"}}
        if entry not in unresolved:
            unresolved.append(entry)

    def changed_key(logical, trail):
        return logical in relevant and (relevant[logical] is None or trail in relevant[logical])

    # Character-keyed tables are direct evidence, even without a complete baseline.
    for logical, keys in relevant.items():
        if logical.startswith("master/character/") and keys:
            for trail in keys:
                if trail[0] in owners:
                    affected.setdefault(trail[0], []).append({"logical_path": logical, "key": "/".join(trail)})
    try:
        characters = table(CHARACTER)
    except (KeyError, FileNotFoundError):
        missing(CHARACTER, None)
        return list(affected.items()), unresolved

    for cid in sorted(owners & characters.keys()):
        root_rows = rows(next(leaves(characters[cid]))[1])
        code = root_rows[0][0] if root_rows and root_rows[0] else ""
        for logical in relevant:
            if code and logical.startswith((f"character/{code}/", f"battle/skill/{code}/")):
                affected.setdefault(cid, []).append({"logical_path": logical})
        queue, seen = [(CHARACTER, cid)], set()
        while queue:
            logical, key = queue.pop()
            if (logical, key) in seen:
                continue
            seen.add((logical, key))
            try:
                if key is None:
                    raw = read(logical)
                    values = list(dsl_signals(parse_dsl(zlib.decompress(raw, -15))["tree"]))
                    trails = [()]
                else:
                    child = table(logical)[key]
                    trails = []
                    values = []
                    for trail, text in leaves(child, (key,)):
                        trails.append(trail)
                        values.extend(table_signals(logical, trail, text, registry=registry))
            except (KeyError, FileNotFoundError):
                missing(logical, key, cid)
                continue
            for trail in trails:
                if changed_key(logical, trail):
                    affected.setdefault(cid, []).append({"logical_path": logical, "key": "/".join(trail)})
            for kind, value in values:
                if kind == "ref" and value[1] not in {"", "(None)"}:
                    queue.append(value)
                elif kind == "optional_ref":
                    if changed_key(value[0], (value[1],)):
                        affected.setdefault(cid, []).append({"logical_path": value[0], "key": value[1]})
                elif kind == "program":
                    target = program_logical(value)
                    if target is None and str(value).startswith("battle/"):
                        target = value if value.endswith(DSL_SUFFIX) else value + DSL_SUFFIX
                    if target:
                        queue.append((target, None))
    return list(affected.items()), unresolved
