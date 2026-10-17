"""将校园配色编译至原生奈芙图集；不重绘、不重排、不修改动画。"""
from __future__ import annotations

import json
import zlib
from collections import Counter

from PIL import Image

import wf_campus_nephtim_common as C
import wf_dsl
import wf_pixelart_vfx as native

OUT = C.ROOT / 'work/codex_out/campus-trio-20260911/nephtim'
PIXEL = C.pkg_path('common', f'character/{C.CODE}/pixelart')
STEMS = {'sprite_sheet': 'pixelart', 'special_sprite_sheet': 'special'}

# imagegen 产出的 palette-imagegen.png 只作为配色参考；游戏资产使用确定性 RGB LUT。
# 保留所有棕肤、眼睛、头发及黑色轮廓。与皮肤共用颜色的金饰也保留。
PROTECTED = {
    (0, 0, 0), (27, 7, 27), (93, 83, 137), (67, 49, 102),
    (78, 65, 107), (72, 55, 105), (107, 78, 106), (95, 67, 95),
    (205, 124, 45), (223, 171, 83), (213, 144, 69), (225, 173, 121),
    (114, 0, 0), (181, 82, 0), (184, 87, 35), (73, 44, 0),
    (213, 153, 122), (247, 227, 197), (237, 203, 155),
}


def rgb(hex_color):
    return tuple(bytes.fromhex(hex_color.lstrip('#')))


# 按官方原色逐项映射；不使用模糊 hue 范围，避免把棕肤误认为金色。
PALETTE = {source: rgb(target) for source, target in {
    (243, 235, 205): 'D5F2E7', (255, 247, 232): 'EFFBF5',
    (237, 217, 177): 'A4DECA', (228, 198, 153): '6ABEA5',
    (123, 103, 122): '614492', (255, 172, 50): '9566D0',
    (255, 242, 172): 'D5F2E7', (245, 190, 78): 'AD8BDD',
    (255, 225, 88): 'C9B1ED', (255, 202, 75): 'B493E1',
    (255, 215, 97): 'C1A6E8', (255, 255, 255): 'E9E0F8',
    (227, 227, 227): 'C9B1ED', (212, 212, 212): 'AD8BDD',
    (201, 201, 201): '9566D0', (189, 189, 189): '805BB6',
    (138, 138, 138): '614492', (79, 79, 79): '3B285C',
    (46, 46, 46): '241A35', (148, 148, 148): '3D8274',
    (168, 167, 172): '214A47', (243, 243, 255): 'A4DECA',
}.items()}
assert not PROTECTED & PALETTE.keys()


def recolor(original):
    """改变显色像素的 RGB；所有 alpha 值和透明区 RGB 均逐字节保留。"""
    result = original.copy()
    result.putdata([(*PALETTE.get(p[:3], p[:3]), p[3]) if p[3] else p
                    for p in original.get_flattened_data()])
    return result


def check_pixels(original, result):
    if original.size != result.size:
        raise ValueError('sheet dimensions changed')
    before, after = list(original.get_flattened_data()), list(result.get_flattened_data())
    if original.getchannel('A').tobytes() != result.getchannel('A').tobytes():
        raise ValueError('alpha changed')
    protected = 0
    for p, q in zip(before, after):
        if not p[3] or p[:3] in PROTECTED:
            protected += 1
            if p != q:
                raise ValueError('skin/hair/outline/transparent pixel changed')
        expected = (*PALETTE.get(p[:3], p[:3]), p[3]) if p[3] else p
        if q != expected:
            raise ValueError('non-palette pixel change')
    changed = sum(p != q for p, q in zip(before, after))
    if not changed:
        raise ValueError('no actual recolor')
    counts = Counter(p[:3] for p, q in zip(before, after) if p != q)
    return dict(size=list(original.size), changed_pixels=changed,
                protected_pixels=protected, alpha_sha256=C.sha256(original.getchannel('A').tobytes()),
                changed_source_colors={str(k): v for k, v in sorted(counts.items())})


def read_tree(name):
    return wf_dsl.parse_dsl(zlib.decompress((PIXEL / name).read_bytes(), -15))['tree']


def check_frames(original, result, stem, kind):
    atlas = read_tree(f'{stem}.atlas.amf3.deflate')
    frame = read_tree(f'{kind}.frame.amf3.deflate')
    timeline = read_tree(f'{kind}.timeline.amf3.deflate')
    index = native.frame_index(atlas, frame['name'])
    total = max(s['end'] for s in timeline['sequences'])
    # 验证全部 atlas 条目，包括其他动画前缀及旋转切片。
    for entry in atlas:
        first, second = (native.restore_frame(im, entry) for im in [original, result])
        if first.size != second.size or first.getchannel('A').tobytes() != second.getchannel('A').tobytes():
            raise ValueError('restored atlas geometry changed')
    # 按原生 END frame 语义逐个 tick 解析，验证全部动作边界和帧号都可还原。
    for number in range(1, total + 1):
        entry = native.entry_for_frame(index, number)
        first, second = (native.restore_frame(im, entry) for im in [original, result])
        if first.getchannel('A').tobytes() != second.getchannel('A').tobytes():
            raise ValueError('timeline frame alpha changed')
    return dict(atlas_entries=len(atlas), timeline_ticks=total,
                endpoint_count=len(index[0]), sequences=timeline['sequences'])


def preview(original, result, stem):
    for label, im in [('before', original), ('after', result)]:
        im.resize((im.width * 4, im.height * 4), Image.Resampling.NEAREST).save(
            OUT / f'{stem}-{label}-4x.png')
    pair = Image.new('RGBA', (original.width * 2, original.height), '#302b3b')
    pair.alpha_composite(original, (0, 0))
    pair.alpha_composite(result, (original.width, 0))
    pair.resize((pair.width * 4, pair.height * 4), Image.Resampling.NEAREST).save(
        OUT / f'{stem}-before-after-4x.png')


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    metadata = {p.name: C.sha256(p.read_bytes()) for p in PIXEL.glob('*.deflate')}
    report = {'method': 'imagegen palette study + deterministic native RGB palette compilation',
              'palette_reference': str(OUT / 'palette-imagegen.png'),
              'metadata_before': metadata, 'sheets': {}, 'package_files_changed': []}
    for stem, kind in STEMS.items():
        source_raw = C.store_read(f'character/{C.TMPL_CODE}/pixelart/{stem}.png')
        original = C.png_open(source_raw)
        result = recolor(original)
        checks = check_pixels(original, result)
        checks.update(check_frames(original, result, stem, kind))
        encoded = C.png_store_bytes(result)
        if C.png_open(encoded).tobytes() != result.tobytes():
            raise ValueError('native PNG roundtrip changed pixels')
        checks.update(source_sha256=C.sha256(source_raw), output_sha256=C.sha256(encoded),
                      output_bytes=len(encoded), alpha_changed_pixels=0,
                      protected_changed_pixels=0, geometric_changes=0)
        result.save(OUT / f'{stem}-recolored.png')
        preview(original, result, stem)
        (PIXEL / f'{stem}.png').write_bytes(encoded)
        report['package_files_changed'].append(str(PIXEL / f'{stem}.png'))
        report['sheets'][stem] = checks
    report['metadata_after'] = {p.name: C.sha256(p.read_bytes()) for p in PIXEL.glob('*.deflate')}
    if report['metadata_after'] != metadata:
        raise ValueError('native metadata changed')
    target = OUT / 'pixel-recolor-verification.json'
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', 'utf-8')
    return report


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False, indent=2))
