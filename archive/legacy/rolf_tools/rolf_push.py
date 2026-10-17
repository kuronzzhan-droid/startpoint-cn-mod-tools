# -*- coding: utf-8 -*-
"""罗尔夫 179999 阶段2:表+资产推送设备 & player_character 花名册授予。"""

from wf.paths import root_path
import hashlib, io, json, pickle, re, shutil, subprocess, sys, zlib
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core

SCRATCH = (root_path("work/legacy-rolf"))
TEMP = SCRATCH / "rolf_temp_store" / "store"
MM = ('${WF_ROOT}\\MuMuPlayer\\nx_main\\MuMuManager.exe'.replace("${WF_ROOT}", str(root_path())))
SHARED = Path(('${WF_ROOT}\\MuMuPlayer\\vms\\MuMuPlayer-15.0-0\\private_shared'.replace("${WF_ROOT}", str(root_path()))))
VM = "/mnt/shared/private_shared"
DEV = "/sdcard/WorldFlipper/dummy/download/production"
BACKUP = "/sdcard/wf_canary_backup_20260812"
SALT = re.search(r'SALT\s*=\s*["\']([^"\']+)["\']',
                 Path(('${WF_ROOT}\\startpoint-cn\\mod-tools\\wf_decrypt_all.py'.replace("${WF_ROOT}", str(root_path())))).read_text(encoding="utf-8", errors="ignore")).group(1)

def sh(cmd, timeout=600):
    r = subprocess.run([MM, "sh", "-v", "0", "-c", cmd], capture_output=True, text=True, timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")

def sn(logical):
    h = hashlib.sha1((logical + SALT).encode()).hexdigest()
    return h[:2], h[2:]

# ---- 批量目录组装:tables(upload) + assets(三根) ----
BATCH = SCRATCH / "rolf_batch"
if BATCH.exists():
    shutil.rmtree(BATCH)
for root in ("upload", "medium_upload", "android_upload"):
    (BATCH / root).mkdir(parents=True)

apply_lines = ["set -e", f"mkdir -p {BACKUP}"]
n_tab = 0
for p in TEMP.rglob("*"):
    if not p.is_file() or ".bak" in p.name:
        continue
    rel = p.relative_to(TEMP)
    dst = BATCH / "upload" / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, dst)
    dev = f"{DEV}/upload/{rel.as_posix()}"
    apply_lines.append(f"mkdir -p {BACKUP}/{rel.parent.as_posix()} {DEV}/upload/{rel.parent.as_posix()}")
    apply_lines.append(f"cp -n {dev} {BACKUP}/{rel.as_posix()} 2>/dev/null || true")
    apply_lines.append(f"cp {VM}/rolf_batch/upload/{rel.as_posix()} {dev}")
    n_tab += 1

assets = pickle.loads((SCRATCH / "rolf_assets.pkl").read_bytes())
for root, lg, data in assets:
    d2, d38 = sn(lg)
    dst = BATCH / root / d2 / d38
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)
    apply_lines.append(f"mkdir -p {DEV}/{root}/{d2}")
    apply_lines.append(f"cp {VM}/rolf_batch/{root}/{d2}/{d38} {DEV}/{root}/{d2}/{d38}")
(BATCH / "apply.sh").write_text("\n".join(apply_lines) + "\necho APPLIED\n", newline="\n")
print(f"batch: tables {n_tab}, assets {len(assets)}")

# ---- 花名册:拉设备 player_character,加 179999 ----
PLAYER_LOGICAL = "master/player/player_character.orderedmap"
d2, d38 = sn(PLAYER_LOGICAL)
out = sh(f"cp {DEV}/upload/{d2}/{d38} {VM}/rolf_player.bin && echo ok")
assert "ok" in out, out
blob = (SHARED / "rolf_player.bin").read_bytes()
outer = core.read_orderedmap_raw_rows_from_bytes(blob, PLAYER_LOGICAL)
pi = outer.keys.index("1000")
inner = core.read_orderedmap_raw_rows_from_bytes(outer.rows[pi], PLAYER_LOGICAL + "#1000")
print("花名册现有角色:", inner.keys)
if "179999" not in inner.keys:
    inner_new = core.OrderedMap(inner.logical_path, [*inner.keys, "179999"],
                                [*inner.rows, zlib.compress(b"1")], Path("[mem]"))
    outer_rows = list(outer.rows)
    outer_rows[pi] = core.build_orderedmap_raw_rows(inner_new)
    new_blob = core.build_orderedmap_raw_rows(
        core.OrderedMap(outer.logical_path, list(outer.keys), outer_rows, Path("[mem]")))
    # 回读校验
    chk_o = core.read_orderedmap_raw_rows_from_bytes(new_blob, PLAYER_LOGICAL)
    chk_i = core.read_orderedmap_raw_rows_from_bytes(chk_o.rows[chk_o.keys.index("1000")], "chk")
    assert "179999" in chk_i.keys and zlib.decompress(chk_i.rows[chk_i.keys.index("179999")]) == b"1"
    (BATCH / "upload_player.bin").write_bytes(new_blob)
    print("179999 已加入花名册(等级1),回读校验过")
else:
    print("179999 已在花名册")

# ---- 推送 ----
if "--push" in sys.argv:
    dst = SHARED / "rolf_batch"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(BATCH, dst)
    out = sh(f"sh {VM}/rolf_batch/apply.sh", timeout=900)
    print("apply:", out.strip()[-120:])
    if (BATCH / "upload_player.bin").exists():
        out = sh(f"mkdir -p {BACKUP}/{d2} && cp -n {DEV}/upload/{d2}/{d38} {BACKUP}/{d2}/{d38} 2>/dev/null; "
                 f"cp {VM}/rolf_batch/upload_player.bin {DEV}/upload/{d2}/{d38} && sha1sum {DEV}/upload/{d2}/{d38}")
        want = hashlib.sha1((BATCH / "upload_player.bin").read_bytes()).hexdigest()
        print("player roster push:", "OK" if out.split()[0] == want else "FAIL " + out[:80])
    # 抽验
    import random
    random.seed(7)
    for root, lg, data in random.sample(assets, 3):
        a2, a38 = sn(lg)
        got = sh(f"sha1sum {DEV}/{root}/{a2}/{a38}").split()[0]
        print("spot", lg.rsplit("/", 1)[1][:30], got == hashlib.sha1(data).hexdigest())
    shutil.rmtree(dst)
    (SHARED / "rolf_player.bin").unlink(missing_ok=True)
