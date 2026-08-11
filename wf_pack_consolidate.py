#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""增量包整合器:手选/上传多个已发布的历史增量 zip,按发布顺序合并去冗余。

与 wf_chain_squash(整链自动压缩:自动发现全链+全版本硬链桥+退役)的分工:
本工具只做"任选一段已发布增量包 → 后写覆盖先写 → 合并成单个整合包"这一件事。
产物写进 work 输出目录,**不碰 CDN、不建桥、不退役、不改 active.json**,
原有的增量发布功能(wf_publish 每次 +0.0.1)完全不受影响。

规则(与服务端 cn-asset-graph.ts / wf_chain_squash 同一套):
  1. 重放顺序 = 客户端应用顺序:边按版本递增;边内按 root 序
     (common<medium<android<patch)+ 数值 seq + relativePath + source 序;
     同路径文件后写覆盖先写,终态每个路径只保留最后一次出现的有效文件。
  2. 整合范围 [A,B] = 所选最早 from → 最新 to。选择来自 CDN 时,按客户端
     实际路径(findReleasePath)自动补齐未勾选但可见的归档(asset-patch/active
     平行边、active.json 锚定的 charpkg)——否则客户端走整合捷径会丢内容;
     不在客户端路径上的选择被排除并在报告中说明。纯上传模式没有 CDN 图,
     要求所选包自身能连成 A→B 的完整链。
  3. 产物命名 pinball-<A>-<B>-<seq>-<tag>.zip:**版本号取所选内容最早版本 A**;
     按最后写入者 root 分桶(patch 并入 common),超 --max-zip-mib 按 seq 拆分
     (CI 门禁单 zip ≤5MiB,先例 1.4.102 拆 7 包;0 = 不拆)。
  4. 落盘前逐 entry(CRC32+size)与重放终态做等价校验,写 report.json 回执。

安全红线(2026-07-18 链重锚事故教训):整合包部署进 CDN 后客户端会优先走
捷径边;范围内还有客户端停在中间版本时,**不要删除被整合的旧包**(删了
它们就永久搁浅)。整链瘦身请直接用 wf_chain_squash,它自带全版本硬链桥。
charpkg 原件承载 active.json 锚定簿记,永远原样保留。

用法:
  python mod-tools/wf_pack_consolidate.py list
  python mod-tools/wf_pack_consolidate.py plan  --from-ver 1.4.150 --to-ver 1.4.160
  python mod-tools/wf_pack_consolidate.py build --from-ver 1.4.150 --to-ver 1.4.160 --tag merge0725
  python mod-tools/wf_pack_consolidate.py build --inputs a.zip b.zip --inputs-root common --tag merge0725
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wf_chain_squash as squash  # noqa: E402
import wf_mod_tool as core  # noqa: E402
import wf_quest_lib as quest  # noqa: E402
import wf_release  # noqa: E402

DEFAULT_BASE = squash.DEFAULT_BASE
CI_ZIP_CAP = 5 << 20
MEMBER_REL_RE = re.compile(r"^[0-9a-f]{2}/[0-9a-f]{38}$")
WORK_DIR = Path(__file__).resolve().parent / "work" / "pack_consolidate"
ORIGIN_CN = {"legacy": "常规增量", "patch": "asset-patch", "anchored": "锚定角色包", "upload": "上传"}


def _resolve_dirs(cdn: str | None = None, repo_root: str | None = None) -> tuple[Path, Path]:
    root = Path(repo_root).resolve() if repo_root else Path(__file__).resolve().parent.parent
    if cdn:
        cdn_root = Path(cdn).resolve()
    else:
        cdn_root = core.resolve_cdn_root_lax(
            legacy_root=root / ".cdn" / "cn"
        )
    return cdn_root, root


def _origin_of(archive: squash.VisibleArchive) -> str:
    if archive.source == "asset-patch:active":
        return "patch"
    if archive.source.startswith("character:"):
        return "anchored"
    if archive.source == "upload":
        return "upload"
    return "legacy"


def _archive_meta(archive: squash.VisibleArchive, frm: str, to: str) -> dict:
    match = squash.ARCHIVE_RE.fullmatch(archive.path.name)
    if match is None:
        raise ValueError(f"可见归档文件名不规范: {archive.path.name}")
    origin = _origin_of(archive)
    try:
        stat = archive.path.stat()
        size, mtime = stat.st_size, int(stat.st_mtime)
    except OSError:
        size, mtime = 0, 0
    return {
        "id": f"{origin}:{archive.relative}",
        "origin": origin,
        "origin_cn": ORIGIN_CN.get(origin, origin),
        "root": archive.root,
        "from": frm,
        "to": to,
        "seq": archive.seq,
        "tag": match.group(4),
        "name": archive.path.name,
        "size": size,
        "mtime": mtime,
    }


def _graph_and_index(cdn_root: Path, repo_root: Path, base: str):
    """可见图 + {id: (archive, frm, to)} 索引(只含 from>=base 的 mod 段)。"""
    graph = squash.build_visible_graph(cdn_root, repo_root)
    index: dict[str, tuple[squash.VisibleArchive, str, str]] = {}
    for (frm, to), archives in graph.edges.items():
        if squash.vkey(frm) < squash.vkey(base):
            continue
        for archive in archives:
            index[f"{_origin_of(archive)}:{archive.relative}"] = (archive, frm, to)
    return graph, index


def scan_selectable(cdn_root: Path, repo_root: Path, base: str = DEFAULT_BASE) -> dict:
    """列出 base 起客户端可见的全部增量归档(可整合候选)+ 当前链况。"""
    graph, index = _graph_and_index(cdn_root, repo_root, base)
    tail, path_edges = squash.find_path(graph, base)
    on_path: set[tuple[str, str]] = set(path_edges)
    packs = [
        {**_archive_meta(archive, frm, to), "on_path": (frm, to) in on_path}
        for _pid, (archive, frm, to) in index.items()
    ]
    packs.sort(key=lambda p: (squash.vkey(p["from"]), squash.vkey(p["to"]),
                              squash.ROOT_ORDER[p["root"]], p["seq"], p["name"]))
    return {"base": base, "tail": tail, "path_edge_count": len(path_edges),
            "packs": packs, "issues": list(graph.issues)}


def _zip_stats(path: Path) -> tuple[int, int]:
    with zipfile.ZipFile(path) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
    return len(infos), sum(i.compress_size for i in infos)


def _parse_upload(path: Path, root: str) -> tuple[squash.VisibleArchive, str, str]:
    if root not in wf_release.CLIENT_ROOTS:
        raise ValueError(f"上传包 root 只能是 common/medium/android,收到 {root!r}")
    match = squash.ARCHIVE_RE.fullmatch(path.name)
    if match is None:
        raise ValueError(
            f"上传包文件名不符合发布命名 pinball-<from>-<to>-<seq>-<tag>.zip: {path.name}")
    seq = int(match.group(3))
    if seq > squash.MAX_ARCHIVE_SEQ:
        raise ValueError(
            f"上传包 sequence 超过 {squash.MAX_ARCHIVE_SEQ}: {seq} ({path.name})"
        )
    frm, to = match.group(1), match.group(2)
    if squash.vkey(to) <= squash.vkey(frm):
        raise ValueError(f"上传包版本边非递增: {path.name}")
    if not path.is_file():
        raise ValueError(f"上传包不存在: {path}")
    try:
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
        if bad is not None:
            raise ValueError(f"上传包损坏(首个坏 entry: {bad}): {path.name}")
    except zipfile.BadZipFile as exc:
        raise ValueError(f"上传包不是有效 zip: {path.name} ({exc})") from exc
    return squash.VisibleArchive(root, path, f"uploads/{path.name}", "upload"), frm, to


def _check_tag(tag: str) -> None:
    if not squash.TAG_RE.fullmatch(tag) or "charpkg" in tag or "charbridge" in tag:
        raise ValueError(f"tag 必须是纯 [a-z0-9] 且不含 charpkg/charbridge: {tag!r}")


def _drop_member_set(
    drop_logicals: list[str] | None, drop_entries: list[str] | None
) -> tuple[set[str], dict[str, str]]:
    """(逻辑路径 | store 相对路径 | 完整成员名) → 待丢弃的 rel 集合 + 溯源标签。

    sha1 不可逆,逻辑路径必须正向算成 rel;同一 rel 在 common/medium/android
    三层同名,所以按 rel 匹配即可覆盖三层。"""
    rels: set[str] = set()
    labels: dict[str, str] = {}
    for logical in drop_logicals or ():
        rel = quest.hashed_rel(logical)
        rels.add(rel)
        labels[rel] = logical
    for raw in drop_entries or ():
        rel = raw.replace("\\", "/").strip("/")
        rel = "/".join(rel.split("/")[-2:])
        if not MEMBER_REL_RE.fullmatch(rel):
            raise ValueError(f"--drop-entry 必须是 xx/38位hex 或完整成员名: {raw!r}")
        rels.add(rel)
        labels.setdefault(rel, rel)
    return rels, labels


def consolidate(
    cdn_root: Path,
    repo_root: Path,
    *,
    tag: str,
    ids: list[str] | None = None,
    files: list[tuple[Path, str]] | None = None,
    from_ver: str | None = None,
    to_ver: str | None = None,
    base: str = DEFAULT_BASE,
    max_zip_mib: int = 5,
    out_dir: Path | None = None,
    drop_logicals: list[str] | None = None,
    drop_entries: list[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    """整合入口。ids 来自 scan_selectable;files=[(zip路径, root)] 为上传/外部包;
    from_ver/to_ver 为区间快捷选择(自动圈入区间内全部可见归档)。返回报告 dict。

    drop_logicals/drop_entries = entry 级排除清单(对外分享时剔除个别文件)。
    **只能用于整文件即整内容的条目**(独立资产文件);orderedmap 表是整文件,
    丢一张表 = 客户端 C8601,表里既有官方行又有内容行时必须走
    wf_enhancement_policy 的按行重建(wf_share_variant.py),不要用这里的 drop。"""
    _check_tag(tag)
    ids = list(dict.fromkeys(ids or ()))
    files = list(files or ())
    if (from_ver is None) != (to_ver is None):
        raise ValueError("--from-ver/--to-ver 必须成对出现")

    graph = index = None
    if ids or from_ver is not None:
        graph, index = _graph_and_index(cdn_root, repo_root, base)
        if from_ver is not None:
            for version, label in ((from_ver, "from"), (to_ver, "to")):
                if not wf_release.VERSION_RE.fullmatch(version):
                    raise ValueError(f"--{label}-ver 版本号格式不对: {version!r}")
            if squash.vkey(to_ver) <= squash.vkey(from_ver):
                raise ValueError(f"--to-ver 必须大于 --from-ver: {from_ver} → {to_ver}")
            if squash.vkey(from_ver) < squash.vkey(base):
                raise ValueError(
                    f"--from-ver {from_ver} 低于 mod 链起点 {base}(官方段不整合;须要可用 --base 下调)")
            in_range = [pid for pid, (_a, frm, to) in index.items()
                        if squash.vkey(frm) >= squash.vkey(from_ver)
                        and squash.vkey(to) <= squash.vkey(to_ver)]
            if not in_range:
                raise ValueError(f"区间 {from_ver} → {to_ver} 内没有任何可见归档")
            ids = list(dict.fromkeys([*ids, *in_range]))

    selected: list[tuple[squash.VisibleArchive, str, str]] = []
    for pid in ids:
        if index is None or pid not in index:
            raise ValueError(f"未知的包 id: {pid}(先用 list/刷新获取当前列表)")
        selected.append(index[pid])

    seen_files: set[tuple[str, str]] = set()
    uploads: list[tuple[squash.VisibleArchive, str, str]] = []
    for path, root in files:
        archive, frm, to = _parse_upload(Path(path), root)
        key = (root, archive.path.name)
        if key in seen_files:
            raise ValueError(f"上传包重复: {root}/{archive.path.name}")
        seen_files.add(key)
        uploads.append((archive, frm, to))

    if not selected and not uploads:
        raise ValueError("没有选中任何增量包")

    all_inputs = [*selected, *uploads]
    start = min((frm for _a, frm, _t in all_inputs), key=squash.vkey)
    end = max((to for _a, _f, to in all_inputs), key=squash.vkey)

    # 工作图:CDN 模式圈入范围内全部可见归档(补齐依据);纯上传模式只有上传包
    work = squash.VisibleGraph()
    if graph is not None and selected:
        for (frm, to), archives in graph.edges.items():
            if squash.vkey(frm) >= squash.vkey(start) and squash.vkey(to) <= squash.vkey(end):
                work.edges[(frm, to)] = list(archives)
    for archive, frm, to in uploads:
        work.add(frm, to, archive)

    reached, path_edges = squash.find_path(work, start)
    if reached != end:
        raise ValueError(
            f"从 {start} 出发沿所选归档只能到 {reached},接不到 {end} —— "
            "版本链断裂:所选包必须能连成完整区间(缺哪段就把哪段一起选上/传上)")

    required: list[tuple[tuple[str, str], squash.VisibleArchive]] = [
        (edge, archive)
        for edge in path_edges
        for archive in sorted(work.edges[edge], key=squash.VisibleArchive.order_key)
    ]
    required_set = {archive for _e, archive in required}
    selected_set = {archive for archive, _f, _t in selected}

    off_path_uploads = [a.path.name for a, _f, _t in uploads if a not in required_set]
    if off_path_uploads:
        raise ValueError(
            f"上传包不在 {start} → {end} 的客户端链路上(平行/断头边): "
            + ", ".join(off_path_uploads))

    auto_included = [
        _archive_meta(archive, edge[0], edge[1]) for edge, archive in required
        if archive not in selected_set and _origin_of(archive) != "upload"
    ] if selected else []
    excluded = [
        {**_archive_meta(archive, frm, to),
         "reason": "不在客户端实际路径上(平行边或已被更短捷径取代),整合它会引入客户端拿不到/重复的内容"}
        for archive, frm, to in selected if archive not in required_set
    ]

    final, conflicts = squash.replay(work, path_edges)

    drop_rels, drop_labels = _drop_member_set(drop_logicals, drop_entries)
    dropped: list[str] = []
    hit_rels: set[str] = set()
    if drop_rels:
        for name in list(final):
            rel = "/".join(name.replace("\\", "/").split("/")[-2:])
            if rel in drop_rels:
                del final[name]
                hit_rels.add(rel)
                dropped.append(name)
        if not final:
            raise ValueError("drop 清单把终态清空了,整合包不能是空包")
    drop_missing = sorted(label for rel, label in drop_labels.items() if rel not in hit_rels)

    inputs_meta = []
    input_entries = input_zip_bytes = 0
    for edge, archive in required:
        meta = _archive_meta(archive, edge[0], edge[1])
        entries, _csize = _zip_stats(archive.path)
        meta["entries"] = entries
        inputs_meta.append(meta)
        input_entries += entries
        input_zip_bytes += meta["size"]

    split = max_zip_mib is not None and max_zip_mib > 0
    max_bytes = (max_zip_mib << 20) if split else (1 << 60)
    parts = squash.plan_parts(final, max_bytes)

    middle = sorted({v for edge in path_edges for v in edge} - {start, end}, key=squash.vkey)
    warnings: list[str] = []
    if middle:
        warnings.append(
            f"范围内有 {len(middle)} 个中间版本({middle[0]} … {middle[-1]}):部署整合包后,"
            "在确认没有客户端停留在这些版本之前不要删除被整合的旧包(删了它们就永久搁浅;"
            "整链瘦身请用 wf_chain_squash,自带全版本硬链桥)")
    if any(m["origin"] == "anchored" for m in inputs_meta):
        warnings.append("整合内容含 active.json 锚定的角色包归档:charpkg 原件与 active.json 必须原样保留(只并内容,不动簿记)")
    if dropped:
        warnings.append(
            f"已按 drop 清单剔除 {len(dropped)} 个条目:产物不再等于原链终态,"
            "只能对外分享,不要拿它当自服链的整合包")
    if drop_missing:
        warnings.append(f"drop 清单里有 {len(drop_missing)} 项在终态里不存在(拼写错?): {drop_missing[:5]}")
    for conflict in conflicts:
        warnings.append(f"边内冲突(按后写覆盖先写解决): {conflict}")

    out_dir = Path(out_dir) if out_dir else WORK_DIR / tag
    report = {
        "tag": tag, "from": start, "to": end, "dry_run": dry_run,
        "out_dir": str(out_dir),
        "inputs": inputs_meta,
        "auto_included": auto_included,
        "excluded": excluded,
        "middle_versions": middle,
        "dropped": sorted(dropped),
        "drop_not_found": drop_missing,
        "stats": {
            "input_zips": len(inputs_meta),
            "input_zip_bytes": input_zip_bytes,
            "input_entries": input_entries,
            "final_entries": len(final),
            "removed_entries": input_entries - len(final) - len(dropped),
            "dropped_entries": len(dropped),
        },
        "outputs": [],
        "warnings": warnings,
    }

    if dry_run:
        report["outputs"] = [
            {"root": part.root, "seq": part.seq,
             "name": squash.part_name(start, end, part.seq, tag),
             "dir": wf_release.ROOT_DIRS[part.root],
             "entries": len(part.entries), "est_size": part.est_bytes}
            for part in parts
        ]
        return report

    if out_dir.exists() and any(out_dir.iterdir()):
        if not force:
            raise ValueError(f"输出目录已存在且非空: {out_dir}(换 tag/--out,或 --force 覆盖)")
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    staging = out_dir / ".staging"
    try:
        written = squash.write_parts(parts, staging, start, end, tag, max_bytes)

        # 产物 vs 重放终态逐 entry 等价校验(CRC32+size),失败即整体回滚
        stage = squash.VisibleGraph()
        stage.edges[(start, end)] = [
            squash.VisibleArchive(part.root, path, f"staging/{part.root}/{path.name}", "staging")
            for part, path in written
        ]
        staged_final, _ = squash.replay(stage, [(start, end)])
        mismatch = [name for name, entry in final.items()
                    if (staged_final.get(name) is None
                        or (staged_final[name].crc, staged_final[name].size) != (entry.crc, entry.size))]
        mismatch += [name for name in staged_final if name not in final]
        if mismatch:
            raise RuntimeError(f"整合产物等价校验失败 {len(mismatch)} 项: {mismatch[:5]}")

        output_bytes = 0
        for part, staged_path in written:
            target = out_dir / wf_release.ROOT_DIRS[part.root] / staged_path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged_path, target)
            size = target.stat().st_size
            output_bytes += size
            if size > CI_ZIP_CAP:
                warnings.append(
                    f"{target.name} ({part.root}) {size} B 超过 CI 单包 5MiB 门禁,"
                    "入玩家仓前需按 seq 拆分(--max-zip-mib 5)")
            digest = hashlib.sha256()
            with target.open("rb") as stream:
                for block in iter(lambda: stream.read(1 << 20), b""):
                    digest.update(block)
            report["outputs"].append(
                {"root": part.root, "seq": part.seq, "name": target.name,
                 "dir": wf_release.ROOT_DIRS[part.root], "path": str(target),
                 "entries": len(part.entries), "size": size, "sha256": digest.hexdigest()})
    except BaseException:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise
    shutil.rmtree(staging, ignore_errors=True)
    report["stats"]["output_zips"] = len(report["outputs"])
    report["stats"]["output_zip_bytes"] = output_bytes
    (out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


# ------------------------------------------------------------------- CLI

def _mib(n: int) -> str:
    return f"{n / 2**20:.2f} MiB"


def _print_report(report: dict) -> None:
    stats = report["stats"]
    mode = "[预览] " if report["dry_run"] else ""
    print(f"{mode}整合范围: {report['from']} → {report['to']}"
          f"(中间版本 {len(report['middle_versions'])} 个), tag={report['tag']}")
    print(f"输入: {stats['input_zips']} 个 zip / {stats['input_entries']} entries"
          f" / {_mib(stats['input_zip_bytes'])}")
    for meta in report["auto_included"]:
        print(f"  [自动纳入] {meta['id']}({meta['origin_cn']},客户端可见,不并会丢内容)")
    for meta in report["excluded"]:
        print(f"  [排除] {meta['id']}: {meta['reason']}")
    print(f"终态: {stats['final_entries']} entries"
          f"(去除被后续版本覆盖的冗余 {stats['removed_entries']} 个"
          + (f",按 drop 清单剔除 {stats['dropped_entries']} 个" if stats.get("dropped_entries") else "")
          + ")")
    for out in report["outputs"]:
        size = out.get("size", out.get("est_size", 0))
        print(f"  {out['dir']}/{out['name']}  {_mib(size)} ({out['entries']} entries)")
    if not report["dry_run"]:
        print(f"产物目录: {report['out_dir']}(按 CDN 目录结构摆放,含 report.json 回执;原包未做任何改动)")
    for warning in report["warnings"]:
        print(f"[警告] {warning}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["list", "plan", "build"])
    parser.add_argument("--from-ver", dest="from_ver", help="区间起点(所选最早 from 版本)")
    parser.add_argument("--to-ver", dest="to_ver", help="区间终点(所选最新 to 版本)")
    parser.add_argument("--inputs", nargs="*", default=[], help="显式 zip 路径(上传/外部包)")
    parser.add_argument("--inputs-root", default="common",
                        choices=list(wf_release.CLIENT_ROOTS), help="--inputs 包的 root(默认 common)")
    parser.add_argument("--tag", default=time.strftime("merge%m%d"),
                        help="整合包 tag,纯 [a-z0-9](默认 mergeMMDD)")
    parser.add_argument("--max-zip-mib", type=int, default=5,
                        help="单 zip 上限 MiB(CI 门禁 5;0=不拆分成单包)")
    parser.add_argument("--out", help=f"输出目录(默认 {WORK_DIR}\\<tag>)")
    parser.add_argument("--drop-logical", action="append", default=[], metavar="逻辑路径",
                        help="entry 级排除:按逻辑路径(sha1 正向算)剔除,可重复。"
                             "只能排独立资产文件;表要去增强请用 wf_share_variant.py")
    parser.add_argument("--drop-entry", action="append", default=[], metavar="xx/38hex",
                        help="entry 级排除:直接给 store 相对路径或完整成员名,可重复")
    parser.add_argument("--base", default=DEFAULT_BASE, help="mod 链起点(默认 1.4.54)")
    parser.add_argument("--cdn", help="CDN 根(默认 WF_CDN_DIR 或 <repo>/.cdn/cn)")
    parser.add_argument("--repo-root", help="仓库根(默认按脚本位置)")
    parser.add_argument("--force", action="store_true", help="build:覆盖已存在的非空输出目录")
    parser.add_argument("--json", action="store_true", help="list:输出 JSON")
    args = parser.parse_args(argv)
    cdn_root, repo_root = _resolve_dirs(args.cdn, args.repo_root)

    if args.command == "list":
        listing = scan_selectable(cdn_root, repo_root, args.base)
        if args.json:
            print(json.dumps(listing, ensure_ascii=False, indent=2))
            return 0
        print(f"mod 链: {listing['base']} → {listing['tail']}"
              f"(客户端路径 {listing['path_edge_count']} 条边)")
        for issue in listing["issues"]:
            print(f"  [ISSUE] {issue}")
        for pack in listing["packs"]:
            flag = "" if pack["on_path"] else "  [不在客户端路径]"
            print(f"  {pack['from']} → {pack['to']}  {pack['root']:<7} "
                  f"{pack['name']}  {_mib(pack['size'])}  [{pack['origin_cn']}]{flag}")
        return 0

    try:
        report = consolidate(
            cdn_root, repo_root, tag=args.tag,
            files=[(Path(p), args.inputs_root) for p in args.inputs],
            from_ver=args.from_ver, to_ver=args.to_ver, base=args.base,
            max_zip_mib=args.max_zip_mib,
            out_dir=Path(args.out) if args.out else None,
            drop_logicals=args.drop_logical, drop_entries=args.drop_entry,
            dry_run=(args.command == "plan"), force=args.force)
    except (ValueError, RuntimeError) as exc:
        print(f"[ERR] {exc}", file=sys.stderr)
        return 2
    _print_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
