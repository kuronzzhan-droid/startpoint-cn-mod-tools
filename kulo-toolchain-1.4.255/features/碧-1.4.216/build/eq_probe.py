import os, zipfile
os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(218)
from base149 import *
eq=load("master/item/equipment.orderedmap")
print(len(eq)); 
for k in ["1010001","5920001","5990001"]:
    if k in eq: print(k, row(eq[k])[:12])
names={k:row(v)[0] for k,v in eq.items()}
import re
for pat in ["领主","白鸽羽毛","珍珠奶茶","血月","大葱","PARADOX","面包刀","赌注","北斗","一拳","鬼面","氪金","三相","肉斩","裂空","GM"]:
    print(pat, [(k,n) for k,n in names.items() if pat in n][:12])
it=load("master/item/item.orderedmap"); 
for k in ["10000320"]: print(k, row(it[k])[:8])
print([(k,row(v)[0]) for k,v in it.items() if "悖论" in row(v)[0] or "领主币" in row(v)[0] or "强化核" in row(v)[0]][:10])
