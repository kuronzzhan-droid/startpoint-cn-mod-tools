"""只读固定灰源码和 219 assets；仅写本目录审计结果。"""
import json, os, re, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.stdout.reconfigure(encoding='utf-8')
ROOT = Path(__file__).resolve().parents[2]/'audit'
ROOT.mkdir(exist_ok=True)
REPO = Path('D:/WF/startpoint-cn-kulo')
OURS = Path('D:/WF/out/角色超限-120/localsrv219/assets')
REF = '224aa2a663b7756fc8a34c0f37f1ae61ad81800c'
IDS = {str(i) for i in range(5990001, 5990007)}
PAT = re.compile(r'(?<!\d)599000[1-6](?!\d)')
def git(*a):
    return subprocess.check_output(['git','-C',str(REPO),*a]).decode('utf-8')
def walk(v,p=()):
    if isinstance(v,dict):
        for k,x in v.items():
            if PAT.search(str(k)): yield p+(str(k),), {'key':str(k),'value':x}
            yield from walk(x,p+(str(k),))
    elif isinstance(v,list):
        for i,x in enumerate(v): yield from walk(x,p+(str(i),))
    elif PAT.search(str(v)): yield p,v
def scan(v):
    return [{'key_path':list(p),'value':x} for p,x in walk(v)]
trees = git('ls-tree','-r','--name-only',REF).splitlines()
data = {'fixed_hui_ref':REF,'our_tip':'1.4.219','server_assets':{},'hui_assets':{},'source_mentions':{},'source_snippets':{}}
for p in OURS.rglob('*.json'):
    if 'asset-patch' in p.parts: continue
    try: v=json.loads(p.read_bytes())
    except Exception: continue
    found=scan(v)
    if found: data['server_assets']['assets/'+p.relative_to(OURS).as_posix()] = found
for p in trees:
    if p.startswith('assets/') and p.endswith('.json') and not p.startswith('assets/asset-patch/'):
        try: v=json.loads(git('show',REF+':'+p))
        except Exception: continue
        found=scan(v)
        if found: data['hui_assets'][p]=found
    if not p.startswith('src/') or not p.endswith('.ts'): continue
    raw=git('show',REF+':'+p); lines=raw.splitlines()
    terms=[]
    for i,line in enumerate(lines):
        if re.search(r'serverItemIds|item_ids|equipment_ids|equipmentIds|equipment_ids|itemIds|baseItemIds|generic.*shop|all.*equipment|Object\.keys\(equipment|Object\.entries\(equipment|599000[1-6]',line,re.I):
            terms.append({'line':i+1,'text':line})
    if terms: data['source_mentions'][p]=terms
    if p in ['src/lib/assets.ts','src/lib/content-master.ts','src/lib/gacha.ts','src/routes/web_api/mail.ts','src/lib/newbie.ts','src/lib/equipment-dissolve.ts','src/routes/api/equipment.ts','src/routes/api/item.ts','src/routes/web_api/validation.ts','src/lib/management-auth.ts','src/routes/api/exchange.ts','src/routes/api/howToGet.ts']:
        data['source_snippets'][p]=raw
(ROOT/'gm-route-source-r3.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('OUR_FILES',[(p,len(v)) for p,v in data['server_assets'].items()])
print('HUI_FILES',[(p,len(v)) for p,v in data['hui_assets'].items()])
print('SOURCE_MENTIONS')
for p,v in data['source_mentions'].items():
    print(p)
    for t in v: print(t['line'],t['text'])
