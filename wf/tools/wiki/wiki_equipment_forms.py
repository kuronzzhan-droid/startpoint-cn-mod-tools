"""Read-only PARADOX form snapshots at its actual enhancement milestones."""
from collections import defaultdict

import wf_describe
from wf_wiki_equipment_helpers import cell, effects, endpoint_row, integer, learned_rows
from wf_wiki_equipment_final import final_effect_fields, row_at_level

KIND = "equipment_enhancement_ability"
TEAM_KINDS = {"55", "696", "226"}
FORM_NOTE = ("强化数值与满觉醒本体叠加；直接攻击由本体6段覆写为8段，Lv200仍为8段，不能相加成14段。"
             "每次弹射追加连击在Lv120与Lv200均合计+50；诅咒从强化120级起生效。")
TOTAL_LABELS = {
    "32": "攻击力", "33": "直接攻击伤害", "34": "技能伤害", "55": "强化弹射伤害",
    "388": "能力伤害", "723": "独立乘区伤害", "693": "独立乘区直接攻击伤害",
    "694": "独立乘区技能伤害", "695": "独立乘区能力伤害", "696": "独立乘区强化弹射伤害",
    "35": "技能充能速度", "245": "技能槽上限", "717": "追加合击角色攻击力比例",
    "226": "每次弹射追加连击",
}


def total_summary(soul_rows, resolved_rows, text, level, *, base_maximum=True):
    """Add only the verified self-target numeric effects; preserve conditions."""
    totals = defaultdict(int)
    for kind, rows in (("ability_soul", soul_rows), (KIND, resolved_rows)):
        blocks = wf_describe.layout(kind)["blocks"]
        content, pre = blocks["instant_content"], blocks["precondition1"]
        for original in rows:
            row = endpoint_row(original, kind, base_maximum if kind == "ability_soul" else True)
            effect = cell(row, content)
            target = cell(row, content + 1)
            if (cell(row, pre - 1) != "0" or effect not in TOTAL_LABELS or
                    (target != "0" and not (effect in TEAM_KINDS and target == ""))):
                continue
            condition = text.clean(cell(row, pre + 5)) if cell(row, pre) == "3" else ""
            if cell(row, pre) not in ("0", "3"):
                continue
            totals[(effect, condition)] += integer(cell(row, content + 4))
    base_label = "满觉醒本体" if base_maximum else "初始本体"
    lines = [f"强化 Lv{level} 主要数值合计（含{base_label}）："]
    for (effect, condition), value in totals.items():
        amount = value / (100000 if effect == "226" else 1000)
        prefix = f"自身为{condition}时额外" if condition else ("" if effect in TEAM_KINDS else "自身")
        lines.append(f"{prefix}{TOTAL_LABELS[effect]} +{amount:g}{'次' if effect == '226' else '%'}")
    lines.append("其他本体规则继续保留；直击形态、回响与诅咒分别见本体及本等级追加效果。")
    return "\n".join(lines)


def paradox_forms(entry, erow, soul_rows, enhancement_rows, increments, text, pictures):
    """Keep max-level compatibility fields; add separate 120/200 snapshots."""
    enhanced = entry["enhancement"]
    first_level = integer(cell(erow, 3))
    first_icon = cell(erow, 4)
    tier2 = text.custom.get("enhanced_pixelart_tier2_" + first_icon, "").split(",", 1)
    milestones = [(first_level, first_icon)]
    if len(tier2) == 2:
        milestones.append((integer(tier2[0]), tier2[1]))
    forms = []
    for level, icon in milestones:
        if not level or level > enhanced["maxLevel"]:
            continue
        point = next((point for point in increments if point["level"] == level), None)
        if point is None:
            raise ValueError(f"悖论形态 Lv{level} 缺少强化面板数值")
        increment = {key: point[key] for key in ("hp", "atk")}
        total = {key: entry["stats"]["awakened"][key] + increment[key] for key in ("hp", "atk")}
        resolved = [row_at_level(row, level) for row in learned_rows(enhancement_rows, level)]
        form = {
            "level": level, "label": f"{'终式' if level == first_level else '蓝金形态'} Lv{level}",
            "name": enhanced["name"], "icon": pictures.image(icon),
            "description": enhanced["description"],
            "effects": effects(resolved, KIND, level, text),
            "stats": {"additional": increment, "total": total},
            "panelDescription": enhanced["panelDescription"],
            "finalDescription": total_summary(learned_rows(soul_rows, entry["maxAwakeningLevel"]), resolved, text, level),
            "initialFinalDescription": total_summary(learned_rows(soul_rows, 1), resolved, text,
                                                     level, base_maximum=False),
            "note": FORM_NOTE,
        }
        form.update(final_effect_fields(soul_rows, enhancement_rows,
                                       entry["maxAwakeningLevel"], level, text))
        frame = text.custom.get("enhanced_frame_override_" + icon)
        if frame:
            form["frame"] = pictures.image(frame)
        forms.append(form)
    return forms
