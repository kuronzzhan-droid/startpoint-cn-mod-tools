import json
from PIL import Image
A={e['n'].split('/')[-1]:e for e in json.load(open('atlas.json'))}; SHEET=Image.open('sheet.png').convert('RGBA')
def crop(n):
    e=A[n]; return SHEET.crop((e['x'],e['y'],e['x']+e['w'],e['y']+e['h']))
GOLD_HI,GOLD,GOLD_SH=(255,232,140,255),(236,180,62,255),(170,104,34,255)
GEM_HI,GEM=(255,246,200,255),(255,150,40,255)
def outline(p): return p[3]>0 and p[:3]==(0,0,0)
def neighbors(im,x,y):
    w,h=im.size
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
        if 0<=x+dx<w and 0<=y+dy<h: yield im.getpixel((x+dx,y+dy))
        else: yield (0,0,0,0)
def lum(p): return 0.3*p[0]+0.59*p[1]+0.11*p[2]
def gold_trim(src, top_rows, bot_rows):
    im=src.copy(); w,h=im.size
    for y in range(h):
        for x in range(w):
            p=src.getpixel((x,y))
            if p[3]==0 or outline(p): continue
            if any(outline(q) or q[3]==0 for q in neighbors(src,x,y)):
                if y in top_rows: im.putpixel((x,y), GOLD_HI if y<=3 else GOLD)
                elif y in bot_rows: im.putpixel((x,y), GOLD if y<h-4 else GOLD_SH)
    return im
def gems(im, pts):
    for (x,y) in pts:
        im.putpixel((x,y),GEM); im.putpixel((x,y-1),GEM_HI)
    return im
def darken_body(src, rows, tint=(70,22,18)):
    im=src.copy(); w,h=im.size
    for y in rows:
        for x in range(w):
            p=im.getpixel((x,y))
            if p[3]==0 or outline(p) or p in (GOLD,GOLD_HI,GOLD_SH): continue
            k=lum(p)/255
            im.putpixel((x,y),(int(tint[0]+k*90),int(tint[1]+k*30),int(tint[2]+k*24),255))
    return im
def lava(im, pts):
    for (x,y) in pts: im.putpixel((x,y),(255,120,30,255))
    return im
full=crop('red_5'); half=crop('red_5_half')
c1=gems(gold_trim(full, range(0,11), range(14,24)), [(8,13),(16,13)])
c2=lava(darken_body(gold_trim(full, range(0,11), range(14,24)), range(9,16)), [(6,12),(7,13),(12,14),(13,13),(18,12),(17,13)])
c2=gems(c2,[(12,11)])
h1=gold_trim(half, range(0,11), range(12,18))
h2=darken_body(h1, range(9,15))
out=[('官方red_5',full),('A 金边+火晶',c1),('B 金边+熔岩身',c2),('官方half',half),('A half',h1),('B half',h2)]
S=10; W=sum(i.size[0]*S+20 for _,i in out)
canvas=Image.new('RGBA',(W,24*S+20),(245,245,245,255)); x=10
for n,i in out:
    canvas.paste(i.resize((i.size[0]*S,i.size[1]*S),Image.NEAREST),(x,10),i.resize((i.size[0]*S,i.size[1]*S),Image.NEAREST)); x+=i.size[0]*S+20
canvas.save('cand_red_v1.png'); c1.save('A_red_6.png'); c2.save('B_red_6.png'); h1.save('A_red_6_half.png'); h2.save('B_red_6_half.png')
