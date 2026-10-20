import sys, json, re, importlib, collections
sys.path.insert(0, "."); sys.path.insert(0, "chars")
from fw import *
Z = json.load(open("audit/zones.json"))
F = Framework(); importlib.import_module("capply").apply(F)
out = F.touched()
cas = out.get(CAS, {}); ask = out.get(AS, {})
bad = collections.defaultdict(list)
terms = {"PF": r"(?<![A-Za-z])PF", "FEVER": r"FEVER", "直击": r"直击", "贯通": r"贯通", "全体队员": r"全体队员", "同时具备": r"同时具备", "同时生效": r"同时生效", "全角加号": r"＋\d", "倍(技能)": None}
def zones_for(sid):
    zs = set(); found = False
    for lp, tbl in ((LE, "leader_ability"), (AB, "ability")):
        lay = D.layout(tbl)["blocks"]
        for k, v in F.table(lp).items():
            rs = [r for r in rows(v) if r]
            if not rs or rs[0][0] != sid: continue
            found = True
            for r in rs:
                mode = r[5] if tbl == "ability" else r[3]
                if mode == "1":
                    c = int(lay["during_content"]); z = Z["during"].get(r[c]); val = r[c + 5] if len(r) > c + 5 else ""
                else:
                    c = int(lay["instant_content"]); z = Z["instant"].get(r[c]); val = r[c + 5]
                for x in (z or []):
                    if x == "6d":
                        if val not in ("", "0"): zs.add(6)
                    elif isinstance(x, int): zs.add(x)
                    else: zs.add(int(x[0]))
    return zs if found else None
for k, nv in cas.items():
    t = rows(nv)[0][0]
    for n, rx in terms.items():
        if rx and re.search(rx, t): bad[n].append(k)
    tags = {int(x.translate(str.maketrans("９", "9"))) for x in re.findall(r"独立伤害乘区([0-9９])", t)}
    if k.startswith("desc_override_"):
        zs = zones_for(k[len("desc_override_"):])
        if zs is not None:
            if tags - zs: bad["多标乘区"].append((k, sorted(tags - zs)))
            if zs - tags: bad["缺乘区标签"].append((k, sorted(zs - tags)))
for code, g in ask.items():
    for lv, v in g.items():
        t = row(v)[1]
        if re.search(r"\d+(\.\d+)?\s*倍", t): bad["技能写倍率"].append((code, lv))
        for n in ("FEVER", "直击", "贯通"):
            if re.search(terms[n], t): bad["技能术语" + n].append((code, lv))
for n, v in bad.items(): print(n, len(v), v[:12])
