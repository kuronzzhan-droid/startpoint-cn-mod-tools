import os,sys,json
os.environ["WF_TIP"]="196"
from live149 import *
from dsltools import commands, walk
P="battle/action/skill/action/rare5/land_dragon_wind_playable$land_dragon_wind_playable_"
for n in ("1","2"):
    t=dsl_tree(P+n)
    print("=====",n)
    def show(node,depth=0):
        if isinstance(node,list) and len(node)>=2 and node[0]=="Command":
            c=node[1]; name=c[0]
            if name=="CreateNormalAttack":
                print("  "*depth+name, json.dumps(c[1:9],ensure_ascii=False)[:300])
            elif name in ("CreateHitArea",):
                print("  "*depth+name, json.dumps(c[1:4],ensure_ascii=False)[:150])
            else:
                print("  "*depth+name, json.dumps([x for x in c[1:4] if not isinstance(x,list) or len(json.dumps(x))<80],ensure_ascii=False)[:160])
            for x in c[1:]:
                show(x,depth+1)
        elif isinstance(node,list):
            for x in node: show(x,depth)
    show(t)
