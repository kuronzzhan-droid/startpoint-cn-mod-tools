"""Offline APK capability inspection; no build, install, or device access."""
import argparse
import json
from pathlib import Path

from wf.view.safety import local_output
from .provides import build_provides


def main(argv=None):
    parser = argparse.ArgumentParser(prog="wf apk")
    commands = parser.add_subparsers(dest="command", required=True)
    provides = commands.add_parser("provides", help="从 APK、SWF 或补丁摘要推导能力")
    provides.add_argument("source", type=Path)
    provides.add_argument("--output", "--out", "--json", dest="output", type=Path,
                          default=Path("work/m2/provides.json"))
    args = parser.parse_args(argv)
    target = local_output(args.output)
    document = build_provides(args.source)
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(text, end="")
    return int(bool(document["unresolved"]))


if __name__ == "__main__":
    raise SystemExit(main())
