# -*- coding: utf-8 -*-
"""万圣四角色规格(复用 wf_seasonal7_specs.SeasonalSpec)。"""
from __future__ import annotations
import hw_env  # noqa
from wf_seasonal7_specs import ELEMENT_TOKENS, SeasonalSpec

BATCH_DIR = "work/character_packs/halloween-20261016"
REQUIRES_CLIENT_BASE = "1.4.220"


def _spec(key, cid, code, name, furigana, title, profile, leader, *, template_id, template_code,
          template_element, element, pf_type, stance, theme, backdrop):
    return SeasonalSpec(
        key=key, cid=cid, code=code, pkg_id=f"hw-{key}-20261016",
        workspace=f"work/character_packs/hw-{key}", template_id=template_id,
        template_code=template_code, template_element=template_element,
        template_identity=template_id, element=element, element_token=ELEMENT_TOKENS[element],
        rarity=5, pf_type=pf_type, stance=stance, identity=cid, theme=theme,
        texts={"name": name, "furigana": furigana, "title": title, "profile": profile,
               "leader": leader, "skill1": None, "desc1": None, "skill2": None, "desc2": None, "cv": None},
        backdrop_colors=backdrop, requires_client_base=REQUIRES_CLIENT_BASE, package_version="1.0.0")


SPECS = {s.key: s for s in (
    _spec("ludi", 139985, "lady_android_halloween", "露迪", "LUDI", "万圣第一的公主殿下",
          "在万圣节扮演起「公主殿下」的机人少女。她把悬浮音箱改造成了南瓜造型，"
          "一边分析着祭典文化，一边认真地学习如何当好一位任性的公主——虽然撒糖果的样子怎么看都很开心。",
          "南瓜公主的号令",
          template_id=231009, template_code="lady_android", template_element=2, element=2,
          pf_type=4, stance="Supporter", theme="万圣·雷·Fever外双形态技能辅助",
          backdrop=((214, 150, 60), (40, 26, 48))),
    _spec("momiya", 169985, "blade_witch_halloween", "莫弥亚", "MOMIYA", "猎魔人装束的魔法剑士",
          "换上猎魔人装束的魔法剑士。万圣节的夜晚魔物横行，她提着魔剑四处巡猎，"
          "顺手把南瓜魔物收作了帮手——据说吃掉它们的时候，剑上的魔力会变得格外锋利。",
          "猎魔之夜",
          template_id=161004, template_code="blade_witch", template_element=5, element=5,
          pf_type=4, stance="Attacker", theme="万圣·暗·协力球直击队长",
          backdrop=((120, 70, 150), (26, 20, 40))),
    _spec("seriol", 159985, "crystal_swordman_halloween", "塞里奥尔", "SAILIAOER", "别扭的吸血鬼伯爵",
          "被拉去扮演吸血鬼伯爵的结晶剑士。嘴上说着「无聊」，披风和红酒杯却准备得一丝不苟。"
          "结晶化的手臂在烛光下闪闪发亮，倒也颇有几分伯爵的威严。",
          "伯爵的晚宴",
          template_id=151033, template_code="crystal_swordman", template_element=4, element=4,
          pf_type=0, stance="Supporter", theme="万圣·光·PF满速辅助",
          backdrop=((176, 40, 56), (30, 18, 26))),
    _spec("recital", 149985, "lich_halloween", "瑞西塔尔", "RUIXITAER", "奇怪的杰克南瓜灯",
          "顶着南瓜灯头套的不死者老人。万圣节是他一年中最开心的日子，"
          "南瓜藤蔓随他的心意四处生长，把调皮的魔物们统统缠住——然后再分给孩子们满满的糖果。",
          "南瓜灯的守夜",
          template_id=341003, template_code="lich", template_element=3, element=3,
          pf_type=3, stance="Supporter", theme="万圣·风·技伤通用麻痹辅助",
          backdrop=((230, 120, 30), (24, 40, 26))),
)}


def get_spec(key: str) -> SeasonalSpec:
    return SPECS[key]


def all_keys():
    return list(SPECS)
