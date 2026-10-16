import os, sys
os.environ["WF_TIP"]="195"
from live149 import *
C = load('master/character/character.orderedmap'); TX = load('master/character/character_text.orderedmap')
CAS = load('master/string/custom_ability_string.orderedmap')
for k,v in TX.items():
    s = str(v)
    for w in ("水灵幽魂","送葬","克劳斯","狩夜","拉夫马诺","见岛","豹","魔王","杰拉德","澄波","索恩"):
        if w in s:
            r=rows(v)[0] if isinstance(v,str) else None
            print(w, k, row(C[k])[0] if k in C else '?', (r[:3] if r else str(v)[:80]))
for k,v in CAS.items():
    s=str(v)
    if "豹步" in s or "骰运" in s or "冻结" in s and "水属性" in s: print('CAS',k,s[:300].replace('\n','|'))
