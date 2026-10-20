# -*- coding: utf-8 -*-
"""1.4.240→1.4.241 增量：本线程包相对已上线 239 的改动，叠在 240（平衡）之上。
文件：与 240 状态（240 覆盖 239）不同的才收；表：取 240 状态的表，只换本线程相对 shipped-239 改过/新增的行。"""
import glob, hashlib, io, json, sys, zipfile
from pathlib import Path
sys.path.insert(0, r"D:/WF/startpoint-cn-wiki/mod-tools")
import wf_mod_tool as core
OUT = Path(r"D:/WF/out/水杰拉德-20261018")
FRM, TO, SLUG = sys.argv[1], sys.argv[2], "water-gerald-fix-local"
def members(pattern):
    m = {}
    for z in sorted(glob.glob(pattern)):
        with zipfile.ZipFile(z) as f:
            for n in f.namelist(): m[n] = f.read(n)
    return m
s239 = members(r"D:/WF/rel239/shipped/pinball-1.4.238-1.4.239-*.zip")
prev = dict(s239)
for d in sys.argv[3:]:                      # 之后各版 shipped 目录，按序覆盖
    prev.update(members(str(Path(d) / "pinball-*.zip")))
new = members(str(OUT / "patch/pinball-1.4.238-1.4.239-*.zip"))
lg = {}
for z in glob.glob(str(OUT / "patch/*.integrity.json")): lg.update(json.load(open(z, encoding="utf-8"))["logical"])
out, report = {}, {}
for n, data in new.items():
    if s239.get(n) == data:
        continue                            # 本线程没改
    L = lg[n]
    if L.endswith(".orderedmap") and n in prev:
        a = core.read_orderedmap_raw_rows_from_bytes(s239[n], L) if n in s239 else None
        b = core.read_orderedmap_raw_rows_from_bytes(data, L)
        p = core.read_orderedmap_raw_rows_from_bytes(prev[n], L)
        da = dict(zip(a.keys, a.rows)) if a else {}
        mine = {k: r for k, r in zip(b.keys, b.rows) if da.get(k) != r}
        keys, rows = list(p.keys), list(p.rows)
        for k, r in mine.items():
            if k in keys: rows[keys.index(k)] = r
            else: keys.append(k); rows.append(r)
        raw = core.build_orderedmap_raw_rows(core.OrderedMap(L, keys, rows, Path(L)))
        back = dict(zip(*[core.read_orderedmap_raw_rows_from_bytes(raw, L).keys, core.read_orderedmap_raw_rows_from_bytes(raw, L).rows]))
        assert all(back[k] == r for k, r in zip(p.keys, p.rows) if k not in mine) and all(back[k] == r for k, r in mine.items())
        if raw != prev[n]:
            out[n] = raw; report[L] = sorted(mine)
    elif prev.get(n) != data:
        out[n] = data; report[L] = "file"
name = f"pinball-{FRM}-{TO}-1-{SLUG}.zip"
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
    for n in sorted(out): z.writestr(n, out[n])
raw = buf.getvalue(); assert len(raw) < 5 * 1024 * 1024
D = OUT / f"delivery-{TO}"; D.mkdir(exist_ok=True)
(D / name).write_bytes(raw)
ent = {"name": name, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(), "members": len(out), "files": sorted(out)}
(D / name.replace(".zip", ".integrity.json")).write_text(json.dumps(ent | {"logical": {n: lg[n] for n in sorted(out)},
    "member_sha256": {n: hashlib.sha256(out[n]).hexdigest() for n in sorted(out)}, "applies_on": FRM, "version": TO}, ensure_ascii=False, indent=1), "utf-8")
entry = {"id": f"water-gerald-fix-{TO}", "type": "patch", "name": f"(测试服) 水杰拉德修正 {TO}",
         "description": "", "version": TO, "depends_on": FRM, "enabled": True, "local_test_only": True, "archive": name,
         "archive_size": len(raw), "chain": [name], "files": sorted(out), "archive_integrity": [ent], "created_at": "2026-10-19"}
(D / f"manifest-entry-{TO}.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2), "utf-8")
(D / "SHA256SUMS.txt").write_text(f"{ent['sha256']} *{name}\n")
print(json.dumps({"zip": name, "size": len(raw), "sha256": ent["sha256"], "changes": report}, ensure_ascii=False, indent=1))
