from common import *

def load_set(code, special=False):
    sheet = 'special_sprite_sheet' if special else 'sprite_sheet'
    fr = 'special' if special else 'pixelart'
    base = f'character/{code}/pixelart/'
    im = png(base + sheet + '.png')
    if im is None: return None
    at = amf(base + sheet + '.atlas.amf3.deflate')
    f = amf(base + fr + '.frame.amf3.deflate')
    t = amf(base + fr + '.timeline.amf3.deflate')
    return dict(code=code, special=special, sheet=im, atlas=at, frame=f, timeline=t,
                raw={k: raw(base + k) for k in [sheet + '.png', sheet + '.atlas.amf3.deflate', fr + '.frame.amf3.deflate', fr + '.timeline.amf3.deflate']})

def crop(s, e):
    """return frame image (unrotated) and its placement (ox, oy) within fw x fh canvas"""
    x, y, w, h = e['x'], e['y'], e['w'], e['h']
    if e.get('r'):
        # verified: sheet region is w x h as listed; rotate CCW to restore upright (h x w)
        c = s['sheet'].crop((x, y, x + w, y + h)).transpose(Image.Transpose.ROTATE_90)
    else:
        c = s['sheet'].crop((x, y, x + w, y + h))
    return c, -e.get('fx', 0), -e.get('fy', 0)

def frame_map(s):
    """frame number -> atlas entry"""
    m = {}
    for e in s['atlas']:
        n = e['n']
        num = int(''.join(ch for ch in n[-4:] if ch.isdigit()))
        m[num] = e
    return m

def frame_at(s, n, fm=None):
    fm = fm or frame_map(s)
    ks = [k for k in fm if k <= n]
    if not ks: return None
    return fm[max(ks)]

def render(s, n, fm=None, canvas=256):
    e = frame_at(s, n, fm)
    img = Image.new('RGBA', (canvas, canvas), (0, 0, 0, 0))
    if e is None: return img
    c, ox, oy = crop(s, e)
    img.alpha_composite(c, (ox, oy))
    return img

def seqs(s):
    return {q['name']: (q['begin'], q['end']) for q in s['timeline']['sequences']}
