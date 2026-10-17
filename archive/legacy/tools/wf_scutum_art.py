"""从作者提供的透明立绘派生盾牌座 UI；保留原图和完整地面。"""
import io
import hashlib
import json
import zlib

import numpy as np
from PIL import Image

import wf_assets
import wf_atf
import wf_campus_art_images as art
import wf_canary_skin
import wf_dsl
import wf_quest_lib as tables
import wf_ui_derive_gate as gate
from wf_scutum_seed import CID, CODE

SOURCES = ("f3c5e2f3086e393733049aec82169e9f.png", "af35462655b6ebd2333d3392f05bfe97.png")
LANDMARKS = (
    dict(face=(1410, 530), eyes=(1410, 530), square_height=950, head_height=550),
    dict(face=(770, 570), eyes=(770, 570), square_height=630, head_height=420),
)


def native_image(seed, tier, logical):
    return Image.open(io.BytesIO(wf_assets.png_decode(seed.outputs[tier, logical]))).convert("RGBA")


def build(seed, source_dir, output):
    output.mkdir(parents=True, exist_ok=True)
    ui = f"character/{CODE}/ui/"
    fulls, geometry, previews, records = [], [], {}, []
    mask_dir = seed.repo / "work/cp/_scripts"
    cache = np.load(mask_dir / "official_shape_masks.npz")
    modes = json.loads((mask_dir / "_official_cache/mask_modes.json").read_bytes())
    masks = {slot: cache[slot] for slot in gate.SHAPE_SLOTS}
    for slot, mask in masks.items():
        signature = hashlib.sha1(mask.tobytes()).hexdigest()[:12] + f"_{mask.shape}"
        if signature != modes[slot][0][0]:
            raise ValueError(f"official modal mask drift: {slot}")
    for level, filename in enumerate(SOURCES):
        raw = (source_dir / filename).read_bytes()
        source = Image.open(io.BytesIO(raw)).convert("RGBA")
        pixels = np.asarray(source).copy()
        # 原图的浅灰抠图余边已低透明；只清理该颜色，人物实色不动。
        matte = (pixels[:, :, :3] == 211).all(axis=2) & (pixels[:, :, 3] < 240)
        pixels[matte, 3] = 0
        source = Image.fromarray(pixels)
        source.save(output / f"source-clean-{level}.png")
        full, geom = art.full_shot(source, LANDMARKS[level]["eyes"])
        fulls.append(full)
        geometry.append(geom)
        seed.emit("medium", ui + f"full_shot_1440_1920_{level}.png", wf_assets.png_encode(art.png(full)))
        icons = art.make_icons(source, LANDMARKS[level], masks, "celtie")
        icons["skill_cutin"] = art.make_cutin(source, LANDMARKS[level])
        problems = gate.derived_icon_problems(icons, masks, level=str(level))
        if problems:
            raise ValueError(problems)
        for slot, icon in icons.items():
            seed.emit("medium", ui + f"{slot}_{level}.png", wf_assets.png_encode(art.png(icon)))
            previews[f"{slot}_{level}"] = icon
        logical = ui + f"skill_cutin_{level}.atf.deflate"
        template = wf_atf.inflate(seed.outputs["android", logical])
        atf = wf_atf.build_cutin_atf(art.png(icons["skill_cutin"]), template)
        info = wf_atf.parse_atf(atf)
        if (info["w"], info["h"], info["mips"]) != (1024, 512, 11):
            raise ValueError("cutin ATF geometry mismatch")
        seed.emit("android", logical, wf_atf.deflate(atf))
        records.append(dict(source=str(source_dir / filename), sha256=art.sha(raw),
                            cleanup_alpha_only=True, cleaned_pixels=int(matte.sum()), geometry=geom))
    logical = ui + "illustration_setting_sprite_sheet.atlas.amf3.deflate"
    atlas = wf_dsl.parse_dsl(zlib.decompress(seed.outputs["common", logical], -15))["tree"]
    logical = ui + "illustration_setting_sprite_sheet.png"
    sheet = Image.new("RGBA", native_image(seed, "medium", logical).size)
    for item in atlas:
        if item.get("r"):
            raise ValueError("unexpected rotated illustration atlas")
        level = int(item["n"].rsplit("_", 1)[1])
        sheet.alpha_composite(wf_canary_skin.fit_rgba(fulls[level], (item["w"], item["h"])), (item["x"], item["y"]))
    seed.emit("medium", logical, wf_assets.png_encode(art.png(sheet)))
    seed.table("master/generated/character_image.orderedmap", {CID: tables.build_node({
        str(n): f"{g['x']},{g['y']},{g['width']},{g['height']}" for n, g in enumerate(geometry)})}, "raw_outer")
    seed.table("master/character/full_shot_image_attribute.orderedmap", {
        CID: tables.build_node({str(n): "1000,1000,1,1000,500" for n in (0, 1)})}, "raw_outer")
    seed.table("master/generated/trimmed_image.orderedmap", {
        **{ui + f"full_shot_1440_1920_{n}": [[str(g['x']), str(g['y']), "2000", "2000"]]
           for n, g in enumerate(geometry)},
        **{ui + f"skill_cutin_{n}": [["0", "0", "1024", "512"]] for n in (0, 1)}})
    art.preview(previews, output / "icons-contact.png")
    art.preview({"full-0": fulls[0], "full-1": fulls[1], "illustration": sheet}, output / "art-contact.png", 3)
    return dict(sources=records, native_shape_masks=True, android_atf_encoded=True)
