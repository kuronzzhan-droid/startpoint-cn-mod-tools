import os,sys,json
os.environ["WF_TIP"]="197"
from live149 import *
from dsltools import commands, summary
ps=["battle/action/skill/action/rare5/lion_swordman_moon$lion_swordman_moon_1","battle/action/skill/action/rare5/lion_swordman_moon$lion_swordman_moon_2"]
ps+=[f"battle/action/power_flip/action/override/lion_swordman_moon_pf$lion_swordman_moon_pf_lv{n}" for n in (1,2,3)]
ps+=[f"battle/action/skill/action/ability_skill/lion_swordman_moon_pf_skill$lion_swordman_moon_pf_skill_lv{n}" for n in (1,2,3)]
ps+=["battle/action/skill/action/ability_skill/ability_skill_kyle_moon_direct_params$ability_skill_kyle_moon_direct_params"]
for p in ps:
    print("=====",p, source(__import__('wf_dsl').dsl_logical(p)))
    try: t=dsl_tree(p)
    except Exception as e: print("ERR",e); continue
    names={}
    for pp,c in commands(t): names[c[0]]=names.get(c[0],0)+1
    print(names)
    for pp,c in commands(t):
        if c[0] in ('CreateNormalAttack','CreateRatioAttack'): print(pp[-3:], c[0], json.dumps(c[1:9],ensure_ascii=False)[:300])
        if c[0]=='CreateCondition': print(pp[-3:], 'CC', json.dumps(c[1:],ensure_ascii=False)[:500])
