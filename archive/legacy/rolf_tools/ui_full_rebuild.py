# -*- coding: utf-8 -*-
"""把罗尔夫立绘铺满全部 ui 图:沿用官方件尺寸与 alpha 蒙版,内容换罗尔夫。
分三类构图:头像类(锚头顶)、半身类(锚脸下移)、全身类(等比填充)。"""

from wf.paths import root_path
import hashlib, io, json, re, shutil, subprocess, sys
from pathlib import Path

import numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from PIL import Image

SALT = re.search(r'SALT\s*=\s*["\']([^"\']+)["\']',
                 Path(('${WF_ROOT}\\startpoint-cn\\mod-tools\\wf_decrypt_all.py'.replace("${WF_ROOT}", str(root_path())))).read_text(encoding="utf-8", errors="ignore")).group(1)
DESK = Path(('${WF_ROOT}\\startpoint-cn\\弹国服\\WorldFlipper\\dummy\\download\\production'.replace("${WF_ROOT}", str(root_path()))))
SCRATCH = (root_path("work/legacy-rolf"))
FSOUT = SCRATCH / "fullshot_out"
OUT = SCRATCH / "ui_rebuild"
OUT.mkdir(exist_ok=True)
MM = ('${WF_ROOT}\\MuMuPlayer\\nx_main\\MuMuManager.exe'.replace("${WF_ROOT}", str(root_path())))
SHARED = Path(('${WF_ROOT}\\MuMuPlayer\\vms\\MuMuPlayer-15.0-0\\private_shared'.replace("${WF_ROOT}", str(root_path()))))
VM = "/mnt/shared/private_shared"
DEV = "/sdcard/WorldFlipper/dummy/download/production"
SRC, DST = "white_wolf_gerald", "black_wolf_knight_wt26"

# 构图类别:head=锚头顶正方 / bust=半身(脸稍上) / full=等比全身
PLAN = {
    "square_132_132":        ("head", 0.30),
    "square_round_136_136":  ("head", 0.30),
    "square_round_95_95":    ("head", 0.28),
    "thumb_party_main":      ("bust", 0.55),
    "thumb_party_unison":    ("bust", 0.55),
    "thumb_level_up":        ("bust", 0.55),
    "battle_control_board":  ("head", 0.32),
    "battle_member_status":  ("head", 0.30),
    "cutin_skill_chain":     ("bust", 0.70),
}

def sn(l):
    h = hashlib.sha1((l + SALT).encode()).hexdigest()
    return h[:2], h[2:]

def desk(l):
    d2, d38 = sn(l)
    for r in ("upload", "medium_upload", "android_upload"):
        p = DESK / r / d2 / d38
        if p.exists():
            return p.read_bytes(), r
    return None, None

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

def sh(cmd, timeout=600):
    r = subprocess.run([MM, "sh", "-v", "0", "-c", cmd], capture_output=True, text=True, timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")

# 罗尔夫两态立绘(内容已 trim)
art = {}
for lv in ("0", "1"):
    im = openpng((FSOUT / f"full_shot_1440_1920_{lv}.png").read_bytes())
    a = np.asarray(im)
    ys, xs = np.where(a[:, :, 3] > 8)
    im = im.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    # 头顶行(脸x带内最高非透明)
    a2 = np.asarray(im)
    cx = im.width // 2
    band = a2[:, max(0, cx - 160):cx + 160, 3]
    head = int(np.argmax((band > 16).any(axis=1)))
    art[lv] = (im, head)
    print(f"lv{lv} 内容 {im.size} 头顶 y={head}")

files = {}
for name, (mode, frac) in PLAN.items():
    for lv in ("0", "1"):
        lg_src = f"character/{SRC}/ui/{name}_{lv}.png"
        raw, root = desk(lg_src)
        if raw is None:
            print(f"  跳过(官方无) {name}_{lv}")
            continue
        off = openpng(raw)
        w, h = off.size
        mask = np.asarray(off)[:, :, 3]
        src_im, head = art[lv]
        if mode == "head":
            # 按目标宽高比取框(避免正方裁切后拉伸变形)
            ch = round(src_im.height * frac)
            cw = round(ch * w / h)
            left = src_im.width // 2 - cw // 2
            top = max(0, head - int(ch * 0.06))
            crop = src_im.crop((left, top, left + cw, top + ch))
        else:  # bust:从头顶往下取 frac 高,宽按目标比例
            ch = round(src_im.height * frac)
            cw = round(ch * w / h)
            left = src_im.width // 2 - cw // 2
            top = max(0, head - int(ch * 0.04))
            crop = src_im.crop((left, top, left + cw, top + ch))
        crop = crop.resize((w, h), Image.LANCZOS)
        cn = np.asarray(crop).copy()
        cn[:, :, 3] = np.minimum(cn[:, :, 3], mask)
        outim = Image.fromarray(cn)
        data = topng(outim)
        files[f"character/{DST}/ui/{name}_{lv}.png"] = (root, data)
        (OUT / f"{name}_{lv}.png").write_bytes(data)
print(f"\n生成 {len(files)} 张")

# 预览网格
cells = []
for lg, (root, data) in sorted(files.items()):
    im = openpng(data)
    bg = Image.new("RGBA", im.size, (55, 55, 65, 255))
    bg.alpha_composite(im)
    bg.thumbnail((120, 120))
    cells.append((lg.rsplit("/", 1)[1][:-4], bg.convert("RGB")))
cols = 8
rows = (len(cells) + cols - 1) // cols
grid = Image.new("RGB", (cols * 130, rows * 145), (25, 25, 30))
from PIL import ImageDraw
d = ImageDraw.Draw(grid)
for i, (nm, im) in enumerate(cells):
    x, y = (i % cols) * 130 + 5, (i // cols) * 145 + 5
    grid.paste(im, (x, y))
    d.text((x, y + 124), nm[:18], fill=(210, 210, 210))
grid.save(OUT / "preview_all_ui.png")
print("预览 ->", OUT / "preview_all_ui.png")

if "--push" in sys.argv:
    BATCH = SCRATCH / "ui_batch"
    if BATCH.exists():
        shutil.rmtree(BATCH)
    lines = ["set -e"]
    for lg, (root, data) in files.items():
        a2, a38 = sn(lg)
        (BATCH / root / a2).mkdir(parents=True, exist_ok=True)
        (BATCH / root / a2 / a38).write_bytes(data)
        lines.append(f"mkdir -p {DEV}/{root}/{a2}")
        lines.append(f"cp {VM}/ui_batch/{root}/{a2}/{a38} {DEV}/{root}/{a2}/{a38}")
    lines.append(f'echo "pushed {len(files)}"')
    (BATCH / "apply.sh").write_text("\n".join(lines), newline="\n")
    tgt = SHARED / "ui_batch"
    if tgt.exists():
        shutil.rmtree(tgt)
    shutil.copytree(BATCH, tgt)
    print(sh(f"sh {VM}/ui_batch/apply.sh").strip()[-60:])
    shutil.rmtree(tgt)
