import os,sys
sys.path.insert(0,r'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build'); os.chdir(r'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build')
from live149 import *
lp,*keys=sys.argv[1:]
T=load(lp)
for k in keys:
    if k.startswith('~'):
        for kk,v in T.items():
            if k[1:] in kk: print(kk,'=>',str(v)[:600])
    else: print(k,'=>',T.get(k))
