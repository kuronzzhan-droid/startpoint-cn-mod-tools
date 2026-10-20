# -*- coding: utf-8 -*-
"""水杰拉德服务端条目（照万圣四角色 1.4.221 / 碧 169978 口径：按键追加，保留换行风格，其余键逐一核对未动）。
    python wg_server.py --entries <out.json>          # 只导出键级条目（交协调按条目合并）
    python wg_server.py <in_assets> <out_assets>      # 对一份 assets 副本生成改动后的文件
另：assets/character_overlimit.json 的 characters 追加 129989（超限 Lv120，无觉醒，不加 level_missions）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import wg_env
import wg_specs as HS

TARGETS = {  # 盒子文件 -> 包内 server 文件
    "cdndata/character_rank_p5b.json": "cdndata/character.json",
    "cdndata/character_text_rank_p5b.json": "cdndata/character_text.json",
    "character_rank_p5b.json": "character.json",
    "mana_node_cnmod.json": "mana_node.json",
    "mana_board.json": "mana_board.json",
}
OVERLIMIT = "character_overlimit.json"


def entries():
    out = {k: {} for k in TARGETS}
    for key in HS.all_keys():
        spec = HS.get_spec(key)
        sroot = wg_env.ROOT / "work" / "character_packs" / f"wg-{key}" / "package" / "roots" / "server"
        for box, pkg in TARGETS.items():
            d = json.loads((sroot / pkg).read_text("utf-8"))
            out[box][spec.cid_s] = d[spec.cid_s]
    out[OVERLIMIT] = {"characters_append": [int(HS.get_spec(k).cid) for k in HS.all_keys()]}
    return out


def dump(d, crlf):
    s = json.dumps(d, ensure_ascii=False, indent=2) + "\n"
    return s.replace("\n", "\r\n") if crlf else s


def apply(in_assets: Path, out_assets: Path):
    ent = entries()
    for rel, adds in ent.items():
        raw = (in_assets / rel).read_bytes().decode("utf-8")
        crlf = "\r\n" in raw
        d = json.loads(raw)
        if dump(d, crlf) != raw:
            raise SystemExit(f"{rel}: 重新序列化与原文不一致，停止")
        before = json.loads(raw)
        if rel == OVERLIMIT:
            add = [c for c in adds["characters_append"] if c not in d["characters"]]
            d["characters"] = d["characters"] + add
            assert all(d[k] == before[k] for k in before if k != "characters"), rel
        else:
            clash = [k for k in adds if k in d]
            assert not clash, f"{rel} 已有 {clash}"
            d.update(adds)
            assert all(d[k] == before[k] for k in before), rel
        p = out_assets / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(dump(d, crlf).encode("utf-8"))
        print(f"{rel}: CRLF={crlf}")


if __name__ == "__main__":
    if sys.argv[1] == "--entries":
        Path(sys.argv[2]).write_text(json.dumps(entries(), ensure_ascii=False, indent=1), "utf-8")
        print("ok", sys.argv[2])
    else:
        apply(Path(sys.argv[1]), Path(sys.argv[2]))
