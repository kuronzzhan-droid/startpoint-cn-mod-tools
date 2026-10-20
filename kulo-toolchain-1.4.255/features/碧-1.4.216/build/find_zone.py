import os; os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(216)
from base149 import *
from base149 import _INDEX
import zipfile
for m in ["production/upload/19/a4aa442b3249499356e7a3f6370e530bfe355e","production/upload/82/93e535e806d70640f45950db1fe14ed9482bdf"]:
    t=q.parse_node(zipfile.ZipFile(_INDEX[m]).read(m))
    print(m, len(t), list(t)[:5])
    for k,v in t.items():
        r=repr(v)
        if "1099035" in r or "evil_w02" in r: print("  ",k, r[:400])
