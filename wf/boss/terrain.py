"""Decode complete object-group layers, which define actual battle waves."""
from __future__ import annotations

import zlib
import wf_dsl
from .terrain_objects import geometry, point


def read_terrain(tables, logical):
    if logical and not logical.endswith(".amf3.deflate"):
        logical += ".amf3.deflate"
    raw = tables.raw(logical) if logical else None
    if raw is None:
        return {"logical": logical, "missing": True, "waves": [], "wave_count": None,
                "source": tables.citation(logical) if logical else None}
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
    return {"logical": logical, "missing": False, "waves": waves, "wave_count": len(waves),
            "source": tables.citation(logical),
            "coordinate_semantics": {"stored": "Tiled rectangle top-left in terrain pixels",
                                     "runtime": "6 * (x + width / 2), 6 * (y + height / 2)",
                                     "names": "Names are layer-local; p1/p2/p3 meanings depend on the native encounter."}}
