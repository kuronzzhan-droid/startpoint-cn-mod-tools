# -*- coding: utf-8 -*-
"""单伤害类型木人 v2（叠加在 kulo 1.4.155 上）：
1) 4 个单体木人（1103–1106）HP 提到约 90 万亿（只改各自 boss_level 行）；
2) 「结实假人们」入口新增 4 个多体版（1107–1110，大木人 + 4 个小木人），克隆 1102 链路；
   小木人与大木人同 HP、同样的三类免疫 / 全伤害 -50% / 3 攻击 +3 防御，全部永续不可驱散。

HP 上限依据（客户端反编译，FFDec 导出 worldflipper_android_release.swf）：
- EnemySourceBase：hp = FloatInt.floor(375 × PartyAtk × HitHpBasic × hits × c3 × correction × questHP × scale)，全程 Number；
- EnemyImpl：HealthPointGaugeImpl(this, Decimal100.fromFloatInt(source.hp)) —— 血量以「HP×100」的 Number 定点保存
  （Decimal100.RESOLTION=100，_new = Math.round）；扣血/比例/血条颜色全走 Number，未见 int 截断；
- ⇒ 精确整数上限 = HP×100 < 2^53 ⇒ HP ≤ 90,071,992,547,409。取 boss 89,991,002,730,251、小木人 89,990,995,368,653
  （命中数列保持 32938902 在 int32 内，倍率放在浮点系数列 c3）。

用法：WF_TIP=155 python typed_dummies_v2.py
"""
import copy
import hashlib
import json
import math
import os
import shutil
import zipfile

os.environ.setdefault("WF_TIP", "155")
from live149 import *  # noqa
import wf_cursed_weapons_r4 as W
import wf_dsl
from wf_character_revision import encode_tree
from stage_all import csv_text as _csv, detect_style, dump_like
import typed_dummies as V1

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.155-1.4.156-1-typed-dummies-v2-local.zip"
HITS = "32938902"
BOSS_C3, FUNNEL_C3 = "90", "152.8048"
LIMIT = 2 ** 53 // 100
SRC_MULTI_QUEST, SRC_MULTI_KEY, SRC_FUNNEL = "1102", "practice_waraboss_tough_funnel_colorless", "funnel_waraboss_tough_colorless"
MULTI = {"1107": "direct", "1108": "ability", "1109": "skill", "1110": "pf"}
SLUG = {v[0]: (k, v[1], v[2]) for k, v in V1.TYPES.items()}     # slug: (单体 quest, 中文, 唯一可伤类型)
LP = dict(V1.LP, funnel="master/battle/boss/funnel/general_funnel.orderedmap",
          flevel="master/battle/boss/funnel_level.orderedmap")


def csv_text(rows_, like):
    s = _csv(rows_)
    return s if like.endswith("\n") else s.rstrip("\n")


def hp(c2: str, c3: str, corr: float) -> int:
    return math.floor(375 * 6 * 1 * float(c2) * float(c3) * corr * 1 * 1 + 1e-10 + 1e-10)


def multi_dsl(only: str, funnel: str) -> list:
    body = [c for c in V1.dsl(only)[11][1]]          # 同一组 CreateCondition（主体 -17）
    for c in body:                                  # 改成 FindAllSubjects 绑定 0（全体敌方单位，官方 anv3 field_start 同形）
        c[1][1] = 0
    return ["ActionDsl", 1, ["None"], False, False, False, False, False, False, False, 0, ["Block", [
        ["Command", ["SpawnFunnel", ["Funnel", funnel], 4, ["FunnelGroup", 1], []]],
        ["Event", ["Wait", 2, "*", ["Block", [
            ["Command", ["FindAllSubjects", 0, 51, [], [], [], [], [], ["DoNothing"], ["Block", body]]]]]]]]]]


def main() -> int:
    T = {k: load(v) for k, v in LP.items()}
    base = {k: load(v) for k, v in LP.items()}
    files, report = {}, {"single": [], "multi": []}
    # 1) 单体 HP
    for slug, (qid, cn, only) in SLUG.items():
        key = f"practice_typed_dummy_{slug}"
        lv = row(T["level"][key])
        assert lv[2] == V1.HITS and lv[3] == "1", lv
        lv[2], lv[3] = HITS, BOSS_C3
        T["level"][key] = csv_text([lv], T["level"][key])
        h = hp(HITS, BOSS_C3, 13.491646245)
        assert h <= LIMIT
        report["single"].append({"quest": qid, "key": key, "hp": h})
    # 2) 多体版
    src_q = row(T["practice"][SRC_MULTI_QUEST])
    orders = [int(row(v)[1]) for v in T["practice"].values() if row(v)[0] == src_q[0]]
    for n, (qid, slug) in enumerate(MULTI.items()):
        _single, cn, only = SLUG[slug]
        key, fkey = f"practice_typed_dummies_{slug}", f"funnel_typed_dummy_{slug}"
        assert qid not in T["practice"]
        for k in ("field", "zone", "boss", "level"):
            assert key not in T[k]
        for k in ("funnel", "flevel"):
            assert fkey not in T[k]
        r = list(src_q)
        assert r[0] == "99" and r[110] == SRC_MULTI_KEY and r[99] == "100" and r[100] == "100"
        r[1], r[2], r[99], r[100], r[110] = str(max(orders) + 1 + n), f"仅{cn}木人们·无", "1", "1", key
        T["practice"][qid] = csv_text([r], T["practice"][SRC_MULTI_QUEST])
        f = row(T["field"][SRC_MULTI_KEY]); f[2] = key
        T["field"][key] = csv_text([f], T["field"][SRC_MULTI_KEY])
        z = row(T["zone"][SRC_MULTI_KEY]["0"]); assert z[24] == z[26] == SRC_MULTI_KEY
        z[24] = z[26] = key
        T["zone"][key] = {"0": csv_text([z], T["zone"][SRC_MULTI_KEY]["0"])}
        program = f"{V1.DSL_DIR}$multi_{slug}"
        b = row(T["boss"][SRC_MULTI_KEY]["100"])
        assert b[109].endswith("$funnel_colorless")
        b[1], b[109] = f"仅{cn}木人们", program
        T["boss"][key] = {"100": csv_text([b], T["boss"][SRC_MULTI_KEY]["100"])}
        lv = row(T["level"][SRC_MULTI_KEY]); lv[2], lv[3] = HITS, BOSS_C3
        T["level"][key] = csv_text([lv], T["level"][SRC_MULTI_KEY])
        T["funnel"][fkey] = copy.deepcopy(T["funnel"][SRC_FUNNEL])
        fl = row(T["flevel"][SRC_FUNNEL]); assert fl[4] == "hit_hp_correction_funnel"
        fl[2], fl[3] = HITS, FUNNEL_C3
        T["flevel"][fkey] = csv_text([fl], T["flevel"][SRC_FUNNEL])
        tree = multi_dsl(only, fkey)
        assert not W.dsl_signature_problems(tree), W.dsl_signature_problems(tree)
        files[wf_dsl.dsl_logical(program)] = encode_tree(tree)
        bh, fh = hp(HITS, BOSS_C3, 13.491646245), hp(HITS, FUNNEL_C3, 7.9464)
        assert bh <= LIMIT and fh <= LIMIT
        report["multi"].append({"quest": qid, "name": r[2], "key": key, "funnel": fkey, "boss_hp": bh, "funnel_hp": fh,
                                "dsl": program})
    for k, lp in LP.items():
        if T[k] == base[k]:
            continue
        data = q.build_node(T[k])
        back = q.parse_node(data)
        assert back == T[k]
        changed = [x for x, v in base[k].items() if back[x] != v]
        assert k == "level" or not changed, (k, changed)
        files[lp] = data
    members = {member(lp): d for lp, d in files.items()}
    path = OUT / "patch" / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "applies_on": "1.4.155", "version": "1.4.156"}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    # 服务端 practice_quest.json
    name = "practice_quest.json"
    raw = (ASSETS / name).read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    value = json.loads(text)
    s7 = OUT / "server7"
    if s7.exists():
        shutil.rmtree(s7)
    s7.mkdir()
    for m in report["multi"]:
        assert m["quest"] not in value
        e = copy.deepcopy(value[SRC_MULTI_QUEST]); e["name"] = m["name"]
        value[m["quest"]] = e
    style = detect_style(text)
    if dump_like(json.loads(text), style) == text:
        out = dump_like(value, style)
    else:
        end = len(text.rstrip()); prefix_end = len(text[:end - 1].rstrip())
        mt = json.dumps({m["quest"]: value[m["quest"]] for m in report["multi"]}, ensure_ascii=False, indent=2).splitlines()[1:-1]
        out = text[:prefix_end] + ",\n" + "\n".join(mt) + text[prefix_end:]
    assert json.loads(out) == value
    (s7 / name).write_bytes((out.replace("\n", "\r\n") if crlf else out).encode("utf-8"))
    print(json.dumps({"zip": {k: integ[k] for k in ("name", "size", "sha256", "members")}, **report}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
