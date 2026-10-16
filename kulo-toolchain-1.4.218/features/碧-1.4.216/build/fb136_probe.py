import env; env.setup(212)
import zipfile, csv
from base149 import *
from base149 import _INDEX
S=r"C:/Users/12101/AppData/Local/Temp/claude/D--WF-startpoint-cn/a2145ccb-7177-4f83-94fc-33a202dbacd2/scratchpad"
m=member("master/battle/boss/general_boss.orderedmap"); print(m)
t=q.parse_node(zipfile.ZipFile(S+"/k136.zip").read(m))
o=load("master/battle/boss/general_boss.orderedmap")
# kulo 135 base: store131 + kulo 131-135 zips
import subprocess
SD=Path(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/kulo_staging")
b=None
for z in sorted(SD.glob("pinball-*.zip")):
    if m in zipfile.ZipFile(z).namelist(): b=q.parse_node(zipfile.ZipFile(z).read(m)); print("base from",z.name)
for i in (1,2,3):
    if m in zipfile.ZipFile(f"{S}/k135-{i}.zip").namelist(): b=q.parse_node(zipfile.ZipFile(f"{S}/k135-{i}.zip").read(m)); print("base from 135")
if b is None: b=q.parse_node((STORE131/m.split("upload/")[1]).read_bytes()); print("base store131")
def diff(b,t,o,path,out):
    for k in sorted(set(b)|set(t),key=str):
        bv,tv=b.get(k),t.get(k)
        if bv==tv: continue
        ov=o.get(k)
        if ov==bv: out["clean"].append(path+[k])
        elif ov==tv: out["same"].append(path+[k])
        elif all(isinstance(x,dict) for x in (bv,tv,ov)): diff(bv,tv,ov,path+[k],out)
        else: out["conflict"].append((path+[k],bv,tv,ov))
out={"clean":[],"same":[],"conflict":[]}; diff(b,t,o,[],out)
print("our src", source("master/battle/boss/general_boss.orderedmap"))
print({k:len(v) for k,v in out.items()}); print("clean",out["clean"])
for p,bv,tv,ov in out["conflict"]:
    print("CONFLICT",p); [print("  ",l,str(v)[:400]) for l,v in (("B",bv),("T",tv),("O",ov))]
for k in ("mod_fb2_035_evil_w02","mod_fb2_037_evil_w01","mod_fb2_039_evil_w02"):
    print(k, "ours==base", o.get(k)==b.get(k))
pre=member("battle/action/enemy/action/mod/five_boss_v2/fb2_preload$evil_fixed_green.action.dsl.amf3.deflate"); print("preload in our chain", pre in _INDEX)
# any other evil_fixed_green / preload shim in our chain?
for p,bv,tv,ov in out["conflict"]:
    B,T,O=[next(csv.reader([x])) for x in (bv,tv,ov)]
    print(p, len(B),len(T),len(O))
    for i in range(max(len(B),len(T),len(O))):
        g=lambda r:r[i] if i<len(r) else None
        if len({g(B),g(T),g(O)})>1: print("  col",i,"B=",str(g(B))[:120],"| T=",str(g(T))[:120],"| O=",str(g(O))[:120])
print("=== col109")
for p,bv,tv,ov in out["conflict"]:
    B,T,O=[next(csv.reader([x])) for x in (bv,tv,ov)]
    print(p[0],"B==T",B[109]==T[109],"B==O",B[109]==O[109]); print("  B",B[109]); print("  O",O[109])
    print("  other cols differ T vs O:", [i for i in range(162) if T[i]!=O[i]])
