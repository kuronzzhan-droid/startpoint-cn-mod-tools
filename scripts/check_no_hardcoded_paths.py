"""Reject workstation roots and fixed absolute import bootstraps.

Scan tracked and non-ignored source, including archive/legacy and documentation.
Ignored machine profiles and generated work/ artifacts are not repository code.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
import subprocess

REPOSITORY = Path(__file__).resolve().parents[1]
WORKSTATION = re.compile(r"(?i)" + "D:" + r"[/\\]+WF(?=[/\\\s\"'`.)]|$)")
DRIVE = re.compile(r"^[A-Za-z]:[/\\]")


def source_paths(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root, check=True, capture_output=True,
    )
    return sorted({root / value.decode("utf-8") for value in result.stdout.split(b"\0")
                   if value and (root / value.decode("utf-8")).is_file()})


def scan_text(text: str, name: str) -> list[dict]:
    findings = []
    for number, line in enumerate(text.splitlines(), 1):
        if WORKSTATION.search(line):
            findings.append({"path": name, "line": number, "rule": "workstation-root"})
    if not name.endswith(".py"):
        return findings
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return findings  # Syntax is covered separately by the Python test suite.
    assignments: dict[str, list[ast.AST]] = {}
    path_aliases = {"sys.path"}
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if isinstance(target, ast.Name) and node.value is not None:
                    assignments.setdefault(target.id, []).append(node.value)
        if isinstance(node, ast.ImportFrom) and node.module == "sys":
            path_aliases.update(alias.asname or alias.name for alias in node.names if alias.name == "path")
        if isinstance(node, ast.Import):
            path_aliases.update((alias.asname or "sys") + ".path" for alias in node.names if alias.name == "sys")
    for key, values in assignments.items():
        if any(ast.unparse(value) in path_aliases for value in values):
            path_aliases.add(key)

    def external(node: ast.AST, seen=frozenset()) -> bool:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return bool(DRIVE.match(node.value) or node.value.startswith(("/", "\\\\")))
        if isinstance(node, ast.Name) and node.id not in seen:
            return any(external(value, seen | {node.id}) for value in assignments.get(node.id, []))
        if isinstance(node, ast.Call):
            called = ast.unparse(node.func)
            if called in {"root_path", "path", "wf.paths.path", "wf.paths.root_path", "Path.home"}:
                return True
            if called.startswith(("os.environ.", "os.getenv")):
                return True
        return any(external(child, seen) for child in ast.iter_child_nodes(node))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if (ast.unparse(node.func.value) not in path_aliases
                or node.func.attr not in {"insert", "append", "extend"}):
            continue
        args = node.args[1:] if node.func.attr == "insert" else node.args
        if any(external(arg) for arg in args):
            findings.append({"path": name, "line": node.lineno, "rule": "absolute-import-path"})
    return findings


def scan(root: Path = REPOSITORY) -> dict:
    findings, count = [], 0
    for path in source_paths(root):
        try:
            raw = path.read_bytes()
            if b"\0" in raw:
                continue
            text = raw.decode("utf-8-sig")
        except UnicodeError:
            continue
        count += 1
        findings.extend(scan_text(text, path.relative_to(root).as_posix()))
    return {"scanned_text_files": count, "findings": findings, "count": len(findings)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = scan()
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        target = args.json.resolve()
        if not target.is_relative_to(REPOSITORY):
            parser.error("report must be inside this checkout")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output + "\n", encoding="utf-8")
    print(output)
    return bool(result["count"])


if __name__ == "__main__":
    raise SystemExit(main())
