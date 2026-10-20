# -*- coding: utf-8 -*-
"""作者 1019 裁定的数据+文案修正。视图 = 1.4.245 + WF_MORE(246,247)。用法 python hotfix2.py [--write VER]"""
import sys, os, json, hashlib, zipfile, copy, zlib
sys.path.insert(0, '.')
import v245 as V, psim as P
_cwd = os.getcwd(); os.chdir(V.BUILD)
import wf_mod_tool as M
from stage_all import csv_text
from wf_character_revision import encode_tree
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W
os.chdir(_cwd)
NL = "\n"
ICON = " <icon id='main'>  "


def leaf(v, rs):
    s = csv_text(rs)
    return s if v.endswith(NL) else s.rstrip(NL)


def raw_replace(lp, edits):
    raw, _ = V.read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    for k, node in edits.items():
        assert V.q.build_node(V.load(lp)[k]) == rows0[keys0.index(k)], (lp, k)
        om.rows[om.keys.index(k)] = V.q.build_node(node)
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys == keys0
    assert [i for i in range(len(rows0)) if back.rows[i] != rows0[i]] == sorted(keys0.index(k) for k in edits)
    return out


T = {lp: V.load(lp) for lp in (V.AB, V.LE, V.CAS, V.AS, V.TX)}
OUT = {}
LOG = []
ROWS = {}


def rows_of(lp, key):
    if (lp, key) not in ROWS:
        ROWS[(lp, key)] = [r for r in V.rows(T[lp][key]) if r]
    return ROWS[(lp, key)]


def setcell(lp, key, i, col, old, new, why):
    r = rows_of(lp, key)[i]
    assert r[col] == old, (key, i, col, r[col])
    r[col] = new
    LOG.append(f"ability[{key}]#{i} c{col}: {old} -> {new}  {why}")


def cas_edit(key, pairs, why):
    v = OUT.get(V.CAS, {}).get(key, T[V.CAS][key])
    t = V.rows(v)[0][0]
    for o, n in pairs:
        assert t.count(o) == 1, (key, o)
        t = t.replace(o, n)
    nv = leaf(v, [[t]])
    assert V.rows(nv)[0] == [t]
    OUT.setdefault(V.CAS, {})[key] = nv
    LOG.append(f"custom_ability_string[{key}]: {why}")


def skill_text(cid, code, pairs, why):
    g = copy.deepcopy(OUT.get(V.AS, {}).get(code, T[V.AS][code]))
    for lv in g:
        r = list(V.rows(g[lv])[0])
        t = r[1]
        for o, n in pairs:
            assert t.count(o) == 1, (code, lv, o)
            t = t.replace(o, n)
        r[1] = t
        g[lv] = V.join(r) + (NL if g[lv].endswith(NL) else "")
    OUT.setdefault(V.AS, {})[code] = g
    v = T[V.TX][cid]
    tx = V.rows(v)[0]
    for c in (5, 7, 9):
        for o, n in pairs:
            if o in tx[c]:
                tx[c] = tx[c].replace(o, n)
    OUT.setdefault(V.TX, {})[cid] = V.join(tx) + (NL if v.endswith(NL) else "")
    LOG.append(f"action_skill[{code}] all levels + character_text[{cid}]: {why}")


DSLS = {}


def dsl(p):
    if p not in DSLS:
        DSLS[p] = copy.deepcopy(V.dsl_tree(p))
    return DSLS[p]


def walk(n, fn):
    if isinstance(n, list):
        fn(n)
        for a in n:
            walk(a, fn)


def is_cmd(n, name):
    return len(n) == 2 and n[0] == "Command" and isinstance(n[1], list) and n[1] and n[1][0] == name


# 1 玛格诺斯 119996：永恒之火只在火共鸣时点燃（改文案）
skill_text("119996", "lion_swordman_reborn", [("点燃自身的「永恒之火」，", "【火属性共鸣时】点燃自身的「永恒之火」，")],
           "永恒之火只在火属性共鸣时点燃")

# 3 稻穗·中秋 159991 能力4：强化月满丰穰无实际差别（删句）
cas_edit("desc_override_cnmod_inaho_midautumn_4",
         [("\n" + ICON + "光属性共鸣时，强化『月满稻穗·星屑幻梦』的「月满丰穰」效果", "")],
         "删去没有实际效果的「强化月满丰穰」句")

# 4 赛瑞斯 129999：吐息补上与技能相同的旗号 1 强化
SK = "battle/action/skill/seris_dragon_king/seris_dragon_king_2"
flag_block = []
walk(dsl(SK), lambda n: flag_block.append(copy.deepcopy(n)) if is_cmd(n, "ConditionalsChangeSkillFlag") and n[1][1] == 1 else None)
assert len(flag_block) == 1
del DSLS[SK]
BR = "battle/action/skill/action/ability_skill/ability_skill_seris_breath$ability_skill_seris_breath"
done = []


def addflag(n):
    if is_cmd(n, "FindAllSubjects") and n[1][1] == 0 and n[1][2] == 49:
        blk = n[1][9]
        assert blk[0] == "Block" and "ConditionalsChangeSkillFlag" not in json.dumps(blk)
        blk[1].append(flag_block[0])
        done.append(1)


walk(dsl(BR), addflag)
assert done == [1]
LOG.append("DSL ability_skill_seris_breath: 敌人块末尾追加 ConditionalsChangeSkillFlag 1（强制赋予 PF 抗性-15%、水抗性-15%，20 秒），与『苍海潮涌』同款")

# 5 莉莉丝EX 139997：能力伤害增益对象 光 -> 雷
for lv in (1, 2):
    p = f"battle/action/skill/action/rare5/resistance_princess_ex$resistance_princess_ex_{lv}"
    hit = []

    def sel(n):
        if is_cmd(n, "FindAllSubjects") and n[1][2] == 33 and n[1][3] == [5] and "ACAbilityDamage" in json.dumps(n[1][9]):
            n[1][3] = [3]
            hit.append(1)

    walk(dsl(p), sel)
    assert hit == [1], (p, hit)
LOG.append("DSL resistance_princess_ex_1/_2: 能力伤害增益 FindAllSubjects 选择器 [5]光 -> [3]雷")
skill_text("139997", "resistance_princess_ex", [("赋予光属性角色能力伤害提升效果", "赋予雷属性角色能力伤害提升效果")], "增益对象改为雷属性角色")

# 6 伊尔梅塔雷 159950：治疗属性加成 火 -> 光
for lv in (1, 2):
    p = f"battle/action/skill/action/rare5/discard_dragon_light_playable$discard_dragon_light_playable_{lv}"
    hit = []

    def heal(n):
        if is_cmd(n, "CreateRatioHeal") and n[1][4] == [1]:
            n[1][4] = [5]
            hit.append(1)

    walk(dsl(p), heal)
    assert hit == [1], (p, hit)
LOG.append("DSL discard_dragon_light_playable_1/_2: CreateRatioHeal 属性加成 [1]火 -> [5]光")
skill_text("159950", "discard_dragon_light_playable",
           [("回复队伍全体最大生命值8%的生命值", "回复队伍全体最大生命值8%的生命值【对光属性角色效果提升】")], "治疗补写光属性加成")

# 8 海茵莱特 119970 能力4：整键仅主位
for i in range(3):
    setcell(V.AB, "1199704", i, 1, "true", "false", "嫉火来源全是仅主位能力，能力4 改为仅主位（自动面板带主位图标）")

# 7 凉月 159992 能力3行2：PowerFlipComboCountDown 正值=减少所需连击（官方先例 magical_bayonetter_3 +1~3、限2次）；
#   现值 -6 且不限次 = 每次 Lv3 后所需连击 +6 无限累加。改为 -6 连击（正值）且只触发 1 次。
setcell(V.AB, "1599923", 2, 51, "-600000", "600000", "凉月 Lv3 后所需连击数符号写反")
setcell(V.AB, "1599923", 2, 52, "-600000", "600000", "凉月 Lv3 后所需连击数符号写反")
setcell(V.AB, "1599923", 2, 34, "(None)", "1", "凉月 只在首次 Lv3 后生效 1 次，避免无限叠加")

# 克劳斯 129997 能力2：强化中毒 = 水属性角色毒伤害提升
new = [""] * 126
for c, x in {0: "claude_wolf_assassin_ex_2", 1: "true", 2: "condition", 3: "0", 5: "0", 6: "0", 13: "0", 20: "0", 27: "0",
             39: "(None)", 46: "0", 47: "199", 48: "5", 49: "Blue", 51: "200000", 52: "200000"}.items():
    new[c] = x
rows_of(V.AB, "1299972").append(new)
LOG.append("ability[1299972] 追加行#2: c47=199 PoisonStrength 全队(水) +200%（克劳斯在队时中毒伤害提升，数值可调）")
cas_edit("desc_override_claude_wolf_assassin_ex_2", [("强化中毒：中毒伤害大幅提升", "强化中毒：水属性角色毒伤害+200%")], "强化中毒写成具体数值")

# 文案：协力球、白虎图标
skill_text("129991", "psychic_yuki_swim", [("赋予水属性角色及协力球屏障", "赋予水属性角色屏障")], "屏障/抗性只给角色，删『及协力球』")
skill_text("139991", "outlaw_panther_moon", [("赋予队伍全体及协力球直接攻击伤害提升", "赋予队伍全体直接攻击伤害提升")], "直伤/连击只给角色，删『及协力球』")
skill_text("129995", "wander_armor_water_playable", [("赋予水属性角色及协力球攻击力提升", "赋予水属性角色攻击力提升")], "攻击/抗性只给角色，删『及协力球』")
cas_edit("desc_override_white_tiger_ghost_playable_5",
         [("\n" + ICON + "与风属性角色合击时，自身视为风属性", "\n自身作为合击角色与风属性主要角色合击时，自身视为风属性")],
         "去掉标反的主位图标")

# 汇总
probs = []
for (lp, key), rs in ROWS.items():
    tb = "leader_ability" if lp == V.LE else "ability"
    for r in rs:
        assert len(r) == (124 if lp == V.LE else 126)
        probs += [f"{key}: {p}" for p in L.client_legality_problems(tb, r)]
        _, iss, _ = P.simulate(tb, r)
        probs += [f"{key}: sim {x}" for x in iss if x[0] not in ("NAN_FLOAT", "EMPTY_INT", "EMPTY_INT_OPT")]
    OUT.setdefault(lp, {})[key] = leaf(T[lp][key], rs)
files = {}
for p, tree in DSLS.items():
    probs += [f"{p}: {x}" for x in W.dsl_signature_problems(tree)]
    enc = encode_tree(tree)
    assert V.wf_dsl.parse_dsl(zlib.decompress(enc, -15))["tree"] == tree, p
    files[V.member(V.wf_dsl.dsl_logical(p))] = enc
print("\n".join(LOG))
print("tables:", {lp.split('/')[-1]: sorted(e) for lp, e in OUT.items()})
print("dsl:", sorted(DSLS))
print("problems:", probs)
if "--write" in sys.argv:
    VER = sys.argv[sys.argv.index("--write") + 1]
    BASE = os.environ["WF_BASE"]
    assert not probs
    for lp, ed in OUT.items():
        b = raw_replace(lp, ed)
        back = V.q.parse_node(b)
        assert set(back) == set(T[lp]) and sorted(k for k in back if back[k] != T[lp][k]) == sorted(ed), lp
        files[V.member(lp)] = b
    name = f"pinball-{BASE}-{VER}-1-panel-fix-1019-local.zip"
    os.makedirs("patch2", exist_ok=True)
    with zipfile.ZipFile(f"patch2/{name}", "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(files):
            zf.writestr(m, files[m])
    blob = open(f"patch2/{name}", "rb").read()
    assert len(blob) <= 5 * 1024 * 1024
    with zipfile.ZipFile(f"patch2/{name}") as zf:
        assert zf.testzip() is None and all(zf.read(m) == files[m] for m in files)
    integ = {"name": name, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(files),
             "files": sorted(files), "member_sha256": {m: hashlib.sha256(files[m]).hexdigest() for m in sorted(files)},
             "applies_on": BASE, "version": VER, "log": LOG}
    open(f"patch2/{name[:-4]}.integrity.json", "w", encoding="utf8").write(json.dumps(integ, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}))
