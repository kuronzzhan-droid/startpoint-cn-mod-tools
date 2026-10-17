# -*- coding: utf-8 -*-
"""把一个角色的 pixelart 图集整体等比缩小并重排,修 512xN 竖条超纹理上限。

为什么需要它:`wf_boss_player_pixel.py` 把缩放写死成 1/2
(`if scale != (1, 2): raise`)。对源图 72-100px 的 boss 这没问题,但
`epuration_boss_highest`(女王)源图 292px 宽,半缩后仍有 146px,645 帧按固定
512 宽向下堆就堆到 11319 —— 超过 Starling 纹理上限,`Texture.empty()` 抛
ArgumentError #3766,角色详情页直接崩(2026-09-01 实测)。

变换(与官方 boss->可玩配方一致:只动图集数字,timeline 不碰):
  w,h,fx,fy,fw,fh 全部除以 k。fw/fh **必须跟着除**,否则 -fx 变小而画框不变,
  角色会在画框里向左上偏移 —— 那正是作者肉眼看到的现象。除以 k 后
  cx = -fx + w/2 仍等于 fw/2,构图不变,只是整体变小。
帧像素用 NEAREST 重采样(像素画不能插值);重排保持**图集条目顺序不变**,
只改 x,y —— .frame/.timeline 按名字索引,不绑坐标(官方 boss_land_dragon_wind
-> land_dragon_wind 的 timeline 逐字节相同,是这条的先例)。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import time
import zlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core  # noqa: E402

MAX_TEXTURE = 4096
PAD = 1


class RescaleError(RuntimeError):
    pass


def salt() -> str:
    src = (TOOLS / "wf_decrypt_all.py").read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"SALT\s*=\s*['\"]([^'\"]+)['\"]", src)
    if not m:
        raise RescaleError("无法从 wf_decrypt_all.py 提取 SALT")
    return m.group(1)


def store_path(root: Path, logical: str, s: str) -> Path:
    h = hashlib.sha1((logical + s).encode()).hexdigest()
    return root / h[:2] / h[2:]


def read_png(raw: bytes) -> Image.Image:
    # store 里 PNG 魔数是小写 \x89png,PIL 不认,先补回大写
    return Image.open(io.BytesIO(raw[:1] + b"PNG" + raw[4:])).convert("RGBA")


def write_png(img: Image.Image, lowercase_magic: bool) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    raw = buf.getvalue()
    return raw[:1] + b"png" + raw[4:] if lowercase_magic else raw


@dataclass
class AtlasCodec:
    offset: int
    wbits: int


def read_atlas(raw: bytes) -> tuple[list[dict], AtlasCodec]:
    for wbits in (15, -15):
        for offset in (0, 4):
            try:
                value = core.AMF3Reader(zlib.decompress(raw[offset:], wbits)).read_value()
            except Exception:
                continue
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value, AtlasCodec(offset, wbits)
    raise RescaleError("图集解不出")


def _encode_amf3(value):
    try:
        return core.encode_amf3(value)
    except AttributeError:
        import wf_dsl
        return wf_dsl.encode_amf3(value)


def write_atlas(entries: list[dict], codec: AtlasCodec, original: bytes) -> bytes:
    body = _encode_amf3(entries)
    comp = zlib.compressobj(9, zlib.DEFLATED, codec.wbits)
    packed = comp.compress(body) + comp.flush()
    return original[: codec.offset] + packed


def rescale_entry(entry: dict, k: float) -> dict:
    out = dict(entry)
    for field in ("w", "h", "fw", "fh"):
        out[field] = max(1, round(entry[field] / k))
    for field in ("fx", "fy"):
        out[field] = -max(0, round(-entry[field] / k))
    return out


def repack(entries: list[dict], sheet_width: int) -> int:
    """行式重排,保持条目顺序不变。返回所需高度。"""
    x = y = PAD
    row_h = 0
    for e in entries:
        if x + e["w"] + PAD > sheet_width:
            x = PAD
            y += row_h + PAD
            row_h = 0
        e["x"], e["y"] = x, y
        x += e["w"] + PAD
        row_h = max(row_h, e["h"])
    return y + row_h + PAD


def process(root: Path, code_name: str, stem: str, k: float, s: str,
            apply: bool) -> dict:
    png_logical = f"character/{code_name}/pixelart/{stem}.png"
    atl_logical = f"character/{code_name}/pixelart/{stem}.atlas.amf3.deflate"
    png_path = store_path(root, png_logical, s)
    atl_path = store_path(root, atl_logical, s)
    if not png_path.exists() or not atl_path.exists():
        raise RescaleError(f"{code_name}/{stem}: store 缺 png 或 atlas")

    png_raw = png_path.read_bytes()
    lowercase = png_raw[1:4] == b"png"
    sheet = read_png(png_raw)
    atlas_raw = atl_path.read_bytes()
    entries, codec = read_atlas(atlas_raw)

    old_dims = list(sheet.size)
    frames = []
    for e in entries:
        box = (e["x"], e["y"], e["x"] + e["w"], e["y"] + e["h"])
        if box[2] > sheet.width or box[3] > sheet.height:
            raise RescaleError(f"{e['n']}: 原图集 rect 越界 {box} vs {sheet.size}")
        frames.append(sheet.crop(box))

    new_entries = [rescale_entry(e, k) for e in entries]
    scaled = [
        f.resize((n["w"], n["h"]), Image.Resampling.NEAREST)
        for f, n in zip(frames, new_entries)
    ]

    width = max(512, max(n["w"] for n in new_entries) + 2 * PAD)
    height = repack(new_entries, width)
    if height > MAX_TEXTURE:
        for candidate in (1024, 2048, 4096):
            width = candidate
            height = repack(new_entries, width)
            if height <= MAX_TEXTURE:
                break
    if height > MAX_TEXTURE or width > MAX_TEXTURE:
        raise RescaleError(f"重排后仍超上限 {width}x{height}")

    out = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for img, n in zip(scaled, new_entries):
        out.alpha_composite(img, (n["x"], n["y"]))

    # --- 自检:条目数/顺序/名字/越界/构图 ---
    if len(new_entries) != len(entries):
        raise RescaleError("条目数变了")
    for a, b in zip(entries, new_entries):
        if a["n"] != b["n"]:
            raise RescaleError("条目顺序或名字变了")
        if b["x"] + b["w"] > width or b["y"] + b["h"] > height:
            raise RescaleError(f"{b['n']}: 重排后越界")
        cx_old = (-a["fx"] + a["w"] / 2) / a["fw"]
        cx_new = (-b["fx"] + b["w"] / 2) / b["fw"]
        gl_old = (-a["fy"] + a["h"]) / a["fh"]
        gl_new = (-b["fy"] + b["h"]) / b["fh"]
        if abs(cx_old - cx_new) > 0.03 or abs(gl_old - gl_new) > 0.03:
            raise RescaleError(
                f"{b['n']}: 构图漂移 cx {cx_old:.3f}->{cx_new:.3f} "
                f"地线 {gl_old:.3f}->{gl_new:.3f}")

    new_png = write_png(out, lowercase)
    new_atlas = write_atlas(new_entries, codec, atlas_raw)
    back, _ = read_atlas(new_atlas)
    if back != new_entries:
        raise RescaleError("图集往返自检不一致")
    if read_png(new_png).size != (width, height):
        raise RescaleError("回读 PNG 尺寸不符")

    report = {
        "stem": stem,
        "logical_png": png_logical,
        "logical_atlas": atl_logical,
        "frames": len(entries),
        "sheet_before": old_dims,
        "sheet_after": [width, height],
        "median_wh_before": [sorted(e["w"] for e in entries)[len(entries) // 2],
                             sorted(e["h"] for e in entries)[len(entries) // 2]],
        "median_wh_after": [sorted(e["w"] for e in new_entries)[len(new_entries) // 2],
                            sorted(e["h"] for e in new_entries)[len(new_entries) // 2]],
        "fw_before": entries[0]["fw"],
        "fw_after": new_entries[0]["fw"],
        "png_bytes": [len(png_raw), len(new_png)],
        "applied": False,
    }
    if apply:
        suffix = f".bak-pixelrescale-{time.strftime('%Y%m%d-%H%M%S')}"
        for path, data in ((png_path, new_png), (atl_path, new_atlas)):
            backup = path.with_name(path.name + suffix)
            if not backup.exists():
                backup.write_bytes(path.read_bytes())
            path.write_bytes(data)
        report["applied"] = True
        report["backup_suffix"] = suffix
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--code-name", required=True)
    p.add_argument("--factor", type=float, required=True,
                   help="再缩倍率 k(>1 表示缩小,2 = 再缩一半)")
    p.add_argument("--stems", default="sprite_sheet,special_sprite_sheet")
    p.add_argument("--store",
                   default=r"弹国服/WorldFlipper/dummy/download/production/upload")
    p.add_argument("--apply", action="store_true",
                   help="真写盘(默认只干跑并打印报告)")
    args = p.parse_args(argv)
    if args.factor <= 1:
        raise SystemExit("--factor 必须 > 1")
    s = salt()
    root = Path(args.store)
    reports = [process(root, args.code_name, stem.strip(), args.factor, s, args.apply)
               for stem in args.stems.split(",")]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
