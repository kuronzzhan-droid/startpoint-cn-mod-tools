"""Read-only whole-table policy audit with all findings and coverage states."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from .model import ACTION_SKILL, CHARACTER, CUSTOM, SERVER_TARGETS, TextWorkspace, cells, custom_text, sha256
from .standard import check_entry, coverage, rule_catalog
from wf.view.safety import local_output


def audit_workspace(workspace: TextWorkspace):
    """Audit every override (including unowned keys) and every skill tier."""
    entries, findings, surfaces = [], [], set()
    owners = {}
    for cid, leaf in workspace.table(CHARACTER).items():
        row = cells(leaf)
        owners.setdefault(row[8], []).append(cid)

    def add(key, text, surface, location, source, **details):
        surfaces.add(surface)
        found = check_entry(key, text, surface=surface, location=location)
        index = len(entries) + 1
        for finding in found:
            finding.update(entry=index, **details)
        entries.append({"entry": index, "key": key, "location": location, "surface": surface,
                        "source": source, "text_sha256": sha256(text.encode()),
                        "problem_count": len(found), **details})
        findings.extend(found)

    for key, leaf in workspace.table(CUSTOM).items():
        if key.startswith("desc_override_"):
            add(key, custom_text(leaf), "desc_override", f"desc_override.{key}", CUSTOM)
    for key, tiers in workspace.table(ACTION_SKILL).items():
        if not isinstance(tiers, dict):
            raise ValueError(f"action_skill[{key}] is not a tier table")
        for tier, leaf in tiers.items():
            if not leaf:
                continue
            row = cells(leaf)
            if len(row) < 2:
                raise ValueError(f"action_skill[{key}][{tier}] lacks c0/c1")
            add(key, row[1], "action_skill", f"action_skill.{key}.{tier}.c1", ACTION_SKILL,
                character_ids=owners.get(key, []), tier=tier)
    mirrors = []
    for target in SERVER_TARGETS:
        if target not in workspace.server_docs:
            mirrors.append({"target": target, "state": "未执行", "message": "未提供该版本完整服务端镜像；不以当前文件冒充历史"})
            continue
        count = 0
        for cid, rows in workspace.server_docs[target].items():
            if not isinstance(rows, list) or not rows or not isinstance(rows[0], list):
                raise ValueError(f"malformed server mirror: {target}:{cid}")
            for tier, column in (("1", 5), ("2", 7), ("3", 9)):
                if len(rows[0]) > column and rows[0][column]:
                    add(cid, rows[0][column], "action_skill", f"{Path(target).name}.{cid}.c{column}", target,
                        character_ids=[cid], tier=tier)
                    count += 1
        mirrors.append({"target": target, "state": "满足", "message": "完整回读显式镜像并执行技能描述规则；不代表已部署", "checked": count})
    workspace.verify()
    states = coverage(surfaces, findings)
    manifest = getattr(workspace.view, "manifest", None)
    manifest_evidence = None
    if manifest is not None:
        raw = Path(manifest).read_bytes()
        manifest_evidence = {"path": str(manifest), "sha256": sha256(raw),
                             "cdn_version": json.loads(raw).get("cdn_version")}
    return {"schema": "wf-text-standard-audit/1", "tip": getattr(workspace.view, "tip", None),
            "manifest": manifest_evidence,
            "view_lock": workspace.view.lock_data() if hasattr(workspace.view, "lock_data") else None,
            "standard_version": rule_catalog()["version"], "standard_source_sha256": rule_catalog()["source_sha256"],
            "state": "问题" if findings else "待验证" if entries else "未执行",
            "scope": rule_catalog()["scope_note"], "checked_entries": len(entries),
            "problem_count": len(findings), "problem_entries": len({f["entry"] for f in findings}),
            "problems_by_rule": dict(sorted(Counter(f["rule"] for f in findings).items())),
            "sources": {**{key: sha256(raw) for key, raw in workspace.raw.items()},
                        **{key: sha256(raw) for key, raw in workspace.server_raws.items()}},
            "coverage": states, "server_mirrors": mirrors, "entries": entries, "findings": findings}


def markdown_standard(report):
    lines = [f"# 面板文案规范核查 {report['tip']}", "",
             f"扫描 {report['checked_entries']} 条文本；{report['problem_entries']} 条文本有确定性问题，"
             f"共 {report['problem_count']} 项。状态：{report['state']}。", "",
             report["scope"], "",
             "所有输入只读，未改原文。无命中只证明所列确定性写法未命中；玩法语义、数值真实性、首处说明和副作用保留均须核对。",
             "完整键清单、全文问题证据、输入摘要及逐规则覆盖状态保存在同名 JSON。", "",
             "## 规则覆盖", "", "| 规则 | 状态 | 覆盖边界 |", "|---|---|---|"]
    lines += [f"| {r['rule']} | {r['state']} | {r['boundary']} |" for r in report["coverage"]]
    lines += ["", "## 服务端镜像", ""]
    lines += [f"- {r['target']}：{r['state']}，{r['message']}" for r in report["server_mirrors"]]
    lines += ["", "## 全部确定性问题", ""]
    for index, finding in enumerate(report["findings"], 1):
        lines += [f"### {index}. {finding['location']}", "",
                  f"规则：`{finding['rule']}`（{finding['source']}；{finding['evidence_nature']}）", "",
                  finding["message"], "", "```text", finding["evidence"]["text"], "```", "",
                  "命中：" + json.dumps(finding["evidence"]["matches"], ensure_ascii=False), ""]
    return "\n".join(lines) + "\n"


def write_report(report, output):
    output = local_output(output)
    if output.suffix.lower() != ".json":
        raise ValueError("text audit output must use .json (a companion .md is also written)")
    markdown = local_output(output.with_suffix(".md"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", "utf-8")
    markdown.write_text(markdown_standard(report), "utf-8")
    return output
