# -*- coding: utf-8 -*-
"""全量审计+修复:wt26 的 63 件资产里,凡内容含 white_wolf_gerald 的都改写成 black_wolf_knight_wt26。
覆盖 amf3(atlas/parts/frame)、纯文本、以及 .atf/png 里的裸串。"""

from wf.paths import root_path
import hashlib, io, json, pickle, re, shutil, subprocess, sys, zlib
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl

SCRATCH = (root_path("work/legacy-rolf"))
SALT = re.search(r'SALT\s*=\s*["\']([^"\']+)["\']',
                 Path(('${WF_ROOT}\\startpoint-cn\\mod-tools\\wf_decrypt_all.py'.replace("${WF_ROOT}", str(root_path())))).read_text(encoding="utf-8", errors="ignore")).group(1)
MM = ('${WF_ROOT}\\MuMuPlayer\\nx_main\\MuMuManager.exe'.replace("${WF_ROOT}", str(root_path())))
SHARED = Path(('${WF_ROOT}\\MuMuPlayer\\vms\\MuMuPlayer-15.0-0\\private_shared'.replace("${WF_ROOT}", str(root_path()))))
VM = "/mnt/shared/private_shared"
DEV = "/sdcard/WorldFlipper/dummy/download/production"
SRC, DST = "white_wolf_gerald", "black_wolf_knight_wt26"
SRCP, DSTP = f"character/{SRC}/", f"character/{DST}/"

def sh(cmd, timeout=600):
    r = subprocess.run([MM, "sh", "-v", "0", "-c", cmd], capture_output=True, text=True, timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")

def sn(l):
    h = hashlib.sha1((l + SALT).encode()).hexdigest()
    return h[:2], h[2:]

def inflate(b):
    for raw in (b, b[4:]):
        for wb in (15, -15):
            try:
                return zlib.decompress(raw, wb), (raw is not b, wb)
            except Exception:
                pass
    return None, None

def deflate(d, mode):
    prefix_skipped, wb = mode
    co = zlib.compressobj(9, zlib.DEFLATED, wb)
    return co.compress(d) + co.flush()

assets = pickle.loads((SCRATCH / "rolf_assets.pkl").read_bytes())
print(f"审计 {len(assets)} 件")

fixed, clean, failed = [], [], []
new_assets = []
for root, lg, data in assets:
    hit_raw = SRC.encode() in data
    infl, mode = inflate(data)
    hit_infl = infl is not None and SRC.encode() in infl
    if not (hit_raw or hit_infl):
        clean.append(lg)
        new_assets.append((root, lg, data))
        continue
    newdata = None
    # ① AMF3 结构化改写(atlas/parts/frame 这类)
    if hit_infl:
        try:
            tree = wf_dsl.parse_dsl(infl)["tree"]
            def rw(v):
                if isinstance(v, str):
                    return v.replace(SRCP, DSTP)
                if isinstance(v, list):
                    return [rw(x) for x in v]
                if isinstance(v, dict):
                    return {k: rw(x) for k, x in v.items()}
                return v
            newdata = deflate(wf_dsl.encode_amf3(rw(tree)), mode)
            # 回读校验
            chk, _ = inflate(newdata)
            assert SRC.encode() not in chk
        except Exception as exc:
            failed.append((lg, f"amf3 改写失败: {exc}"))
            new_assets.append((root, lg, data))
            continue
    # ② 裸字节改写(等长替换,不动结构)——仅当 amf3 路子不适用
    if newdata is None and hit_raw:
        if len(SRC) == len(DST):
            newdata = data.replace(SRC.encode(), DST.encode())
        else:
            failed.append((lg, "裸串长度不等,需专项处理"))
            new_assets.append((root, lg, data))
            continue
    fixed.append(lg)
    new_assets.append((root, lg, newdata))

print(f"\n干净 {len(clean)} 件 | 已改写 {len(fixed)} 件 | 失败 {len(failed)} 件")
print("\n=== 改写的资产 ===")
for lg in fixed:
    print("  ", lg.replace(DSTP, ""))
if failed:
    print("\n=== 失败 ===")
    for lg, why in failed:
        print("  ", lg.replace(DSTP, ""), "|", why)

(SCRATCH / "rolf_assets_fixed.pkl").write_bytes(pickle.dumps(new_assets))

# ---- 推送修好的件 ----
if "--push" in sys.argv:
    BATCH = SCRATCH / "fix_batch"
    if BATCH.exists():
        shutil.rmtree(BATCH)
    lines = ["set -e"]
    n = 0
    for root, lg, data in new_assets:
        if lg not in fixed:
            continue
        d2, d38 = sn(lg)
        dst = BATCH / root / d2
        dst.mkdir(parents=True, exist_ok=True)
        (dst / d38).write_bytes(data)
        lines.append(f"cp {VM}/fix_batch/{root}/{d2}/{d38} {DEV}/{root}/{d2}/{d38}")
        n += 1
    lines.append(f'echo "pushed {n}"')
    (BATCH / "apply.sh").write_text("\n".join(lines), newline="\n")
    tgt = SHARED / "fix_batch"
    if tgt.exists():
        shutil.rmtree(tgt)
    shutil.copytree(BATCH, tgt)
    print(sh(f"sh {VM}/fix_batch/apply.sh").strip()[-100:])
    shutil.rmtree(tgt)
