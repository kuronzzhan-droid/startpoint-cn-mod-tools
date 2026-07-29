#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对外分享包变体构建器:同一批内容产出 full / content-only 两个变体。

- **full**:我们自服的完整终态(含平衡总包、白虎重做、敌人血量上调等个人增强)。
- **content-only**:同样的三自制角色 + 15 把深渊武器 + 700099 随机塔模式,
  但所有官方行回滚为官方原值,被改写的官方资产文件不下发。
  规则与实现见 wf_enhancement_policy.py。

两条硬约束(2026-07-18 链重锚事故 + 2026-07-29 隔离方案定案):

  1. **我方自己的链零改动**:本工具只读 CDN/asset-patch,产物一律写进
     work/share_variant/(或 --out 指定的仓外目录),拒绝写进 CDN 或
     assets/asset-patch。
  2. **已消费的 from-to 边严禁换内容重切**:变体按收方链尾重新锚定
     (--anchor <收方当前 tail>),产出一条属于收方血统的新边;若这条边
     在我方可见图里已经存在,直接拒绝构建。

用法:
  python mod-tools/wf_share_variant.py plan
  python mod-tools/wf_share_variant.py plan  --anchor 1.4.130
  python mod-tools/wf_share_variant.py build --anchor 1.4.130 --tag share0729 \
      --min-server modes-20260714 --server-feature rush-mode
  python mod-tools/wf_share_variant.py build --variant content-only --out D:/tmp/share
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

MOD_DIR = Path(__file__).resolve().parent
ROOT = MOD_DIR.parent
sys.path.insert(0, str(MOD_DIR))

import wf_enhancement_policy as policy_mod  # noqa: E402
import wf_mod_tool as core  # noqa: E402
from wf_enhancement_policy import (  # noqa: E402
    CLIENT_ROOTS, EXPECTED_CONTENT_ROWS, BaselineUnavailable, EntrySource,
    OfficialBaseline, Policy, bump_version, chain_sources, member_name,
    plan_content_only, sha256, verify_content_only, vkey,
)

VARIANTS = ("full", "content-only")
VARIANT_TAG_SUFFIX = {"full": "", "content-only": "co"}
WORK_DIR = MOD_DIR / "work" / "share_variant"
CI_ZIP_CAP = 5 << 20
ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
ROOT_DIRS = {
    "common": "archive-common-diff",
    "medium": "archive-medium-diff",
    "android": "archive-android-diff",
}
# 与 wf_dev_catalog 同源:带这些表 = 收方服务端的派生表需同步(重启或热载)
try:  # pragma: no cover - 只在 wf_dev_catalog 缺失时走 fallback
    from wf_dev_catalog import RESTART_SENSITIVE_LOGICALS
except Exception:  # pragma: no cover
    RESTART_SENSITIVE_LOGICALS = {
        "master/character/character.orderedmap": "角色表有变更",
        "master/character/character_text.orderedmap": "角色文案表有变更",
    }

README_TEMPLATE = """WF mod 分享包({variant_cn})
生成时间: {stamp}
内容来源: {since} → {tail}({edges} 条边,重放终态 {entries} 条目)
落到你的链上: {anchor_from} → {anchor_to}

【这个包是什么】
{variant_desc}

【怎么用】
1. 先确认你的 CDN 链尾正好是 {anchor_from}(不是就别用这个包,找发包人按你的
   实际链尾重新锚定: wf_share_variant.py build --anchor <你的链尾>)。
2. 把 archive-*-diff/ 下的 zip 原样拷进你 CDN 对应目录(同名目录合并即可)。
3. 服务端按 requires.json 的声明处理(见下)。
4. 客户端更新到 {anchor_to} 后自查: 700099 模式入口出现、兑换商店不报「数据不足」。

【依赖】
{requires_lines}

【变体互斥】
full 与 content-only 是同一批内容的两个版本,**二选一**。两者 zip 文件名不同
(tag 分别是 {tag_full} / {tag_content}),同时放进 CDN 会让客户端把两份都应用,
终态取决于文件名序——务必只放一个变体。

【本包里的官方数据】
{official_note}
"""

VARIANT_DESC = {
    "full": (
        "我们自服的完整终态: 三自制角色(129999/139999/149999)、15 把深渊武器\n"
        "(8000101-8000115)、700099 随机塔模式,**外加**我们自服的个人增强——\n"
        "全角色平衡总包(ability/leader_ability/character_status/ability_soul)、\n"
        "白虎(角色 10)专项重做、官方 boss 血量上调等。想要原汁原味官方数值的,\n"
        "请改用 content-only 变体。"),
    "content-only": (
        "纯内容变体: 三自制角色(129999/139999/149999)、15 把深渊武器\n"
        "(8000101-8000115)、700099 随机塔模式。**不含任何个人增强**——所有官方\n"
        "行都已按官方 CDN 原值重建(含白虎/平衡总包/敌人血量),被我们改过的官方\n"
        "资产文件不下发,你的官方数值不会被动。"),
}


# ------------------------------------------------------------------ 数据结构

@dataclass
class VariantEntry:
    root: str
    rel: str
    est_bytes: int
    payload: Callable[[], bytes]

    @property
    def member(self) -> str:
        return member_name(self.root, self.rel)


@dataclass
class PlannedPart:
    root: str
    seq: int
    entries: list[VariantEntry]
    est_bytes: int


class VariantError(RuntimeError):
    """构建前置条件不满足(锚定冲突/输出目录违规等)。"""


# ------------------------------------------------------------------ 计划

def plan_parts(entries: Iterable[VariantEntry], max_zip_bytes: int) -> list[PlannedPart]:
    """按 root 分桶、名字序稳定切分,预留余量保证实际产物不破 CI 5MiB 门禁。"""
    buckets: dict[str, list[VariantEntry]] = {}
    for entry in entries:
        buckets.setdefault(entry.root, []).append(entry)
    overhead = 128
    budget = max_zip_bytes - max(64 << 10, max_zip_bytes // 64)
    parts: list[PlannedPart] = []
    for root in CLIENT_ROOTS:
        items = sorted(buckets.get(root, ()), key=lambda item: item.member)
        if not items:
            continue
        current: list[VariantEntry] = []
        size = 0
        seq = 1
        for entry in items:
            cost = entry.est_bytes + overhead
            if current and size + cost > budget:
                parts.append(PlannedPart(root, seq, current, size))
                current, size, seq = [], 0, seq + 1
            current.append(entry)
            size += cost
        parts.append(PlannedPart(root, seq, current, size))
    return parts


def variant_entries(
    sources: Sequence[EntrySource],
    variant: str,
    baseline: OfficialBaseline | None,
    policy: Policy,
    *,
    official_file_action: str = "drop",
) -> tuple[list[VariantEntry], dict]:
    """按变体裁剪终态条目集。full 原样透传;content-only 走去增强策略。"""
    if variant == "full":
        entries = [
            VariantEntry(source.root, source.rel,
                         source.compress_size or source.size, source.read)
            for source in sources
        ]
        return entries, {"entries": len(entries), "kept": len(entries),
                         "dropped": 0, "rebuilt": 0}
    if baseline is None:
        raise VariantError("content-only 变体需要官方基准(OfficialBaseline)")
    verdicts, summary = plan_content_only(
        sources, baseline, policy, official_file_action=official_file_action)
    entries: list[VariantEntry] = []
    for source in sources:
        verdict = verdicts[(source.root, source.rel)]
        if verdict.action == "drop":
            continue
        if verdict.action == "rebuild" and verdict.data is not None:
            data = verdict.data
            entries.append(VariantEntry(
                source.root, source.rel, len(zlib.compress(data, 9)),
                lambda payload=data: payload))
        else:
            entries.append(VariantEntry(
                source.root, source.rel,
                source.compress_size or source.size, source.read))
    return entries, summary


# ------------------------------------------------------------------ 落盘

def write_parts(parts: Sequence[PlannedPart], staging: Path, from_ver: str,
                to_ver: str, tag: str) -> list[tuple[PlannedPart, Path]]:
    written: list[tuple[PlannedPart, Path]] = []
    for part in parts:
        out_path = staging / ROOT_DIRS[part.root] / \
            f"pinball-{from_ver}-{to_ver}-{part.seq}-{tag}.zip"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for entry in sorted(part.entries, key=lambda item: item.member):
                info = zipfile.ZipInfo(entry.member, ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, entry.payload(), compresslevel=9)
        written.append((part, out_path))
    return written


def written_sources(pack_dir: Path) -> list[EntrySource]:
    """从已落盘的变体包重新读出条目集(自检/金样校验用)。"""
    sources: list[EntrySource] = []
    for zip_path in sorted(pack_dir.rglob("pinball-*.zip")):
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
        for info in infos:
            if info.is_dir():
                continue
            parsed = policy_mod.split_member(info.filename)
            if parsed is None:
                continue
            root, rel = parsed

            def _read(path: Path = zip_path, member: str = info.filename) -> bytes:
                with zipfile.ZipFile(path) as handle:
                    return handle.read(member)

            sources.append(EntrySource(root, rel, info.CRC, info.file_size,
                                       _read, info.compress_size))
    return sources


# ------------------------------------------------------------------ 声明文件

def detect_restart(entries: Iterable[VariantEntry]) -> tuple[bool, list[str]]:
    sensitive = {policy_mod.quest.hashed_rel(logical): reason
                 for logical, reason in RESTART_SENSITIVE_LOGICALS.items()}
    reasons: list[str] = []
    for entry in entries:
        reason = sensitive.get(entry.rel)
        if reason and reason not in reasons:
            reasons.append(reason)
    return bool(reasons), reasons


def build_requires(
    variant: str, chain_meta: dict, anchor: tuple[str, str], summary: dict,
    outputs: list[dict], restart: tuple[bool, list[str]], *,
    min_server: str | None, server_features: Sequence[str],
    client_patches: Sequence[str], official_tail: str,
) -> dict:
    content_only = variant == "content-only"
    requires = {
        "schemaVersion": 2,
        "pack": {
            "variant": variant,
            "since": chain_meta["since"],
            "tail": chain_meta["tail"],
            "sourceEdges": chain_meta["edges"],
            "anchor": {"from": anchor[0], "to": anchor[1]},
            "archives": [output["path"] for output in outputs],
        },
        "enhancement": not content_only,
        "enhancementDetail": {
            "officialBaseline": official_tail if content_only else None,
            "revertedRows": summary.get("revertedRows", 0),
            "restoredRows": summary.get("restoredRows", 0),
            "revertedTables": [table["logical"] for table in summary.get("rebuiltTables", ())],
            "droppedEntries": summary.get("droppedLogicals", []),
            "note": (
                "官方行已全部回滚为官方 CDN 原值(基准=官方链尾 "
                f"{official_tail}),不含平衡总包/白虎重做/敌人数值上调"
                if content_only else
                "含发包方自服的个人增强(平衡总包/白虎重做/敌人数值上调等),"
                "会覆盖你的官方数值;只想要内容请用 content-only 变体"),
            # 服务端 JSON 不在客户端包里,只能声明:收方若直接用了发包方的服务端分支,
            # 这些行仍是增强态,要自己改回官方值。
            "serverSideEnhancements": (
                list(policy_mod.SERVER_SIDE_ENHANCEMENTS) if content_only else []),
        },
        "requires": {
            "serverRestart": restart[0],
            "restartReasons": restart[1],
            "minServerVersion": min_server,
            "serverFeatures": list(server_features),
            "clientPatches": list(client_patches),
        },
    }
    if restart[0]:
        requires["requires"]["serverDataNote"] = (
            "角色类内容的服务端派生表(assets/character.json 等)不在本包内;"
            "收方服务端需同步拉新(重启)或用 mod-admin 热载")
    return requires


def render_readme(variant: str, chain_meta: dict, anchor: tuple[str, str],
                  requires: dict, tags: dict[str, str]) -> str:
    lines: list[str] = []
    block = requires["requires"]
    lines.append(f"- 需重启服务端: {'是' if block['serverRestart'] else '否'}")
    for reason in block["restartReasons"]:
        lines.append(f"  - {reason}")
    if block["minServerVersion"]:
        lines.append(f"- 最低服务端版本/分支: {block['minServerVersion']}")
    if block["serverFeatures"]:
        lines.append(f"- 需要的服务端功能: {', '.join(block['serverFeatures'])}")
    if block["clientPatches"]:
        lines.append(f"- 需要的客户端补丁: {', '.join(block['clientPatches'])}")
    if len(lines) == 1 and not block["serverRestart"]:
        lines.append("- 纯 CDN 内容包,无额外依赖")
    detail = requires["enhancementDetail"]
    if requires["enhancement"]:
        official_note = (
            "本包按我方自服终态整包下发,官方表行带我方个人增强改动。若你在意\n"
            "官方数值/活动数据,请改用 content-only 变体。")
    else:
        official_note = (
            f"官方行已按官方 CDN 原值重建:回滚 {detail['revertedRows']} 行、"
            f"补回 {detail['restoredRows']} 行,\n涉及 {len(detail['revertedTables'])} 张表;"
            f"另有 {len(detail['droppedEntries'])} 个被我方改写过的官方资产文件不下发。\n"
            "注意:表是整文件替换,你自己在这些表里加过的行仍会被覆盖——"
            "有自家活动数据的\n服主请走行级合并(见 docs/self-host-modes.md 路线 B)。\n"
            + ("\n服务端侧还有几行增强不在本包里(客户端包管不到),"
               "你若直接用了发包方的服务端分支,\n请自行改回官方值:\n"
               + "\n".join(
                   f"  - {item['file']} 行 {item['row']} 的 {item['field']}:"
                   f"{item['ours']} → {item['official']}({item['note']})"
                   for item in requires["enhancementDetail"]["serverSideEnhancements"])
               if requires["enhancementDetail"].get("serverSideEnhancements") else ""))
    return README_TEMPLATE.format(
        variant_cn="完整变体 full" if requires["enhancement"] else "纯内容变体 content-only",
        stamp=time.strftime("%Y-%m-%d %H:%M"),
        since=chain_meta["since"], tail=chain_meta["tail"],
        edges=chain_meta["edges"], entries=chain_meta["entries"],
        anchor_from=anchor[0], anchor_to=anchor[1],
        variant_desc=VARIANT_DESC[variant],
        requires_lines="\n".join(lines),
        tag_full=tags["full"], tag_content=tags["content-only"],
        official_note=official_note,
    )


# ------------------------------------------------------------------ 主流程

def _check_out_dir(out_dir: Path, cdn_root: Path, repo_root: Path) -> None:
    resolved = out_dir.resolve()
    for forbidden, label in ((cdn_root.resolve(), "CDN 根"),
                             ((repo_root / "assets" / "asset-patch").resolve(),
                              "assets/asset-patch")):
        if resolved == forbidden or forbidden in resolved.parents:
            raise VariantError(
                f"拒绝把变体产物写进{label}({resolved});变体只给收方,"
                "我方自己的链必须零改动")


def _check_anchor(cdn_root: Path, repo_root: Path, anchor: tuple[str, str],
                  *, foreign_lineage: bool = False) -> list[str]:
    """锚定边合法性。返回需要写进报告的警告。"""
    import wf_chain_squash as squash

    from_ver, to_ver = anchor
    if vkey(to_ver) <= vkey(from_ver):
        raise VariantError(f"锚定目标版本必须大于起点: {from_ver} → {to_ver}")
    graph = squash.build_visible_graph(cdn_root, repo_root)
    if (from_ver, to_ver) not in graph.edges:
        return []
    if not foreign_lineage:
        raise VariantError(
            f"锚定边 {from_ver} → {to_ver} 在我方链里已经存在:同一条 from-to 换内容"
            "重切会让已升级的客户端永远拿不到新内容(2026-07-18 链重锚事故)。"
            f"收方在我方血统上 → 换个未被占用的 --anchor-to(如 {bump_version(graph_tail(graph))});"
            "收方是外血统(自己的版本号空间)→ 加 --foreign-lineage 显式声明")
    return [f"锚定边 {from_ver} → {to_ver} 与我方同名边重名,已按外血统放行:"
            "发包前请确认收方 CDN 里这条边不存在(否则收方客户端会拿到两份内容)"]


def graph_tail(graph) -> str:
    versions = {version for edge in graph.edges for version in edge}
    return max(versions, key=vkey) if versions else policy_mod.OFFICIAL_TAIL


def build(
    cdn_root: Path,
    repo_root: Path,
    *,
    tag: str,
    variants: Sequence[str] = VARIANTS,
    since: str = policy_mod.OFFICIAL_TAIL,
    anchor_from: str | None = None,
    anchor_to: str | None = None,
    out_dir: Path | None = None,
    max_zip_mib: int = 5,
    official_file_action: str = "drop",
    min_server: str | None = None,
    server_features: Sequence[str] = (),
    client_patches: Sequence[str] = (),
    official_tail: str = policy_mod.OFFICIAL_TAIL,
    foreign_lineage: bool = False,
    expect_content_rows: dict[str, Sequence[str]] | None = EXPECTED_CONTENT_ROWS,
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    if not tag.isalnum() or not tag.islower():
        raise VariantError(f"tag 必须是纯小写字母数字: {tag!r}")
    unknown = [name for name in variants if name not in VARIANTS]
    if unknown:
        raise VariantError(f"未知变体: {unknown}")

    sources, chain_meta = chain_sources(cdn_root, repo_root, since=since)
    anchor = (anchor_from or chain_meta["since"],
              anchor_to or bump_version(anchor_from or chain_meta["since"]))
    if anchor_from is None and anchor_to is None:
        anchor = (chain_meta["since"], chain_meta["tail"])  # 同血统:原样跨整段
    anchor_warnings = _check_anchor(cdn_root, repo_root, anchor,
                                    foreign_lineage=foreign_lineage)

    out_dir = Path(out_dir) if out_dir else WORK_DIR / tag
    _check_out_dir(out_dir, cdn_root, repo_root)

    tags = {name: tag + VARIANT_TAG_SUFFIX[name] for name in VARIANTS}
    baseline = None
    if "content-only" in variants:
        baseline = OfficialBaseline(cdn_root, official_tail=official_tail)
    policy = Policy()
    max_bytes = (max_zip_mib << 20) if max_zip_mib and max_zip_mib > 0 else (1 << 60)

    report = {"tag": tag, "chain": chain_meta, "anchor": {"from": anchor[0], "to": anchor[1]},
              "out_dir": str(out_dir), "dry_run": dry_run, "variants": {},
              "warnings": list(anchor_warnings)}
    for conflict in chain_meta.get("conflicts", ())[:5]:
        report["warnings"].append(f"边内冲突(按后写覆盖先写解决): {conflict}")

    for variant in variants:
        entries, summary = variant_entries(
            sources, variant, baseline, policy,
            official_file_action=official_file_action)
        parts = plan_parts(entries, max_bytes)
        pack_name = f"wfshare-{anchor[0]}-to-{anchor[1]}-{variant}"
        pack_dir = out_dir / pack_name
        variant_report = {
            "variant": variant, "tag": tags[variant], "pack": pack_name,
            "entries": len(entries), "summary": summary,
            "outputs": [
                {"root": part.root,
                 "path": f"{ROOT_DIRS[part.root]}/"
                         f"pinball-{anchor[0]}-{anchor[1]}-{part.seq}-{tags[variant]}.zip",
                 "entries": len(part.entries), "est_size": part.est_bytes}
                for part in parts
            ],
        }
        if dry_run:
            report["variants"][variant] = variant_report
            continue

        if pack_dir.exists() and any(pack_dir.iterdir()):
            if not force:
                raise VariantError(f"输出目录已存在且非空: {pack_dir}(换 --tag/--out 或 --force)")
            shutil.rmtree(pack_dir)
        staging = pack_dir.with_name(pack_dir.name + ".staging")
        shutil.rmtree(staging, ignore_errors=True)
        try:
            written = write_parts(parts, staging, anchor[0], anchor[1], tags[variant])
            outputs = []
            for part, path in written:
                size = path.stat().st_size
                outputs.append({
                    "root": part.root,
                    "path": f"{ROOT_DIRS[part.root]}/{path.name}",
                    "entries": len(part.entries), "size": size,
                    "sha256": sha256(path.read_bytes()),
                })
                if size > CI_ZIP_CAP:
                    report["warnings"].append(
                        f"{path.name} {size} B 超过单包 5MiB 门禁,收方仓入库前需再拆")
            variant_report["outputs"] = outputs

            problems = self_check(staging, entries, variant, baseline, policy,
                                  expect_content_rows=expect_content_rows)
            if problems:
                raise VariantError(
                    f"{variant} 变体自检未通过({len(problems)} 项):\n  "
                    + "\n  ".join(problems[:10]))

            restart = detect_restart(entries)
            requires = build_requires(
                variant, chain_meta, anchor, summary, outputs, restart,
                min_server=min_server, server_features=server_features,
                client_patches=client_patches, official_tail=official_tail)
            (staging / "requires.json").write_text(
                json.dumps(requires, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            (staging / "说明.txt").write_text(
                render_readme(variant, chain_meta, anchor, requires, tags), encoding="utf-8")
            (staging / "report.json").write_text(
                json.dumps(variant_report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
            pack_dir.parent.mkdir(parents=True, exist_ok=True)
            staging.replace(pack_dir)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        variant_report["requires"] = str(pack_dir / "requires.json")
        report["variants"][variant] = variant_report

    if not dry_run:
        (out_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def self_check(pack_dir: Path, planned: Sequence[VariantEntry], variant: str,
               baseline: OfficialBaseline | None, policy: Policy,
               *, expect_content_rows: dict[str, Sequence[str]] | None = None) -> list[str]:
    """落盘自检:条目集与计划一致;content-only 再跑一遍金样校验。"""
    problems: list[str] = []
    produced = written_sources(pack_dir)
    produced_keys = [(source.root, source.rel) for source in produced]
    if len(produced_keys) != len(set(produced_keys)):
        problems.append("产物里有重复条目(同一路径出现在多个分包)")
    planned_keys = {(entry.root, entry.rel) for entry in planned}
    missing = planned_keys - set(produced_keys)
    extra = set(produced_keys) - planned_keys
    if missing:
        problems.append(f"产物缺少 {len(missing)} 个计划内条目: {sorted(missing)[:3]}")
    if extra:
        problems.append(f"产物多出 {len(extra)} 个计划外条目: {sorted(extra)[:3]}")
    if variant == "content-only" and baseline is not None:
        problems.extend(verify_content_only(
            produced, baseline, policy, expect_content_keys=expect_content_rows))
    return problems


# ------------------------------------------------------------------ CLI

def _mib(size: int) -> str:
    return f"{size / 2**20:.2f} MiB"


def _print_report(report: dict) -> None:
    chain = report["chain"]
    mode = "[预览] " if report["dry_run"] else ""
    print(f"{mode}内容来源: {chain['since']} → {chain['tail']}"
          f"({chain['edges']} 条边,终态 {chain['entries']} 条目)")
    print(f"锚定到收方链: {report['anchor']['from']} → {report['anchor']['to']}")
    for variant, info in report["variants"].items():
        summary = info["summary"]
        print(f"\n[{variant}] {info['pack']}  tag={info['tag']}  {info['entries']} 条目")
        if variant == "content-only":
            print(f"  去增强: 重建 {summary.get('rebuilt', 0)} 张表"
                  f"(回滚 {summary.get('revertedRows', 0)} 行、"
                  f"补回 {summary.get('restoredRows', 0)} 行)、"
                  f"丢弃 {summary.get('dropped', 0)} 个被改写的官方文件")
            for table in summary.get("rebuiltTables", ())[:8]:
                print(f"    {table['logical']}  回滚 {table['reverted']} 保留新增 {table['kept']}")
            for logical, keys in summary.get("unrecognizedAdditions", {}).items():
                print(f"  [注意] {logical} 有未识别的新增行(已保留): {keys[:8]}")
        for output in info["outputs"]:
            size = output.get("size", output.get("est_size", 0))
            print(f"    {output['path']}  {_mib(size)}({output['entries']} 条目)")
    if not report["dry_run"]:
        print(f"\n产物目录: {report['out_dir']}(每个变体一个子目录,含 requires.json/说明.txt)")
    for warning in report["warnings"]:
        print(f"[警告] {warning}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["plan", "build"])
    parser.add_argument("--variant", action="append", choices=list(VARIANTS),
                        help="要产出的变体(可重复;默认两个都出)")
    parser.add_argument("--since", default=policy_mod.OFFICIAL_TAIL,
                        help=f"内容来源链起点(默认官方链尾 {policy_mod.OFFICIAL_TAIL})")
    parser.add_argument("--anchor", dest="anchor_from",
                        help="收方当前链尾;不给则按我方原始版本边(同血统整段)")
    parser.add_argument("--anchor-to", dest="anchor_to",
                        help="锚定目标版本(默认 --anchor +0.0.1)")
    parser.add_argument("--tag", default=time.strftime("share%m%d"),
                        help="包 tag,纯小写字母数字(默认 shareMMDD;content-only 自动加 co)")
    parser.add_argument("--out", help=f"输出父目录(默认 {WORK_DIR}\\<tag>)")
    parser.add_argument("--max-zip-mib", type=int, default=5,
                        help="单 zip 上限 MiB(CI 门禁 5;0=不拆)")
    parser.add_argument("--official-file-action", choices=("drop", "revert"), default="drop",
                        help="被改写的官方资产文件:丢弃(默认)或回滚为官方原件下发")
    parser.add_argument("--official-tail", default=policy_mod.OFFICIAL_TAIL,
                        help="官方链尾版本(官方基准取到这一版)")
    parser.add_argument("--min-server", help="声明最低服务端版本/分支")
    parser.add_argument("--server-feature", action="append", default=[],
                        help="声明依赖的服务端功能(可重复)")
    parser.add_argument("--client-patch", action="append", default=[],
                        help="声明需要的客户端补丁(可重复)")
    parser.add_argument("--foreign-lineage", action="store_true",
                        help="收方是外血统(版本号空间与我方无关):允许锚定边与我方同名边重名")
    parser.add_argument("--no-content-expectations", action="store_true",
                        help="不校验「三角色/15 武器/700099 模式行齐全」"
                             "(只在故意发局部内容包时用)")
    parser.add_argument("--cdn", help="CDN 根(默认 WF_CDN_DIR 或 <repo>/.cdn/cn)")
    parser.add_argument("--repo-root", help="仓库根(默认按脚本位置)")
    parser.add_argument("--force", action="store_true", help="build:覆盖已存在的非空变体目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 报告")
    args = parser.parse_args(argv)

    cdn_root = Path(args.cdn).resolve() if args.cdn else _default_cdn()
    repo_root = Path(args.repo_root).resolve() if args.repo_root else ROOT
    try:
        report = build(
            cdn_root, repo_root, tag=args.tag,
            variants=tuple(args.variant) if args.variant else VARIANTS,
            since=args.since, anchor_from=args.anchor_from, anchor_to=args.anchor_to,
            out_dir=Path(args.out) if args.out else None,
            max_zip_mib=args.max_zip_mib,
            official_file_action=args.official_file_action,
            min_server=args.min_server, server_features=args.server_feature,
            client_patches=args.client_patch, official_tail=args.official_tail,
            foreign_lineage=args.foreign_lineage,
            expect_content_rows=(None if args.no_content_expectations
                                 else EXPECTED_CONTENT_ROWS),
            dry_run=(args.command == "plan"), force=args.force)
    except (VariantError, BaselineUnavailable, ValueError) as exc:
        print(f"[ERR] {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_report(report)
    return 0


def _default_cdn() -> Path:
    try:
        return Path(core.resolve_cdn_root_lax())
    except Exception:
        return ROOT / ".cdn" / "cn"


if __name__ == "__main__":
    sys.exit(main())
