import os,sys,json
os.environ["WF_TIP"]="192"
from live149 import *
import wf_describe as D
m=D.enum_map()
TABLES={"ability":"master/ability/ability.orderedmap","leader_ability":"master/ability/leader_ability.orderedmap","ability_soul":"master/ability/ability_soul.orderedmap"}
WANT_IC={"468","389","390","469"}; WANT_DC={"155"}; WANT_PRE={"__"}; WANT_IT={"174","189","227"}
out={}
for t,lp in TABLES.items():
    lay=m["layouts"][t]; b=lay["blocks"]
    for k,rs in flat(lp).items():
        for i,r in enumerate(rs):
            ic=r[b["instant_content"]] if len(r)>b["instant_content"] else ""
            dc=r[b["during_content"]] if len(r)>b["during_content"] else ""
            it=r[b["instant_trigger"]] if len(r)>b["instant_trigger"] else ""
            pres=[r[b[p]] for p in ("precondition1","precondition2","precondition3") if len(r)>b[p]]
            hit=(r[2]=="0" and ic in WANT_IC) or (r[2]=="1" and dc in WANT_DC) or any(p in WANT_PRE for p in pres) or (r[2]=="0" and it in WANT_IT)
            if hit:
                out.setdefault(t,[]).append((k,i,r))
for t,v in out.items():
    print("==",t,len(v))
    for k,i,r in v:
        print(k,i,"|".join(r))
