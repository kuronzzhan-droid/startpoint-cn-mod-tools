from fb_layer0_gate import *
import hashlib, collections, json
from PIL import Image
v = View(); allsh = {}
for qid in R0 + R1:
    a, _ = round_assets(v, qid)
    for s, (d, o) in sheets_from_anims(v, a).items():
        allsh.setdefault(s, [d, o, set()])[2].add(qid)
H = collections.defaultdict(list); stats = {}
for s, (d, o, qs) in allsh.items():
    im = png_img(v.file(s + ".png"))
    H[hashlib.sha1(im.tobytes() + str(im.size).encode()).hexdigest()].append(s)
    bb = im.getchannel("A").getbbox()
    stats[s] = dict(size=im.size, bbox=bb, owner=o, quests=sorted(qs), mode=Image.open(io.BytesIO(P.wf_assets.png_decode(v.file(s + ".png")) if hasattr(P, "wf_assets") else b"")).mode if False else None)
for h, ss in H.items():
    if len(ss) > 1: print("DUP", ss)
rows_ = []
for s, st in stats.items():
    w, h = st["size"]; bb = st["bbox"] or (0, 0, 0, 0)
    tw, th = bb[2], bb[3]
    save = area((w, h)) - area((tw, th))
    rows_.append((save, s, (w, h), bb, len(st["quests"])))
rows_.sort(reverse=True)
for r in rows_[:40]: print("%.3f %s %s bbox=%s q=%d" % (r[0] / 1e6, r[1], r[2], r[3], r[4]))
