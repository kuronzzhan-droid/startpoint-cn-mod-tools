# -*- coding: utf-8 -*-
"""四角色服务端条目（碧 169978 同口径：按键追加，保留换行风格，其余键逐一核对未动）。
    python hw_server.py <in_assets> <out_assets>      # 生成并写出改动后的文件
    python hw_server.py --entries <json>              # 只导出键级条目
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import hw_env
import hw_specs as HS

TARGETS = {  # 盒子文件 -> 包内 server 文件
    "cdndata/character_rank_p5b.json": "cdndata/character.json",
    "cdndata/character_text_rank_p5b.json": "cdndata/character_text.json",
    "character_rank_p5b.json": "character.json",
    "mana_node_cnmod.json": "mana_node.json",
    "mana_board.json": "mana_board.json",
}


def entries():
    out = {k: {} for k in TARGETS}
    for key in HS.all_keys():
        spec = HS.get_spec(key)
        sroot = hw_env.ROOT / "work" / "character_packs" / f"hw-{key}" / "package" / "roots" / "server"
        for box, pkg in TARGETS.items():
            d = json.loads((sroot / pkg).read_text("utf-8"))
            out[box][spec.cid_s] = d[spec.cid_s]
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
            # 原文件不是 indent=2 风格：退回紧凑写法核对
            raise SystemExit(f"{rel}: 重新序列化与原文不一致，停止")
        before = json.loads(raw)
        clash = [k for k in adds if k in d]
        assert not clash, f"{rel} 已有 {clash}"
        d.update(adds)
        assert all(d[k] == before[k] for k in before), rel
        p = out_assets / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(dump(d, crlf).encode("utf-8"))
        print(f"{rel}: +{len(adds)} 键 CRLF={crlf}")


if __name__ == "__main__":
    if sys.argv[1] == "--entries":
        Path(sys.argv[2]).write_text(json.dumps(entries(), ensure_ascii=False, indent=1), "utf-8")
        print("written", sys.argv[2])
    else:
        apply(Path(sys.argv[1]), Path(sys.argv[2]))
