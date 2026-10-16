import os; os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(218)
from base149 import *
t=load("master/character/character_text.orderedmap")
for c in ["119998","179982","179983","179984","179985","179986"]:
    r=row(t[c]) if c in t else None; print(c, r[0] if r else None, "|", r[3] if r else None)
