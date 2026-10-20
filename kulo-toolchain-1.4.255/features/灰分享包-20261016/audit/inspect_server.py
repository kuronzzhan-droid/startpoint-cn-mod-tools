import json, os, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = Path(r'D:/WF/startpoint-cn-kulo')
OURS = Path(r'D:/WF/out/角色超限-120/localsrv219/assets')
ANCESTOR = '7e6d55b62eacca91ca7e557a02b5b9af6e2495a9'
HUI = 'origin/main'

def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])

def tree(ref):
    return {p for p in git('ls-tree','-r','--name-only',ref,'assets').decode().splitlines()
            if p.endswith('.json') and not any(p.startswith('assets/'+x) for x in ('asset-patch/','asset_lists/','gacha-movie-variants/'))}

def obj(ref,p):
    if p not in trees[ref]: return None
    return json.loads(git('show',f'{ref}:{p}'))

trees = {r:tree(r) for r in [ANCESTOR,HUI]}
files = trees[ANCESTOR] | trees[HUI] | {'assets/'+p.relative_to(OURS).as_posix() for p in OURS.rglob('*.json') if 'asset-patch' not in p.parts and 'asset_lists' not in p.parts and 'gacha-movie-variants' not in p.parts}
result = []
for p in sorted(files):
    op=OURS/p.removeprefix('assets/')
    if not op.exists(): continue
    b,h,o=obj(ANCESTOR,p),obj(HUI,p),json.loads(op.read_bytes())
    if b==o: continue
    row={'file':p,'base_type':type(b).__name__,'hui_type':type(h).__name__,'ours_type':type(o).__name__}
    if isinstance(o,dict) and (b is None or isinstance(b,dict)):
        bk=b or {}; hk=h or {}
        keys=[k for k in dict.fromkeys([*bk,*o]) if bk.get(k)!=o.get(k)]
        row.update(changes=len(keys),new=[k for k in keys if k not in bk],modified=[k for k in keys if k in bk and k in o],deleted=[k for k in keys if k not in o],hui_changed=[k for k in keys if hk.get(k)!=bk.get(k)],samples={k:o.get(k) for k in keys[:2]})
    elif isinstance(o,list) and isinstance(b,list):
        row.update(changes=len(o)-len(b),new=[v for v in o if v not in b],deleted=[v for v in b if v not in o])
    else: row.update(base=b,hui=h,ours=o)
    result.append(row)
(ROOT/'audit/server-inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for r in result: print(r['file'],r.get('changes'), 'new',str(r.get('new',''))[:300],'mod',str(r.get('modified',''))[:300],'del',str(r.get('deleted',''))[:80], 'hui',str(r.get('hui_changed',''))[:120])
