import os,sys
os.environ["WF_TIP"]="196"
from live149 import *
AB=load("master/ability/ability.orderedmap"); LE=load("master/ability/leader_ability.orderedmap")
U=load("master/character/unique_condition.orderedmap") if True else None
for spec in sys.argv[1:]:
    tb,key=spec.split(":")
    T=AB if tb=="a" else LE
    for i,r in enumerate([r for r in rows(T[key]) if r]):
        print(f"{spec}#{i}", " ".join(f"{c}={v}" for c,v in enumerate(r) if v not in ("",)))
    print()
