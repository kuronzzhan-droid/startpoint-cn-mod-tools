#!/usr/bin/env python3
"""Apply R3 balance edits only inside the two assigned isolated package clones."""

from wf.paths import root_path
import argparse
import json
import os
from pathlib import Path
import tempfile
import zlib

import wf_dsl
import wf_mod_tool as core
from wf_client_legality import client_legality_problems
from wf_newchars_r3_data import gerald_ability6, inaho_leader, inaho_power_flip, sha

BASE = Path(('${WF_ROOT}/startpoint-cn/work/character_packs/codex-r3-20260906'.replace("${WF_ROOT}", str(root_path()))))
ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
PF_ID = "override_fox_oracle_autumn_dual_pf"
PROGRAMS = tuple(f"battle/action/power_flip/action/override/{PF_ID}${PF_ID}_lv{level}"
                 ".action.dsl.amf3.deflate" for level in (1, 2, 3))


def _package(base, code, cid):
    package = (Path(base) / code / "package").resolve(strict=True)
    if package != (BASE / code / "package"):
        parts = {part.lower() for part in package.parts}
        if "codex_out" not in parts or parts & {"pkgarchive", "character_packs", "store", "asset-patch"}:
            raise ValueError("only assigned R3 clones or isolated codex_out fixtures are writable")
    manifest_path = (package / "manifest.json").resolve(strict=True)
    if not manifest_path.is_relative_to(package):
        raise ValueError("manifest escapes package")
    manifest = json.loads(manifest_path.read_bytes())
    if (manifest.get("character_id"), manifest.get("code_name")) != (cid, code):
        raise ValueError("package identity mismatch")
    return package


def _path(package, logical):
    path = (package / "roots/common" / logical).resolve(strict=True)
    if not path.is_relative_to(package):
        raise ValueError("package input escapes isolation")
    return path


def _atomic(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, path)
        if path.read_bytes() != data:
            raise OSError(f"write verification failed: {path}")
    finally:
        temporary.unlink(missing_ok=True)


def _encode(tree):
    encoder = zlib.compressobj(level=9, wbits=-15)
    return encoder.compress(wf_dsl.encode_amf3(tree)) + encoder.flush()


def revise(base=BASE, *, dry_run=True):
    output, report = {}, []
    for code, cid, logical, key, transform in (
            ("unicorn_lancer_rose", 129992, ABILITY, "1299926", gerald_ability6),
            ("fox_oracle_autumn", 139995, LEADER, "139995", inaho_leader)):
        package = _package(base, code, cid)
        target = _path(package, logical)
        table = core.read_orderedmap_file(target, logical)
        old_rows = table.text_rows()
        new_text = transform(old_rows[key])
        table_name = "ability" if logical == ABILITY else "leader_ability"
        for row in core.read_csv_lines(new_text):
            problems = client_legality_problems(table_name, row)
            if problems:
                raise ValueError("; ".join(problems))
        table.set_text_rows({key: new_text})
        raw = core.build_orderedmap(table)
        after_rows = table.text_rows()
        if any(after_rows[k] != value for k, value in old_rows.items() if k != key):
            raise ValueError("unowned table key changed")
        output[target] = (raw, code, logical, [key])
        if code == "fox_oracle_autumn":
            for level, program in enumerate(PROGRAMS, 1):
                path = _path(package, program)
                source = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]
                result = inaho_power_flip(source, level)
                # Preserve identical input bytes on an idempotent replay.
                raw = path.read_bytes() if result == source else _encode(result)
                output[path] = (raw, code, program, [])
    for path, (raw, code, logical, keys) in output.items():
        before = path.read_bytes()
        report.append({"code_name": code, "root": "common", "logical_path": logical,
                       "old_sha256": sha(before), "new_sha256": sha(raw), "size": len(raw),
                       "changed": raw != before, "changed_table_keys": keys,
                       "new_table_keys": []})
    # Compute and validate all five files before any write; manifests belong to
    # the coordinating publisher and are deliberately never changed here.
    if not dry_run:
        for path, (raw, _, _, _) in output.items():
            if path.read_bytes() != raw:
                _atomic(path, raw)
    return {"dry_run": dry_run, "files": report, "manifest_updated": False,
            "new_table_keys": [], "special_scale": 1.25, "special_damage_factor": 0.75,
            "special_radii": [250, 312.5, 437.5], "leader_lv3_combo_increase": 9,
            "gerald_ability6_leader_only": True, "gerald_ability6_cooldown_frames": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=BASE)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = None
    if args.report:
        report = args.report.resolve()
        if "codex_out" not in {part.lower() for part in report.parts}:
            raise ValueError("report must stay in codex_out")
    result = revise(args.base, dry_run=not args.apply)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if report:
        report.parent.mkdir(parents=True, exist_ok=True)
        _atomic(report, payload.encode())
    print(payload)


if __name__ == "__main__":
    main()
