import os,sys,json
os.chdir(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build"); sys.path.insert(0,os.getcwd())
from live149 import *
SK="battle/action/skill/seris_dragon_king/"
def walk(st,depth=0,out=None):
    for s in st:
        if isinstance(s,list) and len(s)==2 and s[0] in("Command","Event"):
            c=s[1]
            if c[0] in("ShowEffect","Wait","HideEffect","ShakeCamera","CreateNormalAttack","FindAllSubjects","CreateHitArea","CreateReferencePoint","ChangeFieldAssets"):
                if c[0]=="ShowEffect": print("  "*depth+json.dumps(c,ensure_ascii=False))
                elif c[0]=="CreateNormalAttack": print("  "*depth+"CNA elem",c[2],"mult",c[6])
                else: print("  "*depth+c[0]+" "+json.dumps([x for x in c[1:] if not (isinstance(x,list) and x and x[0]=="Block")],ensure_ascii=False)[:200])
            for x in c[1:]:
                if isinstance(x,list) and len(x)==2 and x[0]=="Block": walk(x[1],depth+1)
for p in sys.argv[1:]:
    print("=====",p); t=dsl_tree(p); print("root",t[:11]); walk(t[11][1])
