import os,sys,json
os.environ["WF_TIP"]="197"
from live149 import *
AS=load('master/skill/action_skill.orderedmap')
print(len(AS), list(AS.items())[0])
def find(o, path=''):
    if isinstance(o, dict):
        for k,v in o.items(): yield from find(v, path+'/'+str(k))
    elif isinstance(o,str):
        if 'lion_swordman_moon' in o or 'land_dragon_wind_playable' in o: yield path, o[:300]
for p,s in find(AS): print(p, s.replace('\n',' | '))
