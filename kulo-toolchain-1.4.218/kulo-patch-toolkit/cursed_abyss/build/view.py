import sys
from PIL import Image
from pathlib import Path
ps=[Path(p) for p in sys.argv[2:]]
ims=[Image.open(p).convert('RGBA') for p in ps]
S=8; W=24*S
sheet=Image.new('RGBA',(W*len(ims), 24*S),(60,60,70,255))
for i,im in enumerate(ims): sheet.alpha_composite(im.resize((im.size[0]*S,im.size[1]*S),Image.NEAREST),(i*W, 0))
sheet.save(sys.argv[1])
