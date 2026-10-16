import os,sys
sys.path.insert(0,r'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build'); os.chdir(r'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build')
from live149 import *
from layout import *
T=load('master/ability/ability.orderedmap'); c={}
for k,v in T.items():
    for i,r in enumerate([r for r in rows(v) if r]):
        if len(r)>52 and r[5]=='0' and r[47] in ('356','357','255','256'):
            c.setdefault(r[47],[]).append((k,i,r[27]))
for kk,vv in c.items(): print(kk,len(vv),vv[:5])
