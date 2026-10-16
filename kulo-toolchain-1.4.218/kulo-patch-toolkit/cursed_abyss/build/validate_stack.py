import json, os, zipfile, csv, io
os.environ.setdefault("WF_TIP", "153")
from survey import *
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
OUT = Path(__file__).resolve().parent.parent
z = OUT / "patch" / "pinball-1.4.153-1.4.154-1-modchar-stack-cap-local.zip"
integ = json.loads(z.with_name(z.stem + ".integrity.json").read_text("utf-8"))
rep = json.loads((OUT / "stack_cap_report.json").read_text("utf-8"))
probs = []; N = {}
with zipfile.ZipFile(z) as zf:
    for n in zf.namelist():
        lp = integ["logical_paths"][n]; node = q.parse_node(zf.read(n)); base = load(lp)
        if q.parse_node(q.build_node(node)) != node: probs.append("往返 " + lp)
        if set(base) - set(node) or set(node) - set(base): probs.append("键集变化 " + lp)
        diff = [k for k in base if base[k] != node[k]]
        N[lp] = (node, diff)
for t, lp in TABLES.items():
    node, diff = N[lp]
    exp = {c["key"] for c in rep["changes"] if c["t"] == t}
    if set(diff) != exp: probs.append(f"{t} 变化键 {sorted(set(diff) ^ exp)}")
    for k in diff:
        old = [x for x in rows(load(lp)[k]) if x]; new = [x for x in rows(node[k]) if x]
        if len(old) != len(new): probs.append(f"{k} 行数变化")
        for i, (a, b) in enumerate(zip(old, new)):
            d = [j for j in range(len(a)) if a[j] != b[j]]
            if d and t == 'ability' and not set(d) <= {34, 51, 52, 102, 113, 114}: probs.append(f"{k}#{i} 改到非预期列 {d}")
            if d and t == 'leader_ability' and not set(d) <= {32, 49, 50, 100, 111, 112}: probs.append(f"{k}#{i} 改到非预期列 {d}")
            probs += [f"{k}#{i}: {p}" for p in L.client_legality_problems(t, b)]
for c in rep["changes"]:
    if c["new"][1] * 3 > 300000: probs.append(f"{c['key']}#{c['i']} 满层超 300%")
print(json.dumps({"problems": probs, "tables": {lp: len(v[1]) for lp, v in N.items()}}, ensure_ascii=False))
