"""Lossless terrain loading and explicit native coordinate conventions."""
from __future__ import annotations

import copy
import math
import re
import zlib

import wf_dsl


def logical_path(value):
    if not isinstance(value, str) or not re.fullmatch(r"battle/terrain/[A-Za-z0-9_./-]+", value):
        raise ValueError("terrain must be an existing battle/terrain logical path")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError("invalid terrain logical path")
    return value if value.endswith(".amf3.deflate") else value + ".amf3.deflate"


def decode(raw):
    tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
    if not isinstance(tree, dict) or not isinstance(tree.get("layers"), list):
        raise ValueError("terrain must contain a layers array")
    return tree


def encode(tree):
    data = wf_dsl.encode_amf3(tree)
    compressor = zlib.compressobj(wbits=-15)
    raw = compressor.compress(data) + compressor.flush()
    if decode(raw) != tree:
        raise ValueError("terrain AMF3 roundtrip mismatch")
    return raw


def groups(tree):
    return [layer for layer in tree["layers"] if layer.get("type") == "objectgroup"]


def layer(tree, name):
    found = [entry for entry in groups(tree) if str(entry.get("name")) == str(name)]
    if len(found) != 1:
        raise ValueError(f"terrain layer {name}: expected one objectgroup, got {len(found)}")
    return found[0]


def objects(group, token):
    return [obj for obj in group.get("objects", []) if obj.get("type") == token]


def bounds(group):
    found = objects(group, "BOUNDS")
    if len(found) != 1:
        raise ValueError("terrain layer needs exactly one BOUNDS (C14102/C10000)")
    return found[0]


def geometry(value):
    return {key: value.get(key, 0) for key in ("x", "y", "width", "height")}


def point(value):
    box = geometry(value)
    return {"x": 6 * (box["x"] + box["width"] / 2),
            "y": 6 * (box["y"] + box["height"] / 2)}


def next_id(tree):
    return max((obj.get("id", 0) for group in groups(tree)
                for obj in group.get("objects", []) if type(obj.get("id", 0)) is int), default=0) + 1


def fresh_objects(tree, incoming):
    result = copy.deepcopy(incoming)
    first = next_id(tree)
    for index, obj in enumerate(result):
        obj["id"] = first + index
    if "nextobjectid" in tree:
        tree["nextobjectid"] = first + len(result)
    return result


def coordinate(value, *, size=False):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1_000_000:
        raise ValueError("terrain coordinate must be a finite number in -1000000..1000000")
    if size and value < 0:
        raise ValueError("terrain width/height must be nonnegative")
    return value


def move_to_bounds(obj, source, target):
    moved = copy.deepcopy(obj)
    for axis in ("x", "y"):
        moved[axis] = obj.get(axis, 0) + target.get(axis, 0) - source.get(axis, 0)
    return moved
