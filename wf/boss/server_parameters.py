"""Keep server reward element selection aligned with edited quest metadata."""
from __future__ import annotations

import copy


QUEST_FILES = {
    "boss_battle": ("assets/boss_battle_quest.json", "assets/boss_battle_quest_cnmod.json"),
    "hard_multi": ("assets/hard_multi_event_quest.json",),
}


def sync_recommended_element(state, kind, identity, element):
    targets = QUEST_FILES.get(kind)
    if targets is None:
        return  # Practice quests have no server reward table in this editor.
    tables = {target: state.server(target, required=False) for target in targets}
    owner = next((target for target in reversed(targets) if identity in tables[target]), None)
    if owner is None:
        raise ValueError(f"server quest is absent; cannot sync recommended element: {kind}:{identity}")
    entry = copy.deepcopy(tables[owner][identity])
    if not isinstance(entry, dict):
        raise ValueError(f"server quest entry must be an object: {owner}/{identity}")
    if entry.get("element") == element:
        return
    entry["element"] = element
    state.set_server_keys(owner, {identity: entry})
