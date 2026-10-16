# -*- coding: utf-8 -*-
"""碧 169978 的 layer0 占用,以及放进最重组队时会不会溢出(视图 = 测试服链 1.4.218)。只读。
沿用 bughunt-20261015/budget 的 budget210/budget3 口径(fb_layer0_gate)。"""
import json, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["WF_EXTRA_DIRS"] = r"D:/WF/out/凉月修复-20261016/handoff-213;D:/WF/out/角色超限-120/patch;D:/WF/out/平衡1016/patch;D:/WF/out/碧-1.4.216/patch"
import env; env.setup(218)
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
os.chdir(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
from fb_layer0_gate import *  # noqa

V = "169978"
v = View()
chars = char_table(v)
common = {s: d for s, (d, _) in sheets_from_anims(v, {a: "common" for a in COMMON_FX}).items()}
common.update({s: d for s, (d, _) in sheets_from_anims(v, {"battle/common/layer0": "c"}).items()})


def mp(sh): return sum(area(d) for d in sh.values()) / 1e6


def tot(cid):
    s = {}
    for p in ("main", "skill", "leader"): s.update(chars[cid][p])
    return s


rank = sorted(((mp(tot(c)), c, chars[c]["code"]) for c in chars), reverse=True)
pos = [i for i, r in enumerate(rank) if r[1] == V][0]
c = chars[V]
out = {"vyrn": {"main": mp(c["main"]), "skill": mp(c["skill"]), "leader": mp(c["leader"]), "total": mp(tot(V)),
                "rank": pos + 1, "of": len(rank),
                "big": sorted(((area(d) / 1e6, s, d) for s, d in tot(V).items()), reverse=True)[:5]},
       "top10": rank[:10]}
print(json.dumps(out["vyrn"], ensure_ascii=False, default=str))

# 最重可达关的敌方
qsh = {}
for q in R0 + R1:
    an, b = round_assets(v, q, None)
    qsh[q] = {s: d for s, (d, _) in sheets_from_anims(v, an).items()}
hq = max(qsh, key=lambda q: mp(qsh[q]))
out["heaviest_quest"] = (hq, mp(qsh[hq]))


def headroom(sh):
    lo, hi = 0, 4096
    while lo < hi:
        mid = (lo + hi + 1) // 2
        t = dict(sh); t["__probe__"] = (mid, mid)
        if run_pack(t)["ok"]: lo = mid
        else: hi = mid - 1
    return lo


def room(groups):
    sh = dict(common); sh.update(qsh[hq])
    for g in groups:
        for i, cid in enumerate(g):
            parts = ("main", "skill", "leader") if i == 0 else (("main", "skill") if i < 3 else ("skill",))
            for p in parts: sh.update(chars[cid][p])
    return sh


# A. 随机三人纯自制房 + 最重关,碧当某一位队长(最重情形),与不带碧对照
pool = [x for x in chars if x[2:4] in ("99", "98", "97") and x != V]
random.seed(1016)
A = []
for t in range(120):
    ids = random.sample(pool, 18)
    g = [ids[0:6], ids[6:12], ids[12:18]]
    base = room(g)
    g2 = [[V] + ids[1:6], ids[6:12], ids[12:18]]
    withv = room(g2)
    A.append(dict(base=mp(base), with_vyrn=mp(withv), ok=run_pack(withv)["ok"], sq=headroom(withv)))
A.sort(key=lambda x: -x["with_vyrn"])
out["random_trio_custom_heaviest_quest"] = dict(n=len(A), fails=sum(1 for a in A if not a["ok"]),
                                                max=A[0], median=A[len(A) // 2]["with_vyrn"])

# B. 最重刻意凑队(budget3 口径):最重 3 队长 + 主位 + 助战贪心,碧有没有被挑进来;以及把碧强塞进第 1 队长时第几个角色溢出
pick, _ = worst_party(v, chars)
out["worst_pick_has_vyrn"] = any(p[0] == V for p in pick)


def threshold(order):
    for n in range(1, len(order) + 1):
        sh = dict(common); sh.update(qsh[hq])
        for cid, code, role in order[:n]:
            parts = {"leader": ("main", "skill", "leader"), "main": ("main", "skill"), "unison": ("skill",)}[role]
            for p in parts: sh.update(chars[cid][p])
        if not run_pack(sh)["ok"]: return n
    return None


out["worst_threshold"] = threshold(pick)
forced = [(V, "cnmod_vyrn_dark", "leader")] + [p for p in pick if p[0] != V]
forced = forced[:3] + [p for p in forced[3:]]
out["worst_threshold_with_vyrn_leader"] = threshold(forced)
json.dump(out, open(r"D:/WF/out/碧-1.4.216/vyrn_budget.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({k: out[k] for k in out if k not in ("top10",)}, ensure_ascii=False, default=str)[:3000])
print("top10", [(round(a, 2), b, c) for a, b, c in rank[:10]])
