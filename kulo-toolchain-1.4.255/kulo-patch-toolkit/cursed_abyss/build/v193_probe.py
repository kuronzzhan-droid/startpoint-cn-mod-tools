# -*- coding: utf-8 -*-
import os; os.environ["WF_TIP"]="192"
import sys; sys.path.insert(0, r"D:/WF/startpoint-cn-wiki/mod-tools")
from p192_common import *
import wf_share_update_codec as codec
print([z.name for z in base149._ZIPS][-6:])
SP="master/character/character_speech.orderedmap"
for r in ROOTS:
    raw,src=aread(r,SP); print(r, src, raw and len(raw))
raw,src=aread("upload",SP); flat=codec.unpack(raw)
print(len(flat), list(flat)[:5])
for cid in ("149999","129992","169995"):
    print("==",cid, cid in flat)
    if cid in flat:
        for row in codec.node(flat[cid])['csv']: print(row)
