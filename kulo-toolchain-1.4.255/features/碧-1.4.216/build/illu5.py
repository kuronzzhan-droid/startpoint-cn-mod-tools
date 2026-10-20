import os; os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(216)
from base149 import *
from base149 import _INDEX, SCR
KINDS=["upload","medium_upload","android_upload","ios_upload"]
def where(lp):
    h=member(lp).split("upload/")[1]; out=[]
    for k in KINDS:
        n=f"production/{k}/{h}"
        if n in _INDEX: out.append(k+":"+_INDEX[n].name[:34])
        elif (SCR/"store131/production"/k/h).exists(): out.append(k+":store")
    return out
for c in ["fire_dragon","liangyue_onmyoji","cnmod_vyrn_dark","white_wolf_gerald","seris_dragon_king"]:
    for ext in [".png",".atlas",".atlas.amf3.deflate",".json",".atf",".parts.amf3.deflate",".amf3.deflate",""]:
        lp=f"character/{c}/ui/illustration_setting_sprite_sheet{ext}"
        w=where(lp)
        if w: print(c,ext,w)
