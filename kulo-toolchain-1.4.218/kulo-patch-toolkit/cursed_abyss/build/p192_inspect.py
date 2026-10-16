from p192_common import *
import numpy as np
for f, cid, code, s in SLOTS:
    m = Image.open(MASTERS / f); print(f, m.mode, m.size, m.getchannel("A").getbbox(), np.asarray(m)[0,0])
    lp = f"character/{code}/ui/full_shot_1440_1920_{s}.png"
    for r in roots_of(lp):
        raw, src = aread(r, lp); im = png_img(raw); print("  live", r, src, im.size, hashlib.sha256(raw).hexdigest()[:12])
    im.save(ART / "inspect" / f"live_{code}_{s}.png")
    # master preview w/ grid
    bg = Image.new("RGBA", m.size, (128,128,128,255)); bg.alpha_composite(m.convert("RGBA"))
    from PIL import ImageDraw
    d = ImageDraw.Draw(bg)
    for y in range(0, m.size[1], 50): d.line([(0,y),(m.size[0],y)], fill=(255,0,0,255) if y%100==0 else (255,200,200,255), width=1)
    for x in range(0, m.size[0], 50): d.line([(x,0),(x,m.size[1])], fill=(0,0,255,255) if x%100==0 else (200,200,255,255), width=1)
    bg.convert("RGB").save(ART / "inspect" / f"grid_{code}_{s}.jpg", quality=88)
