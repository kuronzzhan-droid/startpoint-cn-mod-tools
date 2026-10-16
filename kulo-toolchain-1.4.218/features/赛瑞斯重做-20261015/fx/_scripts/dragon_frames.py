import sys,zlib,io,json
sys.path.insert(0,r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
import os; os.chdir(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
from live149 import *
import wf_dsl
from PIL import Image
P=r"D:/WF/out/赛瑞斯重做-20261015/pixel/final_USER_DB/game/character/seris_dragon_king/pixelart/"
at=wf_dsl.parse_dsl(zlib.decompress(open(P+"special_sprite_sheet.atlas.amf3.deflate",'rb').read(),-15))['tree']
im=Image.open(r"D:/WF/out/赛瑞斯重做-20261015/fx/_scripts/dragon_special.png")
# unique rects with frame numbers
seen={}; 
for a in at:
    k=(a['x'],a['y'],a['w'],a['h'],a.get('r',False))
    seen.setdefault(k,[]).append(int(a['n'][-4:]))
print(len(seen))
tiles=[]
for k,fr in seen.items():
    x,y,w,h,r=k; c=im.crop((x,y,x+w,y+h))
    if r: c=c.rotate(90,expand=True)
    tiles.append((min(fr),max(fr),c))
tiles.sort()
W=Image.new('RGBA',(1400,900),(30,30,40,255)); X=Y=0; RH=0
from PIL import ImageDraw
d=ImageDraw.Draw(W)
for lo,hi,c in tiles:
    c2=c.resize((c.width*3,c.height*3),Image.NEAREST)
    if X+c2.width>1400: X=0; Y+=RH+14; RH=0
    W.alpha_composite(c2,(X,Y+12)); d.text((X,Y),f"{lo}-{hi}",fill=(255,255,0,255)); X+=c2.width+8; RH=max(RH,c2.height)
W.save(r"D:/WF/out/赛瑞斯重做-20261015/fx/_scripts/dragon_tiles.png")
sel=[t for t in tiles if t[0] in (1,8,14,26,38,50,62,110,122,152,163)]
W=Image.new('RGBA',(len(sel)*130,150),(30,30,40,255)); d=ImageDraw.Draw(W)
for i,(lo,hi,c) in enumerate(sel):
    W.alpha_composite(c.resize((c.width*5,c.height*5),Image.NEAREST),(i*130,20)); d.text((i*130,2),f"{lo} {c.size}",fill=(255,255,0,255))
W.save(r"D:/WF/out/赛瑞斯重做-20261015/fx/_scripts/dragon_small.png")
