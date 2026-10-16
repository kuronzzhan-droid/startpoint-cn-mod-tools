import env; env.setup(212)
import zipfile, json
from base149 import *
from base149 import _INDEX
S=r"C:/Users/12101/AppData/Local/Temp/claude/D--WF-startpoint-cn/a2145ccb-7177-4f83-94fc-33a202dbacd2/scratchpad"
SD=Path(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/kulo_staging")
k134={}
for z in sorted(SD.glob("pinball-*.zip")):
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist(): k134[n]=z.name
out=[]
for i in (1,2,3):
    with zipfile.ZipFile(f"{S}/k135-{i}.zip") as zf:
        for n in zf.namelist():
            d=zf.read(n)
            rel=n.split("production/")[1]
            instore=(SCR/"store131/production"/rel).exists()
            ours=_INDEX.get(n); ours=ours.name if ours else None
            try: q.parse_node(d); om=True
            except Exception: om=False
            out.append((n,len(d),instore,ours,k134.get(n),om))
import collections
print(collections.Counter((o[2],o[3] is not None,o[4] is not None,o[5]) for o in out))
for o in out:
    if o[3] or o[4] or o[5]: print(o)
