import os,sys,json
os.environ["WF_TIP"]="197"
from live149 import *
TX=load('master/character/character_text.orderedmap'); C=load('master/character/character.orderedmap')
for k,v in TX.items():
    if '机车' in v or '狮王' in v or 'lion' in row(C.get(k,'x'))[0]: print(k,row(C[k])[0], v[:60].replace('\n',' '), '|', [x for x in row(v)][5:8])
CAS=load('master/string/custom_ability_string.orderedmap')
for k,v in CAS.items():
    if 'lion_swordman' in k: print('CAS',k,v[:300].replace('\n',' || '))
