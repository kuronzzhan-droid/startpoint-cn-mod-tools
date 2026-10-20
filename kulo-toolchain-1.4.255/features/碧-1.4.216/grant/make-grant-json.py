# -*- coding: utf-8 -*-
"""生成碧 169978 的补发行(与 1009 凉月 grant-chars.json 同格式:满级 379988、突破 4、evolution 1、两盘 41 节点全开、两块羁绊盘 status 2)。
节点 id 取灰 mana_node_cnmod.json 的 169978(已核对与客户端 mana_node 表一致)。"""
import json, subprocess
from pathlib import Path
mn = json.loads(subprocess.check_output(["git", "-C", r"D:/WF/startpoint-cn-kulo", "show", "origin/main:assets/mana_node_cnmod.json"]).decode("utf-8"))["169978"]
vals = sorted(int(k) for b in mn.values() for k in b)
T = "2026-10-16T00:00:00.000Z"
g = {"characters": [{"id": 169978, "entry_count": 1, "evolution_level": 1, "over_limit_step": 4, "protection": 0, "join_time": T, "update_time": T,
                     "exp": 379988, "stack": 0, "mana_board_index": 2, "player_id": 1, "ex_boost_status_id": None, "ex_boost_ability_id_list": None,
                     "illustration_settings": None}],
     "mana_nodes": [{"value": v, "awake_level": 0, "character_id": 169978, "player_id": 1} for v in vals],
     "bond_tokens": [{"mana_board_index": i, "status": 2, "player_id": 1, "character_id": 169978} for i in (1, 2)]}
Path(__file__).with_name("grant-vyrn.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), "utf-8")
print("nodes", len(vals))
