"""Conservative text rules: hard syntax failures and reviewable overlap evidence."""
from __future__ import annotations

import re
import unicodedata

_MAX_HP = r"100(?:\.0+)?%"
_TAUTOLOGY = re.compile(
    rf"(?:生命值|HP|体力)(?:为|在|是)?(?:"
    rf"(?:不高于|小于等于|不超过|≤|<=){_MAX_HP}|"
    rf"{_MAX_HP}(?:以下|及以下|以内))", re.I)


def normalized(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).replace("＋", "+")


def check_character(document: dict) -> list[dict]:
    findings = []

    def add(rule, state, location, message, **evidence):
        findings.append({"rule": rule, "state": state, "location": location,
                         "message": message, "evidence": evidence})

    fields = [("title", document["title"], True)]
    for tier, pair in document["action_skill"].items():
        fields += [(f"action_skill.{tier}.c0", pair["c0"], True),
                   (f"action_skill.{tier}.c1", pair["c1"], False)]
    for section in ("custom_ability_string", "desc_override"):
        fields += [(f"{section}.{key}", value, False) for key, value in document[section].items()]
    # Character names, biography, leader name, voice attribution remain visible.
    fields += [(f"character_text.{column}", value, column in ("0", "3", "10"))
               for column, value in document["character_text"].items() if int(column) not in range(4, 10)]
    for location, value, is_name in fields:
        text = normalized(value)
        if _TAUTOLOGY.search(text):
            add("text.tautology", "问题", location, "生命值不高于100%的条件恒真；应删除条件或核实真实阈值", text=value)
        if (is_name and re.search(r"之核(?:[+＋]*|[）)】」』])?$", text)) or re.search(r"[「『【]([^」』】]*之核)[」』】]", text):
            add("text.core_name", "问题", location, "命名不得采用‘…之核’", text=value)
    enhancements = {k: v for k, v in document["custom_ability_string"].items()
                    if k.startswith("change_skill_")}
    enhancements.update({k: v for k, v in document["desc_override"].items()
                         if re.search(r"强化[『「].+[』」]", v)})
    for tier, pair in document["action_skill"].items():
        desc = normalized(pair["c1"])
        clauses = [normalized(x) for x in re.split(r"[／/\n；;。]", pair["c1"]) if len(normalized(x)) >= 8]
        for clause in set(clauses):
            if clauses.count(clause) > 1:
                add("text.duplicate_enhancement", "问题", f"action_skill.{tier}.c1",
                    "技能描述重复同一效果段落", repeated=clause)
        for key, value in enhancements.items():
            # Remove the skill name and editing verbs. Exact effect clauses are
            # proof of textual duplication; semantic resemblance needs review.
            effects = re.sub(r"[『「][^』」]+[』」]", "", value)
            effects = re.sub(r"^(?:强化|追加|增加|使|将|的|效果|[：:、/／\s])+", "", effects)
            chunks = [normalized(x) for x in re.split(r"[／/\n；;。]", effects)]
            matches = [x for x in chunks if len(x) >= 8 and x in desc]
            if matches:
                add("text.duplicate_enhancement", "问题", f"action_skill.{tier}.c1",
                    "技能描述再次写入关联技能强化文字", key=key, repeated=matches)
            elif len(desc) >= 8 and desc in normalized(value):
                add("text.duplicate_enhancement", "问题", f"action_skill.{tier}.c1",
                    "关联技能强化包含完整技能描述", key=key)
            else:
                # Common effect labels alone do not prove duplicated gameplay.
                # Keep these reviewable instead of inventing equivalence.
                labels = ("攻击力提升", "技能伤害提升", "直接攻击伤害", "全属性抗性降低",
                          "强化弹射伤害", "累积攻击力降低", "技能槽", "贯穿", "浮游")
                overlap = [label for label in labels if label in desc and label in normalized(value)]
                if overlap:
                    add("text.enhancement_overlap", "待验证", f"action_skill.{tier}.c1",
                        "技能与关联强化出现相同效果名；需核对是强化差值还是重复描述", key=key, labels=overlap)
    if not findings:
        add("text.style", "满足", document["character_id"], "已检查恒真条件、命名和可证明的重复强化；语义效果仍需设计者核对")
    return findings
