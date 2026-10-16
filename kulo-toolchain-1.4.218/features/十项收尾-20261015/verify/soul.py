import os,sys
sys.path.insert(0,r'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build'); os.chdir(r'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build')
from live149 import *
from layout import *
T=load('master/ability/ability_soul.orderedmap')
print(D.layout('ability_soul')['blocks'])
for i,r in enumerate([r for r in rows(T[sys.argv[1]]) if r]):
    print(i, D.describe_line(r,'ability_soul'))
    print('   ',{j:v for j,v in enumerate(r) if v not in ('','(None)')})
