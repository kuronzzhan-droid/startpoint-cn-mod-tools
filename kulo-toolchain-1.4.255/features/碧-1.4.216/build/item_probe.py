import os
os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(218)
from base149 import *
from base149 import _INDEX, SCR
it=load("master/item/item.orderedmap"); I={k:row(v) for k,v in it.items()}
for w in ("悖论","领主","强化核","领主币"): print(w, [(k,r[2],r[3]) for k,r in I.items() if w in r[2]][:10])
KINDS=["upload","medium_upload","android_upload","ios_upload"]
def where(lp):
    h=member(lp).split("upload/")[1]; out=[]
    for k in KINDS:
        n=f"production/{k}/{h}"
        if n in _INDEX: out.append(k+":z")
        elif (SCR/"store131/production"/k/h).exists(): out.append(k+":s")
    return out
for p in ["item/equipment/mod/paradox/paradox","item/equipment/general/sword_0001","item/materials/mod/overlimit/overlimit_crystal"]:
    for ext in [".png",".atf",""]: print(p+ext, where(p+ext))
