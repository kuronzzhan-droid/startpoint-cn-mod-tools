# -*- coding: utf-8 -*-
"""1.4.211 -> 1.4.212：十项待定收尾（数据补丁，不需要新 APK，不改服务端）。
  7  杰拉德 149999 character_speech home/home_0 中文字幕「这道伤吗。」→「这道伤疤吗。」（日语原声「この傷か。」无误，只改字）
  8  1699893 / 1599973 按连击叠层（最多 3 层）每层数值上调到官方同类叠层词条的合计区间，desc_override 文案同步
  9  item_quest_search 新增 36 键 10000400–10000453（自制领主币 / 强化核）→ 掉落它的领主战 / 高难联机关卡
  10 领主币商店分类 98「魂珠兑换」换专属横幅 quest/boss_battle/banner/mod_soul_exchange（1000x184，同官方格式）
视图：kulo active 1.4.131–1.4.206 + 超限 localsrv 链上的 1.4.207–1.4.211（WF_EXTRA_ZIPS）。
用法：python build_212.py [--write]"""
import copy, hashlib, io, json, os, sys, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
os.environ["WF_TIP"] = "206"
os.environ["WF_EXTRA_ZIPS"] = (HERE / "extra_zips.txt").read_text("utf-8").strip()
BUILD = Path(r"D:/WF/out/kulo-patch-toolkit/cursed_abyss/build")
sys.path.insert(0, str(BUILD))
os.chdir(BUILD)
sys.path.insert(0, r"D:/WF/startpoint-cn-wiki/mod-tools")
from p192_common import *  # noqa  (live149 + 多根资产读取)
import base149
import wf_mod_tool as M
import wf_share_update_codec as codec
sys.path.insert(0, r"D:/WF/out/kulo-patch-toolkit/oldrepo_modtools")
import wf_client_legality as L

assert base149._ZIPS[-1].name == "pinball-1.4.210-1.4.211-1-wagner-overlimit-tweak-local.zip", base149._ZIPS[-1]
NAME = "pinball-1.4.211-1.4.212-1-ten-items-local.zip"
PATCH = HERE / "patch"
NL = chr(10)
sha = lambda b: hashlib.sha256(b).hexdigest()
LOG, files, lps = [], {}, {}

AB_LP = "master/ability/ability.orderedmap"
CAS_LP = "master/string/custom_ability_string.orderedmap"
SP_LP = "master/character/character_speech.orderedmap"
IQS_LP = "master/search/item_quest_search.orderedmap"
CAT_LP = "master/shop/boss_coin_shop_category.orderedmap"
EDIT = {AB_LP: {}, CAS_LP: {}, IQS_LP: {}, CAT_LP: {}}
T = {lp: load(lp) for lp in EDIT}


def leaf(v, rs):
    from stage_all import csv_text
    s = csv_text(rs)
    return s if v.endswith(NL) else s.rstrip(NL)


def raw_replace(lp, edits):
    """外层 raw rows 原样保留，只替换/追加 edits 中的键 chunk（未动键逐字节相同）。"""
    raw, _ = read_raw(lp)
    om = M.read_orderedmap_raw_rows_from_bytes(raw, lp)
    keys0, rows0 = list(om.keys), list(om.rows)
    added = []
    for k, node in edits.items():
        if k in keys0:
            assert q.build_node(load(lp)[k]) == rows0[keys0.index(k)], (lp, k)
            om.rows[om.keys.index(k)] = q.build_node(node)
        else:
            om.keys.append(k); om.rows.append(q.build_node(node)); added.append(k)
    out = M.build_orderedmap_raw_rows(om)
    back = M.read_orderedmap_raw_rows_from_bytes(out, lp)
    assert back.keys == keys0 + added
    assert [i for i in range(len(rows0)) if back.rows[i] != rows0[i]] == sorted(keys0.index(k) for k in edits if k in keys0)
    return out


def cas_replace(key, pairs):
    v = T[CAS_LP][key]; s = rows(v)[0]; assert len(rows(v)) == 1 and len(s) == 1
    t = s[0]
    for old, new in pairs:
        assert t.count(old) == 1, (key, old)
        t = t.replace(old, new)
    nv = leaf(v, [[t]]); assert rows(nv)[0] == [t]
    EDIT[CAS_LP][key] = nv
    return s[0], t


# ============================================================ 7 杰拉德 home_0 字幕
raw, base = aread("upload", SP_LP)
flat = codec.unpack(raw); assert codec.unpack(codec.pack(flat)) == flat
srows = codec.csv_read(flat["149999"])
hit = [r for r in srows if r[4] == "home/home_0"]; assert len(hit) == 1, hit
OLD7, NEW7 = "这道伤吗。是没能守住的那天留下的印记。", "这道伤疤吗。是没能守住的那天留下的印记。"
assert hit[0][3].startswith(OLD7), hit[0][3]
before7 = hit[0][3]
hit[0][3] = NEW7 + before7[len(OLD7):]
flat2 = dict(flat); flat2["149999"] = codec.csv_write_like(srows, flat["149999"])
sp_out = codec.pack(flat2)
chk = codec.unpack(sp_out); assert list(chk) == list(flat) and all(chk[k] == flat[k] for k in flat if k != "149999")
files[amember("upload", SP_LP)] = sp_out; lps[amember("upload", SP_LP)] = SP_LP
LOG.append(f"7 杰拉德 149999 character_speech home/home_0 字幕：「{before7}」→「{hit[0][3]}」（语音 mp3 不动）")

# ============================================================ 8 叠层词条每层数值
def set_val(key, idx, kind, old, new):
    rs = [r for r in rows(T[AB_LP][key]) if r]
    r = rs[idx]
    assert (r[97], r[102], r[109], r[113], r[114]) == ("2", "3", kind, old, old), (key, idx, r[97], r[102], r[109], r[113], r[114])
    r[113] = r[114] = new
    EDIT[AB_LP][key] = leaf(T[AB_LP][key], rs)
    for i, x in enumerate(rs):
        assert len(x) == 126
        p = L.client_legality_problems("ability", x); assert not p, (key, i, p)

# 1699893：rows 0/1 都在同一键，先改 0 再改 1（在已改的 leaf 上）
rs = [r for r in rows(T[AB_LP]["1699893"]) if r]
assert [(rs[i][97], rs[i][102], rs[i][109], rs[i][113]) for i in (0, 1)] == [("2", "3", "410", "3000"), ("2", "3", "0", "3000")]
rs[0][113] = rs[0][114] = "6000"
rs[1][113] = rs[1][114] = "10000"
EDIT[AB_LP]["1699893"] = leaf(T[AB_LP]["1699893"], rs)
for i, x in enumerate(rs):
    p = L.client_legality_problems("ability", x); assert not p, ("1699893", i, p)
cas_replace("desc_override_ruin_girl_campus_3",
            [("当前每有1连击，暗属性角色直接攻击造成的伤害+3%（独立乘区）、攻击力+3%（最多3次）",
              "当前每有1连击，暗属性角色直接攻击造成的伤害+6%（独立乘区）、攻击力+10%（最多3次）")])
LOG.append("8 一起续杯的约定 169989 能力3(1699893) #0 Fever 中每连击 暗属性角色 kind410 直击独立乘区 3% → 6%（3 层合计 9% → 18%）；"
           "#1 攻击力 3% → 10%（合计 9% → 30%）；上限 3 层不变；desc_override_ruin_girl_campus_3 同步")
set_val("1599973", 6, "23", "6500", "15000")
cas_replace("desc_override_guildknight_leader_tavern_3",
            [("强化弹射伤害随连击数提高（每1连击＋6.5%，最多3次）", "强化弹射伤害随连击数提高（每1连击＋15%，最多3次）")])
LOG.append("8 今晚由团长买单 159997 能力3(1599973) #6 持有「灯火正旺」时每连击 自身 kind23 强化弹射伤害 6.5% → 15%（3 层合计 19.5% → 45%）；"
           "上限 3 层不变；desc_override_guildknight_leader_tavern_3 同步")

# ============================================================ 2 核对出的两处与平衡表不符（墨斯伊克 / 魔王）
UQ_LP = "master/character/unique_condition.orderedmap"
EDIT[UQ_LP] = {}; T[UQ_LP] = load(UQ_LP)
# 墨斯伊克 149997 能力2 #4：核对后保持原样。kind 9 + OneOfParty(龙) + 赋予触发者 = 每名处于攻击力提升的龙族角色各自 +5%，
# 客户端自动文案按 3 名触发者显示「最大+15%」，与平衡表原文一致（表上的 15% 就是游戏内文案）；改 kind 38 会让文案变成最大 45%，不改。
# 魔王 169995：权能每级 +5%「最大 500%」，但固有上限 99 层 → 实际 495%；固有上限改 100。
u = row(T[UQ_LP]["1699950"].rstrip(NL)); assert u[0] == "unique_maou2_playable_authority" and u[4] == "99", u
u2 = list(u); u2[4] = "100"
EDIT[UQ_LP]["1699950"] = join(u2) + (NL if T[UQ_LP]["1699950"].endswith(NL) else "")
rs2 = [x for x in rows(T[AB_LP]["1699952"]) if x]
assert [x[102] for x in rs2[:3]] == ["100", "100", "100"], [x[102] for x in rs2[:3]]
LOG.append("2 魔王 169995 固有「魔王权能」(unique 1699950) 层数上限 99 → 100：能力2 每级 +5% 三条（限 100 次）真正能到表里写的最大 500%；"
           "≥66 门槛不受影响，状态图标最多显示 99")
# 魔王 能力3 四条「每 N 秒」伤害：表写「最近敌人」，数据 255/256 打全体 → 356/357（最近敌人，同参数列 48/51/52）。
rs3 = [x for x in rows(T[AB_LP]["1699953"]) if x]
for i, old, new in ((2, "255", "356"), (3, "256", "357"), (4, "255", "356"), (5, "256", "357")):
    assert rs3[i][27] == "77" and rs3[i][47] == old and rs3[i][48] == "0", (i, rs3[i][47])
    rs3[i][47] = new
EDIT[AB_LP]["1699953"] = leaf(T[AB_LP]["1699953"], rs3)
for i, x in enumerate(rs3):
    p = L.client_legality_problems("ability", x); assert not p, ("1699953", i, p)
LOG.append("2 魔王 169995 能力3(1699953) #2–#5 每 2/3/3/4 秒的光/暗伤害 目标 全体敌人(255/256) → 最近敌人(356/357)，倍率与间隔不变，与平衡表「最近敌人」一致")

# ============================================================ 9 获取途径 item_quest_search
SRC = json.loads((HERE / "coin_sources.json").read_text("utf-8"))
I = load("master/item/item.orderedmap")
BQ = load("master/quest/boss_battle_quest.orderedmap")
HQ = load("master/quest/event/hard_multi_event_quest.orderedmap")
new_keys = {}
for it in range(10000400, 10000454):
    k = str(it)
    if k not in I:
        continue
    assert k not in T[IQS_LP], k
    srcs = SRC[k]
    out = []
    for f, qid, grp, exp in srcs:
        qid = int(qid)
        if f.startswith("boss_battle_quest"):
            boss, diff = (qid // 1000) % 1000, qid % 1000
            assert qid == 1000000 + boss * 1000 + diff
            assert str(diff) in BQ["1"][str(boss)], (k, qid)
            assert row(BQ["1"][str(boss)][str(diff)])[0] == str(qid), (k, qid)
            out.append(["2", "1", str(boss), str(diff), str(qid), exp])
        elif f == "hard_multi_event_quest.json":
            ev, n = qid // 1000, qid % 1000
            assert str(n) in HQ[str(ev)] and row(HQ[str(ev)][str(n)])[0] == str(qid), (k, qid)
            out.append(["18", str(ev), "", str(n), str(qid), exp])
        else:
            raise AssertionError((k, f))
    out.sort(key=lambda r: -r[5])
    def num(x):
        return str(int(x)) if float(x).is_integer() else repr(float(x))
    rs = [r[:5] + [num(r[5])] for r in out]
    new_keys[k] = leaf("x", rs)
    EDIT[IQS_LP][k] = new_keys[k]
assert len(new_keys) == 36, len(new_keys)
LOG.append(f"9 item_quest_search 新增 {len(new_keys)} 键 10000400–10000453：领主币(偶数号 9 个) → 领主战 1080–1088 难度 1–5（reference 2）；"
           "强化核(奇数号 27 个) → 高难联机 2025–2030/2035/2037–2041/2051–2056/2080–2088（reference 18）；"
           "排序权重=服务端 score_reward 固定掉落 + 稀有池 rarity×个数（与服务端结算一致）")

# ============================================================ 10 魂珠兑换横幅
BANNER_LP = "quest/boss_battle/banner/mod_soul_exchange.png"
png = (HERE / "banner" / "cand_A_purple_steel.png").read_bytes()
from PIL import Image
im = Image.open(io.BytesIO(png)); assert im.size == (1000, 184) and im.mode == "RGBA", (im.size, im.mode)
assert png[:8] == bytes([137, 80, 78, 71, 13, 10, 26, 10])
stored = bytes([137, 112, 110, 103]) + png[4:]          # 官方存储态 \x89png
ref, _ = aread("upload", "quest/boss_battle/banner/mod_five_boss_exchange.png"); assert ref[:4] == stored[:4]
assert aread("upload", BANNER_LP)[0] is None
assert png_img(stored).tobytes() == Image.open(io.BytesIO(png)).convert("RGBA").tobytes()
files[amember("upload", BANNER_LP)] = stored; lps[amember("upload", BANNER_LP)] = BANNER_LP
r = row(T[CAT_LP]["98"].rstrip(NL))
assert r[0] == "mod_soul_exchange" and r[9] == "quest/boss_battle/banner/mod_five_boss_exchange", r
r2 = list(r); r2[9] = "quest/boss_battle/banner/mod_soul_exchange"
v = T[CAT_LP]["98"]
EDIT[CAT_LP]["98"] = join(r2) + (NL if v.endswith(NL) else "")
assert row(EDIT[CAT_LP]["98"].rstrip(NL)) == r2
LOG.append("10 boss_coin_shop_category 98 横幅 mod_five_boss_exchange → mod_soul_exchange（新 PNG 1000x184 RGBA，官方领主币横幅版式："
           "左侧魂珠像素物件、右侧放射光+方格带+禁忌星铁大图标、标题「魂珠兑换」副标题「- 禁忌星铁 -」）；背景列不变")

# ============================================================ 编码 + 写包
for lp, ed in EDIT.items():
    if ed:
        b = raw_replace(lp, ed)
        back = q.parse_node(b)
        assert set(back) == set(T[lp]) | set(ed) and sorted(k for k in back if back.get(k) != T[lp].get(k)) == sorted(ed), lp
        files[member(lp)] = b; lps[member(lp)] = lp
        LOG.append(f"{lp}：改/增键 {sorted(ed)[:6]}{'…' if len(ed) > 6 else ''}（{len(ed)} 键）；其余键 chunk 逐字节保留")


def main():
    print("\n".join(LOG))
    if "--write" not in sys.argv:
        print("DRY RUN", len(files), "members"); return 0
    PATCH.mkdir(exist_ok=True)
    path = PATCH / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(files): zf.writestr(m, files[m])
    blob = path.read_bytes(); assert len(blob) <= 5 * 1024 * 1024
    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None and all(zf.read(m) == files[m] for m in files)
    integ = {"name": NAME, "size": len(blob), "sha256": sha(blob), "members": len(files), "files": sorted(files),
             "member_sha256": {m: sha(files[m]) for m in sorted(files)}, "logical_paths": {m: lps[m] for m in sorted(files)},
             "new_files": [BANNER_LP], "server_files": {}, "applies_on": "1.4.211", "version": "1.4.212",
             "requires_client": "纯数据", "log": LOG}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(json.dumps({k: integ[k] for k in ("name", "size", "sha256", "members")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
