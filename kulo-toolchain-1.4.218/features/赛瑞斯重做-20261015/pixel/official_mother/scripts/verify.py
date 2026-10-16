from frames import *
from preview import gif
import glob
REQ9 = ['neutral', 'walk_back', 'walk_front', 'skill_ready', 'kachidoki', 'into_coffin', 'ghost_raise', 'ghost_neutral', 'revive']

def load_dir(d, special):
    sheet = 'special_sprite_sheet' if special else 'sprite_sheet'; fr = 'special' if special else 'pixelart'
    b = bytearray(open(f'{d}/{sheet}.png', 'rb').read()); assert b[1:4] == b'png'; b[1:4] = b'PNG'
    im = Image.open(io.BytesIO(bytes(b))).convert('RGBA')
    rd = lambda p: core.AMF3Reader(zlib.decompress(open(p, 'rb').read(), -15)).read_value()
    return dict(sheet=im, atlas=rd(f'{d}/{sheet}.atlas.amf3.deflate'), frame=rd(f'{d}/{fr}.frame.amf3.deflate'),
                timeline=rd(f'{d}/{fr}.timeline.amf3.deflate'))

problems = []
for d in sorted(glob.glob(OUT + '/sets/*/*')) + sorted(glob.glob(OUT + '/dual_form/*/special')):
    d = d.replace('\\', '/')
    sp = d.endswith('/special')
    s = load_dir(d, sp)
    names = [e['n'] for e in s['atlas']]
    pre = f'character/seris_dragon_king/pixelart/{"special" if sp else "pixelart"}'
    bad = [n for n in names if not n.startswith(pre)]
    if bad: problems.append((d, 'bad names', bad[:3]))
    if s['frame']['name'] != pre or s['frame']['scale'] != 6: problems.append((d, 'frame', s['frame']))
    for e in s['atlas']:
        W, H = e['w'], e['h']
        if e['x'] + W > s['sheet'].size[0] or e['y'] + H > s['sheet'].size[1]: problems.append((d, 'oob', e['n']))
    sq = seqs(s); fm = frame_map(s)
    for q, (b, e) in sq.items():
        if frame_at(s, b, fm) is None: problems.append((d, 'no frame at begin', q))
    if sp:
        miss = [n for n in ['special_land', 'special_pose'] if n not in sq]
        if miss: problems.append((d, 'missing', miss))
    print(d.split('official_mother/')[1], s['sheet'].size, len(names), list(sq))
print('PROBLEMS', problems)

# dual-form gifs: humanoid main vs dragon special at the SAME absolute ticks + special_land/pose
for dd in sorted(glob.glob(OUT + '/dual_form/*')):
    dd = dd.replace('\\', '/'); pair = os.path.basename(dd); h = pair.split('+')[0]
    hd = glob.glob(f'{OUT}/sets/{h}_*/main')[0].replace('\\', '/')
    hs = load_dir(hd, False); ds = load_dir(dd + '/special', True)
    gif([('Seris human (main)', hs), ('Seris dragon (special, same ticks)', ds)], f'{OUT}/preview/dual_{pair}_battle_mirror.gif',
        seq_names=('neutral', 'walk_front', 'walk_back', 'skill_ready', 'kachidoki'))
    gif([('special_land + special_pose', ds)], f'{OUT}/preview/dual_{pair}_join_movie.gif', k=2, seq_names=('special_land', 'special_pose'))
print('gifs ok')
