import sys, json, importlib
sys.path.insert(0, "."); sys.path.insert(0, "chars")
from fw import *
F = Framework(); importlib.import_module("capply").apply(F)
out = F.touched()
CHT = F.table(CH); TXT = F.table(TX)
sid2cid = {}
for cid, v in CHT.items():
    r = row(v); lid = r[17] if r[17] not in ("", "(None)") else cid
    for lp, k in [(LE, lid)] + [(AB, a) for a in r[19:25] if a not in ("", "(None)")]:
        rs = [x for x in rows(F.table(lp).get(k, "")) if x]
        if rs: sid2cid.setdefault(rs[0][0], cid)
        for x in rs:
            for cell in x[1:]:
                if cell.startswith(("change_skill", "override_string", "ability_skill")) or "_" in cell and cell in F.table(CAS): sid2cid.setdefault("REF:" + cell, cid)
    sk = r[8] if r[8] not in ("", "(None)") else r[0]; sid2cid.setdefault("SKILL:" + sk, cid)
def name(cid): return rows(TXT[cid])[0][0] if cid in TXT else "?"
by = {}
for k, nv in out.get(CAS, {}).items():
    sid = k.replace("desc_override_", "")
    cid = sid2cid.get(sid) or sid2cid.get("REF:" + k) or "其他引用串"
    by.setdefault(cid, []).append(("面板 " + k, rows(F.table(CAS)[k])[0][0], rows(nv)[0][0]))
for code, g in out.get(AS, {}).items():
    cid = sid2cid.get("SKILL:" + code, "?"); o = F.table(AS)[code]
    for lv in g:
        if row(g[lv])[1] != row(o[lv])[1]:
            by.setdefault(cid, []).append((f"技能 {code} 档{lv}", row(o[lv])[1], row(g[lv])[1]))
L = []
for cid in sorted(by):
    L.append(f"\n## {name(cid)}（{cid}）")
    for lab, a, b in by[cid]:
        L.append(f"### {lab}\n- 前：\n" + "\n".join("  > " + x for x in a.split("\n")) + "\n- 后：\n" + "\n".join("  > " + x for x in b.split("\n")))
open("audit/diff_227.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
print(len(by), sum(len(v) for v in by.values()))
