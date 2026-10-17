"""海豹球的低强度套件；复用莉可治疗、法夫耐性和原生永久增益。"""
from copy import deepcopy
import hashlib

import wf_dsl
import wf_gui
import wf_client_legality
import wf_seasonal7_common as C
import wf_seasonal7_tables as T


def val(lo, hi=None):
    return [{"min": lo, "max": lo if hi is None else hi}]


def skill_tree(pack, level):
    faf = pack.template_dsl("battle/action/skill/action/rare3/cute_fafnir$cute_fafnir_2")
    rico = pack.template_dsl("battle/action/skill/action/rare3/mens_attire_girl$mens_attire_girl_2")
    tree = deepcopy(faf)
    tree[-1][1] = deepcopy(faf[-1][1][:2])
    for node in C.walk(tree):
        if isinstance(node, list) and node and node[0] == "ACToleranceOfElement":
            node[1] = val(600 if level == "1" else 720)
            node[3] = val(.08 if level == "1" else .10)
    heals = deepcopy(rico[-1][1][1:4])
    for node in C.walk(heals):
        if isinstance(node, list) and node and node[0] == "CreateRatioHeal":
            node[3] = val(.03 if level == "1" else .04)
            node[4], node[5] = [], val(0)
    tree[-1][1].extend(heals)
    return tree


def leader_tree(pack):
    tree = deepcopy(pack.template_dsl("battle/action/skill/action/rare3/cute_fafnir$cute_fafnir_2"))
    tree[-1][1] = tree[-1][1][2:]
    for node in C.walk(tree):
        if isinstance(node, list) and node:
            if node[0] == "ACAttackPoint":
                # CommonBattleConstants.ETERNAL_CONDITION_THRESHOLD == 99999.
                node[1], node[2] = val(99999), val(1)
            elif node[0] == "CreateCondition":
                node[5] = False  # 不可驱散，与整场常驻队长加攻一致。
                node[7] = "spheal_mascot_leader_attack"
    return tree


def ability(slot, effect, value, *, target="0", main=False, trigger="0"):
    row = wf_gui.composer_generate(f"129990{slot}", mode="instant", trigger_kind=trigger,
                                  effect_kind=str(effect), value=value, target=target,
                                  groups="(None)" if target == "5" else "")["row"]
    row[0] = f"spheal_mascot_{slot}"
    row[1], row[2], row[3], row[4] = ("false" if main else "true"), "defense_common", "0", "0"
    if slot == 6:
        row[34] = "5"
    errors = wf_client_legality.client_legality_problems("ability", row)
    if errors:
        raise ValueError(errors)
    return row


def build(pack):
    spec = pack.spec
    abilities = [ability(1, 205, 10), ability(2, 37, 10),
                 ability(3, 205, 10, target="5", main=True),
                 ability(4, 205, 5), ability(5, 33, 10), ability(6, 206, 3, trigger="23")]
    pack.write_flat(T.ABILITY, {key: [row] for key, row in zip(spec.ability_keys, abilities)})
    opening = f"battle/action/skill/ability/ability_skill_{spec.code}_leader"
    leaders = []
    for params in (dict(effect_kind="211", value=100, target="5", groups="(None)"),
                   dict(effect_kind="629", value=0, string_id=f"{spec.code}_leader",
                        action_path=opening)):
        row = wf_gui.composer_generate(f"L:{spec.cid}", mode="instant", trigger_kind="0", **params)["row"]
        row[0], row[1], row[2] = f"{spec.code}_leader", "0", "0"
        errors = wf_client_legality.client_legality_problems("leader_ability", row)
        if errors:
            raise ValueError(errors)
        leaders.append(row)
    pack.write_flat(T.LEADER, {spec.cid_s: leaders})
    pack.write_flat(T.CAS, {f"{spec.code}_leader": "全体参战者攻击力＋100%"})
    programs = [pack.write_dsl(opening, leader_tree(pack), owner="kit")]
    nested = C.core.load_nested_table_bytes(pack.pkg_path("common", T.ACTION).read_bytes(), T.ACTION)
    actions = {}
    for level, text in nested.rows[spec.code].text_rows().items():
        row = C.csv_split(text)[0]
        row[0] = spec.texts["skill1" if level == "1" else "skill2"]
        row[1], row[2], row[4], row[5] = spec.texts["desc2"], "dynamic/skill/heal", "250", "250"
        path = T.program_path(spec, level)
        row[7] = path
        actions[level] = [row]
        tree = skill_tree(pack, level)
        if wf_dsl.player_side_dsl_problems(tree):
            raise ValueError(wf_dsl.player_side_dsl_problems(tree))
        programs.append(pack.write_dsl(path, tree, owner="kit"))
    pack.write_nested(T.ACTION, spec.code, actions)
    # Home / Evolution / Join 是独立种类；主页的觉醒约束不替代演出台词。
    # 原生无语音角色使用 (None)，首次加入和觉醒仍必须有文本行，否则 C2265。
    pack.write_flat(T.SPEECH, {spec.cid_s: [["0", "0", "", "ぱう、ぱう！", "(None)"],
                                         ["0", "1", "", "ぱう〜♪", "(None)"],
                                         ["1", "", "1", "ぱう〜っ！ぱう、ぱう♪", "(None)"],
                                         ["2", "", "", "ぱう！ぱう、ぱう〜♪", "(None)"]]})
    char = C.csv_split(pack.pkg_flat(T.CHAR)[spec.cid_s])[0]
    char[4] = "Beast,Aquatic"
    pack.write_flat(T.CHAR, {spec.cid_s: [char]})
    # 实际候选技能预览：采用原生输入控制，增加观测治疗和耐性反馈的播放时间。
    logical = f"character/{spec.code}/battle/character_detail_skill_preview.battle.amf3.deflate"
    preview = C.amf_parse(pack.pkg_path("common", logical).read_bytes())
    preview["config"]["end_frame"] = 420
    preview["config"]["skill_gauge_ratio"] = 1
    pack.write_asset("common", logical, C.amf_bytes(preview), owner="kit")
    pack.sync_character_mirrors()
    result = {"status": "candidate", "summary": "五星水属性吉祥物；250能量；本队开场充能/参战者永久加攻",
              "skills": {"programs": programs}, "abilities": abilities, "leader": leaders,
              "preview": {"config": preview["config"], "candidate_skill_sha256": {
                  lg: hashlib.sha256(pack.pkg_path("common", lg).read_bytes()).hexdigest() for lg in programs}},
              "runtime_verified": False}
    pack.write_evidence("kit-report.json", result)
    return result
