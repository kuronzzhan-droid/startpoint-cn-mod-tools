# -*- coding: utf-8 -*-
"""给 15 把觉醒武器开一个独立的「深渊武装·觉醒」装备强化分类(第 5 个横幅)。

## 为什么
15 把武器(8000101..8000115)的 shop 行 col0 写的是 "3",落在官方
「机兵装备强化」分类里,没有自己的入口横幅。作者要的是独立入口。

## 改三处
1. `dynamic/equipment_enhancement/abyss_weapon_{banner,header}.png`
   —— 由 wf_abyss_weapon_banner.py 合成(1000x184 / 1440x556,照官方实测规格)。
2. `master/equipment_enhancement/equipment_enhancement_shop_category.orderedmap`
   新增键 "5",10 列,照官方行逐列对齐。
3. `master/equipment_enhancement/equipment_enhancement_shop.orderedmap`
   把引用这 15 把武器的行 col0 由 "3" 改成 "5"。

## 一条硬纪律(2026-09-01 C8601 事故换来的)
`how_to_play_content_id`(c6)和 c7 指向的内容**必须真实存在**,否则玩家一点
「玩法说明」就会 MasterBinaryMap key miss -> C8601,而 C8601 会**先删掉设备上
那张表再抛错**。所以这两列直接复用官方歼灭分类已验证存在的值,不自造新键。
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path

from PIL import Image

TOOLS = Path(__file__).resolve().parents[3]  # 仓库根（本文件在 wf/tools/<组>/ 下）
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core  # noqa: E402
import wf_pixel_rescale as rescale  # noqa: E402

PROD = Path(r"弹国服/WorldFlipper/dummy/download/production")
CATEGORY_LOGICAL = "master/equipment_enhancement/equipment_enhancement_shop_category.orderedmap"
SHOP_LOGICAL = "master/equipment_enhancement/equipment_enhancement_shop.orderedmap"
BANNER_LOGICAL = "dynamic/equipment_enhancement/abyss_weapon_banner.png"
HEADER_LOGICAL = "dynamic/equipment_enhancement/abyss_weapon_header.png"

NEW_KEY = "5"
#: c1 display_order（升序，负数合法且须全表互异）。作者 0928 横幅顺序 诅咒(-2) → 深渊(-1) → 官方 1–4；
#: 本脚本只在键不存在时新增，live 已有的行由 wf_enhancement_category_order 暂存改序。
DISPLAY_ORDER = "-1"
# 16 把:15 把深渊觉醒 + 死亡使者(五重决战商店那把)。作者要求强化页 16 把在一起。
WEAPONS = {f"80001{i:02d}" for i in range(1, 16)} | {"5900101"}
OLD_CATEGORY = "3"

ENHANCEMENT_LOGICAL = "master/equipment_enhancement/equipment_enhancement.orderedmap"
# c1 name.level / c3 pixelart.level / c5 description.level / c7 pixelart_effect_level
# `EquipmentEnhancementLogic` 的 getName/getPixelart/getDescription 都是
# `if (x.level <= 当前强化等级) return Some(...)`。这四列写成 120 意味着 +0..+119
# 全程回落到基础装备行 —— 面板不显示「觉醒」后缀。官方 5020042 与自制 5900101
# 都是 1/70/1/99,以它们为准。
LEVEL_COLUMNS = {1: "1", 3: "70", 5: "1", 7: "99"}


class CategoryError(RuntimeError):
    pass


def _write_png(path: Path, src: Path, apply: bool, stamp: str) -> dict:
    img = Image.open(src).convert("RGBA")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    raw = buf.getvalue()
    data = raw[:1] + b"png" + raw[4:]          # store 里 PNG 魔数是小写
    rec = {"path": str(path), "size": list(img.size), "bytes": len(data),
           "existed": path.exists(), "applied": False}
    if apply:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            bak = path.with_name(path.name + f".bak-abysscat-{stamp}")
            if not bak.exists():
                bak.write_bytes(path.read_bytes())
        path.write_bytes(data)
        rec["applied"] = True
    return rec


def run(art_dir: Path, apply: bool) -> dict:
    salt = rescale.salt()
    up = PROD / "upload"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    report: dict = {"images": [], "category": None, "shop_rows": 0, "applied": apply}

    # --- 1. 两张图 ---
    for logical, name in ((BANNER_LOGICAL, "abyss_weapon_banner.png"),
                          (HEADER_LOGICAL, "abyss_weapon_header.png")):
        src = art_dir / name
        if not src.is_file():
            raise CategoryError(f"缺素材 {src};先跑 wf_abyss_weapon_banner.py")
        report["images"].append(
            {"logical": logical,
             **_write_png(rescale.store_path(up, logical, salt), src, apply, stamp)})

    # --- 2. 分类行 ---
    cat_path = core.table_path(up, CATEGORY_LOGICAL)
    cat = core.read_orderedmap_file(cat_path, CATEGORY_LOGICAL)
    rows = cat.text_rows()
    template = core.read_csv_lines(rows["2"])[0]          # 歼灭分类,c6/c7 已验证存在
    if len(template) != 10:
        raise CategoryError(f"分类表列数变了: {len(template)}")
    new_row = [
        "abyss_weapon",              # c0 string_id
        DISPLAY_ORDER,               # c1 display_order
        template[2],                 # c2 照抄 '(None)'
        "深渊武装·觉醒",              # c3 名称
        BANNER_LOGICAL[:-4],         # c4 banner(逻辑路径不带 .png)
        HEADER_LOGICAL[:-4],         # c5 header
        template[6],                 # c6 how_to_play —— 复用已存在的,禁自造(C8601)
        template[7],                 # c7 同上
        "2000-01-01 00:00:00",       # c8 start_time 恒开
        template[9],                 # c9 end_time '(None)'
    ]
    if NEW_KEY in rows:
        report["category"] = {"action": "已存在", "row": core.read_csv_lines(rows[NEW_KEY])[0]}
    else:
        report["category"] = {"action": "新增", "key": NEW_KEY, "row": new_row,
                              "template": template}
        merged = dict(rows)
        merged[NEW_KEY] = core.write_csv_lines([new_row])
        cat.set_text_rows(merged)
        data = core.build_orderedmap(cat)
        tmp = Path("_tmp_cat.orderedmap"); tmp.write_bytes(data)
        back = core.read_orderedmap_file(tmp, CATEGORY_LOGICAL).text_rows(); tmp.unlink()
        if list(back) != list(rows) + [NEW_KEY]:
            raise CategoryError("分类表键序不符")
        for k in rows:
            if back[k] != rows[k]:
                raise CategoryError(f"分类表既有行 {k} 被改动")
        if core.read_csv_lines(back[NEW_KEY])[0] != new_row:
            raise CategoryError("新分类行往返不一致")
        if apply:
            bak = cat_path.with_name(cat_path.name + f".bak-abysscat-{stamp}")
            if not bak.exists():
                bak.write_bytes(cat_path.read_bytes())
            cat_path.write_bytes(data)

    # --- 3. shop 行改分类 ---
    shop_path = core.table_path(up, SHOP_LOGICAL)
    shop = core.read_orderedmap_file(shop_path, SHOP_LOGICAL)
    srows = shop.text_rows()
    changed = {}
    out = {}
    for k, v in srows.items():
        cells = core.read_csv_lines(v)[0]
        if cells[0] == OLD_CATEGORY and WEAPONS & set(cells):
            new = list(cells)
            new[0] = NEW_KEY
            out[k] = core.write_csv_lines([new])
            changed[k] = (cells[0], NEW_KEY)
        else:
            out[k] = v
    report["shop_rows"] = len(changed)
    report["shop_sample"] = list(changed)[:6]
    if changed:
        shop.set_text_rows(out)
        data = core.build_orderedmap(shop)
        tmp = Path("_tmp_shop.orderedmap"); tmp.write_bytes(data)
        back = core.read_orderedmap_file(tmp, SHOP_LOGICAL).text_rows(); tmp.unlink()
        if list(back) != list(srows):
            raise CategoryError("shop 表键序变了")
        for k in srows:
            if k not in changed and back[k] != srows[k]:
                raise CategoryError(f"shop 无关行 {k} 被改动")
            if k in changed:
                cells = core.read_csv_lines(back[k])[0]
                old = core.read_csv_lines(srows[k])[0]
                if cells[0] != NEW_KEY or cells[1:] != old[1:]:
                    raise CategoryError(f"shop 行 {k} 除 c0 外被改动")
        if apply:
            bak = shop_path.with_name(shop_path.name + f".bak-abysscat-{stamp}")
            if not bak.exists():
                bak.write_bytes(shop_path.read_bytes())
            shop_path.write_bytes(data)
    # --- 4. 强化行的四个等级列 ---
    enh_path = core.table_path(up, ENHANCEMENT_LOGICAL)
    enh = core.read_orderedmap_file(enh_path, ENHANCEMENT_LOGICAL)
    erows = enh.text_rows()
    eout = {}
    efixed = {}
    for k, v in erows.items():
        cells = core.read_csv_lines(v)[0]
        if k in WEAPONS and any(cells[i] != want for i, want in LEVEL_COLUMNS.items()):
            new = list(cells)
            for i, want in LEVEL_COLUMNS.items():
                new[i] = want
            eout[k] = core.write_csv_lines([new])
            efixed[k] = {"before": [cells[i] for i in sorted(LEVEL_COLUMNS)],
                         "after": [LEVEL_COLUMNS[i] for i in sorted(LEVEL_COLUMNS)]}
        else:
            eout[k] = v
    report["enhancement_rows"] = len(efixed)
    report["enhancement_sample"] = dict(list(efixed.items())[:2])
    if efixed:
        enh.set_text_rows(eout)
        data = core.build_orderedmap(enh)
        tmp = Path("_tmp_enh.orderedmap"); tmp.write_bytes(data)
        back = core.read_orderedmap_file(tmp, ENHANCEMENT_LOGICAL).text_rows(); tmp.unlink()
        if list(back) != list(erows):
            raise CategoryError("enhancement 表键序变了")
        for k in erows:
            if k not in efixed and back[k] != erows[k]:
                raise CategoryError(f"enhancement 无关行 {k} 被改动")
            if k in efixed:
                a = core.read_csv_lines(erows[k])[0]
                b = core.read_csv_lines(back[k])[0]
                for i in range(len(a)):
                    if i in LEVEL_COLUMNS:
                        if b[i] != LEVEL_COLUMNS[i]:
                            raise CategoryError(f"{k} c{i} 未写入")
                    elif a[i] != b[i]:
                        raise CategoryError(f"{k} c{i} 被误改")
        if apply:
            bak = enh_path.with_name(enh_path.name + f".bak-abysscat-{stamp}")
            if not bak.exists():
                bak.write_bytes(enh_path.read_bytes())
            enh_path.write_bytes(data)

    if apply:
        report["backup_suffix"] = f".bak-abysscat-{stamp}"
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--art", required=True, help="wf_abyss_weapon_banner.py 的输出目录")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)
    report = run(Path(args.art), args.apply)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("\n需要发布:")
    print(",".join([BANNER_LOGICAL, HEADER_LOGICAL, CATEGORY_LOGICAL, SHOP_LOGICAL,
                     ENHANCEMENT_LOGICAL]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
