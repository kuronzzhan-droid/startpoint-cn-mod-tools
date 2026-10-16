exec(open('probe_old.py',encoding='utf8').read().split('dirs=')[0])
import sys
lp=sys.argv[1]; gis=[int(x) for x in sys.argv[2:]]
t,_=amf(lp+'.parts.amf3.deflate'); print("ng",len(t['g']),"a",t['a'],'s',t['s'],'i0',t['i'][:2])
for gi in gis:
    g=t['g'][gi]; print("g",gi,"t",g['t'])
    for s in g['s']:
        print("  s=%d k=%d i=%d"%(int(s['s'])&0x3fffffff,(int(s['s'])>>30)&3,s['i']), s['l'][:4], len(s['l']))
tl,_=amf(lp+'.timeline.amf3.deflate'); print(tl['sequences'])
