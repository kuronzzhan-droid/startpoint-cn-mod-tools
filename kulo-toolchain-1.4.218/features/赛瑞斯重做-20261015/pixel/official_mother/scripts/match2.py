from common import *
import numpy as np, pickle, json
from scipy import ndimage
ref = np.array(Image.open(r'D:/WF/out/赛瑞斯重做-20261015/pixel/round1/work/user_ref_128.png').convert('RGBA'))[::2, ::2]
Image.fromarray(ref).save('ref64.png')
a = ref[..., 3] > 0
lab, n = ndimage.label(a)
figs = []
for i, sl in enumerate(ndimage.find_objects(lab)):
    m = lab[sl] == i + 1
    if m.sum() < 20: continue
    rgba = ref[sl].copy(); rgba[~m] = 0
    figs.append(rgba)
    Image.fromarray(rgba).save(f'ref_fig{len(figs)-1}.png')
print([f.shape for f in figs])

def cls(rgba):
    al = rgba[..., 3] > 0
    L = rgba[..., :3].astype(int).mean(-1)
    c = np.zeros(al.shape, np.int8)
    c[al & (L < 60)] = 1     # outline
    c[al & (L >= 60) & (L < 170)] = 2  # mid/dark colour
    c[al & (L >= 170)] = 3   # light
    return c

def score(A, B):
    # A,B class arrays; best alignment by sliding; score = matching class over union of alpha
    H = max(A.shape[0], B.shape[0]) + 4; W = max(A.shape[1], B.shape[1]) + 4
    PA = np.zeros((H, W), np.int8); PA[2:2 + A.shape[0], 2:2 + A.shape[1]] = A
    best = (0, 0)
    for dy in range(H - B.shape[0] + 1):
        for dx in range(W - B.shape[1] + 1):
            PB = np.zeros((H, W), np.int8); PB[dy:dy + B.shape[0], dx:dx + B.shape[1]] = B
            u = ((PA > 0) | (PB > 0)).sum()
            sil = ((PA > 0) & (PB > 0)).sum() / u
            same = ((PA == PB) & (PA > 0)).sum() / u
            if same > best[0]: best = (same, sil)
    return best

cache = pickle.load(open('crops.pkl', 'rb'))
print('gerald in cache', 'white_wolf_gerald' in cache, 'seris' , 'seris_dragon_king' in cache)
out = []
fc = [cls(f) for f in figs]
for code, crops in cache.items():
    for nn, (arr, ox, oy) in crops.items():
        al = arr[..., 3] > 0
        ys, xs = np.nonzero(al)
        if len(ys) == 0: continue
        sub = arr[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        for fi, F in enumerate(fc):
            if abs(sub.shape[0] - F.shape[0]) > 3 or abs(sub.shape[1] - F.shape[1]) > 3: continue
            c = cls(sub)
            s1 = score(F, c); s2 = score(F, c[:, ::-1])
            s = max(s1, s2)
            out.append((round(s[0], 3), round(s[1], 3), fi, code, nn))
out.sort(reverse=True)
seen = set()
for fi in range(len(figs)):
    print('--- fig', fi, figs[fi].shape)
    k = 0
    for r in out:
        if r[2] != fi or (fi, r[3]) in seen: continue
        seen.add((fi, r[3])); print(r); k += 1
        if k >= 12: break
json.dump(out[:500], open('match2.json', 'w'))
