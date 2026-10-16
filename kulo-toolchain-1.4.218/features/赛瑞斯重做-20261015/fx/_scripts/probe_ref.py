exec(open('probe_old.py',encoding='utf8').read().split('dirs=')[0])
import sys
for lp in sys.argv[1:]:
    t,src=amf(lp+".parts.amf3.deflate")
    print(lp,src,"keys",list(t.keys()),"i",len(t['i']),"t",len(t['t']),"a",t['a'][:12],"s",t['s'],"m",t['m'][:3],"o",t['o'][:3],"c",t['c'][:2])
    for gi,g in enumerate(t['g'][:4]):
        print(" g",gi,"t",g['t'],"nseg",len(g['s']))
        for s in g["s"][:6]: print("   seg s=%d kind=%d i=%s nl=%d l0=%s"%(int(s["s"])&0x3fffffff,int(s["s"])>>30,s['i'],len(s['l']),s['l'][:3]), {k:v for k,v in s.items() if k not in('s','i','l')})
    tl,_=amf(lp+".timeline.amf3.deflate"); print(" timeline",json.dumps(tl,ensure_ascii=False)[:400])
