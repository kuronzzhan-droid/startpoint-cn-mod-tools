# -*- coding: utf-8 -*-
"""把 1.4.220 视图物化成 store 目录(硬链接 store131 + zip 成员实体覆盖)。只读源;覆盖前先 unlink,不会写穿硬链接。"""
import os, sys, zipfile, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import view  # noqa  sets env + chdir
import base149
SRC = Path(r"D:/WF/out/kulo-patch-toolkit/store131/production")
DST = Path(r"D:/WF/out/万圣新角色-20261016/viewstore/production")
n_link = 0
for root in ("upload", "medium_upload", "android_upload"):
    for dp, dns, fns in os.walk(SRC / root):
        rel = Path(dp).relative_to(SRC)
        (DST / rel).mkdir(parents=True, exist_ok=True)
        for f in fns:
            t = DST / rel / f
            if not t.exists():
                os.link(Path(dp) / f, t); n_link += 1
over = {}
for z in base149._ZIPS:
    with zipfile.ZipFile(z) as zf:
        for n in zf.namelist():
            if n.endswith("/") or not n.startswith("production/"):
                continue
            over[n] = z
by_zip = {}
for n, z in over.items():
    by_zip.setdefault(z, []).append(n)
for z, names in by_zip.items():
    with zipfile.ZipFile(z) as zf:
        for n in names:
            t = DST / n.split("production/", 1)[1]
            t.parent.mkdir(parents=True, exist_ok=True)
            data = zf.read(n)
            if t.exists():
                t.unlink()
            t.write_bytes(data)
(DST.parent / "viewstore.json").write_text(json.dumps({"tip": "1.4.220", "zips": [z.name for z in base149._ZIPS], "linked": n_link, "overlaid": len(over)}, ensure_ascii=False, indent=1), "utf-8")
print("linked", n_link, "overlaid", len(over))
