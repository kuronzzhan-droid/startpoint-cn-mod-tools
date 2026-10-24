"""Validate the lazy reward snapshot and include only its public JSON script."""
from __future__ import annotations

from pathlib import Path

from wf_wiki_dungeon_rewards_schema import read_payload
from wf_wiki_pixel_output import checked_path, digest

INDEX = "rewards-data.js"


def reward_plan(source_root: Path, data: dict, dungeon_ids: set[str]):
    root = checked_path(source_root)
    path = checked_path(root / INDEX)
    payload = read_payload(path, dungeon_ids=dungeon_ids,
                           equipment_ids={item["id"] for item in data["equipment"]},
                           character_ids={item["id"] for item in data["characters"]})
    raw = path.read_bytes()
    signature = digest(raw)
    shops = payload["shops"]
    quests = [quest for dungeon in payload["dungeons"].values() for quest in dungeon["quests"]]
    audit = {"publicIndex": INDEX, "bytes": len(raw), "source": payload["source"],
             "dungeons": len(payload["dungeons"]), "quests": len(quests), "shops": len(shops),
             "products": sum(len(shop["items"]) for shop in shops),
             "rewardRows": sum(len(quest[field]) for quest in quests for field in ("firstClear", "sPlus", "drops")),
             "linksVerified": True, "privateSourcesExcluded": True}
    return [{"path": INDEX, "bytes": len(raw), "sha256": signature}], {INDEX: signature}, audit
