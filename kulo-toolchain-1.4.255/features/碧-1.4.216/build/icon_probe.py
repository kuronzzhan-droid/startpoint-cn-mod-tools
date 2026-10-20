import os, zipfile
os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(218)
from base149 import *
from base149 import _INDEX, SCR
KINDS=["upload","medium_upload","android_upload","ios_upload"]
def where(lp):
    h=member(lp).split("upload/")[1]; out=[]
    for k in KINDS:
        n=f"production/{k}/{h}"
        if n in _INDEX: out.append(k+":"+_INDEX[n].name[:30])
        else:
            p=SCR/"store131/production"/k/h
            if p.exists(): out.append(k+":store%d"%p.stat().st_size)
    return out
for c in ["fire_dragon","cnmod_vyrn_dark","white_wolf_gerald","liangyue_onmyoji"]:
    for s in ["square_0","square_132_132_0","square_round_95_95_0","square_round_136_136_0","sprite_sheet"]:
        for ext in [".png",".atlas.amf3.deflate"]:
            w=where(f"character/{c}/ui/{s}{ext}")
            if w: print(c,s+ext,w)
eq=load("master/equipment/equipment.orderedmap") if True else None
k=list(eq)[:3]; print(k, [str(eq[x])[:200] for x in k])
