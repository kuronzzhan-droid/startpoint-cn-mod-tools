# -*- coding: utf-8 -*-
"""逐动作数 SE（上界：DSL 里每条 ShowEffect 的 timeline.sounds 条数之和；碰撞/命中才出的段按最大次数计）。
before = 1.4.209 实装（build_fx_loud_backup + seris_pf）；after = 本轮（build_fx + seris_pf_quiet + 新 dsl_hooks）。"""
import copy
import importlib
import json
import sys
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, r"D:/WF/out/赛瑞斯重做-20261015/build")
import fxlib as X  # noqa: E402

FXROOT = "battle/effect/skill_unique/seris_dragon_king/"


def fam_sounds(modname):
    m = importlib.import_module(modname)
    out = {}
    for _sub, fn in m.FAMILIES:
        F = fn()
        for e in F.effects:
            out[F.dir_lp + "/" + e.name] = [(s["path"].split("/")[-1], s["begin"], s["volume"]) for s in e.sounds]
    return out


_cache = {}


def official_sounds(p):
    if p not in _cache:
        if p.startswith(FXROOT + "pfq_"):
            sub = p[len(FXROOT):]
            raw = (X.FX / "pf_quiet" / "game" / (p + ".timeline.amf3.deflate")).read_bytes()
        else:
            raw = X.read_raw(p + ".timeline.amf3.deflate")[0]
        tl = X.wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
        _cache[p] = [(s["path"].split("/")[-1], s["begin"], s["volume"]) for s in tl["sounds"]]
    return _cache[p]


def count(tree, fams):
    res = []
    def walk(x):
        if isinstance(x, list):
            if len(x) >= 3 and x[0] == "ShowEffect" and isinstance(x[2], list):
                p = x[2][1]
                res.extend(fams[p] if p in fams else official_sounds(p))
            for y in x:
                walk(y)
    walk(tree)
    return res


def lv4_tree(PF, types, form, hooks):
    t = PF.compose(types, 3, lv4=True)
    blk = t[11][1]
    blk.insert(1, ["Command", copy.deepcopy(hooks["pf_lv4"][form])])
    blk.insert(2, ["Command", copy.deepcopy(hooks["pf_lv4"]["red_bolt_at_ball"])])
    return t


def skill_actions(hooks, fams, auto_key):
    d = hooks["dragon_skill"]
    sk = {
        "人形技能 苍海潮涌": [hooks["human_skill"]["node"]],
        "龙形技能 龙王吐息（升空+3 段）": [d["flight"], d["breath_1"], d["breath_2"], d["breath_3"]],
        "进 Fever：化龙+自动龙息": [hooks["transform_on_fever_start"]["node"], d["flight"], d[auto_key], d["breath_2"], d["breath_3"]],
        "冲刺 龙翼冲撞": [hooks["dash"]["human"]],
        "Fever 结束 回龙人": [hooks["revert_on_fever_end_optional"]["tree"]],
    }
    return {k: count(v, fams) for k, v in sk.items()}


def main():
    hooks_after = json.loads((X.FX / "dsl_hooks.json").read_text("utf-8"))
    hooks_before = copy.deepcopy(hooks_after)
    for k in ("breath_2", "breath_3"):
        hooks_before["dragon_skill"][k][2][1] = FXROOT + "breath/seris_breath"
    fb, fa = fam_sounds("build_fx_loud_backup"), fam_sounds("build_fx")
    PFb, PFa = importlib.import_module("seris_pf"), importlib.import_module("seris_pf_quiet")
    rows = []
    b = skill_actions(hooks_before, fb, "breath_1")
    a = skill_actions(hooks_after, fa, "breath_1_auto")
    for k in b:
        rows.append((k, b[k], a[k]))
    for form, types in (("龙人形", PFb.TYPES_HUMAN), ("真龙形", PFb.TYPES_DRAGON)):
        for lv in (1, 2, 3):
            rows.append((f"PF Lv{lv} {form}", count(PFb.compose(types, lv), fb), count(PFa.compose(types, lv), fa)))
        f = "human" if form == "龙人形" else "dragon"
        rows.append((f"PF Lv4 {form}", count(lv4_tree(PFb, types, f, hooks_before), fb), count(lv4_tree(PFa, types, f, hooks_after), fa)))
    out = []
    for k, bb, aa in rows:
        out.append({"action": k, "before": len(bb), "after": len(aa), "before_se": bb, "after_se": aa})
        print(f"{k:28s} {len(bb):3d} -> {len(aa):2d}   {[x[0] + ('' if x[2] == -1 else f'(vol{x[2]})') for x in aa]}")
    (HERE / "se_count.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), "utf-8")


if __name__ == "__main__":
    main()
