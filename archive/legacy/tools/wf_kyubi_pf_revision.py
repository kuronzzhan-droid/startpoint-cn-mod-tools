#!/usr/bin/env python3
"""Revise an isolated Kyubi package; never load or publish live resources."""
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
from wf_kyubi_pf_dsl import MAIN, SPECIAL, SPECIAL_KEY, SUFFIX, revise_tree

ACTION = "master/skill/action_skill.orderedmap"
TEXT = "master/character/character_text.orderedmap"
STRINGS = "master/string/custom_ability_string.orderedmap"
ABILITY = "master/ability/ability.orderedmap"
SERVER_TEXT = "cdndata/character_text.json"
INPUTS = tuple(("common", p + SUFFIX) for p in (*MAIN, SPECIAL)) + (
    ("common", ACTION), ("common", TEXT), ("common", STRINGS),
    ("common", ABILITY), ("server", SERVER_TEXT),
)
OLD_DESCRIPTION = ("召唤秋夜的雷华，对领域内全体敌人造成雷属性伤害（不破坏弱点）"
                   "＋赋予麻痹效果／FEVER槽增加／赋予参战者全员及协力球攻击力提升效果。")
DESCRIPTION = OLD_DESCRIPTION.replace("雷属性伤害（不破坏弱点）",
                                      "雷属性强化弹射伤害（不破坏弱点）")
SPECIAL_DESCRIPTION = ("追加「秋灯雷华」特殊强化弹射，与射击型强化弹射同时生效，"
                       "对触及的敌人造成雷属性强化弹射伤害／自身为队长时，"
                       "FEVER模式中雷属性共鸣且连击达到35以上时攻击次数增加")
CAPABILITY = "kyubi-pf-damage-v1"
# Explicitly assigned integration clone. Compare the resolved input to this literal
# path, not to its symlink target, so a redirected clone cannot authorize live writes.
APPROVED_PACKAGE = Path(('${WF_ROOT}/startpoint-cn/work/character_packs/codex-revision-20260906/fox_oracle_autumn/package'.replace("${WF_ROOT}", str(root_path()))))


def _package(workspace: Path) -> Path:
    workspace = workspace.resolve(strict=True)
    package = workspace if (workspace / "manifest.json").is_file() else workspace / "package"
    package = package.resolve(strict=True)
    if package == APPROVED_PACKAGE:
        return package
    if "codex_out" not in (part.lower() for part in package.parts):
        raise ValueError("only an isolated package below codex_out is accepted")
    if any(part.lower() in ("character_packs", "store", "asset-patch") for part in package.parts):
        raise ValueError("author packages and live/store paths are forbidden")
    return package


def _path(package: Path, root: str, logical: str) -> Path:
    path = (package / "roots" / root / logical).resolve(strict=True)
    if not path.is_relative_to(package):
        raise ValueError("input symlink escapes the isolated package")
    return path


def _json(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _description(value: str) -> str:
    if value not in (OLD_DESCRIPTION, DESCRIPTION):
        raise ValueError("unrecognized Kyubi main skill description")
    return DESCRIPTION


def _flat_text(path: Path) -> bytes:
    table = core.read_orderedmap_file(path, TEXT)
    rows = table.text_rows()
    row, = core.read_csv_lines(rows["139995"])
    row[5], row[7] = _description(row[5]), _description(row[7])
    table.set_text_rows({"139995": core.write_csv_lines([row])})
    return core.build_orderedmap(table)


def _action(path: Path) -> bytes:
    table = core.read_orderedmap_file_raw_rows(path, ACTION)
    index = table.keys.index("fox_oracle_autumn")
    entries = core.decode_action_skill_row(table.rows[index])
    if {key for key, _ in entries} != {"1", "2"}:
        raise ValueError("unexpected Kyubi action skill keys")
    for _, row in entries:
        row[1] = _description(row[1])
    table.rows[index] = core.encode_action_skill_row(entries)
    return core.build_orderedmap_raw_rows(table)


def _strings(path: Path) -> bytes:
    table = core.read_orderedmap_file(path, STRINGS)
    current = table.text_rows()[SPECIAL_KEY]
    if "秋灯雷华" not in current:
        raise ValueError("unrecognized special-PF description")
    table.set_text_rows({SPECIAL_KEY: SPECIAL_DESCRIPTION})
    return core.build_orderedmap(table)


def _atomic_write(path: Path, data: bytes):
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, path)
        if path.read_bytes() != data:
            raise OSError(f"write verification failed: {path}")
    finally:
        temporary.unlink(missing_ok=True)


def revise(workspace: Path, *, dry_run: bool) -> dict:
    package = _package(Path(workspace))
    manifest_path = (package / "manifest.json").resolve(strict=True)
    if not manifest_path.is_relative_to(package):
        raise ValueError("manifest symlink escapes isolated package")
    original_manifest = manifest_path.read_bytes()
    manifest = json.loads(original_manifest)
    if (manifest.get("character_id"), manifest.get("code_name")) != (139995, "fox_oracle_autumn"):
        raise ValueError("manifest must identify Kyubi 139995")
    paths = {(r, p): _path(package, r, p) for r, p in INPUTS}
    # This table is deliberately read-only: ability 2 keeps I354 and unison support,
    # while Fever duration and abilities 4-6 remain the author's integration scope.
    ability_bytes = paths["common", ABILITY].read_bytes()
    output: dict[Path, bytes] = {}
    for program in (*MAIN, SPECIAL):
        path = paths["common", program + SUFFIX]
        source = wf_dsl.parse_dsl(zlib.decompress(path.read_bytes(), -15))["tree"]
        tree = revise_tree(source, program)
        encoder = zlib.compressobj(level=9, wbits=-15)
        payload = wf_dsl.encode_amf3(tree)
        output[path] = encoder.compress(payload) + encoder.flush()
    output[paths["common", ACTION]] = _action(paths["common", ACTION])
    output[paths["common", TEXT]] = _flat_text(paths["common", TEXT])
    output[paths["common", STRINGS]] = _strings(paths["common", STRINGS])
    server = json.loads(paths["server", SERVER_TEXT].read_bytes())
    row, = server["139995"]
    row[5], row[7] = _description(row[5]), _description(row[7])
    output[paths["server", SERVER_TEXT]] = _json(server)
    capabilities = manifest.setdefault("required_capabilities", [])
    if CAPABILITY not in capabilities:
        capabilities.append(CAPABILITY)
    manifest["qa"]["release_ready"] = False
    manifest.setdefault("snapshot", {})["kyubi_pf_revision"] = {
        "version": 1, "client_capability": CAPABILITY,
        "main_skill_pf_level": 1, "special_and_ability2_pf_level": "triggering_pf",
        "ability2_kind": 354, "ability2_unison_preserved": True,
        "special_radius": [320, 480], "requires_reseal": True,
    }
    for root, logical in INPUTS:
        path = paths[root, logical]
        if path not in output:
            continue
        entries = [r for r in manifest["roots"][root] if r["logical_path"] == logical]
        if len(entries) != 1:
            raise ValueError(f"expected one manifest claim for {root}/{logical}")
        entries[0].update(sha256=hashlib.sha256(output[path]).hexdigest(), size=len(output[path]))
    strings_claim = [t for t in manifest["tables"] if t["logical_path"] == STRINGS]
    if len(strings_claim) != 1 or SPECIAL_KEY not in strings_claim[0]["outer_keys"]:
        raise ValueError("manifest is missing the existing custom string claim")
    output[manifest_path] = _json(manifest)
    changed = {p: data for p, data in output.items() if p.read_bytes() != data}
    # Validate every input and build the complete result before the first mutation.
    if not dry_run:
        for path, data in changed.items():
            _atomic_write(path, data)
    if paths["common", ABILITY].read_bytes() != ability_bytes:
        raise RuntimeError("ability table changed during the revision")
    return {"workspace": str(package), "dry_run": dry_run,
            "changed": [str(p.relative_to(package)).replace("\\", "/") for p in changed],
            "requires_client_capability": CAPABILITY, "requires_reseal": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(revise(args.workspace, dry_run=args.dry_run), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
