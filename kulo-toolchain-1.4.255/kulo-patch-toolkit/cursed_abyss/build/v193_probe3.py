# -*- coding: utf-8 -*-
import os; os.environ["WF_TIP"]="192"
import sys; sys.path.insert(0, r"D:/WF/startpoint-cn-wiki/mod-tools")
from p192_common import *
names=["ally/join","ally/evolution"]+[f"home/home_{i}" for i in range(20)]
for fam in ["battle_start","outhole","power_flip","skill","win","skill_ready","skill_ready_alt","matched_skill_ready","matched_skill"]:
    names+= [f"battle/{fam}_{i}" for i in range(16)]
names+=["battle/skill_ready","battle/matched_skill_ready"]
for code in ("white_wolf_gerald","maou2_playable","maou","unicorn_lancer_rose"):
    hits=[]
    for n in names:
        lp=f"character/{code}/voice/{n}.mp3"
        rs=[(r,aread(r,lp)[1]) for r in ROOTS if aread(r,lp)[0] is not None]
        if rs: hits.append((n,rs))
    print("==",code,len(hits))
    for h in hits: print("  ",h)
