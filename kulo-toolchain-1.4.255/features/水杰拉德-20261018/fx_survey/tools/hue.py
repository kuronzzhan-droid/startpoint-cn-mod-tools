import json, colorsys
import numpy as np
import wfio, fxlib
d=json.load(open('fx_index.json',encoding='utf-8'))
import classify
E={e['path']:e for e in d['effects']}
out={}
cache={}
def regs(dp):
    if dp not in cache:
        nm=dp.split('/')[-1]
        a,_=wfio.load_amf(f"{dp}/{nm}.atlas"); png,_=wfio.load_png(f"{dp}/{nm}.png")
        cache[dp]=(a,png)
    return cache[dp]
T=json.load(open('tiers2.json'))
for p in sorted(set(classify.L)|set(T)):
    e=E[p]; parts,_=wfio.load_amf(p+'.parts')
    names=set(im['p'] for im in parts['i'])
    area=0; pix=[]
    for dp in e['atlas_dirs']:
        a,png=regs(dp)
        arr=np.asarray(png,np.float32)
        for r in a:
            if r['n'] in names:
                area+=(r['w']+2)*(r['h']+2)
                sub=arr[r['y']:r['y']+r['h'], r['x']:r['x']+r['w']].reshape(-1,4)
                sub=sub[sub[:,3]>64]
                if len(sub)>4000: sub=sub[::len(sub)//4000]
                pix.append(sub)
    if pix:
        P=np.concatenate(pix)
        rgb=P[:,:3]/255.0
        mx=rgb.max(1); mn=rgb.min(1); sat=(mx-mn)/(mx+1e-6)
        colorful=sat>0.25
        frac_col=float(colorful.mean())
        if colorful.any():
            hs=[colorsys.rgb_to_hsv(*c)[0] for c in rgb[colorful][::max(1,colorful.sum()//1500)]]
            ang=np.array(hs)*2*np.pi
            hue=(np.degrees(np.arctan2(np.sin(ang).mean(),np.cos(ang).mean()))%360)
        else: hue=None
        lum=float(mx.mean())
    else:
        frac_col=0; hue=None; lum=0
    out[p]={'used_area':area,'colorful_frac':round(frac_col,2),'hue':None if hue is None else round(float(hue)),'lum':round(lum,2)}
json.dump(out,open('hue.json','w'))
S='battle/effect/skill_unique/'
for k in ['drawing_witch/drawing_witch_all','vesta_caster/vesta_caster_all','luca_playable/luca_playable_ripple','ruin_lady_meteor23/ruin_lady_meteor23_beam','student_president/student_president_all','holy_mother/holy_mother_all','navy_officer/navy_officer_wave','summoner_little_smr23/summoner_little_smr23_all','aqua/aqua_all']:
    print(k,out[S+k])
