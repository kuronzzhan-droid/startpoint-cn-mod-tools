"""盾牌座身份、成长和魔力板克隆；不继承母本角色的玩法词条。"""
import json
from copy import deepcopy

import wf_mod_tool as core
import wf_quest_lib as tables
from wf_scutum_seed import CID, CODE, TEMPLATE_ID, TEMPLATE_CODE, remap

NAME, TITLE = "盾牌座", "庆典星盾"
WIND_MATERIALS = dict(zip(("46", "47", "48", "49", "65", "66", "67"),
                          ("13", "14", "15", "16", "59", "60", "61")))
SKILL, LEADER = "青苔的爱", "残缺星光的约定"
DESCRIPTION = ("恢复参战者的生命值【对风属性效果提升】并解除一个弱体效果／"
               "赋予风属性角色直接攻击伤害提升效果／自身为风属性时，赋予风属性角色连击效果／"
               "赋予队伍及协力球浮游、最大速度固定效果。")


def text_row():
    return [NAME, "DUNPAIZUO", "星星中的盾牌座 SCUTUM。应庆典而来的不死守护者，"
            "以青苔、花朵与细剑装点礼服，珍惜旅途中的每次相遇。",
            TITLE, SKILL, DESCRIPTION, SKILL + "＋", DESCRIPTION,
            "(None)", "(None)", LEADER, "--"]


def build(seed):
    crow = deepcopy(seed.rows(core.CHARACTER_LOGICAL)[TEMPLATE_ID][0])
    crow[0], crow[2:9] = CODE, ["5", "3", "Undead", "", "3", "Male", CODE]
    crow[17:25] = [CID, LEADER] + [CID + str(n) for n in range(1, 7)]
    crow[26:28] = ["Supporter", CID]
    seed.table(core.CHARACTER_LOGICAL, {CID: [crow]})
    seed.table("master/character/character_text.orderedmap", {CID: [text_row()]})
    seed.table("master/character/character_awake_status.orderedmap", {CID: [["0", "0"]]})
    for logical in ("master/character/character_gacha_sound.orderedmap",
                    "master/generated/character_image.orderedmap",
                    "master/character/full_shot_image_attribute.orderedmap",
                    "master/generated/mana_board.orderedmap", "master/mana_board/mana_node.orderedmap"):
        seed.clone(logical)
    logical = "master/character/character_status.orderedmap"
    raw = core.read_orderedmap_raw_rows_from_bytes(seed.read(logical), logical)
    original = tables.parse_node(raw.rows[raw.keys.index(TEMPLATE_ID)])
    maximum_hp = int(original["100"].split(",")[0])
    status = {level: f"{round(int(value.split(',')[0]) * 4652 / maximum_hp)},1"
              for level, value in original.items()}
    seed.table(logical, {CID: tables.build_node(status)}, "raw_outer")
    for logical in ("master/mana_board/upskill.orderedmap",
                    "master/mana_board/mana_board2_open_condition.orderedmap",
                    "master/skill_preview/skill_preview_character.orderedmap",
                    "master/stance_detail/character_stance_detail.orderedmap"):
        seed.table(logical, {CID: remap(seed.rows(logical)[TEMPLATE_ID])})
    icons = ["heal_up", "condition_directdamage_up", "condition_directattack_more",
             "condition_flying_up", "speed_up", "(None)"]
    seed.table("master/mana_board/upskill.orderedmap", {CID: [icons + icons]})
    logical = "master/mana_board/mana_node.orderedmap"
    own_nodes = tables.parse_node(seed.outputs["common", logical])[CID]
    for board in own_nodes.values():
        for key, value in board.items():
            row, = core.read_csv_lines(value)
            row[2] = ",".join(WIND_MATERIALS.get(x, x) for x in row[2].split(","))
            board[key] = core.write_csv_lines([row]).rstrip("\n")
    seed.table(logical, {CID: tables.build_node(own_nodes)}, "raw_outer")
    logical = "master/generated/trimmed_image.orderedmap"
    source = seed.rows(logical)
    seed.table(logical, {f"character/{CODE}/ui/{stem}": source[f"character/{TEMPLATE_CODE}/ui/{stem}"]
                        for stem in ("full_shot_1440_1920_0", "full_shot_1440_1920_1",
                                     "skill_cutin_0", "skill_cutin_1")})
    seed.server("cdndata/character.json", [crow])
    seed.server("cdndata/character_text.json", [text_row()])
    seed.server("character.json", dict(element=3, name=NAME, rarity=5, skill_count=6))
    nodes = remap(json.loads((seed.repo / "assets/mana_node.json").read_bytes())[TEMPLATE_ID])
    for board in nodes.values():
        for node in board.values():
            node["items"] = {WIND_MATERIALS.get(k, k): v for k, v in node["items"].items()}
    seed.server("mana_node.json", nodes)
    return {"name": NAME, "race": "Undead", "element": "Green", "speciality": "Supporter",
            "level_100_base_hp": 4652, "base_attack": 1, "donor": int(TEMPLATE_ID)}
