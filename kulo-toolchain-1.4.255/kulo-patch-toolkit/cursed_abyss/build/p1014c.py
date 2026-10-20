import os,sys,json
os.environ["WF_TIP"]="197"
from live149 import *
from dsltools import commands
p="battle/action/skill/action/ability_skill/ability_skill_lion_swordman_moon_ignite$ability_skill_lion_swordman_moon_ignite"
t=dsl_tree(p); print(source(__import__('wf_dsl').dsl_logical(p)))
for pp,c in commands(t):
    if c[0] not in ('ShowEffect','HideEffect','RemoveEvent','ShakeCamera'): print(pp, json.dumps(c,ensure_ascii=False)[:700])
