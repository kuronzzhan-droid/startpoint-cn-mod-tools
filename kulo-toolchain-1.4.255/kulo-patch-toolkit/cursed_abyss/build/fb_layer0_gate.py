# -*- coding: utf-8 -*-
"""五重每轮 layer0 门禁：最坏三人房（3 队 × 6 = 18 个不同角色，按 layer0 占用贪心挑最重）+ 该轮全部 boss/召唤物。
用法：python fb_layer0_gate.py [overlay.pkl] [--json out.json]
overlay.pkl = pickle {logical_path: bytes}（模拟补丁后的 live 视图）。"""
import json, pickle, sys
from fb_layer0_sim import *  # noqa

R0 = [1099031, 1099032, 1099033, 1099034, 1099035, 1099036, 1099037, 1099038, 1099039]
R1 = [1099051, 1099052, 1099053, 1099054, 1099055, 1099056, 1099057]
COMMON_FX = [  # ActionDslAssetResolver / 通用命中特效写死路径（字符串闭包抓不到）
    "battle/effect/hit/condition/general_bipolar_down/general_bipolar_down/x",
    "battle/effect/hit/down_fever_gauge/down_fever_gauge/down_fever_gauge",
    "battle/effect/hit/down_fever_gauge/down_fever_gauge_unconverted/down_fever_gauge_unconverted",
    "battle/effect/hit/down_skill_gauge/down_skill_gauge/down_skill_gauge",
    "battle/effect/hit/down_skill_gauge/down_skill_gauge_unconverted/down_skill_gauge_unconverted",
    "battle/effect/hit/normal_damage/dark/x", "battle/effect/hit/normal_damage/fire/x",
    "battle/effect/hit/normal_damage/non_attribute/x", "battle/effect/hit/normal_damage/shine/x",
    "battle/effect/hit/normal_damage/splash/x", "battle/effect/hit/normal_damage/thunder_small/x",
    "battle/effect/hit/normal_damage/tornado/x",
    "battle/effect/hit/up_fever_gauge/up_fever_gauge/up_fever_gauge",
    "battle/effect/hit/up_fever_gauge/up_fever_gauge_unconverted/up_fever_gauge_unconverted",
    "battle/effect/hit/up_skill_gauge/up_skill_gauge/up_skill_gauge",
    "battle/effect/hit/up_skill_gauge/up_skill_gauge_unconverted/up_skill_gauge_unconverted",
    "battle/effect/skill_chain/x",
]


def worst_party(v, chars):
    """贪心：3 队长（像素+技能+PF）→ 6 主位（像素+技能）→ 9 助战（技能），每步取边际面积最大者。"""
    have, pick = {}, []

    def gain(cid, parts):
        return sum(area(d) for p in parts for s, d in chars[cid][p].items() if s not in have)

    def take(cid, parts, role):
        for p in parts:
            have.update(chars[cid][p])
        pick.append((cid, chars[cid]["code"], role))
    for role, parts, n in (("leader", ("main", "skill", "leader"), 3), ("main", ("main", "skill"), 6),
                           ("unison", ("skill",), 9)):
        for _ in range(n):
            used = {c for c, _, _ in pick}
            best = max((c for c in chars if c not in used), key=lambda c: (gain(c, parts), c))
            take(best, parts, role)
    return pick, have


def char_table(v):
    out = {}
    for cid in v.table(T_CH):
        try:
            ca = char_assets(v, cid)
        except Exception:
            continue
        m = char_sheets(v, ca, "main")
        if not m:
            continue
        out[cid] = dict(code=ca["code"], main=m, skill=char_sheets(v, ca, "skill"), leader=char_sheets(v, ca, "leader"))
    return out


def gate(v, party_sheets, quests=R0 + R1, drop=None):
    common = {s: d for s, (d, _) in sheets_from_anims(v, {a: "common" for a in COMMON_FX}).items()}
    res = {}
    for qid in quests:
        an, bosses = round_assets(v, qid, drop)
        bs = {s: d for s, (d, _) in sheets_from_anims(v, an).items()}
        allsh = dict(common); allsh.update(bs); allsh.update(party_sheets)
        r = run_pack(allsh)
        r["boss_area"] = sum(area(d) for d in bs.values())
        r["boss_rects"] = len(bs)
        r["bosses"] = bosses
        res[qid] = r
    return res


def fmt(r):
    sz = f"{r['w']}x{r['h']}" if r["ok"] else "—"
    return (f"{r['rects']:>3} rects  {r['area']/1e6:6.3f} Mpx  fill {100*r['fill']:5.1f}%  "
            f"atlas {sz:>10}  {'PASS' if r['ok'] else 'FAIL size exceeded'}")


if __name__ == "__main__":
    ov = pickle.load(open(sys.argv[1], "rb")) if len(sys.argv) > 1 and sys.argv[1].endswith(".pkl") else {}
    v = View(ov)
    chars = char_table(v)
    pick, ps = worst_party(v, chars)
    print("worst party:", [(c, code, role) for c, code, role in pick])
    print(f"party sheets {len(ps)}  {sum(area(d) for d in ps.values())/1e6:.3f} Mpx")
    res = gate(v, ps)
    for qid, r in res.items():
        print(qid, f"boss {r['boss_rects']:>2}/{r['boss_area']/1e6:.3f}", fmt(r))
    if "--json" in sys.argv:
        json.dump({"pick": pick, "party_mpx": sum(area(d) for d in ps.values()) / 1e6,
                   "rounds": {str(k): v_ for k, v_ in res.items()}},
                  open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
