import sys
from base149 import *
T = {
 'EQ':"master/item/equipment.orderedmap",'ITEM':"master/item/item.orderedmap",'SOUL':"master/ability/ability_soul.orderedmap",
 'EQS':"master/item/equipment_status.orderedmap",'ENH':"master/equipment_enhancement/equipment_enhancement.orderedmap",
 'ENHS':"master/equipment_enhancement/equipment_enhancement_status.orderedmap",'EA':"master/equipment_enhancement/equipment_enhancement_ability.orderedmap",
 'SHOP':"master/equipment_enhancement/equipment_enhancement_shop.orderedmap",'CAT':"master/equipment_enhancement/equipment_enhancement_shop_category.orderedmap"}
ids = sys.argv[1:]
for k,lp in T.items():
    print('#####',k,lp,source(lp))
    t = load(lp)
    if k=='CAT':
        for kk,v in t.items(): print(kk, v)
        continue
    for i in ids:
        if k=='SHOP':
            for kk,v in t.items():
                if kk.startswith(i) and len(kk)==len(i)+2: print(kk, v)
            continue
        print('--',i); v=t.get(i); print(v if v is not None else 'MISSING')
