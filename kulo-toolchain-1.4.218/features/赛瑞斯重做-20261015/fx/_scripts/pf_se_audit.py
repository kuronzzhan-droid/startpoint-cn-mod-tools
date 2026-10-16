exec(open('probe_old.py',encoding='utf8').read().split('dirs=')[0])
import re,json
from collections import Counter
SRC=r"D:/WF/out/赛瑞斯重做-20261015/build/pf_src/"
def walk(st,acc,depth=0,ctx=""):
    for s in st:
        if isinstance(s,list) and len(s)==2 and s[0] in("Command","Event"):
            c=s[1]; acc.append((c[0],c,ctx))
            for x in c[1:]:
                if isinstance(x,list) and len(x)==2 and x[0]=="Block": walk(x[1],acc,depth+1,ctx+"/"+c[0])
names=Counter()
for t in ("knight","fighter","ranged","supporter","special"):
    for lv in (1,2,3):
        tr=json.load(open(SRC+f"{t}_lv{lv}.json",encoding='utf8'))
        acc=[]; walk(tr[11][1],acc)
        for n,c,ctx in acc: names[n]+=1
        effs=[(c[2][1],c[5],ctx.count('/')) for n,c,ctx in acc if n=="ShowEffect"]
        snds=[c for n,c,ctx in acc if 'Sound' in n or 'Se' == n[:2]]
        print(f"== {t} lv{lv} ShowEffect×{len(effs)} soundcmds×{len(snds)}")
        seen={}
        for p,life,d in effs:
            seen[p]=seen.get(p,0)+1
        for p,k in seen.items():
            try:
                tl,_=amf(p+".timeline.amf3.deflate"); s=[(x['path'].split('/')[-1],x['begin']) for x in tl['sounds']]
                seq=[(q['name'],q['begin'],q['end']) for q in tl['sequences']]
            except Exception as e: s=f"ERR {e}"; seq=None
            print(f"   x{k} {p}  sounds={s} seqs={seq}")
print(sorted(names.items()))
