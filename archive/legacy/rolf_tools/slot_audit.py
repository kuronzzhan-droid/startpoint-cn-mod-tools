# -*- coding: utf-8 -*-
"""D 节 13 个 medium 槽位逐件对账:设备上 wt26 的每件 vs 杰拉德同名件内容哈希。
相同=仍是壳,不同=已换自产。附 A1 的 ATF 两件。"""

from wf.paths import root_path
import hashlib, io, re, subprocess, sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
SALT = re.search(r'SALT\s*=\s*["\']([^"\']+)["\']',
                 Path(('${WF_ROOT}\\startpoint-cn\\mod-tools\\wf_decrypt_all.py'.replace("${WF_ROOT}", str(root_path())))).read_text(encoding="utf-8", errors="ignore")).group(1)
MM = ('${WF_ROOT}\\MuMuPlayer\\nx_main\\MuMuManager.exe'.replace("${WF_ROOT}", str(root_path())))
DEV = "/sdcard/WorldFlipper/dummy/download/production"
SRC, DST = "white_wolf_gerald", "black_wolf_knight_wt26"

SLOTS = [
    (1,  "主立绘",        "ui/full_shot_1440_1920_{lv}.png",            "medium_upload"),
    (2,  "立绘定位图集",   "ui/illustration_setting_sprite_sheet.png",   "medium_upload"),
    (3,  "技能cutin",     "ui/skill_cutin_{lv}.png",                    "medium_upload"),
    (4,  "方形头像",       "ui/square_{lv}.png",                        "medium_upload"),
    (5,  "方形132",       "ui/square_132_132_{lv}.png",                 "medium_upload"),
    (6,  "圆角136",       "ui/square_round_136_136_{lv}.png",           "medium_upload"),
    (7,  "圆角95",        "ui/square_round_95_95_{lv}.png",             "medium_upload"),
    (8,  "连锁cutin",     "ui/cutin_skill_chain_{lv}.png",              "medium_upload"),
    (9,  "战斗成员状态",   "ui/battle_member_status_{lv}.png",           "medium_upload"),
    (10, "战斗控制板",     "ui/battle_control_board_{lv}.png",           "medium_upload"),
    (11, "升级缩略",       "ui/thumb_level_up_{lv}.png",                "medium_upload"),
    (12, "编队主位缩略",   "ui/thumb_party_main_{lv}.png",              "medium_upload"),
    (13, "编队合击缩略",   "ui/thumb_party_unison_{lv}.png",            "medium_upload"),
]
EXTRA = [
    ("A1", "skill_cutin ATF", "ui/skill_cutin_{lv}.atf.deflate", "android_upload"),
    ("A2⑥", "立绘定位atlas", "ui/illustration_setting_sprite_sheet.atlas.amf3.deflate", "upload"),
]

def sn(l):
    h = hashlib.sha1((l + SALT).encode()).hexdigest()
    return h[:2], h[2:]

cmds = []
labels = []
for num, name, tmpl, root in SLOTS + EXTRA:
    levels = ["0", "1"] if "{lv}" in tmpl else [""]
    for lv in levels:
        rel = tmpl.format(lv=lv)
        for code, tag in ((DST, "new"), (SRC, "old")):
            a, b = sn(f"character/{code}/{rel}")
            cmds.append(f"echo -n '{num}|{lv}|{tag} '; sha1sum {DEV}/{root}/{a}/{b} 2>/dev/null | cut -c1-40 || echo MISSING")
        labels.append((num, name, lv, rel, root))
r = subprocess.run([MM, "sh", "-v", "0", "-c", "; ".join(cmds)], capture_output=True, timeout=600)
r_stdout = (r.stdout or b"").decode("utf-8", errors="replace")
vals = {}
for line in r_stdout.splitlines():
    if "|" not in line:
        continue
    key, _, sha = line.partition(" ")
    vals[key.strip()] = sha.strip() or "MISSING"

print(f"{'#':4s} {'槽位':14s} {'lv':3s} {'状态':10s}")
print("-" * 56)
done = shell = missing = 0
for num, name, lv, rel, root in labels:
    new = vals.get(f"{num}|{lv}|new", "?")
    old = vals.get(f"{num}|{lv}|old", "?")
    if not new or new in ("MISSING", "?", ""):
        st, missing = "缺失", missing + 1
    elif new == old:
        st, shell = "❌仍是壳", shell + 1
    else:
        st, done = "✅已换自产", done + 1
    print(f"{str(num):4s} {name:14s} {lv:3s} {st}")
print("-" * 56)
print(f"已换自产 {done} / 仍是壳 {shell} / 缺失 {missing}")
