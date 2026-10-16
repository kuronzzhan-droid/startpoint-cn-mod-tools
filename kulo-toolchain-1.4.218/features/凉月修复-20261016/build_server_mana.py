# -*- coding: utf-8 -*-
"""凉月 159992 服务端玛纳盘修复:mana_node 按客户端表原样重建(风材料 13),mana_board 补客户端 generated 行原样。
输入 = 测试服 assets 副本(D:/WF/bughunt-20261015/server/box-assets),输出 = server/assets/ 下两个文件。
行尾跟盒子原文件一致(mana_node.json 是 CRLF,mana_board.json 是 LF),其余键逐字节不变。
用法:python build_server_mana.py"""
import csv, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BOX = Path(r"D:/WF/bughunt-20261015/server/box-assets")
OUT = HERE / "server" / "assets"
os.environ["WF_TIP"] = "210"
os.environ["WF_EXTRA_ZIPS"] = ""
sys.path.insert(0, r"D:/WF/bughunt-20261015/builder")
os.chdir(r"D:/WF/bughunt-20261015/builder")
from live149 import load  # noqa: E402

CID = "159992"
REF = "149986"  # 同批同格式的自制角色,用来校验转换规则
CRLF, LF = chr(13) + chr(10), chr(10)


def csvrow(s):
    return next(csv.reader([s]))


def conv_board(node):
    return {b: {slot: [csvrow(t)] for slot, t in slots.items()} for b, slots in node.items()}


def conv_node(node):
    out = {}
    for b, slots in node.items():
        ob = {}
        for _, t in slots.items():
            r = csvrow(t)
            ids, cnts = r[2].split(","), r[3].split(",")
            ob[r[0]] = {"items": {i: int(c) for i, c in zip(ids, cnts)}, "manaCost": int(r[4]),
                        "field1": r[1], "field5": r[5], "field6": r[6]}
        out[b] = ob
    return out


def dump(d):
    return json.dumps(d, ensure_ascii=False, indent=2) + LF


cb = load("master/generated/mana_board.orderedmap")
cn = load("master/mana_board/mana_node.orderedmap")
OUT.mkdir(parents=True, exist_ok=True)
for name, conv, ctab in (("mana_board.json", conv_board, cb), ("mana_node.json", conv_node, cn)):
    rawb = (BOX / name).read_bytes()
    nl = CRLF if CRLF.encode() in rawb[:4096] else LF
    raw = rawb.decode("utf-8").replace(CRLF, LF)
    data = json.loads(raw)
    assert dump(data) == raw, f"{name}: 重新序列化与原文件不一致,不能整文件写回"
    assert conv(ctab[REF]) == data[REF], f"{name}: 转换规则在 {REF} 上不成立"
    before = data.get(CID)
    data[CID] = conv(ctab[CID])
    outb = dump(data).replace(LF, nl).encode("utf-8")
    (OUT / name).write_bytes(outb)
    n = sum(len(v) for v in data[CID].values())
    print(f"{name}: 行尾 {'CRLF' if nl == CRLF else 'LF'};{CID} {'新增' if before is None else '替换'} {n} 条;"
          f"其余键未动 = {all(k == CID or data[k] == json.loads(raw)[k] for k in data)}")
    if before is not None:
        diff = [k for b in before for k in before[b] if before[b][k] != data[CID][b].get(k)]
        print(f"  改动节点 {len(diff)} 个,例:{diff[0]} {before['1'][diff[0]]} -> {data[CID]['1'][diff[0]]}")
        assert all(set(before[b][k]) == set(data[CID][b][k]) and before[b][k]["manaCost"] == data[CID][b][k]["manaCost"]
                   for b in before for k in before[b]), "只应改材料 id"
