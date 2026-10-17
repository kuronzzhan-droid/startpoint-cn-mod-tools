"""Build Inaho's native PF Lv3 Fever drain; emit shared-table suggestions only."""
from __future__ import annotations

from wf.paths import root_path

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zlib

import wf_dsl
import wf_mod_tool as core
from wf_client_legality import (
    action_dsl_element_problems, action_dsl_hit_area_target_problems,
    action_dsl_subject_binding_problems, client_legality_problems,
)
from wf_dsl_sig import COMMANDS

WORKSPACE = Path(('${WF_ROOT}/startpoint-cn/work/character_packs/inaho-fever-growth-20260906/fox_oracle_autumn'.replace("${WF_ROOT}", str(root_path()))))
OUTPUT = Path(('${WF_ROOT}/startpoint-cn/work/codex_out/inaho-fever-growth-20260906'.replace("${WF_ROOT}", str(root_path()))))
KEY = "ability_fox_oracle_autumn_drain"
PROGRAM = f"battle/action/skill/action/ability_skill/{KEY}${KEY}"
LOGICAL = PROGRAM + ".action.dsl.amf3.deflate"
TEXT = "Fever - 100"


def make_row() -> list[str]:
    """Native every-PF-Lv3 event; no cooldown, limit, resonance or main gate."""
    row = [""] * 126
    for column, value in {
        0: "fox_oracle_autumn_1", 1: "true", 2: "attack_yellow", 3: "0",
        5: "0", 6: "12", 13: "0", 20: "0", 27: "65",
        30: "100000", 31: "100000", 34: "(None)", 35: "0",
        39: "(None)", 46: "0", 47: "629", 70: KEY, 71: PROGRAM,
    }.items():
        row[column] = value
    problems = client_legality_problems("ability", row)
    if problems:
        raise ValueError("; ".join(problems))
    return row


def make_asset() -> tuple[bytes, list]:
    # Same full header as the existing Inaho ability action. Seven flags are false.
    # I629 passes SLvALv.Alv; equal min/max resolves to 100 at every ability level.
    tree = ["ActionDsl", 1, ["None"], *([False] * 7), 3,
            ["Block", [["Command", ["SubtractFeverPoint", [{"min": 100, "max": 100}]]]]]]
    commands = list(wf_dsl.iter_dsl_commands(tree))
    if (len(tree) != 12 or commands != [["SubtractFeverPoint", [{"min": 100, "max": 100}]]]
            or COMMANDS["SubtractFeverPoint"] != ["Array"]):
        raise ValueError("unexpected drain action structure")
    problems = (action_dsl_element_problems(tree, character_element=3)
                + action_dsl_subject_binding_problems(tree)
                + action_dsl_hit_area_target_problems(tree))
    if problems:
        raise ValueError("; ".join(problems))
    plain = wf_dsl.encode_amf3(tree)
    compressor = zlib.compressobj(level=9, wbits=-15)
    raw = compressor.compress(plain) + compressor.flush()
    if wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"] != tree:
        raise ValueError("drain action encode/decode mismatch")
    return raw, tree


def _write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(raw)
    try:
        os.replace(temporary, path)
        if path.read_bytes() != raw:
            raise OSError("write readback failed")
    finally:
        temporary.unlink(missing_ok=True)


def _json(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def build(*, apply: bool = False) -> dict:
    package = (WORKSPACE / "package").resolve(strict=True)
    manifest_path = package / "manifest.json"
    manifest_raw = manifest_path.read_bytes()
    identity = json.loads(manifest_raw)
    if (identity.get("character_id"), identity.get("code_name")) != (139995, "fox_oracle_autumn"):
        raise ValueError("expected the assigned Inaho package")
    path = (package / "roots/common" / LOGICAL).resolve()
    if not path.is_relative_to(package):
        raise ValueError("drain action escapes assigned package")
    raw, tree = make_asset()
    row = make_row()
    previous = path.read_bytes() if path.exists() else None
    if previous is not None and previous != raw:
        raise ValueError("existing drain action differs; refusing overwrite")
    if apply and previous is None:
        _write(path, raw)
    report = {
        "applied": apply, "manifest_updated": False, "shared_tables_updated": False,
        "file": {"root": "common", "logical_path": LOGICAL,
                 "sha256": hashlib.sha256(raw).hexdigest(), "size": len(raw),
                 "already_present": previous == raw},
        "checks": {"amf3_raw_deflate_roundtrip": True, "client_legality": True,
                   "exactly_one_command": True, "fixed_points_all_levels": 100,
                   "unisonable": True, "trigger": "Fever + PF Lv3, every 1 time",
                   "runtime_verified": False},
    }
    if apply and path.read_bytes() != raw:
        raise OSError("drain action final readback failed")
    if manifest_path.read_bytes() != manifest_raw:
        raise ValueError("manifest changed during isolated build")
    _write(OUTPUT / "drain-row.json", _json({"ability_key": "1399951", "append_row": row,
                                           "csv": core.write_csv_lines([row])}))
    _write(OUTPUT / "drain-strings.json", _json({KEY: TEXT}))
    _write(OUTPUT / "drain-action.json", _json(tree))
    _write(OUTPUT / ("drain-applied.json" if apply else "drain-dry-run.json"), _json(report))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    print(json.dumps(build(apply=parser.parse_args().apply), ensure_ascii=False, indent=2))
