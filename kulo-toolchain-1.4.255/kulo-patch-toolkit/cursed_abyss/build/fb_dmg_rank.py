import os, json, collections
os.environ.setdefault("WF_TIP", "187")
from live149 import *
from dsltools import commands
i = json.load(open("../patch/pinball-1.4.185-1.4.186-1-five-boss-buffs-local.integrity.json", encoding="utf-8"))
GB = load("master/battle/boss/general_boss.orderedmap"); BL = load("master/battle/boss/boss_level.orderedmap")
cache = {}
def prog_power(p):
    if p in cache: return cache[p]
    try: t = dsl_tree(p)
    except Exception: cache[p] = (0, 0, 0); return cache[p]
    pw = [c[6][0].get("max", 0) for _, c in commands(t, "CreateNormalAttack") if isinstance(c[6], list) and c[6]]
    rt = [c[3][0].get("max", 0) for _, c in commands(t, "CreateRatioAttack") if isinstance(c[3], list) and c[3]]
    cache[p] = (sum(pw), len(pw), sum(rt)); return cache[p]
by = collections.defaultdict(list)
for b in i["bosses"]:
    r = row(list(GB[b].values())[0]); nm = r[1] or r[3]
    progs = [x for x in r[110:] if x.startswith("battle/action/") and "$" in x]
    tot = [prog_power(p) for p in progs]
    nacts = sum(1 for t in tot if t[1] or t[2])
    s = sum(t[0] for t in tot); ratio = sum(t[2] for t in tot)
    atk = float(BL[b].split(",")[8]); curve = BL[b].split(",")[10]
    avg = s / max(nacts, 1)
    by[(nm, r[42])].append((b, atk, curve, len(progs), nacts, round(s, 2), round(avg, 2), round(ratio, 3), round(atk * avg, 1)))
rank = sorted(by.items(), key=lambda kv: -max(x[-1] for x in kv[1]))
for (nm, rt), v in rank:
    x = v[0]; print(f"{nm:10s} {rt:36s} keys={len(v):2d} atk={x[1]:5g} {x[2]:10s} actions={x[4]:2d} sumPow={x[5]:7g} avgPow={x[6]:6g} ratio={x[7]} score=atk*avg={x[8]}")
