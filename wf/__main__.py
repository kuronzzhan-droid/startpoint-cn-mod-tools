"""Unified offline command entry point: python -m wf <command>."""
import argparse
import importlib
import sys


def main(argv=None):
    values = list(sys.argv[1:] if argv is None else argv)
    commands = {"view": "wf.view.cli", "balance": "wf.balance.cli",
                "text": "wf.text.cli", "deliver": "wf.deliver.cli", "check": "wf.check",
                "caps": "wf.caps.cli", "apk": "wf.apk.cli"}
    if not values or values[0] in {"-h", "--help"}:
        parser = argparse.ArgumentParser(prog="wf", description="World Flipper 离线 MOD 工具")
        parser.add_argument("command", choices=commands)
        parser.print_help()
        return 0
    command, *arguments = values
    if command not in commands:
        print(f"未知子命令: {command}", file=sys.stderr)
        return 2
    try:
        return importlib.import_module(commands[command]).main(arguments)
    except (ValueError, OSError, KeyError) as error:
        print(f"问题: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
