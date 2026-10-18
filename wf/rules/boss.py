"""Evidence-aware boss gates shared by CLI, draft preview and compilation."""
from __future__ import annotations

from .boss_atlas import atlas_check
from .boss_integrity import (both_route_check, choice_check, collision_check, prerequisite_check,
                             reward_check, shop_check, time_check)
from .boss_preload import preload_check
from .boss_levels import enemy_level_check
from .boss_terrain import concurrent_positions, terrain_checks
from .catalog import catalog, result


def check_boss(document, *, view=None, baseline=None, server_changes=None,
               server_before=None, context=None):
    """Check a BossReader.show snapshot, optionally with its actual candidate.

    ``view`` accepts ManifestView.read_raw or prepush View.raw/table. Server
    mappings contain complete JSON file bytes, using the same paths and merge
    semantics as M2.1. ``baseline`` is the before snapshot for element changes.
    ``context`` supplies authoring intent, never a substitute for resource
    checks: custom_content, choice_count/choice_level, new_ids/existing_ids and
    atlas_budget (three party PNG path lists and enemy_sheets), and an explicit
    acknowledgePreload=True waiver for unproven (never known-bad) preloads.
    """
    if not isinstance(document, dict) or not isinstance(document.get("quest"), dict):
        raise ValueError("boss check requires a BossReader.show document with quest")
    context = context or {}
    checks = [*terrain_checks(document, view=view), concurrent_positions(document), enemy_level_check(document),
              preload_check(document, view=view, baseline=baseline, context=context), choice_check(context),
              both_route_check(document, view, context), time_check(document, context),
              reward_check(view, server_changes, server_before),
              shop_check(document, view, server_changes, server_before),
              atlas_check(view, context), prerequisite_check(document, context), collision_check(context)]
    by_id = {entry["rule"]: entry for entry in checks}
    rules = catalog()
    for metadata in rules["rules"]:
        identifier = metadata["id"]
        if "boss" not in metadata["scope"] and identifier not in by_id:
            continue
        if identifier not in by_id:
            by_id[identifier] = result(identifier, "未执行", "此项需要独立的行为或客户端能力证据")
        by_id[identifier].update(evidence_nature=metadata["evidence_nature"],
                                 source=metadata["source"], rule_version=rules["version"])
    return list(by_id.values())


def assert_boss(document, **options):
    """Return all five-state results or reject genuine blocking findings."""
    checks = check_boss(document, **options)
    blocked = [entry for entry in checks if entry["blocking"]]
    if blocked:
        raise ValueError("boss check blocked: " + "; ".join(f"{e['rule']}: {e['message']}" for e in blocked))
    return checks
