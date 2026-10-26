"""合并既有角色的精确数据修订；仅写忽略目录，不操作live、发布链或owner。"""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import zlib

import wf_character_pack as pack
import wf_gerald_percent_revision as gerald
import wf_gerald_percent_skill as gerald_skill
import wf_mod_tool as core
from wf_miniboss_roster import ROSTER

ABILITY = 'master/ability/ability.orderedmap'
LEADER = 'master/ability/leader_ability.orderedmap'
STRINGS = 'master/string/custom_ability_string.orderedmap'
ACTION = 'master/skill/action_skill.orderedmap'
TEXT = 'master/character/character_text.orderedmap'
STATUS = 'master/character/character_status.orderedmap'
SERVER_TEXT = 'cdndata/character_text.json'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def merge_ordered(live, candidate, keys):
    """用声明键替换原始压缩row；其余live行及顺序保持，候选其他行不重放。"""
    left = core.read_orderedmap_raw_rows_from_bytes(live)
    right = core.read_orderedmap_raw_rows_from_bytes(candidate)
    a, b = dict(zip(left.keys,left.rows)), dict(zip(right.keys,right.rows))
    if set(keys)-b.keys():
        raise ValueError('missing candidate keys: '+str(sorted(set(keys)-b.keys())))
    changed = {key for key in keys if a.get(key) != b[key]}
    excluded = sorted(key for key in a.keys()|b.keys() if key not in keys and a.get(key)!=b.get(key))
    for key in sorted(changed):
        if key in a:
            left.rows[left.keys.index(key)] = b[key]
        else:
            left.keys.append(key); left.rows.append(b[key])
    output = core.build_orderedmap_raw_rows(left) if changed else live
    final = dict(zip(left.keys,left.rows))
    assert all(final[key] == raw for key,raw in a.items() if key not in changed)
    return output, dict(changed_keys=sorted(changed),preserved_row_count=len(a)-len(changed&a.keys()),
                        excluded_candidate_differences=excluded)


def _pairs(values):
    output = {}
    for key,value in values:
        if key in output:
            raise ValueError('duplicate JSON key: '+key)
        output[key] = value
    return output


def _json_spans(raw):
    """解析顶层JSON对象的value字节文本片段；引号/转义/嵌套交给标准解码器。"""
    text = raw.decode('utf-8')
    def constant(value):
        raise ValueError('non-finite JSON value: '+value)
    decoder = json.JSONDecoder(object_pairs_hook=_pairs,parse_constant=constant)
    value,end = decoder.raw_decode(text,len(text)-len(text.lstrip()))
    if not isinstance(value,dict) or text[end:].strip():
        raise ValueError('expected exactly one JSON object')
    spans, position = {}, text.index('{')+1
    while True:
        while text[position].isspace():position += 1
        if text[position] == '}':break
        key, position = decoder.raw_decode(text,position)
        while text[position].isspace():position += 1
        if text[position] != ':':raise ValueError('invalid JSON member separator')
        position += 1
        while text[position].isspace():position += 1
        start = position
        _,position = decoder.raw_decode(text,position)
        spans[key] = (start,position)
        while text[position].isspace():position += 1
        if text[position] == ',':position += 1
        elif text[position] != '}':raise ValueError('invalid JSON item separator')
    return text,value,spans


def merge_json(live,candidate,keys):
    text,a,spans = _json_spans(live)
    _,b,_ = _json_spans(candidate)
    if set(keys)-a.keys() or set(keys)-b.keys():
        raise ValueError('JSON revision requires existing live and candidate keys')
    changed = {key for key in keys if a[key] != b[key]}
    for key in sorted(changed,key=lambda key:spans[key][0],reverse=True):
        begin,end = spans[key]
        text = text[:begin]+json.dumps(b[key],ensure_ascii=False,separators=(',',':'),allow_nan=False)+text[end:]
    output = text.encode('utf-8') if changed else live
    original,_,_ = _json_spans(live)
    final,_,final_spans = _json_spans(output)
    assert all(original[s:e] == final[slice(*final_spans[key])]
               for key,(s,e) in spans.items() if key not in changed)
    return output,dict(changed_keys=sorted(changed),preserved_row_count=len(a)-len(changed),
        excluded_candidate_differences=sorted(k for k in a.keys()|b.keys()
                                             if k not in keys and a.get(k)!=b.get(k)))


def validate_text_only(logical,before,after):
    if logical == ACTION:
        old,new = core.decode_action_skill_row(before),core.decode_action_skill_row(after)
        if [k for k,_ in old] != [k for k,_ in new]:raise ValueError('action levels changed')
        restored = deepcopy(new)
        for (level,row),(_,original) in zip(restored,old):
            if level in ('1','2'):row[1] = original[1]
        if restored != old:raise ValueError('non-description action fields changed')
    elif logical in (TEXT,SERVER_TEXT):
        old = core.read_csv_lines(zlib.decompress(before).decode()) if logical == TEXT else before
        new = core.read_csv_lines(zlib.decompress(after).decode()) if logical == TEXT else after
        restored = deepcopy(new)
        for index in (5,7):restored[0][index] = old[0][index]
        if restored != old:raise ValueError('non-description character fields changed')


def _safe_path(path):
    for item in (path,*path.parents):
        if item.is_symlink() or getattr(item,'is_junction',lambda:False)():
            raise ValueError('reparse path is not allowed: '+str(item))
    return path.resolve()


@dataclass
class PatchResult:
    repo: Path
    output: Path
    files: dict
    report: dict
    snapshots: dict

    def __post_init__(self):
        self.repo,self.output = _safe_path(self.repo),_safe_path(self.output)
        if not any(self.output.is_relative_to(self.repo/'work'/name)
                   and self.output != self.repo/'work'/name for name in ('codex_out','character_packs')):
            raise ValueError('patch output must be a child of an ignored workspace root')
        for tier,logical in self.files:
            if tier not in ('common','server') or pack._path_problem(logical):
                raise ValueError('unsafe patch member')

    def write(self):
        _safe_path(self.output)
        if self.output.exists():raise ValueError('patch output already exists')
        for path,raw in self.snapshots.items():
            if path.read_bytes()!=raw:raise ValueError('source changed after plan: '+str(path))
        self.output.mkdir(parents=True)
        for (tier,logical),raw in self.files.items():
            path = self.output/'roots'/tier/logical
            path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
            if path.read_bytes()!=raw:raise OSError('patch readback mismatch')
        (self.output/'patch-manifest.json').write_text(
            json.dumps(self.report,ensure_ascii=False,indent=2),encoding='utf-8')


def plan(repo,gerald_candidate,miniboss_root,output):
    repo = _safe_path(Path(repo))
    snapshots, sources, files, live_bytes, entries = {},[],{},{},{}
    def read(path):
        path = _safe_path(path)
        if path not in snapshots:snapshots[path] = path.read_bytes()
        return snapshots[path]
    profile = json.loads(read(repo/'mod-tools/profiles.json'))['profiles']['cn']
    store = Path(profile['store'])
    if not store.is_absolute():store = repo/store
    def live(tier,logical):
        key = tier,logical
        if key not in live_bytes:
            path = repo/'assets'/logical if tier == 'server' else core.table_path(store,logical)
            live_bytes[key] = read(path)
        return files.get(key,live_bytes[key])
    def candidate(root,cid,code,scopes,asset_paths=()):
        root = _safe_path(Path(root)); package = root/'package'
        if not root.is_relative_to(repo/'work/character_packs'):
            raise ValueError('source candidate must be under character_packs')
        manifest_raw = read(package/'manifest.json'); manifest = json.loads(manifest_raw)
        if (str(manifest['character_id']),manifest['code_name']) != (cid,code):
            raise ValueError('candidate identity mismatch')
        index = {(t,e['logical_path']):e for t,es in manifest['roots'].items() for e in es}
        claims = {(x['root'],x['logical_path']):set(x['outer_keys']) for x in manifest['tables']}
        source = dict(path=str(root),character_id=cid,code_name=code,manifest_sha256=sha(manifest_raw),
                      selected_files=[],excluded_asset_count=len(index)-len(scopes)-len(asset_paths))
        sources.append(source)
        for (tier,logical),keys in scopes.items():
            if not set(keys)<=claims.get((tier,logical),set()):
                raise ValueError('candidate does not claim authorized keys: '+logical)
            raw = read(package/'roots'/tier/logical); entry = index[tier,logical]
            if sha(raw)!=entry['sha256'] or len(raw)!=entry['size']:raise ValueError('candidate hash drift: '+logical)
            before = live(tier,logical)
            if tier == 'common':
                left = core.read_orderedmap_raw_rows_from_bytes(before)
                right = core.read_orderedmap_raw_rows_from_bytes(raw)
                a,b = dict(zip(left.keys,left.rows)),dict(zip(right.keys,right.rows))
                for key in keys:
                    if key in a and key in b:validate_text_only(logical,a[key],b[key])
                after,change = merge_ordered(before,raw,keys)
                if cid==gerald_skill.CID and a[gerald.STRING_KEY]!=b[gerald.STRING_KEY]:
                    old = zlib.decompress(a[gerald.STRING_KEY]).decode()
                    expected = gerald.description(old)
                    actual = core.read_csv_lines(zlib.decompress(b[gerald.STRING_KEY]).decode())
                    if actual != [[expected]]:raise ValueError('Gerald description outside reviewed change')
            else:
                a,b = json.loads(before),json.loads(raw)
                for key in keys:validate_text_only(logical,a[key],b[key])
                after,change = merge_json(before,raw,keys)
            source['selected_files'].append(dict(root=tier,logical_path=logical,sha256=sha(raw),**change))
            if change['changed_keys']:
                files[tier,logical] = after
                entries.setdefault((tier,logical),set()).update(change['changed_keys'])
        for logical,level in asset_paths:
            raw = read(package/'roots/common'/logical); entry = index['common',logical]
            if sha(raw)!=entry['sha256'] or len(raw)!=entry['size']:raise ValueError('candidate DSL hash drift')
            before = live('common',logical)
            if before != raw:
                if gerald_skill.patch_skill_bytes(before,level)!=raw:raise ValueError('unreviewed Gerald DSL')
                files['common',logical] = raw; entries['common',logical] = set()
            source['selected_files'].append(dict(root='common',logical_path=logical,sha256=sha(raw),changed=before!=raw))
    candidate(gerald_candidate,gerald_skill.CID,gerald_skill.CODE,
        {('common',STRINGS):{gerald.STRING_KEY}},tuple((p,lv) for lv,p in gerald_skill.ACTIVE_PATHS.items()))
    for char in ROSTER:
        candidate(Path(miniboss_root)/char.code,char.cid,char.code,{
            ('common',ABILITY):{char.cid+str(n) for n in range(1,7)},
            ('common',LEADER):{char.cid},('common',STRINGS):{
                'desc_override_'+char.code,*('desc_override_'+char.code+f'_{n}' for n in range(1,7))},
            ('common',ACTION):{char.code},('common',TEXT):{char.cid},
            ('common',STATUS):{char.cid},('server',SERVER_TEXT):{char.cid}})
    records = []
    for key,raw in sorted(files.items()):
        before = live_bytes[key]; keys = sorted(entries[key]); preserved = None; row_changes = []
        if keys:
            if key[0]=='server':
                old_text,_,old_spans = _json_spans(before)
                new_text,_,new_spans = _json_spans(raw)
                original = {k:old_text[s:e].encode('utf-8') for k,(s,e) in old_spans.items()}
                final = {k:new_text[s:e].encode('utf-8') for k,(s,e) in new_spans.items()}
            else:
                old_rows = core.read_orderedmap_raw_rows_from_bytes(before)
                new_rows = core.read_orderedmap_raw_rows_from_bytes(raw)
                original = dict(zip(old_rows.keys,old_rows.rows))
                final = dict(zip(new_rows.keys,new_rows.rows))
            preserved = len(original)-len(set(keys)&set(original))
            assert all(final[k]==v for k,v in original.items() if k not in keys)
            row_changes = [dict(key=k,before_sha256=sha(original[k]) if k in original else None,
                                after_sha256=sha(final[k])) for k in keys]
        records.append(dict(root=key[0],logical_path=key[1],before_sha256=sha(before),after_sha256=sha(raw),
            before_size=len(before),after_size=len(raw),exact_keys=keys,row_changes=row_changes,
            bytewise_preserved_row_count=preserved))
    report = dict(schema_version=1,writes_live=False,writes_installed_owner=False,files=records,
                  source_candidates=sources,total_changed_files=len(files),
                  excluded_non_scope_assets=sum(s['excluded_asset_count'] for s in sources))
    destination = Path(output).resolve()
    for source in sources:
        root = Path(source['path'])
        if destination.is_relative_to(root) or root.is_relative_to(destination):
            raise ValueError('patch output overlaps a source candidate')
    return PatchResult(repo,Path(output),files,report,snapshots)


def assemble(repo,gerald_candidate,miniboss_root,output,*,apply=False):
    result = plan(repo,gerald_candidate,miniboss_root,output)
    if apply:result.write()
    return result.report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo','gerald-candidate','miniboss-root','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--apply',action='store_true'); args=parser.parse_args()
    print(json.dumps(assemble(args.repo,args.gerald_candidate,args.miniboss_root,args.output,apply=args.apply),
                     ensure_ascii=False,indent=2))


if __name__=='__main__':main()
