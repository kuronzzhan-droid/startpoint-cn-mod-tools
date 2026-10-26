# -*- coding: utf-8 -*-
"""回归修复(raw 行级,格式无关):设备原表(备份) + 仅罗尔夫键 → 覆写设备。
不解压行内容,只按键做行替换/追加,避免各表格式差异。"""

from wf.paths import root_path
import hashlib, io, re, shutil, subprocess, sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core

SALT = re.search(r'SALT\s*=\s*["\']([^"\']+)["\']',
                 Path(('${WF_ROOT}\\startpoint-cn\\mod-tools\\wf_decrypt_all.py'.replace("${WF_ROOT}", str(root_path())))).read_text(encoding="utf-8", errors="ignore")).group(1)
MM = ('${WF_ROOT}\\MuMuPlayer\\nx_main\\MuMuManager.exe'.replace("${WF_ROOT}", str(root_path())))
SHARED = Path(('${WF_ROOT}\\MuMuPlayer\\vms\\MuMuPlayer-15.0-0\\private_shared'.replace("${WF_ROOT}", str(root_path()))))
VM = "/mnt/shared/private_shared"
DEV = "/sdcard/WorldFlipper/dummy/download/production"
BACKUP = "/sdcard/wf_canary_backup_20260812"
SCRATCH = (root_path("work/legacy-rolf"))
CID = "179999"
ROLF_KEYS = {CID, *(f"{CID}{i}" for i in range(1, 7)), "black_wolf_knight_wt26",
             "black_wolf_knight_wt26_pf"}

TABLES = [
    "master/character/character.orderedmap",
    "master/character/character_text.orderedmap",
    "master/character/character_status.orderedmap",
    "master/character/character_speech.orderedmap",
    "master/ability/ability.orderedmap",
    "master/ability/leader_ability.orderedmap",
    "master/skill/action_skill.orderedmap",
    "master/skill/power_flip_action.orderedmap",
    "master/generated/trimmed_image.orderedmap",
    "master/character/awake.orderedmap",
    "master/skill_preview/skill_preview_character.orderedmap",
    "master/stance_detail/character_stance_detail.orderedmap",
    "master/string/custom_ability_string.orderedmap",
    "master/equipment_enhancement/equipment_flipper_skin/flipper_skin.orderedmap",
]

def sn(l):
    h = hashlib.sha1((l + SALT).encode()).hexdigest()
    return h[:2], h[2:]

def sh(cmd, timeout=600):
    r = subprocess.run([MM, "sh", "-v", "0", "-c", cmd], capture_output=True, timeout=timeout)
    return (r.stdout or b"").decode("utf-8", errors="replace")

_n = [0]
def fetch(p):
    _n[0] += 1
    tag = f"rg2_{_n[0]}"
    if "ok" not in sh(f"cp {p} {VM}/{tag} 2>/dev/null && echo ok"):
        return None
    q = SHARED / tag
    b = q.read_bytes()
    q.unlink(missing_ok=True)
    return b

def is_rolf(k):
    return k in ROLF_KEYS or "black_wolf_knight_wt26" in str(k)

fixes = {}
print(f"{'表':46s} {'原':>6s} {'现':>6s} {'多余':>5s} {'改动':>6s}  处置")
print("-" * 92)
for lg in TABLES:
    d2, d38 = sn(lg)
    cur = fetch(f"{DEV}/upload/{d2}/{d38}")
    bak = fetch(f"{BACKUP}/{d2}/{d38}")
    nm = lg.rsplit("/", 1)[1]
    if cur is None:
        print(f"{nm:46s} {'—':>6s} {'—':>6s} {'—':>5s} {'—':>6s}  设备无")
        continue
    if bak is None:
        print(f"{nm:46s} {'—':>6s} {'—':>6s} {'—':>5s} {'—':>6s}  无备份(未被我覆盖过)")
        continue
    try:
        tc = core.read_orderedmap_raw_rows_from_bytes(cur, lg)
        tb = core.read_orderedmap_raw_rows_from_bytes(bak, lg)
    except Exception as e:
        print(f"{nm:46s} 解析失败 {e}")
        continue
    cur_map = dict(zip(tc.keys, tc.rows))
    bak_map = dict(zip(tb.keys, tb.rows))
    extra = [k for k in cur_map if k not in bak_map and not is_rolf(k)]
    changed = [k for k in bak_map if k in cur_map and cur_map[k] != bak_map[k] and not is_rolf(k)]
    lost = [k for k in bak_map if k not in cur_map]
    if not extra and not changed and not lost:
        print(f"{nm:46s} {len(bak_map):6d} {len(cur_map):6d} {0:5d} {0:6d}  ✓无回归")
        continue
    # 重建:备份为底 + 罗尔夫键
    keys, rows = list(tb.keys), list(tb.rows)
    kidx = {k: i for i, k in enumerate(keys)}
    n_add = 0
    for k in tc.keys:
        if not is_rolf(k):
            continue
        if k in kidx:
            rows[kidx[k]] = cur_map[k]
        else:
            keys.append(k); rows.append(cur_map[k]); n_add += 1
    tb.keys, tb.rows = keys, rows
    fixes[lg] = core.build_orderedmap_raw_rows(tb)
    print(f"{nm:46s} {len(bak_map):6d} {len(cur_map):6d} {len(extra):5d} {len(changed):6d}  → 重建 {len(keys)} 键(罗尔夫 +{n_add})")

print("-" * 92)
if fixes and "--push" in sys.argv:
    BATCH = SCRATCH / "rg2_batch"
    if BATCH.exists():
        shutil.rmtree(BATCH)
    lines = ["set -e"]
    for lg, data in fixes.items():
        a2, a38 = sn(lg)
        (BATCH / a2).mkdir(parents=True, exist_ok=True)
        (BATCH / a2 / a38).write_bytes(data)
        lines.append(f"cp {VM}/rg2_batch/{a2}/{a38} {DEV}/upload/{a2}/{a38}")
    lines.append(f'echo "pushed {len(fixes)}"')
    (BATCH / "apply.sh").write_text("\n".join(lines), newline="\n")
    tgt = SHARED / "rg2_batch"
    if tgt.exists():
        shutil.rmtree(tgt)
    shutil.copytree(BATCH, tgt)
    print(sh(f"sh {VM}/rg2_batch/apply.sh").strip()[-60:])
    shutil.rmtree(tgt)
elif fixes:
    print(f"待修 {len(fixes)} 张(加 --push 落盘)")
else:
    print("无回归")
