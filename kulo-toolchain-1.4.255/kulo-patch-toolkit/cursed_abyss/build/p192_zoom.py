import sys
from p192_common import *
from PIL import ImageDraw
boxes = {0:(430,20,690,240),1:(540,100,760,320),2:(450,60,690,260),3:(420,80,720,320)}
for i,(f,cid,code,s) in enumerate(SLOTS):
    x0,y0,x1,y1 = boxes[i]
    m = Image.open(MASTERS/f).convert("RGBA").crop(boxes[i])
    k=4; m = m.resize((m.width*k, m.height*k), Image.Resampling.LANCZOS)
    bg = Image.new("RGBA", m.size, (128,128,128,255)); bg.alpha_composite(m); d=ImageDraw.Draw(bg)
    for y in range((y0//10+1)*10, y1, 10):
        d.line([(0,(y-y0)*k),(bg.width,(y-y0)*k)], fill=(255,0,0,255) if y%50==0 else (255,120,120,110), width=1)
        if y%50==0: d.text((2,(y-y0)*k+2), str(y), fill=(255,255,0,255))
    for x in range((x0//10+1)*10, x1, 10):
        d.line([((x-x0)*k,0),((x-x0)*k,bg.height)], fill=(0,0,255,255) if x%50==0 else (120,120,255,110), width=1)
        if x%50==0: d.text(((x-x0)*k+2,2), str(x), fill=(0,255,255,255))
    bg.convert("RGB").save(ART/"inspect"/f"zoom_{i}.jpg", quality=90)
