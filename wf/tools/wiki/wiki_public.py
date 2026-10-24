"""Project an export into player-facing data without game keys or source code."""
from __future__ import annotations

import hashlib
import re

PRIVATE = {
    "code", "raw", "rawCommands", "commands", "commandsNote", "commandCount", "program",
    "sources", "sourceHashes", "sourceMissing", "sourceFiles", "sourceDocuments", "fingerprints",
    "changes", "customText", "modificationScope", "key", "elementId", "categorySource", "logical",
    "source", "audioSha", "missingTranslations", "uniqueCondition", "multiballs", "condition",
    "questId",
}

# GROUP_CN in wf_describe; DirectAttack1/2/3 resolve to 1/2/3 attack
# segments in DuringAbilitySource / InstantAbilitySource, not total multipliers.
ENUM_CN = {
    "Red": "火", "Blue": "水", "Yellow": "雷", "Green": "风", "White": "光", "Black": "暗",
    "MySelf": "自身", "Delete": "解除", "Direct": "直接攻击",
    "DirectAttack1": "直接攻击1段（伤害修正）",
    "DirectAttack2": "直接攻击2段（伤害修正）",
    "DirectAttack3": "直接攻击3段（伤害修正）",
    "Flying": "浮游", "Revival": "复活", "Specific": "指定",
    "HPIncrease": "生命回复", "HPDecrease": "生命减少",
}
DISPLAY_FIELDS = {"description", "text", "context", "note", "notes", "summary", "label",
                  "panelDescription", "finalDescription"}
ENUM_PATTERN = re.compile(r"(?<![A-Za-z0-9_])(?:" +
                          "|".join(sorted(ENUM_CN, key=len, reverse=True)) +
                          r"|Flag[1-6]?)(?![A-Za-z0-9_])")


def public_id(kind, value):
    return kind + hashlib.sha256(f"wf-wiki-public-v1:{kind}:{value}".encode()).hexdigest()[:12]


def catalog_order(character_ids):
    """Native character/showOrder order, published only as a continuous rank."""
    identifiers = [str(value) for value in character_ids]
    if len(identifiers) != len(set(identifiers)) or any(not value.isdecimal() for value in identifiers):
        raise ValueError("图鉴顺序需要唯一的原生角色编号")
    return {public_id("c", value): index + 1
            for index, value in enumerate(sorted(identifiers, key=int))}


def clean_text(value, translate_enums=True):
    value = re.sub(r"（固有\d+）", "", value)
    value = re.sub(r"固有\d+", "固有状态", value)
    value = re.sub(r"(?:battle|master|character)/[^\s，。；）\]']+", "相关技能", value)
    value = re.sub(r"(?:[A-Za-z]:[\\/]|file:///)[^\n]+", "本地资料", value)
    value = re.sub(r"\[[A-Za-z][A-Za-z0-9_$./-]*_[A-Za-z0-9_$./-]+\]", "（特殊效果）", value)
    value = re.sub(r"\b[A-Za-z][A-Za-z0-9$]*_[A-Za-z0-9_$./-]+", "特殊效果", value)
    # Only human Chinese explanations; never English/romaji or Japanese dialogue.
    if translate_enums and re.search(r"[\u3400-\u9fff]", value) and not re.search(r"[\u3040-\u30ff]", value):
        value = ENUM_PATTERN.sub(lambda match: ENUM_CN.get(match[0], match[0].replace("Flag", "标记")), value)
    return value.replace("角色 ID", "角色条目").replace("程序摘要", "详细数值")


def readable(value, field="", translate_enums=True):
    if isinstance(value, str):
        return clean_text(value, translate_enums and field in DISPLAY_FIELDS)
    if isinstance(value, list):
        return [readable(item, field, translate_enums) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in PRIVATE or key == "id":
            continue
        if key == "rows":
            item = [row for row in item if isinstance(row, dict)]
        if key == "values" and isinstance(item, list):
            item = [row for row in item if isinstance(row, dict) and "label" in row and "value" in row]
        result[key] = readable(item, key, translate_enums and key != "voices")
    return result


def public_catalog(catalog):
    result = readable(catalog)
    order = catalog_order(character["id"] for character in catalog["characters"])
    for original, public in zip(catalog["characters"], result["characters"]):
        public["id"] = public_id("c", original["id"])
        public["catalogOrder"] = order[public["id"]]
        # Errors retain player context, never exception payloads or file paths.
        public["warnings"] = [w for w in public.get("warnings", []) if not re.search(r"[A-Za-z_]{8,}", w)]
    for original, public in zip(catalog.get("equipment", []), result.get("equipment", [])):
        public["id"] = public_id("w", original["id"])
    result["meta"]["dataNote"] = "数值从当前资料解析；条件、成长与单次命中倍率分别列出。"
    result["meta"]["rosterRule"] = "收录官方可玩角色、改版官方与新增 MOD。剧情及助战占位角色不列为可玩角色；独立角色包的资料来源另行标注。"
    result["meta"]["credits"] = ["界面及配队交互参考作者提供的《弹射世界中文 WIKI》离线版 v3.0.0。感谢memimu及「弹射世界wiki重生群」（QQ群 610753092）整理的 Wiki 资料；当前 MOD 数值以本次数据快照为准。"]
    return result
