"""盾牌座青绿技能图集；直接改 RGB，保留官方透明度、几何与时序。"""
import colorsys
import hashlib
from io import BytesIO
import zlib

from PIL import Image

import wf_dsl
from wf_assets import png_decode, png_encode
from wf_character_revision import encode_tree

SOURCE_CODE, CODE = 'prince_zero', 'scutum_valentine'
SOURCE = f'battle/effect/skill_unique/{SOURCE_CODE}/{SOURCE_CODE}'
TARGET = f'battle/effect/skill_unique/{CODE}/{CODE}'
SUFFIXES = ('.png', '.atlas.amf3.deflate', '.parts.amf3.deflate', '.timeline.amf3.deflate')
# Gold/orange ribbons become green; cyan/blue accents become teal. Preserve S/V.
HUE_STOPS = ((0, 110), (90, 150), (180, 160), (270, 170), (360, 110))


def remap(value):
    if isinstance(value, str):
        return value.replace(SOURCE_CODE, CODE)
    if isinstance(value, list):
        return [remap(item) for item in value]
    if isinstance(value, dict):
        return {remap(key): remap(item) for key, item in value.items()}
    return value


def remap_parts(tree):
    expected = {'t': 66, 's': [{'s': -2147483648.0, 'i': 1,
        'l': [{'m': 255, 't': 66, 'r': 1073741824.0}]}]}
    if not isinstance(tree, dict) or tree.get('g', [None])[0] != expected:
        raise ValueError('prince_zero root topology changed')
    if tree.get('m') != []:
        raise ValueError('unexpected movie resource')
    if any('c' in frame for graphic in tree['g'] for segment in graphic['s'] for frame in segment['l']):
        raise ValueError('source already contains a colour transform')
    # BattleDefaultMeshStyle ignores Flatomo c callbacks. Do not add that field:
    # baking the palette works in battle and avoids a second tint in UI previews.
    return remap(tree)


def tint_rgb(rgb):
    hue, saturation, value = colorsys.rgb_to_hsv(*(channel / 255 for channel in rgb))
    if saturation == 0:
        return rgb  # White glints and black additive-blend edges keep their level.
    hue *= 360
    for (left, a), (right, b) in zip(HUE_STOPS, HUE_STOPS[1:]):
        if hue <= right:
            mapped = a + (b - a) * (hue - left) / (right - left)
            return tuple(round(channel * 255) for channel in
                         colorsys.hsv_to_rgb(mapped / 360, saturation, value))
    raise ValueError('invalid source hue')


def tint_png(raw):
    with Image.open(BytesIO(png_decode(raw))) as image:
        if image.mode != 'RGBA' or image.size != (298, 123):
            raise ValueError('prince_zero texture layout changed')
        pixels = list(image.getdata())
        palette = {pixel[:3]: tint_rgb(pixel[:3]) for pixel in set(pixels) if pixel[3]}
        output = Image.new('RGBA', image.size)
        output.putdata([(*palette[pixel[:3]], pixel[3]) if pixel[3] else pixel for pixel in pixels])
        if output.getchannel('A').tobytes() != image.getchannel('A').tobytes():
            raise ValueError('effect alpha changed')
        buffer = BytesIO()
        output.save(buffer, format='PNG')
    return png_encode(buffer.getvalue())


def assets(official_loader):
    outputs = {}
    for suffix in SUFFIXES:
        raw = official_loader(SOURCE + suffix)
        if suffix == '.png':
            output = tint_png(raw)
        elif suffix == '.timeline.amf3.deflate':
            output = raw
        else:
            tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']
            output = encode_tree(remap_parts(tree) if suffix == '.parts.amf3.deflate' else remap(tree))
        outputs['common', TARGET + suffix] = output
    return outputs


def build(seed):
    outputs = assets(seed.official)
    for (tier, logical), raw in outputs.items():
        seed.emit(tier, logical, raw)
    return {**metadata(), 'assets': [dict(root=tier, logical_path=logical,
                sha256=hashlib.sha256(raw).hexdigest()) for (tier, logical), raw in outputs.items()]}


def metadata():
    return dict(source=SOURCE, target=TARGET, colour_method='baked_rgb_hue_palette',
                hue_stops=HUE_STOPS, source_png_bytes_unchanged=False,
                alpha_bytes_unchanged=True, atlas_rectangles_unchanged=True,
                timeline_bytes_unchanged=True, alpha_blend_geometry_unchanged=True,
                frame_count=66, requires_new_apk=False,
                fixed_rgb_probes=[{'input': list(rgb), 'output': list(tint_rgb(rgb))}
                                  for rgb in ((255,255,255),(255,185,83),(51,190,234),(0,0,0))])
