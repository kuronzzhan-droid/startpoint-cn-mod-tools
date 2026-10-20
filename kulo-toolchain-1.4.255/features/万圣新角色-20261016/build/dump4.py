import sys; sys.path.insert(0, r"D:/WF/out/万圣新角色-20261016/build")
from view import *
from layout import *
sys.argv = ['x'] + sys.argv[1:]
exec(open(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build/dump_char.py", encoding='utf-8').read().split("from layout import *",1)[1])
