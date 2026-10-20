import sys, zipfile, re, json
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
import os; os.environ["WF_TIP"]="149"
from live149 import *
from layout import *
src = json.load(open(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build/official_src.json"))
def off(lp):
    z, m = src[lp]
    with zipfile.ZipFile(r"D:/WF/startpoint-cn-kulo/.cdn/cn/archive-common-full/" + z) as zf:
        return q.parse_node(zf.read(m))
AB = off("master/ability/ability.orderedmap"); LE = off("master/ability/leader_ability.orderedmap")
C = off("master/character/character.orderedmap")
own = {}
for cid, v in C.items():
    r = row(v)
    for s in range(6): own[r[19+s]] = (cid, r[18])
pat = re.compile(sys.argv[1])
for name, T in (("ability", AB), ("leader_ability", LE)):
    for k, v in T.items():
        for i, x in enumerate([x for x in rows(v) if x]):
            try: d = D.describe_line(x, name)
            except Exception as e: continue
            if pat.search(d): print(name, k, own.get(k, ('', ''))[1], i, d)
