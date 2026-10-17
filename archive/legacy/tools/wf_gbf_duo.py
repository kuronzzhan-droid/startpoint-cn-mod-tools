"""Author-supplied GBF Studio projects: isolated native character candidates."""
from __future__ import annotations

from wf.paths import root_path

import argparse
import json
from pathlib import Path

from wf_seasonal7_specs import SeasonalSpec
from wf_seasonal7_common import S7Pack

SOURCE = Path(('${WF_ROOT}/out/冈达葛萨与索利兹导入-20260919'.replace("${WF_ROOT}", str(root_path()))))
# 中秋批次的机读设计稿（B/design/<code>.json）。存在时覆盖 texts / required_capabilities /
# extra_keys，让 tables 与 kit 用同一份文案，不存在时行为与从前逐字相同。
DESIGN_DIR = Path(__file__).resolve().parent.parent / 'work/character_packs/midautumn-20260920/design'
IDENTITIES = {
    'ghandagoza': (129987, 121183, 'guild_front_girl_playable', 3, 'Supporter', '梁田清之'),
    'soriz': (129986, 121033, 'waterdragon_kunfu', 4, 'Attacker', '小山力也'),
}


def design_overrides(code):
    path = DESIGN_DIR / f'{code}.json'
    if not path.is_file():
        return {}, {}, None
    plan = json.loads(path.read_text(encoding='utf-8'))
    spec = plan.get('spec') or {}
    extra = {str(k): tuple(v) for k, v in dict(spec.get('extra_keys') or {}).items()}
    caps = tuple(spec['required_capabilities']) if spec.get('required_capabilities') else None
    return dict(plan.get('texts') or {}), extra, caps


def context(code, source=SOURCE):
    design = json.loads((Path(source) / f'{code}-summary.json').read_text(encoding='utf-8'))
    cid, donor, donor_code, pf, stance, cv = IDENTITIES[code]
    identity, skill, gameplay = design['identity'], design['skill'], design['gameplay']
    design_texts, extra_keys, design_caps = design_overrides(code)
    spec = SeasonalSpec(
        key=code, cid=cid, code=code, pkg_id=f'gbf-{code}-20260919',
        workspace=f'work/character_packs/gbf-{code}-20260919', template_id=donor,
        template_code=donor_code, template_element=1, element=1, element_token='Blue',
        rarity=5, pf_type=pf, stance=stance, identity=cid, template_identity=donor,
        theme=identity['title'], backdrop_colors=((57, 156, 207), (18, 48, 75)),
        requires_client_base='1.4.933',
        # Native adversity / Fever rules do not implement the authored design.
        # No corresponding client capability has been implemented or installed.
        required_capabilities=design_caps or (f'gbf-{code}-mechanics-v1',),
        extra_keys=extra_keys,
        texts=dict(dict(name=design['name'], furigana=code.upper(), title=identity['title'],
                        profile=identity['description'], cv=cv, leader=gameplay['leader']['name'],
                        skill1=skill['name'], skill2=skill['name'],
                        desc1=gameplay['skill']['description'],
                        desc2=gameplay['skill']['description']),
                   **{k: v for k, v in design_texts.items() if v is not None}),
    )
    return S7Pack(spec)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('code', choices=IDENTITIES)
    parser.add_argument('step', choices=('scaffold', 'media', 'manifest', 'kit'))
    parser.add_argument('--source', type=Path, default=SOURCE)
    args = parser.parse_args()
    pack = context(args.code, args.source)
    if args.step == 'scaffold':
        import wf_seasonal7_tables as tables
        import wf_seasonal7_assets as assets
        result = dict(tables=tables.build(pack), assets=assets.build(pack))
    elif args.step == 'manifest':
        import wf_seasonal7_manifest as manifest
        result = manifest.build(pack)
    elif args.step == 'media':
        from wf_studio_bridge import build
        result = build(pack, args.source)
    elif args.code == 'ghandagoza':
        from wf_gbf_kit_ghandagoza import build
        result = build(pack, args.source)
    elif args.code == 'soriz':
        from wf_gbf_kit_soriz import build
        result = build(pack, args.source)
    else:
        from wf_gbf_duo_kit import build
        result = build(pack, args.source)
    pack.write_evidence(f'gbf-{args.step}.json', result)
    print(json.dumps(dict(code=args.code, step=args.step, evidence=str(pack.evidence)), ensure_ascii=False))


if __name__ == '__main__':
    main()
