# -*- coding: utf-8 -*-
"""角色超限 Lv120 · 第二位：休尔特 护花使龙 141099（wind_dragon_wt22）数据补丁。

视图 = kulo 1.4.205 + 1.4.206 + 1.4.207(炎龙王) [+ WF_ROSE_BASE_ZIPS 追加的中间边，如赛瑞斯 1.4.208]。
默认 dry run；--write 写 zip / 服务端 JSON / 报告。版本号由协调分配：WF_ROSE_FROM / WF_ROSE_TO。

改动（只动目标键）：
  action_skill        wind_dragon_wt22 进化 3 档「暴风爱神＋＋」→ 新 DSL _3：去停球、砸地半径 225→300、特效 ×1.4、
                      每敌最多 30 次、倍率 1.6→1.9、自身攻击 +200%
  DSL（新）           ability_skill_wind_dragon_wt22_ol：强化弹射后「爱神旋风」（染色放大的砸地爆炸，按强化弹射伤害）
  特效（新）          ol_pf/（索维特殊 PF 克隆，绿白渐变）、ol_tornado/（单根龙卷）、ol_typhoon/（中心旋涡），均挂 wind_dragon_wt22 目录
  leader_ability      141099 官方行「仅未觉醒」+ 觉醒行（对标四周年希尔媞：全队风攻击 200% 等，含队长位 629 爱神旋风）
  ability             1410991..1410996 官方行「仅未觉醒」+ 觉醒行（约 ×1.25）
  character_status    141099 新增 Lv120
  character_awake_event/status/mission/mission_reward  141099 新增
  character_speech    141099 追加主页 2 行；语音 6 条（存储态 MP3）
服务端（server-rose/）：character_overlimit.json(+141099, 1410991)、mission_char_awake(_reward)_cnmod、character_awake_extension、
  cdndata/character_text.json [8]/[9]
"""
import copy
import hashlib
import json
import os
import sys
import zipfile
import zlib
from pathlib import Path

BUILD = Path(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
OUT = Path(r"D:/WF/out/角色超限-120")
P206 = BUILD.parent / "patch/pinball-1.4.205-1.4.206-1-rolf-moon-skill-rework-local.zip"
P207 = OUT / "patch/pinball-1.4.206-1.4.207-1-overlimit120-wagner-local.zip"
EXTRA = [str(P206), str(P207)] + [z for z in os.environ.get("WF_ROSE_BASE_ZIPS", "").split(";") if z]
os.environ["WF_TIP"] = "205"
os.environ["WF_EXTRA_ZIPS"] = ";".join(EXTRA)
sys.path.insert(0, str(BUILD))
from live149 import *  # noqa: E402,F401
import wf_dsl  # noqa: E402
import wf_mod_tool as M  # noqa: E402
import wf_assets as _assets  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402
from dsltools import commands  # noqa: E402

sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L  # noqa: E402
import wf_cursed_weapons as W  # noqa: E402
import base149 as _B  # noqa: E402

assert [str(z) for z in _B._ZIPS[-len(EXTRA):]] == EXTRA, _B._ZIPS[-len(EXTRA):]
FROM = os.environ.get("WF_ROSE_FROM", "1.4.207")
TO = os.environ.get("WF_ROSE_TO", "1.4.208")
NAME = f"pinball-{FROM}-{TO}-1-overlimit120-rose-dragon-local.zip"
SRV_OUT = OUT / "server-rose"
NL = chr(10)
LOG: list[str] = []
REPORT: dict = {}

CID, CODE = "141099", "wind_dragon_wt22"
NAME_ZH = "休尔特"
LP = {
    "as": "master/skill/action_skill.orderedmap",
    "tx": "master/character/character_text.orderedmap",
    "st": "master/character/character_status.orderedmap",
    "le": "master/ability/leader_ability.orderedmap",
    "ab": "master/ability/ability.orderedmap",
    "aev": "master/mission/character_awake_event.orderedmap",
    "ast": "master/character/character_awake_status.orderedmap",
    "am": "master/mission/character_awake_mission.orderedmap",
    "amr": "master/mission/character_awake_mission_reward.orderedmap",
    "sp": "master/character/character_speech.orderedmap",
}
T = {k: load(v) for k, v in LP.items()}
EDIT: dict[str, dict[str, object]] = {k: {} for k in LP}


def V(lo, hi=None):
    return [{"min": lo, "max": lo if hi is None else hi}]


def cmd(*a):
    return ["Command", list(a)]


def wait(n, body):
    return ["Event", ["Wait", n, "*", ["Block", body]]]


def flat_rows(text):
    return [r for r in rows(text) if r]


def flat_text(rs, like=""):
    return join_rows(rs) + (NL if like.endswith(NL) else "")


def deflate(b):
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    return co.compress(b) + co.flush()


FILES: dict[str, bytes] = {}
FX = f"battle/effect/skill_unique/{CODE}/"

# ======================================================================== 1. 觉醒 PF 特效：仿索维光球 + 单根小龙卷
import rose_pf_fx  # noqa: E402
FX_FILES, FXP, _ = rose_pf_fx.build(read_raw, FX)
for lp in FX_FILES:
    try:
        read_raw(lp)
        raise AssertionError("exists " + lp)
    except FileNotFoundError:
        pass
FILES.update(FX_FILES)
LOG.append(f"特效：{FX}ol_pf/（克隆索维特殊 PF 6 件，亮度→绿白渐变）+ {FX}ol_tornado/（旋风龙 6 根龙卷剥出一根挪到原点，"
           f"去大爆风音效）+ {FX}ol_typhoon/（旋风龙中央大旋涡）共 {len(FX_FILES)} 个文件")

# ======================================================================== 2. 觉醒技能 _3
P2 = f"battle/action/skill/action/rare5/{CODE}${CODE}_2"
P3 = f"battle/action/skill/action/rare5/{CODE}${CODE}_3"
T2 = dsl_tree(P2)
T3 = copy.deepcopy(T2)
body = T3[11][1]
assert body[0] == cmd("StopBall", -18, 70, ["Stop"], ["AB"], 0), body[0]
del body[0]                                                   # 去停球
has = list(commands(T3, "CreateHitArea"))
assert len(has) == 1
ha = has[0][1]
assert ha[9] == ["Circle", V(225)] and ha[14] == ["CalculatedUsingMaxNumOfHits", 20] and ha[15] == ["None"], ha[9:16]
ha[9] = ["Circle", V(300)]
ha[14] = ["CalculatedUsingMaxNumOfHits", 30]
ha[15] = ["Some", V(30)]
cna = list(commands(ha[23], "CreateNormalAttack"))
assert len(cna) == 1 and cna[0][1][6] == V(1.3845, 1.6)
cna[0][1][6] = V(1.6435, 1.9)
for _, c in commands(T3, "ShowEffect"):
    if c[2] == ["SpecifyEffectDirectly", FX + f"{CODE}_explosion"]:
        assert c[12] == ["Some", V(4)]
        c[12] = ["Some", V(5.6)]
    elif c[2] == ["SpecifyEffectDirectly", FX + f"{CODE}_land"]:
        assert c[12] == ["None"]
        c[12] = ["Some", V(1.4)]
conds = list(commands(T3, "CreateCondition"))
assert len(conds) == 1 and conds[0][1][2][0][0] == "ACAttackPoint" and conds[0][1][2][0][2] == V(0.85, 1)
conds[0][1][2][0][2] = V(1.7, 2.0)


def check(tree):
    probs = W.dsl_signature_problems(tree) + L.action_dsl_subject_binding_problems(tree) \
        + L.action_dsl_lookup_scope_problems(tree) + L.action_dsl_hit_area_target_problems(tree) \
        + L.action_dsl_element_problems(tree, 3)
    assert not probs, probs


check(T3)
ENC3 = encode_tree(T3)
assert wf_dsl.parse_dsl(zlib.decompress(ENC3, -15))["tree"] == T3
FILES[wf_dsl.dsl_logical(P3)] = ENC3
REPORT["skill3"] = {"per_target_max_before": 20 * 1.6, "per_target_max_after": 30 * 1.9, "radius": "225→300",
                    "explosion_scale": "4→5.6", "atk_buff": "100%→200%", "stop_ball": "70→去掉"}

SK3_NAME = "暴风爱神＋＋"
SK3_DESC = ("向前方跳跃，操纵旋风使出能斩裂大地的一击，对其周围大范围的敌人造成风属性伤害／赋予自身攻击力大幅提升效果"
            "（技能发动时球不会停止）")
g = copy.deepcopy(T["as"][CODE])
assert list(g) == ["1", "2"]
r2 = row(g["2"])
assert r2[0] == "暴风爱神＋" and r2[7] == P2
r3 = list(r2)
r3[0], r3[1], r3[7] = SK3_NAME, SK3_DESC, P3
g["3"] = join(r3) + (NL if g["2"].endswith(NL) else "")
EDIT["as"][CODE] = g
tx = rows(T["tx"][CID])[0]
assert tx[8] == "(None)" and tx[9] == "(None)", tx[8:10]
tx2 = list(tx)
tx2[8], tx2[9] = SK3_NAME, SK3_DESC
EDIT["tx"][CID] = join(tx2) + (NL if T["tx"][CID].endswith(NL) else "")
LOG.append(f"action_skill {CODE} 新增 3 档 {SK3_NAME}；character_text c8/c9")

# ======================================================================== 3. 觉醒 PF 覆盖（722，仅队长位）：光球 → 首撞爆发 + 12 向龙卷
import math  # noqa: E402
SOVI_PF = "battle/action/power_flip/action/override/override_psycho_reaper_meteor23$override_psycho_reaper_meteor23_lv{}"
SOVI_FX = "battle/effect/powerflip/psycho_reaper_meteor23/psycho_reaper_meteor23_powerflip_attack_special_"
PF_ID = f"{CODE}_overlimit_pf"
PF_DESC_KEY = f"override_string_{PF_ID}"
PF_DESC = "赋予特殊强化弹射"          # 作者 1015：照官方只写一句（索维同类键原文「赋予强化弹射特殊强化效果」）
PF_BASE_PLUS = 5.0                    # 作者 1015：特殊强化弹射爆发「基础倍率+5」= 每档爆发合计倍率 +5
# 作者 1015 二改：①一圈扩散完再下一圈，三圈之后才出台风；②下一次 PF 会把整棵旧 PF 动作删掉
# （SetPowerFilpSuppress 只挡更低档，同档/更高档照发），所以龙卷/台风不能挂在 PF 树里——
# 改由队长技「任一敌方强化弹射命中」→ 629 InvokeSkill 跑独立动作（风巨蜥 149998 / 基诺维 169999 同款通道），
# PF 树只留光球 + 首撞爆发，生命周期回到官方 40 帧。
TOR_MULT = 1.5                                     # 每道龙卷每个敌人 1 下（作者 1015：转 PF 类型、倍率提高 0.8→1.5）
PF_AS = 133   # 判定区 buffTargetAs=133：客户端伤害分类补丁（author-content-1043 damage.py，v28 起带）整体转成「强化弹射 Lv3」，
              # 置 createdByPowerFlipAction、清技能标志 ⇒ 显示/统计/耐性/PF 分档与独立乘区都按强化弹射走
TOR_SPEED = [(0, 20), (12, 10), (26, 4)]           # 基础外推 20×12+10×14+4×19 = 456px
TOR_LIFE = 45
RING_GAP = 40                                      # 每圈间隔：上一圈推完再出下一圈
# (外推倍率, 龙卷缩放, 判定半径, 整圈转角)
WAVES = [(1.0, 2.6, 90, 0.0), (1.3, 3.2, 110, math.pi / 12), (1.6, 3.8, 130, math.pi / 6)]
# 作者 1015 三改：台风与龙卷同步——每圈龙卷出来时中心台风一起出、逐圈放大，每圈台风打 1 下
TY_SCALES, TY_RS, TY_LIFE, TY_MULT = (2.0, 2.8, 3.6), (220, 280, 330), 60, 3.0
SEQ_LIFE = 2 * RING_GAP + TY_LIFE                  # 140 帧
SEQ_CT = 240                                       # CT 4 秒：大于整段时长，龙卷/台风自身的强化弹射伤害不会再触发下一段
REF_ID = 1
ELLIPSE_B = 0.62          # 作者 1015：台风不是正圆，俯视椭圆（横 1 : 纵 0.62），与 rose_pf_fx.TYPHOON_SQUASH 同值


def ellipse_k(theta):
    """朝向 theta（0=向上，顺时针）在横 1、纵 ELLIPSE_B 的椭圆上的半径比例。"""
    return 1 / math.sqrt(math.sin(theta) ** 2 + (math.cos(theta) / ELLIPSE_B) ** 2)


def _attack(tgt, mult):
    return cmd("CreateNormalAttack", tgt, 255, [], [], 0, V(mult), V(0), False, False, False, False, False,
               V(1), V(1), ["Fine"], True)


def tornado_ring(wave, first_id):
    """一圈 12 道龙卷：每道单独一个判定区，朝向 rot、外推速度按椭圆半径缩放 ⇒ 整圈沿椭圆扩散。"""
    k, tor_scale, radius, rot0 = WAVES[wave]
    out = []
    for j in range(12):
        theta = rot0 + j * math.pi / 6
        ek = ellipse_k(theta)
        ha, hit_id, tgt = first_id + 3 * j, first_id + 3 * j + 1, first_id + 3 * j + 2
        moves = [cmd("MoveHitArea", ha, ["CD"], 0, round(v * k * ek, 2), ["None"]) if f == 0
                 else wait(f, [cmd("MoveHitArea", ha, ["CD"], 0, round(v * k * ek, 2), ["None"])])
                 for f, v in TOR_SPEED]
        out.append(cmd(
            "CreateHitArea", "*", REF_ID, ["AB"], 0, 0, theta, False, False, ["Circle", V(radius)], ["Center"],
            ["Center"], ["Single"], ["SpecifyHitAreaLifetimeDirectly", TOR_LIFE],
            ["CalculatedUsingMaxNumOfHits", 1], ["Some", V(1)], False, True, ["None"], ha,
            ["Block", [cmd("ShowEffect", "龙卷", ["SpecifyEffectDirectly", FXP["tornado"][wave]], ha,
                           ["ForesideOfCharacter"], ["UntilTargetTerminates"], ["AB"], 0, 0, 0, True, True,
                           ["Some", V(tor_scale)])] + moves],
            hit_id, tgt, ["Block", [_attack(tgt, TOR_MULT)]], PF_AS, 0, ["None"]))
    return out


def typhoon_wave(w, ha):
    return [
        cmd("ShowEffect", "台风", ["SpecifyEffectDirectly", FXP["typhoon"]], REF_ID, ["BacksideOfCharacter"],
            ["SpecifyEffectLifetimeDirectly", TY_LIFE], ["AB"], 0, 0, 0, False, False, ["Some", V(TY_SCALES[w])]),
        cmd("CreateHitArea", "*", REF_ID, ["AB"], 0, 0, 0, False, False, ["Circle", V(TY_RS[w])], ["Center"], ["Center"],
            ["Single"], ["SpecifyHitAreaLifetimeDirectly", TOR_LIFE], ["CalculatedUsingMaxNumOfHits", 1],
            ["Some", V(1)], False, True, ["None"], ha, ["Block", []], ha + 1, ha + 2,
            ["Block", [_attack(ha + 2, TY_MULT), cmd("ShakeCamera", 1)]], PF_AS, 0, ["None"]),
    ]


def typhoon_seq():
    body = []
    for w in range(len(WAVES)):
        first = REF_ID + 1 + 39 * w
        ring = typhoon_wave(w, first + 36) + tornado_ring(w, first)
        body += ring if w == 0 else [wait(w * RING_GAP, ring)]
    tree = ["ActionDsl", 2, ["None"], False, False, False, False, False, False, False, 3, ["Block", [
        cmd("CreateReferencePoint", -18, ["AB"], 0, 0, 0, False, False, ["Single"], SEQ_LIFE + 2, REF_ID,
            ["Block", body])]]]
    return tree


SEQ_KEY = f"ability_skill_{CODE}_ol_typhoon"
SEQ_PATH = f"battle/action/skill/action/ability_skill/{SEQ_KEY}${SEQ_KEY}"
SEQ_TEXT = "强化弹射命中时卷起龙卷与台风"
SEQ_TREE = typhoon_seq()
check(SEQ_TREE)
_enc = encode_tree(SEQ_TREE)
assert wf_dsl.parse_dsl(zlib.decompress(_enc, -15))["tree"] == SEQ_TREE
FILES[wf_dsl.dsl_logical(SEQ_PATH)] = _enc
REPORT["typhoon_seq"] = {"trigger": "队长技 kind 629 ← 任一敌方强化弹射命中(183)", "ct_frames": SEQ_CT,
                         "rings": [{"start": i * RING_GAP, "reach_px": round(456 * w[0]), "tornado_scale": w[1],
                                    "radius": w[2]} for i, w in enumerate(WAVES)],
                         "typhoon": {"with_each_ring": True, "scales": TY_SCALES, "radius": TY_RS,
                                     "hits_per_ring": 1, "mult": TY_MULT},
                         "tornado_mult": TOR_MULT, "damage_type": "强化弹射 Lv3（判定区 buffTargetAs=133，客户端分类转换补丁）"}
LOG.append(f"DSL {SEQ_PATH}：三圈依次（间隔 {RING_GAP} 帧），每圈 = 中心台风（缩放 {TY_SCALES}，1 下 ×{TY_MULT}）"
           f"+ 12 道椭圆龙卷 ×{TOR_MULT}，共 {SEQ_LIFE} 帧")


PF_FILES, PF_PATHS = {}, []
for lv, n in ((1, "one"), (2, "two"), (3, "three")):
    tree = dsl_tree(SOVI_PF.format(lv))
    s_ = json.dumps(tree, ensure_ascii=False)
    for kind in ("player_", ""):
        old = f"{SOVI_FX}{kind}{n}"
        assert s_.count(f'"{old}"') == 1, (lv, old)
        s_ = s_.replace(f'"{old}"', f'"{FXP["orb" if kind else "burst"][lv]}"')
    assert "psycho_reaper" not in s_
    tree = json.loads(s_)
    hit = [c for c in tree[11][1] if c[0] == "Event" and c[1][0] == "CollisionOfBallAndEnemy"]
    assert len(hit) == 1
    blk = hit[0][1][5][1]
    rp = [i for i, c in enumerate(blk) if c == cmd(*c[1]) and c[1][0] == "CreateReferencePoint"]
    assert len(rp) == 1 and rp[0] == len(blk) - 1, [c[1][0] for c in blk]
    used = {c[19] for _, c in commands(tree, "CreateHitArea")} | {c[21] for _, c in commands(tree, "CreateHitArea")}         | {c[22] for _, c in commands(tree, "CreateHitArea")} | {c[10] for _, c in commands(tree, "CreateReferencePoint")}
    assert used == {1, 2, 3, 4}, used
    # 生命周期保持索维原样（SetPowerFilpSuppress 40 / Wait 38）：龙卷台风不在 PF 树里
    assert blk[1] == cmd("SetPowerFilpSuppress", 40) and blk[3][1][:2] == ["Wait", 38], (blk[1], blk[3][1][:2])
    # 爆发判定（索维原样那一个）：每档合计倍率 +5，按命中上限均摊到每下
    burst = [c for _, c in commands(tree, "CreateHitArea")]
    assert len(burst) == 1 and burst[0][15][0] == "Some", burst
    cap = burst[0][15][1][0]["min"]
    bna = [c for _, c in commands(burst[0][23], "CreateNormalAttack")]
    assert len(bna) == 1
    per0 = bna[0][6][0]["min"]
    per1 = (per0 * cap + PF_BASE_PLUS) / cap
    bna[0][6] = V(per1)
    REPORT.setdefault("pf_burst", {})[lv] = {"hits": cap, "per_hit": f"{per0:.4g}→{per1:.4g}",
                                              "total": f"{per0 * cap:.4g}→{per1 * cap:.4g}"}
    check(tree)
    p = f"battle/action/power_flip/action/override/{PF_ID}${PF_ID}_lv{lv}"
    enc = encode_tree(tree)
    assert wf_dsl.parse_dsl(zlib.decompress(enc, -15))["tree"] == tree
    PF_FILES[wf_dsl.dsl_logical(p)] = enc
    PF_PATHS.append(p)
FILES.update(PF_FILES)
LP["pfa"] = "master/skill/power_flip_action.orderedmap"
T["pfa"] = load(LP["pfa"])
EDIT["pfa"] = {}
assert PF_ID not in T["pfa"]
EDIT["pfa"][PF_ID] = ",".join(PF_PATHS) + (NL if next(iter(T["pfa"].values())).endswith(NL) else "")
REPORT["pf"] = {"skeleton": "索维 121177 特殊强化弹射三档（生命周期原样，爆发合计 +5）"}
LOG.append(f"PF 覆盖 {PF_ID} 三档 = 索维特殊 PF 骨架换多色光球/爆发，爆发合计倍率 +{PF_BASE_PLUS:g}")

# ======================================================================== 4. 属性
st = copy.deepcopy(T["st"][CID])
assert sorted(st, key=int) == ["1", "10", "80", "100"] and st["100"].strip() == "2937,852", st
st["120"] = "3270,945" + (NL if st["100"].endswith(NL) else "")
EDIT["st"][CID] = st


# ======================================================================== 5. 队长技 / 能力
def gate(rs, kc, lc, lvl):
    out = copy.deepcopy(rs)
    for r in out:
        assert r[kc] in ("0", "") and r[lc] in ("0", ""), (r[kc], r[lc])
        r[kc], r[lc] = "1", str(lvl)
    return out


le0 = flat_rows(T["le"][CID])
assert [(r[45], r[49], r[50]) for r in le0] == [("32", "55000", "70000"), ("32", "9000", "12000")], le0
blank = [""] * len(le0[0])
for i in (3, 4, 11, 18, 25, 33, 44):
    blank[i] = "0"
blank[32] = "(None)"
blank[0], blank[1], blank[37] = CODE, "0", "(None)"


def lrow(**cols):
    r = list(blank)
    for k, v in cols.items():
        r[int(k[1:])] = str(v)
    return r


WIND6 = dict(c4=2, c7=600000, c8=600000, c9="Green")
le1 = copy.deepcopy(le0)
le1[0][49], le1[0][50] = "225000", "300000"                    # 全队风攻击 300%（作者 1015：200%→300%）
le1[1][49], le1[1][50] = "13500", "18000"                      # 强化弹射 2 次叠攻击 18%
le1 += [
    lrow(c25=2, c28=200000, c29=200000, c32=10, c45=55, c46=5, c47="Green", c49=11250, c50=15000),   # 叠 PF 伤害
    lrow(c25=2, c28=200000, c29=200000, c32=10, c45=34, c46=5, c47="Green", c49=7500, c50=10000),    # 叠技能伤害
    lrow(**WIND6, c25=23, c26=0, c28=100000, c29=100000, c33=900, c45=211, c46=5, c47="Green", c49=10000,
         c50=10000),                                                                                  # 技能→全队槽 CT15 秒
    lrow(c45=722, c80=PF_ID, c81="1,2,3", c82=PF_DESC_KEY),                                          # 队长位觉醒 PF
    lrow(c25=183, c26=0, c28=100000, c29=100000, c33=SEQ_CT, c45=629, c46=0, c68=SEQ_KEY, c69=SEQ_PATH),  # PF 命中→龙卷台风
    # 作者 1015 追加三行（列式照抄官方：341005 连击里程碑 PF 伤 / 149999 开局技能槽 / 141159 状态连击加成 489）
    lrow(c25=12, c28=1000000, c29=1000000, c32=10, c45=55, c49=15000, c50=15000),                      # 每 10 连击 自身 PF 伤 +15%（限 10 次）
    lrow(c25=0, c28=100000, c29=100000, c45=211, c46=5, c47="Green", c49=50000, c50=50000),          # 开局 风属性技能槽 +50%
    lrow(c25=23, c26=0, c28=100000, c29=100000, c45=489, c49=1500000, c50=1500000, c57=100000, c58=100000,
         c60=10, c61="(None)", c62="(None)", c63="(None)", c65=0, c70="false", c72=1, c73=0),        # 自身技能后 10 次弹射连击 +15
]
EDIT["le"][CID] = flat_text(gate(le0, 1, 2, 0) + gate(le1, 1, 2, 1), T["le"][CID])

ABIL_UP = {"1410991": [(0, 50000, 100000)], "1410992": [(0, 7500, 15000)],
           "1410993": [(0, 6250, 12500), (1, 11250, 22500)], "1410994": [(0, 31250, 62500)],
           "1410995": [(0, 2800, 5600)], "1410996": [(0, 2800, 5600)]}
ABIL_BEFORE = {"1410991": [("40000", "80000")], "1410992": [("6000", "12000")],
               "1410993": [("5000", "10000"), ("9000", "18000")], "1410994": [("25000", "50000")],
               "1410995": [("2250", "4500")], "1410996": [("2250", "4500")]}
for key, ups in ABIL_UP.items():
    a0 = flat_rows(T["ab"][key])
    assert [(r[51], r[52]) for r in a0] == ABIL_BEFORE[key], key
    a1 = copy.deepcopy(a0)
    for i, lo, hi in ups:
        a1[i][51], a1[i][52] = str(lo), str(hi)
    if key == "1410991":                       # 作者 1015：能力 1 追加「强化弹射所需连击数 -5」（kind 200，列式照 1110013）
        pr = [""] * len(a0[0])
        pr[0], pr[1], pr[2] = a0[0][0], a0[0][1], a0[0][2]
        for c in (3, 5, 6, 13, 20, 27, 46):
            pr[c] = "0"
        pr[39], pr[47], pr[51], pr[52] = "(None)", "200", "500000", "500000"
        a1.append(pr)
    EDIT["ab"][key] = flat_text(gate(a0, 3, 4, 0) + gate(a1, 3, 4, 1), T["ab"][key])
LOG.append("leader 141099：官方 2 行门控 + 觉醒 9 行（风攻击 300%、叠攻击 18%、叠 PF 伤害 15%、叠技伤 10%、技能→槽 10% CT15秒、"
           "队长位觉醒 PF 722、每 10 连击 PF 伤 15%×10、开局风槽 50%、技能后 10 次弹射连击 +15）；"
           "ability 1410991-6 ×1.25，1410991 追加 PF 所需连击 -5")

# ======================================================================== 6. 觉醒四表
WIN0, WIN1 = "2020-01-01 00:00:00", "2099-04-13 11:59:59"
assert CID not in T["aev"] and CID not in T["ast"]
EDIT["aev"][CID] = f"{WIN0},(None)" + NL
EDIT["ast"][CID] = "40,0" + NL
TPL, TPL_CODE, TPL_NAME = "341005", "cat_fighter", "缪"
MISSIONS, REWARDS = {}, {}
for s in range(1, 5):
    k, tk = f"{CID}{s}", f"{TPL}{s}"
    assert k not in T["am"] and k not in T["amr"]
    rs = [[c.replace(TPL, CID).replace(TPL_CODE, CODE).replace(TPL_NAME, NAME_ZH) for c in r] for r in flat_rows(T["am"][tk])]
    for r in rs:
        r[27], r[28], r[29], r[30] = WIN0, WIN1, WIN0, WIN1
    if s == 1:
        rs[0][3], rs[0][4], rs[0][7] = f"将{NAME_ZH}的等级提升至120", "5", ""
    MISSIONS[k] = rs
    EDIT["am"][k] = flat_text(rs, T["am"][tk])
    node = copy.deepcopy(T["amr"][tk])
    out = {}
    for ik, txt in node.items():
        rr = [[c.replace(TPL, CID) for c in r] for r in flat_rows(txt)]
        if s == 1:
            rr[0][5] = "120"
        out[ik] = rr
        node[ik] = flat_text(rr, txt)
    REWARDS[k] = out
    EDIT["amr"][k] = node

# ======================================================================== 7. 语音
VOICE_SRC = Path(r"D:/WF/角色语音/超限台词重写_20261015/final/schult")  # v2：Argon 台词 + 紧凑节奏重录
VOICES = ["home/overlimit_0", "home/overlimit_1", "battle/skill_2", "battle/skill_3",
          "battle/power_flip_2", "battle/power_flip_3", "battle/skill_ready_alt_1"]
HOME_SUBS = {"home/overlimit_0": "身体深处，涌上一股炽热的力量。\n不过，礼服的袖子没有撑破。\n……力道的控制，也进步了不少啊。",
             "home/overlimit_1": "新的风涡里，混进了粉色的光。\n琉西亚她们说是花瓣雨，欢呼着。\n……你们喜欢的话，倒也不坏。"}
for v in VOICES:
    lp = f"character/{CODE}/voice/{v}.mp3"
    try:
        read_raw(lp)
        raise AssertionError("voice exists " + lp)
    except FileNotFoundError:
        pass
    FILES[lp] = _assets.mp3_encode((VOICE_SRC / (v + ".mp3")).read_bytes())
sp_rows = flat_rows(T["sp"][CID])
for v, s_ in HOME_SUBS.items():
    sp_rows.append(["0", "2", "", s_, v])
EDIT["sp"][CID] = flat_text(sp_rows, T["sp"][CID])
LOG.append(f"语音 6 条 + character_speech 主页 2 行")


# ======================================================================== 8. 觉醒 PF 文案键
LP["cas"] = "master/string/custom_ability_string.orderedmap"
T["cas"] = load(LP["cas"])
EDIT["cas"] = {}
assert PF_DESC_KEY not in T["cas"]
EDIT["cas"][PF_DESC_KEY] = PF_DESC + (NL if T["cas"]["override_string_psycho_reaper_meteor23"].endswith(NL) else "")
assert SEQ_KEY not in T["cas"]
EDIT["cas"][SEQ_KEY] = SEQ_TEXT + (NL if T["cas"]["override_string_psycho_reaper_meteor23"].endswith(NL) else "")
def _legality():
    probs = []
    for r in flat_rows(EDIT["le"][CID]):
        probs += [f"leader: {p}" for p in L.client_legality_problems("leader_ability", r)]
        probs += [f"leader-629: {p}" for p in L.invoke_skill_string_problems(r, set(load('master/string/custom_ability_string.orderedmap')) | set(EDIT["cas"]), "leader_ability")] if r[45] == "629" else []
    for k in ABIL_UP:
        for r in flat_rows(EDIT["ab"][k]):
            probs += [f"{k}: {p}" for p in L.client_legality_problems("ability", r)]
    return probs


_P = _legality()
assert not _P, _P
import wf_describe as _D  # noqa: E402
for _r in flat_rows(EDIT["le"][CID]):
    LOG.append("  队长 " + _D.describe_line(_r, "leader_ability"))
for _r in flat_rows(EDIT["ab"]["1410991"]):
    LOG.append("  能力1 " + _D.describe_line(_r, "ability"))
LOG.append("客户端合法性检查（leader/ability 行）0 问题")

# ======================================================================== 打包
def raw_replace(lp, edits):
    raw, _ = read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    t0 = load(lp)
    for k, node in edits.items():
        if k in keys0:
            om.rows[om.keys.index(k)] = q.build_node(node)
        else:
            om.keys.append(k)
            om.rows.append(q.build_node(node))
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys[:len(keys0)] == keys0
    changed = [keys0[i] for i in range(len(rows0)) if back.rows[i] != rows0[i]]
    assert sorted(changed + back.keys[len(keys0):]) == sorted(edits), (lp, changed)
    parsed = q.parse_node(out)
    for k, node in edits.items():
        assert parsed[k] == node, (lp, k)
    return out


for t, ed in EDIT.items():
    if ed:
        FILES[LP[t]] = raw_replace(LP[t], ed)
        LOG.append(f"{LP[t]}：键 {sorted(ed)}")

# ======================================================================== 服务端 JSON
ASSETS = KULO / "assets"
srv = {}


def jload(rel):
    p = OUT / "server" / rel
    return json.loads((p if p.exists() else ASSETS / rel).read_text("utf-8"))


def jdump(obj, rel):
    txt = (ASSETS / rel).read_text("utf-8")
    indent = 2 if txt.startswith(("{\n  ", "[\n  ")) else (4 if txt.startswith("{\n    ") else None)
    return (json.dumps(obj, ensure_ascii=False, indent=indent) + ("\n" if txt.endswith("\n") else "")).encode("utf-8")


ct = jload("cdndata/character_text.json")
assert ct[CID][0] == tx
ct[CID][0] = tx2
srv["cdndata/character_text.json"] = json.dumps(ct, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
mc = jload("mission_char_awake_cnmod.json")
mr = jload("mission_char_awake_reward_cnmod.json")
for k in MISSIONS:
    assert k not in mc and k not in mr
    mc[k], mr[k] = MISSIONS[k], REWARDS[k]
srv["mission_char_awake_cnmod.json"] = jdump(mc, "mission_char_awake_cnmod.json")
srv["mission_char_awake_reward_cnmod.json"] = jdump(mr, "mission_char_awake_reward_cnmod.json")
ex = jload("character_awake_extension.json")
assert CID not in ex
ex[CID] = {"linked_mana_node_slots": [{"board_index": 2, "ability_slot": s, "awake_level": 1} for s in (4, 5, 6)]}
srv["character_awake_extension.json"] = jdump(ex, "character_awake_extension.json")
ol_path = Path(r"~/AppData/Local/Temp/claude/D--WF-startpoint-cn/23453274-d715-4189-b086-8c701fe97f86/scratchpad/kulo/assets/character_overlimit.json")
ol = json.loads(ol_path.read_text("utf-8"))
if 141099 in ol["characters"]:                 # 草稿 kulo 已打过 rose 服务端补丁：还原后重加，产物不变
    ol["characters"].remove(141099)
    ol["level_missions"].pop("1410991")
ol["characters"].append(141099)
ol["level_missions"]["1410991"] = 120
srv["character_overlimit.json"] = (json.dumps(ol, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main():
    members = {member(lp): d for lp, d in FILES.items()}
    print(json.dumps(REPORT, ensure_ascii=False, indent=1))
    print(NL.join(LOG))
    if "--write" not in sys.argv:
        print(f"DRY RUN: {NAME} {len(members)} members; server {sorted(srv)}")
        return 0
    (OUT / "patch").mkdir(exist_ok=True)
    path = OUT / "patch" / NAME
    if path.exists():
        path.unlink()
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    assert len(blob) <= 5 * 1024 * 1024
    for rel, data in srv.items():
        p = SRV_OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "applies_on": FROM, "version": TO, "base_extra_zips": EXTRA,
             "logical_paths": {member(lp): lp for lp in sorted(FILES)}, "report": REPORT, "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + NL, "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

