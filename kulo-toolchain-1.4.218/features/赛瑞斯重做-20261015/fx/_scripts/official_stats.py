exec(open('probe_old.py',encoding='utf8').read().split('dirs=')[0])
import re,statistics,json
PL=r"D:/WF/startpoint-cn-kulo/tools/fantasy-gauntlet-mod-tools/WF_PATHLIST_recovered.txt"
lines=[l.strip() for l in open(PL,encoding='utf8')]
dirs=set()
for l in lines:
    if l.startswith('battle/effect/') and ('.parts' in l or l.endswith('.png')):
        dirs.add(l.rsplit('/',1)[0])
res=[]
for d in sorted(dirs):
    dn=d.split('/')[-1]
    try: im,_=png(f"{d}/{dn}.png"); res.append((d.split('/')[2],d,im.size))
    except Exception: pass
out={}
for g in ("skill_unique","powerflip","ALL"):
    a=sorted((w+2)*(h+2) for gg,_,(w,h) in res if gg==g or g=="ALL")
    if not a: continue
    q=lambda p:a[min(len(a)-1,int(p*len(a)))]
    out[g]={"n":len(a),"median":statistics.median(a),"p90":q(0.9),"max":a[-1]}
    print(g,out[g])
big=sorted([r for r in res if r[0]=='skill_unique'],key=lambda r:-(r[2][0]*r[2][1]))[:6]; print(big)
json.dump({"stats":out,"sheets":[[g,l,s] for g,l,s in res]},open("official_stats.json","w"),ensure_ascii=False)
