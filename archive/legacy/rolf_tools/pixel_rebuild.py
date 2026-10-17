# -*- coding: utf-8 -*-
"""像素资产重建(修正版):
主 sheet = wt23 底 + 技能16帧 + 小人16帧(不含 special);
special sheet = wt23 special 底 + spfinal 24 帧(自己的坐标空间);
两张 atlas 前缀改写到 wt26。"""

from wf.paths import root_path
import hashlib, io, json, pickle, re, shutil, subprocess, sys, zlib
from pathlib import Path

import numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
from PIL import Image, ImageSequence

SALT = re.search(r'SALT\s*=\s*["\']([^"\']+)["\']',
                 Path(('${WF_ROOT}\\startpoint-cn\\mod-tools\\wf_decrypt_all.py'.replace("${WF_ROOT}", str(root_path())))).read_text(encoding="utf-8", errors="ignore")).group(1)
DESK = Path(('${WF_ROOT}\\startpoint-cn\\弹国服\\WorldFlipper\\dummy\\download\\production'.replace("${WF_ROOT}", str(root_path()))))
STG = Path(('${WF_ROOT}\\wt26_art_staging'.replace("${WF_ROOT}", str(root_path()))))
SCRATCH = (root_path("work/legacy-rolf"))
OUT = SCRATCH / "pixel_rebuild"
OUT.mkdir(exist_ok=True)
MM = ('${WF_ROOT}\\MuMuPlayer\\nx_main\\MuMuManager.exe'.replace("${WF_ROOT}", str(root_path())))
SHARED = Path(('${WF_ROOT}\\MuMuPlayer\\vms\\MuMuPlayer-15.0-0\\private_shared'.replace("${WF_ROOT}", str(root_path()))))
VM = "/mnt/shared/private_shared"
DEV = "/sdcard/WorldFlipper/dummy/download/production"
WT23, DST = "black_wolf_knight_wt23", "black_wolf_knight_wt26"

def sn(l):
    h = hashlib.sha1((l + SALT).encode()).hexdigest()
    return h[:2], h[2:]

def load(l):
    d2, d38 = sn(l)
    for r in ("upload", "medium_upload", "android_upload"):
        p = DESK / r / d2 / d38
        if p.exists():
            return p.read_bytes(), r
    raise FileNotFoundError(l)

def infl(b):
    for raw in (b, b[4:]):
        for wb in (15, -15):
            try:
                return zlib.decompress(raw, wb)
            except Exception:
                pass
    raise RuntimeError

def defl(d):
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    return co.compress(d) + co.flush()

def openpng(b):
    b = bytearray(b)
    if b[1:4] == b"png":
        b[1:4] = b"PNG"
    return Image.open(io.BytesIO(bytes(b))).convert("RGBA")

def topng(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    b = bytearray(buf.getvalue())
    b[1:4] = b"png"
    return bytes(b)

def paste(sheet, png_path, rect, off=None):
    img = Image.open(png_path).convert("RGBA")
    x, y, w, h = rect
    if img.size != (w, h):
        if off is None:
            off = ((img.width - w) // 2, (img.height - h) // 2)
        img = img.crop((off[0], off[1], off[0] + w, off[1] + h))
    sheet.paste(img, (x, y))

def arr(im):
    return np.asarray(im, dtype=np.float32)

def bbox(a, t=16):
    ys, xs = np.where(a[:, :, 3] > t)
    return None if len(xs) == 0 else a[ys.min():ys.max()+1, xs.min():xs.max()+1]

def ndiff(c, r):
    ca, ra = bbox(c), bbox(r)
    if ca is None or ra is None:
        return 1e9
    ci = Image.fromarray(ca.astype(np.uint8)).resize((ra.shape[1], ra.shape[0]), Image.NEAREST)
    ca = np.asarray(ci, dtype=np.float32)
    m = (ca[:, :, 3] > 16) | (ra[:, :, 3] > 16)
    return float((np.abs(ca[:, :, :3] - ra[:, :, :3]).mean(axis=2) * m).sum() / max(1, m.sum()))

# ================= 主 sheet =================
main_raw, main_root = load(f"character/{WT23}/pixelart/sprite_sheet.png")
main = openpng(main_raw)
main_atlas = wf_dsl.parse_dsl(infl(load(f"character/{WT23}/pixelart/sprite_sheet.atlas.amf3.deflate")[0]))["tree"]
orig_main = np.asarray(main.copy(), dtype=np.float32)
print(f"主 sheet {main.size} / {len(main_atlas)} 帧 [{main_root}]")

# 技能 16 帧
big_meta = json.loads((STG / "02_技能动画16帧" / "big_meta.json").read_text(encoding="utf-8"))
gif = [f.convert("RGBA") for f in ImageSequence.Iterator(Image.open(STG / "02_技能动画16帧" / "wt26_skill_anim_final.gif"))]
n_skill = 0
for i, m in enumerate(big_meta):
    cands = {t: STG / "02_技能动画16帧" / f"bigfix_{i}_{t}.png"
             for t in ("A", "B", "A2", "B2") if (STG / "02_技能动画16帧" / f"bigfix_{i}_{t}.png").exists()}
    if len(gif) == len(big_meta):
        scored = sorted((ndiff(arr(Image.open(p).convert("RGBA")), arr(gif[i])), t) for t, p in cands.items())
        best = scored[0][1]
        if len(scored) > 1 and scored[1][0] - scored[0][0] < 2:
            best = next(t for t in ("B2", "A2", "B", "A") if t in cands)
    else:
        best = next(t for t in ("B2", "A2", "B", "A") if t in cands)
    paste(main, cands[best], m["rect"], m.get("off"))
    n_skill += 1
print(f"技能帧贴入 {n_skill}")

# 小人 16 帧(IoU 反推 rect,只在小 rect 里找)
cur_files = sorted((p for p in (STG / "01_小人正背面").glob("curated_*.png") if p.stem.split("_")[1].isdigit()),
                   key=lambda p: int(p.stem.split("_")[1]))
used = set()
n_small = 0
for p in cur_files:
    canvas = Image.open(p).convert("RGBA")
    best, bs, bimg = None, None, None
    for e in main_atlas:
        w, h = e.get("w", 0), e.get("h", 0)
        if w * h == 0 or w > 40 or h > 40 or w > canvas.width or h > canvas.height:
            continue
        if (e["x"], e["y"]) in used:
            continue
        ox, oy = (canvas.width - w) // 2, (canvas.height - h) // 2
        im = canvas.crop((ox, oy, ox + w, oy + h))
        a = arr(im)
        reg = orig_main[e["y"]:e["y"]+h, e["x"]:e["x"]+w]
        ma, mb = a[:, :, 3] > 16, reg[:, :, 3] > 16
        u = np.logical_or(ma, mb).sum()
        iou = np.logical_and(ma, mb).sum() / u if u else 0
        if bs is None or iou > bs:
            best, bs, bimg = e, iou, im
    if best and bs >= 0.7:
        used.add((best["x"], best["y"]))
        main.paste(bimg, (best["x"], best["y"]))
        n_small += 1
print(f"小人帧贴入 {n_small}")

for e in main_atlas:
    e["n"] = e["n"].replace(f"character/{WT23}/", f"character/{DST}/")

# ================= special sheet =================
sp_raw, sp_root = load(f"character/{WT23}/pixelart/special_sprite_sheet.png")
sp = openpng(sp_raw)
sp_atlas = wf_dsl.parse_dsl(infl(load(f"character/{WT23}/pixelart/special_sprite_sheet.atlas.amf3.deflate")[0]))["tree"]
print(f"special sheet {sp.size} / {len(sp_atlas)} 帧 [{sp_root}]")
sp_meta = json.loads((STG / "03_special获取演出24帧" / "special_meta.json").read_text(encoding="utf-8"))
for i, m in enumerate(sp_meta):
    paste(sp, STG / "03_special获取演出24帧" / f"spfinal_{i}.png", m["rect"], m.get("off"))
print(f"special 帧贴入 {len(sp_meta)}")
for e in sp_atlas:
    e["n"] = e["n"].replace(f"character/{WT23}/", f"character/{DST}/")

# ================= 其余 pixelart 四件(frame/timeline)前缀改写 =================
files = {
    f"character/{DST}/pixelart/sprite_sheet.png": (main_root, topng(main)),
    f"character/{DST}/pixelart/sprite_sheet.atlas.amf3.deflate": ("upload", defl(wf_dsl.encode_amf3(main_atlas))),
    f"character/{DST}/pixelart/special_sprite_sheet.png": (sp_root, topng(sp)),
    f"character/{DST}/pixelart/special_sprite_sheet.atlas.amf3.deflate": ("upload", defl(wf_dsl.encode_amf3(sp_atlas))),
}
for f in ("pixelart.frame", "special.frame"):
    raw, root = load(f"character/{WT23}/pixelart/{f}.amf3.deflate")
    tree = wf_dsl.parse_dsl(infl(raw))["tree"]
    tree["name"] = tree["name"].replace(f"character/{WT23}/", f"character/{DST}/")
    files[f"character/{DST}/pixelart/{f}.amf3.deflate"] = (root, defl(wf_dsl.encode_amf3(tree)))
for f in ("pixelart.timeline", "special.timeline"):
    raw, root = load(f"character/{WT23}/pixelart/{f}.amf3.deflate")
    files[f"character/{DST}/pixelart/{f}.amf3.deflate"] = (root, defl(infl(raw)))

for lg, (root, data) in files.items():
    (OUT / lg.rsplit("/", 1)[1]).write_bytes(data)
main.resize((main.width * 2, main.height * 2), Image.NEAREST).save(OUT / "preview_main_2x.png")
sp.resize((sp.width * 2, sp.height * 2), Image.NEAREST).save(OUT / "preview_special_2x.png")
print("产出:", len(files), "件 ->", OUT)

if "--push" in sys.argv:
    BATCH = SCRATCH / "px_batch"
    if BATCH.exists():
        shutil.rmtree(BATCH)
    lines = ["set -e"]
    for lg, (root, data) in files.items():
        d2, d38 = sn(lg)
        (BATCH / root / d2).mkdir(parents=True, exist_ok=True)
        (BATCH / root / d2 / d38).write_bytes(data)
        lines.append(f"mkdir -p {DEV}/{root}/{d2}")
        lines.append(f"cp {VM}/px_batch/{root}/{d2}/{d38} {DEV}/{root}/{d2}/{d38}")
    lines.append(f'echo "pushed {len(files)}"')
    (BATCH / "apply.sh").write_text("\n".join(lines), newline="\n")
    tgt = SHARED / "px_batch"
    if tgt.exists():
        shutil.rmtree(tgt)
    shutil.copytree(BATCH, tgt)
    r = subprocess.run([MM, "sh", "-v", "0", "-c", f"sh {VM}/px_batch/apply.sh"],
                       capture_output=True, text=True, timeout=600)
    print((r.stdout or "").strip()[-80:], (r.stderr or "")[:80])
    shutil.rmtree(tgt)
