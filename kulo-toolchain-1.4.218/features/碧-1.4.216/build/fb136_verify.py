import os; os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/碧-1.4.216/patch-test-212"
import env; env.setup(212)
from base149 import *
import zipfile, glob
lp="master/battle/boss/general_boss.orderedmap"; m=member(lp)
o=load(lp)
new=None
for z in sorted(glob.glob(r"D:/WF/out/碧-1.4.216/patch-test-212/*.zip")):
    if m in zipfile.ZipFile(z).namelist(): new=q.parse_node(zipfile.ZipFile(z).read(m))
diffk=[(k,s) for k in set(o)|set(new) for s in set(o.get(k,{}))|set(new.get(k,{})) if o.get(k,{}).get(s)!=new.get(k,{}).get(s)]
print("changed rows",diffk)
for k,s in diffk:
    O,N=row(o[k][s]),row(new[k][s]); print(k,s,[(i,O[i][-40:],N[i][-80:]) for i in range(len(O)) if O[i]!=N[i]], "fb3_buff$entrance kept:", "fb3_buff$entrance" in N[109])
