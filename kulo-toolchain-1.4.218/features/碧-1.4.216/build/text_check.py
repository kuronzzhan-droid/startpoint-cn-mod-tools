import os, json, csv
os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/碧-1.4.216/patch-test-212"
import env; env.setup(213)
from base149 import *
st=load("master/skill/action_skill.orderedmap").get("cnmod_vyrn_dark")
print("action_skill", source("master/skill/action_skill.orderedmap"), {k:next(csv.reader([v]))[:2] for k,v in (st or {}).items()})
txt=load("master/character/character_text.orderedmap").get("169978"); print("client character_text", str(txt)[:300])
srv=json.load(open("k_cdn_text.json",encoding="utf-8"))["169978"][0]; print("server",srv[:6])
