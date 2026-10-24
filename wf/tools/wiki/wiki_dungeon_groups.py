"""Public series vocabulary shared by the exporter and package validator.

These are presentation groups only. Every native activity keeps its original
entry ID, quests, guide and recommendation associations.
"""
from __future__ import annotations


LEGACY_GROUPS = {
    "series-gauntlets": ("连战模式", ("幻想连战", "普通深渊", "深渊连战EX")),
    "series-machina": ("机兵决战", ("火", "水", "雷", "风", "光", "暗", "无属性")),
    "series-waste-dragons": ("荒龙讨伐", ("火", "水", "雷", "风", "光", "暗")),
    "series-spirit-beasts": ("精灵兽讨伐", ("火", "水", "雷", "风", "光", "暗")),
}
STORY_TITLES = (
    "幻彩摩天楼", "虚假的人偶公主", "大海的遗产", "妖怪图鉴编纂记",
    "祈愿吧，光之继承者们。", "激斗！情人节盛典攻防战！！", "共誓黎明",
    "HERO:BEGINNING", "热情的爱河★漂流者", "百兽王冠", "前进吧，暗之梦旅人们。",
    "胆怯PureYells！", "交织未来的世界之歌", "碧蓝晴空微笑", "悠久王道，继承之骑士道", "Ceremony",
)
GROUPS = {
    **LEGACY_GROUPS,
    "series-raid-feast": ("战阵之宴", ("护像之宴", "因龙之宴", "契鳍之宴", "乏龙之宴", "妄羊之宴", "画龙之宴", "常驻战阵")),
    "series-score-attack": ("无限演武", ("无限演武",)),
    "series-haniwa": ("土俑嘉年华", ("闪火土机巨土俑", "奔雷土机巨土俑", "溢光强振巨土俑", "云水强振巨土俑",
                                      "宵暗直击巨土俑", "奔雷必杀巨土俑", "旋风必杀巨土俑", "闪火必杀巨土俑")),
    "series-combat-diver": ("狂热激战", ("活动版本",)),
    "series-empresses": ("女王讨伐", ("赤之女王", "青之女王", "金之女王", "碧之女王", "皓之女王", "墨之女王")),
    "series-annihilator": ("歼灭者讨伐战", ("活动版本",)),
    "series-kaleidoscope": ("摇曳的迷宫", ("火", "水", "雷", "风", "光", "暗", "培育素材", "宝物域")),
    "series-recollection": ("追忆试炼", ("追忆试炼",)),
    "series-trials": ("试炼", ("闪火试炼", "云水试炼", "奔雷试炼", "旋风试炼", "溢光试炼", "极时试炼")),
    "series-side-stories": ("外传故事", STORY_TITLES),
    "series-commemorative": ("官方纪念关卡", ("开服纪念", "周年纪念", "节日纪念", "特别纪念")),
    "series-holiday-lottery": ("节日抽奖活动", ("新年", "五一黄金周", "十一黄金周")),
    "series-special-training": ("鹄和凉月的特别训练", ("活动版本",)),
    "series-halloween": ("为你奏响的镇魂歌", ("活动与常驻",)),
    "series-christmas-battle": ("圣夜的淘气鬼", ("活动与常驻",)),
    "series-christmas-story": ("圣夜的骚乱者", ("活动版本",)),
    "series-collab-z": ("阻止暴走的罗梅罗", ("活动版本",)),
    "series-collab-r": ("异界漂泊谭", ("活动版本",)),
    "series-collab-g": ("Cross Blue", ("活动版本",)),
    "series-collab-u": ("摇曳彼方的新大门", ("活动版本",)),
    "series-eye-dragon": ("始龙之眼", ("活动与常驻",)),
    "series-ark-guardian": ("方舟守护者", ("常驻版本",)),
}
SERIES_VARIANTS = {identifier: value[1] for identifier, value in GROUPS.items()}


def group_fields(identifier, variant):
    title, variants = GROUPS[identifier]
    if variant not in variants:
        raise ValueError("副本变体不在已核实系列中")
    return {"seriesId": identifier, "seriesTitle": title, "variantLabel": variant}


def validate_series_fields(item):
    """Reject orphan fields, unknown groups and mislabeled known groups."""
    if not any(field in item for field in ("seriesId", "seriesTitle", "variantLabel")):
        return
    identifier, variant = item.get("seriesId"), item.get("variantLabel")
    if (not isinstance(identifier, str) or identifier not in GROUPS
            or not isinstance(variant, str) or variant not in SERIES_VARIANTS[identifier]):
        raise ValueError("副本系列或变体无效")
    if identifier not in LEGACY_GROUPS or "seriesTitle" in item:
        if item.get("seriesTitle") != GROUPS[identifier][0]:
            raise ValueError("副本系列标题与已核实定义不符")
