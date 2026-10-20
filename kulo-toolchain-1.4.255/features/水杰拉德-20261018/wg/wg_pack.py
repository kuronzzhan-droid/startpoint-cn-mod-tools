# -*- coding: utf-8 -*-
"""水杰拉德角色包 → kulo 测试服补丁 zip（同一版本边，按 ≤5MiB 分包）+ integrity + manifest 条目。

用法：python wg_pack.py 1.4.238 1.4.239 [--out DIR]
- 表（*.orderedmap）：以 1.4.238 视图为底，逐包取「与底不同或新增」的外层行合并（raw 行级，未动行逐字节保留）；
  两包改同一行不同内容 = 冲突直接报错。
- 其它文件：与底逐字节相同的跳过；同一路径两包内容不同 = 冲突报错。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import zipfile
from pathlib import Path

import wg_env
import wf_mod_tool as core
import wf_assets

KEYS = ("aqua",)
ZROOT = {"common": "production/upload", "medium": "production/medium_upload", "android": "production/android_upload"}
CAP = 5 * 1024 * 1024 - 64 * 1024


def base_bytes(root: str, logical: str) -> bytes | None:
    d = core.sha1_path(logical)
    r = wf_assets.roots(wg_env.STORE)["upload" if root == "common" else root]
    p = r / d[:2] / d[2:]
    return p.read_bytes() if p.is_file() else None


def collect():
    tables: dict[str, dict[str, bytes]] = {}
    files: dict[tuple[str, str], tuple[bytes, str]] = {}
    report = {"tables": {}, "files": 0, "skipped_same": 0}
    for key in KEYS:
        roots = wg_env.ROOT / "work" / "character_packs" / f"wg-{key}" / "package" / "roots"
        for root in ZROOT:
            rd = roots / root
            if not rd.is_dir():
                continue
            for p in sorted(rd.rglob("*")):
                if not p.is_file():
                    continue
                lg = p.relative_to(rd).as_posix()
                data = p.read_bytes()
                base = base_bytes(root, lg)
                if base == data:
                    report["skipped_same"] += 1
                    continue
                if lg.endswith(".orderedmap") and root == "common" and base is not None:
                    bom = core.read_orderedmap_raw_rows_from_bytes(base, lg)
                    brows = dict(zip(bom.keys, bom.rows))
                    om = core.read_orderedmap_raw_rows_from_bytes(data, lg)
                    for k, r in zip(om.keys, om.rows):
                        if brows.get(k) == r:
                            continue
                        prev = tables.setdefault(lg, {}).get(k)
                        if prev is not None and prev != r:
                            raise SystemExit(f"table row conflict {lg} {k}")
                        tables[lg][k] = r
                        report["tables"].setdefault(lg, []).append(f"{key}:{k}")
                    missing = [k for k in bom.keys if k not in om.keys]
                    if missing:
                        raise SystemExit(f"{key} package drops base rows in {lg}: {missing[:5]}")
                    continue
                prev = files.get((root, lg))
                if prev is not None and prev[0] != data:
                    raise SystemExit(f"file conflict {root}:{lg} ({prev[1]} vs {key})")
                files[(root, lg)] = (data, key)
                report["files"] += 1
    return tables, files, report


def merged_tables(tables):
    out = {}
    for lg, rows in tables.items():
        base = base_bytes("common", lg)
        om = core.read_orderedmap_raw_rows_from_bytes(base, lg)
        keys, chunks = list(om.keys), list(om.rows)
        for k, r in rows.items():
            if k in keys:
                chunks[keys.index(k)] = r
            else:
                keys.append(k)
                chunks.append(r)
        raw = core.build_orderedmap_raw_rows(core.OrderedMap(lg, keys, chunks, Path(lg)))
        back = core.read_orderedmap_raw_rows_from_bytes(raw, lg)
        bb = dict(zip(om.keys, om.rows))
        after = dict(zip(back.keys, back.rows))
        assert all(after[k] == v for k, v in bb.items() if k not in rows), lg
        assert all(after[k] == v for k, v in rows.items()), lg
        out[lg] = raw
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frm")
    ap.add_argument("to")
    ap.add_argument("--out", default=str(wg_env.OUT / "patch"))
    ap.add_argument("--slug", default="water-gerald-local")
    a = ap.parse_args()
    outd = Path(a.out)
    outd.mkdir(parents=True, exist_ok=True)
    tables, files, report = collect()
    members = {}
    for lg, raw in merged_tables(tables).items():
        d = core.sha1_path(lg)
        members[f"{ZROOT['common']}/{d[:2]}/{d[2:]}"] = (raw, lg)
    for (root, lg), (data, _k) in files.items():
        d = core.sha1_path(lg)
        members[f"{ZROOT[root]}/{d[:2]}/{d[2:]}"] = (data, lg)
    # 分包：表优先放第 1 包
    order = sorted(members, key=lambda m: (not members[m][1].endswith(".orderedmap"), -len(members[m][0])))
    packs, cur, size = [], [], 0
    for m in order:
        n = len(members[m][0])
        if cur and size + n > CAP:
            packs.append(cur)
            cur, size = [], 0
        cur.append(m)
        size += n
    if cur:
        packs.append(cur)
    chain, integ = [], []
    for i, names in enumerate(packs, start=1):
        zname = f"pinball-{a.frm}-{a.to}-{i}-{a.slug}.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for m in sorted(names):
                z.writestr(m, members[m][0])
        raw = buf.getvalue()
        (outd / zname).write_bytes(raw)
        ent = {"name": zname, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
               "members": len(names), "files": sorted(names)}
        (outd / zname.replace(".zip", ".integrity.json")).write_text(json.dumps(
            ent | {"logical": {m: members[m][1] for m in sorted(names)},
                   "member_sha256": {m: hashlib.sha256(members[m][0]).hexdigest() for m in sorted(names)},
                   "applies_on": a.frm, "version": a.to}, ensure_ascii=False, indent=1), "utf-8")
        chain.append(zname)
        integ.append(ent)
    entry = {"id": f"water-gerald-{a.to}", "type": "patch",
             "name": "(测试服) 新角色 水杰拉德（雨后天台的白狼骑士）", "description": "",
             "version": a.to, "depends_on": a.frm, "enabled": True, "local_test_only": True,
             "archive": chain[0], "archive_size": integ[0]["size"], "chain": chain,
             "files": sorted(members), "archive_integrity": integ, "created_at": "2026-10-19"}
    (outd / f"manifest-entry-{a.to}.json").write_text(json.dumps(entry, ensure_ascii=False, indent=2), "utf-8")
    report["members"] = len(members)
    report["zips"] = [(e["name"], e["size"]) for e in integ]
    (outd / f"pack-report-{a.to}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps({"members": len(members), "zips": report["zips"],
                      "tables": {k: len(v) for k, v in report["tables"].items()}}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
