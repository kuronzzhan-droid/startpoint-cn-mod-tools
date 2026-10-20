import os,sys
sys.path.insert(0,r'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build'); os.chdir(r'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build')
from live149 import *
from layout import *
T=load('master/ability/ability.orderedmap'); n=0
for k,v in T.items():
    for i,r in enumerate([r for r in rows(v) if r]):
        if len(r)>102 and r[5]=='1' and r[97]=='38':
            n+=1
            if n<=6: print(k,i,D.describe_line(r,'ability'), {j:r[j] for j in range(97,115) if r[j] not in ('','(None)')})
print('total',n)
