#!/usr/bin/env python3
"""Add Inaho's native special+ranged PF to an isolated package, never live stores."""
from __future__ import annotations

from wf.paths import root_path

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import zipfile
import zlib

import wf_dsl
import wf_mod_tool as core
from wf_client_legality import client_legality_problems
from wf_native_pf_r2_dsl import SOURCE_HASHES, compose, private_path, private_references

PF_ID = "override_fox_oracle_autumn_dual_pf"
STRING_ID = "override_string_fox_oracle_autumn_dual_pf"
CAPABILITY = "kyubi-pf-initial-combo-v1"
PREVIOUS_DESCRIPTION = ("强化弹射时，同时发动射击型与特殊型强化弹射；特殊型强化弹射在撞击敌人后"
                        "产生球形范围攻击／FEVER模式中，雷属性共鸣且本次弹射前连击达到35以上时，"
                        "特殊型强化弹射的攻击次数增加")
DESCRIPTION = ("射击型＋特殊型强化弹射同时生效。Fever中，雷属性共鸣且弹射前达到35连击时，"
               "特殊型攻击次数增加。")
SUFFIX = ".action.dsl.amf3.deflate"
PROGRAMS = tuple(f"battle/action/power_flip/action/override/{PF_ID}${PF_ID}_lv{lv}"
                 for lv in (1, 2, 3))
PF_TABLE = "master/skill/power_flip_action.orderedmap"
LEADER = "master/ability/leader_ability.orderedmap"
ABILITY = "master/ability/ability.orderedmap"
STRINGS = "master/string/custom_ability_string.orderedmap"
APPROVED_PACKAGE = Path(('${WF_ROOT}/startpoint-cn/work/character_packs/codex-r2-20260906/fox_oracle_autumn/package'.replace("${WF_ROOT}", str(root_path()))))
LEADER_BASE = "b038084026a4836c01f3b0165a76c89c5d1aa2107bc29b678094197f8a7342ac"
ABILITY_BASE = "f5bc1b86f4f1267a047a466142486993ee7d7ecbcdf092f960e2d535568891ed"
ABILITY_AFTER = "4d7d06a3690004778d0bb1ce40bcb101143413d053009a481c6dcac8669616ba"


def sha(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


def _safe_package(workspace):
    package = Path(workspace)
    if not (package / "manifest.json").is_file():
        package /= "package"
    package = package.resolve(strict=True)
    if package != APPROVED_PACKAGE:
        parts = {p.lower() for p in package.parts}
        if "codex_out" not in parts or parts & {"character_packs", "pkgarchive", "store", "asset-patch"}:
            raise ValueError("only the approved R2 clone or a codex_out fixture is writable")
    return package


def _path(package, logical):
    path = (package / "roots/common" / logical).resolve()
    if not path.is_relative_to(package):
        raise ValueError("package output escapes through a symlink")
    return path


def load_sources(store, apk):
    """Read known official source bytes; these paths are never write targets."""
    with zipfile.ZipFile(apk) as archive:
        bundle = zipfile.ZipFile(io.BytesIO(archive.read("assets/bundle.zip")))
    sources = {}
    for (kind, level), expected in SOURCE_HASHES.items():
        logical = wf_dsl.dsl_logical(f"battle/action/power_flip/action/{kind}${kind}_lv{level}")
        digest = core.sha1_path(logical)
        path = Path(store) / digest[:2] / digest[2:]
        if path.exists():
            raw = path.read_bytes()
        else:
            matches = [n for n in bundle.namelist() if n.endswith(digest[:2] + "/" + digest[2:])]
            if len(matches) != 1:
                raise ValueError(f"missing or ambiguous official source: {logical}")
            raw = bundle.read(matches[0])
        if sha(raw) != expected:
            raise ValueError(f"official source drift: {logical}")
        sources[kind, level] = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
    return sources


def load_effects(effects, store, apk):
    """Materialize both stock effect families so the package is self-contained."""
    logicals = set()
    for effect in effects:
        parent = effect.rsplit("/", 1)[0]
        if parent not in {"battle/effect/powerflip/effect_powerflip_attack_special",
                          "battle/effect/powerflip/effect_powerflip_attack_beam"}:
            raise ValueError(f"unexpected native PF effect family: {effect}")
        logicals.update(effect + suffix for suffix in (".parts.amf3.deflate", ".timeline.amf3.deflate"))
        atlas = parent + "/" + parent.rsplit("/", 1)[1]
        logicals.update((atlas + ".png", atlas + ".atlas.amf3.deflate"))
    with zipfile.ZipFile(apk) as archive:
        bundle = zipfile.ZipFile(io.BytesIO(archive.read("assets/bundle.zip")))
    output = {}
    for logical in sorted(logicals):
        digest = core.sha1_path(logical)
        source = Path(store) / digest[:2] / digest[2:]
        if source.exists():
            output[logical] = source.read_bytes()
        else:
            matches = [n for n in bundle.namelist() if n.endswith(digest[:2] + "/" + digest[2:])]
            if len(matches) != 1:
                raise ValueError(f"missing or ambiguous native PF effect asset: {logical}")
            output[logical] = bundle.read(matches[0])
    return output


def _leader(table):
    row = [""] * 124
    values = {0: "fox_oracle_autumn", 1: "0", 3: "0", 4: "0", 11: "0", 18: "0",
              25: "0", 37: "(None)", 44: "0", 45: "722", 80: PF_ID,
              81: "1,2,3", 82: STRING_ID}
    for index, value in values.items():
        row[index] = value
    problems = client_legality_problems("leader_ability", row)
    if problems:
        raise ValueError("; ".join(problems))
    rows = core.read_csv_lines(table.text_rows()["139995"])
    if rows[-1] == row:
        rows.pop()
    if sha(core.write_csv_lines(rows)) != LEADER_BASE:
        raise ValueError("unrecognized Inaho leader rows")
    table.set_text_rows({"139995": core.write_csv_lines(rows + [row])})


def _remove_old_629(table):
    rows = core.read_csv_lines(table.text_rows()["1399953"])
    # The exact six surviving rows are validated by reconstructing the known
    # original key, allowing an idempotent replay without touching other slots.
    if len(rows) == 7:
        if sha(core.write_csv_lines(rows)) != ABILITY_BASE:
            raise ValueError("unrecognized Inaho ability 3")
        rows.pop(0)
    if sha(core.write_csv_lines(rows)) != ABILITY_AFTER:
        raise ValueError("unrecognized remaining ability 3 rows")
    table.set_text_rows({"1399953": core.write_csv_lines(rows)})


def _atomic(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(payload)
    try:
        os.replace(temporary, path)
        if path.read_bytes() != payload:
            raise OSError(f"readback failed: {path}")
    finally:
        temporary.unlink(missing_ok=True)


def _encode(tree):
    encoder = zlib.compressobj(level=9, wbits=-15)
    return encoder.compress(wf_dsl.encode_amf3(tree)) + encoder.flush()


def _private_asset(logical, raw):
    if logical.endswith(".png"):
        return raw
    tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
    converted = private_references(tree)
    # Timelines contain only the unchanged official sound/timing data.
    return raw if converted == tree else _encode(converted)


def revise(workspace, store, apk, *, dry_run):
    package = _safe_package(workspace)
    manifest_path = (package / "manifest.json").resolve(strict=True)
    if not manifest_path.is_relative_to(package):
        raise ValueError("manifest symlink escapes package")
    manifest = json.loads(manifest_path.read_bytes())
    if (manifest.get("character_id"), manifest.get("code_name")) != (139995, "fox_oracle_autumn"):
        raise ValueError("package must be Inaho 139995")
    sources = load_sources(store, apk)
    output = {}
    effects = set()
    for level, program in enumerate(PROGRAMS, 1):
        tree = compose(sources["special", level], sources["ranged", level], level)
        legacy_raw = _encode(tree)
        raw = _encode(private_references(tree))
        target = _path(package, program + SUFFIX)
        if target.exists() and target.read_bytes() not in (legacy_raw, raw):
            raise ValueError(f"existing private PF differs from expected result: {program}")
        output[target] = raw
        effects.update(e[2][1] for e in wf_dsl.iter_dsl_commands(tree, "ShowEffect"))
    effect_assets = load_effects(effects, store, apk)
    removed = []
    for logical, raw in effect_assets.items():
        shared = _path(package, logical)
        claims = [e for e in manifest["roots"]["common"] if e["logical_path"] == logical]
        if shared.exists() or claims:
            if (len(claims) != 1 or not shared.exists() or shared.read_bytes() != raw
                    or (claims[0]["sha256"], claims[0]["size"]) != (sha(raw), len(raw))):
                raise ValueError(f"unknown shared FX copy cannot be migrated: {logical}")
            removed.append(shared)
        target = _path(package, private_path(logical))
        converted = _private_asset(logical, raw)
        if target.exists() and target.read_bytes() != converted:
            raise ValueError(f"existing private effect asset differs: {logical}")
        output[target] = converted
    manifest["roots"]["common"] = [e for e in manifest["roots"]["common"]
                                    if e["logical_path"] not in effect_assets]
    for logical in (LEADER, ABILITY, STRINGS, PF_TABLE):
        target = _path(package, logical)
        source = target
        if logical == PF_TABLE and not source.exists():
            digest = core.sha1_path(logical)
            source = Path(store) / digest[:2] / digest[2:]
        table = core.read_orderedmap_file(source, logical)
        if logical == LEADER:
            _leader(table)
        elif logical == ABILITY:
            _remove_old_629(table)
        else:
            key, text = ((STRING_ID, DESCRIPTION) if logical == STRINGS else
                         (PF_ID, core.write_csv_lines([list(PROGRAMS)])))
            existing = table.text_rows().get(key)
            previous_text = logical == STRINGS and existing == PREVIOUS_DESCRIPTION
            if existing is not None and existing != text and not previous_text:
                raise ValueError(f"existing private table key differs: {logical}/{key}")
            table.set_text_rows({key: text})
        output[target] = core.build_orderedmap(table)
    for path, raw in output.items():
        logical = path.relative_to(package / "roots/common").as_posix()
        entries = [e for e in manifest["roots"]["common"] if e["logical_path"] == logical]
        if len(entries) > 1:
            raise ValueError(f"duplicate manifest root entry: {logical}")
        if entries:
            entries[0].update(size=len(raw), sha256=sha(raw))
        else:
            manifest["roots"]["common"].append({"logical_path": logical, "sha256": sha(raw), "size": len(raw)})
    for logical, key in ((PF_TABLE, PF_ID), (STRINGS, STRING_ID)):
        entries = [e for e in manifest["tables"] if e["root"] == "common" and e["logical_path"] == logical]
        if not entries:
            entries = [{"root": "common", "logical_path": logical, "codec_id": "flat",
                        "outer_keys": [], "inner_keys": [], "semantic_claims": []}]
            manifest["tables"].extend(entries)
        if len(entries) != 1:
            raise ValueError(f"duplicate manifest table claim: {logical}")
        if key not in entries[0]["outer_keys"]:
            entries[0]["outer_keys"].append(key)
    manifest["qa"]["release_ready"] = False
    manifest["qa"].pop("workspace_input_sha256", None)
    if CAPABILITY not in manifest.setdefault("required_capabilities", []):
        manifest["required_capabilities"].append(CAPABILITY)
    manifest.setdefault("snapshot", {})["inaho_native_pf_r2"] = {
        "power_flip_id": PF_ID, "native_kinds": ["special", "ranged"],
        "special_radius": [320, 400, 560], "special_radius_scale": 1.6,
        "fever_yellow6_preflip_combo35_extra_hits": 2,
        "client_capability": CAPABILITY, "removed_ability3_kind": 629,
        "effects_namespace": "battle/effect/powerflip/fox_oracle_autumn_native/",
    }
    output[manifest_path] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    changed = {p: raw for p, raw in output.items() if not p.exists() or p.read_bytes() != raw}
    if not dry_run:
        for path, raw in changed.items():
            _atomic(path, raw)
        for path in removed:
            # Exact verified files under the approved package; no recursive delete.
            path.unlink()
    return {"package": str(package), "dry_run": dry_run,
            "changed": [str(p.relative_to(package)) for p in changed],
            "removed": [str(p.relative_to(package)) for p in removed],
            "requires_client_capability": CAPABILITY, "effects": sorted(map(private_path, effects)),
            "effect_assets": sorted(map(private_path, effect_assets)),
            "effect_path_mapping": {path: private_path(path) for path in sorted(effect_assets)},
            "native_pf_key": PF_ID, "programs": list(PROGRAMS)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--source-store", type=Path, required=True)
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(revise(args.workspace, args.source_store, args.apk, dry_run=args.dry_run),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
