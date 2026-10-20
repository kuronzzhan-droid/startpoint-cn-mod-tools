import os,sys,json,collections
os.environ["WF_TIP"]="192"
from live149 import *
import wf_describe as D
m=D.enum_map()
TABLES={"ability":"master/ability/ability.orderedmap","leader_ability":"master/ability/leader_ability.orderedmap","ability_soul":"master/ability/ability_soul.orderedmap"}
cnt=collections.Counter(); ex=collections.defaultdict(list)
for t,lp in TABLES.items():
    lay=m["layouts"][t]; b=lay["blocks"]
    for k,rs in flat(lp).items():
        for i,r in enumerate(rs):
            if len(r)<=b["during_content"]: continue
            if r[b["instant_trigger"]-21+0] if False else False: pass
            mode=r[b["instant_trigger"]-22] if False else None
            it=r[b["instant_trigger"]]; ic=r[b["instant_content"]]
            for key in (("it",it),("ic",ic)):
                if key[1] in ("6","12","390","226","13","70","255"):
                    cnt[(t,)+key]+=1
                    if len(ex[(t,)+key])<4: ex[(t,)+key].append((k,i,r[b["instant_trigger"]:b["instant_trigger"]+12],r[b["instant_content"]:b["instant_content"]+8]))
print(cnt)
for k,v in ex.items():
    print("==",k)
    for e in v: print(" ",e)
