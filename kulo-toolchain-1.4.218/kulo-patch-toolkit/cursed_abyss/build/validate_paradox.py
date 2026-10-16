"""复核 1.4.152 增量包：往返、无丢键、逐行合法性、文案上限、固有上限、触发来源。"""
import json, os, zipfile, csv, io
os.environ.setdefault("WF_TIP", "151")
from live149 import *
import wf_cursed_weapons as W
z = Path(__file__).resolve().parent.parent / "patch" / "pinball-1.4.151-1.4.152-1-paradox-r2-local.zip"
integ = json.loads(z.with_name(z.stem + ".integrity.json").read_text("utf-8"))
probs, T = [], {}
with zipfile.ZipFile(z) as zf:
    for n in zf.namelist():
        lp = integ["logical_paths"][n]
        node = q.parse_node(zf.read(n))
        if q.parse_node(q.build_node(node)) != node: probs.append(f"往返 {lp}")
        if set(load(lp)) - set(node): probs.append(f"丢键 {lp}")
        T[lp] = node
R = lambda v: [r for r in csv.reader(io.StringIO(v, newline="")) if r]
for key in ("5920001", "5921001", "5922001", "5923001"):
    for t, lp in ((W.SOUL_T, W.SOUL), (W.EA_T, W.EA)):
        for i, r in enumerate(R(T[lp][key])):
            probs += [f"{key} {t}#{i}: {p}" for p in W.L.client_legality_problems(t, r)]
            if r[W._col(t, "instant_trigger", "kind")] == "23" and r[2 if t == W.SOUL_T else 5] == "0":
                if r[W._col(t, "instant_trigger", "trigger_puller")] != "0": probs.append(f"{key}#{i} 施技触发 puller 非 0")
for k, v in T[W.CAS].items():
    if k.startswith("desc_override_equipment") and "5920001" in k:
        for line in R(v)[0][0].split("\n"):
            if len(line) > 57: probs.append(f"{k} 行超 57：{line}")
enh = R(T[W.ENH]["5920001"])[0]
if len(enh[6]) > 54: probs.append("强化说明超 54")
u = R(load(W.UNIQUE)["59200011"])[0]
if not (u[4].isdigit() and int(u[4]) > 1): probs.append("诅咒固有上限 ≤1")
print(json.dumps({"problems": probs, "members": len(T)}, ensure_ascii=False))
