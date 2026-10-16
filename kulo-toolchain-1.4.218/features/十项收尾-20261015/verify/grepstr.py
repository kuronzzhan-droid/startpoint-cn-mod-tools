import os,sys
sys.path.insert(0,r'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build'); os.chdir(r'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build')
from live149 import *
for lp in ('master/string/ui_string.orderedmap','master/string/ability_string.orderedmap'):
    try: T=load(lp)
    except Exception as e: print(lp,'ERR',e); continue
    for k,v in T.items():
        s=str(v)
        if sys.argv[1] in s or sys.argv[1] in k: print(lp,k,s[:160])
