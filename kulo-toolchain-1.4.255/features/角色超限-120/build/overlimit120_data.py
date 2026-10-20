# -*- coding: utf-8 -*-
"""角色超限 Lv120 · 首个角色 炎龙王 瓦格纳 111183（fire_dragon_zenith）数据补丁。

叠在 kulo 1.4.205 视图 + 本地 1.4.206（罗尔夫月技能重做）之上 → 暂定 1.4.207（版本号由协调统一分配）。
默认 dry run；--write 才写 zip / 服务端 JSON / 报告。

改动（全部只动目标键，其余键 chunk 逐字节保留）：
  action_skill        fire_dragon_zenith 增加进化 3 档「日珥粉碎＋＋」→ 新 DSL _3
  DSL（新文件）        fire_dragon_zenith_3 = _2 原样 + 冲击波/领域 ×1.2 + 红炎吐息（竖直 1 道 + 两侧 6 对 12 道）
  character_text      111183 c9 觉醒技能说明
  character_status    111183 新增 Lv120 键（APK 补丁据此识别超限角色：★5 且属性表最高键 ≥120）
  leader_ability      111183 官方行门控「仅未觉醒」+ 觉醒行（觉醒1）
  ability             1111832..1111836 同上（能力1已封顶不动）
  character_awake_event / character_awake_status / character_awake_mission / character_awake_mission_reward  111183 新增
  item                新增 10000320 超限结晶（★5 突破结晶类）
  item_quest_search   10000320 → 终始之龙（高难度联机 2088/1）
服务端（整文件输出到 out/角色超限-120/server/，由 format-patch 引用）：
  cdndata/character_text.json、mission_char_awake_cnmod.json、mission_char_awake_reward_cnmod.json、
  character_awake_extension.json、item_ids.json、item_lookup_cnmod.json、score_reward_cnmod.json、rare_score_reward_cnmod.json
用法：python overlimit120_data.py [--write]
"""
import copy
import hashlib
import json
import math
import os
import sys
import zipfile
import zlib
from pathlib import Path

BUILD = Path(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
PATCH206 = BUILD.parent / "patch/pinball-1.4.205-1.4.206-1-rolf-moon-skill-rework-local.zip"
os.environ["WF_TIP"] = "205"
os.environ["WF_EXTRA_ZIPS"] = str(PATCH206)
sys.path.insert(0, str(BUILD))
from live149 import *  # noqa: E402,F401  (load/read_raw/rows/row/join/member/q/KULO/_ZIPS…)
import wf_dsl  # noqa: E402
import wf_mod_tool as M  # noqa: E402
from wf_character_revision import encode_tree  # noqa: E402
from dsltools import commands  # noqa: E402

sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L  # noqa: E402
import wf_cursed_weapons as W  # noqa: E402
import base149 as _B  # noqa: E402

assert TIP == 205, TIP
assert _B._ZIPS[-2].name == "pinball-1.4.204-1.4.205-1-rolf-direct-104-local.zip", _B._ZIPS[-2].name
assert _B._ZIPS[-1] == PATCH206, _B._ZIPS[-1]

OUT = Path(r"D:/WF/out/角色超限-120")
NAME = "pinball-1.4.206-1.4.207-1-overlimit120-wagner-local.zip"
SRV_OUT = OUT / "server"
NL = chr(10)
LOG: list[str] = []
REPORT: dict = {}

CID, CODE = "111183", "fire_dragon_zenith"
ITEM_ID = "10000320"
HM_EVENT, HM_QUEST = 2088, 1          # 终始之龙 高难度联机 2088001
RARE_GROUP = "12199320"               # 新稀有掉落组（终始之龙的现有组 12100088 不动）
DROP_RATE = 0.25

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
    "it": "master/item/item.orderedmap",
    "iqs": "master/search/item_quest_search.orderedmap",
    "sp": "master/character/character_speech.orderedmap",
}
T = {k: load(v) for k, v in LP.items()}
EDIT: dict[str, dict[str, object]] = {k: {} for k in LP}   # 表 → {键: 新节点}


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


# ======================================================================== 1. 技能 DSL _3
P2 = f"battle/action/skill/action/rare5/{CODE}${CODE}_2"
P3 = f"battle/action/skill/action/rare5/{CODE}${CODE}_3"
FX_BEAM = "battle/effect/skill_unique/fire_dragon/fire_dragon"
FX_END = "battle/effect/skill_unique/fire_dragon/fire_dragon_end"

STOP = 200
F_V = 80                                  # 竖直吐息
LIFE_V, HITS_V = 36, 6
F_SIDE = [110, 118, 126, 134, 142, 150]   # 两侧 6 对
LIFE_S, HITS_S = 40, 5
ANG = [0.15, 0.30, 0.45, 0.60, 0.75, 0.90]  # rad ≈ 9°/17°/26°/34°/43°/52°
UP = 1.2                                  # 冲击波、领域倍率提升
MULT_V = V(1.035, 1.2)
MULT_S = V(0.5175, 0.6)
BRK_V, FEV_V = 0.3, 0.1
BRK_S, FEV_S = 0.1, 0.05


def scale(v, k):
    return [{"min": round(x["min"] * k, 6), "max": round(x["max"] * k, 6)} for x in v]


def beam(rp_id, rot, life, hits, mult, brk, fev, label):
    """官方 fire_dragon_3 写法：球上 AB 参考点（偏移 0,-50，跟随）→ 子判定区 CD 继承 + rot 偏转；
    吐息特效挂判定区（CD，随判定区角度），收尾特效挂参考点（CD + w=rot）。"""
    a, b, c = rp_id + 1, rp_id + 2, rp_id + 3
    ha = cmd("CreateHitArea", "*", rp_id, ["CD"], 0, 0, rot, True, False,
             ["Rectangle", V(300), V(2000)], ["Center"], ["Bottom"], ["Single"],
             ["SpecifyHitAreaLifetimeDirectly", life], ["CalculatedUsingMaxNumOfHits", hits], ["None"],
             False, True, ["None"], a,
             ["Block", [cmd("ShowEffect", label, ["SpecifyEffectDirectly", FX_BEAM], a, ["ForesideOfCharacter"],
                            ["SpecifyEffectLifetimeDirectly", life], ["CD"], 0, 0, 0, True, True, ["Some", V(3)])]],
             b, c,
             ["Block", [cmd("CreateNormalAttack", c, 255, [], [], 20, mult, V(0), False, False, False, False, False,
                            V(brk), V(fev), ["Fine"], True),
                        cmd("ShakeCamera", 1)]],
             0, 0, ["None"])
    end = wait(life, [cmd("ShowEffect", label + "終了", ["SpecifyEffectDirectly", FX_END], rp_id, ["BacksideOfCharacter"],
                          ["SpecifyEffectLifetimeDirectly", 84], ["CD"], 0, 0, rot, False, False, ["Some", V(3)])])
    return cmd("CreateReferencePoint", -18, ["AB"], 0, -50, 0, True, False, ["Single"], life, rp_id, ["Block", [ha, end]])


def build_skill3(t2):
    t = copy.deepcopy(t2)
    body = t[11][1]
    assert body[0] == cmd("StopBall", -18, 60, ["Stop"], ["AB"], 0), body[0]
    body[0] = cmd("StopBall", -18, STOP, ["Stop"], ["AB"], 0)
    cnas = list(commands(t, "CreateNormalAttack"))
    assert len(cnas) == 3, len(cnas)
    assert cnas[0][1][6] == V(2.71375, 3.125) and cnas[1][1][6] == cnas[2][1][6] == V(0.430625, 0.5)
    for _, c in cnas:
        c[6] = scale(c[6], UP)
    used = {x for _, c in commands(t, "CreateHitArea") for x in (c[19], c[21], c[22])}
    assert used == {0, 1, 2, 3, 4, 5}, used
    rp = 10
    body.append(wait(F_V, [beam(rp, 0, LIFE_V, HITS_V, MULT_V, BRK_V, FEV_V, "竖直吐息")]))
    for i, (f, ang) in enumerate(zip(F_SIDE, ANG)):
        pair = []
        for sgn in (-1, 1):
            rp += 4
            pair.append(beam(rp, round(sgn * ang, 4), LIFE_S, HITS_S, MULT_S, BRK_S, FEV_S, f"側面吐息{i + 1}{'L' if sgn < 0 else 'R'}"))
        body.append(wait(f, pair))
    return t


def per_target_max(t):
    """每个判定区按 期望命中 × 每次攻击倍率(满级) 累加：冲击波、领域、吐息。"""
    tot = {}
    for _, h in commands(t, "CreateHitArea"):
        n = h[14][1]
        if h[15][0] == "Some":
            n = h[15][1][0]["max"]
        per = sum(c[6][0]["max"] for _, c in commands(h[23], "CreateNormalAttack"))
        key = "explosion" if h[2] == -18 else "field" if h[2] == -1 else ("beam_v" if h[6] == 0 else "beam_side")
        tot[key] = round(tot.get(key, 0) + n * per, 4)
    return tot


T2 = dsl_tree(P2)
T3 = build_skill3(T2)
probs = W.dsl_signature_problems(T3)
probs += L.action_dsl_subject_binding_problems(T3)
probs += L.action_dsl_lookup_scope_problems(T3)
probs += L.action_dsl_hit_area_target_problems(T3)
probs += L.action_dsl_element_problems(T3, 1)
assert not probs, probs
for _, c in commands(T3, "ShowEffect"):
    if c[6] == ["CD"]:
        assert c[3] not in (-18, -17, -33) and c[3] >= 0, c       # CD 只挂参考点/判定区
ENC3 = encode_tree(T3)
assert wf_dsl.parse_dsl(zlib.decompress(ENC3, -15))["tree"] == T3
REPORT["skill3"] = {"logical": wf_dsl.dsl_logical(P3), "member": member(wf_dsl.dsl_logical(P3)),
                    "hit_areas": sum(1 for _ in commands(T3, "CreateHitArea")),
                    "per_target_max_by_part": per_target_max(T3), "before_2": per_target_max(T2),
                    "size": len(ENC3), "sha256": hashlib.sha256(ENC3).hexdigest(),
                    "capabilities": W.dsl_capabilities(T3)}
LOG.append(f"DSL {P3}：_2 原样 + 停球 60→{STOP} + 冲击波/领域倍率×{UP} + 竖直吐息@{F_V} + 两侧 12 道@{F_SIDE}")

# ======================================================================== 2. action_skill 进化 3 档 + 文本
SKILL3_NAME = "日珥粉碎＋＋"
SKILL3_DESC = ("跳向前方，以爆炎的冲击波对周围的敌人造成火属性伤害，随后向正前方与两侧依次喷吐红炎吐息，"
               "对命中的敌人造成火属性伤害 ／ 在一段时间内放出火焰吞噬整个领域，每隔一段时间对所有敌人造成火属性伤害（不破坏弱点）")
g = copy.deepcopy(T["as"][CODE])
assert list(g) == ["1", "2"], list(g)
r2 = row(g["2"])
assert r2[0] == "日珥粉碎＋" and r2[7] == P2, r2
r3 = list(r2)
r3[0], r3[1], r3[7] = SKILL3_NAME, SKILL3_DESC, P3
g["3"] = join(r3) + (NL if g["2"].endswith(NL) else "")
EDIT["as"][CODE] = g
tx = rows(T["tx"][CID])[0]
assert tx[8] == SKILL3_NAME, tx[8]
tx2 = list(tx)
tx2[9] = SKILL3_DESC
EDIT["tx"][CID] = join(tx2) + (NL if T["tx"][CID].endswith(NL) else "")
LOG.append(f"action_skill {CODE} 新增 3 档（SP {r3[4]}/{r3[5]} 同 2 档）；character_text {CID} c9 觉醒技能说明")

# ======================================================================== 4. Lv120 属性
st = copy.deepcopy(T["st"][CID])
assert sorted(st, key=int) == ["1", "10", "80", "100"] and st["100"].strip() == "4059,957", st
st["120"] = "4500,1060" + (NL if st["100"].endswith(NL) else "")
EDIT["st"][CID] = st
LOG.append("character_status 111183 新增 Lv120 = 4500/1060（Lv100 4059/957）")


# ======================================================================== 5. 队长技 / 能力 觉醒门控
def gate(rs, kind_col, lvl_col, lvl):
    out = copy.deepcopy(rs)
    for r in out:
        assert r[kind_col] in ("0", "") and r[lvl_col] in ("0", ""), (r[kind_col], r[lvl_col])
        r[kind_col], r[lvl_col] = "1", str(lvl)
    return out


def scaled(rs, idx, lo_col, hi_col, lo, hi):
    out = copy.deepcopy(rs)
    out[idx][lo_col], out[idx][hi_col] = str(lo), str(hi)
    return out


LEADER_UP = {0: (22500, 30000), 1: (22500, 30000), 2: (5600, 7000)}     # c49/c50
le0 = flat_rows(T["le"][CID])
assert [(r[49], r[50]) for r in le0[:3]] == [("15000", "20000"), ("15000", "20000"), ("4000", "5000")]
le1 = copy.deepcopy(le0)
for i, (lo, hi) in LEADER_UP.items():
    le1 = scaled(le1, i, 49, 50, lo, hi)
EDIT["le"][CID] = flat_text(gate(le0, 1, 2, 0) + gate(le1, 1, 2, 1), T["le"][CID])

ABIL_UP = {  # 键 → [(行, lo, hi)]  c51/c52
    "1111832": [(0, 12500, 25000)],
    "1111833": [(0, 12500, 25000), (1, 12500, 25000), (2, 125000, 250000)],
    "1111834": [(0, 3000, 6000)],
    "1111835": [(0, 4000, 8000)],
    "1111836": [(0, 4500, 9000)],
}
ABIL_BEFORE = {"1111832": [("10000", "20000")], "1111833": [("10000", "20000"), ("10000", "20000"), ("100000", "200000")],
               "1111834": [("2250", "4500")], "1111835": [("3000", "6000")], "1111836": [("3500", "7000")]}
for key, ups in ABIL_UP.items():
    a0 = flat_rows(T["ab"][key])
    assert [(r[51], r[52]) for r in a0] == ABIL_BEFORE[key], (key, [(r[51], r[52]) for r in a0])
    a1 = copy.deepcopy(a0)
    for i, lo, hi in ups:
        a1 = scaled(a1, i, 51, 52, lo, hi)
    EDIT["ab"][key] = flat_text(gate(a0, 3, 4, 0) + gate(a1, 3, 4, 1), T["ab"][key])
LOG.append("leader_ability 111183：官方 6 行打「觉醒0」+ 觉醒 6 行（攻/技伤每次 20%→30%，技能槽 5%→7%）；"
           "ability 1111832-1111836 同法（能力1已封顶不动）")

# ======================================================================== 6. 觉醒活动 / 属性 / 任务 / 奖励
WIN0, WIN1 = "2020-01-01 00:00:00", "2099-04-13 11:59:59"
assert CID not in T["aev"] and CID not in T["ast"]
EDIT["aev"][CID] = f"{WIN0},(None)" + NL
EDIT["ast"][CID] = "40,0" + NL
TPL, TPL_CODE, TPL_NAME = "341005", "cat_fighter", "缪"
MISSIONS: dict[str, list[list[str]]] = {}
for s in range(1, 5):
    k, tk = f"{CID}{s}", f"{TPL}{s}"
    assert k not in T["am"] and k not in T["amr"]
    rs = [[c.replace(TPL, CID).replace(TPL_CODE, CODE).replace(TPL_NAME, "瓦格纳") for c in r] for r in flat_rows(T["am"][tk])]
    for r in rs:
        r[27], r[28], r[29], r[30] = WIN0, WIN1, WIN0, WIN1
    if s == 1:                         # 等级达到 120（MissionPatternKind 5 = character_level_achievement）
        rs[0][3] = "将瓦格纳的等级提升至120"
        rs[0][4] = "5"
        rs[0][7] = ""
    MISSIONS[k] = rs
    EDIT["am"][k] = flat_text(rs, T["am"][tk])
REWARDS: dict[str, dict[str, list[list[str]]]] = {}
for s in range(1, 5):
    k, tk = f"{CID}{s}", f"{TPL}{s}"
    node = copy.deepcopy(T["amr"][tk])
    out = {}
    for ik, txt in node.items():
        rs = [[c.replace(TPL, CID) for c in r] for r in flat_rows(txt)]
        if s == 1:
            rs[0][5] = "120"           # target_progress
        out[ik] = rs
        node[ik] = flat_text(rs, txt)
    REWARDS[k] = out
    EDIT["amr"][k] = node
LOG.append("觉醒：character_awake_event/status（攻击+40）、觉醒任务 1111831-4（1=等级达到120，2/3=编队通关，4=全部完成，模板 341005）")

# ======================================================================== 7. 道具 超限结晶
assert ITEM_ID not in T["it"]
it = row(T["it"]["10003"])
it2 = list(it)
it2[0] = "mod_overlimit_crystal"
it2[1] = ITEM_ID
it2[2] = "超限结晶"
it2[5] = "越过极限之人方能唤醒的结晶。\n可用于已完成4次突破的指定★5角色，\n每次突破使等级上限提升5级，最高至120级。\n每次突破另需1个悖论之核。"
assert it2[6] == "4" and it2[9] == "5" and it2[11] == "false" and it2[17] == "5", it2
it2[11] = "true"   # APK O2/O3 据此识别超限结晶（★5 结晶且可用于低稀有度）
# 图标：c3 缩略图 = 独立 20×20 PNG（异步 setTexture，可独立文件）；c4 掉落/图鉴小图标 = item_icon 图集子纹理（同步取图，
# 独立 PNG 或 (None) 在掉落栏会 C8004/C4208）。龙纹图 = RetroDiffusion rd_pro 40×40，候选在 art/item/。
ICON_SRC = OUT / "art/item" / os.environ.get("WF_OL_ICON", "overlimit_crystal_cand0.png")   # 作者 1015 选 A
C3_PATH = "item/materials/mod/overlimit/overlimit_crystal"
C4_PATH = "item_icon/materials/mod/overlimit/overlimit_crystal"
ICON_FILES = {}


def _png_store(img):
    buf = _io_icon.BytesIO()
    img.save(buf, "PNG")
    b = bytearray(buf.getvalue())
    b[1:4] = b"png"
    return bytes(b)


def _png_load(raw):
    b = bytearray(raw)
    b[1:4] = b"PNG"
    return _Image_icon.open(_io_icon.BytesIO(bytes(b))).convert("RGBA")


import io as _io_icon  # noqa: E402
from PIL import Image as _Image_icon  # noqa: E402
icon40 = _Image_icon.open(ICON_SRC).convert("RGBA")
assert icon40.size == (40, 40)
icon20 = icon40.resize((20, 20), _Image_icon.LANCZOS)
_a = icon20.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
icon20.putalpha(_a)
for lp in (C3_PATH + ".png",):
    try:
        read_raw(lp)
        raise AssertionError("exists " + lp)
    except FileNotFoundError:
        pass
ICON_FILES[C3_PATH + ".png"] = _png_store(icon20)
_atlas_lp, _sheet_lp = "item_icon/sprite_sheet.atlas.amf3.deflate", "item_icon/sprite_sheet.png"
_atlas = M.AMF3Reader(zlib.decompress(read_raw(_atlas_lp)[0], -15)).read_value()
assert C4_PATH not in {e["n"] for e in _atlas}
_sheet = _png_load(read_raw(_sheet_lp)[0])
_W, _H = _sheet.size
_new = _Image_icon.new("RGBA", (_W, _H + 42))
_new.alpha_composite(_sheet, (0, 0))
_new.alpha_composite(icon40, (1, _H + 1))
_atlas2 = list(_atlas) + [{"n": C4_PATH, "w": 40, "h": 40, "x": 1, "y": _H + 1}]
_co = zlib.compressobj(9, zlib.DEFLATED, -15)
ICON_FILES[_atlas_lp] = _co.compress(wf_dsl.encode_amf3(_atlas2)) + _co.flush()
ICON_FILES[_sheet_lp] = _png_store(_new)
assert M.AMF3Reader(zlib.decompress(ICON_FILES[_atlas_lp], -15)).read_value()[:len(_atlas)] == _atlas
it2[3], it2[4] = C3_PATH, C4_PATH
LOG.append(f"超限结晶图标：c3={C3_PATH}（20×20 独立 PNG）、c4={C4_PATH}（item_icon 图集 {_W}×{_H}→{_W}×{_H + 42} 追加 40×40，"
           f"整文件替换图集两件）；源 {ICON_SRC.name}")
EDIT["it"][ITEM_ID] = join(it2) + (NL if T["it"]["10003"].endswith(NL) else "")
assert ITEM_ID not in T["iqs"]
EDIT["iqs"][ITEM_ID] = f"18,{HM_EVENT},,{HM_QUEST},{HM_EVENT * 1000 + HM_QUEST},{round(DROP_RATE * 1, 4)}" + NL
LOG.append(f"item 新增 {ITEM_ID} 超限结晶（突破结晶 ★5，龙纹自制图标）；item_quest_search → 终始之龙 {HM_EVENT}/{HM_QUEST}")


# ======================================================================== 打包
def raw_replace(lp, edits):
    raw, _ = read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    t0 = load(lp)
    for k, node in edits.items():
        if k in keys0:
            assert q.parse_node(q.build_node(t0[k])) == t0[k], (lp, k)
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


# ======================================================================== 8. 新语音（主页 2 / 技能 2 / 强化弹射 2）
import wf_assets as _assets  # noqa: E402
VOICE_SRC = Path(r"D:/WF/角色语音/超限台词重写_20261015/final/wagner")  # v2：Argon 台词 + 紧凑节奏重录
VOICES = ["home/overlimit_0", "home/overlimit_1", "battle/skill_2", "battle/skill_3",
          "battle/power_flip_2", "battle/power_flip_3", "battle/skill_ready_alt_1"]
HOME_SUBS = {
    "home/overlimit_0": "沉寂已久的脏腑，又躁动起来了。\n冲破旧壳、喷涌而出的这股灼热……\n哼，看来本王还退隐不得啊。",
    "home/overlimit_1": "你这家伙，拱火也太乱来了……\n本王的劫火，比以前闹得更凶了。\n——不许笑！叫你负起责任来！",
}
VOICE_FILES = {}
for v in VOICES:
    lp = f"character/{CODE}/voice/{v}.mp3"
    data = (VOICE_SRC / (v + ".mp3")).read_bytes()
    data = _assets.mp3_encode(data)            # 存储态：帧同步字 0x7FF→0x3FF（客户端 MP3Converter.decode 还原）
    try:
        read_raw(lp)
        raise AssertionError(f"voice already exists: {lp}")
    except FileNotFoundError:
        pass
    VOICE_FILES[lp] = data
sp_old = T["sp"][CID]
sp_rows = [r for r in rows(sp_old) if r]
assert not any(r[4].startswith("home/overlimit") for r in sp_rows)
for v, sub_ in HOME_SUBS.items():
    sp_rows.append(["0", "2", "", sub_, v])        # constraint 2 = 始终可见
EDIT["sp"][CID] = flat_text(sp_rows, sp_old)
LOG.append(f"语音：新增 {len(VOICES)} 条（技能/强化弹射为原生随机追加槽 _2/_3），character_speech {CID} 追加主页 2 行")

# ======================================================================== 9. 觉醒射击 PF：红金换色 + 炎龙装饰（722 覆盖，仅队长位）
import io as _io
from PIL import Image as _Image
APK_BUNDLE = Path(r"D:/WF/perf-v30-20261015/out/世界弹射测试服-v30-perf2.signed.apk")
PF_SRC = OUT / "build/pf_src"
PF_ID = "fire_dragon_zenith_overlimit_pf"
PF_DESC_KEY = "override_string_fire_dragon_zenith_overlimit_pf"
PF_DESC = "觉醒后的射击强化弹射：从弹板射出红金色的炎龙光柱，并在球周围燃起龙炎；伤害与官方射击强化弹射相同"
OFF_FAM = "battle/effect/powerflip/effect_powerflip_attack_beam"
PF_BEAMS = {1: ["powerflip_attack_beam_one"], 2: ["powerflip_attack_beam_two_medium", "powerflip_attack_beam_two_small"],
            3: ["powerflip_attack_beam_three_large", "powerflip_attack_beam_three_medium",
                "powerflip_attack_beam_three_small"]}
DECOR = ("battle/effect/skill_unique/fire_dragon_zenith/fire_dragon_zenith_hit", {1: 2.0, 2: 2.5, 3: 3.0})
LP["pfa"] = "master/skill/power_flip_action.orderedmap"
LP["cas"] = "master/string/custom_ability_string.orderedmap"
EDIT["pfa"], EDIT["cas"] = {}, {}
T["pfa"], T["cas"] = load(LP["pfa"]), load(LP["cas"])
read_raw(DECOR[0] + ".parts.amf3.deflate")       # 装饰特效在 CDN（技能已在用）


def _bundle_raw(lp):
    h = hashlib.sha1((lp + SALT).encode()).hexdigest()
    with zipfile.ZipFile(APK_BUNDLE) as apk, zipfile.ZipFile(_io.BytesIO(apk.read("assets/bundle.zip"))) as bz:
        return bz.read(f"production/android_bundle/{h[:2]}/{h[2:]}")


def _deflate(b):
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    return co.compress(b) + co.flush()


PF_FILES: dict[str, bytes] = {}
atlas0 = M.AMF3Reader(zlib.decompress(read_raw(f"{OFF_FAM}/effect_powerflip_attack_beam.atlas.amf3.deflate")[0], -15)).read_value()
png0 = bytearray(read_raw(f"{OFF_FAM}/effect_powerflip_attack_beam.png")[0])
assert png0[1:4] == b"png"
for lv, beams in PF_BEAMS.items():
    fam_name = f"zenith_ol_beam_lv{lv}"
    fam = f"battle/effect/powerflip/{fam_name}"
    for lp in (f"{fam}/{fam_name}.png", f"{fam}/{fam_name}.atlas.amf3.deflate"):
        try:
            read_raw(lp)
            raise AssertionError(f"exists: {lp}")
        except FileNotFoundError:
            pass
    atlas = [dict(e, n=e["n"].replace(OFF_FAM + "/", fam + "/")) for e in atlas0]
    PF_FILES[f"{fam}/{fam_name}.atlas.amf3.deflate"] = _deflate(wf_dsl.encode_amf3(atlas))
    img = _Image.open(PF_SRC / f"{fam_name}.png").convert("RGBA")
    buf = _io.BytesIO()
    img.save(buf, "PNG")
    png = bytearray(buf.getvalue())
    png[1:4] = b"png"
    PF_FILES[f"{fam}/{fam_name}.png"] = bytes(png)
    for b in beams:
        parts = wf_dsl.parse_dsl(zlib.decompress(read_raw(f"{OFF_FAM}/{b}.parts.amf3.deflate")[0], -15))["tree"]
        n = sum(1 for e in parts["i"] if e["p"].startswith(OFF_FAM + "/"))
        assert n == len(parts["i"]), b
        for e in parts["i"]:
            e["p"] = e["p"].replace(OFF_FAM + "/", fam + "/")
        PF_FILES[f"{fam}/{b}.parts.amf3.deflate"] = _deflate(wf_dsl.encode_amf3(parts))
        PF_FILES[f"{fam}/{b}.timeline.amf3.deflate"] = read_raw(f"{OFF_FAM}/{b}.timeline.amf3.deflate")[0]

PF_PATHS = []
for lv in (1, 2, 3):
    tree = wf_dsl.parse_dsl(zlib.decompress(_bundle_raw(
        f"battle/action/power_flip/action/ranged$ranged_lv{lv}.action.dsl.amf3.deflate"), -15))["tree"]
    s = json.dumps(tree, ensure_ascii=False)
    assert s.count(OFF_FAM + "/") == len(PF_BEAMS[lv]), (lv, s.count(OFF_FAM + "/"))
    tree = json.loads(s.replace(OFF_FAM + "/", f"battle/effect/powerflip/zenith_ol_beam_lv{lv}/"))
    body = tree[11][1]
    assert body[0] == cmd("SetPowerFilpSuppress", {1: 20, 2: 25, 3: 35}[lv]), body[0]
    body.insert(1, cmd("ShowEffect", "炎龍装飾", ["SpecifyEffectDirectly", DECOR[0]], -18, ["ForesideOfCharacter"],
                       ["PlayOnlyFirstSequence"], ["AB"], 0, 0, 0, False, False, ["Some", V(DECOR[1][lv])]))
    probs = W.dsl_signature_problems(tree) + L.action_dsl_subject_binding_problems(tree) \
        + L.action_dsl_lookup_scope_problems(tree) + L.action_dsl_hit_area_target_problems(tree)
    assert not probs, (lv, probs)
    p = f"battle/action/power_flip/action/override/{PF_ID}${PF_ID}_lv{lv}"
    enc = encode_tree(tree)
    assert wf_dsl.parse_dsl(zlib.decompress(enc, -15))["tree"] == tree
    PF_FILES[wf_dsl.dsl_logical(p)] = enc
    PF_PATHS.append(p)
assert PF_ID not in T["pfa"] and PF_DESC_KEY not in T["cas"]
EDIT["pfa"][PF_ID] = ",".join(PF_PATHS) + (NL if next(iter(T["pfa"].values())).endswith(NL) else "")
EDIT["cas"][PF_DESC_KEY] = PF_DESC + (NL if T["cas"]["override_string_lion_swordman_moon_pf"].endswith(NL) else "")
# 觉醒队长技追加一行 722（只在觉醒 1 生效）
le_rows = flat_rows(EDIT["le"][CID])
pf_row = [""] * len(le_rows[0])
pf_row[0], pf_row[1], pf_row[2] = CODE, "1", "1"
for i in (3, 4, 11, 18, 25, 44):          # 同 169999 基诺维 722 行的零值列
    pf_row[i] = "0"
pf_row[37] = "(None)"
pf_row[45], pf_row[80], pf_row[81], pf_row[82] = "722", PF_ID, "1,2,3", PF_DESC_KEY
EDIT["le"][CID] = flat_text(le_rows + [pf_row], T["le"][CID])
LOG.append(f"觉醒 PF：{PF_ID} 三档 = 官方 ranged 骨架 + 红金换色光柱族 zenith_ol_beam_lv1-3 + 炎龙装饰；队长技觉醒行追加 722")

files: dict[str, bytes] = {wf_dsl.dsl_logical(P3): ENC3, **VOICE_FILES, **PF_FILES, **ICON_FILES}
for t, ed in EDIT.items():
    if ed:
        files[LP[t]] = raw_replace(LP[t], ed)
        LOG.append(f"{LP[t]}：键 {sorted(ed)}")

# ======================================================================== 服务端 JSON
ASSETS = KULO / "assets"
SRV28 = BUILD.parent / "server28/character_text.json"   # 1.4.206 的 cdndata/character_text
srv: dict[str, bytes] = {}
ct_old = SRV28.read_text("utf-8")
ct = json.loads(ct_old)
assert ct[CID][0] == tx, "服务端 character_text 与客户端不一致"
ct[CID][0] = tx2
srv["cdndata/character_text.json"] = json.dumps(ct, ensure_ascii=False, separators=(",", ":")).encode("utf-8") \
    if not ct_old.lstrip().startswith("{\n") else json.dumps(ct, ensure_ascii=False, indent=2).encode("utf-8")


def jload(name):
    return json.loads((ASSETS / name).read_text("utf-8"))


def jdump(obj, like):
    txt = (ASSETS / like).read_text("utf-8")
    indent = 2 if txt.startswith("{\n  ") or txt.startswith("[\n  ") else (4 if txt.startswith("{\n    ") else None)
    return (json.dumps(obj, ensure_ascii=False, indent=indent) + ("\n" if txt.endswith("\n") else "")).encode("utf-8")


mc = jload("mission_char_awake_cnmod.json")
for k, rs in MISSIONS.items():
    assert k not in mc
    mc[k] = rs
srv["mission_char_awake_cnmod.json"] = jdump(mc, "mission_char_awake_cnmod.json")
mr = jload("mission_char_awake_reward_cnmod.json")
for k, node in REWARDS.items():
    assert k not in mr
    mr[k] = node
srv["mission_char_awake_reward_cnmod.json"] = jdump(mr, "mission_char_awake_reward_cnmod.json")
ex = jload("character_awake_extension.json")
assert CID not in ex
ex[CID] = {"linked_mana_node_slots": [{"board_index": 2, "ability_slot": s, "awake_level": 1} for s in (4, 5, 6)]}
srv["character_awake_extension.json"] = jdump(ex, "character_awake_extension.json")
ids = jload("item_ids.json")
assert int(ITEM_ID) not in ids and ITEM_ID not in ids
ids.append(int(ITEM_ID) if isinstance(ids[0], int) else ITEM_ID)
srv["item_ids.json"] = jdump(ids, "item_ids.json")
lk = jload("item_lookup_cnmod.json")
assert ITEM_ID not in lk
lk[ITEM_ID] = "超限结晶"
srv["item_lookup_cnmod.json"] = jdump(lk, "item_lookup_cnmod.json")
sr = jload("score_reward_cnmod.json")
grp = sr["12100088"]
assert [p["position"] for p in grp] == [1, 2, 3], grp
grp.append({"position": 4, "name": "", "type": 1, "id": int(RARE_GROUP), "rarity": DROP_RATE})
srv["score_reward_cnmod.json"] = jdump(sr, "score_reward_cnmod.json")
rr = jload("rare_score_reward_cnmod.json")
assert RARE_GROUP not in rr
rr[RARE_GROUP] = [{"name": "", "type": 0, "rarity": 1.0, "id": int(ITEM_ID), "count": 1}]
srv["rare_score_reward_cnmod.json"] = jdump(rr, "rare_score_reward_cnmod.json")
LOG.append(f"服务端：觉醒任务/奖励/盘二联动、item_ids/lookup、终始之龙掉落组 12100088 追加位置 4 → 稀有组 {RARE_GROUP}（{DROP_RATE:.0%}，超限结晶×1）")


def main():
    members = {member(lp): d for lp, d in files.items()}
    print(json.dumps(REPORT, ensure_ascii=False, indent=1))
    print(NL.join(LOG))
    if "--write" not in sys.argv:
        print(f"DRY RUN: {NAME} {len(members)} members; server {sorted(srv)}")
        return 0
    (OUT / "patch").mkdir(parents=True, exist_ok=True)
    path = OUT / "patch" / NAME
    assert not path.exists(), path
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            zf.writestr(m, members[m])
    blob = path.read_bytes()
    assert len(blob) <= 5 * 1024 * 1024
    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None
    for rel, data in srv.items():
        p = SRV_OUT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
             "logical_paths": {member(lp): lp for lp in sorted(files)},
             "new_files": [wf_dsl.dsl_logical(P3)],
             "server_files": {f"assets/{rel}": hashlib.sha256(d).hexdigest() for rel, d in sorted(srv.items())},
             "applies_on": "1.4.206", "version": "1.4.207（暂定，待协调分配）",
             "requires_client": ["overlimit120 APK 补丁（内置等级表 + 白名单）"], "report": REPORT, "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + NL, "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
