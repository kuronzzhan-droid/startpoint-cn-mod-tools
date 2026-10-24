"""装配校园希尔媞原生能力加成修订；只写隔离候选，无需新 APK。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import wf_celtie_fever_abilities as abilities
import wf_celtie_fever_leader as leader
import wf_celtie_fever_skill as skill
import wf_campus_panel_text as panel
import wf_client_legality as legality
import wf_mod_tool as core
from wf_celtie_fever_package import Candidate, CID, CODE, encode_tree
from wf_celtie_skill_growth import (GAIN_FLOAT_ID, GAIN_MAX_LAYERS, LEADER_FLAG, LEADER_MAX_LAYERS,
                                    MULTIPLIER_PER_LAYER)

DESCRIPTION = panel.active_description(CID)
SKILL_NAME = "风中快门·十字双空牙"
FLAT_STRINGS = "master/string/custom_ability_string.orderedmap"


def required_capabilities(existing=()):
    """迁移旧候选时移除已退用的来源补丁，保留 V12 Fever 及其他依赖。"""
    return sorted((set(existing) | set(abilities.metadata()["required_client_capabilities"])
                   | set(panel.metadata()["required_client_capabilities"]))
                  - {"celtie-ability-actions-v1"})


def validate_descriptions(ability_rows, leader_rows, flat_rows):
    """按客户端实际读取的平表引用校验，避免能力详情 C8601。"""
    for table, groups, shift in (("ability", ability_rows.values(), 0),
                                  ("leader_ability", [leader_rows], 2)):
        for rows in groups:
            for row in rows:
                problems = (legality.client_legality_problems(table, row)
                    + legality.declared_block_field_problems(table, row)
                    + legality.ability_element_column_problems(table, row, 3))
                if problems:
                    raise ValueError("; ".join(problems))
                kind = row[47 - shift]
                column = 84 - shift if kind == "722" else 70 - shift
                if kind not in {"536", "629", "704", "705", "706", "707", "708", "722"}:
                    continue
                key = row[column]
                if key not in flat_rows or not flat_rows[key] or not flat_rows[key][0][0]:
                    raise ValueError(f"{table} missing flat description: {key}")


def assemble(repo: Path, workspace: Path, *, apply=False):
    candidate = Candidate(repo, workspace)
    ability_path = "master/ability/ability.orderedmap"
    leader_path = "master/ability/leader_ability.orderedmap"
    official = candidate.official_rows(ability_path)
    rows = abilities.ability_rows(official)
    leaders = leader.leader_rows(official, candidate.official_rows(leader_path))
    strings = {**abilities.flat_string_rows(), **leader.flat_string_rows(),
               **panel.native_flat_string_rows(CID),
               **panel.override_string_rows(CID, rows, leaders)}
    validate_descriptions(rows, leaders, strings)
    candidate.splice(ability_path, rows)
    candidate.splice(leader_path, {CID: leaders})
    candidate.splice(FLAT_STRINGS, strings)
    candidate.splice("master/character/unique_condition.orderedmap", leader.unique_rows())
    candidate.splice("master/skill/power_flip_action.orderedmap", leader.power_flip_rows())
    files = {**leader.action_assets(candidate.official), **skill.effect_assets(candidate.official)}
    for (tier, logical), raw in files.items():
        candidate.emit(tier, logical, raw)

    action_path = "master/skill/action_skill.orderedmap"
    table = core.read_orderedmap_raw_rows_from_bytes(candidate.read("common", action_path), action_path)
    actions = core.decode_action_skill_row(table.rows[table.keys.index(CODE)])
    programs = []
    for level, row in actions:
        tree = skill.build_skill(int(level), candidate.official)
        row[0:2] = [SKILL_NAME + ("＋" if level == "2" else ""), DESCRIPTION]
        row[7] = skill.PROGRAM_PATHS[int(level) - 1]
        program = row[7] + ".action.dsl.amf3.deflate"
        candidate.emit("common", program, encode_tree(tree))
        programs.append(program)
    candidate.splice(action_path, {CODE: core.encode_action_skill_row(actions)}, codec="action_nested")
    text_path = "master/character/character_text.orderedmap"
    text_rows = core.read_csv_lines(core.read_orderedmap_file_from_bytes(
        candidate.read("common", text_path))[CID])
    text_rows[0][4:8] = [SKILL_NAME, DESCRIPTION, SKILL_NAME + "＋", DESCRIPTION]
    candidate.splice(text_path, {CID: text_rows})
    candidate.server_character_row("cdndata/character_text.json", text_rows)

    candidate.manifest["skills"]["programs"] = programs + sorted(
        logical for tier, logical in files if logical.endswith(".action.dsl.amf3.deflate"))
    candidate.manifest["unique_condition"] = {
        "ids": [int(uid) for uid in leader.unique_rows()],
        "icons": sorted({values[0][2] + ".png" for values in leader.unique_rows().values()}),
    }
    candidate.manifest["required_capabilities"] = required_capabilities(
        candidate.manifest.get("required_capabilities", []))
    metadata = {
        "abilities": abilities.metadata(), "leader": leader.metadata(),
        "active_description": DESCRIPTION, "active_multiplier": 75,
        "active_growth": {"per_starwind_layer": MULTIPLIER_PER_LAYER,
            "condition": "wind resonance and Fever at cast start",
            "float_id": GAIN_FLOAT_ID, "layer_limit": GAIN_MAX_LAYERS,
            "leader_skill_flag": LEADER_FLAG, "leader_layer_limit": LEADER_MAX_LAYERS},
        "active_segments": [25 * 75 / 70, 45 * 75 / 70], "cross_overlap_hits_per_segment": 1,
        "damage_programs": list(skill.PROGRAM_PATHS) + list(leader.PF_PROGRAM_PATHS),
        "damage_calculation": "native buffTargetAs=2; ability-damage main bonuses",
        "native_limits": "Skill/PowerFlip source flags, resistance and independent terms remain; ability-only terms do not apply",
        "requires_matching_client_patch": False, "requires_new_apk": False,
        "runtime_acceptance": "pending in-game observation on existing client with Fever percentage support",
        "presentation_preserved": True,
        "unique_condition_icon_updated": leader.GAIN_ICON + ".png",
        "panel_descriptions": panel.metadata(),
    }
    candidate.manifest["snapshot"]["campus_celtie"].update(
        skill_damage="wind damage using native ability-damage main bonuses",
        additional_damage="native wind ability I254", gameplay_revision="fever-cross-native-20260912",
    )
    return candidate.finish(metadata, apply=apply)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = assemble(args.repo_root, args.workspace, apply=args.apply)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"applied": report["applied"], "writes_live": False,
                      "files": len(report["changed_files"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
