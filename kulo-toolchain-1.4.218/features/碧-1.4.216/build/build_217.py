# -*- coding: utf-8 -*-
"""1.4.217:修碧 169978 切换立绘 C8004。
根因:灰的包里 character/cnmod_vyrn_dark/ui/illustration_setting_sprite_sheet 装的是一张通用 UI 图集
(square_*/thumb_* 等 20 条),没有立绘设置页要取的 full_shot_illustration_setting_0/1 两条子纹理。
修法:按官方/凉月同结构,从碧自己的 full_shot_1440_1920_0/1 裁出两张立绘设置缩略图,重做这张图集(png+atlas)。
其余成员不动。用法: python build_217.py [DRY=1]"""
import io, os, sys, json, zlib, zipfile, hashlib
os.environ["WF_EXTRA_DIRS"] = r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(216)
from base149 import *
from base149 import _INDEX, SCR
sys.path.insert(0, str(TOOLS))
import wf_dsl, wf_assets
from PIL import Image

C = "cnmod_vyrn_dark"; CID = "169978"
OUT = Path(__file__).resolve().parent.parent
FRAME = 500


def raw(lp, kind):
    h = member(lp).split("upload/")[1]; n = f"production/{kind}/{h}"
    if n in _INDEX:
        with zipfile.ZipFile(_INDEX[n]) as z: return z.read(n)
    return (SCR / "store131/production" / kind / h).read_bytes()


def mem(lp, kind): return f"production/{kind}/" + member(lp).split("upload/")[1]


# 编码器自检:凉月图集字节级往返
ly = raw("character/liangyue_onmyoji/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate", "upload")
ly_tree = wf_dsl.parse_dsl(zlib.decompress(ly, -15))["tree"]
assert wf_dsl.encode_amf3(ly_tree) == zlib.decompress(ly, -15), "atlas 编码器不能字节级往返"

tr = q.parse_node(raw("master/generated/trimmed_image.orderedmap", "upload")) if False else None
fa = load("master/character/full_shot_image_attribute.orderedmap")[CID]
TRIM = {"0": (379, 143), "1": (404, 165)}  # trimmed_image character/cnmod_vyrn_dark/ui/full_shot_1440_1920_<i>
thumbs = []
for i in ("0", "1"):
    png = Image.open(io.BytesIO(wf_assets.png_decode_stored(raw(f"character/{C}/ui/full_shot_1440_1920_{i}.png", "medium_upload")))).convert("RGBA")
    W, H = png.size
    fx, fy = [int(v) for v in fa[i].strip().split(",")[3:5]]
    lx, ly_ = fx - TRIM[i][0], fy - TRIM[i][1]          # 脸在 PNG 内的坐标
    bb = png.getbbox()                                  # 有色内容框
    S = int(min(bb[2] - bb[0], bb[3] - bb[1]) * 0.8)    # 正方取景:内容短边 80%
    left = max(bb[0], min(lx - S // 2, bb[2] - S)); top = max(bb[1], min(ly_ - int(S * 0.35), bb[3] - S))
    crop = png.crop((left, top, left + S, top + S)).resize((FRAME, FRAME), Image.LANCZOS)
    tb = crop.getbbox()
    thumbs.append((i, crop.crop(tb), tb))
    print(f"_{i}: png {W}x{H} face {lx},{ly_} crop {left},{top},{S} -> trim {tb}")

# 打包:左右并排,间隔 1px
w0, h0 = thumbs[0][1].size; w1, h1 = thumbs[1][1].size
sheet = Image.new("RGBA", (w0 + 1 + w1, max(h0, h1)), (0, 0, 0, 0))
sheet.paste(thumbs[0][1], (0, 0)); sheet.paste(thumbs[1][1], (w0 + 1, 0))
tree = []
for (i, im, tb), x in zip(thumbs, (0, w0 + 1)):
    tree.append({"n": f"character/{C}/ui/full_shot_illustration_setting_{i}", "w": im.size[0], "h": im.size[1], "x": x, "y": 0,
                 "fx": -tb[0], "fy": -tb[1], "fw": FRAME, "fh": FRAME})
buf = io.BytesIO(); sheet.save(buf, "PNG", optimize=True)
png_stored = wf_assets.png_encode(buf.getvalue())
amf = wf_dsl.encode_amf3(tree)
assert wf_dsl.parse_dsl(amf)["tree"] == tree
co = zlib.compressobj(9, zlib.DEFLATED, -15); atlas = co.compress(amf) + co.flush()
assert zlib.decompress(atlas, -15) == amf
data = {mem(f"character/{C}/ui/illustration_setting_sprite_sheet.png", "medium_upload"): png_stored,
        mem(f"character/{C}/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate", "upload"): atlas}
for m in data: assert m in _INDEX, m  # 两个成员都是 216 已有的路径,只替换内容
sheet.save(OUT / "illu" / "fixed_sheet_preview.png")
print("sheet", sheet.size, [e["n"].split("/")[-1] for e in tree])
if os.environ.get("DRY") == "1": sys.exit(0)

name = "pinball-1.4.216-1.4.217-1-vyrn-illustration-sheet-local.zip"; p = OUT / "patch" / name
with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(data): zf.writestr(m, data[m])
blob = p.read_bytes()
integ = {"name": name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(data), "files": sorted(data),
         "member_sha256": {m: hashlib.sha256(data[m]).hexdigest() for m in sorted(data)},
         "logical_paths": {mem(f"character/{C}/ui/illustration_setting_sprite_sheet.png", "medium_upload"): f"character/{C}/ui/illustration_setting_sprite_sheet.png",
                           mem(f"character/{C}/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate", "upload"): f"character/{C}/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate"},
         "applies_on": "1.4.216", "version": "1.4.217", "part": "1/1",
         "log": ["修碧切换立绘 C8004:illustration_setting_sprite_sheet 原为通用 UI 图集,缺 full_shot_illustration_setting_0/1;按凉月同结构从碧立绘裁两张缩略图重做 png+atlas"]}
p.with_name(p.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print("WROTE", name, len(blob), integ["sha256"])
