#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fixed-input CLI for dry-run or confirmed formal package assembly."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

from wf_summer_thunder_package_compile import (
    ProductionInputs,
    compile_production_package,
)
from wf_summer_thunder_package_contract import (
    CONFIRMATION,
    PACKAGE_ID,
    PackageAssemblyError,
    PackageImage,
)
from wf_summer_thunder_package_workspace import execute_package


TOOL_ROOT = Path(__file__).resolve().parent


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="雷龙正式角色包：默认只读 dry-run；apply 使用固定确认词。"
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="写入固定 formal workspace（仍不写 store/CDN/server/device）",
    )
    parser.add_argument(
        "--confirm", metavar="PHRASE",
        help=f"--apply 必须逐字提供：{CONFIRMATION}",
    )
    return parser.parse_args(arguments)


def _git_head(tool_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tool_root,
        capture_output=True,
        text=True,
        check=False,
    )
    head = result.stdout.strip().lower()
    if result.returncode != 0 or len(head) != 40 or any(
        character not in "0123456789abcdef" for character in head
    ):
        raise PackageAssemblyError("cannot bind package to an exact generator git HEAD")
    return head


def _compile_fixed_image(tool_root: Path) -> PackageImage:
    build = tool_root / "work" / "builds" / PACKAGE_ID
    return compile_production_package(
        ProductionInputs(
            build_root=build,
            authoring_store=(
                tool_root / "work" / "stores" / f"{PACKAGE_ID}_current"
                / "production" / "upload"
            ),
            clean_release_store=(
                tool_root / "work" / "stores"
                / "cnmod_thunder_dragon_release_base" / "production" / "upload"
            ),
            server_shadow_assets=build / "server_shadow" / "assets",
        ),
        generator_git_head=_git_head(tool_root),
        package_version="1.0.0",
        requires_client_base="1.4.346",
    )


def run(arguments: argparse.Namespace) -> dict:
    if arguments.apply and arguments.confirm != CONFIRMATION:
        raise PackageAssemblyError(f"exact confirmation required: {CONFIRMATION}")
    if not arguments.apply and arguments.confirm is not None:
        raise PackageAssemblyError("--confirm is only valid together with --apply")
    root = Path(TOOL_ROOT)
    image = _compile_fixed_image(root)
    workspace = root / "work" / "character_packs" / PACKAGE_ID
    return execute_package(
        workspace,
        image,
        apply=bool(arguments.apply),
        confirmation=arguments.confirm,
    )


def main(arguments: Sequence[str] | None = None) -> int:
    try:
        report = run(parse_args(arguments))
    except PackageAssemblyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["TOOL_ROOT", "PACKAGE_ID", "parse_args", "run", "main"]
