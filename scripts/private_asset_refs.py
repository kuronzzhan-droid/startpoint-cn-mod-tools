"""Static path relocation for Python consumers; no imports or code execution."""
from __future__ import annotations

import ast
from functools import cache
import os
from pathlib import Path
import re


def destination(path: Path, root: Path, selected: list[str]) -> Path:
    for directory in selected:
        if path.is_relative_to(root / directory):
            return root / "private-assets" / path.relative_to(root)
    return path


def replace_links(text: str, selected: list[str]) -> str:
    for directory in sorted(selected, key=len, reverse=True):
        # Do not double-prefix already relocated references.
        end = r"(?=[/\s\"'`<>)]|$)" if "/" in directory else r"(?=/)"
        text = re.sub(r"(?<![\w/.-])" + re.escape(directory) + end,
                      "private-assets/" + directory, text)
        # A bare folder name in JS is ambiguous except at this filesystem API.
        text = re.sub(r"(path\.join\(\s*__dirname\s*,\s*)(['\"])" + re.escape(directory) + r"\2",
                      lambda m: m[1] + m[2] + "private-assets/" + directory + m[2], text)
    return text


def rewrite_javascript(text: str, source: Path, root: Path, selected: list[str]) -> str:
    """Rewrite static module and __dirname paths relative to their real source."""
    new_parent = destination(source, root, selected).parent

    def relative(match):
        value = match.group("path")
        if match.group("head").lstrip().startswith(("require", "import", "from")) and not value.startswith("."):
            return match.group(0)  # Named packages are not filesystem resources.
        old = (source.parent / value).resolve()
        if not old.is_relative_to(root):
            return match.group(0)
        new = destination(old, root, selected)
        if new == old and new_parent == source.parent:
            return match.group(0)
        updated = os.path.relpath(new, new_parent).replace("\\", "/")
        if not updated.startswith("."):
            updated = "./" + updated
        return match.group("head") + match.group("quote") + updated + match.group("quote")

    pattern = (r"(?P<head>\b(?:require|import)\(\s*|\bfrom\s+|"
               r"\bpath\.(?:join|resolve)\(\s*__dirname\s*,\s*)"
               r"(?P<quote>['\"])(?P<path>[^'\"\r\n]+)(?P=quote)")
    return replace_links(re.sub(pattern, relative, text), selected)


def rewrite_python(text: str, source: Path, root: Path, selected: list[str]) -> str:
    tree = ast.parse(text)
    symbols = {"__file__": source, "REPOSITORY": root}

    def evaluate(node):
        if isinstance(node, ast.Name):
            return symbols.get(node.id)
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in {"Path", "str"} and len(node.args) == 1:
                value = evaluate(node.args[0])
                if isinstance(value, (str, Path)):
                    return Path(value) if node.func.id == "Path" else str(value)
            if isinstance(node.func, ast.Attribute) and node.func.attr in {"resolve", "absolute"}:
                value = evaluate(node.func.value)
                if isinstance(value, Path):
                    return value.resolve()
        if isinstance(node, ast.Attribute):
            value = evaluate(node.value)
            if isinstance(value, Path) and node.attr in {"parent", "parents"}:
                return getattr(value, node.attr)
        if isinstance(node, ast.Subscript):
            value, index = evaluate(node.value), evaluate(node.slice)
            if isinstance(index, int) and isinstance(value, type(root.parents)):
                return value[index]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(left, Path) and isinstance(right, (str, Path)):
                return left / right
        return None

    # Top-level path constants are sufficient for local resource consumers;
    # evaluate only these safe AST operations, never user Python.
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = evaluate(node.value)
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                if isinstance(target, ast.Name) and value is not None:
                    symbols[target.id] = value
    evaluate = cache(evaluate)

    moved_source = destination(source, root, selected) != source
    lines = text.splitlines(keepends=True)
    starts, total = [], 0
    for line in lines:
        starts.append(total)
        total += len(line)

    def offset(node, end=False):
        line = (node.end_lineno if end else node.lineno) - 1
        column = node.end_col_offset if end else node.col_offset
        return starts[line] + len(lines[line].encode("utf-8")[:column].decode("utf-8"))

    edits = []
    def visit(node):
        if isinstance(node, (ast.BinOp, ast.Attribute, ast.Subscript, ast.Call)):
            value = evaluate(node)
            if isinstance(value, Path) and value.is_absolute() and value.is_relative_to(root):
                if moved_source or destination(value, root, selected) != value:
                    anchor = value
                    while not anchor.exists():
                        anchor = anchor.parent
                    relative = anchor.relative_to(root).as_posix()
                    replacement = f"_private_asset_path({relative!r})"
                    if anchor != value:
                        replacement += f" / {value.relative_to(anchor).as_posix()!r}"
                    edits.append((offset(node), offset(node, True), replacement))
                    return
        for child in ast.iter_child_nodes(node):
            visit(child)
    visit(tree)
    for start, end, value in sorted(edits, reverse=True):
        text = text[:start] + value + text[end:]
    if edits:
        tree = ast.parse(text)
        line = 0
        for node in tree.body:
            if ((isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                 and isinstance(node.value.value, str))
                    or isinstance(node, ast.ImportFrom) and node.module == "__future__"):
                line = node.end_lineno
            else:
                break
        lines = text.splitlines(keepends=True)
        # The moved asset builders are also directly executable Python scripts.
        # This relative bootstrap keeps their CLI usable without changing the
        # user's PYTHONPATH or importing a different checkout's wf package.
        relocated = destination(source, root, selected)
        depth = len(relocated.relative_to(root).parts) - 1
        bootstrap = ("from pathlib import Path as _PrivateAssetPath\n"
                     "import sys as _private_asset_sys\n"
                     f"_private_asset_sys.path.insert(0, str(_PrivateAssetPath(__file__).resolve().parents[{depth}]))\n"
                     "from wf.local_assets import asset_path as _private_asset_path\n")
        lines.insert(line, bootstrap)
        text = "".join(lines)
    # Serialized repository-relative asset references (e.g. spec dictionaries).
    # Avoid editing the resolver's own arguments, which deliberately stay public.
    tree = ast.parse(text)
    protected = {id(arg) for node in ast.walk(tree) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "_private_asset_path"
                 for arg in node.args}
    lines = text.splitlines(keepends=True)
    starts, total = [], 0
    for line in lines:
        starts.append(total)
        total += len(line)
    edits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in protected:
            if any(("/" in d and node.value == d) or node.value.startswith(d + "/") for d in selected):
                edits.append((offset(node), offset(node, True), repr("private-assets/" + node.value)))
    for start, end, value in sorted(edits, reverse=True):
        text = text[:start] + value + text[end:]
    ast.parse(text)
    return text
