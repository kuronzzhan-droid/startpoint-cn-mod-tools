import os,sys,json
os.environ["WF_TIP"]="192"
from live149 import *
import wf_describe as D
m=D.enum_map()
print(m.keys())
for blk in ("instant_content","during_content","instant_trigger","during_trigger","precondition"):
    for k,c in m["cases"][blk].items():
        s=json.dumps(c,ensure_ascii=False)
        if any(w in s for w in ("Guts","guts","毅力","根性","Survive","Combo","combo","连击","Endure","Main","主位")):
            print(blk,k,s[:300])
