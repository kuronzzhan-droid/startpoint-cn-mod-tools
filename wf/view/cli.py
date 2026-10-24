"""Read and lock a manifest-derived view without materializing external data."""
import argparse
import json
from pathlib import Path

from .manifest import ManifestView
from .safety import local_output


def main(argv=None):
    parser = argparse.ArgumentParser(prog="wf view")
    parser.add_argument("--tip", required=True)
    parser.add_argument("--base-version", default="1.4.131")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--extra-manifest", type=Path, action="append")
    parser.add_argument("--store", type=Path)
    parser.add_argument("--zip-dir", type=Path, action="append")
    parser.add_argument("--lock", type=Path, help="必须匹配的输入锁文件")
    parser.add_argument("--write-lock", type=Path)
    parser.add_argument("--logical", action="append", default=[], help="额外读取并锁定的逻辑成员")
    parser.add_argument("--json", type=Path, help="视图摘要输出（仓内）")
    args = parser.parse_args(argv)
    view = ManifestView(args.tip, base_version=args.base_version, manifest=args.manifest,
                        store=args.store, search_dirs=args.zip_dir, lock=args.lock,
                        manifests=args.extra_manifest)
    characters = view.characters()
    for logical in args.logical:
        view.read_raw(logical)
    view.verify()
    if args.write_lock:
        view.save_lock(args.write_lock)
    result = {"schema": "wf-view-summary/1", "tip": args.tip, "characters": len(characters),
              "character_ids": sorted(characters), "zip_count": len(view.zips),
              "overlay_member_count": len(view.index), "lock": view.lock_data(),
              "read_members": view.read_members}
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.json:
        target = local_output(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0
