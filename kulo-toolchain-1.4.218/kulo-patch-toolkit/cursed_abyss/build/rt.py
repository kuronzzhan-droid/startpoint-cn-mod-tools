import os
os.environ["WF_TIP"]="196"
from live149 import *
for lp in ("master/ability/ability.orderedmap","master/ability/leader_ability.orderedmap","master/string/custom_ability_string.orderedmap","master/character/unique_condition.orderedmap"):
    raw,_=read_raw(lp); print(lp, q.build_node(q.parse_node(raw))==raw)
