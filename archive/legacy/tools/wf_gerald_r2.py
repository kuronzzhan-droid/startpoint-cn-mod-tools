#!/usr/bin/env python3
"""Apply the authorized Gerald R2 revision only to an isolated character package."""
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
import wf_gerald_r2_data as data

ABILITY = "master/ability/ability.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
TEXT = "master/character/character_text.orderedmap"
STRINGS = "master/string/custom_ability_string.orderedmap"
UNIQUE = "master/character/unique_condition.orderedmap"
ACTION = "master/skill/action_skill.orderedmap"
SERVER_TEXT = "cdndata/character_text.json"
MAIN = tuple("battle/action/skill/action/rare5/"
             f"unicorn_lancer_rose$unicorn_lancer_rose_{level}.action.dsl.amf3.deflate"
             for level in (1, 2))
INPUTS = tuple(("common", p) for p in (ABILITY, LEADER, TEXT, STRINGS, UNIQUE, ACTION, *MAIN)) + (
    ("server", SERVER_TEXT),)
APPROVED_PACKAGE = Path(('${WF_ROOT}/startpoint-cn/work/character_packs/codex-r2-20260906/unicorn_lancer_rose/package'.replace("${WF_ROOT}", str(root_path()))))


def _package(workspace: Path) -> Path:
    workspace = workspace.resolve(strict=True)
    package = workspace if (workspace / "manifest.json").is_file() else workspace / "package"
    package = package.resolve(strict=True)
    if package == APPROVED_PACKAGE:
        return package
    parts = {p.lower() for p in package.parts}
    if "codex_out" not in parts or parts & {"character_packs", "store", "asset-patch"}:
        raise ValueError("only the assigned clone or isolated codex_out package is accepted")
    return package


def _json(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _atomic_write(path: Path, content: bytes):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        os.replace(temporary, path)
        if path.read_bytes() != content:
            raise OSError(f"write verification failed: {path}")
    finally:
        temporary.unlink(missing_ok=True)


def revise(workspace: Path, *, dry_run: bool) -> dict:
    package = _package(Path(workspace))
    manifest_path = (package / "manifest.json").resolve(strict=True)
    if not manifest_path.is_relative_to(package):
        raise ValueError("manifest escapes isolated package")
    manifest = json.loads(manifest_path.read_bytes())
    if (manifest.get("character_id"), manifest.get("code_name")) != (129992, "unicorn_lancer_rose"):
        raise ValueError("package must identify Gerald 129992")
    paths = {}
    claims = {}
    for root, logical in INPUTS:
        path = (package / "roots" / root / logical).resolve(strict=True)
        if not path.is_relative_to(package):
            raise ValueError("input symlink escapes isolated package")
        claim, = [r for r in manifest["roots"][root] if r["logical_path"] == logical]
        raw = path.read_bytes()
        if (claim["sha256"], claim["size"]) != (hashlib.sha256(raw).hexdigest(), len(raw)):
            raise ValueError(f"manifest hash mismatch: {logical}")
        paths[root, logical], claims[root, logical] = path, claim
    output = {}
    for logical, key, transform in ((LEADER, "129992", data.leader),
            (ABILITY, "1299922", data.ability2), (TEXT, "129992", data.character_text),
            (STRINGS, "change_skill_unicorn_lancer_rose", data.ability3)):
        path = paths["common", logical]
        table = core.read_orderedmap_file(path, logical)
        table.set_text_rows({key: transform(table.text_rows()[key])})
        output[path] = core.build_orderedmap(table)
    # The native Unique already forces application and rejects cancellation.
    table = core.read_orderedmap_file(paths["common", UNIQUE], UNIQUE)
    unique, = core.read_csv_lines(table.text_rows()["129992"])
    if unique[9:11] != ["false", "true"]:
        raise ValueError("Duel is no longer force-applied and non-cancelable")
    path = paths["common", ACTION]
    table = core.read_orderedmap_file_raw_rows(path, ACTION)
    index = table.keys.index("unicorn_lancer_rose")
    entries = core.decode_action_skill_row(table.rows[index])
    if {key for key, _ in entries} != {"1", "2"}:
        raise ValueError("unexpected Gerald action skill levels")
    for key, row in entries:
        row[1] = data.description(row[1], key)
    table.rows[index] = core.encode_action_skill_row(entries)
    output[path] = core.build_orderedmap_raw_rows(table)
    path = paths["server", SERVER_TEXT]
    server = json.loads(path.read_bytes())
    row, = server["129992"]
    server["129992"] = core.read_csv_lines(data.character_text(core.write_csv_lines([row])))
    output[path] = _json(server)
    for level, logical in enumerate(MAIN, 1):
        path = paths["common", logical]
        source = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]
        tree = data.revise_tree(source, str(level))
        compressor = zlib.compressobj(level=9, wbits=-15)
        output[path] = compressor.compress(wf_dsl.encode_amf3(tree)) + compressor.flush()
    for key, path in paths.items():
        if path in output:
            claims[key].update(sha256=hashlib.sha256(output[path]).hexdigest(), size=len(output[path]))
    manifest["package_version"] = "0.1.3"
    manifest["qa"].update(release_ready=False, workspace_input_sha256="")
    manifest.setdefault("snapshot", {})["gerald_r2"] = {
        "version": 2, "native_combo_bonus": True, "max_skill_base_multiplier": 90,
        "duel_separated_term_kind": 721, "duel_force_apply": True,
        "duel_cancelable": False, "self_flying_frames": 1200,
        "ability4_gauge_unlimited_preserved": True, "requires_reseal": True,
    }
    output[manifest_path] = _json(manifest)
    changed = {path: content for path, content in output.items() if path.read_bytes() != content}
    if not dry_run:
        for path, content in changed.items():
            _atomic_write(path, content)
    return {"package": str(package), "dry_run": dry_run, "requires_reseal": True,
            "changed": [str(p.relative_to(package)).replace("\\", "/") for p in changed]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(revise(args.workspace, dry_run=args.dry_run), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
