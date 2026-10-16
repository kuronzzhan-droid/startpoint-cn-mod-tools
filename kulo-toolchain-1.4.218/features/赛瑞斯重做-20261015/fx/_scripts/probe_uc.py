import os,sys
os.chdir(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build"); sys.path.insert(0,os.getcwd())
from live149 import *
U=load("master/character/unique_condition.orderedmap")
print(repr(U["22"])); 
for k in list(U)[:3]: print(k,repr(U[k])[:200])
print(len(U), [k for k in U if 'ginovi' in U[k] or 'seris' in U[k]])
