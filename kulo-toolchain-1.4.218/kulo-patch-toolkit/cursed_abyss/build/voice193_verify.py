# -*- coding: utf-8 -*-
import os; os.environ["WF_TIP"]="192"
B=os.path.dirname(os.path.abspath(__file__))
os.environ["WF_EXTRA_ZIPS"]=os.path.join(B,"..","patch","pinball-1.4.192-1.4.193-1-gerald-voice-local.zip")
import sys; sys.path.insert(0, r"D:/WF/startpoint-cn-wiki/mod-tools")
from p192_common import *
import json, wf_assets, wf_share_update_codec as codec
SRC=Path(r"D:/WF/out/杰拉德语音重录-20261008/成品")
mem=json.loads((Path(B)/"out193_voice"/"members.json").read_text("utf8"))
ok=0
for p in sorted(SRC.rglob("*.mp3")):
    slot=p.relative_to(SRC).with_suffix("").as_posix(); lp=f"character/white_wolf_gerald/voice/{slot}.mp3"
    b,src=aread("upload",lp); assert src.startswith("pinball-1.4.192-1.4.193"),(slot,src)
    assert wf_assets.mp3_decode(b)==p.read_bytes(); ok+=1
    assert (Path(B)/"out193_voice"/"members"/amember("upload",lp)).read_bytes()==b
print("voices ok",ok)
raw,src=aread("upload","master/character/character_speech.orderedmap"); print("table from",src)
base=None
import base149
flat=codec.unpack(raw)
for r in codec.csv_read(flat["149999"]): print(r)
lines={x["path"]:x["zh"] for x in json.loads((SRC/"台词清单.json").read_text("utf8"))}
rows={r[4]:r for r in codec.csv_read(flat["149999"])}
for s in [f"home/home_{i}" for i in range(12)]+["ally/join","ally/evolution"]:
    assert rows[s][3]==lines[s]
    if s.startswith("home"): assert rows[s][1]=="2"
print("rows ok", len(rows))
# all member sha match
for m,v in mem.items():
    assert hashlib.sha256((Path(B)/"out193_voice"/"members"/m).read_bytes()).hexdigest()==v["sha256"]
print("members.json ok", len(mem))
