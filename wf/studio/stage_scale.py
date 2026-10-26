"""场地比例预览：按真实关卡边界比角色像素和特效的大小。

关卡 → ``field_data``（与领主战同一列位 c109；主线/EX 表的列位相同）→ 地形
``battle/terrain/...`` → 第一个波次层的 ``BOUNDS``。客户端把 BOUNDS 画成
1080×1920 的战场，地形像素 ×6 = 运行时像素（``terrain_objects.point``）；
像素小人按 ``frame.scale``（官方恒为 6）放大，所以同一张图上可以直接比大小。

只读：不写草稿。默认关卡是主线 1-2-1（``1002001``）。
"""
from __future__ import annotations

from wf.boss import schema as s
from wf.boss.reader import BossReader
from wf.boss.terrain import read_terrain

from .drafts import DraftError

DEFAULT_QUEST = "1002001"
RUNTIME_SCALE = 6
FIELD_DATA_COLUMN = 109
# Tables whose rows point at field_data (same long-row layout as boss_battle_quest).
QUEST_TABLES = (
    ("main", "主线", "master/quest/main_quest.orderedmap"),
    ("ex", "高难EX", "master/quest/ex_quest.orderedmap"),
    ("boss_battle", "领主战", "master/quest/boss_battle_quest.orderedmap"),
    ("character", "角色剧情", "master/quest/character_quest.orderedmap"),
    ("hard_multi", "高难多人", "master/quest/event/hard_multi_event_quest.orderedmap"),
    ("advent", "降临战", "master/quest/event/advent_event_quest.orderedmap"),
    ("raid", "Raid", "master/quest/event/raid_event_quest.orderedmap"),
    ("story_event", "剧情活动", "master/quest/event/story_event_single_quest.orderedmap"),
)


def find_quest(tables, quest: str) -> dict:
    """Quest id (c0) or ordered-map key → row, its table and the field_data id."""
    quest = str(quest).strip()
    fd_table = tables.table(s.FIELD_DATA)
    hits = []
    for kind, label, logical in QUEST_TABLES:
        for path, text in s.iter_leaves(tables.table(logical)):
            if path[-1] != quest and not text.startswith(quest + ","):
                continue
            rows = s.parse_rows(text)
            if not rows or (s.cell(rows[0], 0) != quest and path[-1] != quest):
                continue
            row = rows[0]
            fd = s.cell(row, FIELD_DATA_COLUMN)
            if not s.present(fd) or s.get_leaf(fd_table, [fd]) is None:
                # Shorter event rows: the one cell that names a field_data key.
                fd = next((c for c in row[1:] if s.present(c) and s.get_leaf(fd_table, [c]) is not None), None)
            hits.append({"kind": kind, "category": label, "table": logical, "path": list(path),
                         "name": s.cell(row, 2) if kind != "practice" else path[-1], "fieldData": fd})
    if not hits:
        raise DraftError(f"当前视图里找不到关卡 {quest}")
    with_field = [h for h in hits if h["fieldData"]]
    if not with_field:
        raise DraftError(f"关卡 {quest} 的行里没有 field_data")
    return with_field[0] | {"id": quest, "alternatives": len(with_field) - 1}


def stage(source, quest: str | None = None, terrain: str | None = None) -> dict:
    tables = BossReader(source)
    found = None
    if terrain:
        logical = terrain.strip().removesuffix(".amf3.deflate")
        if not logical.startswith("battle/terrain/") or ".." in logical.split("/"):
            raise DraftError("地形路径必须是 battle/terrain/ 下的逻辑路径")
    else:
        found = find_quest(tables, quest or DEFAULT_QUEST)
        fd = s.get_leaf(tables.table(s.FIELD_DATA), [found["fieldData"]])
        row = s.parse_rows(fd)[0] if isinstance(fd, str) and fd else []
        logical = s.cell(row, 1)
        if not s.present(logical):
            raise DraftError(f"field_data {found['fieldData']} 没有地形")
    data = read_terrain(tables, logical)
    if data["missing"]:
        raise DraftError(f"当前视图里没有地形 {logical}")
    waves = data["waves"]
    wave = next((w for w in waves if w["bounds"]), None)
    if wave is None:
        raise DraftError(f"地形 {logical} 没有 BOUNDS")
    b = wave["bounds"][0]
    bounds = {k: b[k] * RUNTIME_SCALE for k in ("x", "y", "width", "height")}
    others = []
    for obj in wave["objects"]:
        kind = obj.get("type") or ""
        if kind in ("BOUNDS",) or not isinstance(obj.get("x"), (int, float)):
            continue
        box = {k: float(obj.get(k, 0)) * RUNTIME_SCALE for k in ("x", "y", "width", "height")}
        others.append({"type": kind, "name": obj.get("name", ""), **box,
                       "polygon": [[(obj["x"] + p["x"]) * RUNTIME_SCALE, (obj["y"] + p["y"]) * RUNTIME_SCALE]
                                   for p in obj.get("polygon") or obj.get("polyline") or []
                                   if isinstance(p, dict)]})
    return {
        "quest": None if found is None else {k: found[k] for k in ("id", "kind", "category", "name", "fieldData",
                                                                     "alternatives")},
        "terrain": data["logical"].removesuffix(".amf3.deflate"), "wave": wave["name"], "waves": len(waves),
        "bounds": bounds, "runtimeScale": RUNTIME_SCALE,
        "coffins": [{"party": c["party"], "member": c["member"], **c["runtime_point"]} for c in wave["coffins"]],
        "positions": [{"name": p["name"], "type": p["type"], **p["runtime_point"]} for p in wave["named_positions"]],
        "objects": others,
        "note": "运行时像素：地形 ×6，BOUNDS 即客户端的战场框；像素小人按 frame.scale 放大后同比例显示",
    }
