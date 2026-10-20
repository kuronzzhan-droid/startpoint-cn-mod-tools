from p192_common import *
import numpy as np
from rembg import remove, new_session
out=ART/"cutout"; out.mkdir(exist_ok=True)
rows=[]
for model in ("isnet-anime","isnet-general-use","u2net"):
    sess = new_session(model, providers=["CUDAExecutionProvider","CPUExecutionProvider"])
    row=[]
    for i,(f,cid,code,s) in enumerate(SLOTS):
        m = Image.open(MASTERS/f).convert("RGBA")
        mask = remove(m.convert("RGB"), session=sess, only_mask=True)
        mask.save(out/f"mask_{model}_{i}.png"); row.append(mask.convert("RGB").resize((362,483)))
    rows.append(row)
s=Image.new("RGB",(362*4,483*3))
for r,row in enumerate(rows):
    for c,im in enumerate(row): s.paste(im,(c*362,r*483))
s.save(ART/"inspect"/"masks.jpg",quality=85)
