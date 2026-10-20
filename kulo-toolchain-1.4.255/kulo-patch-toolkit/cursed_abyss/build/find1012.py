import os,sys
os.environ["WF_TIP"]="196"
from live149 import *
C = load('master/character/character.orderedmap'); TX = load('master/character/character_text.orderedmap')
for k,v in TX.items():
    s=str(v)
    if any(n in s for n in ("夏琳","碧安卡","墨斯伊克","九尾","稻穗","斩铁","巨蜥","白虎")):
        code=row(C[k])[0] if k in C else None
        print(k, code, s[:100].replace('\n',' | '))
