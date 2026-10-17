"""Build the assigned campus Celtie package; never publish or change live data."""
from __future__ import annotations

import argparse
import json
import zlib

import wf_character_pack as pack
import wf_character_requirements as requirements
import wf_campus_celtie_common as C
import wf_campus_celtie_data as D
import wf_campus_celtie_assets as A


def build_tables():
    leader,abilities,panels=D.build_kit()
    crow,trow=D.character(),D.character_text()
    C.flat('master/character/character.orderedmap',{C.CID:C.core.write_csv_lines([crow]).rstrip('\n')})
    C.flat('master/character/character_text.orderedmap',{C.CID:C.core.write_csv_lines([trow]).rstrip('\n')})
    C.flat('master/ability/leader_ability.orderedmap',
        {C.CID:C.core.write_csv_lines(leader).rstrip('\n')})
    C.flat('master/ability/ability.orderedmap',
        {key:C.core.write_csv_lines(rows).rstrip('\n') for key,rows in abilities.items()})
    for logical in (
        'master/mana_board/upskill.orderedmap',
        'master/mana_board/mana_board2_open_condition.orderedmap',
        'master/skill_preview/skill_preview_character.orderedmap',
        'master/stance_detail/character_stance_detail.orderedmap',
        'master/character/character_awake_status.orderedmap',
    ):
        rows=C.official_flat(logical)
        if C.TEMPLATE_ID in rows:
            cells=C.core.read_csv_lines(rows[C.TEMPLATE_ID])
            C.flat(logical,{C.CID:C.core.write_csv_lines([[C.remap(cell) for cell in row] for row in cells]).rstrip('\n')})
    for logical in (
        'master/character/character_status.orderedmap',
        'master/generated/mana_board.orderedmap',
        'master/mana_board/mana_node.orderedmap',
        'master/generated/character_image.orderedmap',
        'master/character/full_shot_image_attribute.orderedmap',
    ):
        C.clone_outer(logical)
    logical='master/generated/trimmed_image.orderedmap'
    original=C.official_flat(logical)
    keep=tuple('character/'+C.TEMPLATE_CODE+'/ui/'+kind for kind in ('full_shot_','skill_cutin_'))
    C.flat(logical,{k.replace(C.TEMPLATE_CODE,C.CODE):v for k,v in original.items() if k.startswith(keep)})
    logical='master/skill/action_skill.orderedmap'
    source=C.official_raw(logical)
    rows=C.core.decode_action_skill_row(dict(zip(source.keys,source.rows))[C.TEMPLATE_CODE])
    for level,row in rows:
        row[0]=D.SKILL_NAME+('＋' if level=='2' else '')
        row[1]=D.SKILL_DESC
        row[4],row[5]='570',('570' if level=='1' else '520')
        row[7]=A.program(C.CODE,level)
    C.raw_outer(logical,{C.CODE:C.core.encode_action_skill_row(rows)},codec='action_nested',
        inner=[{'outer_key':C.CODE,'keys':[k for k,_ in rows]}])
    C.server('cdndata/character.json',[crow])
    C.server('cdndata/character_text.json',[trow])
    C.server('character.json',{'element':3,'name':'希尔媞','rarity':5,'skill_count':6})
    C.server('mana_node.json',server_mana())
    (C.EVIDENCE/'kit_panel.txt').write_text('\n'.join(panels)+'\n',encoding='utf-8')
    C.evidence('design_sources.json',D.source_notes())
    return panels


def server_mana():
    logical='master/mana_board/mana_node.orderedmap'
    outer=C.core.read_orderedmap_raw_rows_from_bytes(C.output('common',logical).read_bytes(),logical)
    boards=C.core.read_orderedmap_raw_rows_from_bytes(dict(zip(outer.keys,outer.rows))[C.CID],'boards')
    result={}
    for board,blob in zip(boards.keys,boards.rows):
        slots=C.core.read_orderedmap_raw_rows_from_bytes(blob,'slots')
        entries={}
        for raw in slots.rows:
            row,=C.core.read_csv_lines(zlib.decompress(raw).decode('utf-8'))
            if len(row)!=7 or not row[0].startswith(str(int(C.CID)*2)):
                raise ValueError('invalid remapped mana node')
            entries[row[0]]={'field1':row[1],'field5':row[5],'field6':row[6],
                'items':dict(zip(row[2].split(','),map(int,row[3].split(',')))),'manaCost':int(row[4])}
        result[board]=entries
    return result


def manifest():
    roots={name:[] for name in ('common','medium','android','server')}
    for name,entries in roots.items():
        base=C.PACKAGE/'roots'/name
        for path in sorted(base.rglob('*')):
            if path.is_file():
                raw=path.read_bytes()
                entries.append({'logical_path':path.relative_to(base).as_posix(),'sha256':C.sha(raw),'size':len(raw)})
    present={e['logical_path'] for name,entries in roots.items() if name!='server' for e in entries}
    report=requirements.build_requirement_report(requirements.char_asset_requirements(C.CODE),present)
    value={'schema_version':1,'package_id':C.PACKAGE_ID,'character_id':int(C.CID),
        'code_name':C.CODE,'package_version':'0.1.0','requires_client_base':'1.4.54',
        'required_capabilities':[],'roots':roots,'tables':C.CLAIMS,'skills':{},'unique_condition':{},
        'qa':{'delivery_mode':'production','release_ready':False,
            'required_assets_present':report['required_present'],'required_assets_total':37,
            'missing_required':report['missing_required'],'workspace_input_sha256':''},
        'snapshot':{'campus_celtie':{'template_id':int(C.TEMPLATE_ID),'template_code':C.TEMPLATE_CODE,
            'candidate_only':True,'generated_portraits_pending':True,'audio':'official_same_character_inherited',
            'skill_damage':'native skill','additional_damage':'native wind ability I254',
            'runtime_acceptance':'not yet observed'}}}
    C.PACKAGE.joinpath('manifest.json').write_bytes(pack.canonical_manifest_bytes(value))
    errors=pack.validate_manifest(value,C.PACKAGE,require_referenced_assets=True)
    if errors:
        raise ValueError('manifest: '+str(errors))
    C.evidence('table_claims.json',C.CLAIMS)
    C.evidence('official_source_hashes.json',C.SOURCES)
    C.evidence('candidate_build.json',{'required_present':report['required_present'],'missing_required':report['missing_required'],
        'files_by_root':{k:len(v) for k,v in roots.items()},'table_claim_count':len(C.CLAIMS),
        'manifest_errors':errors,'runtime_verified':False,'portraits_pending':True})
    return {'required_present':report['required_present'],'missing_required':report['missing_required'],
        'files_by_root':{k:len(v) for k,v in roots.items()},'manifest_errors':errors}


def build():
    C.CLAIMS.clear()
    C.SOURCES.clear()
    C.EVIDENCE.mkdir(parents=True,exist_ok=True)
    build_tables()
    skills=A.build_skills()
    A.build_template_assets()
    A.build_preview(skills)
    A.build_voices()
    return manifest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',action='store_true',required=True)
    parser.parse_args()
    print(json.dumps(build(),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
