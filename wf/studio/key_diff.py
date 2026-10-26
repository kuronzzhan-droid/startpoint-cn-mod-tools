"""Compare every delivered table against the exact read-only delivery baseline."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import wf_mod_tool as core

from .key_subject import SubjectKeys
from .key_retention import inner_deletions

KEY_LISTS = ("removed", "foreign", "changed", "added", "unknown", "owned")


def _rows(raw, logical):
    if raw is None:
        return {}
    parsed = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
    return dict(zip(parsed.keys, parsed.rows))


def _digest(raw):
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def _before(view, member):
    try:
        return view.read_member(member.member)[0]
    except (FileNotFoundError, KeyError):
        return None


def compare_delivery(baseline_view, zips=(), *, delivery_dir=None, members=None, subject=None,
                     from_version=None, to_version=None):
    """Return full key lists; no data, baseline files or archives are mutated.

    ``members`` accepts ``delivery_inputs.DeliveryMember`` instances. ZIP order
    is preserved, including repeated members across archives; each occurrence
    is compared to the original baseline (never silently merged or omitted).
    """
    from .delivery_inputs import read_delivery_members

    if members is None:
        members = read_delivery_members(zips, delivery_dir=delivery_dir, allow_overlays=True)
    members = list(members)
    ownership = SubjectKeys(baseline_view, subject)
    tables, files = [], []
    for member in members:
        if not member.logical and member.root == "common":
            raise ValueError("无法恢复 common 成员的逻辑路径，不能确认共享表键检查完整："
                             f"{member.archive}/{member.member}；请提供完整性侧车清单或逻辑路径表")
        before = _before(baseline_view, member)
        common = {"logical": member.logical, "root": member.root, "member": member.member,
                  "archive": member.archive, "from": member.from_version, "to": member.to_version,
                  "beforeSha256": _digest(before), "sha256": _digest(member.data)}
        if not member.logical or not member.logical.endswith(".orderedmap"):
            if before != member.data:
                files.append({**common, "change": "added" if before is None else "changed"})
            continue
        previous, current = _rows(before, member.logical), _rows(member.data, member.logical)
        old, new = set(previous), set(current)
        changes = {"added": sorted(new - old), "removed": sorted(old - new),
                   "changed": sorted(key for key in old & new if previous[key] != current[key])}
        deletions = inner_deletions(before, member.data, member.logical, changes["changed"])
        # Keep the public lists in the outer-key namespace. Details identify the
        # exact nested path or record-count loss; a changed key can also lose data.
        changes["removed"] = sorted(set(changes["removed"]) | {d["path"][0] for d in deletions})
        categories = {"owned": [], "foreign": [], "unknown": []}
        for key in sorted(set().union(*changes.values())):
            categories[ownership.classify(member.logical, key)].append(key)
        lists = {**changes, **categories}
        tables.append({**common, "beforeKeys": len(old), "afterKeys": len(new), **lists,
                       "deletions": deletions,
                       "counts": {name: len(keys) for name, keys in lists.items()}, "truncated": False})
    totals = {name: sum(table["counts"][name] for table in tables) for name in KEY_LISTS}
    blocked, foreign = bool(totals["removed"]), bool(totals["foreign"])
    warning = foreign or bool(totals["unknown"])
    starts = [member.from_version for member in members if member.from_version]
    ends = [member.to_version for member in members if member.to_version]
    report = {"schema": "wf-studio-key-diff/1", "ok": not blocked,
              "status": "blocked" if blocked else "warning" if warning else "ok",
              "baseline": {"view": getattr(baseline_view, "view_name", None),
                           "tip": getattr(baseline_view, "tip", None),
                           "version": getattr(baseline_view, "effective_version",
                                              getattr(baseline_view, "tip", None))},
              "delivery": {"from": from_version or (starts[0] if starts else None),
                           "to": to_version or (ends[-1] if ends else None),
                           "archives": list(dict.fromkeys(member.archive for member in members))},
              "subject": ownership.describe(), "counts": totals, "tables": tables, "files": files,
              "blocking": blocked, "warnings": ["存在非本草稿主体的改动键，请与并行线程核对"] if foreign else []}
    if totals["unknown"]:
        report["warnings"].append("部分改动键归属未知，未视为自有键")
    return report


def summarize(report, max_keys=200):
    """Cap all six key lists together, per table occurrence, keeping full counts."""
    if max_keys < 0:
        raise ValueError("max_keys 不能为负")
    result = copy.deepcopy(report)
    for table in result.get("tables", []):
        budget, omitted = max_keys, False
        for name in KEY_LISTS:
            keys = table.get(name, [])
            table[name] = keys[:budget]
            omitted = omitted or len(table[name]) < len(keys)
            budget -= len(table[name])
        table["truncated"] = bool(table.get("truncated") or omitted)
    return result


def _inline(value):
    return "`" + str(value).replace("`", "\\`").replace("\n", " ").replace("\r", " ") + "`"


def markdown(report):
    """Complete Chinese handoff list for concurrent authors to reconcile keys."""
    baseline, delivery = report.get("baseline", {}), report.get("delivery", {})
    labels = {"ok": "通过", "warning": "警告", "blocked": "阻断"}
    lines = ["# 交付共享表键级差异", "", f"基线视图：{_inline(baseline.get('view') or '未命名视图')}",
             f"链尾版本：{_inline(baseline.get('tip') or '未知')}；完整来源版本：{_inline(baseline.get('version') or '未知')}",
             f"交付版本区间：{_inline(delivery.get('from') or '未知')} → {_inline(delivery.get('to') or '未知')}",
             f"结论：**{labels.get(report.get('status'), report.get('status', '未知'))}**。"
             "removed 非空一律阻断；foreign 警告；unknown 需要人工核对。", "",
             "各 ZIP 按输入顺序列出，每次表输出均与上述原始基线比较。行字节不同即 changed。", ""]
    names = {"added": "新增", "changed": "修改", "removed": "删除", "owned": "主体自有",
             "foreign": "非主体", "unknown": "归属未知"}
    for table in report.get("tables", []):
        lines += [f"## {_inline(table['logical'])}", "",
                  f"归档：{_inline(table['archive'])}；CDN 根：{_inline(table['root'])}", "",
                  "；".join(f"{names[name]} {table['counts'][name]}" for name in
                            ("added", "changed", "removed", "owned", "foreign", "unknown")), ""]
        for name in KEY_LISTS:
            if table.get(name):
                lines.append(f"- {names[name]}（{name}）：" + "、".join(map(_inline, table[name])))
        for detail in table.get("deletions", []):
            lines.append(f"- 内层删除：{_inline(json.dumps(detail, ensure_ascii=False))}")
        lines.append("")
    if report.get("files"):
        lines += ["## 非表成员（SHA-256）", ""]
        for item in report["files"]:
            lines.append(f"- {item['change']}：{_inline(item['logical'] or item['member'])}；"
                         f"归档 {_inline(item['archive'])}；{_inline(item['sha256'])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_reports(report, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "key-diff.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
    (directory / "key-diff.md").write_text(markdown(report), "utf-8")
