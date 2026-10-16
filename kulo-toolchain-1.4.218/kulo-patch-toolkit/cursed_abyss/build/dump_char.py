import os, sys, json
os.environ.setdefault("WF_TIP", "158")
from live149 import *
from layout import *
C = load('master/character/character.orderedmap')
AB = load('master/ability/ability.orderedmap'); LE = load('master/ability/leader_ability.orderedmap')
CAS = load('master/string/custom_ability_string.orderedmap'); TX = load('master/character/character_text.orderedmap')
U = load('master/character/unique_condition.orderedmap')
for cid in sys.argv[1:]:
    r = row(C[cid]); code = r[0]
    print('#########', cid, code, r[18])
    print('TEXT', TX.get(cid))
    print('== leader', cid)
    for i, x in enumerate([x for x in rows(LE.get(cid, '')) if x]):
        print(f'  L{i}', D.describe_line(x, 'leader_ability'))
    ov = CAS.get(f'desc_override_{code}')
    if ov: print('  OVR:', rows(ov)[0][0].replace('\n', ' || '))
    for s in range(6):
        k = r[19 + s]
        print(f'== ability {s+1} {k} c1={rows(AB[k])[0][1] if k in AB else None}')
        for i, x in enumerate([x for x in rows(AB.get(k, '')) if x]):
            extra = ''
            if x[47] == '629': extra = ' DSL=' + x[col('ability','instant_content','action_path')]
            print(f'  A{s+1}.{i}', D.describe_line(x, 'ability'), extra)
        ov = CAS.get(f'desc_override_{code}_{s+1}')
        if ov: print('  OVR:', rows(ov)[0][0].replace('\n', ' || '))
    for k, v in CAS.items():
        if code in k and not k.startswith('desc_override'): print('  CAS', k, str(v)[:200])
