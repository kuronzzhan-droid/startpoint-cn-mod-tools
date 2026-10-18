"""Official 1006 shared-battle skeleton with isolated encounter/reward identities."""
from __future__ import annotations

import copy

from wf.view.base149 import row, join
from .edit_state import leaf
from .parameters import (QUESTS, FIELD_DATA, ZONE, columns, find_quest, apply_values,
                         leaves, validate_bgm, require_encounter)

EVENT = "master/quest/event/hard_multi_event.orderedmap"
FOLDER = "master/quest/event/event_folder_events.orderedmap"
SCORE = "master/reward/score_reward.orderedmap"
RARE = "master/reward/rare_score_reward.orderedmap"
QUEST = QUESTS["hard_multi"]
START = "2000-01-01 00:00:00"
REWARD_FILES = tuple(f"assets/{name}{suffix}.json" for name in ("score_reward", "rare_score_reward")
                     for suffix in ("", "_cnmod"))


def allocate(state, requested=None, reserved=()):
    """Reserve a free event/quest/node/reward/zone block from the actual view."""
    used_quests = {r[0] for table in QUESTS.values() for _, text in leaves(state.table(table))
                   if (r := row(text))}
    server_keys = {key for target in (*REWARD_FILES, "assets/hard_multi_event_quest.json")
                   for key in state.server(target, required=False)}
    events = state.table(EVENT)
    folders = state.table(FOLDER).get("2", {})
    if not folders:
        raise ValueError("the 终始之战 event folder 2 is absent")
    requested = dict(requested or {})
    if set(requested) - {"event", "node"}:
        raise ValueError("unknown allocation fields")
    if any(not isinstance(v, str) or not v.isdigit() or int(v) < 1 for v in requested.values()):
        raise ValueError("allocation IDs must be positive decimal strings")
    if requested.get("event") in events:
        raise ValueError("ID collision: event")
    if "event" in requested and not 2000 <= int(requested["event"]) <= 9999:
        raise ValueError("shared event ID must be 2000..9999")
    if "node" in requested and requested["node"] in folders:
        raise ValueError("ID collision: node")
    reserved_nodes = set(reserved.get("nodes", ())) if isinstance(reserved, dict) else set()
    reserved = set(reserved.get("quests", ())) if isinstance(reserved, dict) else set(reserved)
    for event in ([requested["event"]] if "event" in requested else range(2100, 10000)):
        event = str(event)
        quest = str(int(event) * 1000 + 1)
        next_node = max(map(int, set(folders) | reserved_nodes), default=0) + 1
        node = str(requested.get("node", next_node))
        zone = f"studio_shared_{event}"
        reward = str(12200000 + int(event))
        conflicts = []
        for label, occupied in (("event", event in events),
                                ("quest", quest in used_quests or quest in reserved or quest in server_keys),
                                ("node", node in folders or node in reserved_nodes), ("zone", zone in state.table(ZONE)),
                                ("field_data", zone in state.table(FIELD_DATA)),
                                ("score_reward", reward in state.table(SCORE)),
                                ("rare_score_reward", reward in state.table(RARE)),
                                ("server_reward", reward in server_keys)):
            if occupied:
                conflicts.append(label)
        if not conflicts:
            return {"event": event, "quest": quest, "node": node, "zone": zone,
                    "fieldData": zone, "reward": reward}
        if "event" in requested:
            raise ValueError("ID collision: " + ", ".join(conflicts))
    raise ValueError("no free shared-battle ID block")


def template_rows(state, request, ids):
    """Pure generation, also used to compare historical 143–145 cells."""
    name = request.get("name")
    if name is not None:
        if not isinstance(name, str) or not 1 <= len(name) <= 80:
            raise ValueError("name must contain 1..80 characters")
        if any(char in name for char in "\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029\"'“”‘’") or "::" in name:
            raise ValueError("name 不得包含换行、引号或 ::")
    kind, _, _, encounter = find_quest(state, request.get("sourceQuest", "hard_multi:1006/1"))
    require_encounter(kind, encounter)
    values = row(state.table(QUEST)["1006"]["1"])
    source_fd = encounter[columns(kind)["fieldData"][0]]
    fd = row(state.table(FIELD_DATA)[source_fd])
    zone = copy.deepcopy(state.table(ZONE)[fd[2]])
    fd[2] = ids["zone"]
    values[0] = ids["quest"]
    values[2:4] = encounter[2:4]
    if name is not None:
        values[2] = name + " ::quest_rank::"
    values[5:7] = [START, "(None)"]
    values[7:17] = ["(None)", "", "", "", "(None)", "(None)", "", "", "", "(None)"]
    element = int(encounter[columns(kind)["recommendedElement"][0]])
    defaults = {"level": 100, "hpMultiplier": 1.5, "attackMultiplier": 1.3,
                "restrictedElement": element, "recommendedElement": element,
                "bgm": encounter[columns(kind)["bgm"][0]]}
    values = apply_values(values, "hard_multi", {**defaults, **request.get("parameters", {})})
    validate_bgm(state, values[111])
    values[110], values[71] = ids["fieldData"], ids["reward"]
    if "scene" in request.get("parameters", {}):
        from .parameters import FIELD
        scene = request["parameters"]["scene"]
        if scene not in state.table(FIELD):
            raise ValueError(f"scene field does not exist: {scene}")
        fd[0] = scene
    event = row(state.table(EVENT)["1006"])
    name = values[2].replace(" ::quest_rank::", "")
    event[0], event[2] = f"studio_shared_{ids['event']}", f"共同决战【{name}】"
    event[23:26] = [START, "(None)", "(None)"]
    return {"quest": values, "event": event, "fieldData": fd, "zone": zone,
            "eventFolder": ["13", ids["event"], ids["node"]],
            "sourceQuest": request.get("sourceQuest", "hard_multi:1006/1")}


def server_quest(values):
    """Same fields consumed by the existing hard_multi_event_quest server table."""
    return {"scoreRewardGroupId": int(values[71]), "name": values[2], "clearRewardId": int(values[72]),
            "element": int(values[73]),
            **{name: int(values[col]) * scale for name, col, scale in (
                ("bRankTime", 85, 1000), ("aRankTime", 86, 1000), ("sRankTime", 87, 1000),
                ("sPlusRankTime", 88, 1000), ("characterExpReward", 94, 1),
                ("manaReward", 95, 1), ("rankPointReward", 96, 1), ("poolExpReward", 97, 1))}}


def clone_rewards(state, ids):
    source_group = row(state.table(QUEST)["1006"]["1"])[71]
    score = copy.deepcopy(state.table(SCORE)[source_group])
    files = {target: state.server(target, required=False) for target in REWARD_FILES}
    collisions = [target for target, values in files.items() if ids["reward"] in values]
    if collisions:
        raise ValueError(f"server reward ID collision: {ids['reward']}: {', '.join(collisions)}")
    merged = {**files["assets/score_reward.json"], **files["assets/score_reward_cnmod.json"]}
    if source_group not in merged:
        raise ValueError(f"server score_reward group is absent: {source_group}")
    server_rows = copy.deepcopy(merged[source_group])
    rare_ids = set()
    for text in score.values():
        values = row(text)
        if values[1] == "1":
            rare_ids.add(values[6])
    if len(rare_ids) > 1:
        raise ValueError("1006 template has more than one rare group; explicit allocation required")
    for old in rare_ids:
        rare = state.table(RARE).get(old)
        rare_server = {**files["assets/rare_score_reward.json"], **files["assets/rare_score_reward_cnmod.json"]}
        if not rare or old not in rare_server:
            raise ValueError(f"rare reward template is incomplete: {old}")
        state.set_leaf(RARE, (ids["reward"],), rare, new=True)
        state.set_server_keys("assets/rare_score_reward_cnmod.json", {ids["reward"]: rare_server[old]}, new=True)
        for key, text in score.items():
            values = row(text)
            if values[1] == "1":
                values[6] = ids["reward"]
                score[key] = join(values)
        for entry in server_rows:
            if entry.get("type") == 1:
                entry["id"] = int(ids["reward"])
    state.set_leaf(SCORE, (ids["reward"],), score, new=True)
    state.set_server_keys("assets/score_reward_cnmod.json", {ids["reward"]: server_rows}, new=True)


def create_shared(state, request, *, reserved=()):
    ids = allocate(state, request.get("ids"), reserved)
    generated = template_rows(state, request, ids)
    state.set_leaf(QUEST, (ids["event"], "1"), join(generated["quest"]), new=True)
    state.set_leaf(EVENT, (ids["event"],), join(generated["event"]), new=True)
    state.set_leaf(FIELD_DATA, (ids["fieldData"],), join(generated["fieldData"]), new=True)
    state.set_leaf(ZONE, (ids["zone"],), generated["zone"], new=True)
    state.set_leaf(FOLDER, ("2", ids["node"]), join(generated["eventFolder"]), new=True)
    clone_rewards(state, ids)
    state.set_server_keys("assets/hard_multi_event_quest.json", {ids["quest"]: server_quest(generated["quest"])}, new=True)
    return ids
