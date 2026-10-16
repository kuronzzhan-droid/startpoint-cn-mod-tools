import os, zlib, zipfile, struct
os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(216)
from base149 import *
from base149 import _INDEX, SCR
import sys; sys.path.insert(0,str(TOOLS)); import wf_dsl
def raw(lp, kind):
    h=member(lp).split("upload/")[1]; n=f"production/{kind}/{h}"
    if n in _INDEX: return zipfile.ZipFile(_INDEX[n]).read(n)
    return (SCR/"store131/production"/kind/h).read_bytes()
O=r"D:/WF/out/碧-1.4.216/illu/"
a=wf_dsl.parse_dsl(zlib.decompress(raw("character/cnmod_vyrn_dark/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate","upload"),-15))["tree"]
print([e["n"].split("/")[-1] for e in a])
for c in ["liangyue_onmyoji","cnmod_vyrn_dark","white_wolf_gerald"]:
    open(O+c+"_ills.png","wb").write(raw(f"character/{c}/ui/illustration_setting_sprite_sheet.png","medium_upload"))
    for i in (0,1): open(O+c+f"_fs{i}.png","wb").write(raw(f"character/{c}/ui/full_shot_1440_1920_{i}.png","medium_upload"))
tr=q.parse_node(zipfile.ZipFile(_INDEX["production/upload/fb/ab4344a7456dca88f3ce06f01208922f37e395"]).read("production/upload/fb/ab4344a7456dca88f3ce06f01208922f37e395"))
ci=load("master/generated/character_image"); fa=load("master/character/full_shot_image_attribute")
for c,cid in [("liangyue_onmyoji","159992"),("cnmod_vyrn_dark","169978"),("white_wolf_gerald","149999")]:
    print(c, [tr.get(f"character/{c}/ui/full_shot_1440_1920_{i}") for i in (0,1)], ci.get(cid), fa.get(cid))
