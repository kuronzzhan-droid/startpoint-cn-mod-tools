import os, zlib, zipfile
os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(int(os.environ.get("VTIP","217")))
from base149 import *
from base149 import _INDEX, SCR
import sys; sys.path.insert(0,str(TOOLS)); import wf_dsl
def raw(lp, kind="upload"):
    h=member(lp).split("upload/")[1]; n=f"production/{kind}/{h}"
    if n in _INDEX: return zipfile.ZipFile(_INDEX[n]).read(n)
    p=SCR/"store131/production"/kind/h
    return p.read_bytes() if p.exists() and p.stat().st_size>16 else None
bad=[]; n=0
for cid,v in load("master/character/character.orderedmap").items():
    code=row(v)[0]; a=raw(f"character/{code}/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate")
    if a is None: continue
    n+=1
    names={e["n"] for e in wf_dsl.parse_dsl(zlib.decompress(a,-15))["tree"]}
    need={f"character/{code}/ui/full_shot_illustration_setting_{i}" for i in (0,1)}
    if not need<=names: bad.append((cid,code))
print("checked",n,"bad",bad)
