# -*- coding: utf-8 -*-
"""角色平衡 1008（杰拉德 149999 / 稻穗 159991 / 白 149990 / 罗尔夫 179999），叠加在 kulo 1.4.158 视图上。
spec：research/balance_sheet_20261008.md。「去掉」= 删行（被删行均不是各键首行，或首行删除后新首行 c1/c2 不变，已断言）。
用法：WF_TIP=158 python balance_1008.py
"""
import copy
import hashlib
import json
import os
import zipfile

os.environ.setdefault("WF_TIP", "158")
from live149 import *  # noqa
from layout import col
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv
from dsltools import commands, get

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.158-1.4.159-1-balance-1008-local.zip"
AB_LP, LE_LP = "master/ability/ability.orderedmap", "master/ability/leader_ability.orderedmap"
CAS_LP, AS_LP = "master/string/custom_ability_string.orderedmap", "master/skill/action_skill.orderedmap"
TX_LP, U_LP = "master/character/character_text.orderedmap", "master/character/unique_condition.orderedmap"
T = {lp: load(lp) for lp in (AB_LP, LE_LP, CAS_LP, AS_LP, TX_LP, U_LP)}
BASE = {lp: copy.deepcopy(v) for lp, v in T.items()}
DSL: dict[str, list] = {}
LOG: list[str] = []
NL = chr(10)


def leaf(v: str, rs):
    s = _csv(rs)
    return s if v.endswith(NL) else s.rstrip(NL)


class Key:
    def __init__(self, lp, key):
        self.lp, self.key = lp, key
        self.rows = [r for r in rows(T[lp][key]) if r]
        self.drop = set()

    def r(self, i):
        return self.rows[i]

    def set(self, i, block, name, val, table="ability"):
        c = col(table, block, name)
        old = self.rows[i][c]
        self.rows[i][c] = str(val)
        LOG.append(f"{self.key}#{i} {block}.{name}: {old} → {val}")

    def remove(self, *idx):
        self.drop |= set(idx)

    def commit(self):
        keep = [r for i, r in enumerate(self.rows) if i not in self.drop]
        if 0 in self.drop:
            assert keep[0][1] == self.rows[0][1] and keep[0][2] == self.rows[0][2], (self.key, "c1/c2 改变")
        for i in sorted(self.drop):
            LOG.append(f"{self.key}#{i} 删除")
        T[self.lp][self.key] = leaf(T[self.lp][self.key], keep)


def text(lp, key, old, new, sub=None, colno=0):
    node = T[lp][key] if sub is None else T[lp][key][sub]
    rs = rows(node)
    rs = [r for r in rs if r]
    assert old in rs[0][colno], (key, sub, old)
    rs[0][colno] = rs[0][colno].replace(old, new)
    v = leaf(node, rs)
    if sub is None:
        T[lp][key] = v
    else:
        T[lp][key][sub] = v


def override(key, pairs):
    node = T[CAS_LP][key]
    s = rows(node)[0][0]
    for old, new in pairs:
        assert old in s, (key, old)
        s = s.replace(old, new)
    T[CAS_LP][key] = leaf(node, [[s]])


def dsl(program):
    if program not in DSL:
        DSL[program] = copy.deepcopy(dsl_tree(program))
    return DSL[program]


def delete_paths(tree, paths):
    for p in sorted(paths, reverse=True):
        parent = get(tree, p[:-1])
        del parent[p[-1]]


# ============================================================ 杰拉德 149999
G_SKILL = [f"battle/action/skill/action/rare5/white_wolf_gerald$white_wolf_gerald_{i}" for i in (1, 2)]
for p in G_SKILL:
    t = dsl(p)
    hits = [pp for pp, c in commands(t, "CreateCondition") if any(a[0] == "ACToleranceOfElement" for a in c[2])]
    assert len(hits) == 2, (p, hits)
    delete_paths(t, hits)
    LOG.append(f"{p}: 删除 2 处 ACToleranceOfElement(全属性 -15%×10 层) CreateCondition")
for lv in ("1", "2"):
    text(AS_LP, "white_wolf_gerald", " ＋ 赋予敌人累积全属性抗性降低效果（无视弱体抵抗、不可驱散）", "", sub=lv, colno=1)
for c in (5, 7):
    text(TX_LP, "149999", " ＋ 赋予累积全属性抗性降低效果", "", colno=c)
t = dsl("battle/action/power_flip/action/override/white_wolf_gerald_pf$white_wolf_gerald_pf_lv3")
n = 0
for pp, c in commands(t, "CreateCondition"):
    for a in c[2]:
        if a[0] == "ACAdditionalDirectAttack":
            assert a[3] == [{"min": 1.0, "max": 1.0}]
            a[3] = [{"min": 0.0, "max": 0.0}]
            n += 1
assert n == 2
LOG.append("white_wolf_gerald_pf_lv3: ACAdditionalDirectAttack 伤害修正 +100% → 0（段数 6、60 秒不变）×2")
override("override_string_white_wolf_gerald", [("队伍全体的直接攻击变为4次且直接攻击伤害+100%（60秒）", "队伍全体的直接攻击变为6次（60秒）")])
k = Key(LE_LP, "149999")
k.remove(6, 7, 8)
k.commit()
t = dsl("battle/action/skill/action/ability_skill/ability_skill_gerald_time_rift$ability_skill_gerald_time_rift")
n = 0
for pp, c in commands(t, "CreateCondition"):
    for a in c[2]:
        if a[0] in ("ACAbilityDamageResistance", "ACDirectAttackDamageResistance"):
            assert a[2] == [{"min": -1, "max": -1}]
            a[2] = [{"min": -0.05, "max": -0.05}]
            n += 1
assert n == 2
LOG.append("time_rift: 能力/直击伤害耐性 -100% → -5%")
override("ability_skill_gerald_time_rift", [("受到的能力伤害与直接攻击伤害翻倍（15秒）", "受到的能力伤害与直接攻击伤害增加5%（15秒）")])

# ============================================================ 稻穗 159991
I_SKILL = [f"battle/action/skill/action/rare5/cnmod_inaho_midautumn$cnmod_inaho_midautumn_{i}" for i in (1, 2)]
SCALE = {"ACAttackPoint": {2: 0.5, 2.5: 0.625}, "ACAbilityDamage": {2: 0.5, 2.75: 0.6875}, "ACDirectDamage": {0.75: 0.5, 1.5: 1.0}}
for p in I_SKILL:
    t = dsl(p)
    drop = []
    for pp, c in commands(t):
        if c[0] == "ConditionalsUnifyElement":
            inner = json.dumps(c)
            if "ACAbilityDamageResistance" in inner and "ACDirectAttackDamageResistance" in inner and "CreateNormalAttack" not in inner:
                drop.append(pp)
        if c[0] == "CreateCondition":
            for a in c[2]:
                if a[0] == "ACToleranceOfElement" and a[3] == [{"min": -0.15, "max": -0.15}]:
                    a[3] = [{"min": -0.075, "max": -0.075}]
                if a[0] in SCALE and len(a) > 2 and isinstance(a[2], list):
                    v = a[2][0]["max"]
                    if v in SCALE[a[0]] and any(b[0] == "ACRegeneration" for b in c[2]):
                        a[2] = [{"min": SCALE[a[0]][v], "max": SCALE[a[0]][v]}]
    assert len(drop) == 4, (p, len(drop))
    delete_paths(t, drop)
    s = json.dumps(t)
    assert "-0.15" not in s and "ACAbilityDamageResistance" not in s
LOG.append("稻穗技能×2：月蚀光耐性 -15% → -7.5%；删除共鸣追加的能力/直击耐性 -7.5%（4 处）；月满丰穰 攻/能/直击 → +50%（强化版按原比例 +62.5%/+68.75%/+100%）")
desc_old = ("强制赋予敌方永久、不可驱散的「月蚀」：光属性耐性-15%；光属性共鸣时，追加能力伤害耐性、直接攻击耐性各-7.5%。",
            "强制赋予敌方永久、不可驱散的「月蚀」：光属性耐性-7.5%。")
desc_old2 = ("攻击力、能力伤害各+200%，直接攻击伤害+75%", "攻击力、能力伤害、直接攻击伤害各+50%")
for lv in ("1", "2"):
    for o, nw in (desc_old, desc_old2):
        text(AS_LP, "cnmod_inaho_midautumn", o, nw, sub=lv, colno=1)
for c in (5, 7):
    for o, nw in (desc_old, desc_old2):
        text(TX_LP, "159991", o, nw, colno=c)
t = dsl("battle/action/power_flip/action/override/cnmod_inaho_midautumn$cnmod_inaho_midautumn_lv3")
n = 0
for pp, c in commands(t, "CreateNormalAttack"):
    if c[6] == [{"min": 20, "max": 20}]:
        c[6] = [{"min": 5, "max": 5}]
        n += 1
assert n == 1
LOG.append("稻穗 PF Lv3：追加伤害 20 倍 → 5 倍")
override("desc_override_cnmod_inaho_midautumn", [("队长当前攻击力20倍威力", "队长当前攻击力5倍威力")])
k = Key(AB_LP, "1599911")
k.set(4, "instant_content", "strength.power1", 5000); k.set(4, "instant_content", "strength.first_max", 5000)
k.remove(5); k.commit()
override("desc_override_cnmod_inaho_midautumn_1", [("自身发动技能时，自身技能槽＋20%（最多4次）", "自身发动技能时，自身技能槽＋5%（最多4次）"),
                                                   (NL + " <icon id='main'>  自身发动技能时，自身攻击力＋150%[最大＋300%]", "")])
k = Key(AB_LP, "1599912")
k.set(1, "instant_content", "strength.power1", 15000); k.set(1, "instant_content", "strength.first_max", 15000)
k.remove(2); k.commit()
override("desc_override_cnmod_inaho_midautumn_2", [("直接攻击伤害额外乘区＋75%", "直接攻击伤害额外乘区＋15%"),
                                                   (NL + " <icon id='main'>  Fever模式中，强化队伍全体的直接攻击[直接攻击计算为3次 / 合计伤害＋75%]", "")])
k = Key(AB_LP, "1599913")
k.set(3, "instant_content", "target", 5)
k.set(3, "instant_content", "target.character_groups", "(None)")
k.set(3, "instant_content", "strength.power1", 10000); k.set(3, "instant_content", "strength.first_max", 10000)
k.remove(1, 4, 6, 7, 8); k.commit()
override("desc_override_cnmod_inaho_midautumn_3", [
    (NL + " <icon id='main'>  自身回复生命值时，对最近的敌人造成自身攻击力15倍威力的光属性能力伤害（冷却时间：3秒）", ""),
    ("队伍全体攻击力＋15%[最大＋150%]，自身能力伤害＋30%[最大＋300%]", "队伍全体攻击力＋15%[最大＋150%]、能力伤害＋10%[最大＋100%]"),
    (NL + " <icon id='main'>  光属性共鸣时，Fever模式中，自身回复生命值时，队伍全体直接攻击伤害＋35%[最大＋280%]", ""),
    (NL + " <icon id='main'>  光属性角色每发动能力攻击，队伍全体攻击力＋7.5%[最大＋75%]", ""),
    (NL + " <icon id='main'>  光属性角色每发动能力攻击，队伍全体对敌人造成的能力伤害额外乘区＋3.5%[最大＋28%]", ""),
    (NL + " <icon id='main'>  光属性共鸣时，Fever模式中，光属性角色每发动能力攻击，队伍全体对弱化效果中的敌人造成的伤害＋1.5%[最大＋15%]", "")])
k = Key(AB_LP, "1599915"); k.remove(2); k.commit()
override("desc_override_cnmod_inaho_midautumn_5", [(NL + "光属性共鸣时，队伍全体对敌人造成的伤害额外乘区＋3.5%", "")])
k = Key(AB_LP, "1599916"); k.remove(0, 1, 2, 7); k.commit()
override("desc_override_cnmod_inaho_midautumn_6", [("Fever模式中，队伍全体攻击力＋125%" + NL, ""),
                                                   (" <icon id='main'>  Fever模式中，队伍全体能力伤害＋350%、对敌人造成的伤害额外乘区＋10%" + NL, ""),
                                                   (NL + "进入Fever模式时，赋予队伍全体再生效果[恢复75]（30秒）", "")])

# ============================================================ 白 149990
k = Key(AB_LP, "1499901")
k.set(2, "instant_content", "strength.power1", 5000); k.set(2, "instant_content", "strength.first_max", 5000); k.commit()
override("desc_override_white_tiger_summer_1", [("能力伤害额外乘区＋20%（技能斩击本体除外）", "能力伤害额外乘区＋5%")])
k = Key(AB_LP, "1499902")
k.set(0, "instant_trigger", "threshold.power1", 6000000); k.set(0, "instant_trigger", "threshold.first_max", 6000000)
k.set(0, "instant_trigger", "cooltime", 300)
k.set(0, "instant_content", "strength.power1", 1000000); k.set(0, "instant_content", "strength.first_max", 1000000); k.commit()
override("desc_override_white_tiger_summer_2", [("FEVER模式中每持续1.5秒，对全体敌人造成5倍能力伤害", "FEVER模式中每持续1秒，对全体敌人造成10倍能力伤害（CT：5秒）")])
SUNBURN = "battle/action/skill/action/ability_skill/ability_skill_white_tiger_summer_sunburn$ability_skill_white_tiger_summer_sunburn"
DSL[SUNBURN] = ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, ["Block", [
    ["Command", ["FindAllSubjects", 0, 49, [], [], [], [], [], ["DoNothing"], ["Block", [
        ["Command", ["CreateCondition", 0, [["ACUnique", 1499901, [{"min": 1, "max": 1}]],
                                            ["ACAbilityDamageResistance", [{"min": 900, "max": 900}], [{"min": -0.02, "max": -0.02}],
                                             [{"min": 5, "max": 5}]]],
                     [{"min": 1, "max": 1}], ["GenericConditionHitEffect"], False, False, "white_tiger_summer_sunburn", None,
                     False, 3, [{"min": 1, "max": 1}], True]]]]]]]]]
k = Key(AB_LP, "1499903")
for i in (0, 1):
    k.set(i, "instant_trigger", "trigger_limit", 5)
donor = [r for r in rows(T[AB_LP]["1499993"]) if r][5]
assert donor[47] == "629"
r3 = k.r(3)
assert r3[47] == "413"
r3[47:85] = donor[47:85]
r3[70], r3[71] = "ability_skill_white_tiger_summer_sunburn", SUNBURN
LOG.append("1499903#3: 413 敌方固有「晒伤」→ 629（晒伤 1 层 + 敌方能力伤害耐性 -2%/层，最多 5 层，15 秒）")
k.commit()
uc = rows(T[U_LP]["1499901"])[0]
assert uc[4] == "3"
uc[4] = "5"
T[U_LP]["1499901"] = leaf(T[U_LP]["1499901"], [uc])
LOG.append("unique 1499901 晒伤 叠层上限 3 → 5")
T[CAS_LP]["ability_skill_white_tiger_summer_sunburn"] = "使全体敌人获得1层「晒伤」：能力伤害耐性-2%（最多5层，15秒）" + NL
override("desc_override_white_tiger_summer_3", [("风属性角色攻击力＋50%、能力伤害＋50%（最多10层）", "风属性角色攻击力＋50%、能力伤害＋50%（最多5层）"),
                                                 ("赋予全体敌人「晒伤」1层（最多3层）", "赋予全体敌人「晒伤」1层（最多5层）"),
                                                 ("「晒伤」每1层，使敌人的能力伤害抗性－15%（最多－45%，持续15秒）", "「晒伤」每1层，使敌人的能力伤害抗性－2%（最多－10%，持续15秒）")])
k = Key(AB_LP, "1499905")
k.set(0, "instant_trigger", "threshold.power1", 6000000); k.set(0, "instant_trigger", "threshold.first_max", 6000000)
k.set(0, "instant_trigger", "cooltime", 180); k.commit()
override("desc_override_white_tiger_summer_5", [("每达成35连击，风属性角色技能槽＋5%", "每达成60连击，风属性角色技能槽＋5%（CT：3秒）")])
k = Key(AB_LP, "1499906")
k.set(0, "instant_content", "strength.power1", 1000000); k.set(0, "instant_content", "strength.first_max", 1000000); k.commit()
override("desc_override_white_tiger_summer_6", [("弹射时对全体敌人造成5倍能力伤害", "弹射时对全体敌人造成10倍能力伤害")])

# ============================================================ 罗尔夫 179999
k = Key(AB_LP, "1799991"); k.set(1, "instant_trigger", "cooltime", 300); k.commit()
for key in ("1799994", "1799995"):
    k = Key(AB_LP, key)
    idx = (3, 4) if key == "1799994" else (0, 1)
    for i in idx:
        assert k.r(i)[113] == k.r(i)[114] == "20000", (key, i)
        k.set(i, "during_content", "strength.power1", 5000); k.set(i, "during_content", "strength.first_max", 5000)
    k.commit()


def main() -> int:
    import sys
    sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
    import wf_client_legality as L
    import wf_cursed_weapons as W
    files, probs = {}, []
    for lp in T:
        base, now = BASE[lp], T[lp]
        if now == base:
            continue
        data = q.build_node(now)
        back = q.parse_node(data)
        assert back == now and set(base) <= set(back)
        files[lp] = data
    for key in ("1599911", "1599912", "1599913", "1599915", "1599916", "1499901", "1499902", "1499903", "1499905",
                "1499906", "1799991", "1799994", "1799995"):
        for i, r in enumerate([x for x in rows(T[AB_LP][key]) if x]):
            probs += [f"{key}#{i}: {p}" for p in L.client_legality_problems("ability", r)]
    for i, r in enumerate([x for x in rows(T[LE_LP]["149999"]) if x]):
        probs += [f"L149999#{i}: {p}" for p in L.client_legality_problems("leader_ability", r)]
    for p, tree in DSL.items():
        probs += [f"{p}: {x}" for x in W.dsl_signature_problems(tree)]
        files[wf_dsl.dsl_logical(p)] = encode_tree(tree)
    assert not probs, probs
    members = {member(lp): d for lp, d in files.items()}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.158", "version": "1.4.159", "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    print("\n".join(LOG))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
