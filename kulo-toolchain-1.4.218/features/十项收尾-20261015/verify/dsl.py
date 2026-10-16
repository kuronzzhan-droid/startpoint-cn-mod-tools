import os,sys,json
sys.path.insert(0,r'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build'); os.chdir(r'D:/WF/out/kulo-patch-toolkit/cursed_abyss/build')
from live149 import *
print(json.dumps(dsl_tree(sys.argv[1]),ensure_ascii=False)[:int(sys.argv[2]) if len(sys.argv)>2 else 3000])
