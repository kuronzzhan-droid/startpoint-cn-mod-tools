exec(open('probe_old.py',encoding='utf8').read().split('dirs=')[0])
PL=r"D:/WF/startpoint-cn-kulo/tools/fantasy-gauntlet-mod-tools/WF_PATHLIST_recovered.txt"
tls=[l.strip() for l in open(PL,encoding='utf8') if l.startswith('battle/effect/') and l.strip().endswith('.timeline.amf3.deflate')]
from collections import defaultdict
se=defaultdict(list)
for p in tls:
    try: t,_=amf(p)
    except Exception: continue
    for s in t.get('sounds',[]): se[s['path']].append((p.split('/')[-1][:-22],s))
import re
for k in sorted(se):
    if re.search(r'water|wave|splash|aqua|thunder|lightning|elec|tide|sea|ocean|dragon|roar|breath',k):
        print(len(se[k]),k,se[k][0])
print(len(se))
