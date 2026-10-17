# -*- coding: utf-8 -*-
"""把立绘重新排版填满画框,并把 character_image 的裁切矩形改成真实纹理尺寸。

## 两个叠加的缺陷(2026-09-01 实测)

1. **图本身又小又偏下**。生成器 `wf_epuration_boss_ui.py` 用了
   `center_landmark=True`:它把脸钉在画布正中,为了让主体不出框,缩放分母取
   `2*max_dy+1` 而不是主体高度 —— 直接砍掉一半;脸居中又把身体推到下半部。
   实测内容只占画布高度的 42%~43%,而官方是 94%~100%:
     111001 火龙 y 0->1909/1909   169994 白虎 y 44->1739/1800
     179982 步兵 y 683->1489/1920  179985 女帝 y 606->1436/1920

2. **裁切矩形对不上纹理**。`GeneralCharacterLogic.as:398` 用
   `Rectangle(full_shot_x, full_shot_y, full_shot_width, full_shot_height)`
   去裁 `character/<code>/ui/full_shot_1440_1920_<n>.png`。这五只写的是
   `188,224,1488,1761`(五份一模一样的克隆值),而真纹理是 1440x1920 ——
   从 (188,224) 裁 1488x1761 会越过右下边界。
   官方全部对得上:111001 `3,2,1916,1909` 配 1916x1909;
   169994 `0,0,1400,1800` 配 1400x1800。

## 修法
- 重排图:裁到 alpha 包围盒 -> 等比放大到占满画框(宽 98% / 高 94% 取小)
  -> 顶边留 2.4% 边距贴上去(照 169994 的版式,详情页下半被属性面板挡住,
  顶对齐能把主体放进可见窗口)。
- `character_image` 改成 `0,0,<真宽>,<真高>`。
- `full_shot_image_attribute` 的 face_x/face_y 按**内容内相对位置不变**平移缩放。
  实测正常角色与这五只的相对脸位都在 0.25~0.43,本来就是对的,只是内容动了。
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zlib
from pathlib import Path

from PIL import Image

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core  # noqa: E402
import wf_offline_pack_apply as apply_tool  # noqa: E402
import wf_pixel_rescale as rescale  # noqa: E402

CANVAS = (1440, 1920)
FILL_W = 0.98          # 宽度占比上限
FILL_H = 0.94          # 高度占比上限
TOP_MARGIN = 0.024     # 顶边留白(照 169994: 44/1800)

ROOTS = ("upload", "medium_upload", "android_upload")
PROD = Path(r"弹国服/WorldFlipper/dummy/download/production")


class RefitError(RuntimeError):
    pass


def _read_png(raw: bytes) -> Image.Image:
    return Image.open(io.BytesIO(raw[:1] + b"PNG" + raw[4:])).convert("RGBA")


def _write_png(img: Image.Image, lowercase: bool) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    raw = buf.getvalue()
    return raw[:1] + b"png" + raw[4:] if lowercase else raw


def refit_image(img: Image.Image) -> tuple[Image.Image, tuple[int, int, int, int]]:
    bbox = img.getchannel("A").getbbox()
    if bbox is None:
        raise RefitError("整张图全透明")
    content = img.crop(bbox)
    cw, ch = content.size
    scale = min(CANVAS[0] * FILL_W / cw, CANVAS[1] * FILL_H / ch)
    new_w = max(1, round(cw * scale))
    new_h = max(1, round(ch * scale))
    # 放大用 NEAREST 保住像素边缘(源就是 boss 零件按整数倍渲出来的);
    # 缩小才用 LANCZOS。
    resample = Image.Resampling.NEAREST if scale >= 1 else Image.Resampling.LANCZOS
    resized = content.resize((new_w, new_h), resample)
    canvas = Image.new("RGBA", CANVAS, (0, 0, 0, 0))
    x = (CANVAS[0] - new_w) // 2
    y = round(CANVAS[1] * TOP_MARGIN)
    if y + new_h > CANVAS[1]:
        y = max(0, CANVAS[1] - new_h)
    canvas.alpha_composite(resized, (x, y))
    return canvas, (x, y, x + new_w, y + new_h)


def _raw_table(logical: str, root: Path):
    path = core.table_path(root, logical)
    keys, rows = apply_tool.read_rows(path.read_bytes(), "raw_outer", logical)
    return path, keys, rows


def _inner_raw(blob: bytes):
    return core._strict_orderedmap_rows(  # type: ignore[attr-defined]
        blob, label="inner", compressed_rows=False)


def _cells(blob: bytes) -> list[str]:
    try:
        text = zlib.decompress(blob).decode("utf-8")
    except Exception:
        text = blob.decode("utf-8", errors="replace")
    return core.read_csv_lines(text)[0] if text else []


def _pack(cells) -> bytes:
    return zlib.compress(core.write_csv_lines([list(cells)]).encode("utf-8"))


def process(code_names: dict[str, str], apply: bool) -> dict:
    """code_names: {character_id: code_name}"""
    salt = rescale.salt()
    report = {"images": [], "character_image": [], "full_shot_attr": []}
    stamp = time.strftime("%Y%m%d-%H%M%S")
    new_geom: dict[str, dict[str, tuple]] = {}

    # --- 1. 重排每张立绘 ---
    for cid, code in code_names.items():
        new_geom[cid] = {}
        for level in ("0", "1"):
            logical = f"character/{code}/ui/full_shot_1440_1920_{level}.png"
            touched = []
            for root_name in ROOTS:
                root = PROD / root_name
                path = rescale.store_path(root, logical, salt)
                if not path.exists():
                    continue
                raw = path.read_bytes()
                img = _read_png(raw)
                before = img.getchannel("A").getbbox()
                fitted, after = refit_image(img)
                data = _write_png(fitted, raw[1:4] == b"png")
                if _read_png(data).size != CANVAS:
                    raise RefitError(f"{logical}: 回读尺寸不符")
                if apply:
                    backup = path.with_name(path.name + f".bak-refit-{stamp}")
                    if not backup.exists():
                        backup.write_bytes(raw)
                    path.write_bytes(data)
                touched.append(root_name)
                new_geom[cid][level] = (before, after, img.size)
            if touched:
                b, a, sz = new_geom[cid][level]
                report["images"].append({
                    "logical": logical, "roots": touched, "png": list(sz),
                    "bbox_before": list(b), "bbox_after": list(a),
                    "height_ratio_before": round((b[3] - b[1]) / sz[1], 3),
                    "height_ratio_after": round((a[3] - a[1]) / CANVAS[1], 3),
                })
    return report, new_geom, salt, stamp


def fix_tables(code_names, new_geom, salt, stamp, apply, report):
    root = PROD / "upload"

    # --- character_image: 裁切矩形改成真实纹理尺寸 ---
    logical = "master/generated/character_image.orderedmap"
    path, keys, rows = _raw_table(logical, root)
    row_map = dict(zip(keys, rows))
    changed = False
    for cid in code_names:
        if cid not in row_map:
            continue
        ik, ir = _inner_raw(row_map[cid])
        new_ir = list(ir)
        for i, k in enumerate(ik):
            cells = _cells(ir[i])
            if len(cells) != 4:
                raise RefitError(f"character_image[{cid}][{k}] 列数 {len(cells)}")
            want = ["0", "0", str(CANVAS[0]), str(CANVAS[1])]
            if cells != want:
                report["character_image"].append(
                    {"id": cid, "form": k, "before": cells, "after": want})
                new_ir[i] = _pack(want)
                changed = True
        row_map[cid] = apply_tool.build_rows(ik, new_ir, compressed=False)
    if changed:
        data = apply_tool.build_rows(keys, [row_map[k] for k in keys], compressed=False)
        k2, r2 = apply_tool.read_rows(data, "raw_outer", "verify")
        if k2 != keys:
            raise RefitError("character_image 外层键变了")
        for k, before, after in zip(keys, rows, r2):
            if k not in code_names and before != after:
                raise RefitError(f"character_image 无关行 {k} 被改动")
        if apply:
            backup = path.with_name(path.name + f".bak-refit-{stamp}")
            if not backup.exists():
                backup.write_bytes(path.read_bytes())
            path.write_bytes(data)

    # --- full_shot_image_attribute: 脸锚跟着内容平移缩放 ---
    logical = "master/character/full_shot_image_attribute.orderedmap"
    path, keys, rows = _raw_table(logical, root)
    row_map = dict(zip(keys, rows))
    changed = False
    for cid in code_names:
        if cid not in row_map or cid not in new_geom:
            continue
        ik, ir = _inner_raw(row_map[cid])
        new_ir = list(ir)
        for i, k in enumerate(ik):
            cells = _cells(ir[i])
            if len(cells) != 5 or k not in new_geom[cid]:
                continue
            before_bbox, after_bbox, _ = new_geom[cid][k]
            fx, fy = int(cells[3]), int(cells[4])
            # 内容内相对位置保持不变
            rx = (fx - before_bbox[0]) / max(1, before_bbox[2] - before_bbox[0])
            ry = (fy - before_bbox[1]) / max(1, before_bbox[3] - before_bbox[1])
            nfx = round(after_bbox[0] + rx * (after_bbox[2] - after_bbox[0]))
            nfy = round(after_bbox[1] + ry * (after_bbox[3] - after_bbox[1]))
            want = list(cells)
            want[3], want[4] = str(nfx), str(nfy)
            if want != cells:
                report["full_shot_attr"].append(
                    {"id": cid, "form": k, "face_before": [fx, fy],
                     "face_after": [nfx, nfy], "rel": [round(rx, 3), round(ry, 3)]})
                new_ir[i] = _pack(want)
                changed = True
        row_map[cid] = apply_tool.build_rows(ik, new_ir, compressed=False)
    if changed:
        data = apply_tool.build_rows(keys, [row_map[k] for k in keys], compressed=False)
        k2, r2 = apply_tool.read_rows(data, "raw_outer", "verify")
        if k2 != keys:
            raise RefitError("full_shot_image_attribute 外层键变了")
        for k, before, after in zip(keys, rows, r2):
            if k not in code_names and before != after:
                raise RefitError(f"full_shot_image_attribute 无关行 {k} 被改动")
        if apply:
            backup = path.with_name(path.name + f".bak-refit-{stamp}")
            if not backup.exists():
                backup.write_bytes(path.read_bytes())
            path.write_bytes(data)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--id", action="append", required=True, help="角色 ID,可多次")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)

    up = PROD / "upload"
    ch = core.read_orderedmap_file(
        core.table_path(up, "master/character/character.orderedmap"),
        "master/character/character.orderedmap").text_rows()
    code_names = {cid: core.read_csv_lines(ch[cid])[0][0] for cid in args.id}

    report, new_geom, salt, stamp = process(code_names, args.apply)
    fix_tables(code_names, new_geom, salt, stamp, args.apply, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["images"] or report["character_image"] or report["full_shot_attr"]:
        print("\n需要发布:")
        paths = [e["logical"] for e in report["images"]]
        if report["character_image"]:
            paths.append("master/generated/character_image.orderedmap")
        if report["full_shot_attr"]:
            paths.append("master/character/full_shot_image_attribute.orderedmap")
        print(",".join(paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
