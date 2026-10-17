# -*- coding: utf-8 -*-
"""把 pixelart/special 的 frame 注册原点对齐到图集真实画布中心。

## 病症
2026-09-01 实测:歼灭者五人组在**角色列表/详情格子**里像素小人整体向左上偏。
战斗里看不出来 —— `MemberView.as:135` 调 `alignPivot(CENTER, CENTER)`,
按实际顶点包围盒重算枢轴,把常量注册偏移抵消掉了。而
`CharacterCellView.as:1712-1719` 只做 `character.scale /= 6; addChild(...)`,
既不 alignPivot 也不设 x/y,注册偏移原样上屏。

## 判据
局部偏移 = median(-fx + w/2) + frame.x。全库正常角色恒在 **0.0 ~ +0.5**
(官方 fire_dragon / dimension_witch / ginovi / black_wolf_knight,自制
cnmod_epuration_empress / white_tiger_ghost_playable 全部验过)。
歼灭者五人组是 -40 ~ -64:图集按 512x512 画框声明,但帧其实画在
431/385/412 的画布上,美术居中于**真画布**,而 frame.x 写死 -256。

## 修法
只改 `*.frame.amf3.deflate` 里的 x/y 两个数,设成 -round(median cx/cy)。
**不动图集、不动图、不动 timeline** —— 与官方 boss->可玩配方同一条纪律
(那边 timeline 逐字节相同)。fw/fh 保持 512 是安全的:Starling 的 getBounds
读顶点而不是 frame 矩形(Texture.as:348 把顶点放在 left=-frame.x),所以
fw 不参与定位。
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core  # noqa: E402
import wf_pixel_rescale as rescale  # noqa: E402

# X 与 Y 是**两套不同的约定**,别混用(2026-09-01 实测,别再按"垂直居中"推):
#   X = 水平中心:  median(-fx + w/2) + frame.x
#       正常角色实测 0.0 ~ +0.5(官方 fire_dragon/dimension_witch/ginovi/
#       black_wolf_knight,自制 white_tiger_ghost/cnmod_epuration_empress 全部)
#   Y = **地线**(脚底),不是垂直中心: median(-fy + h) + frame.y
#       正常角色 -16 ~ +19.5;两个已验证的 512 画布自制角色恰好 0.0。
#       同一批角色的"垂直中心"量散在 -15 ~ -44,没有带 —— 用它当判据会拉歪。
ACCEPT_X = (-1.0, 1.5)
ACCEPT_Y = (-20.0, 20.0)

SHEETS = (("sprite_sheet", "pixelart"), ("special_sprite_sheet", "special"))


class AlignError(RuntimeError):
    pass


def _read_amf(path: Path):
    raw = path.read_bytes()
    for wbits in (-15, 15):
        for offset in (0, 4):
            try:
                return core.AMF3Reader(zlib.decompress(raw[offset:], wbits)).read_value(), \
                    (wbits, offset, raw)
            except Exception:
                continue
    raise AlignError(f"{path}: AMF3 解不出")


def _write_amf(value, codec, path: Path) -> bytes:
    wbits, offset, raw = codec
    try:
        body = core.encode_amf3(value)
    except AttributeError:
        import wf_dsl
        body = wf_dsl.encode_amf3(value)
    comp = zlib.compressobj(9, zlib.DEFLATED, wbits)
    return raw[:offset] + comp.compress(body) + comp.flush()


def measure(root: Path, code_name: str, sheet: str, frame_stem: str, salt: str):
    atlas_path = rescale.store_path(
        root, f"character/{code_name}/pixelart/{sheet}.atlas.amf3.deflate", salt)
    frame_path = rescale.store_path(
        root, f"character/{code_name}/pixelart/{frame_stem}.frame.amf3.deflate", salt)
    if not atlas_path.exists() or not frame_path.exists():
        return None
    entries, _ = rescale.read_atlas(atlas_path.read_bytes())
    frame, codec = _read_amf(frame_path)
    if not isinstance(frame, dict):
        raise AlignError(f"{code_name}/{frame_stem}: frame 不是 map")
    cx = statistics.median([-e["fx"] + e["w"] / 2 for e in entries])
    cy = statistics.median([-e["fy"] + e["h"] for e in entries])   # 地线,非中心
    return {
        "code_name": code_name,
        "sheet": sheet,
        "frame_stem": frame_stem,
        "frame_path": frame_path,
        "frame": frame,
        "codec": codec,
        "median_cx": cx,
        "median_cy": cy,
        "offset_x": cx + frame["x"],
        "offset_y": cy + frame["y"],
        "want_x": -round(cx),
        "want_y": -round(cy),
        "frames": len(entries),
    }


def align(root: Path, code_name: str, salt: str, apply: bool) -> list[dict]:
    out = []
    suffix = f".bak-framealign-{time.strftime('%Y%m%d-%H%M%S')}"
    for sheet, frame_stem in SHEETS:
        m = measure(root, code_name, sheet, frame_stem, salt)
        if m is None:
            continue
        new_off_x = m["median_cx"] + m["want_x"]
        new_off_y = m["median_cy"] + m["want_y"]
        if not (ACCEPT_X[0] <= new_off_x <= ACCEPT_X[1]
                and ACCEPT_Y[0] <= new_off_y <= ACCEPT_Y[1]):
            raise AlignError(
                f"{code_name}/{frame_stem}: 修正后偏移 x={new_off_x:.1f} y={new_off_y:.1f} "
                f"不在 X{ACCEPT_X} / Y{ACCEPT_Y} —— 说明帧内离散度太大,"
                "不是常量注册偏移,别用这个工具硬拉")
        record = {
            "code_name": code_name,
            "frame_stem": frame_stem,
            "frames": m["frames"],
            "before": [m["frame"]["x"], m["frame"]["y"]],
            "after": [m["want_x"], m["want_y"]],
            "offset_before": [round(m["offset_x"], 1), round(m["offset_y"], 1)],
            "offset_after": [round(new_off_x, 1), round(new_off_y, 1)],
            "changed": (m["frame"]["x"], m["frame"]["y"]) != (m["want_x"], m["want_y"]),
            "applied": False,
        }
        if apply and record["changed"]:
            new_frame = dict(m["frame"])
            new_frame["x"] = m["want_x"]
            new_frame["y"] = m["want_y"]
            data = _write_amf(new_frame, m["codec"], m["frame_path"])
            back, _ = _read_amf_bytes(data)
            if back != new_frame:
                raise AlignError(f"{code_name}/{frame_stem}: 往返自检不一致")
            backup = m["frame_path"].with_name(m["frame_path"].name + suffix)
            if not backup.exists():
                backup.write_bytes(m["frame_path"].read_bytes())
            m["frame_path"].write_bytes(data)
            record["applied"] = True
            record["backup_suffix"] = suffix
            record["logical"] = (f"character/{code_name}/pixelart/"
                                 f"{frame_stem}.frame.amf3.deflate")
        elif record["changed"]:
            record["logical"] = (f"character/{code_name}/pixelart/"
                                 f"{frame_stem}.frame.amf3.deflate")
        out.append(record)
    return out


def _read_amf_bytes(raw: bytes):
    for wbits in (-15, 15):
        for offset in (0, 4):
            try:
                return core.AMF3Reader(zlib.decompress(raw[offset:], wbits)).read_value(), \
                    (wbits, offset, raw)
            except Exception:
                continue
    raise AlignError("回读 AMF3 失败")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--code-name", action="append", required=True,
                   help="可多次;每个角色的两张表都会处理")
    p.add_argument("--store",
                   default=r"弹国服/WorldFlipper/dummy/download/production/upload")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)
    salt = rescale.salt()
    root = Path(args.store)
    records = []
    for code_name in args.code_name:
        records.extend(align(root, code_name, salt, args.apply))
    print(json.dumps(records, ensure_ascii=False, indent=2))
    changed = [r["logical"] for r in records if r.get("changed")]
    if changed:
        print("\n需要发布的逻辑路径:")
        print(",".join(changed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
