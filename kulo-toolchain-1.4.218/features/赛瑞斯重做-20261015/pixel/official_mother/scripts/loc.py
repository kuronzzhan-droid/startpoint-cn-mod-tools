from frames import *
import numpy as np
from PIL import ImageDraw
from pal import palettes
code = sys.argv[1]; frames_ = [int(x) for x in sys.argv[2].split(',')]; mode = sys.argv[3] if len(sys.argv) > 3 else 'body'
sp = mode == 'sp'
s = load_set(code, sp); fm = frame_map(s)
imgs = [np.array(crop(s, frame_at(s, n, fm))[0]) for n in frames_]
from collections import Counter
cnt = Counter()
for a in imgs: cnt.update(map(tuple, a[a[..., 3] > 0][:, :4]))
cols = [c for c, _ in cnt.most_common(40)]
k = 6
W = sum(a.shape[1] * k + 4 for a in imgs) + 4; H = max(a.shape[0] for a in imgs) * k + 4
G = Image.new('RGBA', (W * 4, (H + 14) * ((len(cols) + 3) // 4 + 1)), (90, 90, 90, 255)); d = ImageDraw.Draw(G)
def put(arrs, ox, oy, label):
    x = ox
    for a in arrs:
        im = Image.fromarray(a).resize((a.shape[1] * k, a.shape[0] * k), Image.NEAREST); G.alpha_composite(im, (x, oy + 12)); x += a.shape[1] * k + 4
    d.text((ox, oy), label, fill=(255, 255, 0, 255))
put(imgs, 0, 0, 'orig')
for i, c in enumerate(cols):
    arrs = []
    for a in imgs:
        b = a.copy(); m = np.all(b[..., :4] == np.array(c, np.uint8), -1)
        al = b[..., 3] > 0
        g = (b[..., :3].astype(int).mean(-1) * 0.35 + 40).astype(np.uint8)
        b[..., 0] = g; b[..., 1] = g; b[..., 2] = g
        b[m] = (255, 0, 255, 255); arrs.append(b)
    j = i + 1
    put(arrs, (j % 4) * W, (j // 4) * (H + 14), f'{c[:3]} a{c[3]} n{cnt[c]}')
G.save(f'loc_{code}_{mode}.png')
