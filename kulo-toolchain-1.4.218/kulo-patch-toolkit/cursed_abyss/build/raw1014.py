import os,sys,json
os.environ["WF_TIP"]="197"
from live149 import *
AB=load('master/ability/ability.orderedmap'); LE=load('master/ability/leader_ability.orderedmap')
for lp,T,keys in (("ab",AB,["1399903","1399905","1399912","1499982","1399901"]),("le",LE,["119996","119990","139990"])):
    for k in keys:
        for i,r in enumerate([x for x in rows(T[k]) if x]):
            print(lp,k,i,len(r),{c:v for c,v in enumerate(r) if v not in ('','(None)','0','false')})
