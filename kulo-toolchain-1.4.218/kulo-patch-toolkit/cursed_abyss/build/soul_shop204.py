# -*- coding: utf-8 -*-
"""1.4.203 -> 1.4.204: 领主币商店新增「魂珠兑换」分类 98(54 件自制武器魂珠, 5 禁忌星铁 10000311 换 1, 限购 999)。

移植自 D:/WF/bughunt-20261014/out/soul_shop_{common,build}.py(candidate 1.4.202->203), 改为我方 live 视图
WF_TIP=203 (末层 balance-1015)。只读 kulo active; 不写 kulo assets/manifest。

客户端 4 表, 全部行级追加, 既有键原始压缩块逐字节不动:
  boss_coin_shop          + 990098001..054 (50 列, 模板 990099002)
  boss_coin_shop_category + 98 (复制 99 横幅/背景, 无可见性前置)
  boss_battle_stage_node  ['1'] + '98' (c6=98 → BossCoinExchangeShopScene 找节点, 否则 ClientError 3431)
  boss_battle_quest       ['1'] + '98': {'1': 1098001 隐藏+过期锚点} (节点构造需分支, 否则 2010; c123=true 不可见)
服务端 3 文件 (server27/, 全量副本, 末尾追加): boss_coin_shop.json["98"], boss_coin_shop_item_category_map.json,
mana_board.json(12 自制角色玛纳板); 与 bughunt handoff/batch3 0001-0002 补丁结果逐字节核对 (git blob id)。"""
import os, sys, json, hashlib, zipfile, struct, zlib, subprocess, tempfile, shutil
os.environ["WF_TIP"] = "203"
os.environ.pop("WF_EXTRA_ZIPS", None)
from live149 import *
import base149
assert base149._ZIPS[-1].name == "pinball-1.4.202-1.4.203-1-balance-1015-local.zip", base149._ZIPS[-1]
assert all(z.parent == ACTIVE for z in base149._ZIPS)

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "patch"
SRV = HERE.parent / "server27"
BATCH3 = Path(r"D:/WF/bughunt-20261014/handoff/batch3")
PATCHES = (BATCH3 / "0001-feat-assets-restore-mana-boards-for-twelve-custom-ch.patch",
           BATCH3 / "0002-feat-assets-add-forbidden-steel-ability-soul-exchang.patch")
NAME = "pinball-1.4.203-1.4.204-1-soul-exchange-shop-local.zip"

SHOP = "master/shop/boss_coin_shop.orderedmap"
CATEGORY = "master/shop/boss_coin_shop_category.orderedmap"
ITEM = "master/item/item.orderedmap"
STAGE = "master/quest/boss_battle_stage_node.orderedmap"
QUEST = "master/quest/boss_battle_quest.orderedmap"
WEAPONS = tuple(range(8000101, 8000125)) + tuple(range(5910101, 5910130)) + (5920001,)
PRODUCTS = tuple(str(990098000 + i) for i in range(1, 55))
START, END = "2000-01-01 00:00:00", "2099-12-31 23:59:59"
CURRENCY, PRICE, STOCK = 10000311, 5, 999
ANCHOR = "1098001"
SERVER_FILES = ("boss_coin_shop.json", "boss_coin_shop_item_category_map.json", "mana_board.json")
# batch3 补丁 index 行: 前像 blob -> 后像 blob (kulo 现文件前像已核对一致)
BLOBS = {"mana_board.json": ("f27d7da", "b08b51d"), "boss_coin_shop.json": ("68fc70e", "5965555"),
         "boss_coin_shop_item_category_map.json": ("5c322a3", "f4bf4c7")}


def sha(b): return hashlib.sha256(b).hexdigest()
def blob(b): return hashlib.sha1(b"blob %d\0" % len(b) + b).hexdigest()


def split_map(raw):
    ilen = struct.unpack_from("<I", raw)[0]
    index = zlib.decompress(raw[4:4 + ilen]); n = struct.unpack_from("<I", index)[0]
    kb, data = index[4 + 8 * n:], raw[4 + ilen:]
    keys, chunks, pk, pr = [], [], 0, 0
    for i in range(n):
        ke, re_ = struct.unpack_from("<II", index, 4 + 8 * i)
        assert pk <= ke <= len(kb) and pr <= re_ <= len(data)
        keys.append(kb[pk:ke].decode("utf-8")); chunks.append(data[pr:re_]); pk, pr = ke, re_
    assert pk == len(kb) and pr == len(data) and len(set(keys)) == n
    return keys, chunks


def join_map(keys, chunks):
    kb = rb = b""; pairs = []
    for k, c in zip(keys, chunks):
        kb += k.encode("utf-8"); rb += c; pairs.append((len(kb), len(rb)))
    idx = struct.pack("<I", len(keys)) + b"".join(struct.pack("<II", *p) for p in pairs) + kb
    packed = zlib.compress(idx)
    return struct.pack("<I", len(packed)) + packed + rb


def append_at(raw, path, added):
    """沿 path 下钻, 在末端 map 追加 added; 路径外所有 chunk 原样复制。"""
    keys, chunks = split_map(raw)
    if path:
        i = keys.index(path[0])
        chunks[i] = append_at(chunks[i], path[1:], added)
    else:
        assert not set(added) & set(keys), set(added) & set(keys)
        keys = keys + list(added); chunks = chunks + [q.build_node(v) for v in added.values()]
    return join_map(keys, chunks)


def json_bytes(v): return (json.dumps(v, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def strict_json(raw, label):
    v = json.loads(raw); assert json_bytes(v) == raw, f"JSON 字节往返失败: {label}"; return v


def server_product(weapon):
    return {"costs": [{"id": CURRENCY, "amount": PRICE}], "rewards": [{"type": 0, "id": weapon, "count": 1}],
            "availableFrom": START, "availableUntil": END, "stock": STOCK}


def product_rows():
    items = flat(ITEM)
    template = row(load(SHOP)["990099002"])
    assert len(template) == 50
    assert template[1:6] == ["(None)", "true", "(None)", "", "(None)"]
    assert template[14:17] == ["(None)", "", "(None)"] and template[30:32] == ["(None)", "(None)"]
    assert template[35:] == ["(None)", "", ""] * 5
    out = {}
    for order, (pid, weapon) in enumerate(zip(PRODUCTS, WEAPONS), 1):
        ir = items[str(weapon)]; assert len(ir) == 1, (weapon, ir); it = ir[0]
        assert it[1] == str(weapon) and it[6] == "11", (weapon, it)
        assert it[2].endswith("魂珠") and it[3], it
        r = template.copy()
        r[0] = "98"; r[6] = it[2]
        r[9] = str(len(WEAPONS) + 1 - order)  # 客户端 c9 倒序显示
        r[10] = "消耗5个禁忌星铁兑换1个能力魂珠。"
        r[12], r[13] = it[3], "5"
        r[17], r[18] = str(CURRENCY), str(PRICE)
        for o in (19, 21, 23): r[o:o + 2] = ["(None)", ""]
        r[25], r[26] = START, END
        r[28], r[29] = str(STOCK), str(STOCK)
        r[32:35] = ["0", str(weapon), "1"]
        out[pid] = r
    assert len(out) == 54
    return out


def client_additions():
    cats, stages, quests = load(CATEGORY), load(STAGE), load(QUEST)
    shop = load(SHOP)
    assert not set(PRODUCTS) & set(shop) and not any(row(t)[0] == "98" for t in shop.values())
    assert "98" not in cats and "98" not in stages["1"] and "98" not in quests["1"]
    assert not any(row(t)[6] == "98" for ch in stages.values() for t in ch.values())
    assert not any(row(t)[0] == ANCHOR for ch in quests.values() for st in ch.values() for t in st.values())
    cat = row(cats["99"]); assert len(cat) == 13
    cat[0:2] = ["mod_soul_exchange", "2998"]; cat[3:8] = ["(None)"] * 5  # 无可见性前置
    st = row(stages["1"]["99"]); assert len(st) == 14
    st[0:2] = ["魂珠兑换", "魂珠兑换"]; st[6:11] = ["98", str(CURRENCY), "(None)", "(None)", "(None)"]
    qu = row(quests["1"]["99"]["2"]); assert len(qu) == 124 and qu[123] == "true"
    qu[0:3] = [ANCHOR, "1", "魂珠兑换（商店锚点）"]; qu[5:7] = [START, "2000-01-02 00:00:00"]
    qu[122:124] = ["false", "true"]
    return {SHOP: ((), {p: join(r) for p, r in product_rows().items()}),
            CATEGORY: ((), {"98": join(cat)}),
            STAGE: (("1",), {"98": join(st)}),
            QUEST: (("1",), {"98": {"1": join(qu)}})}


def server_outputs():
    cur = {n: (KULO / "assets" / n).read_bytes() for n in SERVER_FILES}
    for n, b in cur.items():
        assert blob(b).startswith(BLOBS[n][0]), (n, blob(b))  # kulo 现文件 == batch3 前像
    shop = strict_json(cur["boss_coin_shop.json"], "shop")
    cmap = strict_json(cur["boss_coin_shop_item_category_map.json"], "map")
    assert "98" not in shop and 98 not in cmap.values() and not set(PRODUCTS) & set(cmap)
    shop["98"] = {p: server_product(w) for p, w in zip(PRODUCTS, WEAPONS)}
    cmap.update({p: 98 for p in PRODUCTS})
    gen = {"boss_coin_shop.json": json_bytes(shop), "boss_coin_shop_item_category_map.json": json_bytes(cmap)}
    # batch3 补丁在临时目录应用 (git apply, 非仓库模式), 作为参考
    tmp = Path(tempfile.mkdtemp(prefix="soul204_"))
    try:
        (tmp / "assets").mkdir()
        for n, b in cur.items(): (tmp / "assets" / n).write_bytes(b)
        for p in PATCHES:
            subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", "apply", "--whitespace=nowarn", str(p)], cwd=tmp, check=True)
        ref = {n: (tmp / "assets" / n).read_bytes() for n in SERVER_FILES}
    finally:
        shutil.rmtree(tmp)
    for n in SERVER_FILES:
        assert blob(ref[n]).startswith(BLOBS[n][1]), (n, blob(ref[n]))
    for n, b in gen.items():
        assert b == ref[n], f"独立生成与 batch3 不一致: {n}"
    mana_old = strict_json(cur["mana_board.json"], "mana"); mana_new = strict_json(ref["mana_board.json"], "mana new")
    added = [k for k in mana_new if k not in mana_old]
    assert list(mana_new)[:len(mana_old)] == list(mana_old) and all(mana_new[k] == mana_old[k] for k in mana_old)
    # 物理前缀: 旧文件去掉末尾 "\n}\n" 后原样是新文件前缀 (只追加)
    for n in SERVER_FILES:
        pre = cur[n].rsplit(b"\n}", 1)[0]
        assert ref[n].startswith(pre + b",\n"), n
    return cur, ref, {"mana_board.json": added, "boss_coin_shop.json": ["98"],
                      "boss_coin_shop_item_category_map.json": list(PRODUCTS)}


def main():
    members, logical_paths, log = {}, {}, []
    for lp, (path, added) in client_additions().items():
        raw, src = read_raw(lp)
        before = q.parse_node(raw)
        data = append_at(raw, path, added)
        exp = before
        for k in path: exp = exp[k]
        exp.update(added)
        assert q.parse_node(data) == before, lp  # before 已原地加入 added
        members[member(lp)] = data; logical_paths[member(lp)] = lp
        log.append(f"{lp}: base {src} {len(raw)} B sha256 {sha(raw)} -> {len(data)} B; 追加 {'/'.join(path) or '<root>'} +{len(added)} 键")
    path = OUT / NAME
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for m in sorted(members):
            info = zipfile.ZipInfo(m, date_time=(2026, 10, 15, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.create_system = 0; info.external_attr = 0o600 << 16
            zf.writestr(info, members[m])
    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None and sorted(zf.namelist()) == sorted(members)
        assert all(zf.read(m) == members[m] for m in members)

    cur, ref, srv_added = server_outputs()
    SRV.mkdir(exist_ok=True)
    server_files = {}
    for n in SERVER_FILES:
        (SRV / n).write_bytes(ref[n]); assert (SRV / n).read_bytes() == ref[n]
        server_files[f"assets/{n}"] = {"copy": f"server27/{n}", "sha256": sha(ref[n]), "size": len(ref[n]),
                                       "base_sha256": sha(cur[n]), "git_blob": blob(ref[n]),
                                       "added_top_level_keys": srv_added[n] if n != "boss_coin_shop_item_category_map.json" else f"{len(PRODUCTS)} 键 990098001..990098054 -> 98"}
    blob_ = path.read_bytes()
    integ = {"name": NAME, "size": len(blob_), "sha256": sha(blob_), "members": len(members), "files": sorted(members),
             "member_sha256": {m: sha(b) for m, b in members.items()}, "logical_paths": logical_paths,
             "new_files": [], "server_files": server_files, "server_reference": [p.name for p in PATCHES],
             "applies_on": "1.4.203", "version": "1.4.204", "requires_client": "纯数据",
             "products": {p: w for p, w in zip(PRODUCTS, WEAPONS)}, "anchor_quest": ANCHOR, "log": log,
             "ported_from": "D:/WF/bughunt-20261014/out/soul_shop_build.py (candidate 1.4.202->1.4.203)"}
    path.with_name(path.stem + ".integrity.json").write_text(json.dumps(integ, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print("\n".join(log)); print(NAME, len(blob_), integ["sha256"])
    for m, b in sorted(members.items()): print(" ", m, logical_paths[m], len(b), sha(b))
    for k, v in server_files.items(): print(" ", k, v["copy"], v["size"], v["sha256"], v["git_blob"][:7])
    print("mana added:", srv_added["mana_board.json"])


if __name__ == "__main__":
    main()
