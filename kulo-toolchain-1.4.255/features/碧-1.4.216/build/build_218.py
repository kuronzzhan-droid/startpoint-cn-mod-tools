# -*- coding: utf-8 -*-
"""1.4.218:修 6 角色切换立绘 C8004。
根因:灰的包里 character/cnmod_vyrn_dark/ui/illustration_setting_sprite_sheet 装的是一张通用 UI 图集
(square_*/thumb_* 等 20 条),没有立绘设置页要取的 full_shot_illustration_setting_0/1 两条子纹理。
修法:按官方/凉月同结构,从碧自己的 full_shot_1440_1920_0/1 裁出两张立绘设置缩略图,重做这张图集(png+atlas)。
其余成员不动。用法: python build_217.py [DRY=1]"""
import io, os, sys, json, zlib, zipfile, hashlib
os.environ["WF_EXTRA_DIRS"] = r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(217)
from base149 import *
from base149 import _INDEX, SCR
sys.path.insert(0, str(TOOLS))
import wf_dsl, wf_assets
from PIL import Image

CHARS = [c for c in os.environ.get("CIDS", "119998,179982,179983,179984,179985,179986").split(",")]
OUT = Path(__file__).resolve().parent.parent
FRAME = 500


def raw(lp, kind):
    h = member(lp).split("upload/")[1]; n = f"production/{kind}/{h}"
    if n in _INDEX:
        with zipfile.ZipFile(_INDEX[n]) as z: return z.read(n)
    p = SCR / "store131/production" / kind / h
    return p.read_bytes() if p.exists() and p.stat().st_size > 16 else None


def mem(lp, kind): return f"production/{kind}/" + member(lp).split("upload/")[1]


ly = raw("character/liangyue_onmyoji/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate", "upload")
assert wf_dsl.encode_amf3(wf_dsl.parse_dsl(zlib.decompress(ly, -15))["tree"]) == zlib.decompress(ly, -15), "atlas 编码器不能字节级往返"
TRM = q.parse_node(raw("master/generated/trimmed_image.orderedmap", "upload"))
FA = load("master/character/full_shot_image_attribute.orderedmap")
CH = load("master/character/character.orderedmap")
CI = load("master/generated/character_image.orderedmap")
data = {}; notes = {}; logical = {}
for CID in CHARS:
    C = row(CH[CID])[0]
    thumbs = []; note = []
    for i in ("0", "1"):
        src = i
        b = raw(f"character/{C}/ui/full_shot_1440_1920_{i}.png", "medium_upload") or raw(f"character/{C}/ui/full_shot_1440_1920_{i}.png", "upload")
        if b is None:
            src = "0"; b = raw(f"character/{C}/ui/full_shot_1440_1920_0.png", "medium_upload") or raw(f"character/{C}/ui/full_shot_1440_1920_0.png", "upload")
            note.append(f"无 _{i} 立绘,用 _0 代替")
        png = Image.open(io.BytesIO(wf_assets.png_decode_stored(b))).convert("RGBA")
        t = TRM.get(f"character/{C}/ui/full_shot_1440_1920_{src}")
        if t is None:
            t = CI.get(CID, {}).get(src); note.append(f"_{src} 偏移取 character_image")
        tx, ty = [int(v) for v in str(t).strip().split(",")[:2]]
        fx, fy = [int(v) for v in FA[CID][src].strip().split(",")[3:5]]
        lx, ly_ = fx - tx, fy - ty
        bb = png.getbbox()
        S = int(min(bb[2] - bb[0], bb[3] - bb[1]) * 0.8)
        left = max(bb[0], min(lx - S // 2, bb[2] - S)); top = max(bb[1], min(ly_ - int(S * 0.35), bb[3] - S))
        crop = png.crop((left, top, left + S, top + S)).resize((FRAME, FRAME), Image.LANCZOS)
        tb = crop.getbbox(); thumbs.append((i, crop.crop(tb), tb))
        print(f"{CID} {C} _{i}(src _{src}): png {png.size} face {lx},{ly_} crop {left},{top},{S} trim {tb}")
    w0, h0 = thumbs[0][1].size; w1, h1 = thumbs[1][1].size
    sheet = Image.new("RGBA", (w0 + 1 + w1, max(h0, h1)), (0, 0, 0, 0))
    sheet.paste(thumbs[0][1], (0, 0)); sheet.paste(thumbs[1][1], (w0 + 1, 0))
    tree = [{"n": f"character/{C}/ui/full_shot_illustration_setting_{i}", "w": im.size[0], "h": im.size[1], "x": x, "y": 0,
             "fx": -tb[0], "fy": -tb[1], "fw": FRAME, "fh": FRAME} for (i, im, tb), x in zip(thumbs, (0, w0 + 1))]
    buf = io.BytesIO(); sheet.save(buf, "PNG", optimize=True)
    amf = wf_dsl.encode_amf3(tree); assert wf_dsl.parse_dsl(amf)["tree"] == tree
    co = zlib.compressobj(9, zlib.DEFLATED, -15); atlas = co.compress(amf) + co.flush()
    lp_png = f"character/{C}/ui/illustration_setting_sprite_sheet.png"; lp_at = f"character/{C}/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate"
    for kind in ("medium_upload", "upload"):          # png 在哪个 variant 就替换哪个
        if raw(lp_png, kind) is not None: data[mem(lp_png, kind)] = wf_assets.png_encode(buf.getvalue()); logical[mem(lp_png, kind)] = lp_png
    assert raw(lp_at, "upload") is not None; data[mem(lp_at, "upload")] = atlas; logical[mem(lp_at, "upload")] = lp_at
    sheet.save(OUT / "illu" / f"fixed218_{CID}.png"); notes[CID] = note
print("members", len(data), notes)
if os.environ.get("DRY") == "1": sys.exit(0)

name = "pinball-1.4.217-1.4.218-1-illustration-sheet-fix6-local.zip"; p = OUT / "patch" / name
with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(data): zf.writestr(m, data[m])
blob = p.read_bytes()
integ = {"name": name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(data), "files": sorted(data),
         "member_sha256": {m: hashlib.sha256(data[m]).hexdigest() for m in sorted(data)},
         "logical_paths": logical, "notes": notes,
         "applies_on": "1.4.217", "version": "1.4.218", "part": "1/1",
         "log": ["修 119998/179982-179986 切换立绘 C8004:illustration_setting_sprite_sheet 缺 full_shot_illustration_setting_0/1;按凉月同结构从各自立绘裁两张缩略图重做 png+atlas"]}
p.with_name(p.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print("WROTE", name, len(blob), integ["sha256"])
