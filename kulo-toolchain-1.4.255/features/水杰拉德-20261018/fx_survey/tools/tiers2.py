import json,collections
import meta
d=json.load(open('fx_index.json',encoding='utf-8')); ink=json.load(open('ink.json',encoding='utf-8'))
E={e['path']:e for e in d['effects']}; chars=d['chars']; names=meta.load_names(); dsl2skill=d['dsl2skill']
FW,FH=1080,1920
T={}
for p,v in ink.items():
    if '/powerflip/' in p: continue
    b=v['best']; b2=v['best_nodim']; e=E[p]
    if b2['cov']>=0.55 or (b2['area']>=0.55 and b2['ink_w']>=0.9*FW and b2['ink_h']>=0.6*FH): t='A'
    elif b2['cov']>=0.30 or b2['area']>=0.35: t='B'
    elif b['cov']>=0.5 and b2['cov']<0.3: t='D'
    elif b2['ink_w']>=0.85*FW and b2['ink_h']>=0.6*FH: t='E'
    elif b2['ink_w']>=0.9*FW or b2['ink_h']>=0.75*FH: t='C'
    else: continue
    T[p]=t
print(collections.Counter(T.values()))
json.dump(T,open('tiers2.json','w'),indent=0)
out=[]
for p,t in sorted(T.items(), key=lambda kv:(kv[1],kv[0])):
    e=E[p]; v=ink[p]; us=e['usage']
    ch=us[0]['char'] if us else p.split('/')[3]
    c=chars.get(ch,{}); nm=names.get(c.get('id',''),{}).get('name','')
    sk=dsl2skill.get(us[0]['dsl'],[{}])[0] if us else {}
    lbl=sorted(set(u['name'] for u in us))[:3]
    out.append(f"{t} {p.replace('battle/effect/','')} | {ch} {nm} r{c.get('rarity')} e{c.get('element')} {c.get('role')} | cov{v['best_nodim']['cov']:.2f}/{v['best']['cov']:.2f} a{v['best_nodim']['area']:.2f} ink{v['best_nodim']['ink_w']:.0f}x{v['best_nodim']['ink_h']:.0f} | {e['frames']}f s{v['scale']} subj{sorted(set(u['subject'] for u in us))} {sorted(set(u['layer'] for u in us))} | lbl{lbl} | {sk.get('icon','').replace('dynamic/skill/','')}")
open('tiers2.txt','w',encoding='utf-8').write('\n'.join(out))
