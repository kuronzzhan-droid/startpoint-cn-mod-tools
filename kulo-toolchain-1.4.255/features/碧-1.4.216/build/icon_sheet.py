# -*- coding: utf-8 -*-
"""改动汇报页用图标精灵图:96×96 格,WebP q80 + JSON 索引。视图=测试服链 1.4.218。只读。"""
import io, os, json, zipfile, zlib, base64
os.environ["WF_EXTRA_DIRS"] = r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(218)
from base149 import *
from base149 import _INDEX, SCR
import sys; sys.path.insert(0, str(TOOLS))
import wf_assets, wf_dsl
from PIL import Image

OUT = Path(r"D:/WF/out/碧-1.4.216/icons"); OUT.mkdir(exist_ok=True)
CELL = 96
KINDS = ["medium_upload", "upload", "android_upload"]


def raw(lp):
    h = member(lp).split("upload/")[1]
    for k in KINDS:
        n = f"production/{k}/{h}"
        if n in _INDEX:
            with zipfile.ZipFile(_INDEX[n]) as z: return z.read(n)
        p = SCR / "store131/production" / k / h
        if p.exists() and p.stat().st_size > 16: return p.read_bytes()
    return None


def png(lp):
    b = raw(lp + ".png")
    if b is None: return None
    return Image.open(io.BytesIO(wf_assets.png_decode_stored(b))).convert("RGBA")


def from_atlas(sheet_lp, name):
    a = raw(sheet_lp + ".atlas.amf3.deflate"); im = png(sheet_lp)
    if a is None or im is None: return None
    for e in wf_dsl.parse_dsl(zlib.decompress(a, -15))["tree"]:
        if e["n"] == name:
            c = im.crop((e["x"], e["y"], e["x"] + e["w"], e["y"] + e["h"]))
            return c.rotate(90, expand=True) if e.get("r") else c
    return None


CH = {k: row(v) for k, v in load("master/character/character.orderedmap").items()}
TX = {k: row(v) for k, v in load("master/character/character_text.orderedmap").items()}
EQ = {k: row(v) for k, v in load("master/item/equipment.orderedmap").items()}
IT = {k: row(v) for k, v in load("master/item/item.orderedmap").items()}

CHARS = "129952 129999 159997 159996 149986 149987 151159 261089 169994 149990 149998 149989 149999 159991 139995 179999 169999 169988 159994 169995 129992 139991 129998 129997 129991 139992 119989 149997 159998 139990 119996 119990 169989 111183 141099 169978 159992".split()
WEAP = ["5930001", "5930002"] + [f"59300{g:02d}{i}" if g < 10 else f"5930{g*10+i:03d}" for g in range(1, 27) for i in (1, 2)]
WEAP = ["5930001", "5930002"] + [str(5930000 + g * 10 + i) for g in range(1, 27) for i in (1, 2)]
WEAP += [str(x) for x in range(8000116, 8000125)] + ["5920001"]
WEAP += ["5910101", "5910110", "5910111", "5910107", "5910127", "5910128", "5910129", "8000107"]
WEAP += [str(x) for x in range(5990001, 5990007)]
ITEMS = os.environ.get("ITEMS", "10000320,10000302,10000401").split(",")
_coin = [k for k, r in {k: row(v) for k, v in load("master/item/item.orderedmap").items()}.items() if "boss_coin" in r[3]]
print("boss coin items", _coin[:8])

entries, missing = [], []
for cid in CHARS:
    code = CH[cid][0] if cid in CH else None
    name = TX.get(cid, [None])[0]
    im = None
    if code:
        im = png(f"character/{code}/ui/square_132_132_0") or png(f"character/{code}/ui/square_0")
        if im is None:
            im = from_atlas(f"character/{code}/ui/illustration_setting_sprite_sheet", f"character/{code}/ui/square_132_132_0")
    (entries if im else missing).append((cid, name, im) if im else (cid, name, f"character/{code}/ui/square_132_132_0"))
for wid in WEAP:
    r = EQ.get(wid)
    if not r: missing.append((wid, None, "equipment 无此行")); continue
    im = png(r[6]) or from_atlas("item/sprite_sheet", r[6])
    (entries if im else missing).append((wid, r[1], im) if im else (wid, r[1], r[6]))
for iid in ITEMS:
    r = IT.get(iid)
    if not r: missing.append((iid, None, "item 无此行")); continue
    im = png(r[3]) or from_atlas("item/sprite_sheet", r[3])
    (entries if im else missing).append((iid, r[2], im) if im else (iid, r[2], r[3]))

cols = 12; rows_ = (len(entries) + cols - 1) // cols
sheet = Image.new("RGBA", (cols * CELL, rows_ * CELL), (0, 0, 0, 0))
index = {}
for i, (k, name, im) in enumerate(entries):
    t = im.crop(im.getbbox()) if im.getbbox() else im
    m = max(t.width, t.height)
    if m < CELL * 0.75:   # 像素小图标:整数倍最近邻放大
        f = max(1, int(CELL * 0.85 // m)); t = t.resize((t.width * f, t.height * f), Image.NEAREST)
    t.thumbnail((CELL, CELL), Image.LANCZOS)
    x, y = (i % cols) * CELL, (i // cols) * CELL
    sheet.paste(t, (x + (CELL - t.width) // 2, y + (CELL - t.height) // 2), t)
    index[k] = {"x": x, "y": y, "w": CELL, "h": CELL, "name": name}
sheet.save(OUT / "icons.webp", "WEBP", quality=80, method=6)
sheet.save(OUT / "icons_preview.png")
json.dump(index, open(OUT / "icons.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
json.dump([m[:2] + (m[2],) for m in missing], open(OUT / "missing.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("cells", len(entries), "sheet", sheet.size, "webp", (OUT / "icons.webp").stat().st_size, "missing", missing)
print("maou title", TX.get("169995", [None] * 4)[:4])
