#!/usr/bin/env python
"""图标评审拼板：官方同类 / 现图 / 新图，各按 1×、2×、6× 贴在对应稀有度底框上，c4 另列 1× 与 3×。

只读：live store（官方子纹理、底框、现有自制图标）与本目录 icons/；写一张 PNG（默认设计稿目录下 icons_review.png）。
底框 = scene/general/sprite_sheet 的 thumbnail-assets/item_<稀有度>（72×72）；游戏内缩略图是底框 ×2 = 144、
c3 ×6 最近邻 = 120 居中（ItemThumbnailView :115），这里 6× 就按这个比例贴，2×/1× 等比缩小。
用法：python mod-tools/assets/weapon-awaken/build_review.py [--out PATH]
"""
from __future__ import annotations

from wf.paths import root_path

import argparse
import io
import sys
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent.parent
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(HERE))

import build_icons as B  # noqa: E402

DEFAULT_OUT = Path(('${WF_ROOT}/out/武器觉醒与新掉落-20260928/icons_review.png'.replace("${WF_ROOT}", str(root_path()))))
PLATES = {1: "item_white", 2: "item_bronze", 3: "item_silver", 4: "item_gold", 5: "item_rainbow"}
ITEM_SHEET, ICON_SHEET, SCENE_SHEET = "item/sprite_sheet", "item_icon/sprite_sheet", "scene/general/sprite_sheet"

#: key → ((官方同类子纹理, 说明), 第二个官方参照或 None, 现 c3 逻辑路径, 现 c4 子纹理)
ROWS = {
    "king_coin": (("item/materials/boss_coin/owl_3", "领主币(紫)"), ("item/materials/boss_coin/owl_2", "领主币(金)"), None, None),
    "forbidden_star_steel": (("item/materials/awaking_crystal/general/equipment_awaking_crystal_5", "★5星铁钢"),
                             ("item/materials/awaking_crystal/general/equipment_awaking_crystal_4", "★4星铁钢(映射源)"), None, None),
    "deathbringer_blueprint_v2": (("item/materials/event/side_story_event/side_story_event_quest_unlock_certificate", "解锁证书"),
                                  ("item/materials/elements/blue/item_aether_blue_03", "卷轴"),
                                  "item/materials/mod/five_boss/deathbringer_blueprint",
                                  "item_icon/materials/mod/five_boss/deathbringer_blueprint"),
    "deep_crystal_v2": (("item/materials/equipment_enhancement_materials/equipment_enhancement_material_blue_r5", "记忆晶(蓝)"),
                        ("item/materials/event/target_item_drop_event/yuragi_no_kesshou", "摇曳结晶"),
                        "item/materials/mod/five_boss/deep_crystal", "item_icon/materials/mod/five_boss/deep_crystal"),
    "fivefold_clear_badge_v2": (("item/etc/degree", "称号勋章"), ("item/materials/event/haniwa_carnival/haniwa_medal_gold", "埴轮金牌"),
                                "item/materials/mod/five_boss/fivefold_clear_badge",
                                "item_icon/materials/mod/five_boss/fivefold_clear_badge"),
    "five_king_core_v2": (("item/materials/event/boss_epuration_event/boss_epuration_point", "歼灭心核"),
                          ("item/materials/event/challenge_dungeon/event_abyss_matter", "深渊物质"),
                          "item/materials/mod/five_boss/five_king_core", "item_icon/materials/mod/five_boss/five_king_core"),
    "deep_realm_ticket": (("item/materials/event/hard_multi/extreme_multi_battle_token", "高难多人勋章(设计母本)"), None,
                          "item/materials/mod/five_boss/deep_realm_ticket", "item_icon/materials/mod/five_boss/deep_realm_ticket"),
    "contradiction_crystal": (("item/materials/awaking_crystal/general/awaking_crystal_04", "破星结晶★4"),
                              ("item/materials/elements/white/item_jewel_light_04", "光元素★4"),
                              "item/materials/mod/paradox/contradiction_crystal", "item_icon/materials/mod/five_boss/deep_crystal"),
    "paradox_core": (("item/materials/event/challenge_dungeon/event_abyss_matter", "深渊物质"),
                     ("item/materials/event/challenge_dungeon/yumemi_no_monsho_05", "梦见纹章"),
                     "item/materials/mod/paradox/paradox_core", "item_icon/materials/mod/five_boss/five_king_core"),
}

#: key → 同屏邻居的道具 ID：按 live 道具表的 c3 / c17 取实际图标与底框，贴在官方同类列末尾，给作者比轮廓撞不撞。
#: 凭证在五重商店类目 99 与武器扭蛋券（999019 单抽、999020 十连）同列出售，三者同为 ★5 彩虹底框。
NEIGHBOURS = {"deep_realm_ticket": ("999019", "999020")}
ITEM_TABLE = "master/item/item.orderedmap"

BG = (38, 40, 48, 255)
DARK = (24, 26, 32, 255)
FG = (232, 232, 238, 255)
DIM = (170, 172, 184, 255)
GOLD = (255, 214, 120, 255)


class Store:
    def __init__(self):
        import wf_assets
        import wf_mod_tool as core
        self.core, self.assets = core, wf_assets
        self.root = core.resolve_active_store()
        if self.root is None:
            raise SystemExit("no active store")
        self._sheets: dict[str, tuple[Image.Image, dict]] = {}

    def item_row(self, item_id: str) -> list | None:
        """live 道具表一行（23 列）；只读。"""
        if not hasattr(self, "_items"):
            import wf_share_update_codec as codec
            self._items = {}
            for key, blob in codec.unpack(self.raw(ITEM_TABLE)).items():
                rows = self.core.read_csv_lines(zlib.decompress(blob).decode("utf-8")) if blob else []
                self._items[key] = rows[0] if rows else []
        return self._items.get(str(item_id))

    def raw(self, logical: str) -> bytes | None:
        hit = self.assets.locate(self.root, logical)
        return hit[1].read_bytes() if hit else None

    def png(self, logical: str) -> Image.Image | None:
        data = self.raw(logical + ".png")
        return Image.open(io.BytesIO(self.assets.png_decode(data))).convert("RGBA") if data else None

    def sheet(self, base: str):
        if base not in self._sheets:
            img = self.png(base)
            ents = self.core.AMF3Reader(zlib.decompress(self.raw(base + ".atlas.amf3.deflate"), -15)).read_value()
            self._sheets[base] = (img, {e["n"]: e for e in ents})
        return self._sheets[base]

    def sub(self, base: str, name: str) -> Image.Image | None:
        img, idx = self.sheet(base)
        e = idx.get(name)
        if e is None:
            return None
        crop = img.crop((e["x"], e["y"], e["x"] + e["w"], e["y"] + e["h"]))
        if e.get("r"):                       # 存放时顺时针转过 90°，显示 = 逆时针转回（SubTexture.as:102-105）
            crop = crop.rotate(90, expand=True)
        fw, fh = e.get("fw", crop.width), e.get("fh", crop.height)
        out = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
        out.paste(crop, (-e.get("fx", 0), -e.get("fy", 0)))
        return out


def font(size: int, bold: bool = False):
    for f in ((r"C:/Windows/Fonts/msyhbd.ttc" if bold else r"C:/Windows/Fonts/msyh.ttc"), r"C:/Windows/Fonts/simhei.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


F, FS, FB, FT = font(13), font(11), font(15, True), font(20, True)


def on_plate(plate: Image.Image, icon: Image.Image | None, z: int) -> Image.Image:
    """底框 72 → 24·z（6× 时 144），图标 ×z 居中（6× 时 120 @ 12,12）。"""
    side = 24 * z
    base = plate.resize((side, side), Image.NEAREST if z >= 3 else Image.LANCZOS)
    if icon is not None:
        big = icon.resize((icon.width * z, icon.height * z), Image.NEAREST)
        base.alpha_composite(big, ((side - big.width) // 2, (side - big.height) // 2))
    return base


def triple(plate, icon) -> Image.Image:
    """6× | 2× | 1× 并排，底对齐。"""
    parts = [on_plate(plate, icon, z) for z in (6, 2, 1)]
    w = sum(p.width for p in parts) + 8 * 2
    out = Image.new("RGBA", (w, 144), BG)
    x = 0
    for p in parts:
        out.alpha_composite(p, (x, 144 - p.height))
        x += p.width + 8
    return out


def c4_block(c4: Image.Image | None) -> Image.Image:
    out = Image.new("RGBA", (190, 144), DARK)
    d = ImageDraw.Draw(out)
    if c4 is None:
        d.text((10, 60), "（无）", font=F, fill=DIM)
        return out
    out.alpha_composite(c4, (8, 144 - 8 - c4.height))
    big = c4.resize((c4.width * 3, c4.height * 3), Image.NEAREST)
    if big.height > 124:
        big = c4.resize((c4.width * 2, c4.height * 2), Image.NEAREST)
    out.alpha_composite(big, (58, (144 - big.height) // 2))
    d.text((6, 4), f"c4 {c4.width}×{c4.height}", font=FS, fill=DIM)
    return out


def stat(img: Image.Image | None) -> str:
    if img is None:
        return "—"
    m = B.metrics(img)
    return (f"{m['bbox'][0]}×{m['bbox'][1]} · {m['colors']}色 · 杂{m['speckle']:.2f}"
            + ("" if set(m["alphas"]) <= {0, 255} else " · 半透"))


def build(out_path: Path) -> Path:
    st = Store()
    plates = {r: st.sub(SCENE_SHEET, f"scene/general/sprite_sheet/thumbnail-assets/{n}") for r, n in PLATES.items()}
    rows = []
    for icon in B.ICONS:
        key = icon["key"]
        (off_name, off_label), second, cur_c3_name, cur_c4_name = ROWS[key]
        plate = plates[icon["rarity"]]
        off = st.sub(ITEM_SHEET, off_name)
        off2 = st.sub(ITEM_SHEET, second[0]) if second else None
        cur_c3 = st.png(cur_c3_name) if cur_c3_name else None
        if cur_c3 is None and key == "contradiction_crystal":
            cur_c3 = Image.open(TOOLS / "assets/paradox/paradox_shard.png").convert("RGBA")
        if cur_c3 is None and key == "paradox_core":
            cur_c3 = Image.open(TOOLS / "assets/paradox/paradox_core.png").convert("RGBA")
        cur_c4 = st.sub(ICON_SHEET, cur_c4_name) if cur_c4_name else None
        new_c3 = B.render(icon)
        new_c4 = B.ticket_41(new_c3) if key == B.TICKET_KEY else B.to_c4(new_c3)

        cols = []
        lab = Image.new("RGBA", (230, 144), BG)
        d = ImageDraw.Draw(lab)
        d.text((4, 6), f"{icon['item_id']} {icon['name']}", font=FB, fill=GOLD)
        d.text((4, 30), f"★{icon['rarity']}（{PLATES[icon['rarity']]}）", font=F, fill=FG)
        d.text((4, 50), icon["c3"].split("/")[-1], font=FS, fill=DIM)
        d.text((4, 66), "c4: …/" + "/".join(icon["c4"].split("/")[-2:]), font=FS, fill=DIM)
        if key == B.TICKET_KEY:
            d.text((4, 86), "交五重线：ticket_icon_20/41", font=FS, fill=DIM)
            d.text((4, 102), "41 = 40×40 贴 (0,1)", font=FS, fill=DIM)
        cur_note = "现 c4 借五重子纹理" if key in ("contradiction_crystal", "paradox_core") else ""
        if icon.get("rainbow"):
            cur_note = "彩虹件：锥形渐变 × 面亮度"
        if cur_note:
            d.text((4, 86), cur_note, font=FS, fill=DIM)
        cols.append(lab)
        o = triple(plate, off)
        extra = [on_plate(plate, off2, 6)] if off2 is not None else []
        neighbour_caps = []
        for nid in NEIGHBOURS.get(key, ()):
            row = st.item_row(nid)
            if not row:
                raise SystemExit(f"live 道具表没有 {nid}")
            img = st.sub(ITEM_SHEET, row[3]) or st.png(row[3])
            extra.append(on_plate(plates[int(row[17])], img, 6))
            neighbour_caps.append(f"{nid} {row[2]}")
        if extra:
            both = Image.new("RGBA", (o.width + sum(8 + e.width for e in extra), 144), BG)
            both.alpha_composite(o, (0, 0))
            x = o.width
            for e in extra:
                both.alpha_composite(e, (x + 8, 0))
                x += 8 + e.width
            o = both
        cols.append(o)
        cols.append(triple(plate, cur_c3) if cur_c3 is not None else Image.new("RGBA", (232, 144), BG))
        cols.append(c4_block(cur_c4))
        cols.append(triple(plate, new_c3))
        cols.append(c4_block(new_c4))
        caps = ["", f"官方 {off_label} · {stat(off)}" + (f"　｜　{second[1]}" if second else "")
                + (f"　｜　同店：{' / '.join(neighbour_caps)}" if neighbour_caps else ""), f"现 c3 · {stat(cur_c3)}" if cur_c3 is not None else "现：无（新道具）",
                "现 c4", f"新 c3 · {stat(new_c3)}", "新 c4 = c3×2"]
        rows.append((cols, caps))

    heads = ["道具", "官方同类（6× · 2× · 1× ｜ 第二参照或同店邻居 6×）", "现图 c3", "现图 c4", "新图 c3", "新图 c4"]
    gap = 14
    widths = [max(r[0][i].width for r in rows) for i in range(len(heads))]
    row_h = 144 + 24
    top = 92
    W = sum(widths) + gap * (len(widths) + 1)
    H = top + row_h * len(rows) + 30
    sheet = Image.new("RGBA", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    d.text((gap, 10), "武器觉醒与新掉落 · 材料图标评审（官方 / 现图 / 新图）· 2026-09-28", font=FT, fill=(255, 255, 255, 255))
    d.text((gap, 40), "6× = 游戏内缩略图尺寸（底框 72×2=144，c3 20×6=120 居中，最近邻）；2×、1× 同比缩小。c4 = 掉落条/图鉴小图标，左 1× 原尺寸、右放大。",
           font=F, fill=DIM)
    x = gap
    for i, h in enumerate(heads):
        d.text((x, 66), h, font=FB, fill=GOLD)
        x += widths[i] + gap
    y = top
    for cols, caps in rows:
        x = gap
        for i, c in enumerate(cols):
            sheet.alpha_composite(c, (x, y))
            if caps[i]:
                d.text((x, y + 146), caps[i], font=FS, fill=FG)
            x += widths[i] + gap
        y += row_h
    d.text((gap, H - 24), "新图门禁（build_icons.gate，描边阈值同构建器）：20×20、alpha 仅 0/255、包围盒达稀有度下限、"
           "描边为主色压暗（最大通道≥40、s≥0.4、v 0.2–0.5、色相随物件）、色数≤17、孤立杂色≤0.10、c4 = c3×2；"
           "★5 彩虹件免色数与描边集中度，改为描边逐像素压暗。",
           font=FS, fill=DIM)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(out_path)
    return out_path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    p = build(args.out)
    print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
