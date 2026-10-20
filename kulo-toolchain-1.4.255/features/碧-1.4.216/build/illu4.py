import os; os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(216)
from base149 import *
from base149 import _INDEX, SCR
ch=load("master/character/character.orderedmap")
KINDS=["upload","medium_upload","android_upload","ios_upload"]
def where(lp):
    h=member(lp).split("upload/")[1]; out=[]
    for k in KINDS:
        n=f"production/{k}/{h}"
        if n in _INDEX: out.append(k+":"+_INDEX[n].name[:34])
        elif (SCR/"store131/production"/k/h).exists(): out.append(k+":store")
    return out
have=0; miss=[]
for cid,v in ch.items():
    code=row(v)[0]
    w=where(f"character/{code}/ui/full_shot_illustration_setting_0.png")
    if w: have+=1
    else: miss.append((cid,code))
print("have",have,"miss",len(miss)); print(miss[:60])
print(where("character/fire_dragon/ui/full_shot_illustration_setting_0.png"))
