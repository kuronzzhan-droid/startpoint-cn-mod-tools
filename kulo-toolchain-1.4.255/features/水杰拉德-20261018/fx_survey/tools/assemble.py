# -*- coding: utf-8 -*-
"""Assemble final rows (json) used by sheets + markdown."""
import json, collections
import meta, classify

FW, FH = 1080, 1920
d = json.load(open("fx_index.json", encoding="utf-8"))
ink = json.load(open("ink.json", encoding="utf-8"))
T = json.load(open("tiers2.json"))
X = json.load(open("extra.json"))
H = json.load(open("hue.json"))
E = {e["path"]: e for e in d["effects"]}
chars = d["chars"]; names = meta.load_names(); dsl2skill = d["dsl2skill"]
ELEM = {"0": "火", "1": "水", "2": "雷", "3": "风", "4": "光", "5": "暗"}
TIERNAME = {"A": "全屏", "D": "全屏叠色", "E": "全场散布", "B": "半屏以上", "C": "跨屏长线"}

rows = []
for p in sorted(set(T) | set(classify.L)):
    if "/powerflip/" in p:
        continue
    e = E[p]; v = ink.get(p, {}); x = X.get(p, {}); h = H.get(p, {})
    t = T.get(p, "E")
    if p in classify.L:
        cat, desc = classify.L[p]
    else:
        b = v.get("best_nodim", {})
        if b.get("ink_h", 0) >= 0.75 * FH and b.get("ink_w", 0) < 0.6 * FW:
            sub = "竖向光柱/长线"
        elif b.get("ink_w", 0) >= 0.9 * FW and b.get("ink_h", 0) < 0.4 * FH:
            sub = "横向光带/长线"
        else:
            sub = "放射长线/大型爆发"
        cat, desc = "beam", sub + "(按包围盒自动归类)"
        if t == "E":
            t = "C"
    us = e["usage"]
    chs = []
    for u in us:
        if u["char"] not in chs:
            chs.append(u["char"])
    ch = chs[0] if chs else p.split("/")[3]
    c = chars.get(ch, {})
    nm = names.get(c.get("id", ""), {}).get("name", "")
    sk = dsl2skill.get(us[0]["dsl"], [{}])[-1] if us else {}
    scales = sorted(set((u["scale"] if u["scale"] is not None else (e["default_scale"] or 1)) for u in us)) or [e["default_scale"] or 1]
    rows.append({
        "path": p, "base": p.split("/")[-1], "dir": "/".join(p.split("/")[:-1]), "tier": t, "tiername": TIERNAME[t],
        "cat": cat, "desc": desc, "char": ch, "chars": chs, "cn": nm, "element": c.get("element", ""), "elem": ELEM.get(c.get("element", ""), "-"),
        "rarity": c.get("rarity", "-"), "role": c.get("role", "-"), "skill_icon": sk.get("icon", "").replace("dynamic/skill/", ""),
        "skill_name": sk.get("sname", ""), "skill_desc": sk.get("desc", ""),
        "frames": e["frames"], "default_scale": e["default_scale"], "scales": scales,
        "subjects": sorted(set(u["subject"] for u in us)), "layers": sorted(set(u["layer"] for u in us)),
        "lifetimes": sorted(set(u["lifetime"] for u in us)), "labels": sorted(set(u["name"] for u in us)),
        "n_images": e["n_images"], "n_graphics": e["n_graphics"], "n_strips": e["n_strips"], "n_keyframes": e["n_keyframes"],
        "n_matrices": e["n_matrices"], "tween": sum(n for k, n in e["tweens"].items() if k != "0"), "c_count": e["c_count"], "c_top": e["c_top"],
        "blends": e["blends"], "sequences": [(s["name"], s["begin"], s["end"], s["kind"]) for s in e.get("sequences", [])],
        "sounds": e.get("sounds", []), "pngs": [(q["png"], q["size"], q["atlas_n"]) for q in e["pngs"]],
        "biggest": x.get("biggest"), "avg_pl": x.get("avg_pl"), "max_pl": x.get("max_pl"), "mag_med": x.get("mag_med"),
        "used_area": h.get("used_area"), "hue": h.get("hue"), "colorful": h.get("colorful_frac"),
        "cov": (v.get("best_nodim") or {}).get("cov"), "cov_all": (v.get("best") or {}).get("cov"),
        "ink_w": (v.get("best_nodim") or {}).get("ink_w"), "ink_h": (v.get("best_nodim") or {}).get("ink_h"),
        "peak_frame": (v.get("best_nodim") or {}).get("frame"),
        "water": c.get("element") == "1", "supporter": c.get("role") == "Supporter", "healer": c.get("role") == "Healer",
    })
json.dump(rows, open("rows.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
cnt = collections.Counter((r["cat"], r["tier"]) for r in rows)
print(len(rows))
for k in classify.CATS:
    print(k, classify.CATS[k], {t: cnt[(k, t)] for t in "ADEBC" if cnt[(k, t)]})
print("tiers", collections.Counter(r["tier"] for r in rows))
print("water", sum(r["water"] for r in rows), "supp", sum(r["supporter"] for r in rows))
print("chars in A/D/E", len(set(r["char"] for r in rows if r["tier"] in "ADE")))
