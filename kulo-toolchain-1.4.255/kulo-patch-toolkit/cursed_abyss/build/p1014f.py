import os,sys,json
os.environ["WF_TIP"]="197"
from live149 import *
import wf_dsl
from dsltools import commands
AS=load('master/skill/action_skill.orderedmap')
for k in ('lion_swordman_reborn',):
    for lv,v in AS[k].items(): print(lv, row(v)[7])
ps=[row(v)[7] for v in AS['lion_swordman_reborn'].values()]+[f"battle/action/power_flip/action/override/lion_swordman_reborn_pf$lion_swordman_reborn_pf_lv{n}" for n in (1,2,3)]
for p in ps:
    try: t=dsl_tree(p)
    except Exception as e: print(p,'ERR',e); continue
    print('=====',p,source(wf_dsl.dsl_logical(p)))
    for pp,c in commands(t):
        if c[0] in('CreateNormalAttack','CreateRatioAttack'): print(' ',c[0], json.dumps(c[1:8],ensure_ascii=False)[:250])
        if c[0]=='CreateCondition': print('  CC', json.dumps(c[1:],ensure_ascii=False)[:400])
