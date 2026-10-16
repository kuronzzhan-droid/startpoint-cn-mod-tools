import os,sys,json,re
os.chdir(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build"); sys.path.insert(0,os.getcwd())
from live149 import *
PFO="battle/action/power_flip/action/override/"
ps=["battle/action/skill/seris_dragon_king/seris_dragon_king","battle/action/skill/seris_dragon_king/seris_dragon_king_2","battle/action/skill/seris_dragon_king/seris_dragon_king_matched","battle/action/skill/seris_dragon_king/seris_dragon_king_matched_2"]
for k in ("override_seris_human_powerflip","override_seris_dragon_special"):
    for lv in (1,2,3): ps.append(f"{PFO}{k}${k}_lv{lv}")
allp=set()
for p in ps:
    try: t=dsl_tree(p)
    except Exception as e: print(p,"ERR",e); continue
    s=json.dumps(t,ensure_ascii=False)
    refs=sorted(set(re.findall(r'"(battle/(?:effect|uncommon)[^"]+)"',s)))
    print(p.split('/')[-1],refs); allp|=set(refs)
print(sorted(allp))
