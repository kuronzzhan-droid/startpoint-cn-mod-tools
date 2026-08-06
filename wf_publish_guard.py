# -*- coding: utf-8 -*-
"""发布前的「键不许消失」硬闸门。

## 为什么需要它

CDN 的投递单位是**整个文件**:store 里的文件名 = 逻辑路径的 sha1(`2/38` 布局),
而一张 master 表就是一个 orderedmap 二进制块(`ability` 一块装 3020 个键)。
客户端没有「取某一行」的协议 ⇒ 改一行就要重发整块 ⇒ **发布 = 用本地这一份整体替换线上那一份**。

于是任何「本地这份比线上少了几个键」的情况,发布出去就是**删角色**。历史事故:

- 1.4.278 整表发布共享表,把只在设备上的基诺维 169999 顶掉 → 进主城 C8601;
- 杰拉德包里的 `power_flip_action.orderedmap` 只有 7 键而 live 有 10 键,
  发布即删掉赛瑞斯人形/龙形 PF + 风巨蜥 PF 三个键(见 `DO-NOT-PUBLISH-20260804.md`)。

两次的共同点:**没人在打包前比过键集合**。这个模块就干这一件事。

## 判据

对每个待发文件,取链上最新版本的同路径文件:
  链上有的键,新版必须一个不少。少一个 = 硬失败。
新增键、内容变化都放行(那才是发布的目的)。

键的读取走 `core.parse_index`,只解 orderedmap 的键索引,**与行编解码器无关**,
所以对 ability/character/action_skill/power_flip_action 这些不同 codec 的表一视同仁;
解不出来的(DSL、图片、mp3)自动跳过,只做存在性报告。

用法:
    python mod-tools/wf_publish_guard.py              # 检查当前 pending 列表
    python mod-tools/wf_publish_guard.py --tables ability,leader_ability
被 wf_publish 在打包前自动调用;要强行放行用 --allow-key-deletion(会在输出里大声说明)。
"""
from __future__ import annotations

import io
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mod-tools"))
import wf_mod_tool as core  # noqa: E402

CDN_COMMON_DIFF = ROOT / ".cdn" / "cn" / "archive-common-diff"
CDN_COMMON_FULL = ROOT / ".cdn" / "cn" / "archive-common-full"
PACKS = ROOT / "work" / "character_packs"

_EDGE = re.compile(r"^pinball-(\d+\.\d+\.\d+)-(\d+\.\d+\.\d+)-(\d+)-")


def _vkey(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def chain_latest_index() -> dict[str, tuple[str, Path, str]]:
    """store 相对路径 -> (落点版本, zip 路径, zip 内条目名);按版本序后来居上。"""
    index: dict[str, tuple[str, Path, str]] = {}
    edges = []
    for path in CDN_COMMON_DIFF.glob("*.zip"):
        matched = _EDGE.match(path.name)
        if matched:
            edges.append(((_vkey(matched.group(2)), int(matched.group(3))),
                          matched.group(2), path))
    for _, to_version, path in sorted(edges, key=lambda item: item[0]):
        try:
            names = zipfile.ZipFile(path).namelist()
        except Exception:
            continue
        for name in names:
            index[name.replace("production/upload/", "")] = (to_version, path, name)
    for path in sorted(CDN_COMMON_FULL.glob("*.zip")):
        try:
            names = zipfile.ZipFile(path).namelist()
        except Exception:
            continue
        for name in names:
            index.setdefault(name.replace("production/upload/", ""),
                             ("full基包", path, name))
    return index


def _keys_of(blob: bytes) -> list[str] | None:
    """orderedmap 的键索引;不是 orderedmap 就返回 None。"""
    try:
        return list(core.parse_index(blob)[0])
    except Exception:
        return None


def protected_keys() -> dict[str, set[str]]:
    """各角色包 claims 的 (逻辑路径 -> 键集合)。这是「谁的行不许丢」的权威清单。"""
    out: dict[str, set[str]] = {}
    for manifest in sorted(PACKS.glob("*/package/manifest.json")):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        for table in data.get("tables") or []:
            logical = table.get("logical_path")
            if not logical:
                continue
            out.setdefault(logical, set()).update(str(k) for k in table["outer_keys"])
    return out


def check(entries: list[tuple[str, bytes]], *, verbose: bool = True) -> list[str]:
    """entries: [(store 相对路径, 待发布字节)]。返回问题列表(空 = 通过)。"""
    index = chain_latest_index()
    guarded = protected_keys()
    # 逻辑路径 -> 相对路径,用来把 claims 清单对到具体文件
    logical_by_rel = {}
    for logical in guarded:
        digest = core.sha1_path(logical)
        logical_by_rel[f"{digest[:2]}/{digest[2:]}"] = logical

    problems: list[str] = []
    for relative, payload in entries:
        relative = relative.replace("production/upload/", "")
        logical = logical_by_rel.get(relative)
        label = logical or relative
        if relative not in index:
            if verbose:
                print(f"  [新增] {label} (链上没有,纯新增)")
            continue
        version, zip_path, name = index[relative]
        try:
            old = zipfile.ZipFile(zip_path).read(name)
        except Exception as exc:
            problems.append(f"{label}: 读不出链上版本 {version} ({exc})")
            continue
        if old == payload:
            if verbose:
                print(f"  [不变] {label} (与链上 {version} 逐字节相同)")
            continue

        old_keys, new_keys = _keys_of(old), _keys_of(payload)
        if old_keys is None or new_keys is None:
            if verbose:
                print(f"  [资产] {label} (非 orderedmap,整文件替换链上 {version})")
            continue

        lost = [k for k in old_keys if k not in set(new_keys)]
        added = [k for k in new_keys if k not in set(old_keys)]
        if lost:
            problems.append(
                f"{label}: 相对链上 {version} 丢了 {len(lost)} 个键 -> {lost[:12]}"
                + (" ..." if len(lost) > 12 else ""))
        elif verbose:
            print(f"  [表  ] {label} 链上{version} {len(old_keys)}键 -> {len(new_keys)}键"
                  f"{(',新增 ' + str(added[:6])) if added else ''}")

        # 角色包 claims 的行必须还在(链上已有的前提下)
        must = guarded.get(logical or "", set()) & set(old_keys)
        gone = sorted(must - set(new_keys))
        if gone:
            problems.append(f"{label}: **角色包 claims 的行不见了** -> {gone}")
    return problems


def _pending_relatives() -> list[str]:
    pending = ROOT / "mod-tools" / "work" / "sync_pending.json"
    if not pending.is_file():
        return []
    return [str(x) for x in json.loads(pending.read_text(encoding="utf-8"))
            if not str(x).startswith(("medium:", "android:"))]


def main(argv: list[str] | None = None) -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    import argparse
    import wf_gui

    parser = argparse.ArgumentParser(description="发布前的键不许消失闸门")
    parser.add_argument("--tables", help="逗号分隔的表别名/逻辑路径(默认用 pending 列表)")
    args = parser.parse_args(argv)

    store = wf_gui.TARGET_STORE
    if args.tables:
        import wf_publish
        relatives = [wf_publish._relative_for_logical(x)
                     for x in wf_publish._explicit_logicals(args.tables)]
    else:
        relatives = _pending_relatives()
    if not relatives:
        print("没有待检查的文件(pending 为空且未指定 --tables)")
        return 0

    entries = []
    for relative in relatives:
        path = store / relative
        if path.is_file():
            entries.append((relative, path.read_bytes()))
        else:
            print(f"  [跳过] {relative} (本地不存在)")
    print(f"检查 {len(entries)} 个文件:")
    problems = check(entries)
    if problems:
        print("\n[阻断] 发布会删掉线上已有的键:")
        for problem in problems:
            print("  !! " + problem)
        return 1
    print("\n[OK] 链上已有的键一个没少。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
