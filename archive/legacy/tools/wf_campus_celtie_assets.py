"""Real candidate skill, recolored pixels, preview data, and official voice assets."""
from copy import deepcopy
import colorsys
import io

from PIL import Image

import wf_assets
import wf_character_requirements as requirements
import wf_client_legality as legality
import wf_dsl_sig
import wf_campus_celtie_common as C
import wf_campus_celtie_data as D

SUFFIX = '.action.dsl.amf3.deflate'
SKILL_DIR = 'battle/action/skill/action/rare5/'


def program(code, level):
    return f'{SKILL_DIR}{code}${code}_{level}'


def _remap_tree(tree):
    if isinstance(tree,list):
        return [_remap_tree(item) for item in tree]
    if isinstance(tree,dict):
        return {k:_remap_tree(v) for k,v in tree.items()}
    if isinstance(tree,str):
        return tree.replace(C.TEMPLATE_CODE,C.CODE)
    return tree


def skill(level):
    base = C.amf(C.official(program(C.TEMPLATE_CODE,level)+SUFFIX))
    donor = C.amf(C.official(program('illusionist_smr20',level)+SUFFIX))
    additions = C.commands(donor,'AddFeverPoint')
    if len(additions)!=1:
        raise ValueError('summer illusionist no longer has exactly one Fever grant')
    tree = deepcopy(base)
    # The body and its subject IDs remain intact. The donated command binds none.
    tree[11][1].append(['Command',['ConditionalsFeverMode',['Block',[]],
        ['Block',[['Command',deepcopy(additions[0])]]]]])
    tree = _remap_tree(tree)
    validate_dsl(tree)
    return tree, {'source':program(C.TEMPLATE_CODE,level),'fever_source':program('illusionist_smr20',level),
        'fever_points':additions[0][1], 'original_skill_lifecycle_preserved':True,
        'condition':'FEVER外のみ加算 / only outside Fever', 'skill_damage_preserved':True}


def validate_dsl(tree):
    problems = (legality.action_dsl_element_problems(tree, character_element=3)
        + legality.action_dsl_subject_binding_problems(tree)
        + legality.action_dsl_hit_area_target_problems(tree))
    for node in C.walk(tree):
        if not (isinstance(node,list) and len(node)==2 and node[0] in ('Command','Event')):
            continue
        command=node[1]
        if not isinstance(command,list) or not command:
            problems.append('empty command')
            continue
        registry=wf_dsl_sig.COMMANDS if node[0]=='Command' else wf_dsl_sig.EVENTS
        if command[0] not in registry or len(command)-1!=len(registry[command[0]]):
            problems.append('unknown command or arity: '+str(command[0]))
    if problems:
        raise ValueError('; '.join(problems))


def build_skills():
    records={}
    effects=set()
    for level in ('1','2'):
        tree,report=skill(level)
        logical=program(C.CODE,level)+SUFFIX
        raw=C.amf_bytes(tree)
        C.write('common',logical,raw)
        report.update(logical=logical,sha256=C.sha(raw))
        records[level]=report
        C.evidence('skill_'+level+'.json',tree)
        effects.update(n[1] for n in C.walk(tree) if isinstance(n,list) and len(n)>1
            and n[0]=='SpecifyEffectDirectly')
    files=set()
    for effect in effects:
        files.update((effect+'.parts.amf3.deflate',effect+'.timeline.amf3.deflate'))
        family=effect.rsplit('/',1)[0]
        texture=family+'/'+family.rsplit('/',1)[1]
        files.update((texture+'.png',texture+'.atlas.amf3.deflate'))
    for logical in sorted(files):
        source=logical.replace(C.CODE,C.TEMPLATE_CODE)
        raw=C.official(source)
        if logical.endswith('.png'):
            raw,_,_=recolor(raw)
        else:
            raw=C.amf_bytes(_remap_tree(C.amf(raw)))
        C.write('common',logical,raw)
    C.evidence('skills_build.json',{'skills':records,'independent_effect_files':sorted(files),
        'source_family':C.TEMPLATE_CODE,'destination_family':C.CODE})
    return records


def recolor(raw):
    original=Image.open(io.BytesIO(wf_assets.png_decode(raw))).convert('RGBA')
    pixels=list(original.getdata())
    palette={}
    for color in set(pixels):
        r,g,b,a=color
        hue,sat,val=colorsys.rgb_to_hsv(r/255,g/255,b/255)
        if a and 0.48<=hue<=0.85 and sat>=0.23:
            # Saturated blue/violet cloth and swordlight -> sage/emerald/mint.
            hue2=0.39+(hue-0.48)*0.14
            rgb=colorsys.hsv_to_rgb(hue2, min(0.8,sat*0.72),val)
            palette[color]=tuple(round(x*255) for x in rgb)+(a,)
    revised=original.copy()
    revised.putdata([palette.get(color,color) for color in pixels])
    if revised.getchannel('A').tobytes()!=original.getchannel('A').tobytes():
        raise ValueError('recolor changed alpha')
    buf=io.BytesIO()
    revised.save(buf,format='PNG',optimize=True)
    return wf_assets.png_encode(buf.getvalue()),revised,{
        'dimensions':original.size,'changed_colors':len(palette),
        'changed_pixels':sum(color in palette for color in pixels),'alpha_unchanged':True,
        'palette':{'%02x%02x%02x%02x'%k:'%02x%02x%02x%02x'%v for k,v in palette.items()}}


def build_template_assets():
    records=[]
    for req in requirements.char_asset_requirements(C.TEMPLATE_CODE):
        if req.category!='required' or req.logical_path.endswith('.battle.amf3.deflate'):
            continue
        logical=req.logical_path
        root,raw=C.official_asset(logical)
        target=logical.replace(C.TEMPLATE_CODE,C.CODE)
        report={'source':logical,'destination':target,'root':root}
        if '/pixelart/' in logical and logical.endswith('.png'):
            raw,image,info=recolor(raw)
            image.save(C.EVIDENCE / ('recolored_'+logical.rsplit('/',1)[1]))
            report.update(info)
        elif logical.endswith('.amf3.deflate'):
            tree=C.amf(raw)
            raw=C.amf_bytes(_remap_tree(tree))
        C.write(root,target,raw)
        records.append(report)
    C.evidence('template_assets.json',records)
    pixel_contact_sheet()
    pixel_animation()


def pixel_contact_sheet():
    sheet=Image.open(io.BytesIO(wf_assets.png_decode(C.output('common',
        f'character/{C.CODE}/pixelart/sprite_sheet.png').read_bytes()))).convert('RGBA')
    atlas=C.amf(C.output('common',f'character/{C.CODE}/pixelart/sprite_sheet.atlas.amf3.deflate').read_bytes())
    samples=[atlas[i] for i in (0,4,9,12,16,20) if i<len(atlas)]
    canvas=Image.new('RGBA',(900,600),(237,244,236,255))
    for index,entry in enumerate(samples):
        x,y,w,h=(int(entry[k]) for k in ('x','y','w','h'))
        patch=sheet.crop((x,y,x+w,y+h))
        if entry.get('r'):
            patch=patch.rotate(-90,expand=True)
        scale=min(12,260//max(patch.size))
        patch=patch.resize((patch.width*scale,patch.height*scale),Image.Resampling.NEAREST)
        canvas.alpha_composite(patch,(index%3*300+(300-patch.width)//2,index//3*300+(300-patch.height)//2))
    canvas.convert('RGB').save(C.EVIDENCE/'pixel_preview.png')


def pixel_animation():
    prefix=f'character/{C.CODE}/pixelart/'
    sheet=Image.open(io.BytesIO(wf_assets.png_decode(C.output('common',prefix+'sprite_sheet.png').read_bytes()))).convert('RGBA')
    atlas=C.amf(C.output('common',prefix+'sprite_sheet.atlas.amf3.deflate').read_bytes())
    frames={int(item['n'][-4:]):item for item in atlas}
    output=[]
    for frame in range(1,111):
        available=[number for number in frames if number<=max(2,frame)]
        item=frames[max(available)]
        x,y,w,h=(int(item[k]) for k in ('x','y','w','h'))
        tile=sheet.crop((x,y,x+w,y+h))
        if item.get('r'):
            tile=tile.rotate(-90,expand=True)
        canvas=Image.new('RGBA',(256,256),(236,242,232,255))
        canvas.alpha_composite(tile,(-int(item.get('fx',0)),-int(item.get('fy',0))))
        output.append(canvas.crop((56,48,200,192)).resize((432,432),Image.Resampling.NEAREST).convert('RGB'))
    output[0].save(C.EVIDENCE/'pixel_animation.gif',save_all=True,append_images=output[1:],duration=33,loop=0)


def build_preview(skills):
    source=f'character/{C.TEMPLATE_CODE}/battle/character_detail_skill_preview.battle.amf3.deflate'
    template=C.amf(C.official(source))
    # Rebuild the playback recipe against this candidate's actual skill asset.
    # The original input events target the displayed unit; the new end frame leaves
    # 60 extra frames to observe FEVER gauge feedback after the inherited sword act.
    preview={'config':deepcopy(template['config']), 'log_parts':deepcopy(template['log_parts'])}
    preview['config']['end_frame']=420
    preview['config']['skill_gauge_ratio']=1
    target=f'character/{C.CODE}/battle/character_detail_skill_preview.battle.amf3.deflate'
    C.write('common',target,C.amf_bytes(preview))
    C.evidence('preview_generation.json',{'target':target,'source_controls':source,
        'candidate_skill_sha256':skills['2']['sha256'],'generated_config':preview,
        'actual_client_render_checked':False,'reason':'保留对应星剑圣动作输入，延长60帧观察新FEVER槽反馈'})


def build_voices():
    manifest=C.wf_assets.char_asset_manifest(C.STORE,C.TEMPLATE_CODE)
    records=[]
    for entry in manifest:
        source=entry['logical']
        if not entry['exists'] or entry['category']=='excluded' or '/voice/' not in source:
            continue
        if not any('/voice/'+cat+'/' in source for cat in ('ally','battle','home')):
            continue
        raw=C.official(source)
        decoded=wf_assets.mp3_decode(raw)
        if wf_assets.mp3_encode(decoded)!=raw:
            raise ValueError('official voice does not roundtrip')
        destination=source.replace(C.TEMPLATE_CODE,C.CODE)
        C.write('common',destination,raw)
        records.append({'source':source,'destination':destination,'sha256':C.sha(raw),
            'subtitle':entry.get('text',''),'inherited_official_audio':True})
    for table in ('character_speech','character_gacha_sound'):
        C.clone_outer('master/character/'+table+'.orderedmap')
    C.evidence('voice_inventory.json',{'count':len(records),'new_generated_audio':False,
        'policy':'官方星之剑圣同名槽继承，字幕同步原音；未复制words/story/login', 'voices':records})
    return records
