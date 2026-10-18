"""Decode complete object-group layers, which define actual battle waves."""
from __future__ import annotations

import zlib
import wf_dsl


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
        waves.append({**layer, "name": str(layer.get("name", "")), "objects": objects,
                      "coffin_count": sum(o.get("type") == "COFFIN" for o in objects),
                      "position_names": [o.get("name", "") for o in objects
                                         if o.get("type") == "CUSTOM_POSITION"]})
    return {"logical": logical, "missing": False, "waves": waves, "wave_count": len(waves),
            "source": tables.citation(logical)}
