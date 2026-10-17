"""CLI for local text inspection, checked edits and prepush explanations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit import explain_warnings, markdown_audit
from .edit import prepare_edit, stage_edit
from .model import TextWorkspace
from .rules import check_character
from .release import audit_workspace, write_report
from .standard import rule_catalog
from wf.view.safety import local_output, restrict_writes


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="wf text")
    commands = parser.add_subparsers(dest="command", required=True)
    rules = commands.add_parser("rules", help="查看逐项文案规范与自动检查边界")
    rules.add_argument("--output", type=Path)
    for name in ("read", "check", "edit", "explain", "audit-standard"):
        command = commands.add_parser(name)
        command.add_argument("--tip", required=True)
        command.add_argument("--lock", type=Path)
        command.add_argument("--server-text", type=Path, help="explicit read-only character_text.json")
        command.add_argument("--rank-text", type=Path, help="explicit read-only character_text_rank_p5b.json")
        if name in ("read", "check"):
            command.add_argument("character_id")
            command.add_argument("--output", type=Path)
        if name == "edit":
            command.add_argument("edit_file", type=Path)
            command.add_argument("--output", required=True, type=Path)
            for field in ("id", "name", "to-version", "slug", "created-at"):
                command.add_argument("--" + field, required=True)
        if name == "explain":
            command.add_argument("log", type=Path)
            command.add_argument("--output", required=True, type=Path)
        if name == "audit-standard":
            command.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        restrict_writes()
        if args.command == "rules":
            encoded = json.dumps(rule_catalog(), ensure_ascii=False, indent=2) + "\n"
            if args.output:
                output = local_output(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(encoded, "utf-8")
            else:
                print(encoded, end="")
            return 0
        from wf.view import ManifestView
        view = ManifestView(tip=args.tip, lock=args.lock)
        workspace = TextWorkspace(view, args.server_text, args.rank_text)
        if args.command == "audit-standard":
            report = audit_workspace(workspace)
            write_report(report, args.output)
            print(json.dumps({key: report[key] for key in ("tip", "state", "checked_entries", "problem_count", "problem_entries")}, ensure_ascii=False))
            return int(report["state"] in {"问题", "未执行"})
        if args.command in ("read", "check"):
            document = workspace.read(args.character_id)
            result = document if args.command == "read" else check_character(document)
        elif args.command == "edit":
            edit = json.loads(args.edit_file.read_text("utf-8"))
            prepared = prepare_edit(workspace, edit)
            metadata = {"id": args.id, "name": args.name, "from_version": args.tip,
                        "to_version": args.to_version, "slug": args.slug, "created_at": args.created_at}
            view.verify()
            target = stage_edit(prepared, args.output, metadata)
            print(json.dumps({"changeset": str(target), "checks": prepared["checks"]}, ensure_ascii=False, indent=2))
            return 0
        else:
            sources = {}
            if args.server_text:
                sources["assets/cdndata/character_text.json"] = args.server_text
            if args.rank_text:
                sources["assets/cdndata/character_text_rank_p5b.json"] = args.rank_text
            result = explain_warnings(args.log, workspace, sources)
        view.verify()
        encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            output = local_output(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(encoded, "utf-8")
            if args.command == "explain":
                local_output(output.with_suffix(".md")).write_text(markdown_audit(result), "utf-8")
        else:
            print(encoded, end="")
        if args.command == "check":
            return int(any(f["state"] == "问题" for f in result))
        if args.command == "explain":
            print(f"逐条解释 {result['warning_count']} 条；历史输入匹配 {result['historical_matches']} 条；原问题状态保留。")
            return int(any(e["category"] == "历史输入已漂移" for e in result["entries"]))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"wf text: {exc}")
        return 2
