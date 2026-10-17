"""夏日白技能采用官方同型能力加成参考；仅写已核对的隔离候选包。"""
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

CID = "149990"
CODE = "white_tiger_summer"
PROGRAMS = tuple(f"battle/action/skill/action/rare5/{CODE}${CODE}_{lv}" for lv in (1, 2))
SUFFIX = ".action.dsl.amf3.deflate"
DESCRIPTION = (
    "冲向最近的敌人并卷起浪涛，浪涛沿途斩击碰撞到的敌人，造成风属性伤害／"
    "强制赋予被斩击的敌人麻痹／为风属性角色累积攻击力提升＆能力伤害提升／"
    "增加连击数／FEVER模式中发动时，追加对全体敌人造成风属性伤害。"
    "技能伤害量以能力伤害加成判定。"
)


def walk(tree):
    if isinstance(tree, list):
        yield tree
        for node in tree:
            yield from walk(node)


def native_reference(tree):
    """只补Fever攻击区域的能力参考；现有追斩、来源与演出原样保留。"""
    if not isinstance(tree, list) or len(tree) != 12 or tree[0] != "ActionDsl":
        raise ValueError("expected native ActionDsl")
    result = deepcopy(tree)
    areas = [node for node in walk(result) if node and node[0] == "CreateHitArea"]
    attacks = [node for node in walk(result) if node and node[0] == "CreateNormalAttack"]
    if len(areas) != 3 or len(attacks) != 3:
        raise ValueError("summer skill must contain chase, enhanced slash and Fever burst")
    if result[10] not in (0, 2) or any(len(area) != 27 or area[24] not in (0, 2) for area in areas):
        raise ValueError("unexpected damage reference; inspect current skill before revising")
    for area in areas:
        direct_attacks = [node for node in walk(area[23]) if node and node[0] == "CreateNormalAttack"]
        if len(direct_attacks) != 1:
            raise ValueError("each summer hit area must own exactly one attack")
        area[24] = 2
    problems = action_dsl_subject_binding_problems(result)
    if problems:
        raise ValueError("; ".join(problems))
    return result


PACKAGE_VERSION_FLOOR = "1.0.2"


def package_version(current: str) -> str:
    """首次修订升到 1.0.2；候选已更高（如 2026-09-27b 平衡批次写回 1.0.3）时保持现值，重跑不降级。"""
    parse = lambda value: tuple(int(part) for part in value.split("."))
    return current if parse(current) >= parse(PACKAGE_VERSION_FLOOR) else PACKAGE_VERSION_FLOOR


def assemble(repo: Path, workspace: Path, *, apply=False):
    manifest = json.loads((Path(workspace) / "package/manifest.json").read_bytes())
    candidate = RevisionCandidate(
        repo, workspace, character_id=CID, code_name=CODE,
        package_version=package_version(manifest["package_version"]),
        snapshot_key="summer_bai_native_ability_reference",
        evidence_name="native-ability-reference.json")
    action_path = "master/skill/action_skill.orderedmap"
    table = core.read_orderedmap_raw_rows_from_bytes(candidate.read("common", action_path), action_path)
    entries = core.decode_action_skill_row(table.rows[table.keys.index(CODE)])
    if {level for level, _ in entries} != {"1", "2"}:
        raise ValueError("expected both evolution levels")
    for level, row in entries:
        path = PROGRAMS[int(level) - 1]
        if row[7] != path:
            raise ValueError("summer skill path drifted")
        logical = path + SUFFIX
        tree = wf_dsl.parse_dsl(zlib.decompress(candidate.read("common", logical), -15))["tree"]
        candidate.emit("common", logical, encode_tree(native_reference(tree)))
        row[1] = DESCRIPTION
    candidate.splice(action_path, {CODE: core.encode_action_skill_row(entries)}, codec="action_nested")
    text_path = "master/character/character_text.orderedmap"
    text_rows = core.read_csv_lines(core.read_orderedmap_file_from_bytes(
        candidate.read("common", text_path))[CID])
    text_rows[0][5] = text_rows[0][7] = DESCRIPTION
    candidate.splice(text_path, {CID: text_rows})
    candidate.server_character_row("cdndata/character_text.json", text_rows)
    candidate.manifest.setdefault("skills", {})["programs"] = [p + SUFFIX for p in PROGRAMS]
    metadata = {
        "damage_reference": "native buffTargetAs=2 for both skills and all six hit areas",
        "new_client_patch_required": False,
        "source_classification": "native skill; independent multipliers, resistance and events unchanged",
        "geometry_damage_values_timing_and_presentation_preserved": True,
        "scope": "active skills only; existing leader, six abilities and power flip unchanged",
    }
    return candidate.finish(metadata, apply=apply)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    report = assemble(args.repo_root, args.workspace, apply=args.apply)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"applied": report["applied"], "writes_live": False,
                      "files": len(report["changed_files"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
