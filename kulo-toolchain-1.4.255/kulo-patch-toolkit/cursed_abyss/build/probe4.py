import os,sys,json
os.environ["WF_TIP"]="196"
from live149 import *
CAS=load("master/string/custom_ability_string.orderedmap"); TX=load("master/character/character_text.orderedmap")
pats=["时空裂痕","魔王权能","焰域研修","250COMBO","250连击","风蚀","雷华","麻痹特攻","秋灯","盛夏","月兔","死神"]
for name,t in (("CAS",CAS),("TX",TX)):
    for k,v in t.items():
        s=str(v)
        hit=[p for p in pats if p in s]
        if hit and (name=="CAS" or k in ("149999","169995","119989","159998","139995","139992","149997","149998","149990","129997")):
            print(name,k,hit, s[:400].replace("\n"," | "))
AB=load("master/ability/ability.orderedmap"); LE=load("master/ability/leader_ability.orderedmap")
for nm,t in (("AB",AB),("LE",LE)):
    for k,v in t.items():
        for r in rows(v):
            if "1499990" in r: print(nm,k,[ (i,x) for i,x in enumerate(r) if x=="1499990"])
