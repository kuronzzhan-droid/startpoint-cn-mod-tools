# -*- coding: utf-8 -*-
"""平衡表 1017 → 测试服下一版（底座=extra_zips.txt 的视图；WF_BASE/WF_VER 指定版本）。
用法：python build_215.py [--write]"""
import hashlib, importlib, json, sys, zipfile
sys.path.insert(0, r"D:/WF/out/气绝设计-1.4.231")
sys.path.insert(0, r"D:/WF/out/气绝设计-1.4.231/chars")
from fw import *  # noqa

MODS = os.environ["WF_MODS"].split(",") if os.environ.get("WF_MODS") else ["c129999", "c129992", "c139995", "c119992", "c169980", "c119991", "c139997", "c119990"]
BASE = os.environ["WF_BASE"]
VER = os.environ["WF_VER"]
NAME = f"pinball-{BASE}-{VER}-1-" + os.environ.get("WF_TAG", "balance-1017") + "-local.zip"
OUT = HERE / os.environ.get("WF_OUT", "patch")

F = Framework()
for m in MODS:
    F.owner = m
    importlib.import_module(m).apply(F)
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
    probs += [f"{p}: {x}" for x in W.dsl_signature_problems(tree)]
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
    OUT.mkdir(exist_ok=True)
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
        import srvmerge
        patch = {k: {str(c): [F.SRV0[k][0][c], F.SRV[k][0][c]] for c in (5, 7, 9) if F.SRV0[k][0][c] != F.SRV[k][0][c]} for k in srv_keys}
        newtxt = srvmerge.merge(txt, patch)
        (sdir / "character_text.patch.json").write_text(json.dumps(patch, ensure_ascii=False, indent=1), "utf-8")
        import shutil; shutil.copyfile(HERE / "srvmerge.py", sdir / "srvmerge.py")
        assert json.loads(newtxt) == F.SRV
        (sdir / "character_text.json").write_text(newtxt, "utf-8")
        srv = {"assets/cdndata/character_text.json": {"copy": "server/character_text.json", "keys": srv_keys,
               "sha256": hashlib.sha256(newtxt.encode()).hexdigest(),
               "base_sha256": hashlib.sha256(txt.encode()).hexdigest()}}
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(files),
             "files": sorted(files), "member_sha256": {m: hashlib.sha256(files[m]).hexdigest() for m in sorted(files)},
             "logical_paths": {m: lps[m] for m in sorted(files)}, "applies_on": BASE, "version": VER,
             "server_files": srv, "log": F.LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
