"""Apply the author's native summer Bai reference without retiming animation.

The input reference is recovered by the Retro Diffusion pixel-fixer API.
Idle is copied exactly; the remaining native poses inherit its palette.
This module returns candidate PNGs only and never publishes or writes live data.
"""
from collections import Counter, defaultdict
from io import BytesIO

from PIL import Image

from wf_assets import png_decode, png_encode
from wf_summer_bai_pixels import CODE, KINDS, decode_family


def palette_from_reference(source, target):
    if source.size != target.size:
        raise ValueError('reference and idle native sizes differ')
    votes = defaultdict(Counter)
    for a, b in zip(source.getdata(), target.getdata()):
        if a[3] and b[3]:
            votes[a[:3]][b[:3]] += 1
    return {color: counts.most_common(1)[0][0] for color, counts in votes.items()}


def build(loader, reference_png):
    target = Image.open(BytesIO(reference_png)).convert('RGBA')
    if target.size != (32, 32) or not target.getbbox():
        raise ValueError('expected the reviewed API 32x32 reference')
    target = target.crop(target.getbbox())
    families = {kind: decode_family(loader, CODE, kind) for kind in KINDS}
    front = families['pixelart']
    neutral = next(s for s in front['timeline']['sequences'] if s['name'] == 'neutral')
    idle = front['frames'][neutral['begin'] - 1]
    idle_crop = idle.crop(idle.getbbox())
    palette = palette_from_reference(idle_crop, target)
    # Clothes have additional shades in turning/attack frames, absent from idle.
    palette.update({(57, 88, 51): (112, 131, 85),
                    (215, 222, 176): (255, 255, 255)})
    outputs, reports = {}, []
    for kind, family in families.items():
        stem = family['stem'] + '.png'
        sheet = Image.open(BytesIO(png_decode(family['raw'][stem]))).convert('RGBA')
        mapped = sheet.copy()
        # Unrecognized shades can belong to embedded spark/ghost animation.
        # Preserve them rather than inventing a nearest-color replacement.
        mapped.putdata([(*palette.get(p[:3], p[:3]), p[3]) if p[3] else p
                        for p in sheet.getdata()])
        exact = 0
        for entry in family['atlas']:
            x, y, w, h = (int(entry[k]) for k in ('x', 'y', 'w', 'h'))
            cell = sheet.crop((x, y, x+w, y+h))
            if entry.get('r'):
                cell = cell.transpose(Image.Transpose.ROTATE_90)
            if cell.size == idle_crop.size and cell.tobytes() == idle_crop.tobytes():
                replacement = target
                if entry.get('r'):
                    replacement = replacement.transpose(Image.Transpose.ROTATE_270)
                mapped.paste(replacement, (x, y))
                exact += 1
        if mapped.size != sheet.size:
            raise ValueError('atlas dimensions changed')
        data = BytesIO()
        mapped.save(data, format='PNG')
        outputs[family['prefix'] + stem] = png_encode(data.getvalue())
        reports.append(dict(kind=kind, ticks=len(family['frames']),
                            sequences=len(family['timeline']['sequences']),
                            atlas_size=list(sheet.size), exact_idle_cells=exact))
    after = decode_family(lambda name: outputs.get(name, loader(name)), CODE, 'pixelart')
    got = after['frames'][neutral['begin'] - 1]
    if got.crop(got.getbbox()).tobytes() != target.tobytes():
        raise ValueError('idle does not match the author reference exactly')
    return outputs, dict(families=reports, atlas_and_timeline_unchanged=True,
                         method='API grid recovery; exact idle; palette-adapted native poses')
