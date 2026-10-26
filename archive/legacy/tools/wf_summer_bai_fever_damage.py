"""夏日白主动技的 Fever 全场追加倍率修订；不改变其它攻击或说明。"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import zlib

import wf_dsl
import wf_mod_tool as core
from wf_character_revision import RevisionCandidate, encode_tree
from wf_client_legality import action_dsl_subject_binding_problems

CID, CODE = "149990", "white_tiger_summer"
ACTION_TABLE = "master/skill/action_skill.orderedmap"
PROGRAMS = tuple(f"battle/action/skill/action/rare5/{CODE}${CODE}_{level}"
                 for level in (1, 2))
SUFFIX = ".action.dsl.amf3.deflate"
MAGNIFICATION = 75.0


def _nodes(value, name):
    if isinstance(value, list):
        if value and value[0] == name:
            yield value
        for child in value:
            yield from _nodes(child, name)


def fever_damage(tree, level):
    """仅定位原生 Fever 真分支的一次全场攻击，拒绝结构或来源漂移。"""
    if level not in (1, 2):
        raise ValueError("expected active skill level 1 or 2")
    result = deepcopy(tree)
    if len(result) != 12 or result[0] != "ActionDsl" or result[10] not in (0, 2):
        raise ValueError("unexpected native skill root")
    branches = list(_nodes(result, "ConditionalsFeverMode"))
    if len(branches) != 1 or len(branches[0]) != 3:
        raise ValueError("expected exactly one native Fever branch")
    areas = list(_nodes(branches[0][1], "CreateHitArea"))
    attacks = list(_nodes(branches[0][1], "CreateNormalAttack"))
    if len(areas) != 1 or len(attacks) != 1:
        raise ValueError("expected exactly one Fever hit area and attack")
    area, attack = areas[0], attacks[0]
    expected_shape = ["Rectangle", [{"min": 1500, "max": 1500}],
                      [{"min": 2000, "max": 2000}]]
    if (len(area) != 27 or area[9] != expected_shape or area[24] != 2
            or area[14] != ["CalculatedUsingMaxNumOfHits", 1]
            or area[15] != ["Some", [{"min": 1, "max": 1}]]
            or list(_nodes(area[23], "CreateNormalAttack")) != [attack]):
        raise ValueError("Fever all-enemy geometry, hit count or damage reference changed")
    expected = [{"min": 50.0, "max": 50.0 if level == 1 else 60.0}]
    target = [{"min": MAGNIFICATION, "max": MAGNIFICATION}]
    if (len(attack) != 17 or attack[1] != area[22] or attack[2] != 255
            or attack[5] != 100 or attack[6] not in (expected, target)):
        raise ValueError("unexpected Fever attack identity or old magnification")
    attack[6] = target
    problems = action_dsl_subject_binding_problems(result)
    if problems:
        raise ValueError("invalid subject binding: " + repr(problems))
    return result


def revise_candidate(repo, workspace, *, apply=False):
    workspace = Path(workspace)
    manifest_bytes = (workspace / "package/manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    candidate = RevisionCandidate(Path(repo), workspace, character_id=CID, code_name=CODE,
        package_version=manifest["package_version"], snapshot_key="summer_fever_damage_75",
        evidence_name="summer-fever-damage-75.json")
    if candidate.manifest_bytes != manifest_bytes:
        raise ValueError("candidate changed while opening revision")
    table = core.read_orderedmap_raw_rows_from_bytes(candidate.read("common", ACTION_TABLE))
    rows = dict(core.decode_action_skill_row(table.rows[table.keys.index(CODE)]))
    old_magnifications = {}
    for level, program in enumerate(PROGRAMS, 1):
        if rows[str(level)][7] != program:
            raise ValueError("active skill program differs from assigned character")
        logical = program + SUFFIX
        raw = candidate.read("common", logical)
        tree = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
        branch = list(_nodes(tree, "ConditionalsFeverMode"))[0]
        old_magnifications[str(level)] = list(_nodes(branch[1], "CreateNormalAttack"))[0][6]
        revised = fever_damage(tree, level)
        if revised != tree:
            candidate.emit("common", logical, encode_tree(revised))
    metadata = dict(
        character_id=CID, active_levels=[1, 2], old_magnifications=old_magnifications,
        fever_additional_magnification=MAGNIFICATION, changed_command_column=6,
        changed_command="CreateNormalAttack inside ConditionalsFeverMode true branch",
        conditions_cooldowns_and_non_fever_attacks_unchanged=True,
        ability3_twenty_times_unchanged=True, descriptions_unchanged=True,
        native_damage_reference_unchanged=True, new_client_patch_required=False,
    )
    return candidate.finish(metadata, apply=apply)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(revise_candidate(args.repo, args.workspace, apply=args.apply),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
