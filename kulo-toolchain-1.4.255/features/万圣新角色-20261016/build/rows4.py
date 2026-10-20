import sys; sys.path.insert(0, r"D:/WF/out/万圣新角色-20261016/build")
from view import *
C = load('master/character/character.orderedmap')
for k in ['231009','161004','151033','341003','169978','159992']:
    r = row(C[k]); print(k, len(r), list(enumerate(r)))
