import os
os.environ["WF_TIP"]="192"
from live149 import *
EQ=flat("master/item/equipment.orderedmap")
for i in ("5010012","2040001","5040009","2050001","5010050","8000104","8000113","5085000","5090047","5010044","4070011"):
    r=EQ.get(i)
    print(i, r[0][1] if r else None, "|", r[0][7] if r else None)
AB=flat("master/ability/ability.orderedmap")
for k in ("1410151","1499963","1499873","2410015","1210011"):
    for i,r in enumerate(AB.get(k,[])): print(k,i,"|".join(r[:10]))
SO=flat("master/ability/ability_soul.orderedmap")
for k in ("8000113","5085000","5010012","2040001"):
    for i,r in enumerate(SO[k]): print(k,i,"|".join(r))
