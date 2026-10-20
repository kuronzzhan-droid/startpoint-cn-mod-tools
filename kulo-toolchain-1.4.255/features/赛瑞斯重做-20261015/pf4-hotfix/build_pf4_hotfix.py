# -*- coding: utf-8 -*-
"""赛瑞斯 PF4 中途消失热修：unique_condition 22「龙王显现」时长 3600 → 72000(20 分钟,<99999 不出∞徽标;FeverEnd 漏发时也有上限)。
标记本应由 Fever 结束(能力3 第4行 184→528)删除；3600 帧=60 秒，Fever 被治疗加 Fever 拉长后标记先到期，
419 PF4 行与能力3 龙形加成(都用 194 数 22)随之失效。
用法：python build_pf4_hotfix.py <from> <to> <基底 zip...>（按版本序，后者覆盖前者；读不到的表退回 viewstore 1.4.238）"""
import glob, hashlib, io, json, sys, zipfile, zlib
from pathlib import Path
sys.path.insert(0, r"D:/WF/startpoint-cn-wiki/mod-tools")
import wf_mod_tool as core
FRM, TO, BASES = sys.argv[1], sys.argv[2], sys.argv[3:]
L = "master/character/unique_condition.orderedmap"
h = core.sha1_path(L); N = f"production/upload/{h[:2]}/{h[2:]}"
VIEW = Path(r"D:/WF/out/水杰拉德-20261018/viewstore/production/upload") / h[:2] / h[2:]
base = VIEW.read_bytes(); src = "viewstore-238"
for z in BASES:
    with zipfile.ZipFile(z) as f:
        if N in f.namelist(): base = f.read(N); src = z
om = core.read_orderedmap_raw_rows_from_bytes(base, L)
keys, rows = list(om.keys), list(om.rows)
i = keys.index("22")
old = zlib.decompress(rows[i]).decode("utf-8")
cols = old.split(",")
assert cols[0] == "unique_seris_dragon_king" and cols[3] == "3600", old
cols[3] = "72000"
rows[i] = zlib.compress(",".join(cols).encode("utf-8"))
raw = core.build_orderedmap_raw_rows(core.OrderedMap(L, keys, rows, Path(L)))
back = core.read_orderedmap_raw_rows_from_bytes(raw, L)
assert list(back.keys) == list(om.keys)
assert all(a == b for k, a, b in zip(keys, back.rows, om.rows) if k != "22")
assert core.read_orderedmap_file_from_bytes(raw)["22"].split(",")[3] == "72000"
name = f"pinball-{FRM}-{TO}-1-seris-pf4-fix-local.zip"
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr(N, raw)
data = buf.getvalue()
D = Path(__file__).resolve().parent / f"delivery-{TO}"; D.mkdir(exist_ok=True)
(D / name).write_bytes(data)
sha = hashlib.sha256(data).hexdigest()
ent = {"name": name, "size": len(data), "sha256": sha, "members": 1, "files": [N]}
(D / name.replace(".zip", ".integrity.json")).write_text(json.dumps(ent | {"logical": {N: L},
    "member_sha256": {N: hashlib.sha256(raw).hexdigest()}, "applies_on": FRM, "version": TO, "table_base": src},
    ensure_ascii=False, indent=1), "utf-8")
entry = {"id": f"seris-pf4-fix-{TO}", "type": "patch", "name": f"(测试服) 赛瑞斯 PF4 中途消失修正 {TO}",
         "description": "", "version": TO, "depends_on": FRM, "enabled": True, "local_test_only": True,
         "archive": name, "archive_size": len(data), "chain": [name], "files": [N],
         "archive_integrity": [ent], "created_at": "2026-10-19"}
(D / f"manifest-entry-{TO}.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2), "utf-8")
(D / "SHA256SUMS.txt").write_text(f"{sha} *{name}\n")
print(json.dumps({"zip": str(D / name), "sha256": sha, "size": len(data), "table_base": src, "old": old}, ensure_ascii=False, indent=1))
