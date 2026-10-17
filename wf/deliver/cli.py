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
    parser.add_argument("--pathlist", type=Path)
    args = parser.parse_args(argv)
    try:
        result = build_delivery(args.changeset, args.out or REPOSITORY / "work/m1/deliver" / args.changeset.stem,
            server_dir=args.server_dir, base_store=args.base_store, baseline_active=args.baseline_active,
            baseline_zips=args.baseline_zip, pathlist=args.pathlist)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f"wf deliver: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result["prepush"]["exit_code"] or 0)


if __name__ == "__main__":
    raise SystemExit(main())
