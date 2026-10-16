# -*- coding: utf-8 -*-
"""Final Seris pixel set: dragonman = user's own sprite (native size) on alk_3halfanv timeline skeleton;
true dragon = wind_dragon (DB) recolour, retimed into special slot + DB special_land/pose."""
from frames import *
import numpy as np, json, copy, hashlib, math
from build import recolor_set, dual_special, deflate, store_png, pack, TARGET
from maps import MOTHERS
OUTF = r"D:/WF/out/赛瑞斯重做-20261015/pixel/final_USER_DB"
GAME = OUTF + "/game/character/seris_dragon_king/pixelart"

# ---------------------------------------------------------------- user sprites (snap to clean palette)
PAL = [(0, 0, 0), (255, 255, 255), (240, 245, 249), (211, 222, 234), (153, 161, 183), (109, 116, 142),
       (64, 118, 180), (53, 68, 151), (107, 166, 226)]
def snap(path):
    a = np.array(Image.open(path).convert('RGBA')).copy()
    P = np.array(PAL)
    m = a[..., 3] > 0
    px = a[m][:, :3].astype(int)
    idx = ((px[:, None, :] - P[None]) ** 2).sum(-1).argmin(1)
    a[m, :3] = P[idx]; a[m, 3] = 255; a[~m] = 0
    return Image.fromarray(a.astype(np.uint8))
FRONT = snap(SR + '/ref_fig0.png'); BACK = snap(SR + '/ref_fig1.png')
POSE = snap(SR + '/ref_fig2.png'); POSE_B = snap(SR + '/ref_fig3.png')

# ---------------------------------------------------------------- composition helpers
def place(canvas, img, dy=0, dx=0):
    w, h = img.size
    canvas.alpha_composite(img, (128 - w // 2 + dx, 128 - h + dy))

def finish(canvas):
    bb = canvas.getbbox()
    c = canvas.crop(bb)
    return (c, bb[0], bb[1])  # fx = -bb[0], fy = -bb[1]

def body_frame(img, dy=0, dx=0, under=(), over=()):
    C = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
    for fn in under: fn(C)
    place(C, img, dy, dx)
    for fn in over: fn(C)
    return finish(C)

def sway(img, s):
    """shift bottom 2 rows (hem / tail) by s px; canvas widened by 1 each side"""
    w, h = img.size
    out = Image.new('RGBA', (w + 2, h), (0, 0, 0, 0))
    out.paste(img.crop((0, 0, w, h - 2)), (1, 0))
    out.paste(img.crop((0, h - 2, w, h)), (1 + s, h - 2))
    return out

def put(C, x, y, col):
    if 0 <= x < 256 and 0 <= y < 256: C.putpixel((int(x), int(y)), col + (255,) if len(col) == 3 else col)

# ---------------------------------------------------------------- water flourish (simple shapes, official flat style)
WL, WM, WD, WW = (210, 241, 255), (54, 192, 255), (14, 128, 255), (255, 255, 255)
def ring(phase, half):
    rx = 7 + 9 * min(1.0, phase * 1.6); ry = max(2.0, rx * 0.38); cx, cy = 128, 125
    th0 = phase * 2 * math.pi * 1.6
    def draw(C):
        span = 4.2
        n = 70
        for i in range(n):
            t = i / (n - 1); th = th0 - t * span
            front = math.sin(th) > 0
            if front != (half == 'front'): continue
            x = cx + rx * math.cos(th); y = cy + ry * math.sin(th)
            col = WW if t < 0.08 else WL if t < 0.35 else WM if t < 0.7 else WD
            put(C, round(x), round(y), col)
            if t < 0.5: put(C, round(x), round(y) - 1, WL if t < 0.2 else WM)
    return draw

def drops(phase, seed=0):
    def draw(C):
        for k in range(6):
            ang = k * 1.047 + seed
            x0 = 128 + 13 * math.cos(ang); y0 = 125 + 5 * math.sin(ang)
            t = phase - k * 0.06
            if t <= 0 or t > 0.9: continue
            x = x0 + (3 if math.cos(ang) > 0 else -3) * t; y = y0 - 26 * t + 18 * t * t
            xi, yi = round(x), round(y)
            for dx_, dy_, c in ((0, 0, WM), (1, 0, WM), (0, 1, WD), (1, 1, WD), (0, -1, WW)):
                put(C, xi + dx_, yi + dy_, c)
    return draw

def sparkle(points, big=True):
    G1, G2 = (255, 212, 64), (255, 255, 213)
    def draw(C):
        for (x, y, s) in points:
            x += 128; y += 128
            put(C, x, y, WW)
            for d in range(1, s + 1):
                c = G2 if d == 1 else G1
                put(C, x + d, y, c); put(C, x - d, y, c); put(C, x, y + d, c); put(C, x, y - d, c)
    return draw

# ---------------------------------------------------------------- learned official recolours (alk pairs)
alk = load_set('alk_3halfanv'); afm = frame_map(alk)
def arr(n): return np.array(crop(alk, afm[n])[0])
def lum(c): return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
def learn(n_src, n_dst):
    A, Bq = arr(n_src), arr(n_dst)
    pairs = {}
    if A.shape != Bq.shape: return []
    m = (A[..., 3] > 0) & (Bq[..., 3] > 0)
    for s_, d_ in zip(A[m], Bq[m]):
        pairs.setdefault(lum(s_[:3]), tuple(int(v) for v in d_))
    return sorted(pairs.items())
MAG = learn(163, 161)      # liedown -> magenta blink
GHO = learn(2, 201)        # standing -> ghost
def lum_map(img, pairs, tint=(0, 0, 0)):
    a = np.array(img).copy()
    L = np.array([p[0] for p in pairs])
    for y in range(a.shape[0]):
        for x in range(a.shape[1]):
            if a[y, x, 3] == 0: continue
            d = pairs[int(np.abs(L - lum(a[y, x, :3])).argmin())][1]
            a[y, x] = [min(255, max(0, d[0] + tint[0])), min(255, max(0, d[1] + tint[1])), min(255, max(0, d[2] + tint[2])), d[3]]
    return Image.fromarray(a)

LIE = FRONT.transpose(Image.Transpose.ROTATE_90)            # lying down (rotated)
LIE_MAG = lum_map(LIE, MAG)
def ghostify(img):
    g = lum_map(img, GHO, tint=(-12, -2, 14))                # official ghost greys pushed white-blue
    a = np.array(g); h, w = a.shape[:2]; c = w // 2
    for row, keep in ((h - 1, 1), (h - 2, 3), (h - 3, 5)):    # tail: bottom rows taper to centre
        for x in range(w):
            if abs(x - c) > keep: a[row, x] = 0
    return Image.fromarray(a)
GHOST = ghostify(FRONT)
def silhouette(img, col):
    a = np.array(img).copy(); m = a[..., 3] > 0; a[m] = col + (255,); return Image.fromarray(a)

def classify(n):
    a = arr(n); px = a[a[..., 3] > 0]; cols = {tuple(int(v) for v in p[:3]) for p in px}
    if cols == {(255, 255, 255)}: return 'white'
    if cols == {(0, 0, 0)}: return 'black'
    if (177, 0, 227) in cols: return 'magenta'
    if (138, 138, 138) in cols: return 'ghost'
    return 'body'
def alk_dy(n):
    e = afm[n]; h = e['w'] if e.get('r') else e['h']
    return -e['fy'] - 128 + h

# ---------------------------------------------------------------- frame plan on alk skeleton
seq = seqs(alk)
F = {}
F[2] = body_frame(FRONT)
F[1] = F[2]   # frame 1 visible too (legality visibility gate; shares rect with 2)
for img, keys in ((BACK, (8, 14, 20, 26)), (FRONT, (32, 38, 44, 50))):
    for i, k in enumerate(keys):
        s_ = [0, -1, 0, 1][i]; dy = [0, 1, 0, 1][i]
        F[k] = body_frame(sway(img, s_) if s_ else img, dy=dy)
# skill_ready 51-110 : casting pose + water ring + droplets, then back to front
for f in range(52, 111, 2):
    if f <= 96:
        ph = (f - 52) / 44.0
        dy = -1 if (f // 4) % 2 else 0
        under = [ring(ph, 'back')] if f >= 56 else []
        over = ([ring(ph, 'front')] if f >= 56 else []) + ([drops((f - 70) / 30.0)] if f >= 70 else [])
        F[f] = body_frame(POSE, dy=dy, under=under, over=over)
    else:
        over = [drops((f - 70) / 30.0)] if f < 100 else []
        F[f] = body_frame(FRONT, over=over)
# kachidoki 111-158 (anchors 116/122/152/158; client reads 129 -> lands on 122/128)
SA = [(-10, -14, 2), (9, -12, 1), (0, -20, 1)]
SB = [(-7, -18, 1), (11, -17, 2), (-12, -8, 1)]
F[116] = body_frame(FRONT)
for k, dy, sp in ((122, 0, SA), (128, -1, SB), (134, 0, SA), (140, -1, SB), (146, 0, SA)):
    F[k] = body_frame(POSE, dy=dy, over=[sparkle(sp)])
F[152] = body_frame(FRONT, dy=-3, over=[sparkle(SB)])
F[155] = body_frame(FRONT, dy=-1)
F[158] = body_frame(FRONT)
# into_coffin / ghost / revive : mirror alk keyframe-by-keyframe (type + vertical offset)
for n in sorted(afm):
    if n < seq['into_coffin'][0]: continue
    kind = classify(n); dy = alk_dy(n)
    if n <= seq['into_coffin'][1]:
        base = {'white': silhouette(LIE, (255, 255, 255)), 'black': silhouette(LIE, (0, 0, 0)),
                'magenta': LIE_MAG}.get(kind, LIE)
    elif kind == 'white': base = silhouette(GHOST, (255, 255, 255))
    elif kind == 'black': base = silhouette(GHOST, (0, 0, 0))
    elif kind == 'ghost': base = GHOST
    else: base = FRONT
    F[n] = body_frame(base, dy=dy)
print('keyframes', len(F), 'types used ok')

# ---------------------------------------------------------------- assemble main set
sheet, km = pack([(n, F[n][0]) for n in sorted(F)], maxw=256)
atlas = []
for n in sorted(F):
    (x, y), (w, h) = km[n]; c, x0, y0 = F[n]
    atlas.append({'n': f'character/{TARGET}/pixelart/pixelart{n:04d}', 'w': w, 'h': h, 'x': x, 'y': y,
                  'fx': -x0, 'fy': -y0, 'fw': 256, 'fh': 256})
timeline = copy.deepcopy(alk['timeline'])
frame = {'name': f'character/{TARGET}/pixelart/pixelart', 'x': -128, 'y': -128, 'scale': 6, 'smoothing': False}
MAIN = dict(sheet=sheet, atlas=atlas, frame=frame, timeline=timeline)

# ---------------------------------------------------------------- dual special: DB retimed + DB land/pose
md = MOTHERS['wind_dragon']; cmap = {**md['body'], **md['fx']}
dmain = recolor_set('wind_dragon', False, cmap); dspec = recolor_set('wind_dragon', True, cmap)
ssheet, satlas, sframe, stl = dual_special(MAIN, dmain, dspec)
# markers: one unit_body entry per sequence (begin+1), land/pose empty (legality: one frame per sequence)
ub = next(c for c in stl['circles'] if c['path'] == 'unit_body')
for q in stl['sequences'][len(ub['frames']):]:
    ub['frames'].append({'begin': q['begin'] + 1, 'data': []})
if not any(e['n'].endswith('special0001') for e in satlas):
    e2 = next(e for e in satlas if e['n'].endswith('special0002'))
    e1 = dict(e2); e1['n'] = e2['n'][:-4] + '0001'; satlas.insert(0, e1)
SPEC = dict(sheet=ssheet, atlas=satlas, frame=sframe, timeline=stl)

# ---------------------------------------------------------------- write + verify
os.makedirs(GAME, exist_ok=True)
files = {}
def emit(name, blob):
    open(f'{GAME}/{name}', 'wb').write(blob); files[name] = blob
for S, sh, fr in ((MAIN, 'sprite_sheet', 'pixelart'), (SPEC, 'special_sprite_sheet', 'special')):
    emit(f'{sh}.png', store_png(S['sheet']))
    emit(f'{sh}.atlas.amf3.deflate', deflate(S['atlas']))
    emit(f'{fr}.frame.amf3.deflate', deflate(S['frame']))
    emit(f'{fr}.timeline.amf3.deflate', deflate(S['timeline']))
    os.makedirs(OUTF + '/png', exist_ok=True); S['sheet'].save(f'{OUTF}/png/{sh}.png')
json.dump({'main_keyframes': sorted(F), 'special_sequences': stl['sequences']}, open(OUTF + '/work_frames.json', 'w'), indent=0)
print('main sheet', sheet.size, len(atlas), '| special sheet', ssheet.size, len(satlas))
