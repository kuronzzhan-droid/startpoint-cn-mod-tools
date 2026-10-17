# -*- coding: utf-8 -*-
"""C 节 8 道验收门(能自动的全自动,须真机的标注人工)。设备实况为准。"""

from wf.paths import root_path
import hashlib, io, json, re, subprocess, sys, zlib
from pathlib import Path

import numpy as np
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_atf, wf_dsl
import wf_mod_tool as core
from PIL import Image

SALT = re.search(r'SALT\s*=\s*["\']([^"\']+)["\']',
                 Path(('${WF_ROOT}\\startpoint-cn\\mod-tools\\wf_decrypt_all.py'.replace("${WF_ROOT}", str(root_path())))).read_text(encoding="utf-8", errors="ignore")).group(1)
MM = ('${WF_ROOT}\\MuMuPlayer\\nx_main\\MuMuManager.exe'.replace("${WF_ROOT}", str(root_path())))
SHARED = Path(('${WF_ROOT}\\MuMuPlayer\\vms\\MuMuPlayer-15.0-0\\private_shared'.replace("${WF_ROOT}", str(root_path()))))
VM = "/mnt/shared/private_shared"
DEV = "/sdcard/WorldFlipper/dummy/download/production"
SCRATCH = (root_path("work/legacy-rolf"))
CODE, CID = "black_wolf_knight_wt26", "179999"
S = chr(36)
results = []

def sn(l):
    h = hashlib.sha1((l + SALT).encode()).hexdigest()
    return h[:2], h[2:]

def sh(cmd, timeout=600):
    r = subprocess.run([MM, "sh", "-v", "0", "-c", cmd], capture_output=True, timeout=timeout)
    return (r.stdout or b"").decode("utf-8", errors="replace")

_pull_n = [0]
def pull(logical, roots=("upload", "medium_upload", "android_upload")):
    d2, d38 = sn(logical)
    _pull_n[0] += 1
    tag = f"g_{_pull_n[0]}"
    for r in roots:
        out = sh(f"cp {DEV}/{r}/{d2}/{d38} {VM}/{tag} 2>/dev/null && echo ok")
        if "ok" in out:
            p = SHARED / tag
            b = p.read_bytes()
            p.unlink(missing_ok=True)
            return b, r
    return None, None

def openpng(b):
    b = bytearray(b)
    if b[1:4] == b"png":
        b[1:4] = b"PNG"
    return Image.open(io.BytesIO(bytes(b))).convert("RGBA")

def infl(b):
    for raw in (b, b[4:]):
        for wb in (15, -15):
            try:
                return zlib.decompress(raw, wb)
            except Exception:
                pass
    return None

def gate(n, name, ok, detail):
    results.append((n, name, ok, detail))
    mark = "✅通过" if ok is True else ("⚠人工" if ok is None else "❌未过")
    print(f"\n门{n} {name}: {mark}")
    for line in detail.splitlines():
        print("   " + line)

# ---------------- 门1 成对完整性 ----------------
r = subprocess.run([sys.executable, str(SCRATCH / "slot_audit.py")], capture_output=True, timeout=900)
txt = (r.stdout or b"").decode("utf-8", errors="replace")
last = [l for l in txt.splitlines() if "已换自产" in l and "/" in l]
shell_n = int(re.search(r"仍是壳 (\d+)", last[-1]).group(1)) if last else -1
gate(1, "medium 13 槽成对完整性", shell_n == 0, last[-1] if last else "审计失败")

# ---------------- 门2 cutin PNG↔ATF + 立绘三表 ----------------
d2 = []
ok2 = True
for lv in ("0", "1"):
    png, _ = pull(f"character/{CODE}/ui/skill_cutin_{lv}.png")
    atf_raw, _ = pull(f"character/{CODE}/ui/skill_cutin_{lv}.atf.deflate")
    if not png or not atf_raw:
        ok2 = False
        d2.append(f"cutin_{lv}: 文件缺失")
        continue
    pw, ph = openpng(png).size
    a = wf_atf.parse_atf(wf_atf.inflate(atf_raw))
    same = (a["w"], a["h"]) == (pw, ph)
    ok2 &= same
    d2.append(f"cutin_{lv}: PNG {pw}×{ph} ↔ ATF {a['w']}×{a['h']} mips={a['mips']} → {'同步' if same else '不同步'}")
# 立绘三表互检
tabs = {}
for lg, key in (("master/generated/character_image.orderedmap", "img"),
                ("master/character/full_shot_image_attribute.orderedmap", "attr")):
    b, _ = pull(lg)
    om = core.read_orderedmap_raw_rows_from_bytes(b, lg)
    tabs[key] = core.read_orderedmap_file_from_bytes(om.rows[om.keys.index(CID)])
b, _ = pull("master/generated/trimmed_image.orderedmap")
tp = SCRATCH / "g_trim.bin"
tp.write_bytes(b)
trim = core.read_orderedmap_file(tp, "master/generated/trimmed_image.orderedmap").text_rows()
for lv in ("0", "1"):
    png, _ = pull(f"character/{CODE}/ui/full_shot_1440_1920_{lv}.png")
    w, h = openpng(png).size
    ix, iy, iw, ih = [int(x) for x in tabs["img"][lv].split(",")]
    at = tabs["attr"][lv].split(",")
    tr = trim.get(f"character/{CODE}/ui/full_shot_1440_1920_{lv}", "")
    tx, ty = (int(x) for x in tr.split(",")[:2]) if tr else (-1, -1)
    c1 = (iw, ih) == (w, h)          # 内容框=实际尺寸
    c2 = (tx, ty) == (ix, iy)        # trimmed 与 character_image 的 x,y 相等
    ok2 &= c1 and c2
    d2.append(f"lv{lv}: PNG {w}×{h} / character_image {ix},{iy},{iw},{ih} → 尺寸{'✓' if c1 else '✗'}"
              f" | trimmed {tx},{ty} vs {ix},{iy} → {'✓' if c2 else '✗'} | attr pivot/face={','.join(at)}")
gate(2, "cutin PNG↔ATF + 立绘三表互检", ok2, "\n".join(d2))

# ---------------- 门3 图集预算 ----------------
d3 = []
ok3 = True
for lg, budget, label in ((f"character/{CODE}/pixelart/sprite_sheet.png", 0.18, "pixelart 主"),
                          (f"character/{CODE}/pixelart/special_sprite_sheet.png", 0.18, "pixelart special")):
    b, _ = pull(lg)
    if not b:
        ok3 = False
        d3.append(f"{label}: 缺失")
        continue
    w, h = openpng(b).size
    mp = w * h / 1e6
    good = mp <= budget
    ok3 &= good
    d3.append(f"{label}: {w}×{h} = {mp:.3f}Mpx / 预算 {budget} → {'✓' if good else '✗超预算'}")
gate(3, "图集预算(pixelart 0.18Mpx)", ok3, "\n".join(d3) + "\n多人房三队合并测试=真机项(未跑)")

# ---------------- 门4 DSL 校验 ----------------
d4 = []
ok4 = True
KNOWN_MISSING = []
for lv in (1, 2, 3):
    pp = f"battle/action/power_flip/action/override/{CODE}_pf{S}{CODE}_pf_lv{lv}"
    b, _ = pull(wf_dsl.dsl_logical(pp))
    if not b:
        ok4 = False
        d4.append(f"722 lv{lv}: DSL 缺失")
        continue
    tree = wf_dsl.parse_dsl(zlib.decompress(b, -15))["tree"]
    # 收集引用的资产路径
    refs = []
    def scan(n):
        if isinstance(n, list):
            if n and n[0] == "SpecifyEffectDirectly" and len(n) > 1:
                refs.append(n[1])
            for x in n:
                if isinstance(x, (list, dict)):
                    scan(x)
        elif isinstance(n, dict):
            for x in n.values():
                scan(x)
    scan(tree)
    # 非法构造名扫描(Command Wait 等)
    bad = []
    def scan_bad(n):
        if isinstance(n, list):
            if len(n) == 2 and n[0] == "Command" and isinstance(n[1], list) and n[1] and n[1][0] == "Wait":
                bad.append("Command Wait(非法)")
            for x in n:
                if isinstance(x, (list, dict)):
                    scan_bad(x)
        elif isinstance(n, dict):
            for x in n.values():
                scan_bad(x)
    scan_bad(tree)
    # 生命周期三件
    flat = json.dumps(tree, ensure_ascii=False)
    life = all(k in flat for k in ("SetPowerFilpSuppress", "NotifyPowerflipEnd"))
    # 引用资产存在性(按 .parts 探)
    missing = []
    for rp in refs:
        got, _ = pull(rp + ".parts.amf3.deflate")
        if not got:
            missing.append(rp)
    okl = not bad and life and not missing
    ok4 &= okl
    KNOWN_MISSING += missing
    d4.append(f"722 lv{lv}: 引用 {len(refs)} 件, 缺 {len(missing)} | 生命周期{'✓' if life else '✗'} | 非法构造 {bad or '无'}")
    for m in missing:
        d4.append(f"    缺失引用: {m}")
gate(4, "DSL 结构与引用完整性", ok4, "\n".join(d4) + "\n真机 describe 双验=真机项")

# ---------------- 门5 语音 ----------------
b, _ = pull("master/character/character_speech.orderedmap")
d5 = []
ok5 = None
if b:
    sp = SCRATCH / "g_speech.bin"
    sp.write_bytes(b)
    st = core.read_orderedmap_file(sp, "master/character/character_speech.orderedmap").text_rows()
    has = CID in st
    d5.append(f"speech 表含 {CID}: {has}")
    if has:
        rows = core.read_csv_lines(st[CID])
        vis = sum(1 for r in rows if len(r) > 2 and r[2] not in ("", "0"))
        d5.append(f"  记录 {len(rows)} 条, constraint 可见数 {vis}(0 会崩 2265)")
        ok5 = vis > 0
        d5.append(f"  ⚠ 语音文件仍是杰拉德日配(罗尔夫 21 条台词已定稿未配音)")
else:
    d5.append("speech 表拉取失败")
gate(5, "语音/speech 表", ok5, "\n".join(d5))

# ---------------- 门6 词条/队长表 ----------------
d6 = []
ok6 = True
b, _ = pull("master/ability/ability.orderedmap")
ap = SCRATCH / "g_ab.bin"
ap.write_bytes(b)
ab = core.read_orderedmap_file(ap, "master/ability/ability.orderedmap").text_rows()
PULLER_KINDS = {"8", "9", "87", "187", "188", "200", "205"}
for i in range(1, 7):
    k = f"{CID}{i}"
    if k not in ab:
        ok6 = False
        d6.append(f"词条键 {k}: 缺失")
        continue
    rows = core.read_csv_lines(ab[k])
    ncol = len(rows[0])
    bad_puller = []
    for r in rows:
        for ci in range(len(r) - 1):
            if r[ci] in PULLER_KINDS and ci + 1 < len(r) and r[ci + 1] == "":
                bad_puller.append((ci, r[ci]))
    d6.append(f"词条 {k}: {len(rows)} 条记录 / {ncol} 列 / 前置puller空 {len(bad_puller)}")
    ok6 &= ncol == 126 and len(rows) <= 9
b, _ = pull("master/ability/leader_ability.orderedmap")
lp = SCRATCH / "g_la.bin"
lp.write_bytes(b)
la = core.read_orderedmap_file(lp, "master/ability/leader_ability.orderedmap").text_rows()
lrows = core.read_csv_lines(la[CID])
kinds = [r[45] for r in lrows if len(r) > 45]
# 官方先例:全表统计每个 kind 的出现次数(排除自制 ID 段 1x9999)
prec = {}
for k2, v in la.items():
    if k2.startswith("1") and k2.endswith("9999"):
        continue
    for r in core.read_csv_lines(v):
        if len(r) > 45 and r[45]:
            prec[r[45]] = prec.get(r[45], 0) + 1
no_prec = [k3 for k3 in kinds if prec.get(k3, 0) == 0]
has713 = "713" in kinds
ok6 &= not no_prec and not has713 and len(lrows[0]) == 124
d6.append(f"队长表 {CID}: {len(lrows)} 行 / {len(lrows[0])} 列 / kinds={kinds}")
d6.append(f"  无官方先例的 kind: {no_prec or '无(全部有先例)'} | 713 禁入: {'违规' if has713 else '✓'}")
d6.append(f"  ⚠ 套件内容仍是杰拉德占位(设计稿 §4.1-4.3 未落表)")
gate(6, "词条/队长表结构与先例", ok6, "\n".join(d6))

# ---------------- 门7/8 ----------------
gate(7, "金丝雀真机全流程", None,
     "抽卡→详情→编队→出战→技能/PF→获取演出→玛纳板\n"
     "已过:详情页/编队/角色一览/进战斗\n待验:PF 发动(刚修 subject)/技能演出/获取演出/玛纳板")
b, _ = pull("master/character/character.orderedmap")
cp = SCRATCH / "g_ch.bin"
cp.write_bytes(b)
ct = core.read_orderedmap_file(cp, "master/character/character.orderedmap").text_rows()
gate(8, "键集核对", CID in ct,
     f"character 表键数 {len(ct)},含 {CID}: {CID in ct}\n"
     f"⚠ 本次为设备直推(不走 wf_publish_guard),发布前须手动键集核对")

print("\n" + "=" * 60)
p = sum(1 for _, _, ok, _ in results if ok is True)
f = sum(1 for _, _, ok, _ in results if ok is False)
m = sum(1 for _, _, ok, _ in results if ok is None)
print(f"验收门总计: 通过 {p} / 未过 {f} / 人工待验 {m}")
for n, name, ok, _ in results:
    print(f"  门{n} {name}: {'✅' if ok is True else ('⚠' if ok is None else '❌')}")
