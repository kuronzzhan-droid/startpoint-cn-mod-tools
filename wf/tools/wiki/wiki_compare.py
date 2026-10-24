"""Official-versus-live comparisons for the same character ID, never templates."""
from __future__ import annotations

import re

import wf_describe
from wf_wiki_compare_refs import at, character_references
from wf_wiki_catalog_source import TABLES, sha256, walk_commands
from wf_wiki_skill_values import skill_numeric_details

LABELS = {"identity": "角色资料", "stats": "基础数值与觉醒增量", "leader": "队长技",
          "skills": "主动技能与能量", "abilities": "六项能力", "dependencies": "关联说明与固有状态",
          "programs": "技能与强化弹射程序"}
SKILL_LABELS = {"1": "普通技能", "2": "进化技能", "3": "二次进化技能"}


def state(before, after) -> str:
    if before == after:
        return "unchanged"
    return "added" if before is None else "removed" if after is None else "changed"


def differences(before, after, path="数据") -> list[dict]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        return [change for key in sorted(set(before) | set(after)) for change in
                differences(before.get(key), after.get(key), f"{path}.{key}")]
    if isinstance(before, list) and isinstance(after, list):
        return [change for index in range(max(len(before), len(after))) for change in
                differences(before[index] if index < len(before) else None,
                            after[index] if index < len(after) else None, f"{path}[{index}]")]
    return [{"field": path, "before": before, "after": after}]


def column_labels(kind: str) -> dict[int, str]:
    layout = wf_describe.layout(kind)
    result = {int(column[1:]): label for column, label in layout["head"]}
    fields = wf_describe.enum_map()["block_fields"]
    for block, start in layout["blocks"].items():
        key = "precondition" if block.startswith("precondition") else block
        for offset, name, label in fields.get(key, []):
            result[start + offset] = f"{block}.{name}（{label}）"
    return result


def row_changes(before: list, after: list, labels: dict | None = None) -> list[dict]:
    result = []
    for index in range(max(len(before), len(after))):
        old = before[index] if index < len(before) else []
        new = after[index] if index < len(after) else []
        for column in range(max(len(old), len(new))):
            a = old[column] if column < len(old) else None
            b = new[column] if column < len(new) else None
            if a != b:
                name = (labels or {}).get(column, f"c{column}")
                result.append({"field": f"第 {index + 1} 行 · c{column} · {name}", "before": a, "after": b})
    return result


def item(key: str, label: str, before, after, changes: list | None = None) -> dict:
    return {"key": key, "label": label, "status": state(before, after),
            "before": before, "after": after,
            "changes": differences(before, after) if changes is None else changes}


def section(key: str, items: list[dict]) -> dict:
    return {"key": key, "label": LABELS[key], "items": items,
            "status": "changed" if any(row["status"] in ("changed", "added", "removed") for row in items)
            else "unavailable" if any(row["status"] == "unavailable" for row in items) else "unchanged"}


def text_only(text: str) -> str:
    return re.sub(r"<icon\s+id=['\"]main['\"]\s*/?>", "【主位】", text).strip()


def identity_text(row: list) -> str:
    elements = {"0": "火", "1": "水", "2": "雷", "3": "风", "4": "光", "5": "暗"}
    types = {"0": "剑士", "1": "格斗", "2": "射击", "3": "辅助", "4": "特殊"}
    return f"{at(row, 2)}★ · {elements.get(at(row, 3), at(row, 3))}属性 · {types.get(at(row, 6), at(row, 6))}"


def ability_view(source, row: list[str], kind: str, slot: int, official: bool) -> dict:
    key = at(row, 17 if kind == "leader" else 18 + slot)
    rows = source.table(kind, official).get(key, [])
    parsed_kind = "leader_ability" if kind == "leader" else "ability"
    conditions = source.table("condition", official)

    def condition_name(match):
        match_rows = conditions.get(match[1], [])
        name = at(match_rows[0], 1) if match_rows else ""
        return f"{name}（固有{match[1]}）" if name else match[0]

    parsed = [re.sub(r"固有(\d+)", condition_name, desc)
              for desc in wf_describe.describe_rows(rows, parsed_kind)]
    override = source.table("strings", official).get("desc_override_" + (at(rows[0], 0) if rows else ""), [])
    authored = text_only(override[0][0]) if override and override[0] else ""
    return {"name": at(row, 18) if kind == "leader" else f"能力 {slot}", "key": key,
            "text": authored or "\n".join(parsed), "rows": rows,
            "source": "游戏面板覆盖文案" if authored else "该版本数据行自动解析"}


def stat_items(source, cid: str) -> list[dict]:
    old = {str(lv): {"hp": hp, "atk": atk} for lv, hp, atk in source.table("status", True).get(cid, [])}
    new = {str(lv): {"hp": hp, "atk": atk} for lv, hp, atk in source.table("status").get(cid, [])}

    def view(values):
        return None if values is None else {"text": f"HP {values['hp']} / ATK {values['atk']}", "values": values}

    result = [item(level, f"Lv{level} 基础数值", view(old.get(level)), view(new.get(level)),
                   differences(old.get(level), new.get(level), "基础数值"))
              for level in sorted(set(old) | set(new), key=int)]
    awake = []
    for official in (True, False):
        rows = source.table("awake", official).get(cid, [])
        awake.append(None if not rows else {"text": f"每节点 ATK +{at(rows[0], 0)} / HP +{at(rows[0], 1)}", "rows": rows})
    if any(awake):
        result.append(item("awake", "独立觉醒大节点增量", *awake))
    return result


def skill_items(source, before: list, after: list) -> list[dict]:
    old, new = source.table("skill", True).get(before[8], {}), source.table("skill").get(after[8], {})

    def view(rows):
        if not rows:
            return None
        row = rows[0]
        return {"name": at(row, 0), "text": text_only(at(row, 1)) +
                f"\n技能能量：初级 {at(row, 4)} / 满级 {at(row, 5)}", "rows": rows,
                "values": {"gaugeMin": at(row, 4), "gauge": at(row, 5), "program": at(row, 7)}}

    labels = {0: "技能名称", 1: "技能说明", 4: "初级技能能量", 5: "满级技能能量", 7: "技能程序"}
    return [item(level, SKILL_LABELS.get(level, level), view(old.get(level)), view(new.get(level)),
                 row_changes(old.get(level, []), new.get(level, []), labels))
            for level in sorted(set(old) | set(new))]


def program_items(source, old_programs: dict, new_programs: dict) -> list[dict]:
    output = []

    def view(logical, official):
        if not logical:
            return None, None
        tree = source.tree(logical, official)
        if tree is None:
            return None, None
        commands = list(walk_commands(tree))
        details = skill_numeric_details(tree, source.table("condition", official))
        lines = []
        for row in details["rows"]:
            context = "（" + "，".join(row["context"]) + "）" if row["context"] else ""
            fields = "；".join(f"{value['label']}：{value['value']}" for value in row["values"])
            lines.append(f"{row['label']}{context}：{fields}")
        text = "\n".join(lines) or "尚无可展示的倍率或状态数值；关联技能设置仍按实际数据比较。"
        return {"text": text, "numericDetails": details,
                "values": {"program": logical, "commandCount": len(commands)}}, tree

    for binding in sorted(set(old_programs) | set(new_programs)):
        old, old_tree = view(old_programs.get(binding), True)
        new, new_tree = view(new_programs.get(binding), False)
        changes = differences(old_tree, new_tree, "DSL")
        data = item(binding, program_label(binding), old, new, changes)
        # Byte-level re-encoding does not imply a gameplay change.
        data["status"] = state(old_tree, new_tree)
        if (old_programs.get(binding) and old is None) or (new_programs.get(binding) and new is None):
            data["status"] = "unavailable"
        output.append(data)
    return output


def program_label(binding: str) -> str:
    parts = binding.split(":")
    if parts[0] in ("skill", "switched"):
        return ("主动技能 · " if parts[0] == "skill" else "切换技能 · ") + SKILL_LABELS.get(parts[1], "其他层级")
    owner = "队长技" if parts[0] == "L" else "能力 " + parts[0][1:]
    effect = parts[-1]
    return owner + (f" · 强化弹射 Lv{effect[2:]}" if effect.startswith("PF") else " · 触发技能")


def dependency_view(table: str, rows) -> dict | None:
    if rows is None:
        return None
    if table == "strings":
        text = "\n".join(text_only(row[0]) for row in rows if row)
    elif table == "condition":
        row = rows[0] if rows else []
        parts = [at(row, 1) or "固有状态"]
        duration = at(row, 3)
        if duration.isdigit():
            frames = int(duration)
            parts.append("持续至战斗结束" if frames >= 99999 else f"持续 {frames / 60:g} 秒")
        if at(row, 4).isdigit():
            parts.append(f"叠加上限 {at(row, 4)} 层")
        text = "；".join(parts)
    else:
        text = "关联技能设置；数值效果见下方技能数值对照。"
    return {"text": text, "rows": rows}


def official_comparison(source, cid: str, *, verified_unchanged: bool = False) -> dict:
    """The compact mode is only for characters already checked by detect_roster."""
    official_characters = source.table("character", True)
    if not official_characters:
        return {"status": "unavailable", "baseline": None, "summary": ["缺少官方角色基准，无法可靠比较。"], "sections": [], "sources": []}
    official_rows = official_characters.get(cid)
    if not official_rows:
        return {"status": "new", "baseline": None, "summary": ["新增 MOD 角色，无相同角色 ID 的官方版本；不与制作模板或同名变体混比。"], "sections": [], "sources": []}
    before, after = official_rows[0], source.table("character")[cid][0]
    old_text = source.table("text", True).get(cid, [[]])[0]
    new_text = source.table("text").get(cid, [[]])[0]
    baseline_version = getattr(getattr(source, "baseline", None), "official_tail", "未知")
    baseline = {"version": baseline_version, "id": cid, "code": before[0],
                "name": at(old_text, 0), "title": at(old_text, 3)}
    if verified_unchanged:
        _refs, programs = character_references(source, after)
        missing = any(source.raw(logical, side) is None
                      for logical in programs.values() for side in (True, False))
        return {"status": "unavailable" if missing else "unchanged", "baseline": baseline,
                "summary": ["已取得的角色数据与官方版本相同；部分关联技能程序缺失，无法核对。" if missing else
                            "所检查的角色资料、数值、能力及关联技能程序与官方版本相同。"],
                "sections": [], "sources": []}
    identity = []
    for key, label, old, new, labels in (
            ("character", "角色属性与类型", before, after, {2: "稀有度", 3: "属性", 6: "强化弹射类型",
             9: "技能切换条件类型", 14: "切换技能键", 15: "切换技能静音", 16: "切换就绪语音静音", 17: "队长技键"}),
            ("text", "名称、称号与人物介绍", old_text, new_text, {0: "名称", 2: "人物介绍", 3: "称号"})):
        text = identity_text if key == "character" else (
            lambda row: f"{at(row, 0)} · {at(row, 3)}\n{at(row, 2)}")
        identity.append(item(key, label, {"text": text(old), "rows": [old]}, {"text": text(new), "rows": [new]}, row_changes([old], [new], labels)))
    sections = [section("identity", identity), section("stats", stat_items(source, cid))]
    for kind, section_key, slots in (("leader", "leader", (0,)), ("ability", "abilities", range(1, 7))):
        entries = []
        for slot in slots:
            old, new = ability_view(source, before, kind, slot, True), ability_view(source, after, kind, slot, False)
            labels = column_labels("leader_ability" if kind == "leader" else "ability")
            entries.append(item(str(slot), "队长技" if not slot else f"能力 {slot}", old, new, row_changes(old["rows"], new["rows"], labels)))
        sections.append(section(section_key, entries))
    sections.insert(3, section("skills", skill_items(source, before, after)))
    old_refs, old_programs = character_references(source, before, True)
    new_refs, new_programs = character_references(source, after)
    dependencies = []
    for table in old_refs:
        for key in sorted(old_refs[table] | new_refs[table]):
            old, new = source.table(table, True).get(key), source.table(table).get(key)
            if old == new:
                continue
            label = {"strings": "游戏面板说明", "condition": "固有状态", "switched": "切换技能设置",
                     "power_flip": "强化弹射设置"}[table]
            dependencies.append(item(f"{table}:{key}", label,
                                     dependency_view(table, old), dependency_view(table, new)))
    sections.extend((section("dependencies", dependencies), section("programs", program_items(source, old_programs, new_programs))))
    summary = []
    if before[2] != after[2]:
        summary.append(f"星级：{before[2]}★ → {after[2]}★")
    for data in sections[1]["items"]:
        if data["status"] != "unchanged":
            summary.append(f"{data['label']}：{(data['before'] or {}).get('text', '无')} → {(data['after'] or {}).get('text', '无')}")
    for data in next(s for s in sections if s["key"] == "skills")["items"]:
        old, new = (data["before"] or {}).get("values", {}), (data["after"] or {}).get("values", {})
        if old.get("gauge") != new.get("gauge"):
            summary.append(f"{data['label']}满级能量：{old.get('gauge', '无')} → {new.get('gauge', '无')}")
    for data in sections:
        changed = [row["label"] for row in data["items"] if row["status"] in ("changed", "added", "removed")]
        if changed and data["key"] not in ("stats", "identity"):
            summary.append(f"{data['label']}：{'、'.join(changed)}有调整")
    names = {"character", "text", "status", "awake", "ability", "leader", "skill", *old_refs}
    logicals = {TABLES[name] for name in names} | set(old_programs.values()) | set(new_programs.values())
    sources = [{"logical": logical, "officialSha256": sha256(raw) if (raw := source.raw(logical, True)) else None,
                "currentSha256": sha256(raw) if (raw := source.raw(logical)) else None} for logical in sorted(logicals)]
    changed = any(data["status"] == "changed" for data in sections)
    incomplete = any(data["status"] == "unavailable" for data in sections)
    return {"status": "changed" if changed else "unavailable" if incomplete else "unchanged", "baseline": baseline,
            "summary": summary or ["部分关联程序缺失，无法完成比较。" if incomplete else
                                   "所检查的数据与官方版本相同。"], "sections": sections, "sources": sources,
            "note": "原版来自 CN 官方最终归档；基础数值不含装备或玛纳板。能力描述分别解析各自版本；列差异和 DSL 路径为原始参数，程序变化不自动等同于总伤害变化。"}
