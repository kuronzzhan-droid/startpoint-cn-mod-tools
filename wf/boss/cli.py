"""Offline boss list/show commands, with explicit reproducible view options."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from wf.view.manifest import ManifestView
from wf.view.safety import local_output
from .reader import BossReader


def main(argv=None):
    parser = argparse.ArgumentParser(prog="wf boss")
    parser.add_argument("action", choices=("list", "show"))
    parser.add_argument("quest", nargs="?")
    parser.add_argument("--tip", default="1.4.236")
    parser.add_argument("--base-version", default="1.4.131")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--extra-manifest", type=Path, action="append")
    parser.add_argument("--store", type=Path)
    parser.add_argument("--zip-dir", type=Path, action="append")
    parser.add_argument("--lock", type=Path)
    parser.add_argument("--write-lock", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    if (args.action == "show") != (args.quest is not None):
        parser.error("show 需要 quest；list 不接受 quest")
    view = ManifestView(args.tip, base_version=args.base_version, manifest=args.manifest,
                        store=args.store, search_dirs=args.zip_dir, lock=args.lock,
                        manifests=args.extra_manifest)
    reader = BossReader(view)
    result = reader.list() if args.action == "list" else reader.show(args.quest)
    view.verify()
    if args.write_lock:
        view.save_lock(args.write_lock)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.json:
        target = local_output(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0
