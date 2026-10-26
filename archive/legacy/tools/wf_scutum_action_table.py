"""盾牌座主动技能的原生权重、名称及两档动作链接。"""
import wf_mod_tool as core
from wf_scutum_identity import SKILL, DESCRIPTION
from wf_scutum_seed import CODE, TEMPLATE_CODE
from wf_scutum_skill import ACTIVE_PATHS


def install(seed):
    logical = "master/skill/action_skill.orderedmap"
    source = core.read_orderedmap_raw_rows_from_bytes(seed.official(logical), logical)
    rows = core.decode_action_skill_row(source.rows[source.keys.index(TEMPLATE_CODE)])
    if [level for level, _ in rows] != ["1", "2"]:
        raise ValueError("unexpected official active skill levels")
    for level, row in rows:
        row[0:2] = [SKILL + ("＋" if level == "2" else ""), DESCRIPTION]
        row[4:6] = ["500", "500"]
        row[7] = ACTIVE_PATHS[int(level) - 1]
    seed.table(logical, {CODE: core.encode_action_skill_row(rows)}, "action_nested")
    seed.inner_keys["common", logical] = [dict(outer_key=CODE, keys=["1", "2"])]
    return dict(skill_weight=500, active_paths=list(ACTIVE_PATHS))
