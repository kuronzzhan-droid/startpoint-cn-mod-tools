#!/usr/bin/env python3
"""Install official knight + supporter PF into the assigned isolated Gerald package."""
from __future__ import annotations

from wf.paths import root_path

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

import wf_mod_tool as core
from wf_client_legality import client_legality_problems
from wf_gerald_native_pf_dsl import EFFECTS, SUFFIX, compose, encode

LEADER = "master/ability/leader_ability.orderedmap"
STRINGS = "master/string/custom_ability_string.orderedmap"
PF_TABLE = "master/skill/power_flip_action.orderedmap"
PF_KEY = "override_unicorn_lancer_rose_dual_pf"
STRING_KEY = "override_string_unicorn_lancer_rose_dual_pf"
PREVIOUS_DESCRIPTION = "剑士型强化弹射与辅助型强化弹射同时生效"
DESCRIPTION = "剑士型＋辅助型强化弹射同时生效。"
PROGRAMS = tuple(f"battle/action/power_flip/action/override/{PF_KEY}${PF_KEY}_lv{n}"
                 for n in (1, 2, 3))
LEADER_R2_HASH = "cc747217c7e26d30726c4ec31d9f13dadd57ed68f5cd7670d570bea23478cd88"
APPROVED_PACKAGE = Path(('${WF_ROOT}/startpoint-cn/work/character_packs/codex-r2-20260906/unicorn_lancer_rose/package'.replace("${WF_ROOT}", str(root_path()))))


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _path(package: Path, logical: str) -> Path:
    path = (package / "roots/common" / logical).resolve()
    if not path.is_relative_to(package):
        raise ValueError("logical path escapes package isolation")
    return path


def _override_row() -> list[str]:
    row = [""] * 124
    for index, value in {0: "unicorn_lancer_rose", 1: "0", 3: "0", 4: "0", 11: "0",
                         18: "0", 25: "0", 37: "(None)", 44: "0", 45: "722",
                         80: PF_KEY, 81: "1,2,3", 82: STRING_KEY}.items():
        row[index] = value
    problems = client_legality_problems("leader_ability", row)
    if problems:
        raise ValueError(f"invalid native PF override: {problems}")
    return row


def _asset_paths() -> set[str]:
    paths = set()
    for effect in {effect for effects in EFFECTS.values() for effect in effects}:
        paths.update(effect + suffix for suffix in (".parts.amf3.deflate", ".timeline.amf3.deflate"))
        family = effect.rsplit("/", 1)[0]
        texture = family + "/" + family.rsplit("/", 1)[1]
        paths.update((texture + ".png", texture + ".atlas.amf3.deflate"))
    return paths


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, path)
        if path.read_bytes() != data:
            raise OSError(f"write verification failed: {path}")
    finally:
        temporary.unlink(missing_ok=True)


def revise(workspace: Path, sources: Path, *, dry_run: bool = True) -> dict:
    workspace = Path(workspace).resolve(strict=True)
    package = workspace if (workspace / "manifest.json").is_file() else workspace / "package"
    package = package.resolve(strict=True)
    parts = {part.lower() for part in package.parts}
    if package != APPROVED_PACKAGE and ("codex_out" not in parts or
                                       parts & {"character_packs", "store", "asset-patch"}):
        raise ValueError("only the assigned R2 clone or isolated codex_out package is accepted")
    sources = Path(sources).resolve(strict=True)
    manifest_path = (package / "manifest.json").resolve(strict=True)
    if not manifest_path.is_relative_to(package):
        raise ValueError("manifest symlink escapes isolation")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    if (manifest.get("character_id"), manifest.get("code_name")) != (129992, "unicorn_lancer_rose"):
        raise ValueError("package must identify Gerald 129992")
    output: dict[str, bytes] = {}
    input_bytes: dict[Path, bytes | None] = {manifest_path: manifest_bytes}

    def table(logical: str) -> core.OrderedMap:
        path = _path(package, logical)
        if not path.exists():
            if logical != PF_TABLE:
                raise ValueError(f"missing existing table: {logical}")
            input_bytes[path] = None
            return core.OrderedMap(logical, [], [], path)
        raw = path.read_bytes()
        input_bytes[path] = raw
        claims = [entry for entry in manifest["roots"]["common"] if entry["logical_path"] == logical]
        if len(claims) != 1 or (claims[0]["sha256"], claims[0]["size"]) != (_hash(raw), len(raw)):
            raise ValueError(f"manifest input fingerprint mismatch: {logical}")
        return core.read_orderedmap_file(path, logical)

    leader = table(LEADER)
    rows = core.read_csv_lines(leader.text_rows()["129992"])
    if len(rows) not in (8, 9) or _hash(core.write_csv_lines(rows[:8]).encode()) != LEADER_R2_HASH:
        raise ValueError("Gerald R2 leader fingerprint drift")
    override = _override_row()
    if len(rows) == 9 and rows[8] != override:
        raise ValueError("unexpected existing Gerald PF override")
    if len(rows) == 8:
        rows.append(override)
    leader.set_text_rows({"129992": core.write_csv_lines(rows)})
    output[LEADER] = core.build_orderedmap(leader)
    for logical, key, value in ((STRINGS, STRING_KEY, DESCRIPTION),
                                (PF_TABLE, PF_KEY, core.write_csv_lines([list(PROGRAMS)]))):
        current = table(logical)
        existing = current.text_rows().get(key)
        previous_text = logical == STRINGS and existing == PREVIOUS_DESCRIPTION
        if existing is not None and existing != value and not previous_text:
            raise ValueError(f"private PF key already has unexpected content: {key}")
        current.set_text_rows({key: value})
        output[logical] = core.build_orderedmap(current)
        claims = [entry for entry in manifest["tables"] if entry["logical_path"] == logical]
        if not claims:
            claims = [{"codec_id": "flat", "inner_keys": [], "logical_path": logical,
                       "outer_keys": [], "root": "common", "semantic_claims": []}]
            manifest["tables"].extend(claims)
        if len(claims) != 1:
            raise ValueError(f"duplicate table ownership: {logical}")
        if key not in claims[0]["outer_keys"]:
            claims[0]["outer_keys"].append(key)
    for level, program in enumerate(PROGRAMS, 1):
        source_bytes = [(sources / f"{kind}_lv{level}{SUFFIX}").read_bytes()
                        for kind in ("knight", "supporter")]
        output[program + SUFFIX] = encode(compose(*source_bytes, level))
    asset_sources = json.loads((sources / "asset-sources.json").read_bytes())
    if set(asset_sources) != _asset_paths():
        raise ValueError("official effect snapshot closure mismatch")
    for logical, claim in asset_sources.items():
        path = (sources / "assets" / logical).resolve(strict=True)
        if not path.is_relative_to(sources):
            raise ValueError("official effect source escapes snapshot")
        raw = path.read_bytes()
        if (claim["sha256"], claim["size"]) != (_hash(raw), len(raw)):
            raise ValueError(f"official effect fingerprint mismatch: {logical}")
        output[logical] = raw
    for logical, raw in output.items():
        path = _path(package, logical)
        before = path.read_bytes() if path.exists() else None
        input_bytes.setdefault(path, before)
        if logical not in (LEADER, STRINGS, PF_TABLE) and before not in (None, raw):
            raise ValueError(f"refusing to overwrite differing PF asset: {logical}")
        claims = [entry for entry in manifest["roots"]["common"] if entry["logical_path"] == logical]
        if not claims:
            claims = [{"logical_path": logical}]
            manifest["roots"]["common"].extend(claims)
        if len(claims) != 1:
            raise ValueError(f"duplicate root claim: {logical}")
        claims[0].update(sha256=_hash(raw), size=len(raw))
    manifest["qa"]["release_ready"] = False
    manifest["qa"].pop("workspace_input_sha256", None)
    manifest.setdefault("snapshot", {})["gerald_native_pf_r2"] = {
        "key": PF_KEY, "programs": list(PROGRAMS), "base": "knight", "donor": "supporter",
        "official_values_preserved": True, "requires_reseal": True}
    changes = {_path(package, logical): data for logical, data in output.items()}
    changes[manifest_path] = _json(manifest)
    changes = {path: data for path, data in changes.items() if input_bytes[path] != data}
    if not dry_run:
        for path, raw in input_bytes.items():
            if (path.read_bytes() if path.exists() else None) != raw:
                raise ValueError("package input changed during preparation")
        for path, raw in changes.items():
            _atomic_write(path, raw)
    return {"package": str(package), "dry_run": dry_run,
            "changed": [str(path.relative_to(package)) for path in changes],
            "pf_key": PF_KEY, "requires_reseal": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(revise(args.workspace, args.sources, dry_run=not args.apply),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
