"""Character list / detail payloads for the 角色工坊 (read-only)."""
from __future__ import annotations

import wf_describe
from wf_wiki_catalog import (
    ELEMENTS, GENDERS, RACES, ROLES, TYPES, ability_group, cell, numeric, skills_for,
)

from .source import StudioSource

# Board grouping follows the Codex prototype IA: slots 1-3 = 一板, 4-6 = 二板,
# rows flagged as awakening (replace/add) = 三板. It is an inference from the
# slot position plus the awakening columns, not a separate board table.
BOARD_RULE = "按能力槽推定：能力 1–3 归一板，能力 4–6 归二板；带觉醒替换/追加标记的数据行归三板（觉醒）。"
AWAKE_KIND = {"1": "觉醒替换", "2": "觉醒追加"}


BLOCK_CN = {"precondition1": "前置1", "precondition2": "前置2", "precondition3": "前置3",
            "instant_trigger": "瞬发触发", "instant_precontent": "瞬发前置效果", "instant_delay": "瞬发延迟",
            "instant_content": "瞬发效果", "during_accumulation_trigger": "持续累积触发",
            "during_trigger": "持续触发", "even_if_owner_dead": "倒下仍生效", "during_content": "持续效果",
            "opening": "开幕"}


def column_labels(kind: str) -> list[dict]:
    """Per-column labels from ability_enum_map.json (block base + field offset)."""
    layout = wf_describe.layout(kind)
    fields = wf_describe.enum_map()["block_fields"]
    labels: dict[int, dict] = {}
    for name, note in layout.get("head", []):
        labels[int(name[1:])] = {"block": "基础", "field": note.split(" ")[0], "note": note}
    blocks = sorted(layout["blocks"].items(), key=lambda item: item[1])
    for i, (block, start) in enumerate(blocks):
        end = blocks[i + 1][1] if i + 1 < len(blocks) else int(layout.get("ncols", start + 1))
        known = {int(o): (f, n) for o, f, n in fields.get("precondition" if block.startswith("precondition") else block, [])}
        for column in range(int(start), int(end)):
            field, note = known.get(column - int(start), (f"+{column - int(start)}", ""))
            labels[column] = {"block": BLOCK_CN.get(block, block), "field": field, "note": note}
    return [labels.get(i, {"block": "", "field": "", "note": ""}) for i in range(int(layout.get("ncols", 0)))]


def _official_status(source: StudioSource, cid: str, row: list[str]) -> str:
    official = source.table("character", True)
    if not official:
        return "unknown"
    if cid not in official:
        return "new"
    base = official[cid][0] if official[cid] else []
    if base != row:
        return "modified"
    for name, keys in (("ability", row[19:25]), ("leader", [cell(row, 17)])):
        live, ref = source.table(name), source.table(name, True)
        if any(live.get(k) != ref.get(k) for k in keys if k and k != "(None)"):
            return "modified"
    if source.table("skill").get(cell(row, 8)) != source.table("skill", True).get(cell(row, 8)):
        return "modified"
    return "official"


def list_characters(source: StudioSource, *, with_origin: bool = True) -> list[dict]:
    characters = source.table("character")
    texts = source.table("text")
    result = []
    for cid, rows in characters.items():
        if not rows or not rows[0]:
            continue
        row = rows[0]
        text = texts.get(cid, [[]])[0] if texts.get(cid) else []
        result.append({
            "id": cid, "code": row[0], "name": cell(text, 0) or row[0], "title": cell(text, 3),
            "rarity": numeric(cell(row, 2)), "elementId": cell(row, 3),
            "element": ELEMENTS.get(cell(row, 3), cell(row, 3)),
            "type": TYPES.get(cell(row, 6), cell(row, 6)),
            "origin": _official_status(source, cid, row) if with_origin else "unknown",
        })
    result.sort(key=lambda item: int(item["id"]) if item["id"].isdigit() else 0)
    return result


def _is_awake(row: list[str]) -> bool:
    kind, level = cell(row, 3).strip(), cell(row, 4).strip()
    return kind == "2" or (kind == "1" and level.isdigit() and int(level) >= 1)


def _ability_entry(source: StudioSource, slot: int, key: str) -> dict:
    group = ability_group(source, "ability", key, f"能力 {slot}")
    base_rows, awake_rows = [], []
    for item in group["rows"]:
        (awake_rows if _is_awake(item["values"]) else base_rows).append(item)
        if _is_awake(item["values"]):
            item["awake"] = {"kind": AWAKE_KIND.get(cell(item["values"], 3), cell(item["values"], 3)),
                             "level": cell(item["values"], 4)}
    return {"slot": slot, **group, "baseRows": base_rows, "awakeRows": awake_rows}


def _strip_programs(group: dict) -> dict:
    # rawCommands can be large; keep only the summary for the UI.
    for program in group.get("relatedPrograms", []):
        program.pop("rawCommands", None)
        program.pop("numericDetails", None)
    return group


def character_detail(source: StudioSource, cid: str) -> dict | None:
    rows = source.table("character").get(cid)
    if not rows or not rows[0]:
        return None
    row = rows[0]
    text_rows = source.table("text").get(cid, [])
    text = text_rows[0] if text_rows else []
    abilities = [_strip_programs(_ability_entry(source, i + 1, key)) for i, key in enumerate(row[19:25])]
    leader = _strip_programs(ability_group(source, "leader", cell(row, 17), cell(row, 18) or "队长技"))
    skills, switch = skills_for(source, row)
    for skill in skills:
        skill.pop("rawCommands", None)
        skill.pop("numericDetails", None)
    boards = [
        {"id": "board1", "label": "一板", "slots": [a for a in abilities if a["slot"] <= 3],
         "rowsKey": "baseRows"},
        {"id": "board2", "label": "二板", "slots": [a for a in abilities if a["slot"] >= 4],
         "rowsKey": "baseRows"},
        {"id": "board3", "label": "三板（觉醒）", "slots": [a for a in abilities if a["awakeRows"]],
         "rowsKey": "awakeRows"},
    ]
    levels = sorted(({"level": numeric(level), "hp": hp, "atk": atk}
                     for level, hp, atk in source.table("status").get(cid, [])),
                    key=lambda entry: entry["level"] if isinstance(entry["level"], int) else 0)
    return {
        "id": cid, "code": row[0], "name": cell(text, 0) or row[0], "nameEn": cell(text, 1),
        "title": cell(text, 3), "rarity": numeric(cell(row, 2)), "elementId": cell(row, 3),
        "element": ELEMENTS.get(cell(row, 3), cell(row, 3)), "type": TYPES.get(cell(row, 6), cell(row, 6)),
        "role": ROLES.get(cell(row, 26), cell(row, 26)),
        "races": [RACES.get(v, v) for v in cell(row, 4).split(",") if v],
        "gender": GENDERS.get(cell(row, 7), cell(row, 7)), "cv": cell(text, 11), "profile": cell(text, 2),
        "origin": _official_status(source, cid, row),
        "boardRule": BOARD_RULE, "boards": boards, "leader": leader, "abilities": abilities,
        "skills": skills, "switch": switch, "levels": levels,
        "describeNote": "中文描述由 wf_describe 按数据行语义生成，不是游戏客户端原文；有覆盖文案时优先显示覆盖文案。",
        "sources": [source.citation(name) for name in ("character", "text", "ability", "leader", "skill", "strings")],
        "raw": {"character": row, "characterText": text},
        "columns": {"ability": column_labels("ability"), "leader_ability": column_labels("leader_ability")},
    }
