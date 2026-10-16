import os,sys
os.environ["WF_TIP"]="196"
from live149 import *
import glob
pats=sys.argv[1:]
for lp in ["master/string/custom_ability_string.orderedmap","master/string/ability_string.orderedmap","master/string/ability_description.orderedmap","master/string/ability_text.orderedmap"]:
    try: t=load(lp)
    except Exception as e: print(lp,"ERR",type(e).__name__); continue
    print(lp,len(t))
    for k,v in t.items():
        s=str(v)
        if any(p in s for p in pats): print(" ",k,s[:200].replace("\n"," | "))
