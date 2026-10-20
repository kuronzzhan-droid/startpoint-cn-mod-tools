import os,sys,json
os.environ["WF_TIP"]="200"
from live149 import *
import wf_dsl
from dsltools import commands, get, walk
def outline(n, depth=0, path=()):
    # print command tree outline
    if isinstance(n, list) and len(n)==2 and n[0]=='Command' and isinstance(n[1],list) and n[1] and isinstance(n[1][0],str):
        c=n[1]; nm=c[0]
        extra=''
        if nm=='CreateCondition': extra=json.dumps([c[1]]+[[a[0]]+a[1:] for a in c[2]][:6]+c[3:],ensure_ascii=False)[:420]
        elif nm.startswith('Conditionals') or nm.startswith('Target') or nm.startswith('Find'): extra=json.dumps(c[1:],ensure_ascii=False)[:200]
        elif nm in ('CreateNormalAttack','CreateRatioAttack','CreateHitArea'): extra=json.dumps(c[1:],ensure_ascii=False)[:300]
        print('  '*depth+f'{path} {nm} {extra}')
        for i,x in enumerate(c[1:],1):
            if isinstance(x,list): sub(x,depth+1,path+(1,i))
        return
    sub(n,depth,path)
def sub(n,depth,path):
    if isinstance(n,list):
        for i,x in enumerate(n): 
            if isinstance(x,list): outline(x,depth,path+(i,))
for lv in sys.argv[1:]:
    p=f"battle/action/skill/action/rare5/ginovi$ginovi_{lv}"
    print('=====',p,source(wf_dsl.dsl_logical(p)))
    outline(dsl_tree(p))
