exec(open('probe_old.py',encoding='utf8').read().split('dirs=')[0])
import re
PL=r"D:/WF/startpoint-cn-kulo/tools/fantasy-gauntlet-mod-tools/WF_PATHLIST_recovered.txt"
parts=[l.strip()[:-len('.parts.amf3.deflate')] for l in open(PL,encoding='utf8') if l.strip().startswith('battle/effect/skill_unique/') and l.strip().endswith('.parts.amf3.deflate')]
n=ov=0; ex=[]
for p in parts[:400]:
    try: t,_=amf(p+'.parts.amf3.deflate')
    except Exception: continue
    n+=1
    for gi,g in enumerate(t['g']):
        segs=[(int(s['s'])&0x3fffffff, (int(s['s'])>>30)&3, sum(int(k.get('t',1))&0xffff for k in s['l'])) for s in g['s']]
        img=[(a,a+d) for a,k,d in segs if k==0]
        hit=any(img[i][0]<img[j][1] and img[j][0]<img[i][1] for i in range(len(img)) for j in range(i+1,len(img)))
        if hit:
            ov+=1; ex.append((p,gi)); break
print(n,ov,ex[:8])
