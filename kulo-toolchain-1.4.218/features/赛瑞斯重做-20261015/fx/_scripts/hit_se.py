exec(open('probe_old.py',encoding='utf8').read().split('dirs=')[0])
PL=r"D:/WF/startpoint-cn-kulo/tools/fantasy-gauntlet-mod-tools/WF_PATHLIST_recovered.txt"
for l in open(PL,encoding='utf8'):
    l=l.strip()
    if l.startswith('battle/effect/hit/') and 'water' in l and l.endswith('.timeline.amf3.deflate'):
        t,_=amf(l); print(l.split('/')[-1], [(s['path'].split('/')[-1],s['begin']) for s in t['sounds']])
