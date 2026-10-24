"""置顶五位角色的能力1主位修订；只改既有行c1与原生红M。"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import zlib

import wf_mod_tool as core

CODES = {"149990": "white_tiger_summer", "119989": "lady_summoner_campus",
         "149989": "wind_spgirl_campus", "169989": "ruin_girl_campus",
         "149988": "scutum_valentine"}
ABILITY = "master/ability/ability.orderedmap"
STRINGS = "master/string/custom_ability_string.orderedmap"
MAIN = " <icon id='main'>  "


def main_description(text):
    """每个非空说明行加原生标记，原文字、换行及已存在的标记保持。"""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("ability description must be nonempty text")
    return "\n".join(MAIN + line if line.strip() and "<icon id='main'>" not in line
                     else line for line in text.split("\n"))


def main_only_rows(character_id, rows):
    cid = str(character_id)
    if cid not in CODES:
        raise ValueError("unsupported featured character")
    if not rows:
        raise ValueError("ability1 rows must not be empty")
    result = deepcopy(rows)
    for row in result:
        if len(row) != 126 or row[0] != CODES[cid] + "_1" or row[1] not in ("true", "false"):
            raise ValueError("unexpected native ability1 identity or shape")
        row[1] = "false"
    return result


def _replace(raw, key, rows):
    table = core.read_orderedmap_raw_rows_from_bytes(raw)
    if key not in table.keys:
        raise ValueError("existing ability/description key required: " + key)
    index = table.keys.index(key)
    before = core.read_csv_lines(zlib.decompress(table.rows[index]).decode("utf-8"))
    if rows == before:
        return raw
    table.rows[index] = zlib.compress(core.write_csv_lines(rows).rstrip("\n").encode("utf-8"))
    return core.build_orderedmap_raw_rows(table)


def patch_tables(character_id, ability_raw, string_raw):
    """只返回两张表和两个精确键；不会导出其他角色或六能力整组。"""
    cid = str(character_id)
    if cid not in CODES:
        raise ValueError("unsupported featured character")
    ability_key, text_key = cid + "1", "desc_override_" + CODES[cid] + "_1"
    abilities = core.read_orderedmap_file_from_bytes(ability_raw)
    strings = core.read_orderedmap_file_from_bytes(string_raw)
    if ability_key not in abilities or text_key not in strings:
        raise ValueError("existing ability/description key required")
    original = core.read_csv_lines(abilities[ability_key])
    text = core.read_csv_lines(strings[text_key])
    if len(text) != 1 or len(text[0]) != 1:
        raise ValueError("description must be a native single text cell")
    result = {ABILITY: _replace(ability_raw, ability_key, main_only_rows(cid, original)),
              STRINGS: _replace(string_raw, text_key, [[main_description(text[0][0])]])}
    return result, {"character_id": cid, "ability_key": ability_key, "text_key": text_key,
                    "row_count": len(original), "changed_ability_columns": [1],
                    "gameplay_values_and_conditions_unchanged": True,
                    "description_change": "native main-position icon only"}


def revise_candidate(repo, workspace, character_id, *, apply=False):
    """仅在作者给定候选窗口调用；默认只读计划，apply也不写live。"""
    from wf_character_revision import RevisionCandidate
    cid = str(character_id)
    if cid not in CODES:
        raise ValueError("unsupported featured character")
    workspace = Path(workspace)
    manifest_bytes = (workspace / "package/manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    candidate = RevisionCandidate(Path(repo), workspace, character_id=cid, code_name=CODES[cid],
        package_version=manifest["package_version"], snapshot_key="featured_main_ability1",
        evidence_name="featured-main-ability1.json")
    if candidate.manifest_bytes != manifest_bytes:
        raise ValueError("candidate manifest changed while opening plan")
    inputs = {logical: candidate.read("common", logical) for logical in (ABILITY, STRINGS)}
    files, metadata = patch_tables(cid, inputs[ABILITY], inputs[STRINGS])
    claims = {t["logical_path"]: set(t["outer_keys"]) for t in manifest["tables"] if t["root"] == "common"}
    if metadata["ability_key"] not in claims.get(ABILITY, set()):
        raise ValueError("candidate does not declare its own ability1")
    unclaimed_text = metadata["text_key"] not in claims.get(STRINGS, set())
    if unclaimed_text and cid != "149990":
        raise ValueError("candidate does not declare its own ability1 text")
    metadata.update(existing_unclaimed_summer_text=unclaimed_text,
                    ownership_claims_unchanged=True, new_client_patch_required=False)
    for logical, after in files.items():
        if after != inputs[logical]:
            candidate.emit("common", logical, after)
    if not candidate.outputs:
        return {"writes_live": False, "applied": False, "no_change": True,
                "metadata": metadata, "changed_files": []}
    result = candidate.finish(metadata, apply=apply)
    result["exact_keys"] = {ABILITY: [metadata["ability_key"]], STRINGS: [metadata["text_key"]]}
    result["input_sha256"] = {p: hashlib.sha256(raw).hexdigest() for p, raw in inputs.items()}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--character-id", choices=tuple(CODES), required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = revise_candidate(args.repo, args.workspace, args.character_id, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
