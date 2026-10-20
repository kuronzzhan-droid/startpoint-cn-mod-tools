"""汇总第三轮 GM 获取边界：固定本地数据和源码静态审计。"""
import hashlib, json, os, re, subprocess, sys, zipfile
from pathlib import Path
sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.stdout.reconfigure(encoding='utf-8')
A = Path(__file__).resolve().parent
R = A.parent
REPO = Path('D:/WF/startpoint-cn-kulo')
TOOL = REPO/'tools/fantasy-gauntlet-mod-tools'
BASE = Path('D:/WF/out/kulo-patch-toolkit/store131')
OURS = Path('D:/WF/out/角色超限-120/localsrv219/assets')
REF = '224aa2a663b7756fc8a34c0f37f1ae61ad81800c'
sys.path.insert(0,str(TOOL))
import wf_quest_lib as q
PAT = re.compile(r'(?<!\d)599000[1-6](?!\d)')
def git(*a): return subprocess.check_output(['git','-C',str(REPO),*a]).decode('utf-8')
def member(lp):
    h=hashlib.sha1((lp+q.SALT).encode()).hexdigest()
    return 'production/upload/'+h[:2]+'/'+h[2:]
def leaves(v,p=()):
    if isinstance(v,dict):
        for k,x in v.items(): yield from leaves(x,p+(str(k),))
    else: yield p,v
def refs(v):
    return [{'key_path':list(p),'value':x} for p,x in leaves(v) if PAT.search('/'.join(p)+' '+str(x))]
source=json.loads((A/'gm-route-source-r3.json').read_bytes())
inputs=json.loads((A/'inputs.json').read_bytes())
logicals={}
for l in (TOOL/'WF_PATHLIST_recovered.txt').read_text('utf-8-sig').splitlines():
    l=l.strip()
    if l and not l.startswith('#'): logicals[member(l)]=l
old=json.loads((A/'exclusions.json').read_bytes())
for row in old.get('gm_references',[]): logicals[row['member']]=row['logical_path']
index={}
for s in inputs['ours']:
    with zipfile.ZipFile(s['path']) as z:
        for n in z.namelist():
            if not n.endswith('/'): index[n]=s['path']
client=[]; parsed=0
for m,p in index.items():
    with zipfile.ZipFile(p) as z: raw=z.read(m)
    try: value=q.parse_node(raw)
    except Exception: continue
    parsed+=1
    hits=refs(value)
    if hits:
        client.append({'member':m,'logical_path':logicals.get(m,'未核实'),
                       'source_archive':Path(p).name,'references':hits})
route_rx=re.compile(r'shop|reward|gacha|exchange|present|gift|mail|mission|quest',re.I)
base_route_scanned=[]; base_route_hits=[]
for m,lp in logicals.items():
    if m in index or not lp.endswith('.orderedmap') or not route_rx.search(lp): continue
    path=BASE/m
    if not path.is_file(): continue
    try: value=q.parse_node(path.read_bytes())
    except Exception: continue
    base_route_scanned.append(lp)
    hit=refs(value)
    if hit: base_route_hits.append({'logical_path':lp,'member':m,'references':hit})
server_files=[]; parse_errors=[]
for p in OURS.rglob('*.json'):
    if 'asset-patch' in p.parts: continue
    try: json.loads(p.read_bytes()); server_files.append('assets/'+p.relative_to(OURS).as_posix())
    except Exception as e: parse_errors.append({'file':str(p),'error':str(e)})
evidence=[]
specs={
 'src/lib/assets.ts':['treasureShopItems','generalShopItems','getGenericShopItemsSync','getShopItemSync','getEquipmentCraftSync'],
 'src/lib/content-master.ts':['baseItemIds','serverItemIds','serverEventShops','serverGachas'],
 'src/lib/gacha.ts':['gacha.pool','ratePool[randomWeightedIndex','Object.entries(rewards)'],
 'src/multi/five-boss/rewards.ts':['FIVE_BOSS_CURSED_WEAPON_ID_BASE =','FIVE_BOSS_CURSED_WEAPON_POOL_SIZE =','getFiveBossCursedWeaponPool','CANDIDATE_IDS.filter'],
 'src/routes/api/exchange.ts':['star_crumb_exchange.json','const exchangeList','const targetId','givePlayerEquipmentSync'],
 'src/routes/api/equipment.ts':['const equipment = getPlayerEquipmentSync','if (!equipment)','generate_ability_soul','getPlayerEquipmentSync(playerId, equipmentId)'],
 'src/routes/api/sell.ts':['getPlayerEquipmentSync','calculateDissolveRewards','Not enough'],
 'src/lib/item-sell.ts':['getPlayerItemSync','currentCount','Insufficient','item_sale'],
 'src/routes/web_api/mail.ts':['CDN_ITEM_IDS','CDN_EQUIP_IDS','fastify.post("/send"','insertMailSync'],
 'src/routes/web_api/player.ts':['VALID_ITEM_IDS.has','givePlayerItemSync'],
 'src/lib/management-auth.ts':['function isManagementPath','"/api/mail"','installManagementAuth','some(isManagementPath)','unauthorized'],
 'src/cn-server.ts':['installManagementAuth(fastify)','Gift code exchange','indexWebApiPlugin, { prefix'],
 'src/routes/api/mail.ts':['getPlayerMailSync','getPlayerMailsSync','givePlayerEquipmentSync','mail.type_id'],
 'src/data/domains/player.ts':['export function insertDefaultPlayerSync','insertPlayerItemsSync(playerId, {})','insertPlayerEquipmentListSync(playerId, {})'],
 'src/routes/cn/tool.ts':['insertDefaultPlayerSync','insertAccountSync'],
 'src/routes/api/tool.ts':['insertDefaultPlayerSync'],
 'src/lib/player-login.ts':['insertDefaultPlayerSync'],
 'src/routes/web_api/server.ts':['const template = loadDefaultSaveTemplate()','restorePlayerSaveSnapshotV2Sync(snapshot, player.id','() => insertDefaultPlayerSync(accId)'],
 'src/data/defaultSave.ts':['const FILE','export function loadDefaultSaveTemplate','parsed?.schema','return parsed;'],
 'src/data/domains/account.ts':['export function insertAccountSync','INSERT INTO accounts'],
}
for p,terms in specs.items():
    raw=source['source_snippets'].get(p) or git('show',REF+':'+p)
    lines=raw.splitlines(); snips=[]
    for i,line in enumerate(lines):
        if any(t in line for t in terms):
            snips.append({'line':i+1,'text':'\n'.join(lines[max(0,i-2):min(len(lines),i+6)])})
    evidence.append({'file':p,'sha256':hashlib.sha256(raw.encode()).hexdigest(),'snippets':snips})
body_paths=set(source['server_assets'])
client_tables={x['logical_path'] for x in client}
expected_client={'master/item/equipment.orderedmap','master/item/item.orderedmap','master/item/equipment_status.orderedmap','master/ability/ability_soul.orderedmap'}
assert client_tables==expected_client,client_tables
assert not base_route_hits,base_route_hits
assert not parse_errors,parse_errors
review={
 'scope':'固定灰 1.4.136 本地源码和 assets；我方 1.4.219 全部非 asset-patch JSON、131–219 CDN 终态和未修改的可定位基础获取表。只读静态审计；未运行服务器、客户端或网络。',
 'hui_ref':REF, 'gm_weapon_ids':list(range(5990001,5990007)),
 'server_json_files_scanned':len(server_files),'server_json_parse_errors':parse_errors,
 'server_gm_body_files':source['server_assets'],'hui_server_gm_references':source['hui_assets'],
 'client_final_unique_members':len(index),'client_decodable_members':parsed,
 'client_gm_reference_tables':client,'base_unchanged_route_tables_scanned':base_route_scanned,
 'base_unchanged_route_table_hits':base_route_hits,
 'actual_normal_player_acquisition_rows':[], 'mixed_normal_and_gm_acquisition_rows':[],
 'exclude_acquisition_rows':[],
 'new_account_automatic_all_ids_grant':False,
 'default_template_boundary':'固定灰新建账号的insertDefaultPlayerSync显式传入空物品和空装备；注册表不扩展开户库存。管理后台/newSave可另行恢复管理员上传的V2默认存档模板，此内容来自运行目录default_save.json，不属于本包；线上模板及历史库存未读取、未核实。',
 'conclusions':[
  'GM 本体、魂珠、状态、能力引用之外，未发现当前输入数据中的 GM 商店、掉落、奖励、任务、兑换、邮件或礼包获取行；排除明细为零，不构造不存在的行。',
  '固定灰源码的普通/宝物/星粒/活动/领主币商店读取显式商品表；getShopItemSync 不用 item_ids/equipment_ids 自动生成商品。武器卡池使用显式 gacha.pool。',
  'equipment_ids 中注册 GM 不会扩展五重诅咒掉落：候选固定为 5910101..5910129，再与注册表求交集；5990001..6 不在候选中。',
  'item_ids/equipment_ids 是注册/校验数据，同时让既有管理后台可识别这些 ID。已有管理接口手工给道具/发送附件可显式授予 GM；这是需管理员操作的既有能力，不是新邮件/礼包条目或玩家正常获取。',
  'equipment_dissolve.generate_ability_soul 和升级/分解会在已持有该 GM 武器时产出同 ID 魂珠；它们要求已持有武器，属于本体正常使用配套，不能从空账号生成第一把 GM。item_sale 为出售已有魂珠换玛纳，不是买入。',
  '普通新建账号经 insertDefaultPlayerSync 显式初始化空物品与空装备，并不枚举 item_ids/equipment_ids；管理后台 newSave 可另恢复管理员预置的 V2 默认模板。此运行目录模板和历史库存未读取、未核实，本包不提供或修改模板。',
  '未发现获取行与正常内容混在一行且不可拆分的情况。',
  '本审计不能证明线上数据库没有历史GM附件/库存，也不核实运行时配置；这些属于未核实，包内不新增任何GM获取条目。',
 ],
 'source_evidence':evidence,
}
(A/'gm-route-review-r3.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
lines=['# 第三轮 GM 武器获取边界审查','',review['scope'],'',f'固定灰 ref：`{REF}`。服务端扫描 {len(server_files)} 个 JSON，解析失败 0；我方 CDN 终态 {len(index)} 个成员，其中可解码 {parsed} 个；额外扫描未修改的基础获取表 {len(base_route_scanned)} 张。','',
 '## 结论','']
for c in review['conclusions']: lines.append('- '+c)
lines+=['','## 新账号／默认模板核对','',
 '固定灰 `src/data/domains/player.ts:665` 显式调用 `insertPlayerItemsSync(playerId, {})`，`:668` 调用 `insertPlayerEquipmentListSync(playerId, {})`。普通新建、登录建号调用同一默认函数，注册 ID 不会自动授予全物品或全装备。',
 '管理后台 `newSave` 另可加载管理员预置的 V2 完整模板，再恢复其库存；模板来自运行目录中的 `default_save.json`。线上模板、历史邮件及库存均未读取、未核实，本包未提供或修改模板。固定 ref 代码位置和 SHA256 记录在下方源码证据与 JSON 中。',
 '','## GM 本体服务端行（并非商品/奖励）','','| 文件 | 键 / ID | 解释 |','|---|---|---|']
explain={
 'equipment_dissolve.json':'已持有武器升级/分解产魂珠；正常使用配套',
 'equipment_element.json':'属性登记','equipment_ids.json':'装备注册及后台附件校验；五重只与固定诅咒候选池求交',
 'equipment_lookup.json':'名称/稀有度/分类','equipment_max_level.json':'最大觉醒等级',
 'item_ids.json':'魂珠注册及后台道具/附件校验','item_lookup_cnmod.json':'魂珠文本',
 'item_sale.json':'出售已有魂珠换玛纳；不是购买',
}
for p in sorted(body_paths): lines.append(f'| `{p}` | `5990001–5990006` | {explain[Path(p).name]} |')
lines+=['','## 客户端终态 GM 行','','| 表 | 键 | 引用数 |','|---|---|---|']
for t in client: lines.append(f"| `{t['logical_path']}` | `5990001–5990006` | {len(t['references'])} |")
lines+=['','## 刻意不收入的 GM 获取途径行','','当前输入中未发现可列出的 GM 获取行，故实际排除行数为 **0**。逐类扫描的空结果记录在 JSON；不能把武器本体/魂珠注册表伪报为商品或奖励。','',
 '## 通用代码入口核对','','以下均为固定灰 ref 的源码行号；完整片段及 SHA256 保存在同名 JSON：','']
for e in evidence:
    lines.append('- `'+e['file']+'`：'+', '.join(str(s['line']) for s in e['snippets']))
(A/'gm-route-review-r3.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'server_jsons':len(server_files),'cdn_final_members':len(index),'cdn_decodable':parsed,
                  'cdn_gm_tables':sorted(client_tables),'base_route_tables':len(base_route_scanned),
                  'actual_acquisition_exclusions':0,'mixed_rows':0},ensure_ascii=False))
