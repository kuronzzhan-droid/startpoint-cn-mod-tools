# -*- coding: utf-8 -*-
"""把 live store 的共享表回灌进各角色 pack 的 workspace,并重算 manifest 哈希。

## 为什么需要
41 个角色 pack 的 `manifest.tables[]` 都 claim 了共享表(典型:
`master/ability/ability.orderedmap` 的 `<id>1..<id>6`)。pack 内
`package/roots/common/<logical>` 存的是**整张表的快照**。

只用 `wf_publish` 往 live 写新行、不同步 pack,下一次对该 pack 做
`flow rebase` / 重发时,`rebase` 按 `outer_keys` 认领、**pack 内容盖 live**
—— 新行会被**静默回滚**。这与 [[wf-flow-ledger-dual-tail]]、
[[wf-share-pack-variant-trap]] 是同一个洞:两份副本各自演进,晚发布的那份赢。

## 做法
逐 pack:把 live 的表字节整份写进 `package/roots/<root>/<logical>`,
然后把 `manifest.roots` 里对应 fileEntry 的 `sha256` / `size` 改成新值。
**只动 fileEntry 的这两个字段,不碰 tables[] 的 outer_keys / codec_id**
—— 认领面不变,变的只是内容快照。

## 不做的事
- 不重建包、不重算 seal:重建会让 ownership 哈希对不上(见
  [[wf-package-manifest-binding]])。这里只做原地内容同步。
- 不发布:本工具只改 workspace,发布仍走 wf_publish 裸表边。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[3]
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.
import wf_mod_tool as core  # noqa: E402

ROOT = TOOLS.parent
PACKS = ROOT / "work" / "character_packs"
ROOT_DIRS = {"common": "common", "medium": "medium", "android": "android", "server": "server"}


class BackfillError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _live_bytes(store: Path, logical: str, root: str) -> bytes | None:
    if root == "server":
        # server 根存的是仓内 assets/ 下的明文 json,不走 store 哈希寻址
        path = ROOT / "assets" / logical.split("assets/", 1)[-1] if "assets/" in logical else None
        if path is None:
            path = ROOT / logical
        return path.read_bytes() if path.is_file() else None
    base = {"common": store, "medium": store.parent / "medium_upload",
            "android": store.parent / "android_upload"}[root]
    path = core.table_path(base, logical)
    return path.read_bytes() if path.is_file() else None


def backfill(pack_dir: Path, store: Path, wanted: set[str], apply: bool) -> dict | None:
    manifest_path = pack_dir / "package" / "manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    claimed = {t.get("logical_path") for t in manifest.get("tables", [])}
    hits = claimed & wanted
    if not hits:
        return None

    changes = []
    roots = manifest.get("roots", {})
    for root_name, entries in roots.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            logical = entry.get("logical_path")
            if logical not in hits:
                continue
            data = _live_bytes(store, logical, root_name)
            if data is None:
                changes.append({"logical": logical, "root": root_name, "status": "live 缺文件"})
                continue
            digest, size = _sha256(data), len(data)
            if entry.get("sha256") == digest and entry.get("size") == size:
                changes.append({"logical": logical, "root": root_name, "status": "已一致"})
                continue
            target = pack_dir / "package" / "roots" / ROOT_DIRS.get(root_name, root_name) / logical
            changes.append({
                "logical": logical, "root": root_name, "status": "同步",
                "size": [entry.get("size"), size],
                "sha256": [str(entry.get("sha256"))[:12], digest[:12]],
                "file_exists": target.is_file(),
            })
            if apply:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                entry["sha256"] = digest
                entry["size"] = size
    if apply and any(c["status"] == "同步" for c in changes):
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True),
            encoding="utf-8")
    return {"pack": pack_dir.name, "claimed_hits": sorted(hits), "changes": changes}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--table", action="append", required=True,
                   help="要回灌的逻辑路径,可多次")
    p.add_argument("--apply", action="store_true")
    args = p.parse_args(argv)
    profile = core.resolve_profile("cn")
    store = Path(profile.store).resolve()
    wanted = set(args.table)
    reports = []
    for pack_dir in sorted(PACKS.iterdir()):
        if not pack_dir.is_dir() or pack_dir.name.startswith("_"):
            continue
        r = backfill(pack_dir, store, wanted, args.apply)
        if r:
            reports.append(r)
    synced = sum(1 for r in reports for c in r["changes"] if c["status"] == "同步")
    same = sum(1 for r in reports for c in r["changes"] if c["status"] == "已一致")
    missing = [(r["pack"], c) for r in reports for c in r["changes"] if c["status"] == "live 缺文件"]
    print(json.dumps({
        "packs_touched": len(reports),
        "entries_synced": synced,
        "entries_already_same": same,
        "live_missing": missing,
        "applied": args.apply,
        "detail": reports[:3],
    }, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
