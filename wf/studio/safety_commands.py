"""Standalone bundle/key checks for studio and external builders."""
from __future__ import annotations

import argparse
from pathlib import Path


def add_commands(sub):
    parser = sub.add_parser("bundle-check", help="核对交付表与 APK 内置表撞名（C7051）")
    parser.add_argument("--apk", type=Path, action="append", required=True)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--zip", type=Path, action="append", nargs="+", default=[])
    inputs.add_argument("--delivery-dir", type=Path)
    parser = sub.add_parser("key-diff", help="对命名基线视图列出交付共享表键级差异")
    parser.add_argument("--view", dest="view_name", default=argparse.SUPPRESS)
    parser.add_argument("--tip", default=argparse.SUPPRESS)
    parser.add_argument("--zip", type=Path, action="append", required=True)
    parser.add_argument("--subject", help="主体角色 ID；缺少归属证据时标 unknown")
    parser.add_argument("--md", type=Path, help="输出完整中文对键清单")


def run(args):
    if args.command == "bundle-check":
        from .bundle_keys import check_bundle_keys
        return check_bundle_keys(args.apk, zips=[p for group in args.zip for p in group],
                                 delivery_dir=args.delivery_dir)
    from .key_diff import compare_delivery, markdown
    from .view_commands import source_from_args
    if not getattr(args, "view_name", None):
        raise ValueError("key-diff 需要 --view 命名基线视图")
    source = source_from_args(args)
    report = compare_delivery(source.view, args.zip, subject=args.subject)
    source.view.verify()
    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(markdown(report), "utf-8")
    return report
