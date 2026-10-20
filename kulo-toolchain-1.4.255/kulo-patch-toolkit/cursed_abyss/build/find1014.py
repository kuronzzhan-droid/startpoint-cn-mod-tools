import os,sys
os.environ["WF_TIP"]="197"
from live149 import *
C=load('master/character/character.orderedmap'); TX=load('master/character/character_text.orderedmap')
for k,v in C.items():
    r=row(v)
    t=TX.get(k,'')
    if 'kyle' in r[0] or '玛格诺斯' in t or 'magnus' in r[0].lower() or k in('139991','149998','119999','139990'):
        print(k, r[0], r[18], t[:80].replace('\n',' '))
