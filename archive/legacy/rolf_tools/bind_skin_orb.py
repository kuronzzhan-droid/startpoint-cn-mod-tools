# -*- coding: utf-8 -*-
"""弹板皮肤绑「延续的黄金」(100012):
① 存档:持有该宝珠 + 装到罗尔夫所在队伍槽位
② flipper_skin 表:加 100012 行,阈值 0,资产路径沿用 flipper_steampunk(冰焰像素已覆盖其图集 rect,零新增资产)
"""

from wf.paths import root_path
import hashlib, io, json, re, shutil, subprocess, sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
pass  # Imports resolve from this checkout/package, not external source copies.
pass  # Imports resolve from this checkout/package, not external source copies.
import haxe_serial as hx
import wf_mod_tool as core

SALT = re.search(r'SALT\s*=\s*["\']([^"\']+)["\']',
                 Path(('${WF_ROOT}\\startpoint-cn\\mod-tools\\wf_decrypt_all.py'.replace("${WF_ROOT}", str(root_path())))).read_text(encoding="utf-8", errors="ignore")).group(1)
MM = ('${WF_ROOT}\\MuMuPlayer\\nx_main\\MuMuManager.exe'.replace("${WF_ROOT}", str(root_path())))
SHARED = Path(('${WF_ROOT}\\MuMuPlayer\\vms\\MuMuPlayer-15.0-0\\private_shared'.replace("${WF_ROOT}", str(root_path()))))
VM = "/mnt/shared/private_shared"
DEV = "/sdcard/WorldFlipper/dummy/download/production"
BACKUP = "/sdcard/wf_canary_backup_20260812"
SCRATCH = Path(__file__).parent
ORB, CID = 100012, "179999"
SKIN_PATHS = ("battle/common/layer0/flipper_skin/flipper_steampunk",
              "battle/common/layer0/flipper_skin/flipper_steampunk/f",
              "battle/common/layer0/flipper_steam")

def sn(l):
    h = hashlib.sha1((l + SALT).encode()).hexdigest()
    return h[:2], h[2:]

def sh(cmd, timeout=600):
    r = subprocess.run([MM, "sh", "-v", "0", "-c", cmd], capture_output=True, timeout=timeout)
    return (r.stdout or b"").decode("utf-8", errors="replace")

# ---------- ① 存档 ----------
sh(f"cp /sdcard/WorldFlipper/save_haxe {VM}/sv_work.txt")
txt = (SHARED / "sv_work.txt").read_text(encoding="utf-8")
(SHARED / "sv_work.txt").unlink(missing_ok=True)
save = hx.loads(txt)
assert hx.dumps(save) == txt, "往返不恒等,拒绝改写"

def walk(node, path=""):
    """找 equipments IntMap 与 party 结构。"""
    yield path, node
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{path}[{i}]")

equip_maps, party_nodes = [], []
for p, n in walk(save):
    if p.endswith(".equipments") and isinstance(n, hx.IntMap):
        equip_maps.append((p, n))
    if isinstance(n, hx.HaxeObj) and "equipmentIds" in n and "characterIds" in n:
        party_nodes.append((p, n))
    elif isinstance(n, hx.HaxeObj) and "equipmentIds" in n:
        party_nodes.append((p, n))
print(f"equipments 表 {len(equip_maps)} 处 / 含 equipmentIds 的编队节点 {len(party_nodes)} 处")

assert equip_maps, "找不到 equipments 表"
ep, emap = equip_maps[0]
print(f"  持有表 {ep}: 现有 {len(emap)} 件 → {list(emap)[:5]}")
if ORB not in emap:
    rec = hx.HaxeObj()
    rec["equipmentId"] = ORB
    rec["protection"] = False
    rec["stack"] = 0
    rec["level"] = 1
    rec["enhancementLevel"] = 0
    emap[ORB] = rec
    print(f"  ✓ 已加入持有:{ORB} 延续的黄金 (level 1, enhancementLevel 0)")
else:
    print(f"  {ORB} 已持有")

# 找罗尔夫所在编队;没有就编进队伍 1 的队长位(槽 0)
def char_id(slot):
    if isinstance(slot, hx.Enum) and slot.args and isinstance(slot.args[0], dict):
        return str(slot.args[0].get("id"))
    return None

n_slot = 0
found = False
for p, node in party_nodes:
    chars, eq = node.get("characters"), node.get("equipmentIds")
    if not isinstance(chars, list) or not isinstance(eq, list):
        continue
    for i, c in enumerate(chars):
        if char_id(c) == CID and i < len(eq):
            eq[i] = hx.Enum("haxe.ds.Option", "Some", [ORB])
            n_slot += 1
            found = True
            print(f"  ✓ {p} 槽{i}(罗尔夫) 装备 → Some({ORB})")
            break

if not found:
    # 编进 parties.1 的槽 0(队长位),沿用同结构的角色记录
    tgt = next((n for p, n in party_nodes if p.endswith(".parties.1")), None)
    assert tgt is not None, "找不到 parties.1"
    chars, eq = tgt["characters"], tgt["equipmentIds"]
    tmpl = next((c for c in chars if isinstance(c, hx.Enum) and c.args), None)
    assert tmpl is not None, "队伍 1 无可用角色记录当模板"
    rec = hx.HaxeObj()
    for k, v in tmpl.args[0].items():
        rec[k] = v
    rec["id"] = int(CID)
    old = char_id(chars[0])
    chars[0] = hx.Enum("haxe.ds.Option", "Some", [rec])
    eq[0] = hx.Enum("haxe.ds.Option", "Some", [ORB])
    tgt["party_edited"] = True
    n_slot = 1
    print(f"  ✓ 队伍1 槽0(队长位) 角色 {old} → {CID} 罗尔夫,装备 → Some({ORB})")

new_txt = hx.dumps(save)
chk = hx.loads(new_txt)
assert hx.dumps(chk) == new_txt, "改写后往返不稳定"
print(f"  存档 {len(txt)} → {len(new_txt)} 字符")

# ---------- ② flipper_skin 表 ----------
FS = "master/equipment_enhancement/equipment_flipper_skin/flipper_skin.orderedmap"
d2, d38 = sn(FS)
sh(f"cp {DEV}/upload/{d2}/{d38} {VM}/fs.bin")
fp = SCRATCH / "fs.bin"
fp.write_bytes((SHARED / "fs.bin").read_bytes())
(SHARED / "fs.bin").unlink(missing_ok=True)
ft = core.read_orderedmap_file(fp, FS)
rows = ft.text_rows()
print(f"flipper_skin 现有 {len(rows)} 行: {list(rows)}")
row_val = ",".join(("0",) + SKIN_PATHS)
ft.set_text_rows({**rows, str(ORB): row_val})
fs_bytes = core.build_orderedmap(ft)
print(f"  ✓ 加行 {ORB} = {row_val}")
print(f"  → {len(ft.keys)} 行(资产路径沿用 steampunk,零新增预载)")

if "--push" in sys.argv:
    (SHARED / "save_new.txt").write_text(new_txt, encoding="utf-8", newline="")
    (SHARED / "fs_new.bin").write_bytes(fs_bytes)
    out = sh(f"cp -n /sdcard/WorldFlipper/save_haxe {BACKUP}/save_haxe.pre_skin 2>/dev/null; "
             f"cp {VM}/save_new.txt /sdcard/WorldFlipper/save_haxe && "
             f"mkdir -p {BACKUP}/{d2} && cp -n {DEV}/upload/{d2}/{d38} {BACKUP}/{d2}/{d38} 2>/dev/null; "
             f"cp {VM}/fs_new.bin {DEV}/upload/{d2}/{d38} && echo pushed && "
             f"sha1sum /sdcard/WorldFlipper/save_haxe {DEV}/upload/{d2}/{d38}")
    print(out.strip()[-200:])
    (SHARED / "save_new.txt").unlink(missing_ok=True)
    (SHARED / "fs_new.bin").unlink(missing_ok=True)
