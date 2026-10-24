"""Read-only kind-629 reachability gate shared by balance and deliver."""
from __future__ import annotations

import zlib

import wf_mod_tool as codec
import wf_quest_lib as nodes
from wf_dsl import parse_dsl

from .references import (ABILITY_TABLES, ACTION_SKILL, DSL_SUFFIX,
                         ability_references, linked_programs, resolve_programs)
from .sanitize import forbidden_629


def check_629_actions(read_raw, *, overrides=None, changed_logicals=None):
    """Check affected 629 roots and all their transitive action-program calls.

    ``read_raw(logical)`` returns bytes or ``(bytes, source)``. Overrides contain
    candidate bytes keyed by logical path. With no changed_logicals all roots
    are checked. Otherwise table key diffs, skill key diffs and transitively
    changed DSL members select roots; unchanged unrelated legacy trees cannot
    block an independent edit. Missing data for a selected root is an error.
    """
    overrides = overrides or {}
    changed = None if changed_logicals is None else set(changed_logicals)
    relevant = set(ABILITY_TABLES) | {ACTION_SKILL}
    report = {"status": "满足", "findings": [], "checked_programs": [], "references": []}
    if changed is not None and not any(p in relevant or p.endswith(DSL_SUFFIX) for p in changed):
        report["status"] = "不适用"
        return report

    def read(logical, *, original=False):
        raw = read_raw(logical) if original or logical not in overrides else overrides[logical]
        return raw[0] if isinstance(raw, tuple) else raw

    def table(logical, *, original=False):
        raw = read(logical, original=original)
        # parse_node treats a zero-key orderedmap as an unknown leaf.
        ordered = codec.read_orderedmap_raw_rows_from_bytes(raw, logical)
        data = nodes.parse_node(raw) if ordered.keys else {}
        if not isinstance(data, dict):
            raise ValueError(f"{logical}: expected an orderedmap")
        return data

    def problem(message, **context):
        report["findings"].append({"rule": "dsl.629-lifecycle", "status": "问题",
                                   "message": message, **context})

    refs, tables, changed_keys = [], {}, {}
    for logical in ABILITY_TABLES:
        try:
            data = table(logical)
        except (FileNotFoundError, KeyError):
            if (logical in overrides or logical in (changed or ())
                    or ABILITY_TABLES[logical] in {"ability", "leader_ability"}):
                problem(f"629 gate cannot read ability table: {logical}")
            continue
        except (ValueError, TypeError, IndexError, zlib.error) as error:
            problem(f"629 gate cannot read ability table {logical}: {error}")
            continue
        tables[logical] = data
        try:
            refs.extend(ability_references(logical, data))
            if changed is not None and logical in changed:
                try:
                    old = table(logical, original=True)
                except (FileNotFoundError, KeyError):
                    old = {}
                changed_keys[logical] = {key for key, value in data.items() if old.get(key) != value}
        except (ValueError, TypeError, IndexError, zlib.error) as error:
            problem(str(error))
    if not tables:
        problem("629 gate cannot infer callers: no ability tables available")
    skills = None
    skill_keys = set()
    if any(r["action"] in {"", "(None)"} for r in refs) or ACTION_SKILL in (changed or ()):
        try:
            skills = table(ACTION_SKILL)
            if changed is not None and ACTION_SKILL in changed:
                try:
                    old = table(ACTION_SKILL, original=True)
                except (FileNotFoundError, KeyError):
                    old = {}
                skill_keys = {key for key in old.keys() | skills.keys() if old.get(key) != skills.get(key)}
        except (FileNotFoundError, KeyError, ValueError, TypeError, IndexError, zlib.error) as error:
            problem(f"629 gate cannot read action_skill: {error}")

    cache = {}

    def graph(logical, seen):
        if logical in seen:
            return
        seen.add(logical)
        if logical not in cache:
            try:
                tree = parse_dsl(zlib.decompress(read(logical), -15))["tree"]
                if not isinstance(tree, list) or not tree or tree[0] != "ActionDsl":
                    raise ValueError("root is not ActionDsl")
                cache[logical] = (tree, None)
            except (FileNotFoundError, KeyError, ValueError, TypeError, IndexError, zlib.error) as error:
                cache[logical] = (None, str(error))
        tree, error = cache[logical]
        if error is None:
            for child in sorted(linked_programs(tree)):
                graph(child, seen)

    checked = set()
    changed_dsl = {p for p in changed or () if p.endswith(DSL_SUFFIX)}
    for reference in refs:
        selected = (changed is None or reference["key"] in changed_keys.get(reference["table"], ())
                    or reference["skill"] in skill_keys)
        if not selected and not changed_dsl:
            continue
        try:
            roots = resolve_programs(reference, skills or {})
        except ValueError as error:
            if selected or changed_dsl:
                problem(str(error), reference=reference)
            continue
        reachable = set()
        for logical in roots:
            graph(logical, reachable)
        if not selected and not reachable.intersection(changed or ()):
            # A broken root/intermediate node can hide the changed descendant.
            # Without its complete closure we cannot certify non-reachability.
            if not changed_dsl or not any(cache[p][1] is not None for p in reachable):
                continue
        report["references"].append({**reference, "programs": sorted(reachable)})
        for logical in sorted(reachable - checked):
            checked.add(logical)
            tree, error = cache[logical]
            if error is not None:
                problem(f"629 action dependency cannot be read: {error}", logical_path=logical)
                continue
            for finding in forbidden_629(tree):
                problem(f"能力动作含真实 PF 生命周期命令: {finding['command']}",
                        logical_path=logical, **finding)
    report["checked_programs"] = sorted(checked)
    if report["findings"]:
        report["status"] = "问题"
    return report
