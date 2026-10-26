"""三角色校园立绘/UI离线装配。只改指定包的UI、三张定位表及manifest。"""
from __future__ import annotations

from wf.paths import root_path

import argparse
import copy
import json
from pathlib import Path

import numpy as np
from PIL import Image

import wf_assets
import wf_atf
import wf_campus_art_images as images
import wf_canary_skin
import wf_character_pack
import wf_dsl
import wf_mod_tool as core
import wf_quest_lib as tables
import wf_ui_derive_gate as gate

ROOT = Path(('${WF_ROOT}/startpoint-cn'.replace("${WF_ROOT}", str(root_path()))))
CHARACTERS = {"bianca": ("119989", "lady_summoner_campus"),
              "celtie": ("149989", "wind_spgirl_campus"),
              "nephtim": ("169989", "ruin_girl_campus")}


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


def build(role, source_dir, landmarks, output, *, apply=False, package=None, headshots=False):
    cid, code = CHARACTERS[role]
    package = Path(package) if package is not None else ROOT / f"work/character_packs/campus-{role}-20260911/package"
    if not package.resolve().is_relative_to((ROOT / "work/character_packs").resolve()):
        raise ValueError("assigned package escaped workspace")
    manifest_path = package / "manifest.json"
    old_manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(old_manifest_bytes)
    if (str(manifest["character_id"]), manifest["code_name"]) != (cid, code):
        raise ValueError("wrong character package")
    output.mkdir(parents=True, exist_ok=True)
    ui = f"character/{code}/ui/"
    candidates, icons_preview, art_preview, fulls, geometry = {}, {}, {}, [], []
    report = dict(character=role, cid=cid, package=str(package), headshots=headshots,
                  sources=[], masks=[], gates={}, files=[], writes_live=False)
    for level in (0, 1):
        source = source_dir / f"{role}-{level}.png"
        master, source_report = images.load_master(source, landmarks[level])
        report["sources"].append(source_report)
        full, geom = images.full_shot(master, landmarks[level]["eyes"])
        fulls.append(full); geometry.append(geom)
        full.save(output / f"full-shot-{level}.png")
        candidates["medium/" + ui + f"full_shot_1440_1920_{level}.png"] = wf_assets.png_encode(images.png(full))
        masks_path = output / f"native-masks-{level}.npz"
        masks_source_path = output / f"native-masks-{level}.json"
        if masks_path.is_file():
            cache = np.load(masks_path)
            masks = {slot: cache[slot] for slot in gate.SHAPE_SLOTS}
            mask_sources = json.loads(masks_source_path.read_bytes())
            if mask_sources["cache_sha256"] != images.sha(masks_path.read_bytes()):
                raise ValueError("native mask cache changed")
        else:
            masks = {slot: np.asarray(images.read_png(package / "roots/medium" / ui / f"{slot}_{level}.png"))[:, :, 3]
                     for slot in gate.SHAPE_SLOTS}
            np.savez_compressed(masks_path, **masks)
            mask_sources = dict(cache_sha256=images.sha(masks_path.read_bytes()), templates={
                slot: images.sha((package / "roots/medium" / ui / f"{slot}_{level}.png").read_bytes())
                for slot in gate.SHAPE_SLOTS})
            masks_source_path.write_text(json.dumps(mask_sources, indent=2), encoding="utf-8")
        report["masks"].append(mask_sources)
        icons = images.make_icons(master, landmarks[level], masks, role, headshots=headshots)
        icons["skill_cutin"] = images.make_cutin(master, landmarks[level], headshots=headshots)
        problems = gate.derived_icon_problems(icons, masks, level=str(level))
        report["gates"][str(level)] = problems
        if problems:
            images.preview(icons, output / f"failed-icons-{level}.png")
            raise ValueError("; ".join(problems))
        for slot, image in icons.items():
            candidates["medium/" + ui + f"{slot}_{level}.png"] = wf_assets.png_encode(images.png(image))
            icons_preview[f"{slot}_{level}"] = image
        atf_rel = "android/" + ui + f"skill_cutin_{level}.atf.deflate"
        atf_path = output / f"cutin-{level}.atf.deflate"
        cache_key = output / f"cutin-{level}.sha256"
        raw_png = images.png(icons["skill_cutin"])
        if atf_path.is_file() and cache_key.is_file() and cache_key.read_text() == images.sha(raw_png):
            atf = atf_path.read_bytes()
        else:
            template = wf_atf.inflate((package / "roots" / atf_rel).read_bytes())
            atf = wf_atf.deflate(wf_atf.build_cutin_atf(raw_png, template))
            atf_path.write_bytes(atf); cache_key.write_text(images.sha(raw_png))
        info = wf_atf.parse_atf(wf_atf.inflate(atf))
        if (info["w"], info["h"], info["mips"]) != (1024, 512, 11):
            raise ValueError("wrong Android cutin dimensions or mip chain")
        candidates[atf_rel] = atf
        art_preview[f"full-shot-{level}"] = full
        art_preview[f"skill-cutin-{level}"] = icons["skill_cutin"]
    sheet_rel, sheet = atlas_sheet(package, ui, fulls)
    candidates[sheet_rel] = wf_assets.png_encode(images.png(sheet))
    art_preview["illustration-sheet"] = sheet
    candidates.update(patch_tables(package, cid, ui, geometry))
    images.preview(icons_preview, output / "icons-contact.png")
    images.preview(art_preview, output / "art-contact.png")
    # 只更新既有UI/表文件的hash；其它技能、像素、音频声明保持原样。
    for relative, raw in candidates.items():
        root, logical = relative.split("/", 1)
        entry, = [e for e in manifest["roots"][root] if e["logical_path"] == logical]
        path = package / "roots" / relative
        before = path.read_bytes()
        if images.sha(before) != entry["sha256"]:
            raise ValueError(f"candidate input drift: {relative}")
        report["files"].append(dict(root=root, logical=logical, before_sha256=images.sha(before),
                                    after_sha256=images.sha(raw), changed=before != raw))
        entry.update(sha256=images.sha(raw), size=len(raw))
    report["geometry"] = geometry
    manifest.setdefault("snapshot", {})["campus_art"] = dict(sources=report["sources"], geometry=geometry,
        original_template_masks=True, full_ground_preserved=True, android_atf_encoded=True,
        face_centered_headshots=headshots,
        visual_review_pending=True)
    if role == "bianca":
        manifest["snapshot"].setdefault("campus_bianca", {})["original_portraits_pending_replacement"] = False
    manifest["qa"].update(release_ready=False, workspace_input_sha256="")
    if apply:
        if manifest_path.read_bytes() != old_manifest_bytes:
            raise ValueError("candidate manifest changed while generating UI")
        for relative, raw in candidates.items():
            path = package / "roots" / relative
            backup = output / "before" / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                backup.write_bytes(path.read_bytes())
            path.write_bytes(raw)
        manifest_path.write_bytes(wf_character_pack.canonical_manifest_bytes(manifest))
    report["applied"] = apply
    (output / ("applied.json" if apply else "preview.json")).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--character", choices=CHARACTERS, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--landmarks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package", type=Path, help="显式指定已从最新live建立的离线候选包")
    parser.add_argument("--headshots", action="store_true", help="所有头像与技能切入采用脸部居中特写")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = build(args.character, args.source_dir,
                   json.loads(args.landmarks.read_bytes())[args.character], args.output,
                   apply=args.apply, package=args.package, headshots=args.headshots)
    print(json.dumps(dict(character=args.character, applied=result["applied"], gates=result["gates"],
                          changed=sum(r["changed"] for r in result["files"]), writes_live=False)))
