import sys; sys.path.insert(0, r"D:/WF/out/万圣新角色-20261016/build")
from view import *
TX = load('master/character/character_text.orderedmap')
C = load('master/character/character.orderedmap')
import base149; print(base149._ZIPS[-1].name)
for k, v in TX.items():
    r = rows(v)[0] if v else []
    s = ' | '.join(r[:4])
    if any(n in s for n in ['露迪','莫弥亚','塞里奥尔','瑞西塔尔','弥亚','里奥尔','西塔尔']):
        cr = row(C[k]) if k in C else []
        print(k, cr[:1], cr[2:12] if cr else '', '||', s[:200])
