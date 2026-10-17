"""Production primitives extracted from wf_campus_art.py (C baseline)."""
from __future__ import annotations
import copy


from PIL import Image


import wf_atf


from wf.chars.support import images as images


from wf.chars.support import images as wf_canary_skin


import wf_dsl


import wf_mod_tool as core


import wf_quest_lib as tables


def patch_tables(package, cid, ui, geometry):
    changes = {
        "master/generated/character_image.orderedmap": {cid: {
            str(n): f"{g['x']},{g['y']},{g['width']},{g['height']}" for n, g in enumerate(geometry)}},
        "master/character/full_shot_image_attribute.orderedmap": {cid: {
            str(n): "1000,1000,1,1000,500" for n in (0, 1)}},
        "master/generated/trimmed_image.orderedmap": {
            **{ui + f"full_shot_1440_1920_{n}": f"{g['x']},{g['y']},2000,2000" for n, g in enumerate(geometry)},
            **{ui + f"skill_cutin_{n}": "0,0,1024,512" for n in (0, 1)}},
    }
    result = {}
    for logical, rows in changes.items():
        path = package / "roots/common" / logical
        tree = tables.load_table(logical, path=path)
        original = copy.deepcopy(tree)
        raw = core.read_orderedmap_file_raw_rows(path, logical)
        for key, value in rows.items():
            if key not in raw.keys:
                raise ValueError(f"candidate did not already own artwork key: {logical}:{key}")
            raw.rows[raw.keys.index(key)] = tables.build_node(value)
        tree.update(rows)
        blob = core.build_orderedmap_raw_rows(raw)
        if tables.parse_node(blob) != tree or any(tree[k] != v for k, v in original.items() if k not in rows):
            raise ValueError("foreign portrait table key changed")
        result["common/" + logical] = blob
    return result


def atlas_sheet(package, ui, fulls):
    atlas_rel = "common/" + ui + "illustration_setting_sprite_sheet.atlas.amf3.deflate"
    atlas = wf_dsl.parse_dsl(wf_atf.inflate((package / "roots" / atlas_rel).read_bytes()))["tree"]
    sheet_rel = "medium/" + ui + "illustration_setting_sprite_sheet.png"
    sheet = Image.new("RGBA", images.read_png(package / "roots" / sheet_rel).size)
    for item in atlas:
        level = int(item["n"].rsplit("_", 1)[1])
        rotated = bool(item.get("r", False))
        fit_size = (item["h"], item["w"]) if rotated else (item["w"], item["h"])
        tile = wf_canary_skin.fit_rgba(fulls[level], fit_size)
        if rotated:
            # Starling SubTexture stores a rotated region clockwise (see
            # wf_pixelart_vfx.restore_frame, which undoes it with a
            # counter-clockwise ROTATE_90); re-rotating our correctly
            # oriented tile clockwise (ROTATE_270) reproduces that storage
            # orientation. Same convention already shipped in
            # wf_summer_bai_pixel_reference.build.
            tile = tile.transpose(Image.Transpose.ROTATE_270)
        sheet.alpha_composite(tile, (item["x"], item["y"]))
    return sheet_rel, sheet
