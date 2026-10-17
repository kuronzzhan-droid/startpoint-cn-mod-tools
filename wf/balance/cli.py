"""CLI adapter; every write stays in the current tools checkout."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from wf.paths import REPOSITORY
from wf.view.safety import restrict_writes
from .engine import apply_recipe
from .inputs import open_inputs
from .output import write_result
from .recipe import load_recipe


def main(argv=None):
    parser = argparse.ArgumentParser(prog="wf balance", description="执行逐格旧值断言的 YAML 平衡配方")
    parser.add_argument("recipe", type=Path)
    parser.add_argument("--write", action="store_true", help="写入本 worktree 的变更集和历史验收 ZIP")
    parser.add_argument("--output", type=Path, help="输出目录，默认 work/m1/balance/<配方ID>")
    args = parser.parse_args(argv)
    restrict_writes()
    try:
        recipe = load_recipe(args.recipe)
        view, verify = open_inputs(recipe, args.recipe.resolve())
        result = apply_recipe(recipe, view)
        verification = verify()
        report = {"status": "满足", "mode": "dry-run", "members": len(result.files),
                  "touched_keys": result.touched_keys, "operations": len(result.changes)}
        if args.write:
            output = args.output or REPOSITORY / "work/m1/balance" / recipe["id"]
            report = write_result(recipe, result, output, verification)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError) as error:
        print(json.dumps({"status": "问题", "message": str(error)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
