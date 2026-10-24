"""Export selected native game atlas sprites without publishing atlas metadata."""
import io
import json
import zlib
from pathlib import Path

import wf_assets
import wf_dsl
from PIL import Image


def crop_sprite(sheet, entry):
    x, y, w, h = (int(entry[k]) for k in ("x", "y", "w", "h"))
    if min(x, y) < 0 or min(w, h) <= 0 or x + w > sheet.width or y + h > sheet.height:
        raise ValueError("原生 UI 图集裁切越界")
    sprite = sheet.crop((x, y, x + w, y + h))
    if entry.get("r"):
        sprite = sprite.transpose(Image.Transpose.ROTATE_90)
    restored = Image.new("RGBA", (int(entry.get("fw", sprite.width)), int(entry.get("fh", sprite.height))))
    restored.paste(sprite, (-int(entry.get("fx", 0)), -int(entry.get("fy", 0))))
    return restored


def atlas_entries(tree):
    if isinstance(tree, dict):
        if all(k in tree for k in ("n", "x", "y", "w", "h")):
            yield tree
        else:
            for child in tree.values():
                yield from atlas_entries(child)
    elif isinstance(tree, list):
        for child in tree:
            yield from atlas_entries(child)


def export_ui_assets(media):
    spec = json.loads((Path(__file__).parent / "wiki-ui-assets.json").read_text(encoding="utf-8"))
    sheets, atlases, result, slices = {}, {}, {}, {}
    for item in spec:
        sheet_path, atlas_path = item["sheetLogical"], item["atlasLogical"]
        if sheet_path not in sheets:
            raw = media._read(sheet_path)
            if raw is None:
                raise ValueError("缺少原生 UI 图集")
            picture = Image.open(io.BytesIO(wf_assets.png_decode(raw))).convert("RGBA")
            sheets[sheet_path] = raw, picture
        if atlas_path not in atlases:
            raw = media._read(atlas_path)
            if raw is None:
                raise ValueError("缺少原生 UI 图集索引")
            tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
            atlases[atlas_path] = raw, {entry["n"]: entry for entry in atlas_entries(tree)}
        sheet_raw, picture = sheets[sheet_path]
        atlas_raw, entries = atlases[atlas_path]
        sprite = crop_sprite(picture, entries[item["textureName"]])
        stream = io.BytesIO()
        sprite.save(stream, "WEBP", lossless=True, method=4)
        logical = "wiki-ui/" + item["group"] + "/" + item["key"]
        url = media._save(logical, sheet_raw + atlas_raw, stream.getvalue(), ".webp",
                          width=sprite.width, height=sprite.height)
        result.setdefault(item["group"], {})[item["key"]] = url
        if item.get("cssBorderImageSliceTopRightBottomLeft"):
            slices.setdefault(item["group"], {})[item["key"]] = item["cssBorderImageSliceTopRightBottomLeft"]
    result["slices"] = slices
    return result
