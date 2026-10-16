from PIL import Image
import art
from palette import WATER
ims=[art.crest(phase=p) for p in range(3)]+[art.crest(big=True,seed=4)]+[art.spout(s) for s in range(4)]+[art.beam_tile(p) for p in range(3)]+[art.wing(),art.flash(),art.flash(col='red'),art.foam_ring(),art.ellipse_ring(),art.droplet(1),art.droplet(2),art.droplet(3),art.streak(),art.bolt(40,180,1),art.bolt(40,180,2,thick=2),art.spark(),art.unique_icon()]
for n in ['ring','splash']:
    im=Image.open(f'../_src/rd/{n}.png').convert('RGBA'); a=im.getchannel('A'); print(n,'alpha0 frac',sum(1 for v in a.getdata() if v==0)/a.width/a.height)
X=0; H=max(i.height for i in ims)*3+10
W=sum(i.width*3+8 for i in ims)
bg=Image.new('RGBA',(min(W,2400),(W//2400+1)*H),(14,16,26,255)); x=y=0
for i in ims:
    j=i.resize((i.width*3,i.height*3),Image.NEAREST)
    if x+j.width>2400: x=0;y+=H
    bg.alpha_composite(j,(x,y)); x+=j.width+8
bg.save('art_check.png'); print(bg.size)
