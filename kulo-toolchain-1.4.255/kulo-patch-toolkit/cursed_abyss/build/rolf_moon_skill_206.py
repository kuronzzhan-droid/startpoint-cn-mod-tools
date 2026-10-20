# -*- coding: utf-8 -*-
"""罗尔夫 149986『月下独奏』技能重做：两段（斩击＋爆击）→ 八段（六连斩＋重斩＋爆击），倍率上调，演出换官方属性色连斩。

叠加在 kulo 1.4.205 视图上 → 1.4.206。默认 dry run；--write 才写 zip / server28 / 设计说明之外的产物。
- 时间轴（帧，60=1秒；同 Block 兄弟 Wait 共原点）：
    0/8/16/24/32/40  六连斩：官方通用斩击 skill_general/area/cutting_left ↔ cutting_right 交替（ResolveByElement 255=随角色属性→_green），
                     节奏照抄官方 gang_girl「千风万刃」（风，左右 8 帧交替）；第 0 帧保留原起手 black_wolf_knight_wt23_slash
    52               重斩：原 black_wolf_knight_wt23_smash（叩きつけ）＋ 官方 cutting_front（brave_mouse 收尾同款）
    64               爆击：原 black_wolf_knight_wt23_explosion，30 帧内期望 10 次命中（与原第二段同参）
  参考点寿命 100→120 帧、停球 70→100 帧以覆盖到 94 帧收尾。
- 每个判定区 params[23]=104（完整直击，damage-type-rules-v1），根头 tree[10] 仍 0。
- 主技能保留 ConditionalsChangeSkillFlag(1) 两支（能力3『威力随连击数提升』= CNA 第 8 位 true）；629 安可无旗号、恒 true，同 1.4.205。
- 削韧(c13)/Fever(c14)/固定项(c5) 按原总量重新分摊：总削韧、总 Fever 不变。
用法：WF_TIP=205 python rolf_moon_skill_206.py [--write]
"""
import copy
import hashlib
import json
import os
import sys
import zipfile
import zlib

os.environ.setdefault("WF_TIP", "205")
from live149 import *  # noqa
import wf_dsl
import wf_mod_tool as M
from wf_character_revision import encode_tree
from dsltools import commands

sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L
import wf_cursed_weapons as W
import base149 as _B

assert TIP == 205, TIP
assert not os.environ.get("WF_EXTRA_ZIPS")
assert all(z.parent == ACTIVE for z in _B._ZIPS)
assert _B._ZIPS[-1].name == "pinball-1.4.204-1.4.205-1-rolf-direct-104-local.zip", _B._ZIPS[-1].name

OUT = Path(__file__).resolve().parent.parent
NAME = "pinball-1.4.205-1.4.206-1-rolf-moon-skill-rework-local.zip"
AS_LP = "master/skill/action_skill.orderedmap"
TX_LP = "master/character/character_text.orderedmap"
SRV_SRC = OUT / "server26/character_text.json"     # = kulo assets/cdndata 现值
SRV_DST = OUT / "server28/character_text.json"
NL = chr(10)
CID, CODE = "149986", "black_wolf_knight_moon"
P1 = "battle/action/skill/action/rare5/black_wolf_knight_moon$black_wolf_knight_moon_1"
P2 = "battle/action/skill/action/rare5/black_wolf_knight_moon$black_wolf_knight_moon_2"
PE = "battle/action/skill/action/ability_skill/ability_skill_wolf_moon_encore$ability_skill_wolf_moon_encore"
FX = "battle/effect/skill_unique/black_wolf_knight_wt23/black_wolf_knight_wt23_"
GEN = "battle/effect/skill_general/area/"
LOG: list[str] = []

assert hashlib.sha256(SRV_SRC.read_bytes()).hexdigest() == hashlib.sha256((KULO / "assets/cdndata/character_text.json").read_bytes()).hexdigest()


def V(lo, hi=None):
    return [{"min": lo, "max": lo if hi is None else hi}]


# ---------------------------------------------------------------- 倍率设计（每段，SLv1→满级）
# 原：lv1 25 + 0.9×10 = 34；lv2 {33→38} + {1.13→1.3}×10 = 44.3→51
# 新：lv2 满级 6×4.0 + 36 + 10×2.0 = 80，SLv1 取 0.875 = 70；lv1 固定 = 满级×0.7 = 56
SPEC = {
    "1": {"slash": V(2.8), "finisher": V(25.2), "blast": V(1.4)},
    "2": {"slash": V(3.5, 4.0), "finisher": V(31.5, 36), "blast": V(1.75, 2.0)},
}
SPEC["encore"] = SPEC["2"]          # 629 一直镜像 lv2 数值（ALv 插值）
# 削韧 / Fever / 固定项：原主技能 10+1×10=20 / 5+0.5×10=10 / 200+3×10；安可 1.5+0.1×10=2.5 / 10
BREAK = {"main": {"slash": 1, "finisher": 4, "blast": 1}, "encore": {"slash": 0.1, "finisher": 0.9, "blast": 0.1}}
FEVER = {"slash": 0.5, "finisher": 2, "blast": 0.5}
FIXED = {"slash": 20, "finisher": 80, "blast": 3}
SLASH_FRAMES = [0, 8, 16, 24, 32, 40]
F_FIN, F_BLAST = 52, 64
RP_LIFE, STOP = 120, 100


def total(spec, key):
    return round(6 * spec["slash"][0][key] + spec["finisher"][0][key] + 10 * spec["blast"][0][key], 4)


def cmd(*a):
    return ["Command", list(a)]


def wait(n, body):
    return ["Event", ["Wait", n, "*", ["Block", body]]]


def show(label, eff, scale):
    """挂参考点 1（静止，CD=朝目标方向；原技能同写法），不追踪。"""
    return cmd("ShowEffect", label, eff, 1, ["ForesideOfCharacter"], ["PlayOnlyFirstSequence"], ["CD"], 0, 0, 0,
               False, False, ["Some", V(scale)])


def by_elem(name):
    return ["ResolveByElement", GEN + name, 255]


def direct(name):
    return ["SpecifyEffectDirectly", FX + name]


def build(t0, mode):
    """mode: '1' / '2' 主技能，'encore' 629。只重写参考点体，FindAll 两段 buff 原样。"""
    t = copy.deepcopy(t0)
    rps = list(commands(t, "CreateReferencePoint"))
    assert len(rps) == 1
    rp = rps[0][1]
    assert rp[1] == -18 and rp[2] == ["GH", 0] and rp[4] == -250 and rp[9] == 100 and rp[10] == 1, rp[:11]
    body = rp[11][1]
    has = [c for pp, c in commands(rp[11], "CreateHitArea")]
    assert len(has) == 2 and [c[24] for c in has] == [104, 104]
    ha_hit, ha_blast = has
    assert ha_hit[13] == ["SpecifyHitAreaLifetimeDirectly", 10] and ha_hit[14] == ["CalculatedUsingMaxNumOfHits", 1]
    assert ha_blast[13] == ["SpecifyHitAreaLifetimeDirectly", 30] and ha_blast[14] == ["CalculatedUsingMaxNumOfHits", 10]
    head = body[0]
    if mode == "encore":
        assert head[1][0] == "MoveBall", head
    else:
        assert head[1][0] == "StopBall" and head[1][2] == 70, head
        head = copy.deepcopy(head); head[1][2] = STOP
    open_fx = body[1]
    assert open_fx[1][0] == "ShowEffect" and open_fx[1][2] == direct("slash")
    assert [n[0] for n in body] == ["Command", "Command", "Event", "Event"]

    flagged = mode != "encore"
    spec = SPEC[mode]
    brk = BREAK["encore" if mode == "encore" else "main"]

    # 母本 CNA（取 then 支 / 安可唯一支），校验与 1.4.205 的数值一致
    def cnas(ha):
        return [c for pp, c in commands(ha[23], "CreateNormalAttack")]
    c_hit, c_blast = cnas(ha_hit), cnas(ha_blast)
    assert len(c_hit) == len(c_blast) == (2 if flagged else 1)
    old = {"1": (V(25), V(0.9)), "2": (V(33, 38), V(1.13, 1.3)), "encore": (V(33, 38), V(1.13, 1.3))}[mode]
    assert all(c[6] == old[0] for c in c_hit) and all(c[6] == old[1] for c in c_blast), mode
    if flagged:
        assert [c[8] for c in c_hit] == [True, False] and [c[8] for c in c_blast] == [True, False]
    else:
        assert c_hit[0][8] is True and c_blast[0][8] is True

    hid = [10]

    def hit_area(tpl, part, life, n, on_create):
        h = copy.deepcopy(tpl)
        a, b, c = hid[0], hid[0] + 1, hid[0] + 2
        hid[0] += 3
        h[13] = ["SpecifyHitAreaLifetimeDirectly", life]
        h[14] = ["CalculatedUsingMaxNumOfHits", n]
        h[19], h[20], h[21], h[22] = a, ["Block", on_create], b, c
        for pp, x in commands(h[23], "CreateNormalAttack"):
            x[1] = c
            x[5] = FIXED[part]
            x[6] = copy.deepcopy(spec[part])
            x[13] = V(brk[part])
            x[14] = V(FEVER[part])
        assert h[24] == 104 and h[2] == 1
        return cmd(*h)

    new_body = [head, open_fx]
    for i, f in enumerate(SLASH_FRAMES):
        name = "cutting_left" if i % 2 == 0 else "cutting_right"
        seg = [show("斬撃%d" % (i + 1), by_elem(name), 3),
               hit_area(ha_hit, "slash", 8, 1, [cmd("ShakeCamera", 1)])]
        new_body += seg if f == 0 else [wait(f, seg)]
    new_body.append(wait(F_FIN, [show("叩きつけ", direct("smash"), 4), show("正面斬撃", by_elem("cutting_front"), 4),
                                  hit_area(ha_hit, "finisher", 10, 1, [cmd("ShakeCamera", 2)])]))
    bl = hit_area(ha_blast, "blast", 30, 10, [])
    new_body.append(wait(F_BLAST, [show("爆発", direct("explosion"), 4), bl]))
    rp[11][1] = new_body
    rp[9] = RP_LIFE
    # 爆击判定区 onHit 保留原 ShakeCamera 1
    assert bl[1][23][1][0] == cmd("ShakeCamera", 1)
    return t


def checks(p, t):
    probs = W.dsl_signature_problems(t)
    probs += L.action_dsl_subject_binding_problems(t)
    probs += L.action_dsl_lookup_scope_problems(t)
    probs += L.action_dsl_hit_area_target_problems(t)
    probs += L.action_dsl_element_problems(t, 3)
    assert not probs, (p, probs)
    has = [c for pp, c in commands(t, "CreateHitArea")]
    assert len(has) == 8 and all(c[24] == 104 for c in has) and t[10] == 0
    # CD 只挂在参考点 1 / 判定区上（不挂敌人/球/角色）
    for pp, c in commands(t, "ShowEffect"):
        assert c[3] == 1 and c[6] == ["CD"], c
    ids = [x for c in has for x in (c[19], c[21], c[22])]
    assert len(ids) == len(set(ids)) and not set(ids) & {0, 1, 8, 9}
    return W.dsl_capabilities(t)


DSL0 = {p: dsl_tree(p) for p in (P1, P2, PE)}
for p in DSL0:
    assert not W.dsl_signature_problems(DSL0[p])
NEW = {P1: build(DSL0[P1], "1"), P2: build(DSL0[P2], "2"), PE: build(DSL0[PE], "encore")}
files: dict[str, bytes] = {}
REPORT: dict = {}


def same_outside_rp(a, b):
    """参考点体外（FindAll 两段 buff、根头、FindNear）逐值不变。"""
    a, b = copy.deepcopy(a), copy.deepcopy(b)
    for t in (a, b):
        rp = list(commands(t, "CreateReferencePoint"))[0][1]
        rp[9] = None; rp[11] = None
    return a == b


for p, t in NEW.items():
    caps = checks(p, t)
    assert caps, "104 必须被识别为客户端能力需求"
    assert same_outside_rp(t, DSL0[p]), p
    enc = encode_tree(t)
    assert wf_dsl.parse_dsl(zlib.decompress(enc, -15))["tree"] == t, p
    raw0, src = read_raw(wf_dsl.dsl_logical(p))
    assert len(enc) < 4 * len(raw0), (p, len(enc), len(raw0))   # 防包装壳膨胀
    files[wf_dsl.dsl_logical(p)] = enc
    mode = {P1: "1", P2: "2", PE: "encore"}[p]
    REPORT[p.split("$")[1]] = {"logical": wf_dsl.dsl_logical(p), "member": member(wf_dsl.dsl_logical(p)), "source": src,
                               "hit_areas": "2 -> 8", "params23": 104, "requires": caps,
                               "total_mult_slv_min": total(SPEC[mode], "min"), "total_mult_slv_max": total(SPEC[mode], "max"),
                               "before_sha256": hashlib.sha256(raw0).hexdigest(), "after_sha256": hashlib.sha256(enc).hexdigest(),
                               "before_size": len(raw0), "after_size": len(enc)}
assert total(SPEC["1"], "max") == 56 and total(SPEC["2"], "min") == 70 and total(SPEC["2"], "max") == 80
LOG.append("罗尔夫 149986 black_wolf_knight_moon_1/_2 + 629 ability_skill_wolf_moon_encore：参考点体重写为 六连斩(0/8/16/24/32/40 帧) + 重斩(52) + 爆击(64, 30 帧期望 10 击)；"
           "判定区 2→8 个，全部 params[23]=104；lv1 34→56、lv2 44.3→51 改 70→80、安可同 lv2；FindAll 两段 buff 与根头逐值不变")

# ---------------------------------------------------------------- 文本六处
OLD_TXT = "向距离最近的敌人挥出斩击，并在其后追加爆击，对命中的敌人及其周围造成风属性伤害（两段均以直接攻击伤害判定）／赋予队伍贯穿效果与最大速度固定效果／赋予风属性角色直接攻击伤害提升效果"
NEW_TXT = "向距离最近的敌人发动连续斩击，最后挥出重斩并引发爆击，对命中的敌人及其周围造成风属性伤害（全段均以直接攻击伤害判定）／赋予队伍贯穿效果与最大速度固定效果／赋予风属性角色直接攻击伤害提升效果"
T = {lp: load(lp) for lp in (AS_LP, TX_LP)}
g = copy.deepcopy(T[AS_LP][CODE]); assert list(g) == ["1", "2"]
for lv in ("1", "2"):
    r = row(g[lv]); assert r[1] == OLD_TXT, r[1]
    r2 = list(r); r2[1] = NEW_TXT
    g[lv] = join(r2) + (NL if g[lv].endswith(NL) else "")
    assert row(g[lv]) == r2 and [j for j in range(len(r)) if r[j] != r2[j]] == [1]
tx = rows(T[TX_LP][CID])[0]
assert tx[5] == tx[7] == OLD_TXT
tx2 = list(tx); tx2[5] = tx2[7] = NEW_TXT
v = T[TX_LP][CID]
nv = join(tx2) + (NL if v.endswith(NL) else "")
assert rows(nv)[0] == tx2
EDIT = {AS_LP: {CODE: g}, TX_LP: {CID: nv}}


def raw_replace(lp, edits):
    raw, _ = read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    for k, node in edits.items():
        assert q.build_node(load(lp)[k]) == rows0[keys0.index(k)], (lp, k)
        om.rows[om.keys.index(k)] = q.build_node(node)
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys == keys0
    assert [i for i in range(len(rows0)) if back.rows[i] != rows0[i]] == sorted(keys0.index(k) for k in edits)
    return out


for lp, ed in EDIT.items():
    files[lp] = raw_replace(lp, ed)
    back = q.parse_node(files[lp])
    assert set(back) == set(T[lp]) and sorted(k for k in T[lp] if back[k] != T[lp][k]) == sorted(ed), lp
    LOG.append(f"{lp}：改动键 {sorted(ed)}；其余 {len(T[lp]) - len(ed)} 键 chunk 逐字节保留")

old_srv = SRV_SRC.read_text("utf-8")
SRV = json.loads(old_srv)
assert SRV[CID][0] == tx, "服务端与客户端 character_text 不一致"
oj, nj = json.dumps(OLD_TXT, ensure_ascii=False), json.dumps(NEW_TXT, ensure_ascii=False)
assert old_srv.count(oj) == 2, old_srv.count(oj)
new_srv = old_srv.replace(oj, nj)
jo, jn = json.loads(old_srv), json.loads(new_srv)
assert set(jo) == set(jn) and sorted(k for k in jo if jo[k] != jn[k]) == [CID] and jn[CID][0] == tx2
LOG.append(f"技能文本六处（action_skill 两档 c1、character_text c5/c7、服务端 cdndata [5]/[7]）统一为「{NEW_TXT}」")


def main():
    members = {member(lp): d for lp, d in files.items()}
    print(json.dumps(REPORT, ensure_ascii=False, indent=1))
    print("\n".join(LOG))
    if "--write" not in sys.argv:
        print(f"DRY RUN: {NAME} {len(members)} members")
        return 0
    SRV_DST.parent.mkdir(exist_ok=True)
    SRV_DST.write_bytes(new_srv.encode("utf-8"))
    path = OUT / "patch" / NAME
    assert not path.exists(), path
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    assert len(blob) <= 5 * 1024 * 1024
    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None
        a = q.parse_node(zf.read(member(AS_LP))); t2 = q.parse_node(zf.read(member(TX_LP)))
    six = [row(a[CODE]["1"])[1], row(a[CODE]["2"])[1], rows(t2[CID])[0][5], rows(t2[CID])[0][7], jn[CID][0][5], jn[CID][0][7]]
    assert set(six) == {NEW_TXT}
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "files": sorted(members), "member_sha256": {m: hashlib.sha256(members[m]).hexdigest() for m in sorted(members)},
             "logical_paths": {member(lp): lp for lp in sorted(files)}, "new_files": [],
             "server_files": {"assets/cdndata/character_text.json": {"copy": "server28/character_text.json",
                                                                      "sha256": hashlib.sha256(SRV_DST.read_bytes()).hexdigest()}},
             "applies_on": "1.4.205", "version": "1.4.206", "requires_client": ["damage-type-rules-v1"],
             "texts": {"before": OLD_TXT, "after_all_six": NEW_TXT}, "report": REPORT,
             "checks": {"dsl_signature_problems": 0, "subject_binding": 0, "lookup_scope": 0, "hit_area_target": 0,
                        "element": 0, "encode_roundtrip": True},
             "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    print(json.dumps(integ["logical_paths"], ensure_ascii=False, indent=1))
    print("server28", integ["server_files"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
