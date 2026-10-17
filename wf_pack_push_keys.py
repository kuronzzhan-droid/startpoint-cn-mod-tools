# -*- coding: utf-8 -*-
"""把角色包 workspace 里**指定外层键**的内容按键级推到 live store。

## 为什么需要

角色已由 flow 管理时，改一条词条行的完整路径是「改 kit → 重建包 → 整包 flow publish」。
但 CLAUDE.md 的授权分级里「整包 `flow publish`」要作者在当次请求里明确说；
而「键级改 live store + `wf_publish` 裸表边」是改数据任务的常设授权。
所以作者只说「改 X」时，落地路径是：

    改 kit → `--step kit,manifest,status`（回写 workspace 候选，同一任务的一部分）
    → 本工具把这几个键推到 live store → `wf_publish` 裸表边 → 作者进游戏就能看到

包里那张表是**整表快照**，直接整文件覆盖 live 会把别家角色的行退回包的快照版本
（[[wf-package-shadow-table-refresh]]）。所以这里只搬点名的外层键，
其余键**保留 live 的原始压缩字节**，写前做逐字节往返自检、写后回读校验并逐键对账。

## 用法

    python mod-tools/wf_pack_push_keys.py --workspace work/character_packs/s7-yuki \\
        --key master/ability/ability.orderedmap:1299912,1299913 \\
        --key master/ability/leader_ability.orderedmap:129991
    # 加 --apply 才落盘；不加只预演并打印 describe 前后对照

之后按提示跑 `wf_publish.py --tables <逗号分隔的逻辑路径>` 铸边。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    pass  # Imports resolve from this checkout/package, not external source copies.

import wf_mod_tool as core  # noqa: E402

ROOT = TOOLS.parent
ROOT_DIRS = ("common", "medium", "android")
DESCRIBE_KINDS = {"master/ability/ability.orderedmap": "ability",
                  "master/ability/leader_ability.orderedmap": "leader_ability"}


class PushError(RuntimeError):
    pass


def parse_targets(specs: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for spec in specs:
        if ":" not in spec:
            raise PushError(f"--key 要写成 <逻辑路径>:<键>[,<键>…]，收到 {spec!r}")
        logical, keys = spec.rsplit(":", 1)
        names = [k.strip() for k in keys.split(",") if k.strip()]
        if not names:
            raise PushError(f"--key {spec!r} 没有列出任何键")
        out.setdefault(logical, [])
        for name in names:
            if name in out[logical]:
                raise PushError(f"键 {name} 在 {logical} 上重复")
            out[logical].append(name)
    return out


def package_table(workspace: Path, logical: str) -> bytes:
    for root in ROOT_DIRS:
        path = workspace / "package" / "roots" / root / Path(*logical.split("/"))
        if path.is_file():
            return path.read_bytes()
    raise PushError(f"包里没有 {logical}（先跑 --step kit,manifest）")


def _describe(logical: str, text: str) -> list[str]:
    kind = DESCRIBE_KINDS.get(logical)
    if kind is None:
        return []
    import wf_describe
    return [wf_describe.describe_line(row, kind) for row in core.read_csv_lines(text)]


def plan_one(store: Path, workspace: Path, logical: str, keys: list[str]) -> dict:
    path = core.table_path(store, logical)
    if not path.is_file():
        raise PushError(f"live store 里没有 {logical}")
    original = path.read_bytes()
    table = core.read_orderedmap_raw_rows_from_bytes(original, logical)
    names, chunks = list(table.keys), list(table.rows)
    if core.build_orderedmap_raw_rows(
            core.OrderedMap(logical, names, chunks, Path(logical))) != original:
        raise PushError(f"{logical}: live 表逐字节往返自检不通过，拒绝写入")
    pkg = core.read_orderedmap_file_from_bytes(package_table(workspace, logical))
    live_text = core.read_orderedmap_file_from_bytes(original)
    changes = []
    for key in keys:
        if key not in names:
            raise PushError(f"{logical}: live 表里没有键 {key}（新增键请走整包 flow publish）")
        if key not in pkg:
            raise PushError(f"{logical}: 包里没有键 {key}")
        before, after = live_text[key], pkg[key]
        chunks[names.index(key)] = zlib.compress(after.encode("utf-8"))
        changes.append({"key": key, "changed": before != after,
                        "describe_before": _describe(logical, before),
                        "describe_after": _describe(logical, after)})
    updated = core.build_orderedmap_raw_rows(core.OrderedMap(logical, names, chunks, Path(logical)))
    check = core.read_orderedmap_file_from_bytes(updated)
    for key in keys:
        if check[key] != pkg[key]:
            raise PushError(f"{logical}: 回读校验失败（{key}）")
    drift = [k for k in names if k not in keys and check[k] != live_text[k]]
    if drift:
        raise PushError(f"{logical}: 别家键被动了，拒绝写入：{drift[:10]}")
    return {"logical": logical, "path": path, "original": original, "updated": updated,
            "outer_keys": len(names), "bytes": [len(original), len(updated)], "keys": changes}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--key", action="append", required=True,
                        help="<逻辑路径>:<键>[,<键>…]，可多次")
    parser.add_argument("--profile", default="cn")
    parser.add_argument("--apply", action="store_true", help="不加则只预演")
    args = parser.parse_args(argv)

    workspace = args.workspace if args.workspace.is_absolute() else ROOT / args.workspace
    store = Path(core.resolve_profile(args.profile).store).resolve()
    targets = parse_targets(args.key)
    plans = [plan_one(store, workspace, logical, keys) for logical, keys in targets.items()]

    stamp = time.strftime("%Y%m%d-%H%M%S")
    report = {"applied": args.apply, "workspace": str(workspace), "tables": []}
    for plan in plans:
        entry = {k: plan[k] for k in ("logical", "outer_keys", "bytes", "keys")}
        if args.apply:
            backup = plan["path"].with_name(plan["path"].name + f".bak-pushkeys-{stamp}")
            backup.write_bytes(plan["original"])
            plan["path"].write_bytes(plan["updated"])
            reread = core.read_orderedmap_file(plan["path"], plan["logical"]).text_rows()
            pkg = core.read_orderedmap_file_from_bytes(package_table(workspace, plan["logical"]))
            entry["backup"] = backup.name
            entry["verified_from_disk"] = all(reread[c["key"]] == pkg[c["key"]] for c in plan["keys"])
        report["tables"].append(entry)
    report["next_command"] = ("python mod-tools/wf_publish.py --tables "
                              + ",".join(targets))
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
