import os; os.environ["WF_EXTRA_DIRS"]=r"D:/WF/out/凉月修复-20261016/handoff-213"
import env; env.setup(213)
from base149 import *
from base149 import _INDEX
import zipfile
m="production/upload/b4/a28679b8eeefdbdcbe6071fd4f2ff85e5b3415"
o=q.parse_node(zipfile.ZipFile(_INDEX[m]).read(m))
S=r"C:/Users/12101/AppData/Local/Temp/claude/D--WF-startpoint-cn/a2145ccb-7177-4f83-94fc-33a202dbacd2/scratchpad"
for i in (1,2,3):
    z=zipfile.ZipFile(f"{S}/k135-{i}.zip")
    if m in z.namelist(): t=q.parse_node(z.read(m))
print(list(o)[:5]); print("O",str(o["159992"])[:500]); print("T",str(t["159992"])[:500])
for lp in ["master/character/character_speech.orderedmap","master/sound/voice_volume.orderedmap","master/character/character_voice.orderedmap"]:
    print(lp, member(lp)==m)
