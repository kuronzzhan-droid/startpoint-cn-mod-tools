#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fixed-input, dry-run-default abyss-gacha replacement assembler CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

import wf_abyss_gacha_package_compile as package_compile
import wf_abyss_gacha_package_contract as contract
import wf_abyss_gacha_package_sources as source_io
import wf_abyss_gacha_package_workspace as workspace_io


TOOL_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AssemblyPlan:
    source: contract.SealedSourcePackage
    additions: contract.AdditionBundle
    generator_git_head: str


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Thunder-dragon 1.1.0 plus abyss gacha replacement assembler; "
            "default is read-only dry-run"
        )
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="write only the fixed fresh formal workspace",
    )
    parser.add_argument(
        "--confirm", metavar="PHRASE",
        help=f"--apply requires exactly: {contract.CONFIRMATION}",
    )
    return parser.parse_args(arguments)


def _git_head(tool_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tool_root,
        capture_output=True, text=True, check=False,
    )
    head = result.stdout.strip().lower()
    if (
        result.returncode != 0
        or len(head) != 40
        or any(ch not in "0123456789abcdef" for ch in head)
    ):
        raise contract.PackageAssemblyError(
            "cannot bind package to an exact generator git HEAD"
        )
    return head


def _fixed_paths(tool_root: Path) -> tuple[Path, Path, Path, Path]:
    work = tool_root / "work"
    source = work / "character_packs" / contract.PACKAGE_ID
    store = (
        work / "stores" / "cnmod_abyss_gacha_release_base"
        / "production" / "upload"
    )
    server = tool_root.parent / "startpoint-cn" / "assets"
    output = work / "character_packs" / workspace_io.WORKSPACE_NAME
    return source, store, server, output


def _compile_fixed_plan(tool_root: Path) -> AssemblyPlan:
    source_path, store, server, _output = _fixed_paths(Path(tool_root))
    first_source = source_io.load_sealed_source_workspace(source_path)
    first_inputs = source_io.load_addition_sources(store, server)
    first_additions = package_compile.compile_additions(
        first_source, first_inputs
    )
    second_source = source_io.load_sealed_source_workspace(source_path)
    second_inputs = source_io.load_addition_sources(store, server)
    second_additions = package_compile.compile_additions(
        second_source, second_inputs
    )
    if first_source != second_source or first_additions != second_additions:
        raise contract.PackageAssemblyError(
            "production inputs changed during double-read compilation"
        )
    return AssemblyPlan(
        first_source, first_additions, _git_head(Path(tool_root))
    )


def _provisional_report(plan: AssemblyPlan, output: Path) -> dict:
    source_counts = {
        root: len(plan.source.roots[root]) for root in contract.ROOT_NAMES
    }
    addition_counts = {
        root: len(plan.additions.roots[root]) for root in contract.ROOT_NAMES
    }
    roots = {
        root: source_counts[root] + addition_counts[root]
        for root in contract.ROOT_NAMES
    }
    acceptance = plan.additions.acceptance
    drop_report = plan.additions.component_reports["drop"]
    accepted_asset_replacements = contract._accepted_asset_replacements(
        plan.additions.input_sha256,
        plan.additions.component_reports,
    )
    return {
        "status": "provisional_fail_closed",
        "integrity_ready": True,
        "apply_ready": False,
        "blockers": ["drop source sync runtime evidence is pending"],
        "payload_count": sum(roots.values()),
        "table_claim_count": (
            len(plan.source.manifest["tables"])
            + len(plan.additions.table_claims)
        ),
        "root_counts": roots,
        "old_payload_exact_count": sum(source_counts.values()),
        "new_payload_exact_count": sum(addition_counts.values()),
        "old_payloads_byte_exact": True,
        "new_paths_exact": True,
        "accepted_asset_replacements": accepted_asset_replacements,
        "all_references_closed": acceptance["all_references_closed"],
        "eight_character_closure": acceptance["eight_character_closure"],
        "ticket_contract_closed": acceptance["ticket_contract_closed"],
        "shop_contract_closed": acceptance["shop_contract_closed"],
        "drop_data_contract_closed": drop_report["drop_contract_closed"],
        "drop_source_sync_closed": acceptance["drop_source_sync_closed"],
        "art_contract_closed": acceptance["art_contract_closed"],
        "unresolved_art_payloads": acceptance["unresolved_art_payloads"],
        "input_sha256_count": len(plan.additions.input_sha256),
        "generator_git_head": plan.generator_git_head,
        "apply": False,
        "workspace": str(output),
        "formal_workspace_written": False,
        "writes_live": False,
    }


def run(arguments: argparse.Namespace) -> dict:
    if arguments.apply and arguments.confirm != contract.CONFIRMATION:
        raise contract.PackageAssemblyError(
            f"exact confirmation required: {contract.CONFIRMATION}"
        )
    if not arguments.apply and arguments.confirm is not None:
        raise contract.PackageAssemblyError(
            "--confirm is only valid together with --apply"
        )
    tool_root = Path(TOOL_ROOT)
    _source, _store, _server, output = _fixed_paths(tool_root)
    workspace_io.inspect_fresh_target(output)
    plan = _compile_fixed_plan(tool_root)
    if plan.additions.acceptance.get("drop_source_sync_closed") is not True:
        if arguments.apply:
            raise contract.PackageAssemblyError(
                "drop source sync runtime evidence is pending"
            )
        return _provisional_report(plan, output)
    image = contract.build_package_image(
        plan.source,
        plan.additions,
        generator_git_head=plan.generator_git_head,
    )
    return workspace_io.execute_fresh_workspace(
        output,
        image,
        apply=bool(arguments.apply),
        confirmation=arguments.confirm,
    )


def main(arguments: Sequence[str] | None = None) -> int:
    try:
        report = run(parse_args(arguments))
    except contract.PackageAssemblyError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "TOOL_ROOT", "AssemblyPlan", "parse_args", "run", "main",
]
