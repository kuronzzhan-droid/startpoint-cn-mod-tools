"""Read-only helpers behind the BOSS工坊 pages: overview modes, template sources, options.

Nothing here writes. Modes only group the existing ``wf-boss-list/1`` items for
the overview; they never change a selector or the rule results.
"""
from __future__ import annotations

import re

from wf.boss import schema as s
from wf.boss.terrain import read_terrain
from wf.boss.parameters import BGM_GROUP, FIELD

from .drafts import status

DEFAULT_TEMPLATE = "hard_multi:1006/1"

# Overview buckets (data-driven; each carries the rule that put an item there).
MODES = {
    "main_lord": "主线领主战",
    "lord": "官方领主战",
    "shared": "共同决战",
    "five": "五重决战",
    "practice": "练习木人",
    "other": "其他",
}
MODE_RULES = {
    "main_lord": "领主战里场景以 mod_mainboss_ 命名的节点（补讨伐的主线 boss），按命名归类",
    "lord": "其余领主战节点",
    "shared": "共同决战（hard_multi）",
    "five": "领主战节点 99：五重决战入口及其隐藏关",
    "practice": "练习木人（practice）",
    "other": "隐藏的领主战锚点（不是可进入的战斗），例如魂珠兑换商店锚点",
}


def _row(reader, item):
    text = s.get_leaf(reader.table(item["table"]), item["path"])
    rows = s.parse_rows(text) if isinstance(text, str) else []
    return rows[0] if rows else []


def _mode(item, fields):
    if item["kind"] == "practice":
        return "practice"
    if item["kind"] == "hard_multi":
        return "shared"
    if item["category"] == "五重决战":
        return "five"
    if fields["field_data"].startswith("mod_mainboss_"):
        return "main_lord"
    return "lord"


def enrich_listing(reader, listing):
    """Add element / mode / BothBoss flags to each list item (same selectors)."""
    by_selector = {}
    for item in listing["items"]:
        row = _row(reader, item)
        columns = s.QUEST_COLUMNS[item["kind"]]
        fields = {name: s.cell(row, column) for name, column in columns.items()}
        item.update(recommendedElement=fields["recommended_element"],
                    restrictedElement=fields["restriction"],
                    fieldData=fields["field_data"],
                    bothBoss=fields.get("both_boss", "").lower() == "true",
                    mode=_mode(item, fields))
        by_selector[item["selector"]] = item
    for group in listing["groups"]:
        members = [by_selector[q] for q in group["quests"] if q in by_selector]
        # Hidden phase quests belong to their lord group (e.g. 维·索拉斯); a group made only
        # of hidden lord quests is an anchor, not an enterable battle.
        visible = [m for m in members if not m["hidden"]] or members
        modes = {m["mode"] for m in visible}
        mode = modes.pop() if len(modes) == 1 else "other"
        if mode in ("lord", "main_lord") and all(m["hidden"] for m in members):
            mode = "other"
        group["mode"] = mode
        for member in members:
            member["mode"] = mode
    listing["modes"] = [{"id": key, "label": label, "rule": MODE_RULES[key]} for key, label in MODES.items()]
    return listing


def template_sources(reader):
    """Whitelist of sourceQuest values for 新建共同决战 (create_shared).

    Only real, visible encounters are offered: 领主战 and 共同决战 quests.
    BothBoss entrances, 五重决战 (routing entrance and heavy hidden stages),
    hidden quests and anchors and 练习木人 are excluded with a stated reason.
    """
    listing = enrich_listing(reader, reader.list())
    allowed, excluded = [], {}
    reasons = {
        "five": "五重决战：入口只是路由，隐藏关由五重构建器生成且图集偏重，不作模板",
        "other": "隐藏锚点不是可进入的战斗",
        "practice": "练习木人是假人关，不作共同决战模板",
        "both": "BothBoss 路由入口自身不是战斗内容",
        "hidden": "隐藏关（阶段链的后续阶段等）不单独作模板",
    }
    for item in listing["items"]:
        reason = ("both" if item["bothBoss"] else item["mode"] if item["mode"] in reasons
                  else "hidden" if item["hidden"] else None)
        if reason:
            excluded[reason] = excluded.get(reason, 0) + 1
            continue
        allowed.append({key: item[key] for key in (
            "selector", "id", "kind", "name", "group", "level", "rank", "mode",
            "recommendedElement", "restrictedElement", "source")}
            | {"default": item["selector"] == DEFAULT_TEMPLATE})
    return {"default": DEFAULT_TEMPLATE, "sources": allowed,
            "excluded": [{"reason": reasons[key], "count": count} for key, count in excluded.items()],
            "note": "模板只复制所选遭遇的场景、zone、名称和 BGM 组；事件美术沿用官方暗凛模板，不生成新 AI/美术/武器/商店"}


def options(reader):
    """Valid BGM groups and scenes (field keys) of the current view."""
    bgm = []
    for key, text in reader.table(BGM_GROUP).items():
        row = s.parse_rows(text)[0] if isinstance(text, str) and text else []
        bgm.append({"id": key, "tracks": [v for v in row[1:] if s.present(v)]})
    scenes = []
    for key, text in reader.table(FIELD).items():
        row = s.parse_rows(text)[0] if isinstance(text, str) and text else []
        scenes.append({"id": key, "background": s.cell(row, 0)})
    return {"bgm": bgm, "scenes": scenes, "terrains": terrain_choices(reader),
            "note": "BGM 填 battle_bgm_group 的键；场景填 field 的键（会为这一关派生独立 field_data）"}


TERRAIN_PATH = re.compile(r"^battle/terrain/[A-Za-z0-9_./-]+$")


def terrain_choices(reader):
    """Existing terrain logical paths (field_data c1) and the field_data rows that use them."""
    users = {}
    for key, text in reader.table(s.FIELD_DATA).items():
        row = s.parse_rows(text)[0] if isinstance(text, str) and text else []
        path = s.cell(row, 1)
        if s.present(path) and TERRAIN_PATH.match(path):
            users.setdefault(path, []).append(key)
    return [{"path": path, "uses": len(keys), "fieldData": sorted(keys)[:5]}
            for path, keys in sorted(users.items())]


def terrain_preview(reader, path):
    """Decoded layers of one existing terrain (read only; nothing is drafted)."""
    path = (path or "").strip().removesuffix(".amf3.deflate")
    if not TERRAIN_PATH.match(path) or ".." in path.split("/"):
        raise ValueError("地形路径必须是 battle/terrain/ 下的逻辑路径")
    result = read_terrain(reader, path)
    if result["missing"]:
        raise ValueError(f"当前视图里没有这个地形：{path}")
    return result


def weapon_icons(reader):
    """Icon references the weapon clone may reuse: equipment c6 and enhanced equipment c4."""
    from wf.boss.shop_model import ENH

    def collect(logical, column, name_column):
        seen = {}
        for key, text in reader.table(logical).items():
            row = s.parse_rows(text)[0] if isinstance(text, str) and text else []
            icon = s.cell(row, column)
            # Only references whose PNG exists in this view pass the clone's icon gate.
            if s.present(icon) and icon not in seen and reader.raw(icon + ".png") is not None:
                seen[icon] = {"icon": icon, "id": key, "name": s.cell(row, name_column)}
        return sorted(seen.values(), key=lambda entry: entry["icon"])
    return {"equipment": collect(s.EQUIPMENT, 6, 1), "enhanced": collect(ENH, 4, 2),
            "note": "只列当前视图里有 PNG 的已有图标引用；不新建图像或图集格"}


def draft_summary(entry, draft):
    requests = [r for change in (draft or {}).get("changes", []) for r in change["params"].get("requests", [])]
    create = next((r for r in requests if r.get("operation") == "create_shared"), None)
    return {**entry, "status": status(draft), "baseView": (draft or {}).get("baseView"),
            "requestCount": len(requests),
            "created": None if create is None else {
                "name": create.get("name"), "sourceQuest": create.get("sourceQuest", DEFAULT_TEMPLATE),
                "ids": create.get("ids")}}
