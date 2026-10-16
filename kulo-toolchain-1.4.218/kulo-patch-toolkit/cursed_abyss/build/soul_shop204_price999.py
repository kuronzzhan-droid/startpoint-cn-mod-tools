# -*- coding: utf-8 -*-
"""1.4.204 魂珠兑换: 作者 1015 改价 5 -> 999 禁忌星铁。在 soul_shop204.py 产物上只改 98 分类 54 行的 c17/c18 价格与 c10 文案,
服务端 server27/boss_coin_shop.json["98"] 的 costs.amount 5 -> 999。其余字节不动。"""
import os, json, hashlib, zipfile, re
os.environ["WF_TIP"] = "203"
from live149 import *  # noqa
import base149
assert base149._ZIPS[-1].name == "pinball-1.4.202-1.4.203-1-balance-1015-local.zip"
from soul_shop204 import append_at, client_additions, PRODUCTS, CURRENCY, NAME, OUT, SRV
import soul_shop204 as S
S.PRICE = 999
OLD_T, NEW_T = "消耗5个禁忌星铁兑换1个能力魂珠。", "消耗999个禁忌星铁兑换1个能力魂珠。"
members = {}
for lp, (path, added) in client_additions().items():
    if lp.endswith("boss_coin_shop.orderedmap"):
        for k, txt in list(added.items()):
            r = row(txt)
            assert r[17] == str(CURRENCY) and r[18] == "999", r[17:19]
            assert r[10] == OLD_T; r[10] = NEW_T
            from stage_all import csv_text
            added[k] = csv_text([r]).rstrip("\n") if not txt.endswith("\n") else csv_text([r])
    raw, src = read_raw(lp)
    before = q.parse_node(raw)
    data = append_at(raw, path, added)
    exp = before
    for k in path: exp = exp[k]
    exp.update(added)
    assert q.parse_node(data) == before
    members[member(lp)] = (lp, data)
path = OUT / NAME
with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
    for m in sorted(members):
        info = zipfile.ZipInfo(m, date_time=(2026, 10, 15, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 0; info.external_attr = 0o600 << 16
        zf.writestr(info, members[m][1])
blob = path.read_bytes()
# server
sp = SRV / "boss_coin_shop.json"; t = sp.read_bytes().decode("utf-8")
i = t.index('\n  "98": {'); head, tail = t[:i], t[i:]
n = tail.count('"amount": 5\n') + tail.count('"amount": 5,')
tail2 = re.sub(r'("id": 10000311,\s*"amount": )5\b', r"\g<1>999", tail)
assert tail2.count('"amount": 999') == 54, tail2.count('"amount": 999')
sp.write_bytes((head + tail2).encode("utf-8"))
js = json.loads((head + tail2))
assert all(v["costs"][0]["amount"] == 999 for v in js["98"].values()) and len(js["98"]) == 54
integ = {"name": NAME, "size": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "members": len(members),
         "files": sorted(members), "member_sha256": {m: hashlib.sha256(d).hexdigest() for m, (lp, d) in sorted(members.items())},
         "logical_paths": {m: lp for m, (lp, d) in sorted(members.items())}, "applies_on": "1.4.203", "version": "1.4.204",
         "server_files": {"assets/boss_coin_shop.json": hashlib.sha256((head + tail2).encode()).hexdigest()},
         "log": ["魂珠兑换 98 分类 54 件: 5 → 999 禁忌星铁/个, 限购 999 不变"]}
path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
print(NAME, len(blob), integ["sha256"]); print("server boss_coin_shop.json", integ["server_files"]["assets/boss_coin_shop.json"])
