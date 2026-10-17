"""Kyle PF: native Targis layered tweens, original perspective, API palette."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

import wf_flatomo_capacity as capacity
import wf_generated_vfx as vfx
import wf_seasonal7_common as common

DIRECTORY = 'battle/effect/skill_unique/kyle_moon/pf_thunder_ring'
SHEET = DIRECTORY + '/pf_thunder_ring'
SOURCE = Path('work/character_packs/midautumn-20260920/rework3/fx/kyle_pf_native')
DONOR = 'starbreak_hunter_meteor23'
PARTS = DONOR + '_explosion.parts.amf3.deflate'
PARTS_SHA = '247ecf7011bdddd9ec26b89b9964170ee4044467fbdbcf0c8487236172876afd'
KEEP = frozenset(('a','b','c','d','e','f','g','h','r','s','t','w','x','y','aa','ab','ac'))
LIFETIMES = (60, 68, 75)
# Native frames 0..12 charge the removed ball; the useful border fades by 60.
BEGIN, END = 13, 60


def effect(level):
    if level not in (1, 2, 3):
        raise ValueError('PF level must be 1, 2 or 3')
    return f'{DIRECTORY}/ring_lv{level}'


def _signed(value):
    return value - 2**32 if value >= 2**31 else value


def filtered_native(raw):
    """Remove orb leaves/charge strips, retaining all native border transforms."""
    if hashlib.sha256(raw).hexdigest() != PARTS_SHA:
        raise ValueError('Targis animation donor changed')
    parts = common.amf_parse(raw)
    keep = {n for n, item in enumerate(parts['i']) if item['p'].split('/')[-1] in KEEP}
    for group in parts['g']:
        group['s'] = [s for s in group['s'] if (int(s['s']) & 0xffffffff) >> 30 or s['i'] in keep]
    # The first child is the explosion graph; the other strips charge its core.
    parts['g'][1]['s'] = parts['g'][1]['s'][:1]
    need = capacity.image_capacities(parts)
    used = [i for i, n in enumerate(need) if n]
    remap = {old: new for new, old in enumerate(used)}
    for group in parts['g']:
        group['s'] = [s for s in group['s'] if (int(s['s']) & 0xffffffff) >> 30 or s['i'] in remap]
        for strip in group['s']:
            if (int(strip['s']) & 0xffffffff) >> 30 == 0:
                strip['i'] = remap[strip['i']]
    parts['i'] = [parts['i'][i] for i in used]
    parts['a'] = [need[i] for i in used]
    return parts


def native_animation(frames, donor=None):
    """Retime native nested tweens, not rendered frames or a rotated still."""
    if frames not in LIFETIMES:
        raise ValueError('unsupported Kyle PF lifetime')
    if donor is None:
        donor = (Path(__file__).resolve().parents[1] / SOURCE / PARTS).read_bytes()
    parts = filtered_native(donor)
    scale = lambda time: round(time * frames / (END - BEGIN))
    for group in parts['g']:
        group['t'] = scale(group['t'])
        for strip in group['s']:
            bits = int(strip['s']) & 0xffffffff
            cursor = bits & 0x3fffffff
            strip['s'] = _signed((bits & 0xc0000000) | scale(cursor))
            for key in strip['l']:
                timing = int(key.get('t') or 1)
                end = cursor + (timing & 0xffff)
                key['t'] = (timing & ~0xffff) | (scale(end) - scale(cursor))
                if 'r' in key:
                    ref = int(key['r']) & 0xffffffff
                    key['r'] = _signed((ref & 0xc0000000) | scale(ref & 0x3fffffff))
                cursor = end
    # Same native uniform root matrix. No global spin, aspect correction, new
    # perspective matrix or per-frame raster. The last key closes the once clip.
    parts['g'][0] = {'t': frames, 's': [{'s': -2147483648, 'i': 1, 'l': [
        {'m': 0, 't': 16646148, 'r': 0x40000000 | scale(BEGIN)},
        {'m': 255, 't': frames-5, 'r': 0x40000000 | (scale(BEGIN)+4)},
        {'m': 0, 't': 1, 'r': 0x40000000 | (scale(BEGIN)+frames-1)}]}]}
    for item in parts['i']:
        item['p'] = f"{DIRECTORY}/.gen/native/{item['p'].split('/')[-1]}"
    parts['a'] = capacity.image_capacities(parts)
    capacity.validate_image_capacities(parts)
    timeline = {'sequences': [{'begin': 1, 'end': frames, 'name': 'neutral', 'kind': 'once'}],
                'sounds': [], 'points': [], 'circles': [], 'rectangles': [], 'matrices': []}
    return parts, timeline


def _sprites(source, names):
    atlas = common.amf_parse((source/(DONOR+'.atlas.amf3.deflate')).read_bytes())
    entries = {item['n']: item for item in atlas}
    sheet = Image.open(source/'palette-atlas.png').convert('RGBA')
    images = []
    for name in names:
        entry = entries[name]; x, y, w, h = (entry[k] for k in ('x','y','w','h'))
        tile = sheet.crop((x, y, x+w, y+h))
        if entry.get('r'): tile = tile.transpose(Image.Transpose.ROTATE_90)
        frame = Image.new('RGBA', (entry.get('fw', tile.width), entry.get('fh', tile.height)))
        frame.alpha_composite(tile, (-entry.get('fx', 0), -entry.get('fy', 0)))
        images.append(frame)
    return images


def build_assets(root):
    source = Path(root) / SOURCE
    receipt = json.loads((source/'accepted.json').read_bytes())
    hashes = {**receipt['files'], 'palette-atlas.png': receipt['palette_atlas_sha256'],
              'api-blue-white.png': receipt['api_sha256']}
    for name, digest in hashes.items():
        if hashlib.sha256((source/name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'native/API source changed: {name}')
    raw = (source/PARTS).read_bytes()
    native = filtered_native(raw)
    names = [f"{DIRECTORY}/.gen/native/{i['p'].split('/')[-1]}" for i in native['i']]
    packed, atlas = vfx.pack_images(_sprites(source, [i['p'] for i in native['i']]), names, trim=True)
    assets = {SHEET+'.png': common.png_store_bytes(packed),
              SHEET+'.atlas.amf3.deflate': common.amf_bytes(atlas)}
    for level, lifetime in enumerate(LIFETIMES, 1):
        parts, timeline = native_animation(lifetime, raw)
        assets[effect(level)+'.parts.amf3.deflate'] = common.amf_bytes(parts)
        assets[effect(level)+'.timeline.amf3.deflate'] = common.amf_bytes(timeline)
    import wf_kyle_pf_hit as hit
    parts, timeline = hit.animation(native, DIRECTORY)
    assets[hit.effect(DIRECTORY)+'.parts.amf3.deflate'] = common.amf_bytes(parts)
    assets[hit.effect(DIRECTORY)+'.timeline.amf3.deflate'] = common.amf_bytes(timeline)
    return assets, {'source': str(SOURCE), 'api': receipt, 'atlas_size': list(packed.size),
                    'lifetimes': list(LIFETIMES), 'native_groups': len(native['g']),
                    'native_matrices': len(native['t']), 'native_easing': len(native['c']),
                    'native_window': [BEGIN, END], 'whole_image_rotation': False,
                    'native_perspective_preserved': True, 'core_sprites_removed': True,
                    'hit_residue_frames': hit.FRAMES, 'hit_residue_reuses_atlas': True,
                    'image_names': [i['p'].split('/')[-1] for i in native['i']]}
