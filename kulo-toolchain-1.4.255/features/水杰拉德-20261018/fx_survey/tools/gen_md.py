# -*- coding: utf-8 -*-
import json, collections
from pathlib import Path
import classify

rows = json.load(open("rows.json", encoding="utf-8"))
OUT = Path(r"D:/WF/out/水杰拉德-20261018/fx_survey/全屏特效清单.md")
TORD = {"A": 0, "D": 1, "E": 2, "B": 3, "C": 4}
FILE = {"flash": "全屏闪光压暗", "radial": "放射光爆", "fall": "从天而降", "wave": "波浪涟漪漩涡", "field": "场地覆盖边框",
        "giant": "巨物召唤", "stage": "舞台烟花", "scatter": "散布粒子", "slash": "巨型斩击", "beam": "贯穿光柱长线_1"}
SUBJ = {-1: "场地中心", -2: "场地左上", -17: "自身", -18: "球/主体"}
LAY = {"SuperForesideOfCharacter": "最前", "ForesideOfCharacter": "角色前", "BacksideOfCharacter": "角色后",
       "NonPixelArt": "高清层", "SameAsCharacter": "同层"}

def subj(r):
    out = []
    for s in r["subjects"]:
        out.append(SUBJ.get(s, f"参考点{s}"))
    return "/".join(out[:2]) + ("…" if len(out) > 2 else "")

def lay(r):
    return "/".join(LAY.get(x, x) for x in r["layers"])

def flags(r):
    f = ""
    if r["water"]:
        f += "【水】"
    if r["supporter"]:
        f += "【辅助】"
    if r["healer"]:
        f += "【治疗】"
    return f

def png(r):
    if not r["pngs"]:
        return "-"
    p, sz, n = r["pngs"][0]
    s = f"{p.split('/')[-1]} {sz[0]}×{sz[1]}"
    if r["used_area"]:
        ua = r["used_area"]
        s += f"(本件{ua/1e6:.3f}Mpx)" if ua >= 10000 else f"(本件{ua}px)"
    return s

def struct(r):
    big = r["biggest"] or [0, 0]
    s = f"层{r['n_graphics']}/轨{r['n_strips']}/图{r['n_images']}(最大{big[0]}×{big[1]})/面片≈{r['avg_pl']}"
    if r["c_count"]:
        s += f"/c×{r['c_count']}"
    return s

def charcell(r):
    s = f"`{r['char']}` {r['cn']}"
    if len(r["chars"]) > 1:
        s += f" 等{len(r['chars'])}人"
    return s

def sc(r):
    return "/".join(str(x) for x in r["scales"])

def table(rs):
    L = ["| 角色 | 属性·★·定位 | 特效(battle/effect/…) | 档 | 帧·缩放·锚·层 | 构造 | 图集 | 外观 |",
         "|---|---|---|---|---|---|---|---|"]
    for r in rs:
        L.append("| {} | {}★{} {} {} | `{}` | {} | {}f·s{}·{}·{} | {} | {} | {} |".format(
            charcell(r), r["elem"], r["rarity"], r["role"], flags(r), r["path"].replace("battle/effect/", ""), r["tiername"],
            r["frames"], sc(r), subj(r), lay(r), struct(r), png(r), r["desc"]))
    return "\n".join(L)

def ctable(rs):
    L = ["| 角色 | 属性·★·定位 | 特效 | 帧·缩放 | 墨迹包围盒(战场单位) | 自动子类 |", "|---|---|---|---|---|---|"]
    for r in rs:
        L.append("| {} | {}★{} {} {} | `{}` | {}f·s{} | {:.0f}×{:.0f} | {} |".format(
            charcell(r), r["elem"], r["rarity"], r["role"], flags(r), r["path"].replace("battle/effect/", ""), r["frames"], sc(r),
            r["ink_w"] or 0, r["ink_h"] or 0, r["desc"].replace("(按包围盒自动归类)", "")))
    return "\n".join(L)

def key(r):
    return (TORD[r["tier"]], 0 if r["water"] else 1, r["char"], r["base"])

cnt_t = collections.Counter(r["tier"] for r in rows)
body = []
for cat, name in classify.CATS.items():
    rs = sorted([r for r in rows if r["cat"] == cat], key=key)
    main = [r for r in rs if r["tier"] != "C"]
    cs = [r for r in rs if r["tier"] == "C"]
    tc = collections.Counter(r["tier"] for r in main)
    nw = sum(r["water"] for r in rs); ns = sum(r["supporter"] for r in rs)
    body.append(f"### 4.{list(classify.CATS).index(cat)+1} {name}\n")
    body.append(f"共 {len(rs)} 个(全屏 {tc['A']}、全屏叠色 {tc['D']}、全场散布 {tc['E']}、半屏以上 {tc['B']}"
                + (f"、跨屏长线 {len(cs)}" if cs else "") + f");其中水属性 {nw} 个、辅助 {ns} 个。预览:`预览_{FILE[cat]}.png`"
                + ("(长线另见 `预览_贯穿光柱长线_2.png`、`_3.png`)" if cat == "beam" else "") + "\n")
    if main:
        body.append(table(main) + "\n")
    if cs:
        body.append("\n**跨屏长线(C 档,单方向贯穿屏幕但面积小,按墨迹包围盒自动归类,未逐个人工复核):**\n")
        body.append(ctable(cs) + "\n")

water = sorted([r for r in rows if r["water"] and r["tier"] in "ADEB"], key=key)
supp = sorted([r for r in rows if r["supporter"] and r["tier"] in "ADEB"], key=key)

def short_list(rs):
    L = ["| 角色 | ★·定位 | 特效 | 档 | 类型 | 外观 |", "|---|---|---|---|---|---|"]
    for r in rs:
        L.append(f"| {charcell(r)} | {r['elem']}★{r['rarity']} {r['role']} | `{r['base']}` | {r['tiername']} | {classify.CATS[r['cat']].split('(')[0]} | {r['desc']} |")
    return "\n".join(L)

md = Path("md_head.md").read_text(encoding="utf-8")
md = md.replace("{{TIERS}}", f"全屏 {cnt_t['A']} + 全屏叠色 {cnt_t['D']} + 全场散布 {cnt_t['E']} + 半屏以上 {cnt_t['B']} + 跨屏长线 {cnt_t['C']} = {len(rows)}")
md = md.replace("{{BODY}}", "\n".join(body))
md = md.replace("{{WATER}}", short_list(water))
md = md.replace("{{SUPP}}", short_list(supp))
md = md.replace("{{NWATER}}", str(len(water))).replace("{{NSUPP}}", str(len(supp)))
OUT.write_text(md, encoding="utf-8")
print("wrote", OUT, len(md))
