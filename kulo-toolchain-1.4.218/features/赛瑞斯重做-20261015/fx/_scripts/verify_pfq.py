import sys,json,zlib,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import fxlib as X
from copy_pf import DIRS, OFF, NEW
G=X.FX/"pf_quiet"/"game"
dec=lambda b: X.wf_dsl.parse_dsl(zlib.decompress(b,-15))['tree']
mp=json.loads((X.FX/"pf_quiet"/"path_map.json").read_text('utf8'))
n=0
for d,nd in DIRS.items():
    od,ndl=OFF+d,NEW+nd
    assert (G/ndl/f"{nd}.png").read_bytes()==X.read_raw(f"{od}/{d}.png")[0]
    a0=dec(X.read_raw(f"{od}/{d}.atlas.amf3.deflate")[0]); a1=dec((G/ndl/f"{nd}.atlas.amf3.deflate").read_bytes())
    assert [dict(x,n=None) for x in a0]==[dict(x,n=None) for x in a1] and all(y['n']==ndl+x['n'][len(od):] for x,y in zip(a0,a1))
    names={x['n'] for x in a1}
    for p,q in mp.items():
        if not p.startswith(od+"/"): continue
        p0=dec(X.read_raw(p+".parts.amf3.deflate")[0]); p1=dec((G/(q+".parts.amf3.deflate")).read_bytes())
        assert all(i['p'] in names for i in p1['i'])
        for i in p1['i']: i['p']=od+i['p'][len(ndl):]
        assert p0==p1, p
        t0=dec(X.read_raw(p+".timeline.amf3.deflate")[0]); t1=dec((G/(q+".timeline.amf3.deflate")).read_bytes())
        assert t1['sounds']==[] and {**t0,'sounds':[]}==t1
        n+=1
print("pfq ok",n,"effects")
sys.path.insert(0,r"D:/WF/out/赛瑞斯重做-20261015/build")
import seris_pf_quiet as PQ
for types in (PQ.TYPES_HUMAN,PQ.TYPES_DRAGON):
    for lv in (1,2,3):
        t=PQ.compose(types,lv)
    t=PQ.compose(types,3,lv4=True)
print("compose ok")
import seris_pf as P0
inv={v:k for k,v in mp.items()}
def back(x):
    if isinstance(x,list):
        if len(x)==2 and x[0]=="SpecifyEffectDirectly" and x[1] in inv: return ["SpecifyEffectDirectly",inv[x[1]]]
        return [back(y) for y in x]
    if isinstance(x,dict): return {k:back(v) for k,v in x.items()}
    return x
for types in (P0.TYPES_HUMAN,P0.TYPES_DRAGON):
    for lv,l4 in ((1,False),(2,False),(3,False),(3,True)):
        assert back(PQ.compose(types,lv,lv4=l4))==P0.compose(types,lv,lv4=l4)
print("trees identical except ShowEffect paths")
