exec(open('probe_old.py',encoding='utf8').read().split('dirs=')[0])
PL=r"D:/WF/startpoint-cn-kulo/tools/fantasy-gauntlet-mod-tools/WF_PATHLIST_recovered.txt"
L=[l.strip() for l in open(PL,encoding='utf8')]
for d in ["effect_powerflip_attack_spin","effect_powerflip_attack_fight","effect_powerflip_attack_beam","effect_powerflip_attack_support","effect_powerflip_attack_special"]:
    D="battle/effect/powerflip/"+d
    fs=[l[len(D)+1:] for l in L if l.startswith(D+"/")]
    im,_=png(f"{D}/{d}.png"); at,_=amf(f"{D}/{d}.atlas.amf3.deflate")
    keys=set(k for a in at for k in a); rot=sum(1 for a in at if a.get('r'))
    print(d, im.size, (im.width+2)*(im.height+2), "atlas",len(at),"keys",sorted(keys),"rot",rot)
    print("   files:",fs)
    for f in fs:
        if f.endswith('.parts.amf3.deflate'):
            t,_=amf(f"{D}/{f}")
            bad=[i for i in t['i'] if not i['p'].startswith(D+"/.gen/")]
            kinds=set((int(s['s'])>>30)&3 for g in t['g'] for s in g['s'])
            print("     ",f, "i",len(t['i']),"ext",bad[:2],"kinds",kinds, "is",set(i['s'] for i in t['i']))
