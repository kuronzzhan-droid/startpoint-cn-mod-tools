# -*- coding: utf-8 -*-
"""战斗记录 C8004 修复：把所有自制魂珠（装备同 ID 的 item 行）c3 缩略图补进常驻 item/sprite_sheet 图集。

根因：BattleHistoryDialogContentMemberView.run 用 view.asset.getTexture(item.thumbnailId) 同步取魂珠图，只认已加载图集子纹理；
官方魂珠 c3 全在 item/sprite_sheet 里，自制魂珠 c3 是独立 PNG ⇒ 打开带自制魂珠角色的战斗记录即 C8004（日志：deathbringer_final）。
做法照 1.4.128 repair_cursed_weapon_awaken_icon_preload：既有帧与像素逐字节保留，只在画布底部追加新行；item 表不动。

用法：WF_TIP=156 python soul_icon_atlas.py
"""
import hashlib
import io
import json
import os
import sys
import zipfile
from PIL import Image

os.environ.setdefault("WF_TIP", "156")
from base149 import *  # noqa
sys.path.insert(0, str(TOOLS))
import wf_battle_atlas_repack as atlas_codec  # noqa: E402

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.156-1.4.157-1-typed-dummies-record-fix-local.zip"
SHEET, ATLAS = "item/sprite_sheet.png", "item/sprite_sheet.atlas.amf3.deflate"
OTHER = ("item_icon/sprite_sheet", "item_sec/sprite_sheet", "scene/general/sprite_sheet")
PAD = 1


def main() -> int:
    sheet_raw, src1 = read_raw(SHEET)
    atlas_raw, src2 = read_raw(ATLAS)
    sheet = atlas_codec.decode_png(sheet_raw).convert("RGBA")
    atlas = atlas_codec.decode_atlas(atlas_raw)
    names = {r["n"] for r in atlas}
    for sh in OTHER:
        names |= {r["n"] for r in atlas_codec.decode_atlas(read_raw(sh + ".atlas.amf3.deflate")[0])}
    IT, EQ = load("master/item/item.orderedmap"), load("master/item/equipment.orderedmap")
    need = {}
    for k in EQ:
        if k in IT:
            c3 = row(IT[k])[3]
            if c3 not in names and c3 not in need:
                need[c3] = k
    icons = []
    for path, k in sorted(need.items()):
        raw, _ = read_raw(path + ".png")
        im = atlas_codec.decode_png(raw).convert("RGBA")
        icons.append((path, k, im))
    # 底部追加：按行排列，行高 = 本行最高 + PAD
    x, y, rowh = PAD, sheet.height + PAD, 0
    frames = []
    for path, k, im in icons:
        w, h = im.size
        if x + w + PAD > sheet.width:
            x, y, rowh = PAD, y + rowh + PAD, 0
        frames.append(({"n": path, "w": w, "h": h, "x": x, "y": y}, im))
        x += w + PAD
        rowh = max(rowh, h)
    height = y + rowh + PAD
    out = Image.new("RGBA", (sheet.width, height))
    out.paste(sheet, (0, 0))
    for fr, im in frames:
        out.paste(im, (fr["x"], fr["y"]))
    new_atlas = atlas + [fr for fr, _ in frames]
    sheet_payload = atlas_codec.encode_png(out)
    atlas_payload = atlas_codec.encode_atlas(new_atlas)
    # 复核
    back = atlas_codec.decode_png(sheet_payload)
    assert back.size == out.size and back.tobytes() == out.tobytes()
    assert back.crop((0, 0, sheet.width, sheet.height)).tobytes() == sheet.tobytes()
    back_atlas = atlas_codec.decode_atlas(atlas_payload)
    assert back_atlas[:len(atlas)] == atlas and len(back_atlas) == len(atlas) + len(frames)
    for fr, im in frames:
        assert back.crop((fr["x"], fr["y"], fr["x"] + fr["w"], fr["y"] + fr["h"])).tobytes() == im.tobytes()
    assert sheet_payload[:4] == b"\x89png"
    files = {SHEET: sheet_payload, ATLAS: atlas_payload}
    members = {member(lp): d for lp, d in files.items()}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.156", "version": "1.4.157",
             "baseline_sheet": [sheet.width, sheet.height], "output_sheet": list(out.size),
             "baseline_frames": len(atlas), "added_frames": [fr["n"] for fr, _ in frames]}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    from collections import Counter
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members", "baseline_sheet", "output_sheet", "baseline_frames")},
                     ensure_ascii=False), "sources", src1, src2)
    print("added", len(frames), Counter(p.rsplit("/", 1)[0] for p in need), Counter(im.size for _, _, im in icons))
    return 0


if __name__ == "__main__":
    from PIL import Image
    raise SystemExit(main())
