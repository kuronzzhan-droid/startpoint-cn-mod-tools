"""第三轮独立只读复核；仅在 audit 写审查报告，不运行构建/应用/服务器。"""
import hashlib, json, os, re, subprocess, sys, zipfile
from functools import lru_cache
from pathlib import Path
sys.dont_write_bytecode=True
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.stdout.reconfigure(encoding='utf-8')
SCRIPT=Path(__file__).resolve()
R=SCRIPT.parents[2] if SCRIPT.parent.name=='build' else SCRIPT.parents[1]
A=R/'audit';D=R/'交付'
K=Path('D:/WF/startpoint-cn-kulo');TOOL=K/'tools/fantasy-gauntlet-mod-tools'
BASE=Path('D:/WF/out/kulo-patch-toolkit/store131')
sys.path.insert(0,str(TOOL))
import wf_quest_lib as q
def read(p):return json.loads(Path(p).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def member(lp):
    h=hashlib.sha1((lp+q.SALT).encode()).hexdigest()
    return 'production/upload/'+h[:2]+'/'+h[2:]
def at(v,p):
    for k in p:v=v[k]
    return v
def leaves(v,p=()):
    if isinstance(v,dict):
        for k,x in v.items():yield from leaves(x,p+(str(k),))
    else:yield p,v
def git(*a):return subprocess.check_output(['git','-C',str(K),*a])
inputs=read(A/'inputs.json');indexes={}
for kind in ['hui','ours']:
    indexes[kind]={}
    for s in inputs[kind]:
        with zipfile.ZipFile(s['path']) as z:
            for n in z.namelist():
                if not n.endswith('/'):indexes[kind][n]=s['path']
@lru_cache(None)
def source_raw(kind,m):
    if m in indexes[kind]:
        with zipfile.ZipFile(indexes[kind][m]) as z:return z.read(m)
    p=BASE/m
    return p.read_bytes() if p.exists() else None
@lru_cache(None)
def source_table(kind,lp):return q.parse_node(source_raw(kind,member(lp)))
entry=read(D/'manifest-entry-1.4.220.json')
assert entry['version']=='1.4.220' and entry['depends_on']=='1.4.136'
assert len(entry['chain'])==14==len(entry['archive_integrity'])
data={};archives=[];sidecar_files=[]
for i,rec in enumerate(entry['archive_integrity'],1):
    p=D/rec['name'];raw=p.read_bytes();integrity=read(p.with_suffix('.integrity.json'))
    assert p.name==f'pinball-1.4.136-1.4.220-{i}-hui-share-20261016.zip'
    assert len(raw)<=5*1024*1024 and len(raw)==rec['size']==integrity['size']
    assert sha(raw)==rec['sha256']==integrity['sha256']
    assert entry['chain'][i-1]==p.name
    with zipfile.ZipFile(p) as z:
        names=z.namelist();assert z.testzip() is None
        assert len(names)==len(set(names)) and set(names)==set(rec['files'])==set(integrity['files'])
        assert len(names)==rec['members']==integrity['members']
        for n in names:
            assert re.fullmatch(r'production/(upload|medium_upload|android_upload|ios_upload)/[0-9a-f]{2}/[0-9a-f]{38}',n)
            assert n not in data
            b=z.read(n);assert sha(b)==integrity['member_sha256'][n]
            data[n]=b
    archives.append({'name':p.name,'size':len(raw),'sha256':sha(raw),'members':len(names)})
    sidecar_files.append({'name':p.with_suffix('.integrity.json').name,'sha256':sha(p.with_suffix('.integrity.json').read_bytes())})
assert len(data)==960==len(entry['files']) and set(data)==set(entry['files'])
@lru_cache(None)
def final_table(lp):
    m=member(lp);return q.parse_node(data.get(m,source_raw('hui',m)))
policy=read(D/'附录/exclusions.json')
original=read(D/'build/original-exclusions.json')
assert not policy['excluded_rows'] and not policy['excluded_members'] and not policy['acquisition_rows'] and not policy['blockers']
restored=[]
for row in original['excluded_rows']:
    lp=row['logical_path'];path=row['key_path']
    assert at(final_table(lp),path)==at(source_table('ours',lp),path),('恢复终态',lp,path)
    restored.append({'logical_path':lp,'path':path,'reason':row['reason']})
resources=[]
for row in original['excluded_members']:
    m=row['member'];assert data.get(m,source_raw('hui',m))==source_raw('ours',m),('恢复资源',m)
    resources.append({'member':m,'sha256':sha(source_raw('ours',m))})
assert len(restored)==156 and len(resources)==63
for row in policy['restored_quests']:
    assert final_table('master/quest/practice/practice_quest.orderedmap')[row['quest_id']]==row['value']
assert len(policy['restored_quests'])==21
gm_allowed={}
for row in policy['gm_body_rows']:gm_allowed.setdefault(row['member'],[]).append(tuple(row['key_path']))
gm_refs=[];PAT=re.compile(r'(?<!\d)599000[1-6](?!\d)')
gm_body_tables={'master/ability/ability_soul.orderedmap','master/item/equipment.orderedmap',
                'master/item/equipment_status.orderedmap','master/item/item.orderedmap'}
allowed_members={member(lp):lp for lp in gm_body_tables}
for m,raw in data.items():
    try:v=q.parse_node(raw)
    except Exception:continue
    if not isinstance(v,dict):continue
    for path,value in leaves(v):
        hits=PAT.findall('/'.join(path)+' '+str(value))
        if not hits:continue
        assert m in allowed_members and any(path[:len(p)]==p for p in gm_allowed.get(m,[])),('非本体GM引用',m,path)
        gm_refs.append({'logical_path':allowed_members[m],'path':list(path),'ids':sorted(set(hits))})
assert len(gm_refs)==30
five=read(A/'five-priority-220.json')
for row in five['client_rules']:
    assert at(final_table(row['logical']),row['path'])==row['ours'],('五重',row['logical'],row['path'])
for row in five.get('binary_dependencies',[]):
    m=row['member'];assert sha(data.get(m,source_raw('hui',m)))==row['terminal_sha256']
assert len(five['client_rules'])==2074
defects=read(A/'defect-resolutions-220.json')
for row in defects['rules']:
    assert row['resolution']=='ours'
    actual=at(final_table(row['logical']),row['path']) if row['path'] else sha(data.get(row['member'],source_raw('hui',row['member'])))
    assert actual==row['ours'],('缺陷修复',row['logical'],row['path'])
server=read(D/'server-entries.json');assert server['from']=='1.4.136' and server['to']=='1.4.220'
tree=set(git('ls-tree','-r','--name-only',server['hui_ref'],'assets').decode().splitlines())
merged={};ops=0;gm_server=[]
for f in server['files']:
    p=f['file'];exists=p in tree;assert exists==f['baseline_exists']
    raw=git('show',server['hui_ref']+':'+p) if exists else None
    if raw is not None:assert sha(raw)==f['baseline_sha256']
    v=json.loads(raw) if raw is not None else ({} if f['kind']=='object' else [])
    for e in f['entries']:
        key=e['key'];expected=e['expected'];ops+=1
        if f['kind']=='id-list':
            assert e['action']=='append-id' and expected['exists'] is False and e['value'] not in v
            v.append(e['value'])
        else:
            assert (key in v)==expected['exists']
            if expected['exists']:assert v[key]==expected['value']
            assert e['action'] in {'add','set','modify','replace','update'}
            v[key]=e['value']
        if PAT.search(key+' '+json.dumps(e['value'],ensure_ascii=False)):
            gm_server.append({'file':p,'key':key,'value':e['value']})
    merged[p]=v
assert len(server['files'])==26 and ops==1438
expected_gm_server={'assets/equipment_dissolve.json','assets/equipment_element.json','assets/equipment_ids.json',
 'assets/equipment_lookup.json','assets/equipment_max_level.json','assets/item_ids.json',
 'assets/item_lookup_cnmod.json','assets/item_sale.json'}
assert len(gm_server)==48 and {x['file'] for x in gm_server}==expected_gm_server
for g in gm_server:
    ours=json.loads((Path('D:/WF/out/角色超限-120/localsrv219')/g['file']).read_bytes())
    assert g['value'] in ours if isinstance(ours,list) else ours[g['key']]==g['value']
practice=merged['assets/practice_quest.json']
our_practice=read(Path('D:/WF/out/角色超限-120/localsrv219/assets/practice_quest.json'))
for i in range(1103,1124):assert practice[str(i)]==our_practice[str(i)]
align=read(D/'manifest-entry-align-1.4.220.json')
assert align['version']=='1.4.220' and align['depends_on']=='1.4.219'
ar=align['archive_integrity'][0];ap=D/ar['name'];ab=ap.read_bytes()
assert sha(ab)==ar['sha256'] and len(ab)==22==ar['size']
with zipfile.ZipFile(ap) as z:assert z.namelist()==[] and z.testzip() is None
report=read(D/'report.json')
assert report['anchor']=={'from':'1.4.136','to':'1.4.220'} and report['members']==len(data)
assert len(report['archives'])==len(archives)
assert report['archives']==archives or all(all(r[k]==a[k] for k in a) for r,a in zip(report['archives'],archives))
assert report['server_files']==len(server['files']) and report['server_entries']==ops
assert report['five_priority_rules']==len(five['client_rules']) and report['verified_defect_overrides']==len(defects['rules'])
assert report['client_conflicts']==5 and report['server_conflicts']==0 and report['schedule_quests']==72
prepush={}
for name,manifest,checked in [('prepush-summary.json','manifest-entry-1.4.220.json',archives),
                             ('prepush-align-summary.json','manifest-entry-align-1.4.220.json',[{'name':ap.name,'size':len(ab),'sha256':sha(ab),'members':0}])]:
    summary=read(D/name)
    assert summary['returncode']==0 and summary['counts']['ERROR']==0 and summary['allowlist'] is None
    assert summary['manifest_entry_sha256']==sha((D/manifest).read_bytes())
    assert summary['candidate_artifacts']==checked
    prepush[name]=summary['counts']
assert report['prepush']==prepush['prepush-summary.json']
assert report['alignment']['prepush']==prepush['prepush-align-summary.json']
doc=(D/'说明.md').read_text('utf-8')
doc_claims=['## GM武器只带数据，正式服不开放获取','已有管理后台通过显式操作人工授予',
            '客户端获取途径行命中 0 个','当前输入中未发现可列出的 GM 获取行',
            '这些属于未核实，包内不新增任何GM获取条目']
assert all(claim in doc for claim in doc_claims)
account_specs={
 'src/data/domains/player.ts':['export function insertDefaultPlayerSync','insertPlayerItemsSync(playerId, {})','insertPlayerEquipmentListSync(playerId, {})'],
 'src/routes/cn/tool.ts':['insertDefaultPlayerSync','insertAccountSync'],
 'src/routes/api/tool.ts':['insertDefaultPlayerSync'],
 'src/lib/player-login.ts':['insertDefaultPlayerSync'],
 'src/routes/web_api/server.ts':['const template = loadDefaultSaveTemplate()','restorePlayerSaveSnapshotV2Sync(snapshot, player.id','() => insertDefaultPlayerSync(accId)'],
 'src/data/defaultSave.ts':['const FILE','export function loadDefaultSaveTemplate','parsed?.schema','return parsed;'],
 'src/data/domains/account.ts':['export function insertAccountSync','INSERT INTO accounts'],
}
account_evidence=[]
for p,terms in account_specs.items():
    raw=git('show',server['hui_ref']+':'+p);text=raw.decode('utf-8');ls=text.splitlines()
    snippets=[]
    for i,line in enumerate(ls):
        if any(t in line for t in terms):snippets.append({'line':i+1,'text':'\n'.join(ls[max(0,i-2):min(len(ls),i+7)])})
    assert snippets,p
    assert 'equipment_ids.json' not in text and 'item_ids.json' not in text,p
    account_evidence.append({'file':p,'sha256':sha(raw),'snippets':snippets})
player_source=git('show',server['hui_ref']+':src/data/domains/player.ts').decode('utf-8')
assert 'insertPlayerItemsSync(playerId, {})' in player_source
assert 'insertPlayerEquipmentListSync(playerId, {})' in player_source
result={'status':'PASS','scope':'独立读取交付ZIP/sidecar/manifest/server-entries，并从固定灰Git ref和我方219来源重新比对；未运行构建、应用脚本、服务器或客户端。',
 'anchor':report['anchor'],'archives':archives,'total_zip_bytes':sum(x['size'] for x in archives),
 'unique_members':len(data),'sidecars':sidecar_files,
 'manifest_sha256':sha((D/'manifest-entry-1.4.220.json').read_bytes()),
 'server_entries_sha256':sha((D/'server-entries.json').read_bytes()),
 'report_validation':{'scope':'仅核对锚点、包/成员/服务端/五重/缺陷/排期数字与prepush计数；不绑定report整文件SHA256，后续文档汇总可重写该文件。',
                      'anchor':report['anchor'],'members':report['members'],'archive_count':len(report['archives']),
                      'server_files':report['server_files'],'server_entries':report['server_entries'],
                      'five_priority_rules':report['five_priority_rules'],'verified_defect_overrides':report['verified_defect_overrides']},
 'prepush_existing_evidence_bound':prepush,
 'documentation_gm_claims_review':{'passed':True,'claims_checked':doc_claims,
                                'conclusion':'GM只数据/零实际获取行表述与本轮来源及源码证据一致；正文保留管理员显式授予、已持有武器衍生魂珠和线上状态未核实边界。'},
 'restored_table_keys':len(restored),'restored_resources':len(resources),'restored_quests':21,
 'gm_body_table_keys':len(policy['gm_body_rows']),'gm_body_resource_members':len(policy['gm_body_members']),
 'gm_client_body_references':gm_refs,'gm_acquisition_references':0,'unclassified_gm_references':0,
 'server_files':len(server['files']),'server_operations':ops,'gm_server_body_operations':gm_server,
 'server_gm_acquisition_operations':0,'five_protected_leaf_rows':len(five['client_rules']),
 'defect_repairs_ours':len(defects['rules']),'alignment_archive':{'name':ap.name,'size':len(ab),'sha256':sha(ab),'members':0},
 'new_account_automatic_all_ids_grant':False,
 'new_account_source_evidence':account_evidence,
 'default_template_boundary':'固定灰新建账号的insertDefaultPlayerSync显式传入空物品和空装备；注册表不扩展开户库存。管理后台/newSave可另行恢复管理员上传的V2默认存档模板，此内容来自运行目录default_save.json，不属于本包；线上模板及历史库存未读取、未核实。',
 'limitations':['获取路线通用源码核查见gm-route-review-r3；受管理身份保护的既有手工授予接口仍可识别登记ID。','本审查不修改或重跑prepush证据；已核对本轮既有检查结果为ERROR0，并绑定其manifest和ZIP SHA256。','report只核对锚点与关键数字，不承诺最终report整文件哈希。','运行时与历史数据库状态未核实。']}
(A/'review-r3.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# 第三轮独立交付读回复核','', '**结论：PASS**。'+result['scope'],'',
 f"- 正式边 1.4.136→1.4.220：{len(archives)} 包、{len(data)} 个唯一成员，总 {result['total_zip_bytes']} 字节；每包不超过 5 MiB；ZIP CRC、成员唯一性、逐成员 SHA256、sidecar、manifest 和 report 相互一致。",
 '- 恢复终态独立比对：156 个原排除表键、63 个资源与我方 219 一致；21 个训练木桩的客户端与服务端均逐键一致。',
 '- GM：25 个本体表键＋1 个 DSL；30 个最终客户端数字 ID 叶行引用全部属于允许本体表（另含 gm_direct_hits 文本键 1 个）；未分类引用 0，获取途径引用 0。',
 '- 服务端：26 个文件、1438 个操作，逐键预期基线与固定灰 Git ref 一致；48 个 GM 操作只在 8 个本体/注册/使用配套文件，GM 获取操作 0。',
 '- 五重：2074 个客户端叶行及 buff 二进制依赖保留我方终态；原 5 处凉月/碧缺陷修复全部仍取我方。',
 '- 测试服对齐边：1.4.219→1.4.220，22 字节空 ZIP，0 成员，CRC/SHA256/manifest 一致。','',
 '本轮既有 prepush 证据已绑定当前 manifest 与全部 ZIP：正式边 ERROR 0／WARN 162，对齐边 ERROR 0／WARN 95，均退出 0、无 allowlist。本审查没有重跑检查器。`report.json` 仅核对锚点和关键数字，不绑定整文件 SHA256，避免后续汇总形成循环绑定。','',
 '说明中“GM只带数据”及“零实际获取行”准确：当前来源没有可列出的GM商品／掉落／奖励等行，不虚构剔除项；正文同时保留了既有管理员手工授予、已有武器产生魂珠和线上状态未核实的边界。','',
 '## 新账号／默认模板核对','',
 '固定灰 `src/data/domains/player.ts:665` 显式调用 `insertPlayerItemsSync(playerId, {})`，`:668` 调用 `insertPlayerEquipmentListSync(playerId, {})`。普通新建、登录建号均调用该默认创建函数；并不枚举 `item_ids`／`equipment_ids` 发全物品或全装备。',
 '管理后台 `newSave` 另可加载管理员预置的 V2 完整模板，再恢复其库存；模板由运行目录中的 `default_save.json` 提供。其线上内容以及历史库存均未读取、未核实，本包不提供或修改模板。逐文件固定 ref 的行号、SHA256 与片段见 JSON。','',
 '## 当前产物 SHA256','', '| 文件 | 字节 | SHA256 |','|---|---:|---|']
for x in archives+[result['alignment_archive']]:lines.append(f"| `{x['name']}` | {x['size']} | `{x['sha256']}` |")
lines+=['','## 边界','']+['- '+x for x in result['limitations']]
(A/'review-r3.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['status','unique_members','total_zip_bytes','restored_table_keys','restored_resources','restored_quests','server_files','server_operations','gm_acquisition_references','five_protected_leaf_rows','defect_repairs_ours']},ensure_ascii=False))
