import os; os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(216)
from base149 import *
from base149 import _INDEX
m="production/upload/fb/ab4344a7456dca88f3ce06f01208922f37e395"
import zipfile
t=q.parse_node(zipfile.ZipFile(_INDEX[m]).read(m))
print(type(t), len(t))
for k in t:
    if "vyrn" in k or "liangyue" in k or "159992" in k: print(k, str(t[k])[:200])
