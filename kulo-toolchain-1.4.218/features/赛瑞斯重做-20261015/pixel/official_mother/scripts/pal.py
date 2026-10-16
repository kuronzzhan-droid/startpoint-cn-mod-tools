from frames import *
import numpy as np
from collections import Counter
from PIL import ImageDraw
def palettes(code):
    s = load_set(code); fm = frame_map(s); sq = seqs(s)
    body = Counter(); eff = Counter(); other = Counter()
    for n, e in fm.items():
        a = np.array(crop(s, e)[0]); px = a[a[..., 3] > 0]
        cols = Counter(map(tuple, px[:, :4]))
        if n <= sq['walk_front'][1] or sq['kachidoki'][0] <= n <= sq['kachidoki'][1]:
            body.update(cols)
        elif sq['skill_ready'][0] <= n <= sq['skill_ready'][1]:
            eff.update(cols)
        else:
            other.update(cols)
    sp = load_set(code, True); spc = Counter()
    for e in sp['atlas']:
        a = np.array(crop(sp, e)[0]); spc.update(map(tuple, a[a[..., 3] > 0][:, :4]))
    return body, eff, other, spc
if __name__ == '__main__':
    code = sys.argv[1]
    body, eff, other, spc = palettes(code)
    print('BODY', len(body)); [print('  ', c, n) for c, n in body.most_common()]
    effonly = Counter({c: n for c, n in eff.items() if c not in body})
    print('SKILL-only', len(effonly)); [print('  ', c, n) for c, n in effonly.most_common(60)]
    oth = Counter({c: n for c, n in other.items() if c not in body and c not in eff})
    print('OTHER-only', len(oth)); [print('  ', c, n) for c, n in oth.most_common(20)]
    sponly = Counter({c: n for c, n in spc.items() if c not in body and c not in eff and c not in other})
    print('SPECIAL-only', len(sponly)); [print('  ', c, n) for c, n in sponly.most_common(30)]
