exec(open('probe_old.py',encoding='utf8').read().split('dirs=')[0])
PL=r"D:/WF/startpoint-cn-kulo/tools/fantasy-gauntlet-mod-tools/WF_PATHLIST_recovered.txt"
parts=[l.strip() for l in open(PL,encoding='utf8') if l.startswith('battle/effect/') and l.strip().endswith('.parts.amf3.deflate')]
mt=[];ms=[];mk=[]
for p in parts:
    try: t,_=amf(p)
    except Exception: continue
    mt.append((len(t['t']),p)); ms.append((max(len(g['s']) for g in t['g']),p)); mk.append((sum(len(s['l']) for g in t['g'] for s in g['s']),p))
for L in (mt,ms,mk):
    L.sort(); print(len(L), L[len(L)//2][0], L[int(len(L)*.9)][0], L[-3:])
