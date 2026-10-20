import sys, json
sys.path.insert(0, '.')
import v245 as V, psim as P
info = json.load(open('x245/info.json', encoding='utf8'))
AB, LE, CH, UQ = (V.load(x) for x in (V.AB, V.LE, V.CH, V.UQ))
def rws(t, k):
    v = t.get(k); return [r for r in V.rows(v) if r] if v else []
B = {"ability": dict(V.D.layout("ability")["blocks"]), "leader_ability": dict(V.D.layout("leader_ability")["blocks"])}
out = []
for cid in sorted(info):
    ch = rws(CH, cid)[0]
    for nm, tb, T, key in [("队长技", "leader_ability", LE, cid)] + [(f"能力{i}", "ability", AB, ch[18 + i]) for i in range(1, 7)]:
        for i, r in enumerate(rws(T, key)):
            rd, iss, ct = P.simulate(tb, r)
            for c, v, n in ct:
                b = [k for k, base in B[tb].items() if base == c]
                if not b: continue
                b = b[0]
                if n == "ConditionCountUnique" and b.startswith("precondition"):
                    th = int(r[c + 4] or 0) / 100000
                    u = r[c + 6]; ur = rws(UQ, u)[0]
                    if th > 1: out.append((cid, f"{nm}#{i}", key, i, tb, c, f"前置188 ≥{th:g} 固有{u}「{ur[1]}」上限{ur[4]}"))
                if n == "ConditionCountUnique" and b == "during_trigger":
                    lim = r[c + 5]; u = r[c + 7]; ur = rws(UQ, u)[0]
                    if lim not in ("1", "(None)", "") and ur[4] not in ("1", "(None)"):
                        out.append((cid, f"{nm}#{i}", key, i, tb, c, f"持续194 限{lim}次 固有{u}「{ur[1]}」上限{ur[4]}"))
                    elif lim == "(None)" and ur[4] not in ("1", "(None)"):
                        out.append((cid, f"{nm}#{i}", key, i, tb, c, f"持续194 无上限 固有{u}「{ur[1]}」上限{ur[4]}(?)"))
for o in out: print(o[0], o[1], o[6])
json.dump(out, open('count_sweep.json', 'w', encoding='utf8'), ensure_ascii=False)
