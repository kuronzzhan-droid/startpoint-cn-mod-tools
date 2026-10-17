"""奈芙A4的固定50%球直击独立加成，写入各球原生本地状态槽。"""
from copy import deepcopy
import json
from pathlib import Path

from wf_bianca_dragon_skill import block, command, value
from wf_character_revision import RevisionCandidate, encode_tree
from wf_client_legality import client_legality_problems, declared_block_field_problems
import wf_mod_tool as core

CID, CODE = "169989", "ruin_girl_campus"
ABILITY_TABLE = "master/ability/ability.orderedmap"
ABILITY_KEY = CID + "4"
STRING_TABLE = "master/string/custom_ability_string.orderedmap"
STRING_ID = CODE + "_multiball_direct_a4"
ACTION_PATH = "battle/action/skill/action/ability_skill/" + CODE + "$" + STRING_ID
LOGICAL_PATH = ACTION_PATH + ".action.dsl.amf3.deflate"
CONDITION_KEY = STRING_ID
# 作者 2026-09-27 多人卡顿修复（方案1，K=10）：能力4 T77 行由每 1 帧改为每 10 帧执行本程序；
# 隐形状态持续帧 = 2 × 周期（原 1 帧/2 帧），相邻两次刷新之间留一个周期余量不断档。
UPDATE_PERIOD_FRAMES = 10
TTL_FRAMES = 2 * UPDATE_PERIOD_FRAMES
UPDATE_PERIOD = str(UPDATE_PERIOD_FRAMES * 100_000)   # 阈值列单位：帧 × 100000


def action_tree():
    condition = command("CreateCondition", 81,
        [["ACSeparatedTermDirectDamage", value(TTL_FRAMES), value(0.5), value(1)]],
        value(1), ["None"], False, False, CONDITION_KEY, None, True, 3, value(1), False)
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False,
            False, 0, block(command("FindMultiballSubjects", 80, 81, False, [],
                                   block(), condition))]


def action_assets():
    return {("common", LOGICAL_PATH): encode_tree(action_tree())}


def flat_string_rows():
    return {STRING_ID: [["协力球对敌人造成的直接攻击伤害+50%（独立乘区）。"]]}


def replace_ball_row(rows):
    """只替换A4失效的target8 During行，主成员行和既有前置条件原样保留。

    已转换的行（T77 → 629 本程序）只把刷新周期改写为 UPDATE_PERIOD，其余格不动。"""
    result = deepcopy(rows)
    if len(result) != 2 or any(len(row) != 126 or row[0] != CODE + "_4" for row in result):
        raise ValueError("unexpected Nephtim ability4 identity or shape")
    old = [i for i, row in enumerate(result)
           if row[5] == "1" and row[109:111] == ["410", "8"]]
    if not old:
        ready = [row for row in result if row[47] == "629" and row[70:72] == [STRING_ID, ACTION_PATH]]
        if len(ready) != 1 or ready[0][27] != "77":
            raise ValueError("expected exactly one original multiball During row")
        row = ready[0]
        if row[30] != row[31] or not row[30].isdigit() or int(row[30]) <= 0:
            raise ValueError("unexpected A4 refresh period")
    elif len(old) != 1:
        raise ValueError("ambiguous multiball During rows")
    else:
        row = result[old[0]]
        if (row[1] != "true" or row[6] != "2" or row[9:12] != ["600000", "600000", "Black"]
                or row[13] != "12" or row[20] != "0" or row[97] != "4"
                or row[113:115] != ["50000", "50000"]):
            raise ValueError("A4 strength, resonance, Fever or unison policy changed")
        row[5] = "0"
        row[27:85] = [""] * 58
        row[97:] = [""] * 29
        for column, content in {27: "77", 34: "(None)", 35: "0", 39: "(None)", 46: "0",
                                47: "629", 70: STRING_ID, 71: ACTION_PATH}.items():
            row[column] = content
    row[30:32] = [UPDATE_PERIOD] * 2
    problems = client_legality_problems("ability", row) + declared_block_field_problems("ability", row)
    if problems:
        raise ValueError("invalid replacement row: " + repr(problems))
    return result


def metadata():
    return dict(ability_slot=4, percent=50, requires_dark_resonance=True,
        requires_fever=True, unisonable=True, target="all local multiball members",
        element_filter=None, summoner_filter=None, update_period_frames=UPDATE_PERIOD_FRAMES,
        condition_duration_ball_updates=TTL_FRAMES, condition_key=CONDITION_KEY,
        invisible=True, force_apply=False, maximum_accumulation=1,
        fixed_magnification=1, party_row_unchanged=True, panel_unchanged=True,
        timing=(f"Refreshed every {UPDATE_PERIOD_FRAMES} frames; last queued write can apply in impact "
                f"phase; expires after {TTL_FRAMES} ball updates."),
        refresh_delay_frames_max=UPDATE_PERIOD_FRAMES,
        inactive_ball_timing="Native inactive/ghost ball update cadence governs expiration.",
        new_client_patch_required=False)


def revise_candidate(repo, workspace, *, apply=False):
    """默认只读计划；调用方须取得本角色候选写锁后才能apply。"""
    workspace = Path(workspace)
    before_manifest = (workspace / "package/manifest.json").read_bytes()
    manifest = json.loads(before_manifest)
    candidate = RevisionCandidate(Path(repo), workspace, character_id=CID, code_name=CODE,
        package_version=manifest["package_version"], snapshot_key="nephtim_a4_ball_fever_bonus",
        evidence_name="nephtim-a4-ball-fever-bonus.json")
    if candidate.manifest_bytes != before_manifest:
        raise ValueError("candidate changed while opening revision")
    table = core.read_orderedmap_file_from_bytes(candidate.read("common", ABILITY_TABLE))
    candidate.splice(ABILITY_TABLE, {ABILITY_KEY: replace_ball_row(core.read_csv_lines(table[ABILITY_KEY]))})
    candidate.splice(STRING_TABLE, flat_string_rows())
    for (tier, logical), raw in action_assets().items():
        candidate.emit(tier, logical, raw)
    programs = candidate.manifest["skills"]["programs"]
    if LOGICAL_PATH not in programs:
        programs.append(LOGICAL_PATH)
    return candidate.finish(metadata(), apply=apply)
