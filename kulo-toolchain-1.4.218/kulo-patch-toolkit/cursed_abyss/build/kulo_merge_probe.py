import os, zipfile, json
os.environ["WF_TIP"]="187"
from base149 import *
from base149 import _INDEX
SD=Path(__file__).resolve().parent.parent/"kulo_staging"
ZS=sorted(p for p in SD.glob("pinball-*.zip"))
def theirs_raw(i, m):
    with zipfile.ZipFile(ZS[i]) as z: return z.read(m)
def base_raw(m):
    # their state before zip i (only 6 overlaps; their zips don't overlap each other)
    return (STORE131/m.split("upload/")[1]).read_bytes()
def our_raw(m):
    if m in _INDEX:
        with zipfile.ZipFile(_INDEX[m]) as z: return z.read(m)
    return base_raw(m)
def diff(b,t,o,path,out):
    for k in sorted(set(b)|set(t), key=str):
        bv,tv=b.get(k),t.get(k)
        if bv==tv: continue
        ov=o.get(k)
        if ov==bv: out["clean"].append(path+[k])
        elif ov==tv: out["same"].append(path+[k])
        elif isinstance(bv,dict) and isinstance(tv,dict) and isinstance(ov,dict): diff(bv,tv,ov,path+[k],out)
        else: out["conflict"].append((path+[k],bv,tv,ov))
for i,z in enumerate(ZS):
    with zipfile.ZipFile(z) as zf: names=[n for n in zf.namelist() if not n.endswith("/")]
    for m in names:
        if m not in _INDEX: continue
        b=q.parse_node(base_raw(m)); t=q.parse_node(theirs_raw(i,m)); o=q.parse_node(our_raw(m))
        out={"clean":[],"same":[],"conflict":[]}; diff(b,t,o,[],out)
        print("==",z.name[:22],m[18:25],"src",_INDEX[m].name[:40],"clean",len(out["clean"]),"same",len(out["same"]),"conflict",len(out["conflict"]))
        print("   clean keys:", [p for p in out["clean"]][:40])
        for p,bv,tv,ov in out["conflict"]:
            print("   CONFLICT",p); 
            for lab,v in (("B",bv),("T",tv),("O",ov)): print("     ",lab,repr(v)[:600])
