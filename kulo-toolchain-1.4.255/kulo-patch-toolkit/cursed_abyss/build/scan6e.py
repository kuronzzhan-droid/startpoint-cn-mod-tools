import os,collections
os.environ["WF_TIP"]="192"
from live149 import *
import wf_describe as D
m=D.enum_map()
TABLES={"ability":"master/ability/ability.orderedmap","leader_ability":"master/ability/leader_ability.orderedmap","ability_soul":"master/ability/ability_soul.orderedmap"}
c=collections.Counter(); ex={}
for t,lp in TABLES.items():
    b=m["layouts"][t]["blocks"]
    for k,rs in flat(lp).items():
        for i,r in enumerate(rs):
            if len(r)<=b["instant_content"]+2: continue
            it=r[b["instant_trigger"]]; ic=r[b["instant_content"]]; tg=r[b["instant_content"]+1]
            if it=="18":
                key=(t,r[b["instant_trigger"]+1],ic,tg); c[key]+=1; ex.setdefault(key,k)
for k,v in sorted(c.items()): print(k,v,ex[k])
