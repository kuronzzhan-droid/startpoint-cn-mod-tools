# -*- coding: utf-8 -*-
import os; os.environ["WF_TIP"]="192"
import sys; sys.path.insert(0, r"D:/WF/startpoint-cn-wiki/mod-tools")
from p192_common import *
import wf_share_update_codec as codec
raw,_=aread("upload","master/character/character.orderedmap"); flat=codec.unpack(raw)
for cid in ("169995","149999","129992"): print(cid, codec.node(flat[cid])['csv'][0][:3])
