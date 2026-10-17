# -*- coding: utf-8 -*-
"""平衡表 1017 → 测试服下一版（底座=extra_zips.txt 的视图；WF_BASE/WF_VER 指定版本）。
用法：python build_215.py [--write]"""
import hashlib, importlib, json, sys, zipfile
from wf.view.safety import restrict_writes
restrict_writes()
from wf.view.balance import *
from wf.paths import path
from wf.view import base149
from wf.view.balance_inputs import verify_balance_view

HERE = Path(__file__).resolve().parent
# The source list later gained target 223 itself. Its frozen 222 prefix is
# recorded with hashes; expected delivery ZIPs are never fed back as inputs.
_view_inputs = json.loads((HERE / "input-zips.json").read_text("utf-8"))
_extra = [root_path(item["path"]) for item in _view_inputs["zips"]]
for item, archive in zip(_view_inputs["zips"], _extra):
    if hashlib.sha256(archive.read_bytes()).hexdigest() != item["sha256"]:
        raise ValueError(f"balance extra ZIP digest drift: {archive}")
_base_lock = json.loads((HERE / "base-lock.json").read_text("utf-8"))
_view = base149.configure(tip=_view_inputs["tip"], extra_zips=_extra,
                          store_member_sha256=_base_lock["store_members"])
verify_balance_view(_view, _base_lock)

MODS = os.environ["WF_MODS"].split(",") if os.environ.get("WF_MODS") else ["c129999", "c129992", "c139995", "c119992", "c169980", "c119991", "c139997", "c119990"]
BASE = "1.4.222"
VER = "1.4.223"
NAME = f"pinball-{BASE}-{VER}-1-" + os.environ.get("WF_TAG", "balance-1017") + "-local.zip"
OUT = path("output", "balance1017")

F = Framework()
for m in MODS:
    F.owner = m
    importlib.import_module("recipes.balance1017." + m).apply(F)
F.owner = None

files, lps, probs = {}, {}, []
out = F.touched()
for lp, ed in out.items():
    if lp == AS:
        enc_ed = ed
    else:
        enc_ed = ed
    for k, nv in ed.items():
        if lp in (AB, LE):
            t = "leader_ability" if lp == LE else "ability"
            for i, r in enumerate(x for x in rows(nv) if x):
                assert len(r) == (124 if lp == LE else 126), (lp, k, i, len(r))
                probs += [f"{lp} {k}#{i}: {p}" for p in L.client_legality_problems(t, r)]
    b = raw_replace(lp, enc_ed)
    back = q.parse_node(b)
    assert set(back) == set(F.table(lp)) and sorted(k for k in back if back[k] != F.table(lp)[k]) == sorted(ed), lp
    files[member(lp)] = b; lps[member(lp)] = lp
dsl_changed = []
for p, tree in F.DSL.items():
    if tree == dsl_tree(p):
        continue
    probs += [f"{p}: {x}" for x in dsl_signature_problems(tree)]
    enc = encode_tree(tree)
    assert wf_dsl.parse_dsl(zlib.decompress(enc, -15))["tree"] == tree, p
    lp = wf_dsl.dsl_logical(p)
    files[member(lp)] = enc; lps[member(lp)] = lp
    dsl_changed.append(p)
assert not probs, probs
srv_keys = sorted(k for k in F.SRV if F.SRV[k] != F.SRV0[k])


def main():
    print("\n".join(F.LOG))
    print("tables:", {lp.split('/')[-1]: sorted(ed) for lp, ed in out.items()})
    print("dsl:", dsl_changed)
    print("server character_text keys:", srv_keys)
    if "--write" not in sys.argv:
        print("DRY RUN", len(files), "members"); return 0
    verification = verify_balance_view(_view, _base_lock)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(files): zf.writestr(m, files[m])
    blob = path.read_bytes(); assert len(blob) <= 5 * 1024 * 1024
    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None and all(zf.read(m) == files[m] for m in files)
    srv = {}
    if srv_keys:
        sdir = OUT / "server"; sdir.mkdir(exist_ok=True)
        txt = SRV_SRC.read_text("utf-8")
        newtxt = txt
        for k in srv_keys:
            for c in (5, 7):
                o, n = F.SRV0[k][0][c], F.SRV[k][0][c]
                if o != n:
                    oj, nj = json.dumps(o, ensure_ascii=False), json.dumps(n, ensure_ascii=False)
                    if newtxt.count(oj) == 0 and newtxt.count(nj) >= 1:
                        continue  # 与另一列同串，已一并替换
                    assert newtxt.count(oj) >= 1, (k, c)
                    newtxt = newtxt.replace(oj, nj)
        assert json.loads(newtxt) == F.SRV
        (sdir / "character_text.json").write_text(newtxt, "utf-8")
        srv = {"assets/cdndata/character_text.json": {"copy": "server/character_text.json", "keys": srv_keys,
               "sha256": hashlib.sha256(newtxt.encode()).hexdigest(),
               "base_sha256": hashlib.sha256(txt.encode()).hexdigest()}}
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(files),
             "files": sorted(files), "member_sha256": {m: hashlib.sha256(files[m]).hexdigest() for m in sorted(files)},
             "logical_paths": {m: lps[m] for m in sorted(files)}, "applies_on": BASE, "version": VER,
             "server_files": srv, "log": F.LOG, "view_verification": verification}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
