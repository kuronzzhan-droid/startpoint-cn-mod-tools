from frames import *
from build import recolor_set, MOTHERS
from maps import EXTRA_CANDIDATES
from PIL import ImageDraw, ImageFont
import numpy as np
GREY = (128, 128, 128, 255)
F_BIG = ImageFont.truetype('C:/Windows/Fonts/msyhbd.ttc', 44)
F_MID = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 22)
F_SM = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 16)

def bbox_union(imgs):
    bb = None
    for im in imgs:
        b = im.getbbox()
        if b is None: continue
        bb = b if bb is None else (min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3]))
    return bb

def key_frames(s):
    sq = seqs(s)
    nb, ne = sq['neutral']; wb, we = sq['walk_front']; bb, be = sq['walk_back']; sb, se = sq['skill_ready']
    body = [('idle', ne), ('walkF1', wb + 5), ('walkF2', wb + 11), ('walkF3', wb + 17), ('back', bb + 5)]
    L = se - sb
    skill = [(f'skill{i}', sb + int(L * t)) for i, t in enumerate((0.1, 0.3, 0.5, 0.75))]
    return body, skill

def row_images(s):
    fm = frame_map(s)
    body, skill = key_frames(s)
    bi = [(n, render(s, f, fm)) for n, f in body]
    si = [(n, render(s, f, fm)) for n, f in skill]
    return bi, si

def draw_row(rowsets, label, sub):
    """rowsets: list of (tag, set) e.g. [('原', s), ('赛瑞斯', s2)]"""
    blocks = []
    for tag, s in rowsets:
        bi, si = row_images(s)
        b1 = bbox_union([im for _, im in bi]); b2 = bbox_union([im for _, im in si])
        cells = []
        # 1x strip
        strip = [im.crop(b1) for _, im in bi]
        cells.append(('1×', strip, 1))
        cells.append(('4× idle/walk/back', [im.crop(b1) for _, im in bi], 4))
        sk = [im.crop(im.getbbox()) for _, im in si]
        big = max(max(c.size) for c in sk) > 70
        cells.append(('2× skill_ready' if big else '4× skill_ready', sk, 2 if big else 4))
        blocks.append((tag, cells))
    # layout
    pad = 10
    def block_size(cells):
        w = 0; h = 0
        for t, ims, k in cells:
            w += sum(im.size[0] * k + 6 for im in ims) + 24
            h = max(h, max(im.size[1] for im in ims) * k)
        return w, h + 26
    widths = [block_size(c)[0] for _, c in blocks]; heights = [block_size(c)[1] for _, c in blocks]
    W = 300 + max(widths) + pad; H = sum(heights) + pad * (len(blocks) + 1)
    H = max(H, 140)
    R = Image.new('RGBA', (W, H), GREY); d = ImageDraw.Draw(R)
    d.text((12, 8), label, font=F_BIG, fill=(255, 255, 80, 255))
    yy = 64
    for line in sub:
        d.text((12, yy), line[:24] if len(line)>24 else line, font=F_SM, fill=(255, 255, 255, 255)); yy += 20
    y = pad
    for (tag, cells), bh in zip(blocks, heights):
        x = 300
        d.text((x - 4, y), tag, font=F_MID, fill=(255, 255, 255, 255))
        x0 = x + 70
        for t, ims, k in cells:
            d.text((x0, y + 2), t, font=F_SM, fill=(220, 220, 220, 255))
            xx = x0
            for im in ims:
                R.alpha_composite(im.resize((im.size[0] * k, im.size[1] * k), Image.NEAREST), (xx, y + 24)); xx += im.size[0] * k + 6
            x0 = xx + 24
        y += bh + pad
    return R

def gif(sets, path, k=3, seq_names=('neutral', 'walk_front', 'walk_back', 'skill_ready')):
    """sets: list of (tag, set) rendered side by side in each set's own timeline order (same tick count padded)."""
    tracks = []
    for tag, s in sets:
        fm = frame_map(s); sq = seqs(s); fr = []
        for nm in seq_names:
            if nm not in sq: continue
            b, e = sq[nm]
            reps = 12 if nm == 'neutral' and e - b < 10 else 1
            for _ in range(reps):
                for f in range(b, e + 1): fr.append(render(s, f, fm))
        tracks.append((tag, fr))
    n = max(len(fr) for _, fr in tracks)
    bbs = [bbox_union(fr) for _, fr in tracks]
    bb = (min(b[0] for b in bbs), min(b[1] for b in bbs), max(b[2] for b in bbs), max(b[3] for b in bbs))
    w = (bb[2] - bb[0]) * k; h = (bb[3] - bb[1]) * k
    out = []; prev = None; durs = []
    for i in range(n):
        C = Image.new('RGBA', (len(tracks) * (w + 12), h + 30), GREY); d = ImageDraw.Draw(C)
        for j, (tag, fr) in enumerate(tracks):
            im = fr[min(i, len(fr) - 1)].crop(bb)
            C.alpha_composite(im.resize((im.size[0] * k, im.size[1] * k), Image.NEAREST), (j * (w + 12), 28))
            d.text((j * (w + 12) + 4, 2), tag, font=F_SM, fill=(255, 255, 80, 255))
        cb = C.convert('RGB').tobytes()
        if prev is not None and cb == prev:
            durs[-1] += 1; continue
        prev = cb; out.append(C.convert('RGB')); durs.append(1)
    ms = [max(20, int(round(dd * 1000 / 60 / 10)) * 10) for dd in durs]
    out[0].save(path, save_all=True, append_images=out[1:], duration=ms, loop=0, disposal=1)

if __name__ == '__main__':
    os.makedirs(OUT + '/preview', exist_ok=True)
    rows = []
    # reference row
    ref = Image.open(SR + '/ref64.png').convert('RGBA'); bb = ref.getbbox(); ref = ref.crop(bb)
    R = Image.new('RGBA', (300 + ref.size[0] * 5 + ref.size[0] + 60, max(150, ref.size[1] * 4 + 20)), GREY); d = ImageDraw.Draw(R)
    d.text((12, 8), 'REF', font=F_BIG, fill=(255, 255, 80, 255)); d.text((12, 64), '用户原稿(2×放大稿还原为1×,13×16)', font=F_SM, fill=(255, 255, 255, 255))
    d.text((12, 84), '结论:非官方/自制小人的换色(逐像素比对无匹配)', font=F_SM, fill=(255, 255, 255, 255))
    R.alpha_composite(ref, (300, 10)); R.alpha_composite(ref.resize((ref.size[0] * 4, ref.size[1] * 4), Image.NEAREST), (300 + ref.size[0] + 30, 10))
    rows.append(R)
    for mother, md in MOTHERS.items():
        s0 = load_set(mother); s1 = recolor_set(mother, False, {**md['body'], **md['fx']})
        rows.append(draw_row([('官方', s0), ('赛瑞斯', s1)], md['id'], [mother, md['name'], '已出整套换色(main+special)']))
        gif([('official ' + mother, s0), ('Seris ' + md['id'], s1)], f"{OUT}/preview/{md['id']}_{mother}.gif")
    for code, cid, name in EXTRA_CANDIDATES:
        s0 = load_set(code)
        rows.append(draw_row([('官方', s0)], cid, [code, name, '仅候选预览(未出换色)']))
        gif([('official ' + code, s0)], f"{OUT}/preview/{cid}_{code}.gif")
    W = max(r.size[0] for r in rows); H = sum(r.size[1] + 6 for r in rows)
    S = Image.new('RGBA', (W, H), (70, 70, 70, 255)); y = 0
    for r in rows: S.alpha_composite(r, (0, y)); y += r.size[1] + 6
    S.convert('RGB').save(OUT + '/候选总览-官方母本.png')
    print(S.size)
