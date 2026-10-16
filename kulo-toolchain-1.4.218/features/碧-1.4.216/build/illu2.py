import os; os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(216)
from base149 import *
from base149 import _INDEX, SCR
KINDS=["upload","medium_upload","android_upload","ios_upload"]
def where(lp):
    m=member(lp); h=m.split("upload/")[1]; out=[]
    for k in KINDS:
        n=f"production/{k}/{h}"
        if n in _INDEX: out.append(k+":"+_INDEX[n].name[:30])
        elif (SCR/"store131/production"/k/h).exists(): out.append(k+":store")
    return out
for c in ["liangyue_onmyoji","cnmod_vyrn_dark","white_wolf_gerald"]:
    for s in ["full_shot_1440_1920_0","full_shot_1440_1920_1","skill_cutin_0","skill_cutin_1","full_shot_0","full_shot_1","square_0","square_1","pixelart/special","pixelart/walk_front"]:
        for ext in [".png",".atf",""]:
            lp=f"character/{c}/ui/{s}{ext}" if "/" not in s else f"character/{c}/{s}{ext}"
            w=where(lp)
            if w: print(c,s+ext,w)
