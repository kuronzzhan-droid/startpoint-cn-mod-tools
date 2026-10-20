import sys; sys.path.insert(0, r"D:/WF/out/万圣新角色-20261016/build")
from view import *
TX = load('master/character/character_text.orderedmap')
C = load('master/character/character.orderedmap')
for k, v in C.items():
    r = row(v)
    if any(r[0].startswith(p) for p in ['lich','lady_android','crystal_swordman','blade_witch']):
        print(k, r[0], r[1:8], rows(TX[k])[0][0] if k in TX else '', rows(TX[k])[0][3] if k in TX else '')
# free ids near customs
used = set(C.keys())
for base in [139980,169980,159980,149980]:
    print(base, [i for i in range(base, base+20) if str(i) not in used][:20])
