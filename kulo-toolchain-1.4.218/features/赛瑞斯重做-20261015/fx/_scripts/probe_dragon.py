import sys,zlib,io,json
sys.path.insert(0,r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
import os; os.chdir(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
from live149 import *
import wf_dsl
from PIL import Image
P=r"D:/WF/out/赛瑞斯重做-20261015/pixel/final_USER_DB/game/character/seris_dragon_king/pixelart/"
def amf(fn): return wf_dsl.parse_dsl(zlib.decompress(open(P+fn,'rb').read(),-15))['tree']
tl=amf("special.timeline.amf3.deflate"); print(json.dumps(tl['sequences']))
fr=amf("special.frame.amf3.deflate"); print(fr)
at=amf("special_sprite_sheet.atlas.amf3.deflate"); print(len(at),at[:3])
b=bytearray(open(P+"special_sprite_sheet.png",'rb').read()); b[1:4]=b'PNG'; im=Image.open(io.BytesIO(bytes(b))); im.save(r"D:/WF/out/赛瑞斯重做-20261015/fx/_scripts/dragon_special.png")
print(sorted({a['n'].split('/')[-2] if '/' in a['n'] else a['n'][:-5] for a in at}))
