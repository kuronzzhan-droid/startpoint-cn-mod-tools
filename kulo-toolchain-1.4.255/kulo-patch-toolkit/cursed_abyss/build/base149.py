# -*- coding: utf-8 -*-
"""1.4.149 视图：store131 + active 中 1.4.131→1.4.149 各 local zip 成员覆盖（后者优先）。只读。"""
import hashlib, os, re, sys, zipfile, csv, io
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
SCR = Path(r"D:/WF/out/kulo-patch-toolkit")
STORE131 = SCR / "store131/production/upload"
ACTIVE = Path(r"D:/WF/startpoint-cn-kulo/assets/asset-patch/active")
KULO = Path(r"D:/WF/startpoint-cn-kulo")
TOOLS = KULO / "tools/fantasy-gauntlet-mod-tools"
os.environ.setdefault('WF_TARGET_STORE', STORE131.as_posix())
sys.path.insert(0, str(TOOLS))
import wf_quest_lib as q  # noqa
SALT = q.SALT

def member(logical):
    h = hashlib.sha1((logical + SALT).encode()).hexdigest()
    return f"production/upload/{h[:2]}/{h[2:]}"

_ZIPS = []
TIP = int(os.environ.get("WF_TIP", "149"))
for v in range(131, TIP):
    pat = re.compile(rf"^pinball-1\.4\.{v}-1\.4\.{v+1}-\d+-.*\.zip$")
    for name in sorted(os.listdir(ACTIVE)):
        if pat.match(name) and 'candidate' not in name:
            _ZIPS.append(ACTIVE / name)
for _x in filter(None, os.environ.get('WF_EXTRA_ZIPS', '').split(';')):
    _ZIPS.append(Path(_x))
_INDEX = {}
for z in _ZIPS:
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            _INDEX[n] = z  # later wins

def read_raw(logical):
    m = member(logical)
    if m in _INDEX:
        with zipfile.ZipFile(_INDEX[m]) as zf:
            return zf.read(m), _INDEX[m].name
    p = STORE131 / m.split('production/upload/')[1]
    return p.read_bytes(), 'store131'

def load(logical):
    raw, src = read_raw(logical)
    return q.parse_node(raw)

def source(logical):
    return read_raw(logical)[1]

def row(text):
    return next(csv.reader([text]))

def rows(text):
    return list(csv.reader(io.StringIO(text, newline='')))

def join(r):
    b = io.StringIO(); csv.writer(b, lineterminator='').writerow(r); return b.getvalue()

def join_rows(rs):
    return "\n".join(join(r) for r in rs)

if __name__ == '__main__':
    print([z.name for z in _ZIPS])
