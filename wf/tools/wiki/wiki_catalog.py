"""Build an auditable MOD-character wiki snapshot without modifying game data."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import zlib

import wf_describe
import wf_dsl_sig
from wf_wiki_categories import (
    ALIASES, CATEGORIES, EDITOR_NOTES, HIDDEN_CHARACTER_IDS, SMALL_ANIMAL_NOTE, category_for,
)
from wf_wiki_catalog_source import WikiSource, detect_roster, version_at, walk_commands
from wf_wiki_catalog_tags import OFFICIAL_NON_PLAYABLE_IDS, character_tags
from wf_wiki_compare import official_comparison
from wf_wiki_skill_values import skill_numeric_details
from wf_wiki_ability_conditions import ability_restrictions
from wf_wiki_nameplates import attach_nameplates
from wf_wiki_avatars import character_avatars

ELEMENTS = {"0": "火", "1": "水", "2": "雷", "3": "风", "4": "光", "5": "暗", "6": "通用"}
TYPES = {"0": "剑士", "1": "格斗", "2": "射击", "3": "辅助", "4": "特殊"}
RACES = dict(Human="人", Beast="兽", Element="精灵", Machine="机械", Undead="不死",
             Mystery="神秘", Dragon="龙", Devil="魔", Plants="植物", Aquatic="水栖")
ROLES = dict(Attacker="进攻", Balance="均衡", Healer="治疗", Jammer="妨碍", Supporter="支援", Tank="防御")
GENDERS = dict(Male="男", Female="女", Unknown="未知", Ririi="其他（Ririi）")
LEVELS = {"1": "普通技能", "2": "进化技能", "3": "二次进化技能"}
SWITCHES = {"0": "HP 达到阈值", "1": "存在指定状态", "2": "协力球达到指定数量",
            "3": "技能变化标志触发", "4": "处于合击位"}
# This one official path contains a historical MOD reskin in the live store.
# Keep the exception precise: other official and MOD media still use live assets.
OFFICIAL_PORTRAIT_OVERRIDES = frozenset({
    "character/pirates_girl/ui/full_shot_1440_1920_0.png",
})


def cell(row: list, index: int, default=""):
    return row[index] if index < len(row) else default


def numeric(value):
    try:
        return int(value)
    except (ValueError, TypeError):
        return value or None


def plain(text: str) -> str:
    """Preserve authored content but convert the one known main-position icon."""
    return re.sub(r"<icon\s+id=['\"]main['\"]\s*/?>", "【主位】", text).strip()


def condition_names(source: WikiSource, text: str) -> str:
    conditions = source.table("condition")

    def replace(match):
        rows = conditions.get(match[1], [])
        name = cell(rows[0], 1) if rows else ""
        return f"{name}（固有{match[1]}）" if name else match[0]

    return re.sub(r"固有(\d+)", replace, text)


def ability_group(source: WikiSource, kind: str, key: str, name: str) -> dict:
    rows = source.table(kind).get(key, [])
    parsed_kind = "leader_ability" if kind == "leader" else "ability"
    descriptions = [condition_names(source, text) for text in wf_describe.describe_rows(rows, parsed_kind)]
    strings = source.table("strings")
    sid = rows[0][0] if rows and rows[0] else ""
    override = strings.get("desc_override_" + sid, [])
    authored = plain(override[0][0]) if override and override[0] else ""
    references = {}
    for row in rows:
        for value in row:
            if value in strings and value not in references:
                references[value] = "\n".join(plain(r[0]) for r in strings[value] if r)
    description = authored or "\n".join(descriptions)
    if not description and key in ("", "(None)"):
        description = "此角色未配置队长技。" if kind == "leader" else "此角色未配置该能力。"
    return {
        "key": key, "name": name,
        "description": description,
        "descriptionSource": "游戏面板覆盖文案" if authored else "数据行自动解析",
        "rows": [{"index": i + 1, "description": desc, "values": row,
                  **({"restrictions": ability_restrictions(row)} if kind == "ability" else {})}
                 for i, (row, desc) in enumerate(zip(rows, descriptions))],
        "customText": references, "relatedPrograms": related_programs(source, rows, parsed_kind),
    }


def skill_program(source: WikiSource, program: str) -> dict:
    if not program or program == "(None)":
        return {"commands": [], "commandCount": 0, "warning": "本层级未引用技能程序"}
    logical = program if program.endswith(".amf3.deflate") else program + ".action.dsl.amf3.deflate"
    try:
        tree = source.tree(logical)
        if tree is None:
            return {"commands": [], "commandCount": 0, "warning": "技能程序文件缺失"}
        raw = list(walk_commands(tree))
        summaries = list(dict.fromkeys(wf_dsl_sig.brief_command(item[1]) for item in raw))
        return {"commands": summaries[:24], "commandCount": len(raw), "rawCommands": compact_commands(raw),
                "numericDetails": skill_numeric_details(tree, source.table("condition")),
                "commandsNote": "程序节点摘要；原始参数中的 commandRef 指向同表节点编号，保留嵌套分支且避免重复展开。",
                "source": source.citation(logical)}
    except (ValueError, IndexError, KeyError, TypeError, zlib.error) as exc:
        return {"commands": [], "commandCount": 0, "warning": "技能程序解析失败：" + str(exc)}


def compact_commands(commands: list) -> list[dict]:
    """Keep exact arguments while replacing repeated nested subtrees with links."""
    indices = {id(node): index + 1 for index, node in enumerate(commands)}

    def argument(value):
        if isinstance(value, list):
            if id(value) in indices:
                return {"commandRef": indices[id(value)]}
            return [argument(child) for child in value]
        if isinstance(value, dict):
            return {key: argument(child) for key, child in value.items()}
        return value

    return [{"index": index + 1, "kind": node[0], "name": node[1][0],
             "arguments": argument(node[1][1:])} for index, node in enumerate(commands)]


def related_programs(source: WikiSource, rows: list[list[str]], kind: str) -> list[dict]:
    """Follow native InvokeSkill paths and explicit power-flip table references."""
    blocks = wf_describe.layout(kind)["blocks"]
    content = int(blocks["instant_content"])
    flips = source.table("power_flip")
    refs: dict[str, dict] = {}
    for row in rows:
        if cell(row, content) == "629":
            sid = cell(row, content + 23)
            program = cell(row, content + 24)
            if sid and sid != "(None)" and program.startswith("battle/"):
                refs[program] = {"kind": "能力触发技能", "key": sid, "program": program}
        for value in (cell(row, content + 35), cell(row, int(blocks["during_content"]) + 11)):
            if value not in flips:
                continue
            for entries in flips[value]:
                for level, program in enumerate(entries, 1):
                    if program.startswith("battle/"):
                        refs[program] = {"kind": f"特殊强化弹射 Lv{level}", "key": value,
                                         "program": program}
    return [dict(ref, **skill_program(source, program)) for program, ref in refs.items()]


def skills_for(source: WikiSource, row: list[str]) -> tuple[list[dict], dict | None]:
    skills = []
    main = source.table("skill").get(row[8], {})
    for level, rows in main.items():
        fields = rows[0] if rows else []
        program = cell(fields, 7)
        skills.append({"kind": "main", "level": level, "label": LEVELS.get(level, level),
                       "name": cell(fields, 0), "description": plain(cell(fields, 1)),
                       "gauge": numeric(cell(fields, 5)), "gaugeMin": numeric(cell(fields, 4)),
                       "gaugeLabel": "满技能等级所需能量", "program": program, "raw": fields,
                       **skill_program(source, program)})
    switch = None
    switch_key = cell(row, 14)
    if cell(row, 9) not in ("", "(None)") and switch_key:
        switch = {"kind": row[9], "label": SWITCHES.get(row[9], row[9]),
                  "condition": cell(row, 10), "uniqueCondition": cell(row, 11),
                  "multiballs": cell(row, 12), "threshold": cell(row, 13), "key": switch_key}
        condition = source.table("condition").get(cell(row, 11), [])
        if condition:
            switch["conditionName"] = cell(condition[0], 1)
        for level, rows in source.table("switched").get(switch_key, {}).items():
            fields = rows[0] if rows else []
            program = cell(fields, 0)
            original = next((s for s in skills if s["kind"] == "main" and s["level"] == level), {})
            same_program = program == original.get("program")
            voice_route = same_program and switch_key.endswith("_voice_ready")
            label = "语音路由（共用原技能程序）" if voice_route else "切换后技能"
            skills.append({"kind": "switched", "level": level,
                           "label": label + " · " + LEVELS.get(level, level),
                           "name": original.get("name", switch_key),
                           "description": "由角色技能切换条件调用；独立效果见程序摘要。" if not same_program
                           else "此路由共用原技能程序" + ("，用于语音切换。" if voice_route else "。"),
                           "gauge": original.get("gauge"), "gaugeMin": original.get("gaugeMin"),
                           "gaugeLabel": "沿用对应普通/进化技能的能量", "program": program, "raw": fields,
                           **skill_program(source, program)})
    return skills, switch


def character_entry(source: WikiSource, cid: str, scope: list[str] | None, media) -> dict:
    row = source.table("character")[cid][0]
    text_rows = source.table("text").get(cid, [])
    text = text_rows[0] if text_rows else []
    code = row[0]
    abilities = [dict(slot=i + 1, **ability_group(source, "ability", key, f"能力 {i + 1}"))
                 for i, key in enumerate(row[19:25])]
    leader = ability_group(source, "leader", row[17], row[18])
    skills, switch = skills_for(source, row)
    levels = [{"level": numeric(level), "hp": hp, "atk": atk}
              for level, hp, atk in source.table("status").get(cid, [])]
    levels.sort(key=lambda entry: entry["level"])
    awake = source.table("awake").get(cid, [])
    awake_row = awake[0] if awake else []
    portraits = []
    warnings = []
    for form, label in (("0", "觉醒前"), ("1", "觉醒后")):
        logical = f"character/{code}/ui/full_shot_1440_1920_{form}.png"
        if logical in OFFICIAL_PORTRAIT_OVERRIDES:
            url = media.official_image(logical, source.baseline)
            if not url:
                warnings.append(label + "官方立绘暂不可用，已隐藏错误图片")
        else:
            url = media.image(logical)
        if url:
            portraits.append({"label": label, "url": url})
    avatars = character_avatars(code, media)
    icon = avatars.get("before") or avatars.get("after")
    if not levels:
        warnings.append("缺少基础数值表")
    if not portraits:
        warnings.append("当前数据源缺少可导出的立绘")
    for entry in [leader] + abilities:
        if not entry["rows"] and entry["key"] not in ("", "(None)"):
            warnings.append(entry["name"] + "没有数据行")
    warnings.extend(s["warning"] for s in skills if s.get("warning"))
    warnings.extend(program["warning"] for group in [leader] + abilities
                    for program in group["relatedPrograms"] if program.get("warning"))
    sources = [source.citation(name) for name in
               ("character", "text", "status", "awake", "ability", "leader", "skill", "strings", "power_flip", "condition")]
    official = cid in source.table("character", True)
    category, category_source = category_for(cid, official_modified=bool(scope),
                                             official_original=official and not scope)
    origin = "改版官方" if scope else "官方原版" if official else "新增MOD"
    return {
        "id": cid, "code": code, "name": cell(text, 0) or code, "nameEn": cell(text, 1),
        "title": cell(text, 3), "rarity": numeric(row[2]), "elementId": row[3],
        "element": ELEMENTS.get(row[3], row[3]), "type": TYPES.get(row[6], row[6]),
        "role": ROLES.get(row[26], row[26]), "races": [RACES.get(v, v) for v in row[4].split(",") if v],
        "gender": GENDERS.get(row[7], row[7]), "cv": cell(text, 11), "profile": cell(text, 2),
        "origin": origin, "modificationScope": scope or ([] if official else ["新增角色"]),
        "category": category, "categorySource": category_source,
        **character_tags(cid, row, cell(text, 0), ALIASES.get(cid, [])),
        "officialComparison": official_comparison(source, cid, verified_unchanged=official and not scope),
        "editorNote": EDITOR_NOTES.get(cid, ""), "earlyDesign": cid == "129999",
        "icon": icon, "avatars": avatars, "portraits": portraits,
        "leader": leader, "abilities": abilities, "skills": skills,
        "switch": switch, "stats": {"levels": levels,
            "awakePerNode": {"atk": numeric(cell(awake_row, 0)), "hp": numeric(cell(awake_row, 1))}
            if awake_row else None,
            "note": "基础数值断点；区间内由客户端线性插值并向上取整。未计玛纳板、装备及能力加成。",
            "awakeNote": "觉醒表为每个已点亮觉醒大节点的独立增量，未计入上表；不是满觉醒总面板。"},
        "sources": sources, "warnings": warnings, "raw": {"character": row, "characterText": text},
    }


def build_catalog(repo: Path, media) -> dict:
    repo = Path(repo)
    version = version_at(repo)
    source = WikiSource(repo, Path(media.store))
    _mod_roster, modified = detect_roster(source)
    official = set(source.table("character", True))
    roster = sorted(set(source.table("character")) - (official & OFFICIAL_NON_PLAYABLE_IDS), key=int)
    # Filter before entry creation: hidden characters must not export any media.
    roster = [cid for cid in roster if cid not in HIDDEN_CHARACTER_IDS]
    modified = {cid: scope for cid, scope in modified.items() if cid in roster}
    characters = [character_entry(source, cid, modified.get(cid), media) for cid in roster]
    nameplates = attach_nameplates(repo, source, characters, media)
    source.verify_unchanged()
    if version_at(repo) != version:
        raise RuntimeError("导出过程中本地版本链发生变化，请重新导出")
    return {"meta": {
        "version": version, "source": "本地 live 客户端表与官方归档差异快照",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "counts": {"total": len(roster), "newMod": len(set(roster) - official),
                   "modifiedOfficial": len(modified),
                   "officialOriginal": len(set(roster) & official) - len(modified)},
        "categoryCounts": {category: sum(c["category"] == category for c in characters)
                           for category in CATEGORIES},
        "categoryNote": SMALL_ANIMAL_NOTE,
        "rosterRule": "收录官方可玩角色与新增 MOD 角色。官方档案中的 21 条剧情、助战及占位记录（已核 ID，c32=2/4）不列为可玩角色。改版官方依据身份、文案、数值、能力、主/切换技能及关联程序的差异识别。",
        "themeNote": "节庆主题来自明确的角色主题标记；未识别主题的同一人物变体标为其他变体，基础形态标为通常版。",
        "dataNote": "游戏文案与程序数据分别展示；自动解析不等同于实机机制验收。",
        "nameplates": {key: value for key, value in nameplates.items() if key != "sourceFiles"},
        "sourceFiles": nameplates["sourceFiles"],
        "fingerprints": source.fingerprints,
        "sourceHashes": source.live_hashes, "sourceMissing": sorted(source.missing),
    }, "characters": characters}
