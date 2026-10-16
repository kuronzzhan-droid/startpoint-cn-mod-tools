import json, glob, os, sys
A = r"D:/WF/startpoint-cn-kulo/assets"
sr = {}
for f in ("score_reward.json", "score_reward_cnmod.json"):
    p = os.path.join(A, f)
    if os.path.exists(p): sr.update(json.load(open(p, encoding="utf-8")))
rr = {}
for f in ("rare_score_reward.json", "rare_score_reward_cnmod.json"):
    p = os.path.join(A, f)
    if os.path.exists(p): rr.update(json.load(open(p, encoding="utf-8")))
TARGET = set(range(10000400, 10000454))
out = {}
for f in sorted(glob.glob(A + "/*.json")):
    try: d = json.load(open(f, encoding="utf-8"))
    except Exception: continue
    if not isinstance(d, dict): continue
    for qid, v in d.items():
        if not isinstance(v, dict) or "scoreRewardGroupId" not in v: continue
        g = str(v["scoreRewardGroupId"])
        exp = {}
        for e in sr.get(g, []):
            if e.get("type") == 0 and e.get("reward_type") == 0 and e.get("id") in TARGET:
                exp[e["id"]] = exp.get(e["id"], 0) + e["count"]
            elif e.get("type") == 1:
                grp = rr.get(str(e["id"]), [])
                for x in grp:
                    if x.get("type") == 0 and x.get("id") in TARGET:
                        exp[x["id"]] = exp.get(x["id"], 0) + e["rarity"] * x["count"] / len(grp)
        for it, n in exp.items():
            out.setdefault(it, []).append((os.path.basename(f), qid, g, round(n, 6)))
json.dump({str(k): v for k, v in sorted(out.items())}, open(sys.argv[1], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(out), "items with sources")
for k in sorted(TARGET):
    print(k, out.get(k))
