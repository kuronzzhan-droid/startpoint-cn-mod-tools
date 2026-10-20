"""固定输入、只读链视图与 orderedmap 工具；所有缓存严格限制在本工作区。"""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import zipfile

sys.dont_write_bytecode = True
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / '交付'
CACHE = ROOT / 'cache'
KULO = Path('D:/WF/startpoint-cn-kulo')
TOOL = KULO / 'tools/fantasy-gauntlet-mod-tools'
BASE = Path('D:/WF/out/kulo-patch-toolkit/store131')
OURS_MANIFEST = Path('D:/WF/out/角色超限-120/localsrv219/assets/asset-patch/manifest.json')
OURS_DIRS = [Path('D:/WF/out/碧-1.4.216/localsrv-216/assets/asset-patch/active'),
             Path('D:/WF/out/角色超限-120/patch')]
sys.path.insert(0, str(TOOL))
import wf_quest_lib as q

def sha(b):
    return hashlib.sha256(b).hexdigest()

def write_json(path, value):
    path = Path(path).resolve()
    assert path.is_relative_to(ROOT.resolve()), path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def git_show(path, ref='origin/main'):
    return subprocess.check_output(['git', '-C', str(KULO), 'show', f'{ref}:{path}'])

def member(logical, area='upload'):
    h = hashlib.sha1((logical + q.SALT).encode()).hexdigest()
    return f'production/{area}/{h[:2]}/{h[2:]}'

def cells(s):
    return next(csv.reader([s]))

def join(c):
    f = io.StringIO()
    csv.writer(f, lineterminator='').writerow(c)
    return f.getvalue()

def version(v):
    return int(v.split('.')[-1]) if re.fullmatch(r'1\.4\.\d+', v) else -1

def archives(e):
    return e.get('chain') or [e['archive']]

class View:
    def __init__(self, kind):
        self.kind = kind
        CACHE.mkdir(exist_ok=True)
        lock_path = OUT / 'build/source-lock.json'
        lock = json.loads(lock_path.read_text('utf-8')) if lock_path.exists() else None
        pin = CACHE / 'kulo-ref.json'
        if not pin.exists():
            ref = subprocess.check_output(['git', '-C', str(KULO), 'log', '-1', '--format=%H', 'origin/main']).decode().strip()
            write_json(pin, {'ref': ref})
        self.ref = lock['hui_ref'] if lock else json.loads(pin.read_text('utf-8'))['ref']
        self.manifest = json.loads(git_show('assets/asset-patch/manifest.json', self.ref)) if kind == 'hui' else json.loads(OURS_MANIFEST.read_text('utf-8-sig'))
        if lock and kind == 'ours':
            assert sha(OURS_MANIFEST.read_bytes()) == lock['our_manifest_sha256'], 'locked our manifest changed'
        self.index = {}
        self.sources = []
        self.edges = []
        tip = 136 if kind == 'hui' else 219
        for e in self.manifest['patches']:
            if not e.get('enabled', True) or not 131 <= version(e['version']) <= tip:
                continue
            self.edges.append(e)
            for name in archives(e):
                if kind == 'hui':
                    p = CACHE / 'hui' / name
                    if not p.exists():
                        p.parent.mkdir(exist_ok=True)
                        p.write_bytes(git_show('assets/asset-patch/active/' + name, self.ref))
                else:
                    p = next((d / name for d in OURS_DIRS if (d / name).exists()), None)
                    if p is None:
                        raise FileNotFoundError(name)
                raw = p.read_bytes()
                if lock and kind == 'ours':
                    assert sha(raw) == lock['our_archives'][name], ('locked input sha256', name)
                expected = next((x for x in e.get('archive_integrity', []) if x['name'] == name), {})
                if expected.get('sha256'):
                    assert sha(raw) == expected['sha256'], ('input sha256', name)
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    names = [n for n in z.namelist() if not n.endswith('/')]
                    assert len(names) == len(set(names)), name
                    for n in names:
                        assert re.fullmatch(r'production/(?:medium_upload|android_upload|ios_upload|upload)/[a-f0-9]{2}/[a-f0-9]{38}', n), (name, n)
                        self.index[n] = p
                self.sources.append({'name': name, 'path': str(p), 'size': len(raw), 'sha256': sha(raw), 'version': e['version']})
        assert [version(e['version']) for e in self.edges] == list(range(131, tip + 1))

    def raw(self, m):
        if m in self.index:
            with zipfile.ZipFile(self.index[m]) as z:
                return z.read(m)
        return base_raw(m)

    def load(self, logical):
        b = self.raw(member(logical))
        return q.parse_node(b) if b is not None else None

def base_raw(m):
    p = BASE / m
    return p.read_bytes() if p.exists() else None

def logical_index():
    paths = set()
    f = TOOL / 'WF_PATHLIST_recovered.txt'
    for line in f.read_text('utf-8-sig').splitlines():
        s = line.strip()
        if s and not s.startswith('#'):
            paths.add(s)
    # 新增路径可能尚未收进 recovered，取只读构建脚本中的字面路径。
    dirs = [Path('D:/WF/out/kulo-patch-toolkit/cursed_abyss/build'),
            Path('D:/WF/out/角色超限-120'), Path('D:/WF/out/碧-1.4.216/build'),
            Path('D:/WF/out/赛瑞斯重做-20261014')]
    for d in dirs:
        if d.exists():
            for p in d.rglob('*.py'):
                if p.stat().st_size > 1500000:
                    continue
                text = p.read_text('utf-8-sig', errors='replace')
                paths.update(re.findall(r'(?:master|character|battle|item|ui|world|quest)/[A-Za-z0-9_./$-]+\.(?:orderedmap|amf3\.deflate|atf\.deflate|png|mp3|json)', text))
    result = {}
    for p in sorted(paths):
        result[member(p)] = p
        result[member(p, 'medium_upload')] = p
    return result

def leaves(node, path=()):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from leaves(v, path + (k,))
    else:
        yield path, node
