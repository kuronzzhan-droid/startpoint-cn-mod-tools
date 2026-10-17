#!/usr/bin/env python3
"""Apply the approved Inaho R2 numbers to an isolated character package only."""
from __future__ import annotations

from wf.paths import root_path

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile

import wf_mod_tool as core

ABILITY = "master/ability/ability.orderedmap"
APPROVED_PACKAGE = Path(('${WF_ROOT}/startpoint-cn/work/character_packs/codex-r2-20260906/fox_oracle_autumn/package'.replace("${WF_ROOT}", str(root_path()))))
RESONANCE = ["2", "", "", "600000", "600000", "Yellow", ""]
# R1 installed package 1.4.765: exact CSV row fingerprints before/after R2.
KNOWN = {'1399952': [('21d8e2cae8ab096cb50f68c85ba6023f6166958c786788cd6751c67cc6eed736',
              '21d8e2cae8ab096cb50f68c85ba6023f6166958c786788cd6751c67cc6eed736',
              {})],
 '1399955': [('6500411925eba04974682418172a654209b7d3b86f77bc9cd7081c9aeccdccb5',
              'f653117d04aa57cc3cc0801598d62460984250c99847c25dbd2f22cb5db4c74e',
              {6: '2', 9: '600000', 10: '600000', 11: 'Yellow'}),
             ('dbc783e94a12a17cb99b5af8ad9dbfc948b3989caeccc7085dcdd8544d53c181',
              'c223f5c7f6cacda126a6285d7dcb1ca82b3878047f31fedb6edfb5a391eb887c',
              {6: '2', 9: '600000', 10: '600000', 11: 'Yellow'}),
             ('972bf3e37ac032e8cafc3a35fe8bf3658f9d3d31f9b0f0467741d38644f53dfe',
              '0812d791d22fba35ccbfee319279852982c8ba559ae5a08602a6538ca5252e79',
              {6: '2',
               9: '600000',
               10: '600000',
               11: 'Yellow',
               47: '695',
               48: '5',
               49: 'Yellow',
               51: '10000',
               52: '20000'})],
 '1399956': [('e24562dc9284a73b222663883715c48fb203db690445cb86ab42ad33c4ab3576',
              '09c7fc60195ad0ed4f9098399f3e7a59bccf2ca438883efa59769a0d3cd6dd8b',
              {6: '2', 9: '600000', 10: '600000', 11: 'Yellow'}),
             ('086314dda60f71c1aa3e09233d9cbbaa1bb584869d7a4d95ad0f963f20036dc9',
              '87c4d2188820be0b7bfb5ce34bf725e2b1c6051dfac7c4f5d95ef43871660ae1',
              {6: '2', 9: '600000', 10: '600000', 11: 'Yellow'})]}


def _digest(row: list[str]) -> str:
    return hashlib.sha256(core.write_csv_lines([row]).encode("utf-8")).hexdigest()


def _resonance(row: list[str]) -> None:
    if any(row[c:c + 7] == RESONANCE for c in (6, 13, 20)):
        return
    for c in (6, 13, 20):
        if row[c:c + 7] == ["0", "", "", "", "", "", ""]:
            row[c:c + 7] = RESONANCE
            return
    raise ValueError("no empty precondition slot for thunder resonance")


def _flip_row() -> list[str]:
    row = [""] * 126
    values = {0: "fox_oracle_autumn_2", 1: "true", 2: "attack_yellow", 3: "0",
              5: "0", 6: "12", 13: "0", 20: "0", 27: "6", 30: "100000",
              31: "100000", 34: "(None)", 35: "0", 39: "(None)", 46: "0",
              47: "226", 51: "250000", 52: "500000"}
    for column, value in values.items():
        row[column] = value
    return row


def revise_rows(rows: dict[str, list[list[str]]]) -> dict[str, list[list[str]]]:
    """Fingerprint known rows; preserve extras, ordering, unrelated keys and I354."""
    result = copy.deepcopy(rows)
    for key, specs in KNOWN.items():
        if key not in result or any(len(r) != 126 for r in result[key]):
            raise ValueError(f"missing key or unsupported row width: {key}")
        fingerprints = [_digest(r) for r in result[key]]
        for before, after, updates in specs:
            matches = [i for i, value in enumerate(fingerprints) if value in (before, after)]
            if len(matches) != 1:
                raise ValueError(f"known input fingerprint missing or duplicated: {key}/{before}")
            for column, value in updates.items():
                result[key][matches[0]][column] = value
    for key in ("1399955", "1399956"):
        for row in result[key]:
            _resonance(row)
    added = _flip_row()
    candidates = [row for row in result["1399952"] if row[27] == "6" and row[47] == "226"]
    if candidates and candidates != [added]:
        raise ValueError("unexpected existing BallFlip/AddCombo row")
    if not candidates:
        result["1399952"].append(added)
    return result


def _package(workspace: Path) -> Path:
    workspace = workspace.resolve(strict=True)
    package = workspace if (workspace / "manifest.json").is_file() else workspace / "package"
    package = package.resolve(strict=True)
    if package == APPROVED_PACKAGE:
        return package
    parts = {p.lower() for p in package.parts}
    if "codex_out" not in parts or parts & {"character_packs", "store", "asset-patch"}:
        raise ValueError("only the assigned R2 clone or an isolated codex_out package is accepted")
    return package


def _json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, path)
        if path.read_bytes() != data:
            raise OSError(f"write verification failed: {path}")
    finally:
        temporary.unlink(missing_ok=True)


def revise(workspace: Path, *, dry_run: bool = True) -> dict:
    package = _package(Path(workspace))
    table_path = (package / "roots/common" / ABILITY).resolve(strict=True)
    manifest_path = (package / "manifest.json").resolve(strict=True)
    if not all(p.is_relative_to(package) for p in (table_path, manifest_path)):
        raise ValueError("package input symlink escapes isolation")
    originals = {p: p.read_bytes() for p in (table_path, manifest_path)}
    manifest = json.loads(originals[manifest_path])
    if (manifest.get("character_id"), manifest.get("code_name")) != (139995, "fox_oracle_autumn"):
        raise ValueError("package identity must be Inaho 139995")
    table = core.read_orderedmap_file(table_path, ABILITY)
    before = table.text_rows()
    result = revise_rows({key: core.read_csv_lines(before[key]) for key in KNOWN})
    table.set_text_rows({key: core.write_csv_lines(value) for key, value in result.items()})
    data = core.build_orderedmap(table)
    claims = [x for x in manifest["roots"]["common"] if x["logical_path"] == ABILITY]
    if len(claims) != 1:
        raise ValueError("one ability root claim is required")
    original_data = originals[table_path]
    if (claims[0]["sha256"] != hashlib.sha256(original_data).hexdigest()
            or claims[0]["size"] != len(original_data)):
        raise ValueError("ability input does not match its manifest fingerprint")
    ownership = [x for x in manifest["tables"] if x["logical_path"] == ABILITY]
    if len(ownership) != 1 or not set(KNOWN) <= set(ownership[0]["outer_keys"]):
        raise ValueError("package does not own the three changed ability keys")
    claims[0].update(sha256=hashlib.sha256(data).hexdigest(), size=len(data))
    manifest["qa"]["release_ready"] = False
    manifest["qa"].pop("workspace_input_sha256", None)
    manifest.setdefault("snapshot", {})["inaho_numbers_r2"] = {
        "ability2": "Fever BallFlip combo 2.5 -> 5; original I354 retained",
        "ability5": "thunder resonance; independent ability 10 -> 20 percent replaces PF",
        "ability6": "thunder resonance; original skill Fever gain and Fever PF retained",
        "requires_reseal": True,
    }
    outputs = {table_path: data, manifest_path: _json(manifest)}
    changed = {p: value for p, value in outputs.items() if value != originals[p]}
    if not dry_run:
        if any(p.read_bytes() != value for p, value in originals.items()):
            raise ValueError("package input changed during preparation")
        for path, value in changed.items():
            _atomic_write(path, value)
    return {"package": str(package), "dry_run": dry_run,
            "changed": [str(p.relative_to(package)) for p in changed],
            "changed_keys": [key for key in KNOWN if before[key] != core.write_csv_lines(result[key])],
            "requires_reseal": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="write the isolated package (default: preview)")
    args = parser.parse_args()
    print(json.dumps(revise(args.workspace, dry_run=not args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
