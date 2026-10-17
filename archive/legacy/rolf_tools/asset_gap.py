# -*- coding: utf-8 -*-
"""穷举角色资产命名空间:从 swf 抽 character/<code>/... 路径模板,对 gerald 实测存在性,
再比对设备上 wt26 的缺口。"""

from wf.paths import root_path
import hashlib, io, re, subprocess, sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
SALT = re.search(r'SALT\s*=\s*["\']([^"\']+)["\']',
                 Path(('${WF_ROOT}\\startpoint-cn\\mod-tools\\wf_decrypt_all.py'.replace("${WF_ROOT}", str(root_path())))).read_text(encoding="utf-8", errors="ignore")).group(1)
DESK = Path(('${WF_ROOT}\\startpoint-cn\\弹国服\\WorldFlipper\\dummy\\download\\production'.replace("${WF_ROOT}", str(root_path()))))
SWF = Path(('${WF_ROOT}\\MuMuPlayer\\vms\\MuMuPlayer-15.0-0\\private_shared\\wf_run.swf'.replace("${WF_ROOT}", str(root_path()))))
MM = ('${WF_ROOT}\\MuMuPlayer\\nx_main\\MuMuManager.exe'.replace("${WF_ROOT}", str(root_path())))
DEV = "/sdcard/WorldFlipper/dummy/download/production"
SRC, DST = "white_wolf_gerald", "black_wolf_knight_wt26"

def sn(l):
    h = hashlib.sha1((l + SALT).encode()).hexdigest()
    return h[:2], h[2:]

def desk_root(l):
    d2, d38 = sn(l)
    for r in ("upload", "medium_upload", "android_upload"):
        if (DESK / r / d2 / d38).exists():
            return r
    return None

# ---- ① 从 swf 抽资产名片段(ui/ 下与 pixelart/ 下的常量串) ----
b = SWF.read_bytes()
frag = set()
for m in re.finditer(rb"[a-z0-9_]{3,60}", b):
    s = m.group(0).decode()
    if any(k in s for k in ("full_shot", "square", "thumbnail", "illustration", "skill_cutin",
                            "pixelart", "special", "sprite_sheet", "chibi", "battle_control",
                            "voice", "cutin", "portrait", "icon")):
        frag.add(s)
print(f"swf 资产名候选片段: {len(frag)}")

# ---- ② 组合探测 gerald 实际存在的资产 ----
DIRS = ["ui", "pixelart", "battle", "voice", ""]
EXTS = [".png", ".atf.deflate", ".amf3.deflate", ".mp3", ""]
found = {}
tried = set()
def probe(rel):
    lg = f"character/{SRC}/{rel}"
    if lg in tried:
        return
    tried.add(lg)
    r = desk_root(lg)
    if r:
        found[rel] = r

# 片段 × 目录 × 后缀 × 序号
for f in sorted(frag):
    for d in DIRS:
        base = f"{d}/{f}" if d else f
        for ext in EXTS:
            probe(base + ext)
            for i in (0, 1, 2, 3):
                probe(f"{base}_{i}{ext}")
print(f"探测 {len(tried)} 条,gerald 命中 {len(found)}")

# ---- ③ 与已推送清单比对 ----
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_assets
pushed = set()
for lg in wf_assets.all_asset_logicals(DESK / "upload", SRC):
    pushed.add(lg.replace(f"character/{SRC}/", "", 1))
print(f"all_asset_logicals 给出 {len(pushed)} 条")

missing = sorted(set(found) - pushed)
print(f"\n=== all_asset_logicals 漏掉的 gerald 资产({len(missing)} 条) ===")
for rel in missing:
    print(f"  [{found[rel]:14s}] {rel}")

# ---- ④ 设备上 wt26 缺口实测 ----
cmds = []
allrel = sorted(set(found) | pushed)
for rel in allrel:
    lg = f"character/{DST}/{rel}"
    d2, d38 = sn(lg)
    root = found.get(rel) or desk_root(f"character/{SRC}/{rel}") or "upload"
    cmds.append(f"[ -f {DEV}/{root}/{d2}/{d38} ] && echo 'OK {rel}' || echo 'MISS {rel}|{root}'")
script = "\n".join(cmds)
SHARED = Path(('${WF_ROOT}\\MuMuPlayer\\vms\\MuMuPlayer-15.0-0\\private_shared'.replace("${WF_ROOT}", str(root_path()))))
(SHARED / "gap_check.sh").write_text(script, newline="\n")
r = subprocess.run([MM, "sh", "-v", "0", "-c", "sh /mnt/shared/private_shared/gap_check.sh"],
                   capture_output=True, text=True, timeout=600)
(SHARED / "gap_check.sh").unlink(missing_ok=True)
dev_missing = [l[5:] for l in r.stdout.splitlines() if l.startswith("MISS")]
print(f"\n=== 设备上 wt26 缺失({len(dev_missing)}/{len(allrel)}) ===")
for m in dev_missing:
    print("  ", m)
(root_path("work/legacy-rolf") / 'wt26_gap.txt').write_text(
    "\n".join(dev_missing), encoding="utf-8")
