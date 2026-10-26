"""校园奈芙提姆暗直击套件；在原生命令/词条行上做有界移植。"""
from __future__ import annotations

import copy
import json
import wf_campus_nephtim_common as C
import wf_campus_nephtim_tables as T
import wf_mod_tool as core
import wf_dsl
import wf_describe

CID = str(C.CID)


def walk(node):
    if isinstance(node, list):
        yield node
        for item in node:
            yield from walk(item)
    elif isinstance(node, dict):
        for item in node.values():
            yield from walk(item)


def replace_strings(node, substitutions):
    if isinstance(node, str):
        for old, new in substitutions.items():
            node = node.replace(old, new)
        return node
    if isinstance(node, list):
        return [replace_strings(item, substitutions) for item in node]
    if isinstance(node, dict):
        return {replace_strings(k, substitutions): replace_strings(v, substitutions)
                for k, v in node.items()}
    return node


def make_skill(level):
    """泳装奈芙鼓舞/连击 + 奥莉维尔贯通与星轨，去掉条件切换依赖。"""
    own = C.amf_read(f"battle/action/skill/action/rare5/ruin_girl_smr21$ruin_girl_smr21_{level}.action.dsl.amf3.deflate")
    donor = C.amf_read(f"battle/action/skill/action/rare5/olivia$olivia_{level}.action.dsl.amf3.deflate")
    own_commands = own[-1][1]
    branch = copy.deepcopy(own_commands[1][1][3][1])
    # 选择原生普通分支，防止未继承泳装六能力时产生悬空切换。
    for cmd in walk(branch):
        if not cmd:
            continue
        if cmd[0] == "FindAllSubjects":
            cmd[1], cmd[3] = 70, [6]
        elif cmd[0] == "CreateCondition" and cmd[1] == 1:
            cmd[1] = 70
        elif cmd[0] == "ACAttackPoint":
            cmd[1] = [{"min": 900, "max": 900}]
            cmd[2] = [{"min": 0.6 if level == '1' else 0.7,
                       "max": 0.8 if level == '1' else 1.0}]
        elif cmd[0] == "ACAdditionalDirectAttack":
            cmd[1] = [{"min": 900, "max": 900}]
            cmd[3] = [{"min": 0.25 if level == '1' else 0.35,
                       "max": 0.35 if level == '1' else 0.45}]
    for cmd in walk(donor):
        if not cmd:
            continue
        if cmd[0] == "ACPiercing":
            cmd[1] = [{"min": 720, "max": 900}]
        elif cmd[0] == "CreateNormalAttack":
            cmd[6] = [{"min": 1.5 if level == '1' else 2.0,
                       "max": 2.0 if level == '1' else 2.5}]
        elif cmd[0] == "ACAttackPoint":
            cmd[2] = [{"min": -0.1, "max": -0.15}]
        elif cmd[0] == "Block":
            cmd[1][:] = [x for x in cmd[1] if not (
                isinstance(x, list) and len(x) > 1 and x[0] == 'Command'
                and x[1][0] == 'CreateCondition'
                and any(y[0] == 'ACFrozen' for y in x[1][2]))]
    donor[-1][1] = [copy.deepcopy(own_commands[0]), *branch, *donor[-1][1]]
    # 将特效树隔离在新角色命名空间，原装角色不受染色或后续修改影响。
    return replace_strings(donor, {
        "battle/effect/skill_unique/ruin_girl_smr21/": f"battle/effect/skill_unique/{C.CODE}_star/",
        "battle/effect/skill_unique/olivia/": f"battle/effect/skill_unique/{C.CODE}_wave/",
    })


def build_abilities():
    source = C.load_flat(core.ABILITY_LOGICAL)[1]
    donor_map = {
        1: [('1611771', 0), ('1510632', 0)],
        2: [('1610032', 0)],
        3: [('1611351', 0)],
        4: [('1610035', 0), ('1510634', 0)],
        5: [('2610536', 1)],
        6: [('1610036', 0)],
    }
    rows, provenance = {}, []
    for slot, donors in donor_map.items():
        current = []
        for key, index in donors:
            row = core.read_csv_lines(source[key])[index][:]
            row[0], row[1], row[4] = f"{C.CODE}_{slot}", 'false' if slot == 3 else 'true', ''
            row = [{'White': 'Black', 'attack_white': 'attack_black'}.get(v, v) for v in row]
            current.append(row)
            provenance.append({'slot': slot, 'donor_key': key, 'donor_row': index})
        rows[f'{CID}{slot}'] = current
    # 百分比为客户端整数1000单位；保留每行原生触发/上限/主位字段。
    rows[f'{CID}1'][1][113:115] = ['37500', '75000']
    rows[f'{CID}3'][0][113:115] = ['70000', '140000']
    rows[f'{CID}4'][0][51:53] = ['12500', '25000']
    rows[f'{CID}4'][1][113:115] = ['20000', '40000']
    rows[f'{CID}5'][0][51:53] = ['17500', '35000']
    T.write_flat(core.ABILITY_LOGICAL, {k: T.csv_join(v) for k, v in rows.items()})
    leaders = C.load_flat('master/ability/leader_ability.orderedmap')[1]
    leader = [core.read_csv_lines(leaders['161003'])[0][:],
              core.read_csv_lines(leaders['161135'])[0][:]]
    for row in leader:
        row[0] = C.CODE
    leader[1][111:113] = ['160000', '220000']
    T.write_flat('master/ability/leader_ability.orderedmap', {CID: T.csv_join(leader)})
    return {'provenance': provenance,
            'abilities': {k: wf_describe.describe_rows(v, 'ability') for k, v in rows.items()},
            'leader': wf_describe.describe_rows(leader, 'leader_ability')}


def build():
    report = build_abilities()
    icons = ['condition_attack_up', 'condition_directattack_more',
             'condition_piercing_up', 'common_attack_up', '(None)', '(None)']
    T.write_flat('master/mana_board/upskill.orderedmap', {CID: T.csv_join([icons + icons])})
    lg = 'master/skill/action_skill.orderedmap'
    nested = core.load_nested_table(lg, C.STORE)
    source = nested.rows[C.TMPL_CODE]
    skill_rows = {}
    for level in ['1', '2']:
        row = core.read_csv_lines(source.text_rows()[level])[0]
        row[0], row[1] = T.TEXT[f'skill{level}'], T.TEXT[f'desc{level}']
        row[4:7] = ['560', '560' if level == '1' else '510', '1']
        row[7] = f'battle/action/skill/action/rare5/{C.CODE}${C.CODE}_{level}'
        tree = make_skill(level)
        C.write_pkg('common', wf_dsl.dsl_logical(row[7]), C.amf_bytes(tree))
        (C.EVIDENCE / f'skill-{level}.json').write_text(json.dumps(tree, ensure_ascii=False, indent=2), 'utf-8')
        skill_rows[level] = T.csv_join([row])
    nested.rows[C.CODE] = core.OrderedMap(lg, list(skill_rows),
                                         [v.encode('utf-8') for v in skill_rows.values()], C.STORE)
    C.write_pkg('common', lg, core.build_nested_table(nested, lg))
    (C.EVIDENCE / 'kit-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
    return report


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False, indent=2))
