import os,sys,json,zlib,glob
os.environ["WF_TIP"]="197"
from live149 import *
import wf_dsl
from dsltools import commands
for f in sorted(glob.glob(r"D:/WF/pkgarchive/ma-magnus-20260920-1.4.1002/roots/common/battle/action/**/*.deflate", recursive=True)):
    t=wf_dsl.parse_dsl(zlib.decompress(open(f,'rb').read(),-15))["tree"]
    s=json.dumps(t,ensure_ascii=False)
    print(os.path.basename(f), 'Resist' in s, [c[0] for p,c in commands(t,'CreateCondition')], [ac[0] for p,c in commands(t,'CreateCondition') for ac in c[2]])
