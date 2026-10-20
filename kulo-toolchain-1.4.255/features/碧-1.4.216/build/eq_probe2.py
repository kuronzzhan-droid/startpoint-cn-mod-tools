import os
os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(218)
from base149 import *
eq=load("master/item/equipment.orderedmap")
E={k:row(v) for k,v in eq.items()}
for pat in ["领主","白鸽羽毛","珍珠奶茶","血月","大葱","PARADOX","面包刀","赌注","北斗","一拳","鬼面","氪金","三相","肉斩","裂空","GM"]:
    print(pat, [(k,r[1]) for k,r in E.items() if pat in r[1]][:12])
mod=[(k,r[1],r[0]) for k,r in E.items() if r[0].startswith("mod_")]
print(len(mod)); print(mod)
it=load("master/item/item.orderedmap"); I={k:row(v) for k,v in it.items()}
print([(k,r[2],r[3]) for k,r in I.items() if any(w in r[2] for w in ("悖论","领主币","强化核","核"))][:20])
