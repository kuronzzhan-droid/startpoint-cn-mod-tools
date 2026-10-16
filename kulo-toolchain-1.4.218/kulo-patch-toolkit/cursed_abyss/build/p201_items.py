import os,sys,json,hashlib
os.environ["WF_TIP"]="200"
from live149 import *
L='master/battle/item/executable_instant_item_level.orderedmap'
E='master/battle/item/executable_instant_item.orderedmap'
D='master/battle/yakumono/direct_instant_item.orderedmap'
raw,src=read_raw(L); print('level src',src,hashlib.sha256(raw).hexdigest(),len(raw))
lv=load(L); e=load(E); d=load(D)
print('eii src',source(E),'dii src',source(D))
print('lv',len(lv),list(lv.items())[:5])
print('eii-lv',sorted(set(e)-set(lv)))
print('lv-eii',sorted(set(lv)-set(e)))
print('dii keys-lv',sorted(set(d)-set(lv)))
print('dii c1 -lv',sorted({row(v)[1] for v in d.values()}-set(lv)))
print('dii c1 -eii',sorted({row(v)[1] for v in d.values()}-set(e)))
print('dii sample',list(d.items())[:4])
