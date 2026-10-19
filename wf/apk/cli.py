"""Offline APK capability inspection; no build, install, or device access."""
import argparse
import json
from pathlib import Path

from wf.view.safety import local_output
from .provides import build_provides
from .kinds import inspect_profile


def main(argv=None):
    parser = argparse.ArgumentParser(prog="wf apk")
    commands = parser.add_subparsers(dest="command", required=True)
    provides = commands.add_parser("provides", help="从 APK、SWF 或补丁摘要推导能力")
    provides.add_argument("source", type=Path)
    provides.add_argument("--output", "--out", "--json", dest="output", type=Path,
                          default=Path("work/m2/provides.json"))
    kinds = commands.add_parser("kinds", help="从档案的实际 SWF 读取各能力表 kind 分支")
    kinds.add_argument("--profile", required=True)
    kinds.add_argument("--swf", type=Path, help="显式 SWF/APK 路径；仍校验所选档案 SWF 哈希")
    kinds.add_argument("--output", "--out", "--json", dest="output", type=Path,
                       help="可选 JSON 文件；省略时只输出到 stdout")
    register = commands.add_parser("register-local", help="实际SWF方法证据登记本地自用APK；非测试服包")
    register.add_argument("source", type=Path)
    register.add_argument("--profile", help="可选local-档案名；默认从v35文件名前缀读取")
    args = parser.parse_args(argv)
    target = local_output(args.output) if getattr(args, "output", None) else None
    try:
        if args.command == "register-local":
            from .register_local import register_local
            document = register_local(args.source, profile=args.profile)
            print(json.dumps(document, ensure_ascii=False, indent=2))
            return 0
        document = (inspect_profile(args.profile, swf=args.swf) if args.command == "kinds"
                    else build_provides(args.source))
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if target is not None:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    print(text, end="")
    return int(bool(document["mismatches"] if args.command == "kinds" else document["unresolved"]))


if __name__ == "__main__":
    raise SystemExit(main())
