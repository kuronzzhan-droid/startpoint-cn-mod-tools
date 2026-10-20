import os, sys, json
os.environ["WF_TIP"]="195"
from live149 import *
from dsltools import commands
AB = load('master/ability/ability.orderedmap'); LE = load('master/ability/leader_ability.orderedmap')
CAS = load('master/string/custom_ability_string.orderedmap')
def show(tb, k):
    T = AB if tb=='a' else LE
    for i,r in enumerate([x for x in rows(T[k]) if x]):
        print(tb,k,i, {j:v for j,v in enumerate(r) if v not in ('',)})
for a in sys.argv[1:]:
    tb,k=a.split(':'); show(tb,k)
