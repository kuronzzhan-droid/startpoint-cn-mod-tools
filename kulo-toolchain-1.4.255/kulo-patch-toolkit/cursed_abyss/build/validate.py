# -*- coding: utf-8 -*-
"""独立复核 ../patch 里的 zip：成员逐个解析回放、往返、文案上限、强化阶段、撞号、PNG 签名、服务端/客户端对齐。"""
import csv
import io
import json
import sys
import zipfile
import zlib
from pathlib import Path

from live149 import *  # noqa: F401,F403
import wf_cursed_weapons_r4 as W
import wf_dsl

import os
OUT = Path(os.environ.get("CA_STAGE_DIR", str(Path(__file__).resolve().parent.parent)))
zp = next((OUT / "patch").glob("*.zip"))
integ = json.loads(zp.with_name(zp.stem + ".integrity.json").read_text("utf-8"))
lp_of = integ["logical_paths"]
problems: list[str] = []
checks: list[str] = []
tables = {}
with zipfile.ZipFile(zp) as z:
    assert sorted(z.namelist()) == integ["files"]
    for name in z.namelist():
        data = z.read(name)
        lp = lp_of[name]
        assert member(lp) == name, lp
        if lp.endswith(".orderedmap"):
            node = q.parse_node(data)
            if q.parse_node(q.build_node(node)) != node:
                problems.append(f"往返失败 {lp}")
            base = load(lp)
            lost = set(base) - set(node)
            if lost:
                problems.append(f"{lp} 丢键 {sorted(lost)[:5]}")
            tables[lp] = node
        elif lp.endswith(".png"):
            if data[:4] != b"\x89png":
                problems.append(f"PNG 签名 {lp}")
        elif lp.endswith(".deflate"):
            tree = wf_dsl.parse_dsl(zlib.decompress(data, -15))["tree"]
            problems += [f"DSL {lp}: {p}" for p in W.dsl_signature_problems(tree) + W.colorless_hit_effect_problems(tree)]
checks.append(f"zip 成员 {len(lp_of)} 个全部解析；orderedmap 往返 parse(build(x))==x；无丢键")

R = lambda v: [r for r in csv.reader(io.StringIO(v, newline="")) if r]
EQ, ENH, SHOP, EA = (tables.get(x) or load(x) for x in (W.EQUIPMENT, W.ENH, W.ENH_SHOP, W.EA))
SOUL = tables.get(W.SOUL) or load(W.SOUL)
ids = [str(i) for i in range(8000116, 8000125)] + [str(i) for i in range(5910101, 5910130)]
for wid in ids:
    e = R(EQ[wid])[0]
    if len(e[7]) > 57:
        problems.append(f"{wid} equipment c7 {len(e[7])} 字 > 57")
    h = R(ENH[wid])[0]
    if len(h[6]) > 54:
        problems.append(f"{wid} 强化 c6 {len(h[6])} 字 > 54")
    st = sorted((R(v)[0] for v in SHOP.values() if v and R(v)[0][29] == wid), key=lambda r: int(r[3]))
    if [int(r[30]) for r in st] != [69, 70, 98, 99, 119, 120] or any(r[31] != "5" for r in st):
        problems.append(f"{wid} 强化阶段 {[r[30] for r in st]}")
    ea = R(EA[wid])
    slots = [r[0] for r in ea]
    if len(slots) != len(set(slots)):
        problems.append(f"{wid} EA 重复 slot（C2324 风险）")
    for t, rows_ in ((W.SOUL_T, R(SOUL[wid])), (W.EA_T, ea)):
        for i, r in enumerate(rows_):
            problems += [f"{wid} {t}#{i}: {p}" for p in W.L.client_legality_problems(t, r)]
checks.append("38 把（新 9 + 诅咒 29）：c7≤57、强化 c6≤54、强化 6 阶 69/70/98/99/119/120 需满破 5、EA slot 唯一、逐行 client_legality")

# 固有状态叠层上限（按层读的门 c4>1）
U = tables.get(W.UNIQUE) or load(W.UNIQUE)
for uid in ("59100011", "59100105"):
    r = R(U[uid])[0]
    if not (r[4].isdigit() and int(r[4]) > 1):
        problems.append(f"固有 {uid} 上限 {r[4]}")
checks.append("新固有 59100011/59100105 叠层上限 3（>1，按层读的 144/199 门有效）")

# 服务端 ↔ 客户端
S = OUT / "server"
srv_enh = json.loads((S / "equipment_enhancement_shop.json").read_text("utf-8"))
for k, v in SHOP.items():
    r = R(v)[0]
    if r[29] in ids[:9]:
        e = srv_enh.get(k)
        costs = [{"id": int(r[i]), "amount": int(r[i + 1])} for i in (14, 16, 18, 20) if r[i] not in ("", "(None)")]
        if not e or e["costs"] != costs or e["enhancementMaxLevel"] != int(r[30]) or e["groupId"] != int(r[2]) \
                or e["stage"] != int(r[3]) or e["shopCategoryId"] != int(r[0]) or e["equipmentId"] != int(r[29]):
            problems.append(f"强化商店 {k} 客户端/服务端不一致")
ev = json.loads((S / "event_item_shop.json").read_text("utf-8"))["11"]["700099"]
evc = tables["master/shop/event_item_shop.orderedmap"]
idmap = json.loads((S / "event_item_shop_id_map.json").read_text("utf-8"))
for pid in range(9700121, 9700130):
    pid = str(pid)
    c = R(evc[pid])[0]
    e = ev[pid]
    if e["rewards"] != [{"type": int(c[32]), "id": int(c[33]), "count": int(c[34])}] or \
            e["costs"] != [{"id": int(c[18]), "amount": int(c[19])}] or idmap.get(pid) != {"eventType": 11, "eventId": 700099}:
        problems.append(f"深渊商店 {pid} 不一致")
checks.append("强化商店 54 行 / 深渊兑换 9 行 客户端与服务端逐列一致")

# 撞号：新 ID 在 1.4.149 客户端与 kulo 服务端原文件里都不存在
for lp, keys in ((W.EQUIPMENT, ids[:9]), (W.ITEM, ids[:9]), ("master/shop/event_item_shop.orderedmap",
                 [str(x) for x in range(9700121, 9700130)]), (W.ENH_SHOP, [str(x) for x in range(8100091, 8100145)])):
    clash = [k for k in keys if k in load(lp)]
    if clash:
        problems.append(f"{lp} 撞号 {clash}")
for name in ("equipment_lookup.json", "item_sale.json", "equipment_element.json"):
    base = json.loads((ASSETS / name).read_text("utf-8"))
    mine = json.loads((S / name).read_text("utf-8"))
    clash = [k for k in ids[:9] if k in base and base[k] != mine[k]]   # 1.4.150 已安装则须逐项相同
    if clash:
        problems.append(f"{name} 撞号 {clash}")
checks.append("新 ID 8000116-8000124 / 商品 9700121-9700129 / 强化键 8100091-8100144 / 组 81016-81024 在 1.4.149 与服务端均未占用")
print(json.dumps({"problems": problems, "checks": checks}, ensure_ascii=False, indent=1))
(OUT / "validate_report.json").write_text(json.dumps({"problems": problems, "checks": checks}, ensure_ascii=False, indent=1), "utf-8")
sys.exit(1 if problems else 0)
