import os; os.environ["WF_TIP"]="191"
from live149 import *
import base149; print([z.name for z in base149._ZIPS][-12:])
C = load("master/character/character.orderedmap")
for k in ("149999","129992","149986"):
    print(k, C[k][:200] if isinstance(C[k],str) else C[k])
for lp in ("master/generated/character_image.orderedmap","master/generated/trimmed_image.orderedmap","master/character/full_shot_image_attribute.orderedmap"):
    try:
        raw,src=read_raw(lp); t=q.parse_node(raw); print(lp, src, type(t), len(t))
        ks=list(t)[:3]; print(ks, [str(t[k])[:200] for k in ks])
    except Exception as e: print(lp, "ERR", e)
