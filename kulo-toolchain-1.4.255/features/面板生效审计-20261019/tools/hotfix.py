# -*- coding: utf-8 -*-
"""1.4.245 之上的数据热修：计数类门修正（只改 kind 列）。用法：python hotfix.py [--write VER]"""
import sys, os, json, hashlib, zipfile
sys.path.insert(0, '.')
import v245 as V, psim as P
_cwd = os.getcwd(); os.chdir(V.BUILD)
import wf_mod_tool as M
from stage_all import csv_text
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
os.chdir(_cwd)
NL = "\n"
def leaf(v, rs):
    s = csv_text(rs); return s if v.endswith(NL) else s.rstrip(NL)
def raw_replace(lp, edits):
    raw, _ = V.read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    for k, node in edits.items():
        assert V.q.build_node(V.load(lp)[k]) == rows0[keys0.index(k)], (lp, k)
        om.rows[om.keys.index(k)] = V.q.build_node(node)
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys == keys0
    assert [i for i in range(len(rows0)) if back.rows[i] != rows0[i]] == sorted(keys0.index(k) for k in edits)
    return out

T = {V.AB: V.load(V.AB), V.LE: V.load(V.LE)}
ROWS = {}
LOG = []
def rows_of(lp, key):
    if (lp, key) not in ROWS:
        ROWS[(lp, key)] = [r for r in V.rows(T[lp][key]) if r]
    return ROWS[(lp, key)]
def setcell(lp, key, i, col, old, new, why):
    r = rows_of(lp, key)[i]
    assert r[col] == old, (lp, key, i, col, r[col], old)
    r[col] = new
    LOG.append(f"{'leader' if lp == V.LE else 'ability'}[{key}]#{i} c{col}: {old} → {new}  {why}")

# 1) 斯拉姆冈 129951 能力2#2：前置2 144（按层，上限1恒0）→ 187（有无）
setcell(V.AB, "1299512", 2, 13, "144", "187", "斯拉姆冈 水势时追加大海啸：上限1固有按层数读恒0")
# 2) 前置 188（数实例，叠层固有恒1）阈值≥2 → 144（按层）
for cid, slot, key, i, tb, c, msg in json.load(open("count_sweep.json", encoding="utf8")):
    lp = V.LE if tb == "leader_ability" else V.AB
    if msg.startswith("前置188"):
        setcell(lp, key, i, c, "188", "144", f"{cid} {msg}")
    elif msg.startswith("持续194") and "无上限" not in msg:
        setcell(lp, key, i, c, "194", "134", f"{cid} {msg}（每层应按层数计）")

edits, probs = {}, []
for (lp, key), rs in ROWS.items():
    nv = leaf(T[lp][key], rs)
    assert nv != T[lp][key]
    tb = "leader_ability" if lp == V.LE else "ability"
    for r in rs:
        assert len(r) == (124 if lp == V.LE else 126)
        probs += [f"{key}: {p}" for p in L.client_legality_problems(tb, r)]
        _, iss, _ = P.simulate(tb, r)
        probs += [f"{key}: sim {x}" for x in iss if x[0] not in ("NAN_FLOAT", "EMPTY_INT", "EMPTY_INT_OPT")]
    edits.setdefault(lp, {})[key] = nv
print("\n".join(LOG)); print(len(LOG), "cells;", {lp.split('/')[-1]: len(e) for lp, e in edits.items()})
print("problems:", probs)
if "--write" in sys.argv:
    VER = sys.argv[sys.argv.index("--write") + 1]
    assert not probs
    files = {}
    for lp, ed in edits.items():
        b = raw_replace(lp, ed)
        back = V.q.parse_node(b)
        assert set(back) == set(T[lp]) and sorted(k for k in back if back[k] != T[lp][k]) == sorted(ed)
        files[V.member(lp)] = b
    BASE = os.environ.get("WF_BASE", "1.4.245"); name = f"pinball-{BASE}-{VER}-1-count-gate-fix-local.zip"
    os.makedirs("patch", exist_ok=True)
    with zipfile.ZipFile(f"patch/{name}", "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(files): zf.writestr(m, files[m])
    blob = open(f"patch/{name}", "rb").read()
    with zipfile.ZipFile(f"patch/{name}") as zf:
        assert zf.testzip() is None and all(zf.read(m) == files[m] for m in files)
    integ = {"name": name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(files),
             "files": sorted(files), "member_sha256": {m: hashlib.sha256(files[m]).hexdigest() for m in sorted(files)},
             "applies_on": BASE, "version": VER, "log": LOG}
    open(f"patch/{name[:-4]}.integrity.json", "w", encoding="utf8").write(json.dumps(integ, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}))
