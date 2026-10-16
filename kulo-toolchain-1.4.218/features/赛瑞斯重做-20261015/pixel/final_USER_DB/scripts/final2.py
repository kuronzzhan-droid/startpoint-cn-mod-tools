# -*- coding: utf-8 -*-
"""verify + legality + manifest + previews for final_USER_DB"""
from frames import *
import numpy as np, json, hashlib, glob
sys.path.insert(0, r'D:/WF/out/kulo-patch-toolkit/oldrepo_modtools')
import wf_client_legality as LG
from preview import gif, F_BIG, F_MID, F_SM, GREY
from PIL import ImageDraw
OUTF = r"D:/WF/out/赛瑞斯重做-20261015/pixel/final_USER_DB"
GAME = OUTF + "/game/character/seris_dragon_king/pixelart"
STORE = r"D:/WF/out/kulo-patch-toolkit/store131/production"

def load_game(special):
    sh = 'special_sprite_sheet' if special else 'sprite_sheet'; fr = 'special' if special else 'pixelart'
    raws = {}
    b = open(f'{GAME}/{sh}.png', 'rb').read(); raws[sh + '.png'] = b
    assert b[:4] == b'\x89png', 'game header'
    bb = bytearray(b); bb[1:4] = b'PNG'
    im = Image.open(io.BytesIO(bytes(bb))); im.load(); im = im.convert('RGBA')
    out = dict(sheet=im)
    for key, fn in (('atlas', f'{sh}.atlas.amf3.deflate'), ('frame', f'{fr}.frame.amf3.deflate'), ('timeline', f'{fr}.timeline.amf3.deflate')):
        blob = open(f'{GAME}/{fn}', 'rb').read(); raws[fn] = blob
        dec = zlib.decompress(blob, -15)
        v = core.AMF3Reader(dec).read_value()
        import wf_dsl
        assert wf_dsl.encode_amf3(v) == dec, 'roundtrip ' + fn   # byte-exact re-encode
        out[key] = v
    return out, raws

report = {}
sets = {}
for sp in (False, True):
    s, raws = load_game(sp); sets[sp] = s
    fm = frame_map(s); tl = s['timeline']
    # alpha pixels per frame number (as client resolves: max keyframe <= f)
    last = max(q['end'] for q in tl['sequences'])
    alpha = {}
    cache = {}
    for f in range(1, last + 1):
        e = frame_at(s, f, fm)
        if e is None: alpha[f] = 0; continue
        if e['n'] not in cache:
            c = np.array(crop(s, e)[0]); cache[e['n']] = int((c[..., 3] >= 128).sum())
        alpha[f] = cache[e['n']]
    oob = [e['n'] for e in s['atlas'] if e['x'] + e['w'] > s['sheet'].size[0] or e['y'] + e['h'] > s['sheet'].size[1]]
    pre = 'character/seris_dragon_king/pixelart/' + ('special' if sp else 'pixelart')
    badname = [e['n'] for e in s['atlas'] if not e['n'].startswith(pre)]
    report['special' if sp else 'main'] = dict(
        sheet=s['sheet'].size, atlas_entries=len(s['atlas']), frame=s['frame'],
        sequences=[(q['name'], q['kind'], q['begin'], q['end']) for q in tl['sequences']],
        pixelart_timeline_problems=LG.pixelart_timeline_problems(tl),
        pixelart_visibility_problems=LG.pixelart_visibility_problems(tl, alpha),
        atlas_out_of_bounds=oob, bad_names=badname)
# dual mirror sanity: same 9 sequences at identical ticks
m9 = [q for q in sets[False]['timeline']['sequences']]
s9 = sets[True]['timeline']['sequences'][:9]
report['mirror_ok'] = [(a['name'], a['begin'], a['end']) for a in m9] == [(b['name'], b['begin'], b['end']) for b in s9]
report['special_has_land_pose'] = [q['name'] for q in sets[True]['timeline']['sequences'][9:]]
print(json.dumps({k: (v if k in ('mirror_ok', 'special_has_land_pose') else {kk: vv for kk, vv in v.items() if kk != 'sequences'}) for k, v in report.items()}, ensure_ascii=False, indent=1, default=str))

# ---------------- manifest
import hashlib as H
files = []
SALT = __import__('base149').SALT
for fn in sorted(os.listdir(GAME)):
    logical = f'character/seris_dragon_king/pixelart/{fn}'
    b = open(f'{GAME}/{fn}', 'rb').read()
    h = H.sha1((logical + SALT).encode()).hexdigest()
    roots = [r for r in ('upload', 'medium_upload', 'android_upload') if os.path.exists(f'{STORE}/{r}/{h[:2]}/{h[2:]}')]
    prev = {r: {'sha256': H.sha256(open(f'{STORE}/{r}/{h[:2]}/{h[2:]}', 'rb').read()).hexdigest(),
                'size': os.path.getsize(f'{STORE}/{r}/{h[:2]}/{h[2:]}'), 'source': 'store131'} for r in roots}
    files.append({'logical': logical, 'local': os.path.normpath(f'{GAME}/{fn}'), 'roots': roots,
                  'sha256': H.sha256(b).hexdigest(), 'size': len(b), 'replaces_existing': bool(roots), 'previous': prev})
man = {'character': {'id': '129999', 'code': 'seris_dragon_king'},
       'view': 'WF_TIP=206 (store131 + active 1.4.131..1.4.206); 8 pixelart files only live in store131 upload root',
       'design': {'main': 'dragonman = user sprite (13x16 front/back, 17x16 cast pose) on alk_3halfanv timeline skeleton (1-428), scale 6',
                  'special': 'wind_dragon (DB) Seris recolour retimed onto main ticks + DB special_land/special_pose appended'},
       'checks': {k: {kk: vv for kk, vv in v.items() if kk.endswith('problems') or kk in ('atlas_out_of_bounds', 'bad_names')} if isinstance(v, dict) else v for k, v in report.items()},
       'files': files}
json.dump(man, open(OUTF + '/drop_manifest.json', 'w', encoding='utf8'), ensure_ascii=False, indent=1)

# ---------------- previews
os.makedirs(OUTF + '/preview', exist_ok=True)
M, S = sets[False], sets[True]
gif([('Seris dragonman', M)], OUTF + '/preview/dragonman_neutral_walk_skill_kachidoki_ghost.gif', k=4,
    seq_names=('neutral', 'walk_front', 'walk_back', 'skill_ready', 'kachidoki', 'into_coffin', 'ghost_raise', 'ghost_neutral', 'revive'))
gif([('dragonman (main)', M), ('dragon DB (special, same ticks)', S)], OUTF + '/preview/USER+DB_battle_mirror.gif', k=3,
    seq_names=('neutral', 'walk_front', 'walk_back', 'skill_ready', 'kachidoki'))
gif([('special_land + special_pose (join movie)', S)], OUTF + '/preview/USER+DB_join_movie.gif', k=2, seq_names=('special_land', 'special_pose'))

# contact sheet: rows = sequences, keyframes at 1x and 4x
def strip(s, nums, k):
    fm = frame_map(s); ims = [render(s, n, fm) for n in nums]
    bb = None
    for im in ims:
        b = im.getbbox()
        if b: bb = b if bb is None else (min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3]))
    return [im.crop(bb).resize(((bb[2] - bb[0]) * k, (bb[3] - bb[1]) * k), Image.NEAREST) for im in ims]
rows = [
    ('原稿', None, None),
    ('人形 neutral/walk', M, [2, 8, 14, 20, 26, 32, 38, 44, 50]),
    ('人形 skill_ready', M, [52, 58, 64, 70, 76, 82, 88, 94, 100]),
    ('人形 kachidoki', M, [116, 122, 128, 140, 152, 158]),
    ('人形 coffin/ghost/revive', M, [159, 161, 167, 200, 201, 226, 305, 389, 395, 428]),
    ('真龙DB neutral/walk(同帧号)', S, [2, 8, 14, 20, 26, 32, 38, 44, 50]),
    ('真龙DB skill_ready', S, [52, 58, 64, 70, 76, 82, 88, 94, 100]),
    ('获取演出 land/pose', S, [433, 470, 520, 560, 575, 600]),
]
blocks = []
for title, s, nums in rows:
    if s is None:
        ims = [snapimg for snapimg in []]
        ref = [Image.open(SR + f'/ref_fig{i}.png').convert('RGBA') for i in range(4)]
        one = ref; four = [r.resize((r.size[0] * 4, r.size[1] * 4), Image.NEAREST) for r in ref]
    else:
        one = strip(s, nums, 1); four = strip(s, nums, 4 if title.startswith('人形') or 'neutral' in title else 2)
    blocks.append((title, one, four))
W = 0; H = 0
for t, one, four in blocks:
    W = max(W, 330 + sum(i.size[0] + 4 for i in one) + 20 + sum(i.size[0] + 6 for i in four))
    H += max(max(i.size[1] for i in four), 60) + 30
C = Image.new('RGBA', (W + 20, H + 90), GREY); d = ImageDraw.Draw(C)
d.text((12, 8), '最终像素 · 用户人形 + DB 真龙', font=F_BIG, fill=(255, 255, 80, 255))
y = 80
for t, one, four in blocks:
    hh = max(max(i.size[1] for i in four), 60)
    d.text((12, y + 4), t, font=F_MID, fill=(255, 255, 255, 255))
    x = 330
    for i in one: C.alpha_composite(i, (x, y + 24)); x += i.size[0] + 4
    x += 20
    for i in four: C.alpha_composite(i, (x, y + 24)); x += i.size[0] + 6
    y += hh + 30
C.convert('RGB').save(OUTF + '/最终像素-用户人形+DB.png')
print('done', C.size)
