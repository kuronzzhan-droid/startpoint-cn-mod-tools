import os, zlib, zipfile, struct
os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(216)
from base149 import *
from base149 import _INDEX, SCR
import sys; sys.path.insert(0,str(TOOLS))
import wf_dsl
def raw(lp, kind="upload"):
    h=member(lp).split("upload/")[1]; n=f"production/{kind}/{h}"
    if n in _INDEX: return zipfile.ZipFile(_INDEX[n]).read(n)
    return (SCR/"store131/production"/kind/h).read_bytes()
def png_size(b): return struct.unpack(">II", b[16:24])
for c in ["fire_dragon","liangyue_onmyoji","cnmod_vyrn_dark","white_wolf_gerald"]:
    a=raw(f"character/{c}/ui/illustration_setting_sprite_sheet.atlas.amf3.deflate")
    d=zlib.decompress(a,-15)
    try: obj=wf_dsl.parse_dsl(d)
    except Exception as e: obj=("ERR",e)
    p=raw(f"character/{c}/ui/illustration_setting_sprite_sheet.png","medium_upload")
    print(c, "png", png_size(p), len(p)); print("   ", str(obj)[:600])
