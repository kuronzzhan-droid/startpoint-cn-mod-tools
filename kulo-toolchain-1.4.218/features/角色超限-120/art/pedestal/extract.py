import sys, hashlib, zlib, io, json, os
sys.path.insert(0, r"D:/WF/startpoint-cn-kulo/tools/fantasy-gauntlet-mod-tools")
import wf_mod_tool as core
from PIL import Image
SALT="K6R9T9Hz22OpeIGEWB0ui6c6PYFQnJGy"
ROOTS=[r"D:/WF/out/kulo-patch-toolkit/store131/production/"+r for r in ("upload","medium_upload","android_upload")]
def find(lp):
    h=hashlib.sha1((lp+SALT).encode()).hexdigest()
    for r in ROOTS:
        p=os.path.join(r,h[:2],h[2:])
        if os.path.exists(p): return p
for lp in ["character_pedestal/sprite_sheet.png","character_pedestal/sprite_sheet.atlas.amf3.deflate","character_pedestal/sprite_sheet.atf"]:
    print(lp, find(lp))
raw=open(find("character_pedestal/sprite_sheet.atlas.amf3.deflate"),'rb').read()
for b in (raw, raw[4:]):
    for w in (15,-15):
        try: atlas=core.AMF3Reader(zlib.decompress(b,w)).read_value(); break
        except Exception: atlas=None
    if atlas: break
print(type(atlas), str(atlas)[:500])
png=bytearray(open(find("character_pedestal/sprite_sheet.png"),'rb').read()); png[1:4]=b"PNG"
im=Image.open(io.BytesIO(bytes(png))); print(im.size, im.mode); im.save("sheet.png")
json.dump(atlas, open("atlas.json","w"), ensure_ascii=False, indent=0, default=str)
