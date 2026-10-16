import os,sys,json
os.environ["WF_TIP"]="192"
from live149 import *
import wf_describe as D
m=D.enum_map()
for blk,k in (("instant_content","468"),("instant_content","389"),("instant_content","390"),("instant_content","469"),("instant_trigger","6"),("instant_trigger","12"),("precondition","202"),("during_content","155"),("instant_content","211"),("instant_content","226")):
    print(blk,k,json.dumps(m["cases"][blk][k],ensure_ascii=False))
print(json.dumps(m["usage_counts"],ensure_ascii=False)[:600])
uc=m["usage_counts"]
for key in uc:
    for k in ("468","389","390","469","202","155"):
        try: print(key,k,uc[key].get(k))
        except Exception as e: pass
print(m["layouts"].keys())
