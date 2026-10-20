import os,zipfile,json,hashlib
os.environ["WF_TIP"]="192"
from live149 import *
P=Path(__file__).resolve().parent.parent
z=zipfile.ZipFile(P/"patch/pinball-1.4.192-1.4.193-1-gm-weapon6-local.zip")
integ=json.loads((P/"patch/pinball-1.4.192-1.4.193-1-gm-weapon6-local.integrity.json").read_text("utf-8"))
for n,lp in integ["logical_paths"].items():
    raw,src=read_raw(lp); old=q.parse_node(raw); new=q.parse_node(z.read(n))
    added=[k for k in new if k not in old]; changed=[k for k in old if new.get(k)!=old[k]]
    print(lp,src,"rt_bytes_equal",q.build_node(old)==raw,"added",added,"changed",changed,
          "disk==zip",(P/"patch/gm-weapon6-members"/n).read_bytes()==z.read(n))
import difflib
for f in sorted((P/"server19").iterdir()):
    a=(ASSETS/f.name).read_text("utf-8").splitlines(); b=f.read_text("utf-8").splitlines()
    d=[l for l in difflib.unified_diff(a,b,lineterm="",n=0) if l[:1] in "+-" and not l.startswith(("+++","---"))]
    print(f.name, d)
