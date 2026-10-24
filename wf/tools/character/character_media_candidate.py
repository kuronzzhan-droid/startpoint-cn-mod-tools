"""已存在角色的媒体候选装配；限定自身路径/表键，不操作live或发布账本。"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import zlib

import wf_character_pack as pack
import wf_mod_tool as core
from wf.deliver.json_merge import merge_json

CHARACTER = 'master/character/character.orderedmap'
SPEECH = 'master/character/character_speech.orderedmap'
SWITCH = 'master/skill/switched_action_skill.orderedmap'
IMAGE = 'master/generated/character_image.orderedmap'
ATTRIBUTE = 'master/character/full_shot_image_attribute.orderedmap'
TRIMMED = 'master/generated/trimmed_image.orderedmap'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def apply(package, *, assets=None, tables=None, server=None, snapshot=None):
    """表值为已编码外层row；只接受本角色媒体及原生准备音路由字段。"""
    package = Path(package).resolve()
    if 'work' not in package.parts or 'character_packs' not in package.parts:
        raise ValueError('media changes require an ignored character candidate')
    manifest_path = package/'manifest.json'
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    cid, code = str(manifest['character_id']), manifest['code_name']
    ui, voice, pixel = (f'character/{code}/{kind}/' for kind in ('ui','voice','pixelart'))
    index = {(tier, e['logical_path']):e for tier, entries in manifest['roots'].items() for e in entries}
    outputs, originals, report = {}, {}, []

    def read(tier, logical):
        key = tier, logical
        if pack._path_problem(logical) or tier not in manifest['roots']:
            raise ValueError('unsafe media path')
        path = package/'roots'/tier/logical
        raw = path.read_bytes() if path.is_file() else None
        entry = index.get(key)
        if entry is not None and (raw is None or sha(raw)!=entry['sha256'] or len(raw)!=entry['size']):
            raise ValueError('candidate input hash drift: '+logical)
        originals[key] = raw
        return raw

    def claim(logical, keys, codec):
        existing = next((x for x in manifest['tables'] if x['root']=='common' and x['logical_path']==logical),None)
        if existing is None:
            existing = dict(root='common',logical_path=logical,codec_id=codec,
                            outer_keys=[],inner_keys=[],semantic_claims=[])
            manifest['tables'].append(existing)
        if existing['codec_id']!=codec:
            raise ValueError('media table codec changed')
        existing['outer_keys'] = sorted(set(existing['outer_keys']) | set(keys))
        if codec in ('action_nested','switched_nested'):
            inner={x['outer_key']:set(x['keys']) for x in existing['inner_keys']}
            for key,value in keys.items():
                inner.setdefault(key,set()).update(k for k,_ in core.decode_action_skill_row(value))
            existing['inner_keys']=[dict(outer_key=k,keys=sorted(v)) for k,v in sorted(inner.items())]

    for (tier, logical), raw in (assets or {}).items():
        valid = ((tier in ('medium','android') and logical.startswith(ui)) or
                 (tier=='common' and (logical.startswith(voice) or logical.startswith(pixel) or logical.startswith(ui))))
        if not valid:
            raise ValueError('asset outside character media namespace: '+logical)
        read(tier,logical)
        outputs[tier,logical] = raw
    for logical, spec in (tables or {}).items():
        keys, source, codec = spec['rows'],spec['source'],spec['codec']
        if logical not in (CHARACTER,SPEECH,SWITCH,IMAGE,ATTRIBUTE,TRIMMED) or not keys:
            raise ValueError('unsupported or empty media table update')
        allowed = ({cid} if logical in (CHARACTER,SPEECH,IMAGE,ATTRIBUTE) else
                   {code+'_voice_ready'} if logical==SWITCH else
                   set(keys) if logical==TRIMMED and all(k.startswith(ui) for k in keys) else set())
        if not set(keys)<=allowed:
            raise ValueError('table key outside character media scope')
        before = read('common',logical)
        if before is None:before = source
        elif before != source:raise ValueError('media table source differs from candidate')
        old = core.read_orderedmap_raw_rows_from_bytes(before,logical)
        prior = dict(zip(old.keys,old.rows))
        for key,value in keys.items():
            if logical==CHARACTER:
                a=core.read_csv_lines(zlib.decompress(prior[key]).decode('utf-8'))
                b=core.read_csv_lines(zlib.decompress(value).decode('utf-8'))
                restored=deepcopy(b);restored[0][9:17]=a[0][9:17]
                if restored!=a:raise ValueError('voice route changed other character columns')
            if logical==SPEECH:
                a=core.read_csv_lines(zlib.decompress(prior[key]).decode('utf-8'))
                b=core.read_csv_lines(zlib.decompress(value).decode('utf-8'))
                if len(a)!=len(b) or any(len(row)!=5 for row in b):
                    raise ValueError('voice subtitle structure changed')
                restored=deepcopy(b)
                for i,row in enumerate(restored):row[3]=a[i][3]
                if restored!=a:raise ValueError('voice subtitle changed unlock or slot binding')
            if key in prior:old.rows[old.keys.index(key)]=value
            else:old.keys.append(key);old.rows.append(value)
        if any(v!=prior[k] for k,v in zip(old.keys,old.rows) if k in prior and k not in keys):
            raise AssertionError('foreign media table row changed')
        outputs['common',logical]=core.build_orderedmap_raw_rows(old)
        claim(logical,keys,codec)
    for logical,value in (server or {}).items():
        if logical!='cdndata/character.json':raise ValueError('unsupported media server mirror')
        before=read('server',logical)
        source=json.loads(before);target=deepcopy(source)
        restored=deepcopy(value);restored[0][9:17]=source[cid][0][9:17]
        if restored!=source[cid]:raise ValueError('voice mirror changed non-route fields')
        target[cid]=value
        outputs['server',logical]=merge_json(before,json.dumps(target,ensure_ascii=False).encode('utf-8'),{cid})[0]
    for key,raw in outputs.items():
        old=originals[key]
        entry=index.get(key)
        if entry is None:
            entry=dict(logical_path=key[1]);manifest['roots'][key[0]].append(entry)
        entry.update(sha256=sha(raw),size=len(raw))
        report.append(dict(root=key[0],logical_path=key[1],before_sha256=sha(old) if old is not None else None,
                           after_sha256=sha(raw),changed=old!=raw))
    for entries in manifest['roots'].values():entries.sort(key=lambda e:e['logical_path'])
    manifest.setdefault('snapshot',{})['media_revision']=snapshot or {}
    manifest['qa'].update(release_ready=False,workspace_input_sha256='')
    if manifest_path.read_bytes()!=manifest_raw:raise ValueError('candidate manifest changed during preparation')
    for key,old in originals.items():
        path=package/'roots'/key[0]/key[1]
        if (path.read_bytes() if path.is_file() else None)!=old:raise ValueError('candidate changed during preparation')
    for (tier,logical),raw in outputs.items():
        path=package/'roots'/tier/logical;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    manifest_path.write_bytes(pack.canonical_manifest_bytes(manifest))
    return dict(character_id=cid,files=report,writes_live=False)
