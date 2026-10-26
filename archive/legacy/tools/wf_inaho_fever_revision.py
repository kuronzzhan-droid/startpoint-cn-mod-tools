#!/usr/bin/env python3
"""Move Inaho's direct-hit combo into Fever ability 3 and trim ability 5.

Only the assigned isolated package or explicit codex_out fixtures are writable.
The publisher owns manifests; this module changes three outer ability keys only.
"""

from wf.paths import root_path
from copy import deepcopy
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

import wf_mod_tool as core
from wf_client_legality import client_legality_problems
from wf_quest_lib import parse_node

WORKSPACE = Path(('${WF_ROOT}/startpoint-cn/work/character_packs/inaho-fever-20260906/fox_oracle_autumn'.replace("${WF_ROOT}", str(root_path()))))
LOGICAL = "master/ability/ability.orderedmap"
KEYS = ("1399951", "1399953", "1399955")
HASHES = {
    "1399951": ("d6f837ddbaae945ad418c15aba657e30e6960cce15b3e71ffe6b4285b1e7822c",
                "bd5b31c1065bba95d0adaa353a9198af9e8f11a5dd0224357c1f0bd05e107898"),
    "1399953": ("4d7d06a3690004778d0bb1ce40bcb101143413d053009a481c6dcac8669616ba",
                "393cba110c315ca9763a97fc5516e8eba60b5eed1dff7fbd4bf48fbd323c2d80"),
    "1399955": ("d133c40f14454c64b36d6835a53b378ade31411923191493bc0f85757ce843dc",
                "a098b91cbe078ad826613992a58ebbc4fc195c30e5458221b275c6f505a4f577"),
}


def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode()).hexdigest()


def transform(texts):
    """Accept only the complete known original or completed three-key state."""
    if set(texts) != set(KEYS):
        raise ValueError("expected exactly Inaho ability keys 1, 3 and 5")
    hashes = {key: sha(texts[key]) for key in KEYS}
    if all(hashes[key] == HASHES[key][1] for key in KEYS):
        return dict(texts)
    if not all(hashes[key] == HASHES[key][0] for key in KEYS):
        raise ValueError("unknown or partially applied Inaho ability rows")
    rows = {key: core.read_csv_lines(texts[key]) for key in KEYS}
    original = deepcopy(rows)
    if tuple(len(rows[key]) for key in KEYS) != (3, 6, 3):
        raise ValueError("unexpected Inaho row counts")
    moved = rows["1399951"].pop(2)
    if (moved[27], moved[47], moved[51], moved[52]) != ("20", "226", "250000", "500000"):
        raise ValueError("expected growing direct-hit combo bonus")
    moved[0], moved[1] = "fox_oracle_autumn_3", "false"
    # Copy the entire native precondition block from ability 3's Fever dash.
    moved[6:27] = original["1399953"][-1][6:27]
    if moved[6] != "12":
        raise ValueError("expected native Fever precondition")
    rows["1399953"].append(moved)
    if tuple(row[47] for row in rows["1399955"]) != ("693", "118", "695"):
        raise ValueError("unexpected ability 5 damage terms")
    rows["1399955"].pop(0)
    rows["1399955"][0][51:53] = ["10000", "20000"]
    if rows["1399953"][:-1] != original["1399953"]:
        raise ValueError("existing ability 3 effect changed")
    result = {key: core.write_csv_lines(rows[key]) for key in KEYS}
    for key in KEYS:
        if sha(result[key]) != HASHES[key][1]:
            raise ValueError("unexpected Inaho revision output")
        for row in rows[key]:
            problems = client_legality_problems("ability", row)
            if problems:
                raise ValueError("; ".join(problems))
    return result


def _package(workspace):
    path = Path(workspace)
    if not (path / "manifest.json").is_file():
        path /= "package"
    package = path.resolve(strict=True)
    if package != WORKSPACE / "package":
        parts = {part.lower() for part in package.parts}
        if "codex_out" not in parts or parts & {"pkgarchive", "character_packs", "store", "asset-patch"}:
            raise ValueError("only assigned Inaho clone or isolated codex_out fixture is accepted")
    manifest = (package / "manifest.json").resolve(strict=True)
    if not manifest.is_relative_to(package):
        raise ValueError("manifest escapes package")
    identity = json.loads(manifest.read_bytes())
    if (identity.get("character_id"), identity.get("code_name")) != (139995, "fox_oracle_autumn"):
        raise ValueError("package identity must be Inaho 139995")
    return package


def _atomic(path, raw):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(raw)
    try:
        os.replace(temporary, path)
        if path.read_bytes() != raw:
            raise OSError("write readback failed")
    finally:
        temporary.unlink(missing_ok=True)


def revise(workspace=WORKSPACE, *, dry_run=True):
    package = _package(workspace)
    path = (package / "roots/common" / LOGICAL).resolve(strict=True)
    if not path.is_relative_to(package):
        raise ValueError("ability input escapes package")
    before = path.read_bytes()
    table = core.read_orderedmap_file(path, LOGICAL)
    original_keys, original_rows = list(table.keys), dict(zip(table.keys, table.rows))
    old_texts = table.text_rows()
    updates = transform({key: old_texts[key] for key in KEYS})
    changed = [key for key in KEYS if old_texts[key] != updates[key]]
    raw = before
    if changed:
        table.set_text_rows(updates)
        if list(table.keys) != original_keys:
            raise ValueError("outer ability keys changed")
        for key, row in zip(table.keys, table.rows):
            if key not in KEYS and row != original_rows[key]:
                raise ValueError("unowned outer ability row changed")
        raw = core.build_orderedmap(table)
        if parse_node(raw) != table.text_rows():
            raise ValueError("ability orderedmap roundtrip failed")
        if not dry_run:
            _atomic(path, raw)
    return {"dry_run": dry_run, "manifest_updated": False,
            "manifest_sha256": sha((package / "manifest.json").read_bytes()),
            "files": [{"code_name": "fox_oracle_autumn", "root": "common", "logical_path": LOGICAL,
                       "old_sha256": sha(before), "new_sha256": sha(raw), "size": len(raw),
                       "changed": raw != before, "changed_table_keys": changed, "new_table_keys": []}],
            "ability_row_counts": [2, 2, 7, 2, 2, 2], "direct_hit_combo_growth": [2.5, 5],
            "direct_hit_fever_only": True, "direct_hit_unisonable": False,
            "paralysis_stun_slayer_growth": [0.1, 0.2], "six_yellow_resonance_preserved": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=WORKSPACE)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = args.report.resolve() if args.report else None
    if report and "codex_out" not in {part.lower() for part in report.parts}:
        raise ValueError("report must stay in codex_out")
    payload = json.dumps(revise(args.workspace, dry_run=not args.apply), ensure_ascii=False, indent=2) + "\n"
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        _atomic(report, payload.encode())
    print(payload)


if __name__ == "__main__":
    main()
