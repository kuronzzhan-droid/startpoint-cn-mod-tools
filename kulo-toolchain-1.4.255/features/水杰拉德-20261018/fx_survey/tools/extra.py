import json, collections
import wfio, fxlib
from multiprocessing import Pool
d=json.load(open('fx_index.json',encoding='utf-8')); T=json.load(open('tiers2.json'))
import classify
E={e['path']:e for e in d['effects']}
want=sorted(set(T)|set(classify.L))
_tex={}
def tex(e):
    t={}
    for dp in e['atlas_dirs']:
        if dp not in _tex:
            nm=dp.split('/')[-1]
            a,_=wfio.load_amf(f"{dp}/{nm}.atlas"); _tex[dp]=a
        for r in _tex[dp]:
            t[r['n']]=(r.get('fw',r['h'] if r.get('r') else r['w']), r.get('fh',r['w'] if r.get('r') else r['h']))
    return t
def work(p):
    e=E[p]; parts,_=wfio.load_amf(p+'.parts'); t=tex(e)
    sizes=[t.get(im['p'],(0,0)) for im in parts['i']]
    big=max(sizes,key=lambda s:s[0]*s[1]) if sizes else (0,0)
    nf=e['frames']; step=max(1,nf//30)
    pl=[len(fxlib.placements(parts,f)) for f in range(0,nf,step)]
    # max magnification of an image (matrix scale) * dsl scale
    mags=[]
    for f in range(0,nf,max(1,nf//10)):
        for comp,al,bl,ct,name in fxlib.placements(parts,f):
            a,b,c,dd,x,y=comp
            mags.append(max((a*a+b*b)**.5,(c*c+dd*dd)**.5))
    return p,{'img_sizes':sizes,'biggest':big,'avg_pl':round(sum(pl)/len(pl),1) if pl else 0,'max_pl':max(pl) if pl else 0,
              'mag_med':round(sorted(mags)[len(mags)//2],2) if mags else 0,'mag_max':round(max(mags),2) if mags else 0}
if __name__=='__main__':
    with Pool(20) as pool:
        res=dict(pool.map(work,want,chunksize=2))
    json.dump(res,open('extra.json','w'))
    print(len(res))
