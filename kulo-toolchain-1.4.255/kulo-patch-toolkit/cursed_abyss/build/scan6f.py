import os
os.environ["WF_TIP"]="192"
from live149 import *
SO=flat("master/ability/ability_soul.orderedmap")
for k in ("5050017","5900913","300001"):
    for i,r in enumerate(SO[k]):
        if r[24] in ("18",) or r[44] in ("468","211"): print(k,i,r[24:30],r[44:48])
