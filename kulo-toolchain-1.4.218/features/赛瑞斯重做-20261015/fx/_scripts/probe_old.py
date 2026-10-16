import os,sys,json,zlib,io
os.chdir(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build"); sys.path.insert(0,os.getcwd())
from live149 import *
import wf_dsl
from PIL import Image
def amf(lp):
    raw,src=read_raw(lp)
    for b in (raw,raw[4:]):
        for w in (-15,15):
            try: return wf_dsl.parse_dsl(zlib.decompress(b,w))['tree'],src
            except Exception: pass
    raise
def png(lp):
    raw,src=read_raw(lp); raw=bytearray(raw); raw[1:4]=b'PNG'; return Image.open(io.BytesIO(bytes(raw))),src
dirs={"battle/effect/skill_unique/seris_human_royal_tide_ring":["seris_human_royal_tide_ring"],
"battle/effect/skill_unique/seris_dragon_flight":["seris_dragon_flight"],
"battle/effect/skill_unique/seris_dragon_frozen_thunder_breath":["seris_dragon_frozen_thunder_breath"],
"battle/effect/skill_unique/seris_dragon_king":["seris_dragon_king"],
"battle/uncommon/layer1/seris_dragon_king":["seris_dragon_king_transform"]}
for d,names in dirs.items():
    dn=d.split('/')[-1]
    try:
        im,src=png(f"{d}/{dn}.png"); print(d,"PNG",im.size,im.mode,src)
    except Exception as e: print(d,"PNG miss",e)
    try:
        at,src=amf(f"{d}/{dn}.atlas.amf3.deflate"); 
        nm=sorted({a['n'].split('/.gen/')[-1].split('/')[0] for a in at}); print("  atlas",len(at),"groups",nm[:20])
        mx=max(a['x']+a['w'] for a in at); my=max(a['y']+a['h'] for a in at); print("  used",mx,my, "area",sum(a['w']*a['h'] for a in at))
    except Exception as e: print("  atlas miss",e)
    for n in names:
        for ext in ("parts","timeline"):
            try:
                t,src=amf(f"{d}/{n}.{ext}.amf3.deflate"); print("  ",n,ext,src, json.dumps(t)[:300] if ext=="timeline" else ("g",len(t['g']),"i",len(t['i']),"t",len(t['t']),'a',t['a'][:5],'s',t['s']))
            except Exception as e: print("  ",n,ext,"miss",e)
