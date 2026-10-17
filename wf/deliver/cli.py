"""CLI for packaging a validated local change set."""
import argparse
import json
from pathlib import Path

from wf.paths import REPOSITORY
from .build import build_delivery


def main(argv=None):
    parser = argparse.ArgumentParser(prog="wf deliver", description="从变更集生成本地交付并自动 prepush --since")
    parser.add_argument("changeset", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--server-dir", type=Path, help="只读服务端 JSON 参考目录；不会启动或写入服务")
    parser.add_argument("--base-store", type=Path)
    parser.add_argument("--baseline-active", type=Path)
    parser.add_argument("--baseline-zip", type=Path, action="append", default=[])
    parser.add_argument("--baseline-manifest", type=Path, help="只读主清单；必须尚未占用目标版本")
    parser.add_argument("--baseline-manifest-extra", type=Path, action="append", default=[])
    parser.add_argument("--baseline-zip-dir", type=Path, action="append", default=[])
    parser.add_argument("--base-version", default="1.4.131")
    parser.add_argument("--view-lock", type=Path)
    parser.add_argument("--no-baseline-i-know", action="store_true", help="显式放弃缺失的客户端基线检查并留痕；不豁免服务端摘要或 DSL 门禁")
    parser.add_argument("--pathlist", type=Path)
    args = parser.parse_args(argv)
    try:
        result = build_delivery(args.changeset, args.out or REPOSITORY / "work/m1/deliver" / args.changeset.stem,
            server_dir=args.server_dir, base_store=args.base_store, baseline_active=args.baseline_active,
            baseline_zips=args.baseline_zip, pathlist=args.pathlist,
            baseline_manifest=args.baseline_manifest, baseline_manifests=args.baseline_manifest_extra,
            baseline_zip_dirs=args.baseline_zip_dir, base_version=args.base_version,
            view_lock=args.view_lock, no_baseline_i_know=args.no_baseline_i_know)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"wf deliver: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result["prepush"]["exit_code"] or 0)


if __name__ == "__main__":
    raise SystemExit(main())
