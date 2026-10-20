# -*- coding: utf-8 -*-
"""碧 169978 服务端条目:在给定 assets 目录(盒子底)上按键追加,保留原文件换行风格;其余键逐一核对未动。
用法: python build_server.py <in_assets> <out_assets>"""
import json, sys, subprocess
from pathlib import Path
IN, OUT = Path(sys.argv[1]), Path(sys.argv[2])
CID = "169978"
def kulo(rel): return json.loads(subprocess.check_output(["git","-C",r"D:/WF/startpoint-cn-kulo","show",f"origin/main:assets/{rel}"]).decode("utf-8"))
def dump(d, crlf):
    s = json.dumps(d, ensure_ascii=False, indent=2) + "\n"
    return s.replace("\n", "\r\n") if crlf else s
board = json.load(open(Path(__file__).with_name("mana_board_169978.json"), encoding="utf-8"))
plan = {
    "cdndata/character_rank_p5b.json": lambda d: d.__setitem__(CID, kulo("cdndata/character_rank_p5b.json")[CID]),
    "cdndata/character_text_rank_p5b.json": lambda d: d.__setitem__(CID, kulo("cdndata/character_text_rank_p5b.json")[CID]),
    "character_rank_p5b.json": lambda d: d.__setitem__(CID, kulo("character_rank_p5b.json")[CID]),
    "mana_node_cnmod.json": lambda d: d.__setitem__(CID, kulo("mana_node_cnmod.json")[CID]),
    "mana_board.json": lambda d: d.__setitem__(CID, board),
    "degree_character_mod.json": lambda d: [d.__setitem__(k, kulo("degree_character_mod.json")[k]) for k in ("9910090", "9910091")],
    "character_degree_rewards.json": lambda d: d["characters"].append({"character_id": 169978, "degree_ids": [9910090, 9910091]}),
}
for rel, fn in plan.items():
    raw = (IN / rel).read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    d = json.loads(raw)
    assert dump(d, crlf) == raw, f"{rel}: 重新序列化与原文不一致"
    before = json.loads(raw)
    if rel == "character_degree_rewards.json":
        assert all(r["character_id"] != 169978 for r in d["characters"]), rel
    elif rel == "degree_character_mod.json":
        assert "9910090" not in d and "9910091" not in d, rel
    else:
        assert CID not in d, f"{rel} 已有 {CID}"
    fn(d)
    if rel == "character_degree_rewards.json":
        same = d["characters"][:-1] == before["characters"] and {k: v for k, v in d.items() if k != "characters"} == {k: v for k, v in before.items() if k != "characters"}
    else:
        same = all(d[k] == before[k] for k in before)
    assert same, rel
    out = OUT / rel; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(dump(d, crlf).encode("utf-8"))
    print(f"{rel}: +{len(d)-len(before) if rel!='character_degree_rewards.json' else 1} 键, CRLF={crlf}, 其余未动")
# 称号 id 不得已被占用
for rel in ("degree.json", "degree_author926.json", "degree_rank_p5b.json", "degree_sponsor.json", "degree_exclusive.json"):
    p = IN / rel
    if p.exists():
        t = p.read_text("utf-8"); assert "9910090" not in t and "9910091" not in t, rel
print("degree ids free")
