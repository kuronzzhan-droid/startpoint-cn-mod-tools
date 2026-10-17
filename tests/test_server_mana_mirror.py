# -*- coding: utf-8 -*-
"""服务端玛纳镜像门禁：assets/mana_board.json 与 assets/mana_node.json 的覆盖面。

背景（事实）：`src/lib/assets.ts` 的 `getManaNodeAwakeCost` 先查
`assets/mana_board.json[characterId]`，查不到就返回 null，`/api/character/mana`
随即 400（玛纳板觉醒直接不可用）。`assets/mana_node.json` 同理被
`learn_mana_node` 的校验/扣费读取。

角色包管线过去只把 `mana_node.json` 列进 `SERVER_LOGICAL_PATHS`，
`mana_board.json` 结构上进不了包，所以每发一个自制角色，服务端镜像就少一行。
本门禁把"两张镜像表必须同时覆盖全部可玩角色"钉成红/绿信号。

`700xxx` 是敌方/boss 侧条目（`assets/character.json` 里存在但没有玛纳板），
按现状排除。
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ASSETS = REPO_ROOT / "assets"
# 敌方/boss 前缀：这些 id 在 character.json 里有行，但官方从不给玛纳板。
ENEMY_ID_PREFIX = "700"


def _load(name: str) -> dict:
    from external_sources import server_source
    return json.loads(server_source("assets/" + name).read_text(encoding="utf-8"))


class ServerManaMirrorCoverageTest(unittest.TestCase):
    """assets/ 三张表的键级一致性（只读仓库，不写盘）。"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.characters = _load("character.json")
        cls.mana_board = _load("mana_board.json")
        cls.mana_node = _load("mana_node.json")

    def _playable_ids(self) -> set[str]:
        return {
            key for key in self.characters
            if not str(key).startswith(ENEMY_ID_PREFIX)
        }

    def test_every_playable_character_has_a_mana_board_entry(self) -> None:
        missing = sorted(self._playable_ids() - set(self.mana_board))
        self.assertEqual(
            missing, [],
            "assets/mana_board.json 缺角色条目 → getManaNodeAwakeCost 返回 null，"
            f"/api/character/mana 400：{missing[:20]}",
        )

    def test_every_playable_character_has_a_mana_node_entry(self) -> None:
        missing = sorted(self._playable_ids() - set(self.mana_node))
        self.assertEqual(
            missing, [],
            "assets/mana_node.json 缺角色条目 → learn_mana_node 校验/扣费失败："
            f"{missing[:20]}",
        )

    def test_mana_board_rows_have_the_six_column_client_shape(self) -> None:
        """服务端行 = 客户端 CSV 行原样 [nodeId,x,y,shape,pedestal,parent]。"""
        bad: list[str] = []
        for character_id, boards in self.mana_board.items():
            if not isinstance(boards, dict):
                bad.append(f"{character_id}: boards is not an object")
                continue
            for board_key, slots in boards.items():
                if not isinstance(slots, dict):
                    bad.append(f"{character_id}/{board_key}: slots is not an object")
                    continue
                for slot_key, rows in slots.items():
                    label = f"{character_id}/{board_key}/{slot_key}"
                    if not isinstance(rows, list) or not rows:
                        bad.append(f"{label}: rows must be a non-empty array")
                        continue
                    for row in rows:
                        if (
                            not isinstance(row, list)
                            or len(row) != 6
                            or any(not isinstance(cell, str) for cell in row)
                        ):
                            bad.append(f"{label}: row is not six CSV strings")
        self.assertEqual(bad[:20], [], "mana_board.json 行形状异常")


if __name__ == "__main__":
    unittest.main()
