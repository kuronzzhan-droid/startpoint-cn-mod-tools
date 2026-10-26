"""把碧安卡已发布角色包修订成小龙协力球版本；仅写隔离候选。"""
from __future__ import annotations

import argparse
import copy
import json
import zlib
from pathlib import Path

import wf_bianca_dragon_abilities as abilities
import wf_bianca_dragon_bridge as bridge
import wf_bianca_dragon_icons as icons
import wf_bianca_dragon_pixels as pixels
import wf_bianca_dragon_skill as skill
import wf_campus_panel_text as panel
import wf_campus_bianca_data as old
import wf_mod_tool as core
from wf_bianca_dragon_package import Candidate, CID, CODE, encode_tree

DESCRIPTION = panel.active_description(CID)
FEVER_NAME = "焰域研修"


def nested_blob(logical: str, values: dict) -> bytes:
    return core.build_orderedmap_raw_rows(core.OrderedMap(
        logical_path=logical, source_path=Path("<memory>"), keys=list(values),
        rows=[zlib.compress(core.write_csv_lines(rows).rstrip("\n").encode("utf-8"))
              for rows in values.values()],
    ))


def assemble(repo: Path, candidate_root: Path, *, apply=False):
    candidate = Candidate(repo, candidate_root)
    ability_path = "master/ability/ability.orderedmap"
    leader_path = "master/ability/leader_ability.orderedmap"
    source = candidate.official_rows(ability_path)
    rows = abilities.ability_rows(source)
    rows[CID + "1"].extend(bridge.a1_enhancement_rows(source))
    rows.update(bridge.support_damage_rows(source))
    leaders = abilities.leader_rows(source, candidate.official_rows(leader_path))
    for group in rows.values():
        for row in group:
            old.validate_row(row, "ability")
    for row in leaders:
        old.validate_row(row, "leader_ability")
    candidate.splice(ability_path, rows)
    candidate.splice(leader_path, {CID: leaders})
    candidate.splice("master/string/custom_ability_string.orderedmap", {
        **abilities.fever_tick_string_rows(), **bridge.flat_string_rows(),
        **panel.native_flat_string_rows(CID), **panel.override_string_rows(CID, rows, leaders),
    })
    for (tier, logical), raw in abilities.fever_tick_assets().items():
        candidate.emit(tier, logical, raw)

    unique = bridge.unique_condition_rows()
    stack_id = str(abilities.FEVER_STACK_UNIQUE_ID)
    stack = copy.deepcopy(unique[str(bridge.BREATH_UNIQUE_ID)][0])
    stack[:5] = [CODE + "_fever_stack", FEVER_NAME,
                 "battle/common/unique_condition/" + CODE + "_fever_stack",
                 "99999999", str(abilities.UNIQUE_MAX_ACCUMULATION)]
    stack[13] = "true"
    unique[stack_id] = [stack]
    candidate.splice(bridge.UNIQUE_TABLE, unique)
    icon_assets = icons.build_icon_assets()
    for target, raw in icon_assets.items():
        candidate.emit("common", target, raw)
    strings = {key: nested_blob(bridge.POWER_UP_TABLE, levels)
               for key, levels in bridge.power_up_string_rows().items()}
    candidate.splice(bridge.POWER_UP_TABLE, strings, codec="raw_outer")
    candidate.manifest["unique_condition"] = {
        "ids": [int(key) for key in unique], "icons": sorted(icon_assets),
    }

    for logical, values in skill.build_multiball_tables(
        candidate.official_rows("master/battle/multiball/multiball.orderedmap"),
        candidate.official_rows("master/battle/multiball/multiball_level.orderedmap"),
    ).items():
        candidate.splice(logical, values)
    actor, actor_evidence = pixels.build_dragon_assets(candidate.official)
    for (tier, logical), raw in {**actor, **skill.build_effect_assets(candidate.official)}.items():
        candidate.emit(tier, logical, raw)

    action_path = "master/skill/action_skill.orderedmap"
    action_table = core.read_orderedmap_raw_rows_from_bytes(candidate.read("common", action_path), action_path)
    entries = core.decode_action_skill_row(action_table.rows[action_table.keys.index(CODE)])
    programs = []
    for level, row in entries:
        tree = skill.build_skill(int(level))
        old.validate_skill(tree)
        row[:2] = [old.SKILL + ("＋" if level == "2" else ""), DESCRIPTION]
        row[7] = f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}"
        program = row[7] + ".action.dsl.amf3.deflate"
        candidate.emit("common", program, encode_tree(tree))
        programs.append(program)
    candidate.splice(action_path, {CODE: core.encode_action_skill_row(entries)}, codec="action_nested")
    candidate.manifest["skills"]["programs"] = programs + [
        logical for tier, logical in abilities.fever_tick_assets()]

    text_path = "master/character/character_text.orderedmap"
    table = core.read_orderedmap_file_from_bytes(candidate.read("common", text_path))
    text_rows = core.read_csv_lines(table[CID])
    text_rows[0][5] = text_rows[0][7] = DESCRIPTION
    candidate.splice(text_path, {CID: text_rows})
    candidate.server_character_row("cdndata/character_text.json", text_rows)
    required = candidate.manifest.setdefault("required_capabilities", [])
    for capability in (abilities.metadata()["required_client_capabilities"]
                       + panel.metadata()["required_client_capabilities"]):
        if capability not in required:
            required.append(capability)
    candidate.manifest["snapshot"]["campus_bianca"].update(
        persistent_multiball=True, native_dragon_summon_attack=False,
        skill_buff_target_as=0, hit_area_buff_target_as=None,
        active_source="I251 createdByAbility; dragon support target TriggerPuller",
        gameplay_revision="owned-dragon-multiball-20260912",
        fever_guards="user kit; native percentage requires kyubi-fever-ratio-v1",
    )
    metadata = {
        **abilities.metadata(), "active_description": DESCRIPTION,
        "actor": actor_evidence, "dragon_id": skill.DRAGON_ID,
        "breath_damage_multiplier": 50, "debuff_duration_frames": 900,
        "breath_fever_points": 250,
        "enhanced_resistance": "all ability damage resistance -20%, plus fire resistance -25%",
        "a1_optional": "support damage exists even before learning A1",
        "owner_isolation": "own+ID selection, commanded dragon marker, caster TriggerPuller",
        "client_version_authorized": "existing client supports dash and Fever percentage; exact version unknown",
        "dragon_level_100_base": {"hp": 5000, "attack": 5000},
        "summon_visual": "ready/appear contain only native particles; one active dragon actor",
        "dragon_idle": "single official as frame for idle and movement; selected by user",
        "existing_art_voice_preserved": True,
        "status_icons": "three original generated 48px RGBA icons; native condition paths preserved",
        "panel_descriptions": panel.metadata(),
    }
    return candidate.finish(metadata, apply=apply)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = assemble(args.repo_root, args.workspace, apply=args.apply)
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(applied=result["applied"], writes_live=False,
                         files=len(result["changed_files"]), report=str(args.report)), ensure_ascii=False))


if __name__ == "__main__":
    main()
