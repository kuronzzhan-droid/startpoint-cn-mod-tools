import os
os.environ["WF_TIP"]="197"
from live149 import *
for lp in ('master/string/custom_ability_string.orderedmap','master/character/character_text.orderedmap'):
    T=load(lp)
    for k,v in T.items():
        s=str(v)
        if '烈狱' in s or ('lion_swordman_reborn' in k): print(lp,k,s[:300].replace('\n',' || '))
