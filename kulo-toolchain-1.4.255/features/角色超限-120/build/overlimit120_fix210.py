# -*- coding: utf-8 -*-
"""1.4.209 → 1.4.210：超限结晶图标修复（原图 A 左上被裁、主体偏左上 → 换完整居中的同款龙纹 A）。

只放两处图标文件：c3 缩略图 item/materials/mod/overlimit/overlimit_crystal.png（20×20），
c4 图集 item_icon/sprite_sheet.png（只改 207 追加的那 40×40 一格，图集 atlas 不变不发）。
用法：python overlimit120_fix210.py [--write]
"""
import hashlib, io, json, sys, zipfile
from pathlib import Path
from PIL import Image
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
import os
os.environ.setdefault("WF_TIP", "205")
import base149 as B
import wf_mod_tool as M
import zlib

OUT = Path(r"D:/WF/out/角色超限-120")
P207 = OUT / "patch/pinball-1.4.206-1.4.207-1-overlimit120-wagner-local.zip"
SRC = OUT / "art/item/overlimit_crystal_A_fix.png"
NAME = "pinball-1.4.209-1.4.210-1-overlimit-crystal-icon-fix-local.zip"
C3 = "item/materials/mod/overlimit/overlimit_crystal.png"
SHEET, ATLAS = "item_icon/sprite_sheet.png", "item_icon/sprite_sheet.atlas.amf3.deflate"
C4 = "item_icon/materials/mod/overlimit/overlimit_crystal"


def load_png(raw):
    b = bytearray(raw); b[1:4] = b"PNG"
    return Image.open(io.BytesIO(bytes(b))).convert("RGBA")


def store_png(img):
    buf = io.BytesIO(); img.save(buf, "PNG"); b = bytearray(buf.getvalue()); b[1:4] = b"png"
    return bytes(b)


icon40 = Image.open(SRC).convert("RGBA")
assert icon40.size == (40, 40)
bb = icon40.getbbox()
assert bb[0] <= 3 and bb[1] <= 3 and bb[2] >= 37 and bb[3] >= 37, bb      # 完整铺满、四边对称
icon20 = icon40.resize((20, 20), Image.LANCZOS)
icon20.putalpha(icon20.getchannel("A").point(lambda v: 255 if v >= 128 else 0))

with zipfile.ZipFile(P207) as z:
    sheet = load_png(z.read(B.member(SHEET)))
    atlas = M.AMF3Reader(zlib.decompress(z.read(B.member(ATLAS)), -15)).read_value()
e = [x for x in atlas if x["n"] == C4]
assert len(e) == 1 and (e[0]["w"], e[0]["h"]) == (40, 40) and not e[0].get("r"), e
x, y = e[0]["x"], e[0]["y"]
new = sheet.copy()
new.paste(Image.new("RGBA", (40, 40)), (x, y))
new.alpha_composite(icon40, (x, y))
# 其余像素逐字节不变
a0, a1 = sheet.tobytes(), new.tobytes()
W = sheet.size[0]
diff_rows = {i // (W * 4) for i in range(0, len(a0), 4) if a0[i:i + 4] != a1[i:i + 4]}
assert diff_rows and min(diff_rows) >= y and max(diff_rows) < y + 40
files = {C3: store_png(icon20), SHEET: store_png(new)}
members = {B.member(lp): d for lp, d in files.items()}
print(json.dumps({"slot": [x, y], "files": sorted(files)}, ensure_ascii=False))
if "--write" in sys.argv:
    path = OUT / "patch" / NAME
    assert not path.exists()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "applies_on": "1.4.209", "version": "1.4.210", "logical_paths": {B.member(lp): lp for lp in files}}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}))
