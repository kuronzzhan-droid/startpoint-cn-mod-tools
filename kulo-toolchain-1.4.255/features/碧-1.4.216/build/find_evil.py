import os; os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(216)
from base149 import *
from base149 import _INDEX
import zipfile
want=[b"mod_fb2_035_evil_w02",b"mod_fb2_037_evil_w01",b"mod_fb2_039_evil_w02"]
import zlib
for m,z in _INDEX.items():
    if "/upload/" not in m: continue
    raw=zipfile.ZipFile(z).read(m)
    try: s=q.build_node and repr(q.parse_node(raw)).encode()
    except Exception: continue
    hits=[w for w in want if w in s]
    if hits and m!=member("master/battle/boss/general_boss.orderedmap"):
        print(m, z.name, hits)
        t=q.parse_node(raw)
        for k,v in t.items():
            if any(w.decode() in repr(v) for w in hits): print("   key",k, repr(v)[:300])
