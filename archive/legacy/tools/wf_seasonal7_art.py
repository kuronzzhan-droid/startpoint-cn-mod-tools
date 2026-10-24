# -*- coding: utf-8 -*-
"""季节换装立绘/UI 离线装配（参数化 wf_campus_art.build）。

输入：透明立绘母图 ``<batch>/art/masters/<key>-<0|1>.png`` + landmarks JSON
（``{key: [{face, eyes, head_height, square_height, sha256} ×2]}``，坐标在母图像素空间）。
输出（只写指定角色包）：full_shot ×2、20 图标、cutin PNG ×2 + Android ATF ×2、立绘图集 PNG、
三张定位表几何；原位更新 manifest 条目 hash，qa 复位。默认 dry-run，``--apply`` 才写。

形状蒙版 = **官方基线统计**（``OfficialBaseline`` medium 根，按角色 ID 升序取官方角色的
``<slot>_{0,1}.png`` alpha，两个立绘槽合并取逐像素中位数），与母本无关。
不能用母本自己的图标 alpha：``thumb_*`` / ``square_round_136_136`` / ``battle_member_status``
的官方 alpha 带着该角色自己的剪影（131020 与其他角色 IoU 仅 0.76~0.89），``min(alpha, 母本 alpha)``
会把旧角色轮廓印到新图标上，门禁再拿同一份 alpha 比对 = 恒通过。统计蒙版缓存在批目录
``art/official-shape-masks.npz``（sha 与样本统计记在同名 .json）。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import io

import numpy as np

import wf_assets
import wf_atf
import wf_campus_art as campus_art
import wf_campus_art_images as images
import wf_character_pack
import wf_seasonal7_common as C
import wf_seasonal7_specs as S
import wf_ui_derive_gate as gate

STEP = "art"


def default_source_dir(root: Path) -> Path:
    return root / S.BATCH_DIR / "art" / "masters"


def default_landmarks(root: Path) -> Path:
    return root / S.BATCH_DIR / "art" / "landmarks.json"


def default_output(pack: C.S7Pack) -> Path:
    return pack.evidence / "art"


MASK_SAMPLE = 120                 # 每槽每立绘槽取的官方角色数（两槽合并 = 240 张）
MASK_METHOD = "official-baseline median alpha, levels 0+1 pooled"


def default_mask_cache(root: Path) -> Path:
    return root / S.BATCH_DIR / "art" / "official-shape-masks.npz"


def shape_masks_from_samples(samples: dict[str, list[np.ndarray]]) -> dict[str, np.ndarray]:
    """槽 -> 官方 alpha 样本列表 ⇒ 逐像素中位数（uint8）。中位数 >127 ⇔ 过半样本该像素不透明：
    共享框的抗锯齿边保留，个别角色的剪影/出框头发被多数票抹掉。"""
    masks = {}
    for slot, stack in samples.items():
        want = gate.OFFICIAL_ICON_SIZES[slot]
        good = [a for a in stack if a.shape[::-1] == want]
        if len(good) < 16:
            raise ValueError(f"too few official samples for {slot}: {len(good)}")
        masks[slot] = np.median(np.stack(good), axis=0).astype(np.uint8)
    return masks


def _official_samples(pack: C.S7Pack, sample: int) -> tuple[dict[str, list[np.ndarray]], dict]:
    from PIL import Image
    raw_table = pack.official_read("master/character/character.orderedmap", "common")
    if raw_table is None:
        raise ValueError("official baseline unavailable: cannot derive shape masks")
    rows = C.core.read_orderedmap_file_from_bytes(raw_table)
    codes = []
    for _cid, text in sorted(rows.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
        cells = C.csv_split(text)
        if cells and cells[0] and cells[0][0]:
            codes.append(cells[0][0])
    samples: dict[str, list[np.ndarray]] = {slot: [] for slot in gate.SHAPE_SLOTS}
    used: dict[str, list[str]] = {slot: [] for slot in gate.SHAPE_SLOTS}
    for slot in gate.SHAPE_SLOTS:
        want = gate.OFFICIAL_ICON_SIZES[slot]
        per_level = {"0": 0, "1": 0}
        for code in codes:
            if min(per_level.values()) >= sample:
                break
            for level in ("0", "1"):
                if per_level[level] >= sample:
                    continue
                raw = pack.official_read(f"character/{code}/ui/{slot}_{level}.png", "medium")
                if raw is None:
                    continue
                alpha = np.asarray(Image.open(io.BytesIO(wf_assets.png_decode(raw))).convert("RGBA"))[:, :, 3]
                if alpha.shape[::-1] != want:
                    continue
                samples[slot].append(alpha)
                per_level[level] += 1
                if not used[slot] or used[slot][-1] != code:
                    used[slot].append(code)
    return samples, {"characters": {slot: len(v) for slot, v in used.items()},
                     "samples": {slot: len(v) for slot, v in samples.items()},
                     "character_list_sha256": {slot: images.sha(json.dumps(v).encode("utf-8"))
                                               for slot, v in used.items()}}


def official_shape_masks(pack: C.S7Pack, *, cache: Path | None = None,
                         sample: int = MASK_SAMPLE) -> tuple[dict[str, np.ndarray], dict]:
    """官方统计形状蒙版（与母本无关），批目录缓存；缓存 sha 不符即报错（不静默重算）。"""
    cache = Path(cache) if cache is not None else default_mask_cache(pack.root)
    meta_path = cache.with_suffix(".json")
    if cache.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("cache_sha256") != images.sha(cache.read_bytes()):
            raise ValueError(f"official shape mask cache changed: {cache}")
        data = np.load(cache)
        return {slot: data[slot] for slot in gate.SHAPE_SLOTS}, meta
    samples, info = _official_samples(pack, sample)
    masks = shape_masks_from_samples(samples)
    stats = {}
    for slot, mask in masks.items():
        on = mask > 127
        ious = [float(((a > 127) & on).sum() / max(1, ((a > 127) | on).sum())) for a in samples[slot]]
        stats[slot] = {"coverage": round(float((mask > gate.ALPHA_ON).mean()), 4),
                       "sample_iou_p10": round(float(np.percentile(ious, 10)), 3),
                       "sample_iou_p50": round(float(np.median(ious)), 3)}
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache, **masks)
    meta = {"method": MASK_METHOD, "sample_per_level": sample, **info, "stats": stats,
            "cache_sha256": images.sha(cache.read_bytes())}
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return masks, meta


def _template_iou(folder: Path, level: int, masks: dict[str, np.ndarray]) -> dict:
    """证据：母本图标 alpha 与统计蒙版的 IoU（证明蒙版不是母本剪影）。"""
    out = {}
    for slot in gate.SHAPE_SLOTS:
        path = folder / f"{slot}_{level}.png"
        if not path.is_file():
            continue
        alpha = np.asarray(images.read_png(path))[:, :, 3] > 127
        on = masks[slot] > 127
        if alpha.shape == on.shape:
            out[slot] = round(float((alpha & on).sum() / max(1, (alpha | on).sum())), 3)
    return out


def _load_masks(pack: C.S7Pack, level: int, mask_cache: Path | None = None) -> tuple[dict, dict]:
    masks, meta = official_shape_masks(pack, cache=mask_cache)
    source = {"method": meta["method"], "cache": str(mask_cache or default_mask_cache(pack.root)),
              "cache_sha256": meta["cache_sha256"], "level": level,
              "coverage": {slot: v["coverage"] for slot, v in meta.get("stats", {}).items()}}
    return masks, source


def build(pack: C.S7Pack, landmarks: list[dict], *, source_dir: Path | None = None,
          output: Path | None = None, apply: bool = False, headshots: bool = False,
          mask_cache: Path | None = None) -> dict[str, Any]:
    spec = pack.spec
    pack.check_identity()
    source_dir = Path(source_dir) if source_dir is not None else default_source_dir(pack.root)
    output = Path(output) if output is not None else default_output(pack)
    package = pack.package
    if len(landmarks) != 2:
        raise ValueError("landmarks must contain two entries (normal, awakened)")
    manifest_path = package / "manifest.json"
    old_manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(old_manifest_bytes)
    if (manifest["character_id"], manifest["code_name"]) != (spec.cid, spec.code):
        raise ValueError("wrong character package")
    output.mkdir(parents=True, exist_ok=True)
    role = f"s7:{spec.key}"
    images.COLORS[role] = tuple(tuple(c) for c in spec.backdrop_colors)   # 按 spec 注入底色
    ui = f"character/{spec.code}/ui/"
    candidates: dict[str, bytes] = {}
    icons_preview, art_preview, fulls, geometry = {}, {}, [], []
    report: dict[str, Any] = dict(character=spec.key, cid=spec.cid, package=str(package),
                                  headshots=headshots, backdrop_colors=[list(c) for c in spec.backdrop_colors],
                                  sources=[], masks=[], gates={}, files=[], writes_live=False)
    for level in (0, 1):
        source = source_dir / f"{spec.key}-{level}.png"
        master, source_report = images.load_master(source, landmarks[level])
        report["sources"].append(source_report)
        full, geom = images.full_shot(master, landmarks[level]["eyes"])
        fulls.append(full)
        geometry.append(geom)
        full.save(output / f"full-shot-{level}.png")
        candidates["medium/" + ui + f"full_shot_1440_1920_{level}.png"] = wf_assets.png_encode(images.png(full))
        masks, mask_sources = _load_masks(pack, level, mask_cache)
        before_dir = output / "before" / "medium" / ui          # 首次 apply 前的母本图标备份
        template_dir = before_dir if (before_dir / f"{gate.SHAPE_SLOTS[0]}_{level}.png").is_file() \
            else package / "roots/medium" / ui
        mask_sources["template_alpha_iou"] = _template_iou(template_dir, level, masks)
        report["masks"].append(mask_sources)
        icons = images.make_icons(master, landmarks[level], masks, role, headshots=headshots)
        icons["skill_cutin"] = images.make_cutin(master, landmarks[level], headshots=headshots)
        problems = gate.derived_icon_problems(icons, masks, level=str(level))
        if landmarks[level].get("transparent_icon_background", False):
            # An explicit transparent backdrop intentionally differs from opaque
            # official cards; keep size, mask, upper coverage and crop checks.
            exceptions = [p for p in problems if "不透明占比" in p and "低于官方下界" in p
                          and not p.startswith("skill_cutin:")]
            report.setdefault("transparent_background_coverage", {})[str(level)] = exceptions
            problems = [p for p in problems if p not in exceptions]
        report["gates"][str(level)] = problems
        if problems:
            images.preview(icons, output / f"failed-icons-{level}.png")
            (output / "failed.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
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
            atf_path.write_bytes(atf)
            cache_key.write_text(images.sha(raw_png))
        info = wf_atf.parse_atf(wf_atf.inflate(atf))
        if (info["w"], info["h"], info["mips"]) != (1024, 512, 11):
            raise ValueError("wrong Android cutin dimensions or mip chain")
        candidates[atf_rel] = atf
        art_preview[f"full-shot-{level}"] = full
        art_preview[f"skill-cutin-{level}"] = icons["skill_cutin"]
    sheet_rel, sheet = campus_art.atlas_sheet(package, ui, fulls)
    candidates[sheet_rel] = wf_assets.png_encode(images.png(sheet))
    art_preview["illustration-sheet"] = sheet
    candidates.update(campus_art.patch_tables(package, spec.cid_s, ui, geometry))
    images.preview(icons_preview, output / "icons-contact.png")
    images.preview(art_preview, output / "art-contact.png")
    for relative, raw in candidates.items():
        root, logical = relative.split("/", 1)
        matches = [e for e in manifest["roots"][root] if e["logical_path"] == logical]
        if len(matches) != 1:
            raise ValueError(f"manifest must already declare {relative}; run --step manifest first")
        entry = matches[0]
        path = package / "roots" / relative
        before = path.read_bytes()
        if images.sha(before) != entry["sha256"]:
            raise ValueError(f"candidate input drift: {relative}; rerun --step manifest")
        report["files"].append(dict(root=root, logical=logical, before_sha256=images.sha(before),
                                    after_sha256=images.sha(raw), changed=before != raw))
        entry.update(sha256=images.sha(raw), size=len(raw))
    report["geometry"] = geometry
    manifest.setdefault("snapshot", {})["seasonal7_art"] = dict(
        sources=[{k: s[k] for k in ("sha256", "source_size", "alpha_bbox", "landmarks")}
                 for s in report["sources"]],
        geometry=[{k: g[k] for k in ("x", "y", "width", "height")} for g in geometry],
        shape_masks=MASK_METHOD, original_template_masks=False, android_atf_encoded=True,
        face_centered_headshots=headshots, visual_review_pending=True)
    manifest["qa"].update(release_ready=False, workspace_input_sha256="")
    if apply:
        if manifest_path.read_bytes() != old_manifest_bytes:
            raise ValueError("candidate manifest changed while generating UI")
        owned = []
        for relative, raw in candidates.items():
            root, logical = relative.split("/", 1)
            path = package / "roots" / relative
            backup = output / "before" / relative
            backup.parent.mkdir(parents=True, exist_ok=True)
            if not backup.exists():
                backup.write_bytes(path.read_bytes())
            pack.write_pkg(root, logical, raw)
            if not logical.endswith(".orderedmap"):
                owned.append((root, logical))
        pack.register_outputs(STEP, owned)
        manifest_path.write_bytes(wf_character_pack.canonical_manifest_bytes(manifest))
    report["applied"] = apply
    (output / ("applied.json" if apply else "preview.json")).write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def load_landmarks(path: Path, key: str) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if key not in data:
        raise KeyError(f"landmarks file has no entry for {key}: {path}")
    return data[key]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--char", choices=S.all_keys(), required=True)
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--landmarks", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--headshots", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    pack = C.S7Pack(S.get_spec(args.char))
    landmarks = load_landmarks(args.landmarks or default_landmarks(pack.root), args.char)
    result = build(pack, landmarks, source_dir=args.source_dir, output=args.output,
                   apply=args.apply, headshots=args.headshots)
    print(json.dumps(dict(character=args.char, applied=result["applied"], gates=result["gates"],
                          changed=sum(r["changed"] for r in result["files"]), writes_live=False),
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
