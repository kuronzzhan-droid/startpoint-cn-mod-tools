import os,sys,json
os.environ["WF_TIP"]="196"
from live149 import *
U=load("master/character/unique_condition.orderedmap")
for k in ("1699950","129997","1499970","11998903"):
    print(k, U.get(k))
t=dsl_tree("battle/action/skill/action/ability_skill/ability_skill_gerald_time_rift$ability_skill_gerald_time_rift")
print(json.dumps(t,ensure_ascii=False)[:6000])
