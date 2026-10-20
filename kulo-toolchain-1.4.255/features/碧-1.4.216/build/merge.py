# -*- coding: utf-8 -*-
"""把灰 1.4.134->1.4.135(碧+凉月整合)重切为本地链 1.4.{TIP}->1.4.{TIP+1}:与本地链重叠的表做三方行级合并,非表成员要求本地未改才取灰版。"""
import os, sys, json, zipfile, hashlib, zlib
MYTIP=int(os.environ.get("TIP","212"))
import env; env.setup(MYTIP)
from base149 import *
from base149 import _INDEX
S=Path(r"~/AppData/Local/Temp/claude/D--WF-startpoint-cn/a2145ccb-7177-4f83-94fc-33a202dbacd2/scratchpad")
SD=Path(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/kulo_staging")
OUT=Path(__file__).resolve().parent.parent
DRY=os.environ.get("DRY","1")=="1"
k134={}
for z in sorted(SD.glob("pinball-*.zip")):
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist(): k134[n]=z
def base_raw(m):
    if m in k134:
        with zipfile.ZipFile(k134[m]) as z: return z.read(m)
    p=STORE131/m.split("upload/")[1] if "production/upload/" in m else SCR/"store131/production"/m.split("production/")[1]
    return p.read_bytes() if p.exists() else None
def our_raw(m):
    if m in _INDEX:
        with zipfile.ZipFile(_INDEX[m]) as z: return z.read(m)
    return base_raw(m) if m not in k134 else None  # k134-only member never reached our chain? treat specially
def is_map(b):
    try: q.parse_node(b); return True
    except Exception: return False
CONFLICTS=[]
def colmerge(bv,tv,ov):
    """同一 CSV 行:双方改了不同列才合并,同列不同值返回 None(冲突)。"""
    B,T,O=row(bv),row(tv),row(ov)
    if not (len(B)==len(T)==len(O)) or len(B)<2: return None
    R=[]
    for b,t,o in zip(B,T,O):
        if t==b: R.append(o)
        elif o==b or o==t: R.append(t)
        else: return None
    return join(R)
def merge(b,t,o,path,log):
    r=dict(o)
    for k in list(b)+[k for k in t if k not in b]:
        bv,tv=b.get(k),t.get(k)
        if bv==tv: continue
        ov=o.get(k)
        if ov==bv:
            if tv is None: r.pop(k,None); log.append(("del",path+[k]))
            else: r[k]=tv; log.append(("add" if bv is None else "mod",path+[k]))
        elif ov==tv: log.append(("same",path+[k]))
        elif all(isinstance(x,dict) for x in (bv,tv,ov)): r[k]=merge(bv,tv,ov,path+[k],log)
        elif all(isinstance(x,str) for x in (bv,tv,ov)) and colmerge(bv,tv,ov) is not None:
            r[k]=colmerge(bv,tv,ov); log.append(("col",path+[k]))
        else: CONFLICTS.append((path+[k],bv,tv,ov)); log.append(("CONFLICT",path+[k]))
    return r
data={}
for i in (1,2,3):
    with zipfile.ZipFile(S/f"k135-{i}.zip") as zf:
        for n in zf.namelist():
            if not n.endswith("/"): data[n]=zf.read(n)
k135=dict(data)
WITH136=os.environ.get("WITH136","1")=="1"
if WITH136:
    with zipfile.ZipFile(S/"k136.zip") as zf:
        for n in zf.namelist():
            if not n.endswith("/"):
                assert n not in k135, n  # 两边不重叠,基线即 k134/store
                data[n]=zf.read(n)
merged={}; taken=[]
for m in sorted(data):
    if m not in _INDEX: continue  # 本地链没碰过:原样
    o=our_raw(m); b=base_raw(m); t=data[m]
    if o==t: taken.append((m,"same")); continue
    if b is not None and o==b: taken.append((m,"theirs")); continue
    if b is not None and is_map(t) and is_map(o) and is_map(b):
        bb,tt,oo=q.parse_node(b),q.parse_node(t),q.parse_node(o)
        assert q.parse_node(q.build_node(oo))==oo, m
        log=[]; res=merge(bb,tt,oo,[],log)
        nb=q.build_node(res); assert q.parse_node(nb)==res
        data[m]=nb; merged[m]={"src_ours":_INDEX[m].name,"rows":[f"{a}:{'/'.join(map(str,p))}" for a,p in log]}
    else:
        CONFLICTS.append(([m],"<bin base>" if b else None,"<bin theirs>","<bin ours %s>"%_INDEX[m].name))
print("members",len(data),"overlap",sum(1 for m in data if m in _INDEX),"taken",taken.__len__(),"merged",len(merged))
for m,v in merged.items():
    print("MERGED",m[18:28],v["src_ours"][:45],len(v["rows"]),v["rows"][:12])
for p,bv,tv,ov in CONFLICTS:
    print("CONFLICT",p)
    for lab,v in (("B",bv),("T",tv),("O",ov)): print("    ",lab,repr(v)[:700])
if CONFLICTS: sys.exit(1)
if DRY: sys.exit(0)
# ---- 写包 ----
FRM=MYTIP; TO=int(os.environ.get("TO", str(MYTIP+1))); TAG="vyrn-character"
PD=OUT/("patch" if os.environ.get("FINAL")=="1" else f"patch-test-{MYTIP}")
PD.mkdir(exist_ok=True)
LIMIT=5*1024*1024
names=sorted(data)
comp={m:len(zlib.compress(data[m],6)) for m in names}
groups=[]
for m in sorted(names,key=lambda x:-comp[x]):
    for g in groups:
        if g[1]+comp[m]+400<=LIMIT-64*1024: g[0].append(m); g[1]+=comp[m]+400; break
    else: groups.append([[m],comp[m]+400])
src_sha={f"k135-{i}":hashlib.sha256((S/f"k135-{i}.zip").read_bytes()).hexdigest() for i in (1,2,3)}
if WITH136: src_sha["k136"]=hashlib.sha256((S/"k136.zip").read_bytes()).hexdigest()
for i,(gm,_) in enumerate(groups,1):
    name=f"pinball-1.4.{FRM}-1.4.{TO}-{i}-{TAG}-local.zip"; p=PD/name
    with zipfile.ZipFile(p,"w",zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(gm): zf.writestr(m,data[m])
    blob=p.read_bytes(); assert len(blob)<=LIMIT,(name,len(blob))
    integ={"name":name,"size":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),"members":len(gm),"files":sorted(gm),
      "member_sha256":{m:hashlib.sha256(data[m]).hexdigest() for m in sorted(gm)},
      "applies_on":f"1.4.{FRM}","version":f"1.4.{TO}","part":f"{i}/{len(groups)}",
      "source":{"repo":"Ku1o/startpoint-cn-kulo@main 87b9b14d+cc94fcca","archives":[f"pinball-1.4.134-1.4.135-{k}-vyrn-liangyue-atlas-final-20261011.zip" for k in (1,2,3)]+(["pinball-1.4.135-1.4.136-1-five-boss-evil-cannon-preload.zip"] if WITH136 else []),"sha256":src_sha},
      "merged_tables":{m:v for m,v in merged.items() if m in gm},
      "log":[f"重切自灰 1.4.134->1.4.135(碧 169978 + 凉月整合)"+(" 与 1.4.135->1.4.136(五重 evil 绿炮弹预载)" if WITH136 else "")+";与本地链 1.4.131-1.4.{FRM} 重叠的表三方行级合并,其余成员原样"]}
    p.with_name(p.stem+".integrity.json").write_text(json.dumps(integ,ensure_ascii=False,indent=2)+"\n","utf-8")
    print("WROTE",name,len(blob),integ["sha256"],len(gm))
