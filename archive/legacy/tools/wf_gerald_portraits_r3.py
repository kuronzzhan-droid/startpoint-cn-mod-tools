"""Offline Gerald R3 artwork replacement; crops only, no generation or live writes."""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

import wf_assets
import wf_atf
import wf_canary_skin
import wf_dsl
import wf_mod_tool as core
import wf_quest_lib as tables
import wf_ui_derive_gate as gate

CODE = "unicorn_lancer_rose"
CID = "129992"
UI = f"character/{CODE}/ui/"
SOURCE_HASHES = (
    "455b3bbc0bef556b99724fc8150a1cc8e38bd383ef3fb4886e4c11c5ba34a9c0",
    "504d88b59cadd2959e4bba95d3bbba3573e57abc04cfae5a180be318a0ee5656",
)
# Source-pixel landmarks inspected against the supplied full-resolution art.
FACE = ((510, 170), (474, 148))
EYES = ((510, 147), (509, 113))
HEAD_HEIGHT = (210, 200)
SQUARE_CROP_HEIGHT = (280, 275)
GROUPS = (
    (("square", "square_132_132", "square_round_136_136", "square_round_95_95"), (.5, .5, 1.0)),
    (("thumb_level_up", "thumb_party_unison"), (.504, .382, 1.368)),
    (("battle_member_status",), (.535, .510, .917)),
    (("battle_control_board",), (.494, .227, 2.513)),
    (("cutin_skill_chain",), (.505, .538, 1.201)),
    (("thumb_party_main",), (.494, .300, 2.128)),
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def read_png(path: Path) -> Image.Image:
    return Image.open(io.BytesIO(wf_assets.png_decode(path.read_bytes()))).convert("RGBA")


def matte_regions(rgb: np.ndarray) -> np.ndarray:
    """Select large 4-connected near-black regions without optional SciPy."""
    black = np.pad(rgb.max(axis=2) <= 20, 1)
    width = black.shape[1]
    remaining = black.ravel().copy()
    selected = np.zeros_like(remaining)
    for seed in np.flatnonzero(remaining):
        if not remaining[seed]:
            continue
        stack, region = [int(seed)], []
        remaining[seed] = False
        while stack:
            index = stack.pop()
            region.append(index)
            for neighbor in (index - 1, index + 1, index - width, index + width):
                if remaining[neighbor]:
                    remaining[neighbor] = False
                    stack.append(neighbor)
        if len(region) > 900:
            selected[region] = True
    return selected.reshape(black.shape)[1:-1, 1:-1]


def load_master(path: Path, level: int) -> tuple[Image.Image, dict]:
    raw = path.read_bytes()
    if sha(raw) != SOURCE_HASHES[level]:
        raise ValueError(f"Unreviewed source artwork for form {level}")
    source = Image.open(io.BytesIO(raw)).convert("RGBA")
    array = np.asarray(source).copy()
    removed = 0
    if level == 1:
        # This supplied PNG has an opaque near-black matte. Remove only the large
        # connected matte regions; preserve small dark outlines/helmet details.
        background = matte_regions(array[:, :, :3])
        array[background, 3] = 0
        removed = int(background.sum())
    if not np.array_equal(array[:, :, :3], np.asarray(source)[:, :, :3]):
        raise AssertionError("Artwork RGB must remain unchanged")
    master = Image.fromarray(array, "RGBA")
    bbox = master.getchannel("A").getbbox()
    if not bbox:
        raise ValueError("Empty source artwork")
    return master, {"source": str(path), "sha256": sha(raw), "source_size": list(source.size),
                    "alpha_bbox": list(bbox), "matte_pixels_removed": removed,
                    "rgb_preserved": True}


def crop_at(image: Image.Image, face, height: float, size, anchor) -> Image.Image:
    width = height * size[0] / size[1]
    left = round(face[0] - anchor[0] * width)
    top = round(face[1] - anchor[1] * height)
    return image.crop((left, top, left + round(width), top + round(height))).resize(
        size, Image.Resampling.LANCZOS)


def icon_background(size) -> Image.Image:
    yy, xx = np.mgrid[:size[1], :size[0]]
    radius = np.sqrt(((xx / size[0]) - .5) ** 2 + ((yy / size[1]) - .42) ** 2)
    radius = np.clip(radius / radius.max(), 0, 1)[..., None]
    rgb = np.array((66, 96, 150)) * (1 - radius) + np.array((18, 26, 58)) * radius
    return Image.fromarray(np.dstack((rgb.astype(np.uint8), np.full(radius.shape[:2], 255, np.uint8))))


def make_icons(master, level, masks) -> dict:
    icons = {}
    for slots, (fx, fy, multiplier) in GROUPS:
        size = gate.OFFICIAL_ICON_SIZES[slots[0]]
        base = icon_background(size)
        base.alpha_composite(crop_at(master, FACE[level], SQUARE_CROP_HEIGHT[level] * multiplier,
                                    size, (fx, fy)))
        for slot in slots:
            image = base.resize(gate.OFFICIAL_ICON_SIZES[slot], Image.Resampling.LANCZOS)
            if slot in gate.SHAPE_SLOTS:
                alpha = np.asarray(image).copy()
                if masks[slot].shape != alpha.shape[:2]:
                    raise ValueError(f"Invalid official mask: {slot}")
                alpha[:, :, 3] = np.minimum(alpha[:, :, 3], masks[slot])
                image = Image.fromarray(alpha, "RGBA")
            icons[slot] = image
    return icons


def make_cutin(master, level) -> Image.Image:
    # Same face-anchored upper-body window as the established cutin_face workflow.
    image = crop_at(master, EYES[level], 512 * HEAD_HEIGHT[level] / 207,
                    (1024, 512), (.52, .485))
    array = np.asarray(image).copy()
    alpha = array[:, :, 3].astype(float)
    ramp = np.r_[np.zeros(4), np.linspace(0, 1, 60)]
    alpha[:, :64] *= ramp
    alpha[:64, :] *= ramp[:, None]
    alpha[:, -64:] *= ramp[::-1]
    # Leave an unobtrusive open edge on the right, matching the existing art slot.
    alpha[:, 717:840] *= np.linspace(1, 0, 123)
    alpha[:, 840:] = 0
    array[:, :, 3] = alpha.astype(np.uint8)
    return Image.fromarray(array, "RGBA")


def preview(images: dict, path: Path) -> None:
    cell = (310, 375)
    sheet = Image.new("RGB", (cell[0] * 5, cell[1] * ((len(images) + 4) // 5)), "#343949")
    draw = ImageDraw.Draw(sheet)
    for index, (name, image) in enumerate(images.items()):
        tile = image.copy()
        tile.thumbnail((286, 336))
        x, y = (index % 5) * cell[0], (index // 5) * cell[1]
        bg = Image.new("RGBA", tile.size, "#989da8")
        bg.alpha_composite(tile)
        sheet.paste(bg.convert("RGB"), (x + (310 - tile.width) // 2, y + 25))
        draw.text((x + 8, y + 6), name, fill="white")
    sheet.save(path)


def build(package: Path, sources: tuple[Path, Path], masks_path: Path, output: Path, apply: bool) -> dict:
    package = package.resolve()
    if package.name != "package" or "codex-r3-20260906" not in package.parts:
        raise ValueError("Only the isolated R3 package is writable")
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("package_id") != CODE:
        raise ValueError("Wrong character package")
    output.mkdir(parents=True, exist_ok=True)
    cached = np.load(masks_path)
    masks = {slot: cached[slot] for slot in gate.SHAPE_SLOTS}
    candidates, report, previews, masters = {}, {"files": [], "sources": [], "gates": {}, "claims": []}, {}, []
    crops, geometry = [], {}
    for level, path in enumerate(sources):
        master, source_report = load_master(path, level)
        report["sources"].append(source_report)
        masters.append(master)
        bbox = master.getchannel("A").getbbox()
        full = master.crop(bbox)
        full.save(output / f"full-shot-{level}.png")
        crops.append(full)
        face = (EYES[level][0] - bbox[0], EYES[level][1] - bbox[1])
        x, y = 1000 - face[0], 509 - face[1]
        if not (0 <= x <= 2000 - full.width and 0 <= y <= 2000 - full.height):
            raise ValueError("Artwork does not fit the existing virtual canvas")
        geometry[str(level)] = f"{x},{y},{full.width},{full.height}"
        candidates["medium/" + UI + f"full_shot_1440_1920_{level}.png"] = wf_assets.png_encode(png(full))
        icons = make_icons(master, level, masks)
        cutin = make_cutin(master, level)
        icons["skill_cutin"] = cutin
        problems = gate.derived_icon_problems(icons, masks, level=str(level))
        report["gates"][str(level)] = problems
        if problems:
            raise ValueError("; ".join(problems))
        for slot, image in icons.items():
            candidates["medium/" + UI + f"{slot}_{level}.png"] = wf_assets.png_encode(png(image))
            previews[f"{slot}_{level}"] = image
        atf_rel = "android/" + UI + f"skill_cutin_{level}.atf.deflate"
        atf_path = output / f"cutin-{level}.atf.deflate"
        cutin_bytes = png(cutin)
        cache_key = output / f"cutin-{level}.sha256"
        if atf_path.exists() and cache_key.exists() and cache_key.read_text() == sha(cutin_bytes):
            atf = atf_path.read_bytes()
        else:
            ref = wf_atf.inflate((package / "roots" / atf_rel).read_bytes())
            atf = wf_atf.deflate(wf_atf.build_cutin_atf(cutin_bytes, ref))
            atf_path.write_bytes(atf)
            cache_key.write_text(sha(cutin_bytes))
        info = wf_atf.parse_atf(wf_atf.inflate(atf))
        assert (info["w"], info["h"], info["mips"]) == (1024, 512, 11)
        candidates[atf_rel] = atf
    atlas_rel = "common/" + UI + "illustration_setting_sprite_sheet.atlas.amf3.deflate"
    atlas = wf_dsl.parse_dsl(wf_atf.inflate((package / "roots" / atlas_rel).read_bytes()))["tree"]
    sheet_rel = "medium/" + UI + "illustration_setting_sprite_sheet.png"
    sheet = Image.new("RGBA", read_png(package / "roots" / sheet_rel).size)
    for item in atlas:
        level = int(item["n"].rsplit("_", 1)[1])
        tile = wf_canary_skin.fit_rgba(crops[level], (item["w"], item["h"]))
        sheet.alpha_composite(tile, (item["x"], item["y"]))
    candidates[sheet_rel] = wf_assets.png_encode(png(sheet))
    report["atlas_preserved"] = sha((package / "roots" / atlas_rel).read_bytes())
    changes = {
        "master/generated/character_image.orderedmap": {CID: geometry},
        "master/character/full_shot_image_attribute.orderedmap": {CID: {str(n): "1000,1000,1,1000,509" for n in (0, 1)}},
        "master/generated/trimmed_image.orderedmap": {
            **{UI + f"full_shot_1440_1920_{n}": ",".join(geometry[str(n)].split(",")[:2]) + ",2000,2000" for n in (0, 1)},
            **{UI + f"skill_cutin_{n}": "0,0,1024,512" for n in (0, 1)}},
    }
    for logical, rows in changes.items():
        path = package / "roots/common" / logical
        tree = tables.load_table(logical, path=path)
        before = copy.deepcopy(tree)
        tree.update(rows)
        assert all(tree[k] == v for k, v in before.items() if k not in rows)
        raw_map = core.read_orderedmap_file_raw_rows(path, logical)
        for key, value in rows.items():
            raw_map.rows[raw_map.keys.index(key)] = tables.build_node(value)
        candidate = core.build_orderedmap_raw_rows(raw_map)
        assert tables.parse_node(candidate) == tree
        candidates["common/" + logical] = candidate
        report["claims"].append({"root": "common", "logical_path": logical, "keys": list(rows)})
    preview(previews, output / "icons-contact.png")
    preview({"full-shot-0": crops[0], "full-shot-1": crops[1], "illustration-sheet": sheet,
             "skill-cutin-0": previews["skill_cutin_0"], "skill-cutin-1": previews["skill_cutin_1"]}, output / "art-contact.png")
    for relative, data in candidates.items():
        path = package / "roots" / relative
        old = path.read_bytes()
        backup = output / "before" / relative
        baseline = backup.read_bytes() if backup.exists() else old
        record = {"root": relative.split("/", 1)[0], "logical_path": relative.split("/", 1)[1],
                  "old_sha256": sha(baseline), "before_run_sha256": sha(old),
                  "new_sha256": sha(data), "size": len(data), "changed": baseline != data,
                  "would_write": old != data}
        report["files"].append(record)
        if apply and old != data:
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                backup.write_bytes(old)
            path.write_bytes(data)
            assert path.read_bytes() == data
    report["applied"] = apply
    report["geometry"] = geometry
    report["mask_source"] = {"path": str(masks_path), "sha256": sha(masks_path.read_bytes())}
    (output / ("applied.json" if apply else "preview.json")).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--awake", required=True, type=Path)
    parser.add_argument("--masks", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = build(args.package, (args.base, args.awake), args.masks, args.output, args.apply)
    print(json.dumps({"applied": result["applied"], "changed_from_baseline": sum(r["changed"] for r in result["files"]),
                      "writes_this_run": sum(r["would_write"] for r in result["files"]), "gates": result["gates"]}))


if __name__ == "__main__":
    main()
