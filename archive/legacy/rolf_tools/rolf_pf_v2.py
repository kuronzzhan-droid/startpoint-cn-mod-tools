# -*- coding: utf-8 -*-
"""罗尔夫 722 v2(按官方 PF 种类机制重建):
- speciality_type c6: 0(knight) → 3(supporter),卡面类型=辅助
- 722 DSL = 官方 ranged 三档(真光柱 effect_powerflip_attack_beam + 锁头)
           ＋ 辅助段 CreateCondition(攻击/贯通,**摘 ACFlying 浮游**)
"""

from wf.paths import root_path
import copy, hashlib, io, json, re, shutil, subprocess, sys, zlib
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_dsl
import wf_mod_tool as core

SALT = re.search(r'SALT\s*=\s*["\']([^"\']+)["\']',
                 Path(('${WF_ROOT}\\startpoint-cn\\mod-tools\\wf_decrypt_all.py'.replace("${WF_ROOT}", str(root_path())))).read_text(encoding="utf-8", errors="ignore")).group(1)
REPO = Path(('${WF_ROOT}\\startpoint-cn'.replace("${WF_ROOT}", str(root_path()))))
DESK = REPO / "弹国服/WorldFlipper/dummy/download/production"
SCRATCH = (root_path("work/legacy-rolf"))
OUT = SCRATCH / "rolf_pf_v2"
OUT.mkdir(exist_ok=True)
MM = ('${WF_ROOT}\\MuMuPlayer\\nx_main\\MuMuManager.exe'.replace("${WF_ROOT}", str(root_path())))
SHARED = Path(('${WF_ROOT}\\MuMuPlayer\\vms\\MuMuPlayer-15.0-0\\private_shared'.replace("${WF_ROOT}", str(root_path()))))
VM = "/mnt/shared/private_shared"
DEV = "/sdcard/WorldFlipper/dummy/download/production"
KEY, CID = "black_wolf_knight_wt26_pf", "179999"
S = chr(36)

def sn(l):
    h = hashlib.sha1((l + SALT).encode()).hexdigest()
    return h[:2], h[2:]

def defl(d):
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    return co.compress(d) + co.flush()

def sh(cmd, timeout=600):
    r = subprocess.run([MM, "sh", "-v", "0", "-c", cmd], capture_output=True, timeout=timeout)
    return (r.stdout or b"").decode("utf-8", errors="replace")

_n = [0]
def pull(logical):
    d2, d38 = sn(logical)
    _n[0] += 1
    tag = f"v2_{_n[0]}"
    for r in ("upload", "medium_upload", "android_upload"):
        if "ok" in sh(f"cp {DEV}/{r}/{d2}/{d38} {VM}/{tag} 2>/dev/null && echo ok"):
            p = SHARED / tag
            b = p.read_bytes()
            p.unlink(missing_ok=True)
            return b, r
    return None, None

def find(node, name, out):
    if isinstance(node, list):
        if node and node[0] == name:
            out.append(node)
        for x in node:
            if isinstance(x, (list, dict)):
                find(x, name, out)
    elif isinstance(node, dict):
        for x in node.values():
            find(x, name, out)
    return out

# ---------- ① 官方 ranged 三档 ----------
ranged = json.loads((REPO / "RG_ranged.json").read_text(encoding="utf-8"))
print("官方 ranged DSL:", {k: "OK" for k in ranged})

# 引用的 beam 特效在设备上存在性
beams = set()
for lv in ("lv1", "lv2", "lv3"):
    for n in find(ranged[lv]["tree"], "SpecifyEffectDirectly", []):
        if len(n) > 1:
            beams.add(n[1])
print(f"光柱特效 {len(beams)} 件,设备存在性:")
ok_all = True
for b in sorted(beams):
    got, root = pull(b + ".parts.amf3.deflate")
    print(f"   {'✓' if got else '✗'} [{root or '-':14s}] {b.rsplit('/',1)[1]}")
    ok_all &= bool(got)
if not ok_all:
    print("⚠ 有光柱特效缺失,继续但真机可能 8100")

# ---------- ② 辅助段(从杰拉德 PF 取,摘 ACFlying) ----------
gpp = f"battle/action/power_flip/action/override/white_wolf_gerald_pf{S}white_wolf_gerald_pf_lv1"
_lg = wf_dsl.dsl_logical(gpp)
_d2, _d38 = sn(_lg)
graw = None
for _r in ("upload", "medium_upload", "android_upload"):
    _p = DESK / _r / _d2 / _d38
    if _p.exists():
        graw = _p.read_bytes(); break
assert graw, "桌面 store 无杰拉德 PF DSL"
gtree = wf_dsl.parse_dsl(zlib.decompress(graw, -15))["tree"]
gfas = copy.deepcopy(find(gtree, "FindAllSubjects", [])[0])
inner = gfas[9][1]
kept, removed = [], []
for cmd in inner:
    cc = cmd[1]
    kind = cc[2][0][0] if cc[0] == "CreateCondition" else None
    if kind == "ACFlying":
        removed.append(kind)
        continue
    kept.append(cmd)
gfas[9][1] = kept
print(f"辅助段:保留 {len(kept)} 条条件,摘除 {removed}")

# ---------- ③ 合成三档 ----------
TUNE = {1: (150, 60), 2: (200, 90), 3: (260, 120)}
files = {}
for lv in (1, 2, 3):
    tree = copy.deepcopy(ranged[f"lv{lv}"]["tree"])
    fas = copy.deepcopy(gfas)
    atk, pierce = TUNE[lv]
    for cmd in fas[9][1]:
        cc = cmd[1]
        k = cc[2][0][0]
        if k == "ACAttackPoint":
            cc[2][0][1][0]["min"] = cc[2][0][1][0]["max"] = atk
        elif k == "ACPiercing":
            cc[2][0][1][0]["min"] = cc[2][0][1][0]["max"] = pierce
    block = tree[11][1]
    # 插在 SetPowerFilpSuppress 之后(生命周期开头),不动射击段
    idx = next((i for i, c in enumerate(block)
                if isinstance(c[1], list) and c[1][0] == "SetPowerFilpSuppress"), 0)
    block.insert(idx + 1, ["Command", fas])
    data = wf_dsl.encode_amf3(tree)
    assert json.dumps(wf_dsl.parse_dsl(data)["tree"], sort_keys=True) == json.dumps(tree, sort_keys=True)
    (OUT / f"{KEY}_lv{lv}.json").write_text(json.dumps(tree, ensure_ascii=False, indent=1), encoding="utf-8")
    files[wf_dsl.dsl_logical(f"battle/action/power_flip/action/override/{KEY}{S}{KEY}_lv{lv}")] = defl(data)
    nse = len(find(tree, "ShowEffect", []))
    nhit = len(find(tree, "CreateHitArea", []))
    print(f"lv{lv}: 光柱 ShowEffect {nse} / 命中区 {nhit} / 辅助条件 {len(fas[9][1])} / {len(data)}B")

# ---------- ④ c6 speciality_type → 3(supporter) ----------
CH = "master/character/character.orderedmap"
craw, _ = pull(CH)
cp = SCRATCH / "v2_ch.bin"
cp.write_bytes(craw)
ct = core.read_orderedmap_file(cp, CH)
rows = {k: core.read_csv_lines(v) for k, v in ct.text_rows().items()}
old = rows[CID][0][6]
rows[CID][0][6] = "3"
print(f"c6 speciality_type: {old}(knight) → 3(supporter)")
ct.set_text_rows({k: "\n".join(",".join(f'"{c}"' if ("," in c or '"' in c) else c for c in r)
                                for r in v) for k, v in rows.items()})
files[CH] = core.build_orderedmap(ct)

if "--push" in sys.argv:
    BATCH = SCRATCH / "v2_batch"
    if BATCH.exists():
        shutil.rmtree(BATCH)
    lines = ["set -e"]
    for lg, data in files.items():
        a2, a38 = sn(lg)
        (BATCH / a2).mkdir(parents=True, exist_ok=True)
        (BATCH / a2 / a38).write_bytes(data)
        lines.append(f"cp {VM}/v2_batch/{a2}/{a38} {DEV}/upload/{a2}/{a38}")
    lines.append(f'echo "pushed {len(files)}"')
    (BATCH / "apply.sh").write_text("\n".join(lines), newline="\n")
    tgt = SHARED / "v2_batch"
    if tgt.exists():
        shutil.rmtree(tgt)
    shutil.copytree(BATCH, tgt)
    print(sh(f"sh {VM}/v2_batch/apply.sh").strip()[-60:])
    shutil.rmtree(tgt)
