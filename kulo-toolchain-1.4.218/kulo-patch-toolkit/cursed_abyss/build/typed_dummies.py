# -*- coding: utf-8 -*-
"""练习关「结实假人」入口新增 4 个单伤害类型木人（无属性，HP≈9999亿，10 分钟），叠加在 kulo 1.4.154 视图上。

每个木人 = 新练习关（practice_quest 1103–1106，入口 100「结实假人」）→ 新 field_data / zone → 新 general_boss（克隆
practice_waraboss_tough_colorless，c109 pre_action 挂本脚本生成的 DSL，c110 rerun=true）→ 新 boss_level（只改命中数列让 HP≈9999亿）。

开场 DSL（照官方 funnel_epuration_highest$funnel_buff 形：自身 -17、目标种类 3、9999999 帧、cancelable=false）：
- 另外三类伤害耐性 +100%（ACxxxDamageResistance 1.0 = 官方「伤害无效」写法，只剩 1 点保底伤害）；
- 「全部伤害下降 50%」= 全属性耐性（ACToleranceOfElement 254）+0.97，与 3 个「防御力提升」各 +0.01 合计 1.0 ⇒ 受到伤害 ÷2；
- 3 个「攻击力提升」= ACAttackPoint +10%（各自独立键串，三个独立状态）；
全部永续（9999999 帧 ≈ 46 小时）、不可驱散。

用法：WF_TIP=154 python typed_dummies.py
"""
import copy
import hashlib
import json
import os
import shutil
import zipfile

os.environ.setdefault("WF_TIP", "154")
from live149 import *  # noqa
import wf_cursed_weapons_r4 as W
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv, detect_style, dump_like


def csv_text(rows_, like=None):
    s = _csv(rows_)
    nl = chr(10)
    return s if (like is None or like.endswith(nl)) else s.rstrip(nl)

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.154-1.4.155-1-typed-dummies-local.zip"
SRC_QUEST, SRC_KEY = "1101", "practice_waraboss_tough_colorless"
HITS = "32938902"                  # 375×6×HITS×1×13.491646245 = 999,900,030,336（≥9999亿，Number 精确整数）
FRAMES = 9999999
DSL_DIR = "battle/action/enemy/action/boss_waraboss/boss_typed_waraboss"
TYPES = {   # qid: (slug, 中文, 唯一可伤的类型)
    "1103": ("direct", "直击", "ACDirectAttackDamageResistance"),
    "1104": ("ability", "能力", "ACAbilityDamageResistance"),
    "1105": ("skill", "技伤", "ACSkillDamageResistance"),
    "1106": ("pf", "强化弹射", "ACPowerFlipDamageResistance"),
}
ALL_RES = [t[2] for t in TYPES.values()]
LP = {
    "practice": "master/quest/practice/practice_quest.orderedmap",
    "field": "master/battle/field_data.orderedmap",
    "zone": "master/battle/zone.orderedmap",
    "boss": "master/battle/boss/general_boss.orderedmap",
    "level": "master/battle/boss/boss_level.orderedmap",
}


def S(v):
    return [{"min": v, "max": v}]


def cond(ac: list, key: str) -> list:
    return ["Command", ["CreateCondition", -17, [ac], S(1), ["GenericConditionHitEffect"], False, False, key, None,
                        False, 3, S(1), False]]


def dsl(only: str) -> list:
    cmds = [cond([res, S(FRAMES), S(1), S(1)], f"typed_dummy_immune_{i}") for i, res in enumerate(ALL_RES) if res != only]
    cmds.append(cond(["ACToleranceOfElement", S(FRAMES), 254, S(0.97), S(1)], "typed_dummy_damage_down"))
    for i in range(3):
        cmds.append(cond(["ACAttackPoint", S(FRAMES), S(0.1), S(1)], f"typed_dummy_atk_{i}"))
    for i in range(3):
        cmds.append(cond(["ACToleranceOfElement", S(FRAMES), 254, S(0.01), S(1)], f"typed_dummy_def_{i}"))
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, ["Block", cmds]]


def main() -> int:
    T = {k: load(v) for k, v in LP.items()}
    base_T = {k: load(v) for k, v in LP.items()}
    files: dict[str, bytes] = {}
    report = []
    src_q = row(T["practice"][SRC_QUEST])
    folder_orders = [int(row(v)[1]) for v in T["practice"].values() if row(v)[0] == src_q[0]]
    for n, (qid, (slug, cn, only)) in enumerate(TYPES.items()):
        key = f"practice_typed_dummy_{slug}"
        for k in ("practice",):
            assert qid not in T[k], qid
        for k in ("field", "zone", "boss", "level"):
            assert key not in T[k], (k, key)
        # practice quest
        r = list(src_q)
        r[1], r[2], r[100], r[110] = str(max(folder_orders) + 1 + n), f"仅{cn}木人·无", "1", key
        assert r[112] == "36000" and r[0] == "100"
        T["practice"][qid] = csv_text([r], T["practice"][SRC_QUEST])
        # field / zone
        f = row(T["field"][SRC_KEY])
        assert f[2] == SRC_KEY
        f[2] = key
        T["field"][key] = csv_text([f], T["field"][SRC_KEY])
        z = row(T["zone"][SRC_KEY]["0"])
        assert z[24] == z[26] == SRC_KEY
        z[24] = z[26] = key
        T["zone"][key] = {"0": csv_text([z], T["zone"][SRC_KEY]["0"])}
        # boss
        program = f"{DSL_DIR}${slug}"
        b = row(T["boss"][SRC_KEY]["100"])
        assert b[0] == "7" and b[109] == "" and b[110] == "false"
        b[1], b[109], b[110] = f"仅{cn}木人", program, "true"
        T["boss"][key] = {"100": csv_text([b], T["boss"][SRC_KEY]["100"])}
        lv = row(T["level"][SRC_KEY])
        assert lv[1] == "hit_hp_basic_normal" and lv[3] == "1.8"
        lv[2], lv[3] = HITS, "1"
        T["level"][key] = csv_text([lv], T["level"][SRC_KEY])
        tree = dsl(only)
        probs = W.dsl_signature_problems(tree)
        assert not probs, probs
        files[wf_dsl.dsl_logical(program)] = encode_tree(tree)
        report.append({"quest": qid, "name": r[2], "field/zone/boss": key, "dsl": program, "only_damage": cn})
    for k, lp in LP.items():
        data = q.build_node(T[k])
        back = q.parse_node(data)
        assert back == T[k] and all(back[x] == v for x, v in base_T[k].items())
        files[lp] = data
    members = {member(lp): d for lp, d in files.items()}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.154", "version": "1.4.155"}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    # 服务端 practice_quest.json：克隆 1101 行，只换名字
    name = "practice_quest.json"
    raw = (ASSETS / name).read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    value = json.loads(text)
    s6 = OUT / "server6"
    if s6.exists():
        shutil.rmtree(s6)
    s6.mkdir()
    for rep in report:
        assert rep["quest"] not in value
        e = copy.deepcopy(value[SRC_QUEST])
        e["name"] = rep["name"]
        value[rep["quest"]] = e
    style = detect_style(text)
    if dump_like(json.loads(text), style) == text:
        out = dump_like(value, style)
    else:   # 历史混合格式：只在末尾追加成员，其余字节不动（照 revise_practice_clones_1_4_107）
        end = len(text.rstrip())
        assert text[end - 1] == "}"
        prefix_end = len(text[:end - 1].rstrip())
        members_txt = json.dumps({r["quest"]: value[r["quest"]] for r in report}, ensure_ascii=False, indent=2).splitlines()[1:-1]
        out = text[:prefix_end] + ",\n" + "\n".join(members_txt) + text[prefix_end:]
    assert json.loads(out) == value
    (s6 / name).write_bytes((out.replace("\n", "\r\n") if crlf else out).encode("utf-8"))
    print(json.dumps({"zip": {k: integ[k] for k in ("name", "size", "sha256", "members")}, "dummies": report},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
