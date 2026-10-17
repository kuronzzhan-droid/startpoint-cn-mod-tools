"""Prepare only Inaho's native Fever growth tables in the assigned clone."""
from __future__ import annotations

from wf.paths import root_path

import argparse
import json
import os
from pathlib import Path
import tempfile
import zlib

import wf_mod_tool as core
from wf_client_legality import client_legality_problems
import wf_inaho_fever_growth_data as data

BASE = Path(('${WF_ROOT}/startpoint-cn'.replace("${WF_ROOT}", str(root_path()))))
PACKAGE = BASE / "work/character_packs/inaho-fever-growth-20260906/fox_oracle_autumn/package"
OUTPUT = BASE / "work/codex_out/inaho-fever-growth-20260906/growth"


def atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(payload)
    try:
        os.replace(temporary, path)
        if path.read_bytes() != payload:
            raise OSError("written file failed readback")
    finally:
        temporary.unlink(missing_ok=True)


def _scope(package):
    package = Path(package).resolve(strict=True)
    if package != PACKAGE:
        raise ValueError("only the assigned Inaho growth clone may be changed")
    manifest_path = package / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    baseline = json.loads((OUTPUT.parent / "baseline.json").read_bytes())
    if (manifest["character_id"], manifest["code_name"]) != (139995, "fox_oracle_autumn"):
        raise ValueError("unexpected character identity")
    if data.sha(manifest_path.read_bytes()) != baseline["default_manifest_sha256"]:
        raise ValueError("root-owned manifest changed; do not rebuild the sealed package")
    return package


def _path(package, logical):
    path = (package / "roots/common" / logical).resolve()
    if not path.is_relative_to(package / "roots/common"):
        raise ValueError("resource path escapes the assigned clone")
    return path


def prepare(package=PACKAGE):
    package = _scope(package)
    tables, texts = {}, {}
    for logical, keys in data.OWNERS.items():
        table = core.read_orderedmap_file_raw_rows(_path(package, logical), logical)
        tables[logical] = table
        for key in keys:
            texts[key] = zlib.decompress(table.rows[table.keys.index(key)]).decode("utf-8")
    updates = data.transform(texts)
    already_applied = {key: data.sha(text) for key, text in texts.items()} == data.NEW
    tables[data.UNIQUE] = core.read_orderedmap_file_raw_rows(_path(package, data.UNIQUE), data.UNIQUE)
    unique = tables[data.UNIQUE]
    state_text = core.write_csv_lines([data.state_row()])
    if data.UNIQUE_ID in unique.keys:
        existing = zlib.decompress(unique.rows[unique.keys.index(data.UNIQUE_ID)]).decode("utf-8")
        if not already_applied or existing != state_text:
            raise ValueError("private UniqueCondition ID collision or partial input")
    elif already_applied:
        raise ValueError("growth rows exist without their UniqueCondition")
    files, claims = [], []
    for logical, table in tables.items():
        path = _path(package, logical)
        original_keys, original_rows = list(table.keys), list(table.rows)
        own = data.OWNERS.get(logical, (data.UNIQUE_ID,))
        for key in own:
            text = state_text if logical == data.UNIQUE else updates[key]
            if logical != data.UNIQUE:
                alias = "leader_ability" if logical == data.LEADER else "ability"
                for row in core.read_csv_lines(text):
                    errors = client_legality_problems(alias, row)
                    if errors:
                        raise ValueError("; ".join(errors))
            compressed = zlib.compress(text.encode("utf-8"))
            if key in table.keys:
                table.rows[table.keys.index(key)] = compressed
            else:
                table.keys.append(key)
                table.rows.append(compressed)
        payload = core.build_orderedmap_raw_rows(table)
        back = core.read_orderedmap_raw_rows_from_bytes(payload, logical)
        if back.keys != table.keys or back.rows != table.rows:
            raise ValueError("orderedmap byte roundtrip mismatch")
        for key, old_row in zip(original_keys, original_rows):
            if key not in own and back.rows[back.keys.index(key)] != old_row:
                raise ValueError("unowned compressed row changed")
        files.append((path, payload, logical))
        claims.append({"root": "common", "logical_path": logical, "keys": list(own),
                       "new_keys": [key for key in own if key not in original_keys],
                       "unowned_raw_rows_equal": True})
    icon = _path(package, data.ICON)
    image = _path(package, data.ICON_SOURCE).read_bytes()
    if icon.exists() and (not already_applied or icon.read_bytes() != image):
        raise ValueError("private state icon collision")
    files.append((icon, image, data.ICON))
    return files, claims, already_applied


def revise(package=PACKAGE, apply=False):
    files, claims, already_applied = prepare(package)
    records = []
    for path, payload, logical in files:
        before = path.read_bytes() if path.exists() else None
        records.append({"root": "common", "logical_path": logical,
                        "old_sha256": data.sha(before) if before is not None else None,
                        "new_sha256": data.sha(payload), "size": len(payload),
                        "changed": before != payload})
    if apply:
        for path, payload, _ in files:
            if not path.exists() or path.read_bytes() != payload:
                atomic(path, payload)
        # No package/manifest or other agents' resources are written here.
        _, _, complete = prepare(package)
        if not complete:
            raise ValueError("applied package did not return the completed state")
    return {"dry_run": not apply, "already_applied": already_applied,
            "files": records, "claims": claims, "manifest_updated": False,
            "new_unique_id": data.UNIQUE_ID, "seed": data.SEED, "cap": data.CAP,
            "client_legality_errors": [], "raw_roundtrip_equal": True,
            "alv_initial_values": data.simulate(0)[0]["alv_1_to_6"],
            "notes": ["FeverEnd grows integer stacks by floor(S/4).",
                      "Native descriptions may expose stack thresholds and counts.",
                      "Original leader/ability-6 gains use exclusive no-state fallback."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = revise(apply=args.apply)
    name = "applied.json" if args.apply else "dry-run.json"
    target = OUTPUT / name
    if not (args.apply and report["already_applied"] and target.exists()):
        atomic(target, (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    atomic(OUTPUT / "simulation.json", (json.dumps(data.simulate(), indent=2) + "\n").encode())
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
