from frames import *
import numpy as np, json, copy, hashlib, wf_dsl
from maps import MOTHERS
TARGET = 'seris_dragon_king'
STD9 = ['neutral', 'walk_back', 'walk_front', 'skill_ready', 'kachidoki', 'into_coffin', 'ghost_raise', 'ghost_neutral', 'revive']

def recolor_img(im, cmap):
    a = np.array(im.convert('RGBA'))
    out = a.copy()
    rgb = a[..., :3]
    used = {}
    for src, dst in cmap.items():
        m = np.all(rgb == np.array(src, np.uint8), -1) & (a[..., 3] > 0)
        c = int(m.sum())
        if c:
            out[m, 0], out[m, 1], out[m, 2] = dst
            used[src] = c
    return Image.fromarray(out), used

def store_png(im):
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True); b = bytearray(b.getvalue())
    assert b[1:4] == b'PNG'; b[1:4] = b'png'; return bytes(b)

def deflate(tree):
    raw_ = wf_dsl.encode_amf3(tree)
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    blob = co.compress(raw_) + co.flush()
    assert core.AMF3Reader(zlib.decompress(blob, -15)).read_value() == tree
    return blob

def rename(tree, mother):
    s = json.dumps(tree, ensure_ascii=False).replace(f'character/{mother}/', f'character/{TARGET}/')
    return json.loads(s)

def write_set(dirp, sheet_name, fr_name, sheet_img, atlas, frame, timeline):
    os.makedirs(dirp, exist_ok=True)
    files = {
        f'{sheet_name}.png': store_png(sheet_img),
        f'{sheet_name}.atlas.amf3.deflate': deflate(atlas),
        f'{fr_name}.frame.amf3.deflate': deflate(frame),
        f'{fr_name}.timeline.amf3.deflate': deflate(timeline),
    }
    for k, v in files.items():
        open(os.path.join(dirp, k), 'wb').write(v)
    sheet_img.save(os.path.join(dirp, '_preview_' + sheet_name + '.png'))  # normal PNG for viewing
    return files

def recolor_set(mother, special, cmap):
    s = load_set(mother, special)
    img, used = recolor_img(s['sheet'], cmap)
    s2 = dict(s); s2['sheet'] = img
    s2['atlas'] = rename(s['atlas'], mother); s2['frame'] = rename(s['frame'], mother)
    s2['timeline'] = copy.deepcopy(s['timeline'])
    s2['used'] = used
    return s2

# ---------------- dual form: dragon battle frames retimed onto humanoid absolute ticks + dragon special_land/pose
def retime(hseq, dseq, kind):
    hb, he = hseq; db, de = dseq; hl = he - hb + 1; dl = de - db + 1
    m = {}
    for f in range(hb, he + 1):
        t = f - hb
        if dl > hl:
            g = db + (t * dl) // hl
        elif kind == 'loop':
            g = db + (t % dl)
        else:
            g = db + min(t, dl - 1)
        m[f] = g
    return m

def pack(entries_imgs, maxw=1024):
    """entries_imgs: list of (key, PIL img). shelf pack, dedupe identical."""
    uniq = {}; order = []
    for k, im in entries_imgs:
        h = hashlib.md5(im.tobytes() + bytes(str(im.size), 'ascii')).hexdigest()
        if h not in uniq: uniq[h] = im; order.append(h)
    order.sort(key=lambda h: (-uniq[h].size[1], -uniq[h].size[0]))
    x = y = sh = 0; pos = {}; W = 0
    for h in order:
        w, hh = uniq[h].size
        if x + w > maxw: x = 0; y += sh + 1; sh = 0
        pos[h] = (x, y); x += w + 1; sh = max(sh, hh); W = max(W, x)
    H = y + sh
    sheet = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    for h, (px, py) in pos.items(): sheet.paste(uniq[h], (px, py))
    keymap = {}
    for k, im in entries_imgs:
        h = hashlib.md5(im.tobytes() + bytes(str(im.size), 'ascii')).hexdigest()
        keymap[k] = (pos[h], im.size)
    return sheet, keymap

def dual_special(hum_set, dmain, dspec):
    """hum_set: recoloured humanoid main set (for timeline); dmain/dspec: recoloured dragon main/special sets"""
    ht = hum_set['timeline']; hs = {q['name']: q for q in ht['sequences']}
    ds = seqs(dmain); dfm = frame_map(dmain); sfm = frame_map(dspec)
    frames_ = {}  # new frame number -> (img, fx, fy)
    for name in STD9:
        q = hs[name]
        m = retime((q['begin'], q['end']), ds[name], q['kind'])
        prev = None
        for f in range(q['begin'], q['end'] + 1):
            e = frame_at(dmain, m[f], dfm)
            if e is None: continue
            key = (e['x'], e['y'], e['w'], e['h'], e.get('r', False), e['fx'], e['fy'])
            if f == q['begin'] or key != prev:
                c, ox, oy = crop(dmain, e); frames_[f] = (c, e['fx'], e['fy'], e['fw'], e['fh'])
            prev = key
    off = max(q['end'] for q in ht['sequences'])
    sp_seqs = []
    for q in dspec['timeline']['sequences']:
        sp_seqs.append(dict(name=q['name'], kind=q['kind'], begin=q['begin'] + off, end=q['end'] + off))
        if q['begin'] == 1 and frame_at(dspec, 1, sfm) is None:
            # official special_land starts blank (first key at 6); keep that instead of holding the revive frame
            frames_[off + 1] = (Image.new('RGBA', (1, 1), (0, 0, 0, 0)), -128, -128, 256, 256)
        prev = None
        for f in range(q['begin'], q['end'] + 1):
            e = frame_at(dspec, f, sfm)
            if e is None: continue
            key = (e['x'], e['y'], e['w'], e['h'], e.get('r', False), e['fx'], e['fy'])
            if f == q['begin'] or key != prev:
                c, ox, oy = crop(dspec, e); frames_[f + off] = (c, e['fx'], e['fy'], e['fw'], e['fh'])
            prev = key
    sheet, km = pack([(n, v[0]) for n, v in sorted(frames_.items())])
    atlas = []
    for n in sorted(frames_):
        (x, y), (w, h) = km[n]; c, fx, fy, fw, fh = frames_[n]
        atlas.append({'n': f'character/{TARGET}/pixelart/special{n:04d}', 'w': w, 'h': h, 'x': x, 'y': y,
                      'fx': fx, 'fy': fy, 'fw': fw, 'fh': fh})
    seq9 = [copy.deepcopy(hs[n]) for n in STD9]
    timeline = {'sequences': seq9 + sp_seqs, 'circles': copy.deepcopy(ht['circles']),
                'points': copy.deepcopy(ht['points']), 'sounds': []}
    frame = {'name': f'character/{TARGET}/pixelart/special', 'x': -128, 'y': -128, 'scale': 6, 'smoothing': False}
    return sheet, atlas, frame, timeline

if __name__ == '__main__':
    report = {}
    sets = {}
    for mother, md in MOTHERS.items():
        cmap = dict(md['body']); cmap.update(md['fx'])
        for sp in (False, True):
            s2 = recolor_set(mother, sp, cmap)
            sets[(mother, sp)] = s2
            sub = 'special' if sp else 'main'
            d = f"{OUT}/sets/{md['id']}_{mother}/{sub}"
            write_set(d, 'special_sprite_sheet' if sp else 'sprite_sheet', 'special' if sp else 'pixelart',
                      s2['sheet'], s2['atlas'], s2['frame'], s2['timeline'])
            report[f"{md['id']}_{mother}_{sub}"] = {str(k): v for k, v in s2['used'].items()}
    for h in [m for m in MOTHERS if MOTHERS[m]['id'].startswith('H')]:
        for dg in [m for m in MOTHERS if MOTHERS[m]['id'].startswith('D')]:
            sheet, atlas, frame, timeline = dual_special(sets[(h, False)], sets[(dg, False)], sets[(dg, True)])
            d = f"{OUT}/dual_form/{MOTHERS[h]['id']}+{MOTHERS[dg]['id']}/special"
            write_set(d, 'special_sprite_sheet', 'special', sheet, atlas, frame, timeline)
            print('dual', h, dg, sheet.size, len(atlas), [(q['name'], q['begin'], q['end']) for q in timeline['sequences']])
    json.dump(report, open(f'{OUT}/palette_usage.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)
    print('ok')
