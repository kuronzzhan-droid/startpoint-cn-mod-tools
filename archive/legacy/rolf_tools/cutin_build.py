# -*- coding: utf-8 -*-
"""槽位3 + A1:skill_cutin PNG(1024×512 罗尔夫构图)+ 配对 ATF 重编码。"""

from wf.paths import root_path
import hashlib, io, re, shutil, subprocess, sys, time
from pathlib import Path

import numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_atf
from PIL import Image

SALT = re.search(r'SALT\s*=\s*["\']([^"\']+)["\']',
                 Path(('${WF_ROOT}\\startpoint-cn\\mod-tools\\wf_decrypt_all.py'.replace("${WF_ROOT}", str(root_path())))).read_text(encoding="utf-8", errors="ignore")).group(1)
DESK = Path(('${WF_ROOT}\\startpoint-cn\\弹国服\\WorldFlipper\\dummy\\download\\production'.replace("${WF_ROOT}", str(root_path()))))
SCRATCH = (root_path("work/legacy-rolf"))
FSOUT = SCRATCH / "fullshot_out"
OUT = SCRATCH / "cutin_out"
OUT.mkdir(exist_ok=True)
MM = ('${WF_ROOT}\\MuMuPlayer\\nx_main\\MuMuManager.exe'.replace("${WF_ROOT}", str(root_path())))
SHARED = Path(('${WF_ROOT}\\MuMuPlayer\\vms\\MuMuPlayer-15.0-0\\private_shared'.replace("${WF_ROOT}", str(root_path()))))
VM = "/mnt/shared/private_shared"
DEV = "/sdcard/WorldFlipper/dummy/download/production"
SRC, DST = "white_wolf_gerald", "black_wolf_knight_wt26"

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

def topng_store(im):
    buf = io.BytesIO()
    im.save(buf, "PNG")
    b = bytearray(buf.getvalue())
    b[1:4] = b"png"
    return bytes(b)

def sh(cmd, timeout=900):
    r = subprocess.run([MM, "sh", "-v", "0", "-c", cmd], capture_output=True, timeout=timeout)
    return (r.stdout or b"").decode("utf-8", errors="replace")

files = {}
for lv in ("0", "1"):
    off_raw, png_root = desk(f"character/{SRC}/ui/skill_cutin_{lv}.png")
    off = openpng(off_raw)
    W, H = off.size                       # 1024×512
    # 官方不透明度上限 0.621(对账表验收点):以官方 alpha 分布为准做上限钳制
    off_a = np.asarray(off)[:, :, 3].astype(np.float32) / 255.0
    a_cap = float(off_a.max())
    # 罗尔夫立绘:取上半身横构图填满 1024×512
    art = openpng((FSOUT / f"full_shot_1440_1920_{lv}.png").read_bytes())
    aa = np.asarray(art)
    ys, xs = np.where(aa[:, :, 3] > 8)
    art = art.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    a2 = np.asarray(art)
    cx = art.width // 2
    band = a2[:, max(0, cx - 160):cx + 160, 3]
    head = int(np.argmax((band > 16).any(axis=1)))
    ch = round(art.height * 0.42)          # 上半身
    cw = round(ch * W / H)
    left = max(0, cx - cw // 2)
    top = max(0, head - int(ch * 0.03))
    crop = art.crop((left, top, left + cw, top + ch)).resize((W, H), Image.LANCZOS)
    cn = np.asarray(crop).astype(np.float32).copy()
    cn[:, :, 3] = np.clip(cn[:, :, 3] * a_cap, 0, 255)   # 不透明度上限对齐官方
    cutin = Image.fromarray(cn.astype(np.uint8))
    png_bytes = topng_store(cutin)
    files[f"character/{DST}/ui/skill_cutin_{lv}.png"] = (png_root, png_bytes)
    (OUT / f"skill_cutin_{lv}.png").write_bytes(png_bytes)
    # 配对 ATF:参照官方 ATF 的 mip 数
    ref_atf_raw, atf_root = desk(f"character/{SRC}/ui/skill_cutin_{lv}.atf.deflate")
    ref_atf = wf_atf.inflate(ref_atf_raw)
    std_png = bytearray(png_bytes)
    std_png[1:4] = b"PNG"
    t0 = time.time()
    atf = wf_atf.build_cutin_atf(bytes(std_png), ref_atf)
    files[f"character/{DST}/ui/skill_cutin_{lv}.atf.deflate"] = (atf_root, wf_atf.deflate(atf))
    ref = wf_atf.parse_atf(ref_atf)
    got = wf_atf.parse_atf(atf)
    print(f"cutin_{lv}: PNG {W}×{H} alpha上限={a_cap:.3f} | ATF {got['w']}×{got['h']} mips={got['mips']}"
          f"(官方 {ref['w']}×{ref['h']} mips={ref['mips']}) {time.time()-t0:.0f}s")

# 预览
grid = Image.new("RGB", (1024, 540), (25, 25, 30))
for i, lv in enumerate(("0", "1")):
    im = openpng(files[f"character/{DST}/ui/skill_cutin_{lv}.png"][1])
    bg = Image.new("RGBA", im.size, (50, 50, 60, 255))
    bg.alpha_composite(im)
    bg.thumbnail((500, 260))
    grid.paste(bg.convert("RGB"), (10 + i * 510, 20))
grid.save(OUT / "preview_cutin.png")
print("预览 ->", OUT / "preview_cutin.png")

if "--push" in sys.argv:
    BATCH = SCRATCH / "cutin_batch"
    if BATCH.exists():
        shutil.rmtree(BATCH)
    lines = ["set -e"]
    for lg, (root, data) in files.items():
        a2, a38 = sn(lg)
        (BATCH / root / a2).mkdir(parents=True, exist_ok=True)
        (BATCH / root / a2 / a38).write_bytes(data)
        lines.append(f"mkdir -p {DEV}/{root}/{a2}")
        lines.append(f"cp {VM}/cutin_batch/{root}/{a2}/{a38} {DEV}/{root}/{a2}/{a38}")
    lines.append(f'echo "pushed {len(files)}"')
    (BATCH / "apply.sh").write_text("\n".join(lines), newline="\n")
    tgt = SHARED / "cutin_batch"
    if tgt.exists():
        shutil.rmtree(tgt)
    shutil.copytree(BATCH, tgt)
    print(sh(f"sh {VM}/cutin_batch/apply.sh").strip()[-60:])
    shutil.rmtree(tgt)
