import sys, os
os.environ.setdefault('WF_TARGET_STORE',"C:/Users/12101/AppData/Local/Temp/claude/D--WF-startpoint-cn/0f92a444-f33c-48d5-8e42-5c531625b594/scratchpad/store131/production/upload")
sys.path.insert(0,'D:/WF/startpoint-cn-kulo/tools/fantasy-gauntlet-mod-tools')
sys.stdout.reconfigure(encoding='utf-8')
import wf_quest_lib as q
_cache={}
def T(name):
    p = name if name.startswith('master/') else f'master/{name}.orderedmap'
    if p not in _cache: _cache[p]=q.load_table(p)
    return _cache[p]
def rows(name, keys):
    t=T(name)
    for k in keys:
        print(name, k, '=>', repr(t.get(str(k)))[:3000])
