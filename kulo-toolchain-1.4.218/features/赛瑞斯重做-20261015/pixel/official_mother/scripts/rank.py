from common import *
import numpy as np, pickle, json
def cls(rgba):
    al = rgba[..., 3] > 0
    L = rgba[..., :3].astype(int).mean(-1)
    c = np.zeros(al.shape, np.int8)
    c[al & (L < 60)] = 1; c[al & (L >= 60) & (L < 170)] = 2; c[al & (L >= 170)] = 3
    return c
def score(A, B):
    H = max(A.shape[0], B.shape[0]) + 6; W = max(A.shape[1], B.shape[1]) + 6
    PA = np.zeros((H, W), np.int8); PA[3:3 + A.shape[0], 3:3 + A.shape[1]] = A
    best = (0, 0)
    for dy in range(H - B.shape[0] + 1):
        for dx in range(W - B.shape[1] + 1):
            PB = np.zeros((H, W), np.int8); PB[dy:dy + B.shape[0], dx:dx + B.shape[1]] = B
            u = ((PA > 0) | (PB > 0)).sum()
            sil = ((PA > 0) & (PB > 0)).sum() / u
            same = ((PA == PB) & (PA > 0)).sum() / u
            if sil > best[1]: best = (same, sil)
    return best
def trim(a):
    al = a[..., 3] > 0; ys, xs = np.nonzero(al)
    return a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
figs = [np.array(Image.open(f'ref_fig{i}.png')) for i in range(4)]
sv = json.load(open('survey.json', encoding='utf8'))
cache = pickle.load(open('crops.pkl', 'rb'))
def custom(code, v):
    i = int(v['id']); return (i % 10000) >= 9900 or i >= 700000 or any(s in code for s in ['playable', 'cnmod', 'mosiyike', 'ginovi', 'gerald', 'kyle', 'claude', 'seris', '_moon', 'stella_summer', 'lion_swordman_reborn'])
out = []
for code, v in sv.items():
    if custom(code, v) or code not in cache: continue
    cr = cache[code]; sq = v['seqs']
    def at(n):
        ks = [k for k in cr if k <= n]; return trim(cr[max(ks)][0]) if ks else None
    fr = at(sq['neutral'][1]); bk = at(sq['walk_back'][0] + 5)
    if fr is None or bk is None: continue
    s0 = score(cls(figs[0]), cls(fr)); s1 = score(cls(figs[1]), cls(bk))
    out.append((round(s0[1] + s1[1], 3), round(s0[0] + s1[0], 3), code, v['id'], v['rarity'], v['race'], v['gender'], v['special']))
out.sort(reverse=True)
for r in out[:40]: print(r)
json.dump(out, open('rank.json', 'w'))
