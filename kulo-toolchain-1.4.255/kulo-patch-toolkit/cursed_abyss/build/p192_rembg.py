from p192_common import *
import numpy as np
from rembg import remove, new_session
sess = new_session("isnet-anime", providers=["CUDAExecutionProvider","CPUExecutionProvider"])
(ART/"cutout").mkdir(exist_ok=True)
for i,(f,cid,code,s) in enumerate(SLOTS):
    m = Image.open(MASTERS/f).convert("RGBA")
    mask = remove(m, session=sess, only_mask=True)
    a = np.minimum(np.asarray(mask), np.asarray(m)[:,:,3])
    mask.save(ART/"cutout"/f"mask_{i}.png")
    out = m.copy(); out.putalpha(Image.fromarray(a))
    out.save(ART/"cutout"/f"cut_{i}.png")
    bg = Image.new("RGBA", m.size, (90,140,90,255)); bg.alpha_composite(out)
    bg.convert("RGB").resize((543,724)).save(ART/"inspect"/f"cut_{i}.jpg", quality=85)
    print(i, (a>127).mean())
