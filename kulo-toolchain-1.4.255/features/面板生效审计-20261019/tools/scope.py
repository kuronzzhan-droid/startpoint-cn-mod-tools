import sys, json
sys.path.insert(0, '.')
import v245 as V
def base(lp):
    m = V.member(lp)
    p = V.STORE131 / m.split('production/upload/')[1]
    return V.q.parse_node(p.read_bytes()) if p.exists() else {}
out = {}
for lp in (V.AB, V.LE, V.CH, V.CAS, V.AS):
    t, b = V.load(lp), base(lp)
    out[lp] = (t, b)
CHt, CHb = out[V.CH]
ABt, ABb = out[V.AB]; LEt, LEb = out[V.LE]
scope = {}
for cid in CHt:
    keys_ab = [k for k in ABt if k[:-1] == cid and len(k) == len(cid) + 1]
    why = []
    if cid not in CHb: why.append("new")
    if LEt.get(cid) != LEb.get(cid): why.append("leader")
    for k in keys_ab:
        if ABt.get(k) != ABb.get(k): why.append("ab" + k[-1])
    if why: scope[cid] = why
print(len(CHt), len(CHb), len(scope))
json.dump(scope, open("scope.json", "w"), ensure_ascii=False, indent=0)
