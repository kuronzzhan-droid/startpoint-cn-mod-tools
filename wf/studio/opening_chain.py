"""Compare the loaded resource chain with one local manifest snapshot, without writes."""
from __future__ import annotations

import hashlib
from pathlib import Path

from wf.view.chain import archive_names, version

from .drafts import DraftError
from .rehearsal_server import chain_tail


def check(rule, status, message, *, blocking=False):
    return {"rule": "opening." + rule, "status": status, "blocking": blocking, "message": message}


def _local_test_only(entry):
    flag = entry.get("local_test_only")
    if flag is not None and not isinstance(flag, bool):
        raise DraftError("manifest 条目的 local_test_only 必须是布尔值")
    return flag is True


def source_edges(source):
    """Use the already loaded manifest view, including explicit overlay edges."""
    from wf.view.chain import ARCHIVE, manifest_entries

    view = source.view
    if not hasattr(view, "edges"):
        raise DraftError("当前视图没有可核对的 manifest 依赖链；请使用命名 manifest 视图")
    records = {record["name"]: record for record in view.zip_records}
    paths = {Path(path).name: Path(path) for path in view.zips}
    edges = [{"from": edge["depends_on"], "to": edge["version"], "names": list(edge["names"])}
             for edge in view.edges]
    marked = {edge["version"] for edge in view.edges if _local_test_only(edge)}
    if getattr(view, "manifest", None) is not None:
        from .freshness import freshness
        current = freshness(source)
        if current.get("error") or current.get("stale"):
            raise DraftError("已加载视图的 manifest 已更新或不可验证；请重启编辑台加载当前链尾")
        entries = manifest_entries(view.manifest, view.search_dirs, view.manifests)
        marked.update(entry.get("version") for entry in entries if _local_test_only(entry))
    for archive in getattr(view, "extra_zips", []):
        match = ARCHIVE.fullmatch(Path(archive).name)
        if match is None:
            raise DraftError("额外归档缺少合法版本边，不能生成开服清单")
        previous, target = match.group(1, 2)
        if edges and (edges[-1]["from"], edges[-1]["to"]) == (previous, target):
            edges[-1]["names"].append(Path(archive).name)
        else:
            edges.append({"from": previous, "to": target, "names": [Path(archive).name]})
    tail = view.base_version
    for edge in edges:
        if edge["from"] != tail or version(edge["to"]) <= version(tail):
            raise DraftError("当前视图包含不连续或回退的边，不能生成开服清单")
        edge["names"] = archive_names({"depends_on": edge["from"], "version": edge["to"],
                                        "chain": edge["names"]})
        edge["archives"] = []
        edge["localTestOnly"] = edge["to"] in marked
        for name in edge["names"]:
            path = paths.get(name)
            if path is None or not path.is_file() or name not in records:
                raise DraftError("当前视图的归档或加载摘要缺失；请补齐输入并重启编辑台")
            edge["archives"].append({"name": name, "sha256": records[name]["sha256"],
                                      "size": path.stat().st_size})
        tail = edge["to"]
    if tail != source.version:
        raise DraftError("当前视图版本与资源链尾不一致")
    return edges, paths


def compare_manifest(edges, manifest, base_version):
    """A same-number edge with different archives is a conflict, not an update."""
    tail = chain_tail(manifest)
    checks = [check("target-chain", "满足", f"目标本机快照启用链连续，链尾 {tail}")]
    enabled = {entry["version"]: entry for entry in manifest["patches"]
               if entry.get("enabled") is True and entry.get("type") == "patch"}
    for edge in edges:
        existing = enabled.get(edge["to"])
        if existing is None:
            if version(edge["to"]) <= version(tail):
                checks.append(check("chain-prefix", "问题", f"目标链缺少当前视图共有版本 {edge['to']}", blocking=True))
            continue
        try:
            same = (existing.get("depends_on") == edge["from"] and archive_names(existing) == edge["names"])
        except (ValueError, TypeError, KeyError):
            same = False
        if not same:
            checks.append(check("edge-conflict", "问题", f"版本 {edge['to']} 的父版本或归档列表不同", blocking=True))
            continue
        integrity = {item.get("name"): item for item in existing.get("archive_integrity", [])
                     if isinstance(item, dict)}
        for archive in edge["archives"]:
            old = integrity.get(archive["name"], {})
            if any(old.get(key) is not None and old[key] != archive[key] for key in ("sha256", "size")):
                checks.append(check("archive-conflict", "问题", f"版本 {edge['to']} 的归档摘要或大小不同：{archive['name']}", blocking=True))
            elif not old.get("sha256"):
                checks.append(check("archive-evidence", "待验证", f"目标版本 {edge['to']} 缺少归档 SHA-256；版本号相同不证明内容相同"))
    tips = [base_version, *(edge["to"] for edge in edges)]
    if tail not in tips:
        checks.append(check("target-anchor", "问题", "目标链尾不在当前视图依赖链上；禁止降版本或猜测补边", blocking=True))
        return tail, [], checks
    missing = edges[tips.index(tail):]
    disabled = {entry.get("version") for entry in manifest["patches"]
                if entry.get("enabled") is not True}
    for edge in missing:
        if edge["to"] in disabled:
            checks.append(check("disabled-collision", "问题", f"目标已登记停用版本 {edge['to']}；不得直接覆盖或重新启用", blocking=True))
    if not any(item["blocking"] for item in checks):
        checks.append(check("chain-compare", "满足", f"需依次补 {len(missing)} 条边" if missing else "目标链尾与当前视图一致"))
    return tail, missing, checks


def verify_archives(edges, paths):
    """Only hash edges to be copied; no server active directory is written/read."""
    for edge in edges:
        for archive in edge["archives"]:
            with paths[archive["name"]].open("rb") as stream:
                current = hashlib.file_digest(stream, "sha256").hexdigest()
            if current != archive["sha256"]:
                raise DraftError("待补归档已偏离当前视图加载摘要；请重启编辑台后重新核对")
