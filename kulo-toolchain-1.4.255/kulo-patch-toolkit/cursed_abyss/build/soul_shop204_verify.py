# -*- coding: utf-8 -*-
"""独立核验 pinball-1.4.203-1.4.204-1-soul-exchange-shop-local.zip + server27 (移植自 bughunt soul_shop_verify.py)。
不调用构建器的商品生成函数; 逐字段对照 item 表与服务端 JSON; 逐键核对既有原始压缩块。"""
import os, json, hashlib, zipfile
os.environ["WF_TIP"] = "203"
os.environ.pop("WF_EXTRA_ZIPS", None)
from live149 import *
import base149
from soul_shop204 import (split_map, json_bytes, strict_json, blob, NAME, OUT, SRV, SHOP, CATEGORY, ITEM, STAGE,
                          QUEST, WEAPONS, PRODUCTS, START, END, CURRENCY, PRICE, STOCK, ANCHOR, BLOBS)
assert base149._ZIPS[-1].name == "pinball-1.4.202-1.4.203-1-balance-1015-local.zip"
sha = lambda b: hashlib.sha256(b).hexdigest()
CANDIDATE = Path(r"D:/WF/bughunt-20261014/out/pinball-1.4.202-1.4.203-1-soul-exchange-shop-candidate.zip")


def preserved(before_raw, after_raw, path, added_keys):
    bk, bc = split_map(before_raw); ak, ac = split_map(after_raw)
    assert ak == bk + ([] if path else list(added_keys)), (path, ak[-3:])
    n = 0
    for i, k in enumerate(bk):
        if path and k == path[0]:
            n += preserved(bc[i], ac[i], path[1:], added_keys)
        else:
            assert ac[i] == bc[i], (path, k); n += 1
    return n


def main():
    zp = OUT / NAME
    integ = json.loads(zp.with_name(zp.stem + ".integrity.json").read_text("utf-8"))
    blob_ = zp.read_bytes()
    assert integ["sha256"] == sha(blob_) and integ["size"] == len(blob_)
    assert integ["applies_on"] == "1.4.203" and integ["version"] == "1.4.204"
    lps = (SHOP, CATEGORY, STAGE, QUEST)
    raw, parsed = {}, {}
    with zipfile.ZipFile(zp) as zf:
        assert zf.testzip() is None and sorted(zf.namelist()) == sorted(member(l) for l in lps)
        for l in lps:
            info = zf.getinfo(member(l))
            assert info.compress_type == zipfile.ZIP_DEFLATED and info.date_time == (2026, 10, 15, 0, 0, 0)
            raw[l] = zf.read(info); parsed[l] = q.parse_node(raw[l])
            assert integ["member_sha256"][member(l)] == sha(raw[l]) and integ["logical_paths"][member(l)] == l
    before = {l: load(l) for l in lps}
    items = load(ITEM)
    # --- 商品行
    new = set(parsed[SHOP]) - set(before[SHOP])
    assert new == set(PRODUCTS) and len(parsed[SHOP]) == len(before[SHOP]) + 54
    assert {p for p, t in parsed[SHOP].items() if row(t)[0] == "98"} == set(PRODUCTS)
    shop = strict_json((SRV / "boss_coin_shop.json").read_bytes(), "srv shop")
    cmap = strict_json((SRV / "boss_coin_shop_item_category_map.json").read_bytes(), "srv map")
    assert list(shop["98"]) == list(PRODUCTS)
    assert {p for p, c in cmap.items() if c == 98} == new
    for i, (pid, w) in enumerate(zip(PRODUCTS, WEAPONS)):
        t = parsed[SHOP][pid]; r = row(t); it = row(items[str(w)])
        assert len(r) == 50 and join(r) == t and not t.endswith("\n")
        assert it[1] == str(w) and it[6] == "11" and it[2].endswith("魂珠")
        assert r[0] == "98" and r[1:6] == ["(None)", "true", "(None)", "", "(None)"]
        assert r[6] == it[2] and r[7:9] == ["1", "1"] and r[9] == str(54 - i) and r[11] == "(None)"
        assert r[12:14] == [it[3], "5"] and r[14:17] == ["(None)", "", "(None)"]
        assert r[17:25] == [str(CURRENCY), str(PRICE), "(None)", "", "(None)", "", "(None)", ""]
        assert r[25:32] == [START, END, "1", str(STOCK), str(STOCK), "(None)", "(None)"]
        assert r[32:35] == ["0", str(w), "1"] and r[35:] == ["(None)", "", ""] * 5
        assert shop["98"][pid] == {"costs": [{"id": int(r[17]), "amount": int(r[18])}],
                                   "rewards": [{"type": int(r[32]), "id": int(r[33]), "count": int(r[34])}],
                                   "availableFrom": r[25], "availableUntil": r[26], "stock": int(r[29])}, pid
        assert cmap[pid] == int(r[0])
    # --- 分类 / 节点 / 锚点
    cat = row(parsed[CATEGORY]["98"]); c99 = row(before[CATEGORY]["99"])
    assert len(cat) == 13 and cat[:2] == ["mod_soul_exchange", "2998"] and cat[2:9] == ["(None)"] * 7
    assert cat[9:] == c99[9:] and cat[11:] == ["", "false"]
    st = row(parsed[STAGE]["1"]["98"])
    assert len(st) == 14 and st[:2] == ["魂珠兑换", "魂珠兑换"] and st[6:11] == ["98", str(CURRENCY), "(None)", "(None)", "(None)"]
    assert st[2] in load("master/quest/boss_battle_stage_node_group.orderedmap")
    assert [(c, k) for c, ss in parsed[STAGE].items() for k, t in ss.items() if row(t)[6] == "98"] == [("1", "98")]
    anchor = parsed[QUEST]["1"]["98"]; assert list(anchor) == ["1"]
    qu = row(anchor["1"])
    assert len(qu) == 124 and qu[:3] == [ANCHOR, "1", "魂珠兑换（商店锚点）"]
    assert qu[5:7] == [START, "2000-01-02 00:00:00"] and qu[122:124] == ["false", "true"]
    assert sum(row(t)[0] == ANCHOR for ch in parsed[QUEST].values() for s in ch.values() for t in s.values()) == 1
    assert [k for k, t in anchor.items() if row(t)[123] != "true"] == []  # getQuestIds 过滤后为空 → 节点不可见
    # --- 既有原始块逐字节保留 + 解析层面旧键全等
    specs = {SHOP: ((), PRODUCTS), CATEGORY: ((), ["98"]), STAGE: (("1",), ["98"]), QUEST: (("1",), ["98"])}
    kept = {l: preserved(read_raw(l)[0], raw[l], *specs[l]) for l in lps}
    assert all(parsed[SHOP][k] == v for k, v in before[SHOP].items())
    assert all(parsed[CATEGORY][k] == v for k, v in before[CATEGORY].items())
    assert list(parsed[STAGE]) == list(before[STAGE]) and all(parsed[STAGE]["1"][k] == v for k, v in before[STAGE]["1"].items())
    assert list(parsed[QUEST]) == list(before[QUEST]) and all(parsed[QUEST]["1"][k] == v for k, v in before[QUEST]["1"].items())
    # --- 服务端: kulo 现文件未动 (仍是 batch3 前像); server27 = 前像 + 末尾追加, 删除新增后逐字节还原
    for n in ("boss_coin_shop.json", "boss_coin_shop_item_category_map.json", "mana_board.json"):
        old = (KULO / "assets" / n).read_bytes(); newb = (SRV / n).read_bytes()
        assert blob(old).startswith(BLOBS[n][0]) and blob(newb).startswith(BLOBS[n][1]), n
        assert integ["server_files"][f"assets/{n}"]["sha256"] == sha(newb)
        assert newb.startswith(old.rsplit(b"\n}", 1)[0] + b",\n") and b"\r\n" not in newb and newb.endswith(b"}\n"), n
    del shop["98"]
    for p in PRODUCTS: del cmap[p]
    assert json_bytes(shop) == (KULO / "assets/boss_coin_shop.json").read_bytes()
    assert json_bytes(cmap) == (KULO / "assets/boss_coin_shop_item_category_map.json").read_bytes()
    mo = strict_json((KULO / "assets/mana_board.json").read_bytes(), "mana old")
    mn = strict_json((SRV / "mana_board.json").read_bytes(), "mana new")
    added = [k for k in mn if k not in mo]
    for k in added: del mn[k]
    assert json_bytes(mn) == (KULO / "assets/mana_board.json").read_bytes()
    chars = load("master/character/character.orderedmap")
    assert all(k in chars for k in added), [k for k in added if k not in chars]
    dis = json.loads((KULO / "assets/equipment_dissolve.json").read_text("utf-8"))
    assert not set(map(str, WEAPONS)) & set(dis)
    # --- 与 bughunt candidate 对照 (仅信息)
    same = {}
    if CANDIDATE.exists():
        with zipfile.ZipFile(CANDIDATE) as zc:
            same = {l: (member(l) in zc.namelist() and zc.read(member(l)) == raw[l]) for l in lps}
    res = {"result": "VERIFY PASS", "zip": NAME, "size": len(blob_), "sha256": sha(blob_),
           "products": 54, "existing_raw_chunks_preserved": kept, "mana_added": added,
           "dissolve_has_no_target_weapons": True, "candidate_member_identical": same}
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
