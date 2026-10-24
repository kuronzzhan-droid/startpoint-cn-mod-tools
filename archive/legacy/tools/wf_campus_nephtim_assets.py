"""复制原生像素/语音及隔离特效；原角色与生产store均为只读。"""
from __future__ import annotations

import json
import zlib
import wf_assets
import wf_dsl
import wf_campus_nephtim_common as C
from wf_campus_nephtim_kit import replace_strings


def build():
    inventory, voices = [], []
    root_map = {'upload': 'common', 'medium_upload': 'medium', 'android_upload': 'android'}
    assets = wf_assets.char_asset_manifest(C.STORE, C.TMPL_CODE)
    for item in assets:
        if not item['exists'] or item['category'] == 'excluded':
            continue
        logical = item['logical']
        if '/story/' in logical or '/episode_' in logical:
            continue
        loc = wf_assets.locate(C.STORE, logical)
        if loc is None:
            raise FileNotFoundError(logical)
        root = root_map.get(loc[0], loc[0])
        if root not in C.STORES:
            raise ValueError(f'unknown root {loc[0]}')
        target = logical.replace(f'character/{C.TMPL_CODE}/', f'character/{C.CODE}/')
        raw = loc[1].read_bytes()
        if logical.endswith('.amf3.deflate'):
            tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']
            raw = C.amf_bytes(replace_strings(tree, {f'character/{C.TMPL_CODE}/': f'character/{C.CODE}/'}))
        C.write_pkg(root, target, raw)
        entry = {'source': logical, 'root': root, 'target': target,
                 'source_sha256': C.sha256(loc[1].read_bytes()), 'sha256': C.sha256(raw)}
        inventory.append(entry)
        if logical.endswith('.mp3'):
            voices.append({**entry, 'subtitle': item.get('text', ''), 'mode': 'native-inherited'})
    # 特效动画使用目录图集；单一ShowEffect路径不足以把依赖带齐。
    for donor, suffix in [('ruin_girl_smr21', 'star'), ('olivia', 'wave')]:
        source_prefix = f'battle/effect/skill_unique/{donor}/'
        target_prefix = f'battle/effect/skill_unique/{C.CODE}_{suffix}/'
        names = set()
        for line in (C.ROOT / 'mod-tools/WF_PATHLIST_recovered.txt').read_text('utf-8').splitlines():
            if line.strip().startswith(source_prefix):
                names.add(line.strip())
        fx = ['ruin_girl_smr21_all'] if donor == 'ruin_girl_smr21' else ['olivia_charge', 'olivia_slash']
        names.update(source_prefix + donor + ext for ext in ['.png', '.atlas.amf3.deflate'])
        names.update(source_prefix + name + ext for name in fx
                     for ext in ['.parts.amf3.deflate', '.timeline.amf3.deflate'])
        for logical in sorted(names):
            loc = wf_assets.locate(C.STORE, logical)
            if not loc:
                continue
            raw = loc[1].read_bytes()
            target = logical.replace(source_prefix, target_prefix)
            # Bundle basename must match its destination parent directory.
            target = target.replace(target_prefix + donor + '.', target_prefix + C.CODE + '_' + suffix + '.')
            if logical.endswith('.amf3.deflate'):
                tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))['tree']
                raw = C.amf_bytes(replace_strings(tree, {source_prefix: target_prefix}))
            C.write_pkg('common', target, raw)
            inventory.append({'source': logical, 'target': target, 'root': 'common',
                              'source_sha256': C.sha256(loc[1].read_bytes()), 'sha256': C.sha256(raw)})
    for name in ['sprite_sheet.png', 'special_sprite_sheet.png']:
        raw = C.pkg_path('common', f'character/{C.CODE}/pixelart/{name}').read_bytes()
        (C.EVIDENCE / ('native-' + name)).write_bytes(wf_assets.png_decode(raw))
    (C.EVIDENCE / 'asset-inventory.json').write_text(json.dumps(inventory, ensure_ascii=False, indent=2), 'utf-8')
    (C.EVIDENCE / 'voice-inventory.json').write_text(json.dumps(voices, ensure_ascii=False, indent=2), 'utf-8')
    return {'assets': len(inventory), 'inherited_voices': len(voices)}


if __name__ == '__main__':
    print(build())
