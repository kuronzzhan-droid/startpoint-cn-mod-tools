import json
from fb_layer0_gate import *
from PIL import Image, ImageChops
sys.path.insert(0, str(P.base149.TOOLS))
from wf_battle_atlas_repack import decode_png, decode_atlas
v = View()
log = json.load(open("../art/fb_slim196/repack_log.json"))
for x in log:
    if "skip" not in x: continue
    s = x["sheet"]
    img = decode_png(v.file(s + ".png")); recs = decode_atlas(v.file(s + ".atlas.amf3.deflate"))
    W, H = img.size
    uniq = sorted({(r["x"], r["y"], r["w"], r["h"]) for r in recs})
    res = []
    for ring in (0, 1, 2):
        cov = Image.new("L", img.size, 0)
        for (rx, ry, rw, rh) in uniq:
            cov.paste(255, (max(0, rx - ring), max(0, ry - ring), min(W, rx + rw + ring), min(H, ry + rh + ring)))
        out = ImageChops.multiply(img.getchannel("A"), ImageChops.invert(cov))
        res.append(sum(1 for p in out.getdata() if p))
    # overlap of ring-1 expanded rects
    ov = 0
    E = [(rx - 1, ry - 1, rw + 2, rh + 2) for rx, ry, rw, rh in uniq]
    for i in range(len(E)):
        a = E[i]
        for b in E[i + 1:]:
            if not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]):
                ov += 1
    rots = sum(1 for r in recs if r.get("r"))
    print(f"{s.split('/')[-1]:40s} {W}x{H} outside@ring0/1/2={res} ring1_overlaps={ov} rot={rots} keys={sorted(recs[0])}")
