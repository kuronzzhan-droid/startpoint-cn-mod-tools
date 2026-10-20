import sys, json, collections
sys.path.insert(0, '.')
import v245 as V, psim as P
idx = json.load(open(r'D:/WF/out/面板核对-1.4.227/audit/index.json', encoding='utf8'))
SC = {x['id'] for x in idx} | {'129989'}
res = collections.Counter(); offi = collections.Counter(); hits = []
for lp, tb in ((V.AB, "ability"), (V.LE, "leader_ability")):
    T = V.load(lp)
    for k, v in T.items():
        cid = k if tb == "leader_ability" else k[:-1]
        for i, r in enumerate(x for x in V.rows(v) if x):
            reads, iss, ct = P.simulate(tb, r)
            for it in iss:
                key = (tb, it[0], it[1] if len(it) > 1 else None)
                if cid in SC:
                    res[key] += 1; hits.append((tb, k, i, it))
                else:
                    offi[key] += 1
print("SCOPE", res.most_common(40))
print("OFFICIAL", offi.most_common(40))
json.dump([list(map(str, h)) for h in hits], open("sim_hits.json", "w"), ensure_ascii=False, indent=0)
