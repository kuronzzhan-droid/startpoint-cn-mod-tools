# 设备复原:1.4.216 -> 1.4.212。比对设备 md5 选 variant,输出要回写/删除的清单。
import os, sys, json, zipfile, hashlib, glob
from pathlib import Path
EX=r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
os.environ["WF_EXTRA_DIRS"]=EX
import env
STAGE=Path(r"D:/WF/out/碧-1.4.216/restore"); STAGE.mkdir(exist_ok=True)
zips=[]
for d,pat in [(r"D:/WF/out/凉月修复-20261016/handoff-213","pinball-1.4.212-1.4.213-*.zip"),(r"D:/WF/out/角色超限-120/patch","pinball-1.4.213-1.4.214-*.zip"),(r"D:/WF/out/平衡1016/patch","pinball-1.4.214-1.4.215-*.zip"),(r"D:/WF/out/碧-1.4.216/patch","pinball-1.4.215-1.4.216-*.zip"),(r"D:/WF/out/碧-1.4.216/patch","pinball-1.4.216-1.4.217-*.zip"),(r"D:/WF/out/碧-1.4.216/patch","pinball-1.4.217-1.4.218-*.zip")]:
    zips+=sorted(glob.glob(os.path.join(d,pat)))
final={}
for z in zips:
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            if not n.endswith("/"): final[n]=zf.read(n)
env.setup(212)
import base149
from base149 import _INDEX, SCR
def base(n):
    if n in _INDEX:
        with zipfile.ZipFile(_INDEX[n]) as zf: return zf.read(n)
    p=SCR/"store131/production"/n.split("production/")[1]
    return p.read_bytes() if p.exists() else None
dev=dict(l.split()[::-1] for l in open(sys.argv[1],encoding="utf-8") if l.strip() and not l.startswith("MISSING"))
plan={"write":{}, "delete":[], "unknown":[], "absent":[]}
for n in sorted(final):
    dm=dev.get(n)
    if dm is None: plan["absent"].append(n); continue
    if hashlib.md5(final[n]).hexdigest()!=dm: plan["unknown"].append(n); continue
    b=base(n)
    if b is None: plan["delete"].append(n)
    else:
        f=STAGE/n.replace("/","_"); f.write_bytes(b); plan["write"][n]=(f.name, hashlib.md5(b).hexdigest())
json.dump(plan,open(STAGE/"plan.json","w"),indent=1)
print({k:len(v) for k,v in plan.items()})
open(STAGE/"rels.txt","w",newline="\n").write("\n".join(sorted(final))+"\n")
