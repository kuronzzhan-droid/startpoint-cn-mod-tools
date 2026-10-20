# -*- coding: utf-8 -*-
"""五重调参（叠加在 1.4.186 上）：登场负面 攻击 -200%、技能伤害 -200%、充能 -50%（防御 -30% 不变）；
boss_level 攻击基数（c8）：画龙/水鬼斯拉姆冈 ×0.8，低伤害组 ×1.15。只动五重专用 mod_ 键。"""
import copy, hashlib, json, os, zipfile, zlib
os.environ.setdefault("WF_TIP", "187")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from dsltools import commands
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_cursed_weapons as W
OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.186-1.4.187-1-five-boss-tune-local.zip"
PROG = "battle/action/enemy/action/mod/five_boss_v3/fb3_buff$entrance"
BL_LP = "master/battle/boss/boss_level.orderedmap"; GB_LP = "master/battle/boss/general_boss.orderedmap"
NL = chr(10)
DOWN = {"yokai_emaki_middle_boss": 0.8, "spirit_beast_water": 0.8}
UP = {"lich_expert": 1.15, "hermit_crab_expert_100": 1.15, "mod_fb2_deep_king": 1.15, "hermit_crab_another": 1.15,
      "administrator_80": 1.15, "desert_bonds_big_boss": 1.15}
NEW = {"fb3_atk_down": -2.0, "fb3_skill_down": -2.0, "fb3_weary": -0.5}
LOG = []
t = copy.deepcopy(dsl_tree(PROG)); n = 0
for pp, c in commands(t, "CreateCondition"):
    if c[7] in NEW:
        ac = c[2][0]; idx = 2
        assert ac[idx] == [{"min": -0.3, "max": -0.3}], (c[7], ac)
        ac[idx] = [{"min": NEW[c[7]], "max": NEW[c[7]]}]; n += 1
    elif c[7] == "fb3_def_down":
        assert c[2][0][3] == [{"min": -0.3, "max": -0.3}]
assert n == 3
assert not W.dsl_signature_problems(t)
d = encode_tree(t); assert wf_dsl.parse_dsl(zlib.decompress(d, -15))["tree"] == t
files = {wf_dsl.dsl_logical(PROG): d}
LOG.append("登场负面：攻击力 -30% → -200%，技能伤害 -30% → -200%，技能充能 -30% → -50%，全属性耐性 -30% 不变")
integ0 = json.load(open(OUT / "patch" / "pinball-1.4.185-1.4.186-1-five-boss-buffs-local.integrity.json", encoding="utf-8"))
BL = load(BL_LP); GB = load(GB_LP); BASE = copy.deepcopy(BL); changed = {}
for b in integ0["bosses"]:
    assert b.startswith("mod_"), b
    rt = row(list(GB[b].values())[0])[42]
    f = DOWN.get(rt) or UP.get(rt)
    if not f: continue
    r = row(BL[b]); old = r[8]; r[8] = f"{float(old) * f:.6g}"
    s = q.csv_text([r]) if hasattr(q, "csv_text") else None
    from stage_all import csv_text as _csv
    s = _csv([r]); BL[b] = s if BL[b].endswith(NL) else s.rstrip(NL)
    changed.setdefault(rt, []).append((b, old, r[8], f))
for rt, v in sorted(changed.items()):
    LOG.append(f"{rt}: {len(v)} 键 atk {v[0][1]} → {v[0][2]}（×{v[0][3]}）")
data = q.build_node(BL); back = q.parse_node(data); assert back == BL and set(back) == set(BASE)
assert all(k.startswith("mod_") for k in BASE if back[k] != BASE[k])
files[BL_LP] = data
members = {member(lp): x for lp, x in files.items()}
path = OUT / "patch" / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members): zf.writestr(m, members[m])
blob = path.read_bytes()
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
         "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.186", "version": "1.4.187",
         "changed": changed, "log": LOG}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + NL, "utf-8")
print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False)); print(NL.join(LOG))
