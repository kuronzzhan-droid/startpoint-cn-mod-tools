#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Add the Abyss token to the ordinary battle-result reward table.

Rush clients treat a non-empty ``rush_battle_reward_list`` as a complete
folder clear. Per-round token display must therefore use the native
``drop_additional_reward_ids`` result channel instead.

Usage:
  python wf_rogue_token_result.py
  python wf_rogue_token_result.py --write
"""
from __future__ import annotations

import argparse
import copy
import json
import zipfile
from pathlib import Path

import wf_quest_lib as q
import wf_mod_tool as core
from wf.tools.rogue import rogue_reward_schedule as schedule


ADDITIONAL_REWARD_T = "master/reward/event/additional_reward.orderedmap"
ABYSS_TOKEN_ITEM_ID = 2370099
ABYSS_TOKEN_GROUP_ID = 237009900

ROOT = Path(__file__).resolve().parents[3]
ACTIVE_PATCH: Path | None = None
PATCH_MANIFEST: Path | None = None


def _archive_names(patch: dict) -> list[str]:
    chain = patch.get("chain")
    if isinstance(chain, list):
        return [str(name) for name in chain]
    archive = patch.get("archive")
    return [str(archive)] if archive else []


def load_effective_table() -> dict:
    """Load the newest enabled full-table payload, falling back to the store."""
    table = q.load_table(ADDITIONAL_REWARD_T)
    member = "production/upload/" + q.hashed_rel(ADDITIONAL_REWARD_T).replace("\\", "/")
    server = core.resolve_server_dir() if PATCH_MANIFEST is None or ACTIVE_PATCH is None else None
    manifest = PATCH_MANIFEST if PATCH_MANIFEST is not None else server / "assets/asset-patch/manifest.json"
    active = ACTIVE_PATCH if ACTIVE_PATCH is not None else server / "assets/asset-patch/active"
    if not manifest.is_file():
        return table

    document = json.loads(manifest.read_text(encoding="utf-8"))
    for patch in document.get("patches", []):
        if not patch.get("enabled"):
            continue
        for archive_name in _archive_names(patch):
            archive_path = active / archive_name
            if not archive_path.is_file():
                continue
            with zipfile.ZipFile(archive_path) as archive:
                if member not in archive.namelist():
                    continue
                parsed = q.parse_node(archive.read(member))
                if not isinstance(parsed, dict):
                    raise ValueError(f"{archive_name}:{member} is not an ordered map")
                table = parsed
    return table


def build_table(source: dict) -> dict:
    table = copy.deepcopy(source)
    key = str(ABYSS_TOKEN_GROUP_ID)
    expected = schedule.additional_reward_rows()
    existing = table.get(key)
    legacy = {"1": "abyss_token_result,0,2370099,5,1"}
    if existing is not None and existing not in (legacy, expected):
        raise ValueError(f"additional reward group {key} is already occupied: {existing!r}")
    table[key] = expected
    return table


def validate_table(table: dict) -> None:
    rows = table.get(str(ABYSS_TOKEN_GROUP_ID))
    if rows != schedule.additional_reward_rows():
        raise ValueError("Abyss independent reward-slot rows are missing or malformed")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install the per-round Abyss token ordinary-result reward row",
    )
    parser.add_argument("--write", action="store_true", help="write the effective table to the isolated store")
    args = parser.parse_args()

    source = load_effective_table()
    built = build_table(source)
    validate_table(built)
    print(
        f"{ADDITIONAL_REWARD_T}: {len(source)} -> {len(built)} groups; "
        f"group={ABYSS_TOKEN_GROUP_ID}, slots={len(schedule.additional_reward_rows())}",
    )
    if args.write:
        path = q.save_table(ADDITIONAL_REWARD_T, built)
        print(f"written: {path}")
    else:
        print("dry-run: pass --write to save")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
