"""Quest-owned terrain edits, preserving shared resources and native positions."""
from __future__ import annotations

import copy
import re

import wf_quest_lib as codec
from wf.view.base149 import join
from . import schema as s
from .edit_state import leaf
from .parameters import columns, find_quest, require_encounter
from .reader import BossReader
from .terrain_identity import terrain_identity
from .terrain_objects import (bounds, coordinate, decode, encode, fresh_objects, groups,
                              layer, logical_path, move_to_bounds, objects, require_within_bounds)

OPERATIONS = {"terrain_replace", "terrain_position", "terrain_add_layer"}


def _owned_row(state, logical, identity, current, value):
    existing = leaf(state.table(logical), (identity,))
    original = state.original.get(logical)
    introduced = any(change["table"] == logical and change["path"] == [identity]
                     and change["old"] is None for change in state.changes)
    if existing is not None and (leaf(codec.parse_node(original), (identity,)) is not None
                                 or identity != current and not introduced):
        raise ValueError(f"ID collision: {logical}/{identity}")
    state.set_leaf(logical, (identity,), value, new=existing is None)


def _read(state, quest):
    kind, logical, path, values = find_quest(state, quest)
    require_encounter(kind, values)
    doc = BossReader(state).show(f"{kind}:{'/'.join(path)}")
    if any(doc[name].get("missing") for name in ("field_data", "field", "zone", "terrain")):
        raise ValueError("terrain edit requires complete field_data/field/zone/terrain references")
    return kind, logical, path, values, doc


def _replace(state, current, document, request):
    logical = logical_path(request["terrain"])
    raw = state.raw(logical)
    if raw is None:
        raise ValueError(f"existing terrain is absent: {logical}")
    tree = decode(raw)
    if {str(w["name"]) for w in groups(tree)} != {str(w["name"]) for w in groups(current)}:
        raise ValueError("replacement terrain layers must match existing zone waves; use terrain_add_layer")
    # Native p1/p2 names are not universal meanings. Preserve this encounter's
    # points relative to BOUNDS instead of silently adopting a host's p1. Keep
    # every original point: StandardBoss/DSL may refer to names indirectly.
    for old in groups(current):
        wave = str(old["name"])
        new = layer(tree, wave)
        old_positions = {o.get("name"): o for o in objects(old, "CUSTOM_POSITION")}
        if len(old_positions) != len(objects(old, "CUSTOM_POSITION")):
            raise ValueError(f"existing terrain contains duplicate CUSTOM_POSITION in layer {wave}")
        for name in old_positions:
            replacement = move_to_bounds(old_positions[name], bounds(old), bounds(new))
            require_within_bounds(replacement, bounds(new), layer_name=wave)
            matches = [o for o in objects(new, "CUSTOM_POSITION") if o.get("name") == name]
            if len(matches) > 1:
                raise ValueError(f"replacement contains duplicate CUSTOM_POSITION {wave}/{name}")
            if matches:
                matches[0].update({key: replacement.get(key, 0) for key in ("x", "y", "width", "height")})
            else:
                new["objects"].extend(fresh_objects(tree, [replacement]))
    return tree


def _position(tree, request):
    name = request["name"]
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", name):
        raise ValueError("CUSTOM_POSITION name must contain only letters, digits, underscore or hyphen")
    group = layer(tree, request["layer"])
    matches = [o for o in objects(group, "CUSTOM_POSITION") if o.get("name") == name]
    action = request["action"]
    if action == "add":
        if not all(key in request for key in ("x", "y")):
            raise ValueError("CUSTOM_POSITION add requires both x and y")
        if matches:
            raise ValueError(f"CUSTOM_POSITION already exists: {name}")
        obj = {"type": "CUSTOM_POSITION", "name": name, "visible": True,
               "x": 0, "y": 0, "width": 16, "height": 16, "rotation": 0, "ellipse": True}
        obj = fresh_objects(tree, [obj])[0]
        group["objects"].append(obj)
    else:
        if len(matches) != 1:
            raise ValueError(f"CUSTOM_POSITION {name}: expected one match, got {len(matches)}")
        obj = matches[0]
    if action == "delete":
        group["objects"].remove(obj)
    elif action in {"add", "update"}:
        for key in ("x", "y", "width", "height"):
            if key in request:
                obj[key] = coordinate(request[key], size=key in {"width", "height"})
        require_within_bounds(obj, bounds(group), layer_name=str(group["name"]))
    else:
        raise ValueError(f"unknown position action: {action}")
    return tree


def _append(state, tree, document, request, identity):
    source = _read(state, request["sourceQuest"])[-1]
    if source["quest"]["fields"].get("recommended_element") != document["quest"]["fields"].get("recommended_element"):
        raise ValueError("新增层来源与目标推荐属性不同，不能沿用来源遭遇的预载假设（C8016）；请选同推荐属性来源")
    source_tree = decode(state.raw(source["terrain"]["logical"]))
    incoming = copy.deepcopy(layer(source_tree, request["sourceLayer"]))
    waves = groups(tree)
    names = {str(w["name"]) for w in waves}
    if names != {str(n) for n in range(len(waves))}:
        raise ValueError("append requires contiguous terrain layers 0..N-1")
    previous = layer(tree, str(len(waves) - 1))
    donor = _read(state, request.get("transitionSourceQuest", request["sourceQuest"]))[-1]
    exits = next((w for w in donor["terrain"]["waves"]
                  if objects(w, "GATE") and objects(w, "TRANSIT")), None)
    field = list(document["field"]["row"])
    while len(field) < 9:
        field.append("(None)")
    for column in (7, 8):
        if not s.present(field[column]):
            value = s.cell(donor["field"]["row"], column)
            if not s.present(value):
                raise ValueError("transition source lacks field c7/c8 (C8251)")
            field[column] = value
    for token in ("GATE", "TRANSIT"):
        if not objects(previous, token):
            if exits is None:
                raise ValueError(f"transition source lacks {token}")
            added = [move_to_bounds(obj, bounds(exits), bounds(previous)) for obj in objects(exits, token)]
            previous["objects"].extend(fresh_objects(tree, added))
    incoming["name"] = str(len(waves))
    incoming["objects"] = fresh_objects(tree, [obj for obj in incoming["objects"]
                                                   if obj.get("type") not in {"GATE", "TRANSIT"}])
    tree["layers"].append(incoming)
    # Zone c0 is the native zone-kind, not the wave index: preserve it verbatim.
    source_zone = leaf(state.table(s.ZONE), (source["zone"]["id"], str(request["sourceLayer"])))
    if not isinstance(source_zone, str):
        raise ValueError("source layer lacks a zone row")
    zone = copy.deepcopy(state.table(s.ZONE)[document["zone"]["id"]])
    if incoming["name"] in zone:
        raise ValueError("new wave collides with an existing zone row")
    zone[incoming["name"]] = source_zone
    _owned_row(state, s.ZONE, identity, document["zone"]["id"], zone)
    _owned_row(state, s.FIELD, identity, document["field"]["id"], join(field))
    return tree


def apply_terrain(state, quest, request):
    """Apply one request to an in-memory overlay; never write the source view."""
    operation = request["operation"]
    if operation not in OPERATIONS:
        raise ValueError(f"unsupported terrain operation: {operation}")
    kind, logical, path, values, document = _read(state, quest)
    selector = document["quest"]["selector"]
    identity, target = terrain_identity(state, selector, document["terrain"]["logical"])
    tree = decode(state.raw(document["terrain"]["logical"]))
    before_tree = copy.deepcopy(tree)
    if operation == "terrain_replace":
        tree = _replace(state, tree, document, request)
    elif operation == "terrain_position":
        tree = _position(tree, request)
    else:
        tree = _append(state, tree, document, request, identity)
    if tree == before_tree and operation != "terrain_add_layer":
        return [selector]
    existing = state.raw(target)
    if existing is not None and (target != document["terrain"]["logical"] or state.original.get(target) is not None):
        raise ValueError(f"ID collision: terrain/{target}")
    state.set_raw(target, encode(tree), new=existing is None)
    fd = list(document["field_data"]["row"])
    fd[1] = target.removesuffix(".amf3.deflate")
    if operation == "terrain_add_layer":
        fd[0] = fd[2] = identity
    _owned_row(state, s.FIELD_DATA, identity, document["field_data"]["id"], join(fd))
    values[columns(kind)["fieldData"][0]] = identity
    state.set_leaf(logical, path, join(values))
    return [selector]
