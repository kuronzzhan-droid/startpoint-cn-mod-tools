"""十五套纯原生kit总入口；调用方显式传入原队长PF覆盖行。"""
from copy import deepcopy

from wf_miniboss_budget import INDEPENDENT, audit
from wf_miniboss_roster import BY_ID
from wf_miniboss_rows import Kit
from wf_miniboss_water import BUILDERS as WATER
from wf_miniboss_wind import BUILDERS as WIND
from wf_miniboss_fire import BUILDERS as FIRE
from wf_miniboss_other import BUILDERS as OTHER

BUILDERS = {**WATER, **WIND, **FIRE, **OTHER}
PF_CHARACTERS = {"139996", "149993", "159999"}


def build(character_id, *, source_leader=None):
    char = BY_ID[str(character_id)]
    abilities, leader = BUILDERS[char.cid](Kit(char.code, char.group, char.uid, char.layers))
    if char.cid in PF_CHARACTERS:
        if source_leader is None:
            raise ValueError("installed native PF override row is required")
        overrides = [row for row in source_leader if row[3] == "0" and row[45] == "722"]
        if len(overrides) != 1:
            raise ValueError("expected exactly one native PF override")
        leader.extend(deepcopy(overrides))
    for row in leader:
        if (row[3], int(row[45] if row[3] == "0" else row[107])) in INDEPENDENT:
            raise ValueError("leader must not add an independent damage term")
    metadata = audit(abilities)
    metadata.update(character_id=char.cid, code_name=char.code, role=char.role,
                    main_only_slots=[3], retained_unique_id=char.uid,
                    active_dsl_policy="retain installed bytes and characteristic attack geometry",
                    native_combo_policy="threshold crossings of current combo; rebuild can trigger again")
    return {f"{char.cid}{slot}": rows for slot, rows in abilities.items()}, {char.cid: leader}, metadata


def build_abilities(character_id):
    """当前窄维护入口：只返回六能力，不能导出队长/主动/基础数值。"""
    char = BY_ID[str(character_id)]
    abilities, _ = BUILDERS[char.cid](Kit(char.code, char.group, char.uid, char.layers))
    metadata = audit(abilities)
    metadata.update(character_id=char.cid, code_name=char.code, role=char.role,
                    revision="abilities-v2-gauge-20260927", main_only_slots=[3],
                    unique_id=char.uid, unique_master_unchanged=True,
                    source_skill_and_leader_unchanged=True)
    return {char.cid + str(slot): rows for slot, rows in abilities.items()}, metadata
