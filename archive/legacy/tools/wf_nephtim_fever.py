"""组装校园奈芙提姆暗直击修订，只写已隔离的候选角色包。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import wf_client_legality as legality
import wf_dsl_sig
import wf_mod_tool as core
import wf_nephtim_fever_abilities as abilities
import wf_nephtim_ball_hit_count as ball_hit_count
import wf_nephtim_multiball_direct as multiball_direct
import wf_nephtim_multiball_fever as multiball_fever
import wf_nephtim_fever_ball_pixels as balls
import wf_nephtim_fever_effects as effects
import wf_nephtim_fever_leader as leader
import wf_nephtim_fever_pixels as pixels
import wf_nephtim_fever_powerflip as powerflip
import wf_nephtim_fever_skill as skill
import wf_nephtim_fever_text as panel
from wf_character_revision import encode_tree
from wf_nephtim_fever_package import Candidate, CID, CODE

FLAT_STRINGS = "master/string/custom_ability_string.orderedmap"
SKILL_NAME = "午后星轨·甜蜜续杯"
SUFFIX = ".action.dsl.amf3.deflate"


def _walk(value):
    if isinstance(value, list):
        yield value
        for child in value:
            yield from _walk(child)


def validate_program(tree):
    problems = (legality.action_dsl_element_problems(tree, character_element=5)
                + legality.action_dsl_subject_binding_problems(tree)
                + legality.action_dsl_hit_area_target_problems(tree))
    for wrapped in _walk(tree):
        if len(wrapped) != 2 or wrapped[0] not in ("Command", "Event"):
            continue
        registry = wf_dsl_sig.COMMANDS if wrapped[0] == "Command" else wf_dsl_sig.EVENTS
        command = wrapped[1]
        if command[0] not in registry or len(command)-1 != len(registry[command[0]]):
            problems.append("unknown instruction or arity: " + command[0])
    if problems:
        raise ValueError("; ".join(problems))


def validate_rows(ability_rows, leaders, strings):
    for table, groups, shift in (("ability", ability_rows.values(), 0),
                                 ("leader_ability", [leaders], 2)):
        for rows in groups:
            for row in rows:
                problems = (legality.client_legality_problems(table, row)
                    + legality.declared_block_field_problems(table, row)
                    + legality.ability_element_column_problems(table, row, 5))
                if problems:
                    raise ValueError("; ".join(problems))
                kind = row[47-shift]
                if kind not in {"536", "629", "722"}:
                    continue
                key = row[(84 if kind == "722" else 70)-shift]
                if not strings.get(key, [[""]])[0][0]:
                    raise ValueError(f"missing native ability description: {table}:{key}")


def assemble(repo: Path, workspace: Path, *, piercing_extension, apply=False):
    if piercing_extension != "dark_resonance":
        raise ValueError("采用暗属性共鸣时队伍贯穿时间常驻方案（2026-09-27 起能力2 +40%）")
    candidate = Candidate(repo, workspace)
    ability_path, leader_path = "master/ability/ability.orderedmap", "master/ability/leader_ability.orderedmap"
    source = candidate.official_rows(ability_path)
    rows = abilities.ability_rows(source)
    leaders = leader.leader_rows(source, piercing_extension=piercing_extension)
    strings = {**abilities.flat_string_rows(), **powerflip.flat_string_rows(),
               ball_hit_count.STRING_ID: [[ball_hit_count.DESCRIPTION]],
               **panel.native_flat_string_rows(),
               **panel.panel_rows(rows, leaders, piercing_extension=piercing_extension)}
    validate_rows(rows, leaders, strings)
    candidate.splice(ability_path, rows)
    candidate.splice(leader_path, {CID: leaders})
    candidate.splice(FLAT_STRINGS, strings)
    candidate.splice("master/character/unique_condition.orderedmap", skill.unique_rows())
    candidate.splice("master/skill/power_flip_action.orderedmap", powerflip.power_flip_rows())
    for logical, replacements in skill.multiball_rows(
            candidate.official_rows("master/battle/multiball/multiball.orderedmap"),
            candidate.official_rows("master/battle/multiball/multiball_level.orderedmap")).items():
        candidate.splice(logical, replacements)

    bundle = repo / "弹国服/bundle.zip"
    native = candidate.native_assets(bundle)
    files = {**pixels.assets(native), **balls.assets(native),
             **effects.assets(native), **powerflip.action_assets(native),
             **multiball_direct.action_assets(), **multiball_fever.action_assets()}
    files['common', ball_hit_count.ACTION_PATH + SUFFIX] = encode_tree(ball_hit_count.action_tree())
    spawn = skill.build_spawn()
    validate_program(spawn)
    files["common", abilities.SPAWN_ACTION_PATH + SUFFIX] = encode_tree(spawn)
    for (tier, logical), raw in files.items():
        candidate.emit(tier, logical, raw)

    logical = "master/skill/action_skill.orderedmap"
    table = core.read_orderedmap_raw_rows_from_bytes(candidate.read("common", logical), logical)
    actions = core.decode_action_skill_row(table.rows[table.keys.index(CODE)])
    programs = []
    description = panel.active_description()
    for level, row in actions:
        tree = skill.build_skill(int(level))
        validate_program(tree)
        row[0:2] = [SKILL_NAME + ("＋" if level == "2" else ""), description]
        row[2] = "dynamic/skill/multi_ball"
        row[7] = skill.ACTIVE_PATHS[int(level)-1]
        candidate.emit("common", row[7] + SUFFIX, encode_tree(tree))
        programs.append(row[7] + SUFFIX)
    candidate.splice(logical, {CODE: core.encode_action_skill_row(actions)}, codec="action_nested")
    text_path = "master/character/character_text.orderedmap"
    text = core.read_csv_lines(core.read_orderedmap_file_from_bytes(candidate.read("common", text_path))[CID])
    text[0][4:8] = [SKILL_NAME, description, SKILL_NAME + "＋", description]
    candidate.splice(text_path, {CID: text})
    candidate.server_character_row("cdndata/character_text.json", text)

    candidate.manifest["skills"]["programs"] = programs + sorted(
        path for tier, path in files if path.endswith(SUFFIX))
    candidate.manifest["unique_condition"] = {
        "ids": [skill.STATE_UID], "icons": [skill.STATE_ICON + ".png"],
    }
    candidate.manifest["required_capabilities"] = sorted(set(
        candidate.manifest.get("required_capabilities", []))
        | set(abilities.metadata()["required_client_capabilities"])
        | {"panel-description-override-v2"})
    metadata = {"abilities": abilities.metadata(), "leader": leader.metadata(),
                "active": skill.metadata(), "power_flip": powerflip.metadata(),
                "pixels": pixels.metadata(), "ball_pixels": balls.metadata(),
                "panel": panel.metadata(piercing_extension=piercing_extension),
                "panel_strategy": piercing_extension, "active_description": description,
                "requires_new_apk": False, "portrait_voice_and_ui_preserved": True,
                "runtime_acceptance": "pending in-game observation", "new_state_icon": skill.STATE_ICON}
    return candidate.finish(metadata, apply=apply)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--piercing-extension", choices=("dark_resonance",), required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = assemble(args.repo_root, args.workspace,
                      piercing_extension=args.piercing_extension, apply=args.apply)
    if args.report:
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"applied": report["applied"], "writes_live": False,
                      "files": len(report["changed_files"])}))


if __name__ == "__main__":
    main()
