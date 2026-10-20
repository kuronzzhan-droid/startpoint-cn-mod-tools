import os,sys
sys.path.insert(0,r'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build')
os.chdir(r'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build')
from live149 import *
from layout import *
tbl={'a':('ability','master/ability/ability.orderedmap'),'l':('leader_ability','master/ability/leader_ability.orderedmap')}
for arg in sys.argv[1:]:
    t,k=arg.split(':',1); idx=None
    if '#' in k: k,idx=k.split('#'); idx=int(idx)
    name,lp=tbl[t]; T=load(lp)
    lay=D.layout(name); 
    rs=[r for r in rows(T[k]) if r]
    for i,r in enumerate(rs):
        if idx is not None and i!=idx: continue
        print(arg,i,D.describe_line(r,name))
        print('   ', {j:v for j,v in enumerate(r) if v not in ('','(None)')})
