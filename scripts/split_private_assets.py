"""Preview or apply checked directory decisions from the public-assets review.

No network, Git commits, or history edits. The default is a read-only plan.
Only explicit [x] 移出 rows are moved; a checked 可公开 row is left alone.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

try:
    from scripts.private_asset_refs import destination, replace_links, rewrite_javascript, rewrite_python
except ModuleNotFoundError:
    from private_asset_refs import destination, replace_links, rewrite_javascript, rewrite_python

REPOSITORY = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".json", ".md", ".html", ".js", ".cjs", ".mjs", ".css", ".txt", ".ts", ".yml", ".yaml", ".toml"}


def decisions(text: str, allowed: set[str]) -> list[str]:
    selected = []
    for line in text.splitlines():
        if not line.startswith("|") or "<!-- asset-dir:" not in line:
            continue
        match = re.search(r"<!-- asset-dir:([^>]+) -->", line)
        if not match:
            raise ValueError("Malformed asset directory row")
        directory = match.group(1).strip()
        if directory not in allowed:
            raise ValueError(f"Directory is not in the audited inventory: {directory}")
        public = bool(re.search(r"\[[xX]\]\s*可公开", line))
        private = bool(re.search(r"\[[xX]\]\s*移出", line))
        if public and private:
            raise ValueError(f"Conflicting author decisions: {directory}")
        if private:
            selected.append(directory)
    return sorted({d for d in selected if not any(d.startswith(p + "/") for p in selected if p != d)})


def inside(root: Path, path: Path) -> Path:
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"Path leaves the checkout: {path}")
    return path


def no_links(root: Path, path: Path) -> None:
    """An in-checkout junction is still unsafe for the private destination."""
    inside(root, path)
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        if candidate.is_symlink() or (hasattr(candidate, "is_junction") and candidate.is_junction()):
            raise ValueError(f"Relocation path contains a link: {candidate}")


def plan(root: Path, selected: list[str], tracked: list[Path], inventory: dict) -> dict:
    root = root.resolve()
    moves, edits = [], []
    if not selected:
        return {"moves": moves, "edits": edits}
    for directory in selected:
        relative = Path(directory)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError(f"Invalid resource directory: {directory}")
        source = inside(root, root / relative)
        target = inside(root, root / "private-assets" / relative)
        no_links(root, source)
        no_links(root, target)
        if not source.is_dir():
            raise ValueError(f"Source missing: {directory}")
        if source.is_symlink() or (hasattr(source, "is_junction") and source.is_junction()):
            raise ValueError(f"Resource directory is a link: {directory}")
        # Validate all descendants, including junctions, before any mutation.
        for child in source.rglob("*"):
            inside(root, child)
            if child.is_symlink() or (hasattr(child, "is_junction") and child.is_junction()):
                raise ValueError(f"Resource contains a link: {child}")
            candidate = inside(root, target / child.relative_to(source))
            if candidate.exists() and not (child.is_dir() and candidate.is_dir()):
                raise ValueError(f"Destination collision: {candidate}")
        if target.exists() and not target.is_dir():
            raise ValueError(f"Destination is not a directory: {target}")
        for item in inventory["files"]:
            if Path(item["path"]).is_relative_to(relative):
                raw = (root / item["path"]).read_bytes()
                if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                    raise ValueError(f"Audited asset changed: {item['path']}")
        moves.append((source, target))
    for source in tracked:
        inside(root, source)
        if source.suffix.lower() not in TEXT_SUFFIXES or not source.is_file():
            continue
        relative = source.relative_to(root).as_posix()
        if relative.startswith(("docs/m0/", "scripts/private_asset", "scripts/split_private")):
            continue  # Audit evidence and the migration implementation are immutable inputs.
        raw = source.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if source.suffix == ".py":
            updated = rewrite_python(text, source, root, selected)
        elif source.suffix in {".js", ".cjs", ".mjs", ".ts"}:
            updated = rewrite_javascript(text, source, root, selected)
        else:
            updated = replace_links(text, selected)
        if updated != text:
            edits.append((destination(source, root, selected), raw, updated.encode("utf-8")))
    return {"moves": moves, "edits": edits}


def apply_plan(root: Path, changes: dict) -> None:
    moved, edited, original_directories, created_directories = [], [], [], []

    def mkdir(path):
        missing = []
        current = path
        while not current.exists():
            missing.append(current)
            current = current.parent
        path.mkdir(parents=True, exist_ok=True)
        created_directories.extend(reversed(missing))

    try:
        for source, target in changes["moves"]:
            inside(root, source)
            inside(root, target)
            no_links(root, source)
            no_links(root, target)
            original_directories.extend([source, *(p for p in source.rglob("*") if p.is_dir())])
            for child in source.rglob("*"):
                no_links(root, child)
                final = target / child.relative_to(source)
                no_links(root, final)
                if final.exists() and not (child.is_dir() and final.is_dir()):
                    raise ValueError(f"Destination collision after planning: {final}")
            mkdir(target.parent)
            if not target.exists():
                source.rename(target)
                moved.append((source, target))
            else:
                # Archived fixtures may already occupy the private mirror.
                # Merge only preflighted, non-colliding files; preserve all old data.
                for child in list(source.rglob("*")):
                    if child.is_file():
                        final = target / child.relative_to(source)
                        mkdir(final.parent)
                        child.rename(final)
                        moved.append((child, final))
                for child in sorted(source.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                    if child.is_dir():
                        child.rmdir()
                source.rmdir()
        for target, original, updated in changes["edits"]:
            inside(root, target)
            if target.read_bytes() != original:
                raise ValueError(f"Reference changed after planning: {target}")
            edited.append((target, original))
            target.write_bytes(updated)
    except Exception:
        for target, original in reversed(edited):
            target.write_bytes(original)
        for source, target in reversed(moved):
            source.parent.mkdir(parents=True, exist_ok=True)
            target.rename(source)
        for directory in original_directories:
            directory.mkdir(parents=True, exist_ok=True)
        for directory in reversed(created_directories):
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()
        raise


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=REPOSITORY / "docs/m0/public-assets-review.md")
    parser.add_argument("--apply", action="store_true", help="Apply explicit checked directory decisions")
    args = parser.parse_args(argv)
    root = REPOSITORY.resolve()
    inside(root, args.review.resolve())
    inventory = json.loads((root / "docs/m0/public-assets-inventory.json").read_text(encoding="utf-8"))
    selected = decisions(args.review.read_text(encoding="utf-8"), set(inventory["directories"]))
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode("utf-8").split("\0")
    changes = plan(root, selected, [root / name for name in names if name], inventory)
    print(json.dumps({"apply": args.apply, "directories": selected,
                      "moves": [str(s.relative_to(root)) for s, _ in changes["moves"]],
                      "updated_references": [str(p.relative_to(root)) for p, _, _ in changes["edits"]]},
                     ensure_ascii=False, indent=2))
    if args.apply:
        apply_plan(root, changes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
