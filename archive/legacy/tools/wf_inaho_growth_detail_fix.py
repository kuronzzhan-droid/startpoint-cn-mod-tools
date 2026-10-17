"""Repair Inaho C10010 only in the assigned isolated character package."""

from wf.paths import root_path
import argparse
import json
import os
from pathlib import Path
import tempfile
import zlib

import wf_mod_tool as core
import wf_inaho_growth_detail_data as data

BASE = Path(('${WF_ROOT}/startpoint-cn'.replace("${WF_ROOT}", str(root_path()))))
PACKAGE = BASE / "work/character_packs/inaho-detail-c10010-20260906/fox_oracle_autumn/package"
OUTPUT = BASE / "work/codex_out/inaho-detail-c10010-20260906/fix"


def atomic(path, raw):
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


def prepare(package=PACKAGE):
    package = Path(package).resolve(strict=True)
    if package != PACKAGE:
        raise ValueError("only the assigned Inaho detail clone is accepted")
    manifest = (package / "manifest.json").read_bytes()
    baseline = json.loads((OUTPUT.parent / "baseline.json").read_bytes())
    if data.sha(manifest) != baseline["default_manifest_sha256"]:
        raise ValueError("root-owned manifest changed; do not rebuild a sealed package")
    identity = json.loads(manifest)
    if (identity["character_id"], identity["code_name"]) != (139995, "fox_oracle_autumn"):
        raise ValueError("unexpected character")
    tables, texts = {}, {}
    for logical, keys in data.OWNERS.items():
        path = (package / "roots/common" / logical).resolve(strict=True)
        if not path.is_relative_to(package / "roots/common"):
            raise ValueError("table escapes package")
        table = core.read_orderedmap_file_raw_rows(path, logical)
        tables[logical] = table
        for key in keys:
            texts[key] = zlib.decompress(table.rows[table.keys.index(key)]).decode()
    updates = data.transform(texts)
    completed = {key: data.sha(text) for key, text in texts.items()} == data.NEW
    files, claims = [], []
    for logical, table in tables.items():
        before = dict(zip(table.keys, table.rows))
        for key in data.OWNERS[logical]:
            table.rows[table.keys.index(key)] = zlib.compress(updates[key].encode())
        raw = core.build_orderedmap_raw_rows(table)
        back = core.read_orderedmap_raw_rows_from_bytes(raw, logical)
        assert back.keys == table.keys and back.rows == table.rows
        assert all(back.rows[back.keys.index(key)] == value for key, value in before.items()
                   if key not in data.OWNERS[logical])
        files.append((package / "roots/common" / logical, raw, logical))
        claims.append({"root": "common", "logical_path": logical,
                       "keys": list(data.OWNERS[logical]), "unowned_raw_rows_equal": True})
    raw, _ = data.asset()
    dsl_path = (package / "roots/common" / data.DSL).resolve()
    if not dsl_path.is_relative_to(package / "roots/common"):
        raise ValueError("DSL escapes package")
    if dsl_path.exists() and (not completed or dsl_path.read_bytes() != raw):
        raise ValueError("new DSL collision or partial package")
    if completed and not dsl_path.exists():
        raise ValueError("fixed ability row exists without its DSL")
    files.append((dsl_path, raw, data.DSL))
    return files, claims, completed


def revise(apply=False):
    files, claims, completed = prepare()
    records = []
    for path, raw, logical in files:
        old = path.read_bytes() if path.exists() else None
        records.append({"root": "common", "logical_path": logical,
                        "old_sha256": data.sha(old) if old is not None else None,
                        "new_sha256": data.sha(raw), "size": len(raw), "changed": old != raw})
    if apply:
        for path, raw, _ in files:
            if not path.exists() or path.read_bytes() != raw:
                atomic(path, raw)
        assert prepare()[2]
    return {"dry_run": not apply, "already_applied": completed, "files": records,
            "table_claims": claims, "custom_string_key": data.KEY,
            "custom_string_written": False, "manifest_written": False,
            "old_row_hashes": data.OLD, "new_row_hashes": data.NEW,
            "raw_roundtrip": True, "native_legality_passed": True,
            "growth_formula": "min(1000000000,S+floor(S/4))",
            "gain_limits": {"pf3": data.CAP // 210, "ability6": data.CAP // 120,
                            "leader": data.CAP // 280}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    report = revise(args.apply)
    target = OUTPUT / ("applied.json" if args.apply else "dry-run.json")
    if not (args.apply and report["already_applied"] and target.exists()):
        atomic(target, (json.dumps(report, indent=2) + "\n").encode())
    print(json.dumps(report))


if __name__ == "__main__":
    main()
