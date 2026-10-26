"""夏日白绿衣像素：恢复雷白原生动作节奏，保留七个战斗兼容动作。"""
from copy import deepcopy
from io import BytesIO
import hashlib
import zlib

from PIL import Image

from wf_assets import png_decode, png_encode
from wf_character_revision import encode_tree
from wf_dsl import parse_dsl
from wf_generated_vfx import pack_images
from wf_pixelart_vfx import entry_for_frame, frame_index, restore_frame

CODE = 'white_tiger_summer'
DONOR = 'white_tiger_2anv'
KINDS = ('pixelart', 'special')
FALLBACK = ('wince_ready', 'stun_ready', 'attack_initial', 'attack_charge',
            'attack_action', 'attack_fire', 'dead')
# 作者 2026-09-10 选定的绿衣映射；毛色、黑线及透明度不在映射内。
PALETTE = {
    (16, 24, 91): (34, 59, 37), (19, 28, 91): (34, 59, 37),
    (23, 35, 136): (57, 88, 51), (44, 54, 148): (105, 133, 75),
    (52, 75, 166): (105, 133, 75), (70, 103, 174): (159, 181, 119),
    (70, 108, 187): (159, 181, 119), (84, 114, 190): (215, 222, 176),
}
EXPECTED = {'pixelart': (747, 430), 'special': (236, 220)}


def _tree(raw):
    return parse_dsl(zlib.decompress(raw, -15))['tree']


def _recolor(image):
    result = image.copy()
    result.putdata([(*PALETTE.get(p[:3], p[:3]), p[3]) if p[3] else p
                    for p in image.getdata()])
    return result


def decode_family(loader, code, kind, *, recolor=False):
    """按原生 END suffix 展开每个 tick，拒绝空引用、重复末帧和错误锚点。"""
    if kind not in KINDS:
        raise ValueError('unknown pixel family')
    prefix = f'character/{code}/pixelart/'
    stem = 'sprite_sheet' if kind == 'pixelart' else 'special_sprite_sheet'
    names = (stem + '.png', stem + '.atlas.amf3.deflate',
             kind + '.frame.amf3.deflate', kind + '.timeline.amf3.deflate')
    raw = {name: loader(prefix + name) for name in names}
    frame, timeline = (_tree(raw[names[n]]) for n in (2, 3))
    if frame != {'name': prefix + kind, 'x': -128, 'y': -128,
                 'scale': 6, 'smoothing': False}:
        raise ValueError('pixel identity or anchor changed')
    atlas = _tree(raw[names[1]])
    index = frame_index(atlas, frame['name'])
    if len(index[0]) != len(atlas):
        raise ValueError('foreign atlas frame prefix')
    sequences = timeline['sequences']
    cursor = 1
    seen = set()
    for seq in sequences:
        if seq['name'] in seen or seq['begin'] != cursor or seq['end'] < cursor:
            raise ValueError('sequence gap, overlap or duplicate')
        seen.add(seq['name'])
        cursor = seq['end'] + 1
    if index[0][-1] != cursor - 1:
        raise ValueError('atlas final END suffix differs from timeline')
    with Image.open(BytesIO(png_decode(raw[names[0]]))) as image:
        sheet = image.convert('RGBA')
    if recolor:
        sheet = _recolor(sheet)
    cache = {entry['n']: restore_frame(sheet, entry) for entry in atlas}
    frames = [cache[entry_for_frame(index, n)['n']] for n in range(1, cursor)]
    return dict(raw=raw, frame=frame, timeline=timeline, atlas=atlas,
                frames=frames, stem=stem, prefix=prefix)


def marker_at(timeline, section, path, frame):
    groups = [group for group in timeline.get(section, []) if group['path'] == path]
    if len(groups) > 1:
        raise ValueError('duplicate marker path')
    value = []
    previous = 0
    for key in groups[0]['frames'] if groups else []:
        if key['begin'] <= previous:
            raise ValueError('marker keys must increase')
        previous = key['begin']
        if key['begin'] <= frame:
            value = key['data']
    return value


def _markers(segments, section):
    """拷贝各原序列的 marker 相对位置；必要时显式恢复跨序列携带状态。"""
    paths = list(dict.fromkeys(g['path'] for src, _, _ in segments
                              for g in src['timeline'].get(section, [])))
    result = []
    for path in paths:
        keys, previous = [], []
        for source, seq, new in segments:
            tl = source['timeline']
            src_keys = next((g['frames'] for g in tl.get(section, [])
                             if g['path'] == path), [])
            local = [k for k in src_keys if seq['begin'] <= k['begin'] <= seq['end']]
            initial = marker_at(tl, section, path, seq['begin'])
            if initial != previous and not (local and local[0]['begin'] == seq['begin']):
                keys.append(dict(begin=new['begin'], data=deepcopy(initial)))
            for key in local:
                keys.append({**deepcopy(key), 'begin': new['begin'] + key['begin'] - seq['begin']})
            previous = marker_at(tl, section, path, seq['end'])
        result.append(dict(path=path, frames=keys))
    return result


def retime_family(current, donor, kind):
    """迁移只接受已发布的线性采样版，拒绝覆盖未知后续绘制。"""
    if (len(current['frames']), len(donor['frames'])) != EXPECTED[kind]:
        raise ValueError('unexpected installed or donor timeline length')
    donor_by = {s['name']: s for s in donor['timeline']['sequences']}
    current_names = [s['name'] for s in current['timeline']['sequences']]
    expected = list(donor_by) + (list(FALLBACK) if kind == 'pixelart' else [])
    if current_names != expected:
        raise ValueError('unexpected compatibility sequence inventory')
    frames, segments, sequences, cursor = [], [], [], 1
    memo = {}
    def pixels(im):
        key = id(im)
        if key not in memo:
            memo[key] = im.tobytes()
        return memo[key]
    for old in current['timeline']['sequences']:
        seq = donor_by.get(old['name'], old)
        source = donor if old['name'] in donor_by else current
        if old['kind'] != seq['kind']:
            raise ValueError('sequence playback kind drift')
        selected = source['frames'][seq['begin'] - 1:seq['end']]
        n = old['end'] - old['begin'] + 1
        if source is donor:
            for offset, actual in enumerate(current['frames'][old['begin'] - 1:old['end']]):
                index = round(offset * (len(selected) - 1) / (n - 1)) if n > 1 else 0
                if pixels(actual) != pixels(selected[index]):
                    raise ValueError('installed green poses differ from known author-selected palette')
        new = {**deepcopy(seq), 'begin': cursor, 'end': cursor + len(selected) - 1}
        sequences.append(new)
        segments.append((source, seq, new))
        frames.extend(selected)
        cursor = new['end'] + 1
    timeline = deepcopy(current['timeline'])
    timeline['sequences'] = sequences
    for section in ('circles', 'points', 'sounds'):
        timeline[section] = _markers(segments, section)
    return frames, timeline, segments


def assets(existing_loader, official_loader):
    """返回八个 common 私有文件；不读写包、live、CDN 或角色表。"""
    outputs = {}
    for kind in KINDS:
        current = decode_family(existing_loader, CODE, kind)
        donor = decode_family(official_loader, DONOR, kind, recolor=True)
        frames, timeline, _ = retime_family(current, donor, kind)
        hashes = [hashlib.sha256(im.tobytes()).digest() for im in frames]
        ends = [n for n in range(len(frames)) if n == len(frames) - 1 or hashes[n] != hashes[n + 1]]
        names = [current['frame']['name'] + f'{n + 1:04d}' for n in ends]
        sheet, atlas = pack_images([frames[n] for n in ends], names, trim=True,
                                   dedup=True, max_width=None)
        buffer = BytesIO()
        sheet.save(buffer, format='PNG')
        prefix, stem = current['prefix'], current['stem']
        outputs['common', prefix + stem + '.png'] = png_encode(buffer.getvalue())
        outputs['common', prefix + stem + '.atlas.amf3.deflate'] = encode_tree(atlas)
        outputs['common', prefix + kind + '.frame.amf3.deflate'] = current['raw'][kind + '.frame.amf3.deflate']
        outputs['common', prefix + kind + '.timeline.amf3.deflate'] = encode_tree(timeline)
    return outputs


def metadata():
    return dict(code=CODE, donor=DONOR, palette='author-selected green, 2026-09-10',
                cadence_ticks={'skill_ready': [236, 62], 'special_land': [187, 189],
                               'special_pose': [49, 31]},
                before_total_ticks=983, after_total_ticks=793,
                fallback_sequences=list(FALLBACK), fallback_pixels_and_timing_preserved=True,
                anchors_and_scale_preserved=True, gameplay_dsl_unchanged=True,
                new_poses_invented=False, requires_new_apk=False)
