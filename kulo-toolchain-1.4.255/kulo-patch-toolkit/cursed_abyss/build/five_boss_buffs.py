# -*- coding: utf-8 -*-
"""五重决战（boss_battle_quest 1/99 全 39 关）再削弱 + boss 增益 + 登场负面。叠加在 1.4.185 上。
1) quest c99（boss HP 倍率）×0.5；
2) 每只 boss 的 general_boss c109 出场动作末尾追加 five_boss_buffs$entrance：
   自身：弱体抗性 +75%（永续不可驱散）、全属性耐性 +1.0（永续不可驱散，=受伤减半）、12 个全属性耐性 +1.5（可驱散，各自独立键）；
   全体角色（强制付与、可驱散、30 秒）：攻击力 -30%、全属性耐性 -30%（防御降低）、技能槽充能 -30%（疲惫）、技能伤害 -30%；
3) 五重外也在用的官方 boss 键（administrator_light_multi_80 / yokai_emaki_middle_boss_multi）先克隆成 mod_fb3_* 再只在五重 zone 里改指向。"""
import copy, hashlib, json, os, zipfile, zlib
os.environ.setdefault("WF_TIP", "186")
from live149 import *  # noqa
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv
import sys
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_cursed_weapons as W

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.185-1.4.186-1-five-boss-buffs-local.zip"
LP = {"q": "master/quest/boss_battle_quest.orderedmap", "fd": "master/battle/field_data.orderedmap",
      "zone": "master/battle/zone.orderedmap", "gb": "master/battle/boss/general_boss.orderedmap",
      "bl": "master/battle/boss/boss_level.orderedmap", "var": "master/battle/boss/general_boss_variable.orderedmap"}
PROG = "battle/action/enemy/action/mod/five_boss_v3/fb3_buff$entrance"
NL = chr(10)
FOREVER, DEBUFF_T = 9999999, 1800


def S(v):
    return [{"min": v, "max": v}]


def leaf(v, rs):
    s = _csv(rs)
    return s if v.endswith(NL) else s.rstrip(NL)


def cc(subject, ac, key, cancelable, force):
    return ["Command", ["CreateCondition", subject, [ac], S(1), ["GenericConditionHitEffect"], cancelable, False, key, None,
                        False, 3, S(1), force]]


def entrance_tree():
    me = [cc(-17, ["ACToleranceOfDebuff", S(FOREVER), S(0.75), S(1)], "fb3_debuff_res", False, True),
          cc(-17, ["ACToleranceOfElement", S(FOREVER), 254, S(1.0), S(1)], "fb3_half", False, True)]
    me += [cc(-17, ["ACToleranceOfElement", S(FOREVER), 254, S(1.5), S(1)], f"fb3_def_{i}", True, True) for i in range(12)]
    deb = [cc(0, ["ACAttackPoint", S(DEBUFF_T), S(-0.3), S(1)], "fb3_atk_down", True, True),
           cc(0, ["ACToleranceOfElement", S(DEBUFF_T), 254, S(-0.3), S(1)], "fb3_def_down", True, True),
           cc(0, ["ACSkillGaugeCharging", S(DEBUFF_T), S(-0.3), S(1)], "fb3_weary", True, True),
           cc(0, ["ACSkillDamage", S(DEBUFF_T), S(-0.3), S(1)], "fb3_skill_down", True, True)]
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, ["Block", me + [
        ["Command", ["FindAllSubjects", 0, 33, [], [], [], [], [], ["DoNothing"], ["Block", deb]]]]]]


def main():
    T = {k: load(v) for k, v in LP.items()}
    BASE = copy.deepcopy(T)
    files, log = {}, []
    folder = T["q"]["1"]["99"]
    quests, zones = [], set()
    for k, v in folder.items():
        r = rows(v)[0]
        old = r[99]
        r[99] = f"{float(old) / 2:.15g}"
        folder[k] = leaf(v, [r])
        quests.append((r[0], old, r[99]))
        zk = row(T["fd"][r[109]])[2]
        assert zk in T["zone"], zk
        zones.add(zk)
    assert len(quests) == 39
    bosses = set()
    for zk in zones:
        for zz, zv in T["zone"][zk].items():
            for x in row(zv)[22:34]:
                if x in T["gb"]:
                    bosses.add(x)
    shared = {}
    for b in sorted(bosses):
        if b.startswith("mod_"):
            continue
        users = [zk for zk, zd in T["zone"].items() for v in zd.values() if b in row(v)[22:34]]
        if any(u not in zones for u in users):
            nk = "mod_fb3_" + b
            assert nk not in T["gb"]
            shared[b] = nk
            T["gb"][nk] = copy.deepcopy(T["gb"][b])
            T["bl"][nk] = T["bl"][b]
            if b in T["var"]:
                T["var"][nk] = copy.deepcopy(T["var"][b])
    for zk in zones:
        for zz, zv in list(T["zone"][zk].items()):
            r = row(zv)
            hit = False
            for i in range(22, 34):
                if r[i] in shared:
                    r[i] = shared[r[i]]
                    hit = True
            if hit:
                T["zone"][zk][zz] = leaf(zv, [r])
    targets = {shared.get(b, b) for b in bosses}
    nrows = 0
    for b in sorted(targets):
        for kk, v in T["gb"][b].items():
            r = row(v)
            progs = [p for p in r[109].split(",") if p]
            assert PROG not in progs
            progs.append(PROG)
            r[109] = ",".join(progs)
            T["gb"][b][kk] = leaf(v, [r])
            nrows += 1
    tree = entrance_tree()
    pr = W.dsl_signature_problems(tree)
    assert not pr, pr
    d = encode_tree(tree)
    assert wf_dsl.parse_dsl(zlib.decompress(d, -15))["tree"] == tree
    files[wf_dsl.dsl_logical(PROG)] = d
    for k, lp in LP.items():
        if T[k] == BASE[k]:
            continue
        data = q.build_node(T[k])
        back = q.parse_node(data)
        assert back == T[k] and set(BASE[k]) <= set(back)
        files[lp] = data
    members = {member(lp): x for lp, x in files.items()}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    assert len(blob) <= 5 * 1024 * 1024, len(blob)
    log.append(f"39 关 c99 ×0.5（相对原始 ×0.25）")
    log.append(f"{len(targets)} 个 boss 键 / {nrows} 行 general_boss c109 追加 {PROG}")
    log.append(f"克隆共享官方键：{shared}")
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.185", "version": "1.4.186",
             "quests": quests, "bosses": sorted(targets), "log": log}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + NL, "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    print(NL.join(log))


if __name__ == "__main__":
    main()
