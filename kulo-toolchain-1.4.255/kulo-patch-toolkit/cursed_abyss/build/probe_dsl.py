import os, sys, json
os.environ["WF_TIP"]=os.environ.get("WF_TIP","195")
from live149 import *
import wf_dsl
from dsltools import commands
for p in sys.argv[1:]:
    print("=====", p, source(wf_dsl.dsl_logical(p)))
    t = dsl_tree(p)
    for pp, c in commands(t):
        if c[0] in ("CreateNormalAttack","CreateCondition","CreateRatioAttack","FindAllSubjects","CreateHitArea","FindNearSubjects"):
            s = json.dumps(c, ensure_ascii=False)
            print(pp, s[:900])
