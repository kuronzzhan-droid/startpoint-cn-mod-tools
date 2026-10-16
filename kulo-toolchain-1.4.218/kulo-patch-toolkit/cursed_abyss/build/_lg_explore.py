import os; os.environ["WF_TIP"]="198"
from live149 import *
def show(lp, n=2):
    try: t=load(lp)
    except Exception as e: print(lp,"ERR",type(e).__name__); return None
    ks=list(t)[:n]; print(lp, len(t), "keys", ks)
    for k in ks:
        v=t[k]
        if isinstance(v,dict):
            k2=list(v)[:3]; print("  ",k,"->",k2, [str(v[x])[:300] for x in k2[:1]])
        else: print("  ",k,"->",str(v)[:300])
    return t
for lp in ["master/battle/field_data.orderedmap","master/battle/zone.orderedmap","master/battle/boss/standard_boss.orderedmap","master/battle/boss/general_boss.orderedmap","master/battle/zako/general_zako.orderedmap","master/battle/boss/funnel/general_funnel.orderedmap","master/battle/boss/funnel/standard_funnel.orderedmap","master/battle/enemy/hp/hit_hp_correction_curve.orderedmap","master/battle/enemy/party_atk_curve.orderedmap"]:
    show(lp)
