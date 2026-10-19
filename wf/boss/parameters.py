"""Quest parameter edits using generated *QuestValues column layouts."""
from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
import wf_quest_lib as codec

from wf.view.base149 import row, join
from .edit_state import leaf
from .schema import cell
from .server_parameters import sync_recommended_element

QUESTS = {
    "boss_battle": "master/quest/boss_battle_quest.orderedmap",
    "hard_multi": "master/quest/event/hard_multi_event_quest.orderedmap",
    "practice": "master/quest/practice/practice_quest.orderedmap",
}
FIELD_DATA = "master/battle/field_data.orderedmap"
ZONE = "master/battle/zone.orderedmap"
FIELD = "master/battle/field.orderedmap"
BGM_GROUP = "master/battle/asset/battle_bgm_group.orderedmap"


def leaves(node, path=()):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from leaves(value, path + (key,))


def find_quest(state, quest):
    hits = []
    for kind, logical in QUESTS.items():
        for path, text in leaves(state.table(logical)):
            values = row(text)
            identity = path[-1] if kind == "practice" else values[0] if values else None
            selectors = {identity, f"{kind}:{'/'.join(path)}", f"{kind}:{identity}"}
            if str(quest) in selectors:
                hits.append((kind, logical, path, values))
    if len(hits) != 1:
        raise ValueError(f"quest {quest}: expected one match, got {len(hits)}; practice uses its leaf key")
    return hits[0]


def columns(kind):
    offset = 0 if kind == "boss_battle" else 1
    return {"level": [106 + offset], "hpMultiplier": list(range(97 + offset, 100 + offset)),
            "attackMultiplier": list(range(100 + offset, 103 + offset)),
            "restrictedElement": [68 + offset], "recommendedElement": [72 + offset],
            "bgm": [110 + offset], "fieldData": [109 + offset], "reward": [70 + offset]}


def require_encounter(kind, values):
    if kind == "boss_battle" and cell(values, 122).lower() == "true":
        raise ValueError("BothBoss 入口自身不是战斗内容，禁止参数编辑或作为模板来源；请选 maps 指向的隐藏关")


def number(value):
    try:
        value = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("boss numeric parameter is invalid") from exc
    if not value.is_finite() or not 0 < value <= 2147483647:
        raise ValueError("boss numeric parameters must be finite, positive and <= 2147483647")
    return format(value.normalize(), "f")


def validate_bgm(state, value):
    # BattleQuestBaseImpl.getBgmGroup resolves this value through the master,
    # whose row then selects the actual normal / boss / transition audio.
    if value not in state.table(BGM_GROUP):
        raise ValueError(f"BGM group is absent from this view: {value}")


def apply_values(values, kind, parameters):
    values = list(values)
    mapping = columns(kind)
    for key, value in parameters.items():
        if key == "scene":
            continue
        if key not in mapping or key in {"fieldData", "reward"}:
            raise ValueError(f"unsupported boss parameter: {key}")
        if key in {"restrictedElement", "recommendedElement"}:
            if value is None and key == "restrictedElement":
                text = "(None)"
            elif type(value) is not int or value not in range(6):
                raise ValueError(f"{key}: expected element 0..5")
            else:
                text = str(value)
        elif key == "bgm":
            if not isinstance(value, str) or not value or ".." in value or "\\" in value:
                raise ValueError("bgm requires an existing BGM group ID")
            text = value
        else:
            text = number(value)
            if key == "level" and (Decimal(text) != int(Decimal(text)) or int(text) > 999):
                raise ValueError("level must be an integer in 1..999")
        for column in mapping[key]:
            values[column] = text
    return values


def edit_parameters(state, quest, request):
    kind, logical, path, values = find_quest(state, quest)
    require_encounter(kind, values)
    parameters = request.get("parameters", {})
    tier_values = request.get("tiers")
    if not parameters and not tier_values:
        raise ValueError("edit needs parameters or five tiers")
    targets = [(path, values, parameters)]
    if tier_values is not None:
        if kind != "boss_battle" or len(tier_values) != 5:
            raise ValueError("five tiers require a boss_battle group with exactly five quests")
        group = leaf(state.table(logical), path[:-1])
        if not isinstance(group, dict) or set(group) != {"1", "2", "3", "4", "5"}:
            raise ValueError("the selected boss group is not a five-tier encounter")
        targets = [(path[:-1] + (str(i),), row(group[str(i)]), {**parameters, **extra})
                   for i, extra in enumerate(tier_values, 1)]
    for _, before, _ in targets:
        require_encounter(kind, before)
    changed_ids = []
    for target, before, params in targets:
        after = apply_values(before, kind, params)
        element_column = columns(kind)["recommendedElement"][0]
        if after[element_column] != before[element_column]:
            sync_recommended_element(state, kind, before[0], int(after[element_column]))
        if "scene" in params:
            scene = params["scene"]
            if scene not in state.table(FIELD):
                raise ValueError(f"scene field does not exist: {scene}")
            # Give this quest its own field_data identity; no other owner is edited.
            fd = row(state.table(FIELD_DATA)[before[columns(kind)["fieldData"][0]]])
            identity = target[-1] if kind == "practice" else before[0]
            new_fd = f"studio_boss_{kind}_{identity}_scene"
            exists = new_fd in state.table(FIELD_DATA)
            owned = (new_fd not in codec.parse_node(state.original[FIELD_DATA])
                     and any(c["table"] == FIELD_DATA and c["path"] == [new_fd]
                             and c["old"] is None for c in state.changes))
            if exists and not owned:
                raise ValueError(f"ID collision: field_data/{new_fd}")
            fd[0] = scene
            state.set_leaf(FIELD_DATA, (new_fd,), join(fd), new=not exists)
            after[columns(kind)["fieldData"][0]] = new_fd
        if "bgm" in params:
            validate_bgm(state, params["bgm"])
        state.set_leaf(logical, target, join(after))
        changed_ids.append(f"{kind}:{'/'.join(target)}")
    return changed_ids
