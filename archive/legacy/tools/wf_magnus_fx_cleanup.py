"""只修改狮子克隆演出的编排：去枪体，统一降低爆炸不透明度。"""
from copy import deepcopy

BURST_ALPHA = 140  # 140/255 = 55%; keep native interpolation/fade.
WEAPON_LEAVES = {'zeta_lance': 'g', 'zeta_lance_end': 'b'}


def remove_weapon(parts, name):
    out = deepcopy(parts)
    suffix = '/' + name + '/' + WEAPON_LEAVES[name]
    indices = {i for i, image in enumerate(out['i']) if image['p'].endswith(suffix)}
    if len(indices) != 1:
        raise ValueError('expected exactly one verified Zeta weapon image')
    removed = 0
    for group in out['g']:
        keep = []
        for strip in group['s']:
            kind = (int(strip['s']) & 0xffffffff) >> 30
            if kind == 0 and int(strip['i']) in indices:
                removed += 1
            else:
                keep.append(strip)
        group['s'] = keep
    if not removed:
        raise ValueError('no weapon drawing instance found')
    return out, {'weapon_leaf': suffix, 'removed_strips': removed}


def soften_burst(parts):
    out = deepcopy(parts)
    root = out['g'][0]
    if len(root['s']) != 1 or len(root['s'][0]['l']) != 1:
        raise ValueError('unexpected burst root animation')
    key = root['s'][0]['l'][0]
    packed = int(key['m']) & 0xffffffff
    if packed & 255 != 255:
        raise ValueError('burst root was already dimmed')
    key['m'] = (packed & ~255) | BURST_ALPHA
    return out


def apply_cloned(ctx):
    """Called after the official clone and burst timeline surgery on every rebuild."""
    from wf_character_revision import encode_tree
    import wf_dsl, zlib
    root = 'battle/effect/skill_unique/lion_swordman_moon/'
    report = {}
    for folder, name in [('lance', 'zeta_lance'), ('lance_end', 'zeta_lance_end'), ('burst', 'clarisse')]:
        logical = root + folder + '/' + name + '.parts.amf3.deflate'
        path = ctx.pack.pkg_path('common', logical)
        parts = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))['tree']
        if name == 'clarisse':
            parts = soften_burst(parts)
            report[name] = {'root_alpha': BURST_ALPHA}
        else:
            parts, report[name] = remove_weapon(parts, name)
            from wf_magnus_pf_orbit import shift_cone
            parts = shift_cone(parts)
        # emit through pack so ownership, hashes and provenance are refreshed.
        ctx.write_asset('common', logical, encode_tree(parts))
    return report
