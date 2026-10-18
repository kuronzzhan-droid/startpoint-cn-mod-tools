"""Read-only boss workshop model, independent of filesystem configuration."""
from __future__ import annotations

import copy
import re

from . import schema as s
from .enemies import enemies
from .links import entrances, record, rewards, routing, shops
from .provenance import BossTables
from .terrain import read_terrain


class BossReader(BossTables):
    """Accept a ManifestView, StudioSource or in-memory candidate overlay.

    ``list`` exposes individual playable difficulty rows and separate groups.
    Selectors are ``kind:path/to/leaf`` or an unambiguous public quest ID.
    Practice IDs always use the ordered-map key, never its folder-valued c0.
    """

    def __init__(self, source):
        super().__init__(source)
        version = getattr(source, "version", None)
        if version is None:
            version = getattr(self.view, "tip", None)
            if isinstance(version, int):
                version = f"1.4.{version}"
        self.version, self._quests, self._details = version, None, {}

    def _index(self):
        if self._quests is not None:
            return self._quests
        result = []
        for kind, logical in s.QUEST_TABLES.items():
            for path, text in s.iter_leaves(self.table(logical)):
                rows = s.parse_rows(text)
                if not rows:
                    continue
                if len(rows) != 1:
                    raise ValueError(f"quest leaf must have one row: {logical}/{path}")
                row = rows[0]
                identifier = path[-1] if kind == "practice" else s.cell(row, 0)
                fields = {name: s.cell(row, column) for name, column in s.QUEST_COLUMNS[kind].items()}
                fields["need_quest"] = row[7:17]
                group = row[0] if kind == "practice" else "/".join(path[:-1])
                category = {"boss_battle": "领主战", "hard_multi": "共同决战", "practice": "木人"}[kind]
                if kind == "boss_battle" and path[:2] == ("1", "99"):
                    category = "五重决战"
                result.append({"id": identifier, "native_id": s.cell(row, 0),
                               "selector": f"{kind}:{'/'.join(path)}", "kind": kind,
                               "category": category, "name": re.sub(r"::[^:]+::", "", fields["name"]).strip(),
                               "group": group, "table": logical, "path": list(path),
                               "row": row, "fields": fields})
        self._quests = result
        return result

    def list(self):
        items, groups = [], {}
        for quest in self._index():
            item = {key: value for key, value in quest.items() if key not in ("row", "fields")}
            item.update(source=self.citation(quest["table"], quest["path"]),
                        level=quest["fields"]["level"], rank=quest["fields"]["rank"],
                        hidden=quest["fields"].get("hidden") == "true")
            items.append(item)
            key = quest["kind"], quest["group"]
            if key not in groups:
                groups[key] = {"kind": key[0], "group": key[1], "category": item["category"],
                               "name": item["name"], "quests": [], "quest_count": 0}
            groups[key]["quests"].append(item["selector"])
            groups[key]["quest_count"] += 1
        return {"schema": "wf-boss-list/1", "version": self.version,
                "items": items, "groups": list(groups.values()), "quest_count": len(items),
                "note": "只读客户端配置；不证明服务端开放、运行或设备验收"}

    def find(self, selector):
        selector = str(selector)
        matches = [q for q in self._index() if q["selector"] == selector or q["id"] == selector]
        if not matches and ":" in selector:
            kind, identifier = selector.split(":", 1)
            matches = [q for q in self._index() if q["kind"] == kind and q["id"] == identifier]
        if not matches:
            raise ValueError(f"未知副本: {selector}")
        if len(matches) != 1:
            raise ValueError(f"副本 ID 不唯一，请用 kind:path: {', '.join(q['selector'] for q in matches)}")
        return copy.deepcopy(matches[0])

    def show(self, selector):
        quest = self.find(selector)
        key = quest["selector"]
        if key in self._details:
            return copy.deepcopy(self._details[key])
        quest["source"] = self.citation(quest["table"], quest["path"])
        quest["field_sources"] = {name: {"column": column, "source": quest["source"]}
                                  for name, column in s.QUEST_COLUMNS[quest["kind"]].items()}
        quest["field_sources_semantics"] = {
            "granularity": "whole_leaf", "column_origin_verified": False,
            "note": "field_sources 按字段列位展示整叶来源，不是单格首次引入层或单格最后变更层。"}
        fd_id = quest["fields"]["field_data"]
        fd = record(self, s.FIELD_DATA, [fd_id])
        fd_row = fd["row"] if fd else []
        field_id, terrain_id, zone_id = (s.cell(fd_row, i) for i in range(3))
        field = record(self, s.FIELD, [field_id])
        zone_rows = [record(self, s.ZONE, path, row)
                     for path, row in s.rows_at(self.table(s.ZONE), [zone_id])]
        entrance = entrances(self, quest)
        reward = rewards(self, quest)
        result = {"schema": "wf-boss/1", "version": self.version, "quest": quest,
                  "entrance": entrance, "field_data": {"id": fd_id, "missing": fd is None, **(fd or {})},
                  "field": {"id": field_id, "missing": field is None, **(field or {})},
                  "zone": {"id": zone_id, "missing": not zone_rows, "rows": zone_rows},
                  "terrain": read_terrain(self, terrain_id), "enemies": enemies(self, zone_rows, quest),
                  "rewards": reward, "shops": shops(self, entrance, reward, quest), "routing": routing(self, quest),
                  "source_semantics": "leaf 表示该完整 CSV 叶子最后语义变更的层；不声明每格首次引入层。"
                                      "table_layer 是整表载入层，scope=table 时叶子变更层未核验。"}
        if result["routing"]["kind"] == "BothBoss":
            scope = {"kind": "entrance_only", "label": "入口自身，非战斗内容", "combat_content": False}
            result["content_scope"] = scope
            result["terrain"]["content_scope"] = scope
            for enemy in result["enemies"]:
                enemy["content_scope"] = scope
            result["routing"]["hidden_quests"] = self._hidden_quests(result["routing"]["maps"])
        self._details[key] = result
        return copy.deepcopy(result)

    def _hidden_quests(self, maps):
        targets = {}
        quests = {q["id"]: q for q in self._index() if q["kind"] == "boss_battle"}
        for entry in maps:
            for column in range(11, 15):
                identity = s.cell(entry["row"], column)
                if not s.present(identity):
                    continue
                if identity not in targets:
                    quest = quests.get(identity)
                    targets[identity] = {"id": identity, "missing": quest is None, "map_refs": []}
                    if quest:
                        targets[identity].update(selector=quest["selector"], name=quest["name"],
                                                 hidden=quest["fields"].get("hidden") == "true",
                                                 field_data=quest["fields"]["field_data"],
                                                 source=self.citation(quest["table"], quest["path"]))
                targets[identity]["map_refs"].append({"map": entry["path"][-1], "column": column})
        return list(targets.values())
