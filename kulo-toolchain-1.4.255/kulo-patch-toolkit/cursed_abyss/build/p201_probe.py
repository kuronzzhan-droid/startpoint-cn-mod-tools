import os,sys,json
os.environ["WF_TIP"]="200"
from live149 import *
AS=load('master/skill/action_skill.orderedmap')
for lv,v in AS['ginovi'].items(): print('AS',lv,repr(v)[:1500])
TX=load('master/character/character_text.orderedmap')
print('TX',repr(TX['169999']))
for lp in ('master/ability/ability.orderedmap','master/string/custom_ability_string.orderedmap','master/ability/leader_ability.orderedmap'):
    T=load(lp)
    for k,v in T.items():
        s=json.dumps(v,ensure_ascii=False)
        if '掠影' in s or 'ginovi' in k or '169999' in k: print(lp,k,s[:3000]); print(source(lp))
