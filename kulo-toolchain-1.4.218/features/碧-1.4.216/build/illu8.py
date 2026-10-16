import os, zlib, zipfile
os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(216)
from base149 import *
from base149 import _INDEX, SCR
import sys; sys.path.insert(0,str(TOOLS)); import wf_dsl
def raw(lp, kind="upload"):
    h=member(lp).split("upload/")[1]; n=f"production/{kind}/{h}"
    if n in _INDEX: return zipfile.ZipFile(_INDEX[n]).read(n), _INDEX[n].name
    p=SCR/"store131/production"/kind/h
    return (p.read_bytes(),"store") if p.exists() else (None,None)
for c in ["cnmod_vyrn_dark","liangyue_onmyoji"]:
    for nm in ["sprite_sheet","illustration_setting_sprite_sheet"]:
        b,src=raw(f"character/{c}/ui/{nm}.atlas.amf3.deflate")
        if b: print(c,nm,src,[e["n"].split("/")[-1] for e in wf_dsl.parse_dsl(zlib.decompress(b,-15))["tree"]])
        else: print(c,nm,"MISSING")
fa=load("master/character/full_shot_image_attribute.orderedmap"); print("fa",fa.get("169978"), fa.get("159992"))
