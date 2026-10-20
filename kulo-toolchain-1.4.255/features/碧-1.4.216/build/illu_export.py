# -*- coding: utf-8 -*-
"""改动汇报页:扫链上 1.4.131–1.4.218 改过/新增 full_shot 立绘的角色,并导出指定角色立绘(长边 640,WebP q75 透明)。只读。"""
import io, os, json, zipfile
os.environ["WF_EXTRA_DIRS"] = r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(218)
from base149 import *
from base149 import _INDEX, SCR
import sys; sys.path.insert(0, str(TOOLS))
import wf_assets
from PIL import Image

OUT = Path(r"D:/WF/out/碧-1.4.216/illu_out"); OUT.mkdir(exist_ok=True)
CH = {k: row(v) for k, v in load("master/character/character.orderedmap").items()}
TX = {k: row(v) for k, v in load("master/character/character_text.orderedmap").items()}


def srcs(lp):
    h = member(lp).split("upload/")[1]; out = {}
    for k in ("medium_upload", "upload"):
        n = f"production/{k}/{h}"
        if n in _INDEX: out[k] = _INDEX[n].name
    return out


def ver(zname):  # pinball-1.4.A-1.4.B-...
    return "1.4." + zname.split("-1.4.")[2].split("-")[0]


scan = {}
for cid, r in CH.items():
    code = r[0]
    for i in ("0", "1"):
        s = srcs(f"character/{code}/ui/full_shot_1440_1920_{i}.png")
        if s:
            z = s.get("medium_upload") or s.get("upload")
            scan.setdefault(cid, {})[i] = ver(z)
rows_ = sorted(((min(v.values()), cid, TX.get(cid, [""] * 4)[3] + " " + TX.get(cid, [""])[0], v) for cid, v in scan.items()), key=lambda x: (tuple(int(p) for p in x[0].split(".")), x[1]))
json.dump(rows_, open(OUT / "chain_fullshot_scan.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("chain full_shot changes:", len(rows_))
for r in rows_: print(" ", r)


def get(code, i):
    h = member(f"character/{code}/ui/full_shot_1440_1920_{i}.png").split("upload/")[1]
    for k in ("medium_upload", "upload"):
        n = f"production/{k}/{h}"
        if n in _INDEX:
            with zipfile.ZipFile(_INDEX[n]) as z: return z.read(n), _INDEX[n].name
        p = SCR / "store131/production" / k / h
        if p.exists() and p.stat().st_size > 16: return p.read_bytes(), "store131(官方原版)"
    return None, None


WANT = os.environ.get("WANT", "149999,129992,149986,129999,169978").split(",")
caps = {}
for cid in WANT:
    code = CH[cid][0]
    for i in ("0", "1"):
        b, src = get(code, i)
        if b is None: continue
        im = Image.open(io.BytesIO(wf_assets.png_decode_stored(b))).convert("RGBA")
        bb = im.getbbox(); im = im.crop(bb) if bb else im
        im.thumbnail((640, 640), Image.LANCZOS)
        fn = f"{cid}_{i}.webp"
        im.save(OUT / fn, "WEBP", quality=75, method=6)
        caps[fn] = dict(id=cid, name=TX[cid][0], title=TX[cid][3], slot="觉醒前" if i == "0" else "觉醒后",
                        source=src, size=list(im.size), bytes=(OUT / fn).stat().st_size)
json.dump(caps, open(OUT / "captions.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for k, v in caps.items(): print(k, v)
