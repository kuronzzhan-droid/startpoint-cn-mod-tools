import os,sys,json
os.environ["WF_TIP"]="196"
from live149 import *
U=load("master/character/unique_condition.orderedmap")
print(U.get("1499990"))
for k,v in U.items():
    if "gerald" in str(v): print("U",k,v)
AS=load("master/skill/action_skill.orderedmap")
for k,v in AS.items():
    if "land_dragon_wind" in str(v): print(k, str(v)[:900])
