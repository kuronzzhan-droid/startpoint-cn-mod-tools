"""Decode complete object-group layers, which define actual battle waves."""
from __future__ import annotations

from collections import OrderedDict
import copy
import hashlib
import threading
import zlib
import wf_dsl
from .edit_state import freeze_tree
from .terrain_objects import geometry, point

_TERRAIN_CACHE: OrderedDict[tuple[int, bytes], list[dict]] = OrderedDict()
_TERRAIN_LOCK = threading.RLock()


def _parse_waves(raw: bytes, logical: str) -> list[dict]:
    key = (len(raw), hashlib.sha256(raw).digest())
    with _TERRAIN_LOCK:
        if key in _TERRAIN_CACHE:
            _TERRAIN_CACHE.move_to_end(key)
            return copy.deepcopy(_TERRAIN_CACHE[key])
    tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
    if not isinstance(tree, dict):
        raise ValueError(f"terrain is not an object: {logical}")
    waves = []
    for layer in tree.get("layers", []):
        if layer.get("type") != "objectgroup":
            continue
        objects = layer.get("objects", [])
        positions = [{"object_id": obj.get("id"), "name": obj.get("name", ""),
                      "type": obj.get("type"), "rect": geometry(obj), "runtime_point": point(obj)}
                     for obj in objects if obj.get("name") or obj.get("type") == "CUSTOM_POSITION"]
        coffins = [{"index": index, "party": index // 3, "member": index % 3,
                    "object_id": obj.get("id"), "rect": geometry(obj), "runtime_point": point(obj)}
                   for index, obj in enumerate(o for o in objects if o.get("type") == "COFFIN")]
        waves.append({**layer, "name": str(layer.get("name", "")), "objects": objects,
                      "bounds": [geometry(o) for o in objects if o.get("type") == "BOUNDS"],
                      "coffins": coffins, "named_positions": positions,
                      "custom_positions": [p for p in positions if p["type"] == "CUSTOM_POSITION"],
                      "coffin_count": len(coffins),
                      "position_names": [o.get("name", "") for o in objects
                                         if o.get("type") == "CUSTOM_POSITION"]})
    with _TERRAIN_LOCK:
        _TERRAIN_CACHE[key] = freeze_tree(waves)
        _TERRAIN_CACHE.move_to_end(key)
        while len(_TERRAIN_CACHE) > 64:
            _TERRAIN_CACHE.popitem(last=False)
    return waves


def read_terrain(tables, logical):
    if logical and not logical.endswith(".amf3.deflate"):
        logical += ".amf3.deflate"
    raw = tables.raw(logical) if logical else None
    if raw is None:
        return {"logical": logical, "missing": True, "waves": [], "wave_count": None,
                "source": tables.citation(logical) if logical else None}
    waves = _parse_waves(raw, logical)
    return {"logical": logical, "missing": False, "waves": waves, "wave_count": len(waves),
            "source": tables.citation(logical),
            "coordinate_semantics": {"stored": "Tiled rectangle top-left in terrain pixels",
                                     "runtime": "6 * (x + width / 2), 6 * (y + height / 2)",
                                     "names": "Names are layer-local; p1/p2/p3 meanings depend on the native encounter."}}
