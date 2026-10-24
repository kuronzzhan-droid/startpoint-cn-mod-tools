# -*- coding: utf-8 -*-
"""设备实况取证:①179999 表行(code_name/元素) ②立绘三表 ③fever 残留一致性 ④像素图集覆盖率。"""

from wf.paths import root_path
import hashlib, io, json, re, subprocess, sys, zlib
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core
import wf_dsl

SALT = re.search(r'SALT\s*=\s*["\']([^"\']+)["\']',
                 Path(('${WF_ROOT}\\startpoint-cn\\mod-tools\\wf_decrypt_all.py'.replace("${WF_ROOT}", str(root_path())))).read_text(encoding="utf-8", errors="ignore")).group(1)
MM = ('${WF_ROOT}\\MuMuPlayer\\nx_main\\MuMuManager.exe'.replace("${WF_ROOT}", str(root_path())))
SHARED = Path(('${WF_ROOT}\\MuMuPlayer\\vms\\MuMuPlayer-15.0-0\\private_shared'.replace("${WF_ROOT}", str(root_path()))))
VM = "/mnt/shared/private_shared"
DEV = "/sdcard/WorldFlipper/dummy/download/production"
DESK = Path(('${WF_ROOT}\\startpoint-cn\\弹国服\\WorldFlipper\\dummy\\download\\production'.replace("${WF_ROOT}", str(root_path()))))

def sh(cmd, timeout=180):
    r = subprocess.run([MM, "sh", "-v", "0", "-c", cmd], capture_output=True, text=True, timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")

def sn(l):
    h = hashlib.sha1((l + SALT).encode()).hexdigest()
    return h[:2], h[2:]

def pull(logical, root="upload"):
    d2, d38 = sn(logical)
    tag = f"pull_{d2}{d38[:6]}"
    out = sh(f"cp {DEV}/{root}/{d2}/{d38} {VM}/{tag} 2>/dev/null && echo ok")
    if "ok" not in out:
        return None
    p = SHARED / tag
    b = p.read_bytes()
    p.unlink(missing_ok=True)
    return b

def inflate(b):
    for raw in (b, b[4:]):
        for wb in (15, -15):
            try:
                return zlib.decompress(raw, wb)
            except Exception:
                pass
    return None

print("=" * 60)
print("① character 表 179999 行(设备实况)")
b = pull("master/character/character.orderedmap")
tmp = (root_path("work/legacy-rolf") / 'dev_char.bin')
tmp.write_bytes(b)
ct = core.read_orderedmap_file(tmp, "master/character/character.orderedmap")
rows = ct.text_rows()
print("  179999 在表:", "179999" in rows)
if "179999" in rows:
    cells = core.read_csv_lines(rows["179999"])[0]
    print(f"  c0(code_name)={cells[0]!r} c3(elem)={cells[3]!r} c8(skill_key)={cells[8]!r} c17={cells[17]!r}")
    print(f"  c18(title)={cells[18]!r} c19-24(abilities)={cells[19:25]}")
    print(f"  c27={cells[27]!r} c2(rarity)={cells[2]!r}")

print("=" * 60)
print("② 立绘/图标三表 179999")
for logical, label in (("master/generated/character_image.orderedmap", "character_image"),
                       ("master/character/full_shot_image_attribute.orderedmap", "fs_attr")):
    b = pull(logical)
    if not b:
        print(f"  {label}: 设备无此文件")
        continue
    om = core.read_orderedmap_raw_rows_from_bytes(b, logical)
    if "179999" in om.keys:
        inner = core.read_orderedmap_file_from_bytes(om.rows[om.keys.index("179999")])
        print(f"  {label} 179999: {dict(inner)}")
    else:
        print(f"  {label}: 无 179999(共 {len(om.keys)} 键)")
b = pull("master/generated/trimmed_image.orderedmap")
tmp.write_bytes(b)
tt = core.read_orderedmap_file(tmp, "master/generated/trimmed_image.orderedmap")
tr = tt.text_rows()
wt26_keys = [k for k in tr if "black_wolf_knight_wt26" in k]
print(f"  trimmed wt26 键: {len(wt26_keys)}")
for k in wt26_keys[:6]:
    print(f"    {k.rsplit('/', 2)[-2]}/{k.rsplit('/', 1)[-1]} = {tr[k]}")

print("=" * 60)
print("③ fever 残留一致性(town_warastage)")
base = "battle/field_object/world_town/town_warastage/fever_gauge/town_warastage_fever_gauge"
for suf in (".parts.amf3.deflate", ".atlas.amf3.deflate", ".timeline.amf3.deflate", ".png"):
    d2, d38 = sn(base + suf)
    dev_sha = sh(f"sha1sum {DEV}/upload/{d2}/{d38} 2>/dev/null").split()
    desk = DESK / "upload" / d2 / d38
    desk_sha = hashlib.sha1(desk.read_bytes()).hexdigest() if desk.exists() else None
    state = "缺失" if not dev_sha else ("=官方" if desk_sha and dev_sha[0] == desk_sha else "≠官方(我方残留)")
    print(f"  {suf:26s} 设备:{'有' if dev_sha else '无':2s} 桌面:{'有' if desk_sha else '无':2s} → {state}")
    if suf == ".parts.amf3.deflate" and dev_sha:
        blob = pull(base + suf)
        tree = wf_dsl.parse_dsl(inflate(blob))["tree"]
        print(f"     引用件名: {[e['p'].rsplit('/', 1)[1] for e in tree['i']]}")

print("=" * 60)
print("④ 像素图集覆盖率(wt26 sheet vs wt23 官方帧)")
dev_sheet = pull("character/black_wolf_knight_wt26/pixelart/sprite_sheet.png")
print("  设备 wt26 sheet:", "有" if dev_sheet else "无", len(dev_sheet) if dev_sheet else "")
d2, d38 = sn("character/black_wolf_knight_wt23/pixelart/sprite_sheet.png")
off = (DESK / "upload" / d2 / d38).read_bytes()
from PIL import Image
def openpng(b):
    b = bytearray(b)
    if b[1:4] == b"png":
        b[1:4] = b"PNG"
    return Image.open(io.BytesIO(bytes(b))).convert("RGBA")
import numpy as np
a_new = np.asarray(openpng(dev_sheet), dtype=np.int16)
a_off = np.asarray(openpng(off), dtype=np.int16)
atlas = wf_dsl.parse_dsl(inflate((DESK / "upload" / Path(*sn("character/black_wolf_knight_wt23/pixelart/sprite_sheet.atlas.amf3.deflate"))).read_bytes()))["tree"]
same, diff = [], []
for e in atlas:
    x, y, w, h = e["x"], e["y"], e["w"], e["h"]
    r1 = a_new[y:y+h, x:x+w]
    r2 = a_off[y:y+h, x:x+w]
    (same if np.array_equal(r1, r2) else diff).append(e["n"].rsplit("/", 1)[1])
print(f"  图集 {len(atlas)} 帧: 已换 {len(diff)} 帧, 仍是 wt23 原样 {len(same)} 帧")
print(f"  仍原样(前30): {same[:30]}")
