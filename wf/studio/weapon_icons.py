"""Replayable PNG imports: standalone weapon pixels and append-only item atlas."""
from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import io

from PIL import Image

from wf.boss import schema as s
from wf.boss.shop_edit import one
from wf.boss.shop_model import ITEM
from wf.view.base149 import join
from wf.tools.weapon.weapon_awaken import (ATLAS_PNG, ATLAS_MAP, decode_atlas, encode_atlas,
                                           find_slot, open_png, store_png, verify_atlas)


def _image(encoded, size):
    if not isinstance(encoded, str) or len(encoded) > 2_000_000:
        raise ValueError("icon png must be base64 PNG, at most 2000000 characters")
    try:
        raw = base64.b64decode(encoded, validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != "PNG" or image.size != size or getattr(image, "n_frames", 1) != 1:
                raise ValueError(f"icon must be a single-frame {size[0]}x{size[1]} PNG")
            image.load()
            return image.convert("RGBA")
    except (binascii.Error, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("invalid icon PNG") from exc


def _new_resource(state, logical, raw):
    before = state.raw(logical)
    if before is not None and before != raw:
        raise ValueError(f"icon content-addressed path collision: {logical}")
    state.set_raw(logical, raw, new=before is None)


def import_icon(state, spec):
    wid, kind = spec["id"], spec["kind"]
    equipment = one(state, s.EQUIPMENT, wid, 16)
    if kind not in ("weapon", "soul", "material"):
        raise ValueError("icon kind must be weapon, soul or material")
    if kind != "material" and "item_id" in spec:
        raise ValueError("item_id is only accepted for material icons")
    image = _image(spec["png"], (20, 20) if kind == "weapon" else (40, 40))
    digest = hashlib.sha256(image.tobytes()).hexdigest()[:16]
    # Distinct names leave every existing shared image and atlas entry intact.
    stem = f"studio_weapon/{wid}/{kind}_{digest}"
    if kind == "weapon":
        reference = "item/equipment/" + stem
        _new_resource(state, reference + ".png", store_png(image))
        equipment[6] = reference
        state.set_leaf(s.EQUIPMENT, [wid], join(equipment))
        return {"kind": kind, "logical": reference + ".png", "size": [20, 20], "atlasSize": None}
    item_id = spec.get("item_id") if kind == "material" else equipment[10]
    if not isinstance(item_id, str) or not item_id.isdigit() or int(item_id) <= 0:
        raise ValueError("material icon requires item_id")
    item = one(state, ITEM, item_id, 23)
    reference, thumbnail = "item/" + stem, "item_icon/" + stem
    old_entries = decode_atlas(state.read_raw(ATLAS_MAP)[0])
    old_sheet = open_png(state.read_raw(ATLAS_PNG)[0]).convert("RGBA")
    entries, sheet = copy.deepcopy(old_entries), old_sheet.copy()
    hits = [entry for entry in entries if entry.get("n") == thumbnail]
    if hits:
        if len(hits) != 1:
            raise ValueError("duplicate atlas icon name")
        entry = hits[0]
        if (entry["w"], entry["h"]) != (40, 40) or entry.get("r"):
            raise ValueError("existing icon atlas geometry differs")
        box = (entry["x"], entry["y"], entry["x"] + 40, entry["y"] + 40)
        if sheet.crop(box).tobytes() != image.tobytes():
            raise ValueError("existing icon atlas pixels differ")
    else:
        slot = find_slot(entries, sheet, image.size)
        if slot is None:
            raise ValueError("item_icon atlas has no free 40x40 slot; canvas expansion is forbidden")
        sheet.paste(image, slot)
        entries.append({"n": thumbnail, "w": 40, "h": 40, "x": slot[0], "y": slot[1]})
    problems = verify_atlas(old_entries, old_sheet, entries, sheet, {thumbnail} if not hits else set())
    if problems:
        raise ValueError("; ".join(problems))
    _new_resource(state, reference + ".png", store_png(image.resize((20, 20), Image.Resampling.NEAREST)))
    state.set_raw(ATLAS_PNG, store_png(sheet))
    state.set_raw(ATLAS_MAP, encode_atlas(entries))
    item[3], item[4] = reference, thumbnail
    state.set_leaf(ITEM, [item_id], join(item))
    return {"kind": kind, "itemId": item_id, "logical": reference + ".png",
            "thumbnail": thumbnail, "atlasSize": list(sheet.size), "size": [40, 40],
            "preservedEntries": len(old_entries)}
