import os; os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(216)
from base149 import *
from base149 import _INDEX, SCR
import zipfile
m="production/upload/fb/ab4344a7456dca88f3ce06f01208922f37e395"
t=q.parse_node(zipfile.ZipFile(_INDEX[m]).read(m))
ks=[k for k in t if "illustration_setting" in k]
print(len(ks)); print([k for k in ks if any(c in k for c in ("liangyue","vyrn","white_wolf_gerald","seris"))])
print(ks[:5])
KINDS=["upload","medium_upload","android_upload","ios_upload"]
def where(lp):
    h=member(lp).split("upload/")[1]; out=[]
    for k in KINDS:
        n=f"production/{k}/{h}"
        if n in _INDEX: out.append(k+":"+_INDEX[n].name[:34])
        elif (SCR/"store131/production"/k/h).exists(): out.append(k+":store")
    return out
for c in ["liangyue_onmyoji","cnmod_vyrn_dark","white_wolf_gerald"]:
    for i in (0,1):
        lp=f"character/{c}/ui/full_shot_illustration_setting_{i}.png"; print(c,i,where(lp), t.get(f"character/{c}/ui/full_shot_illustration_setting_{i}"))
