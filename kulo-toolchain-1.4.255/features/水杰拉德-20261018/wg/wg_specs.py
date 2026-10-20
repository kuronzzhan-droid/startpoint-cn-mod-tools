# -*- coding: utf-8 -*-
"""水杰拉德规格(复用 wf_seasonal7_specs.SeasonalSpec)。母本=拉绮夏 121007(★5 水 辅助 强化弹射类型 3)。"""
from __future__ import annotations
import wg_env  # noqa
from wf_seasonal7_specs import ELEMENT_TOKENS, SeasonalSpec

BATCH_DIR = "work/character_packs/water-gerald-20261018"
REQUIRES_CLIENT_BASE = "1.4.238"


def _spec(key, cid, code, name, furigana, title, profile, leader, *, template_id, template_code,
          template_element, element, pf_type, stance, theme, backdrop):
    return SeasonalSpec(
        key=key, cid=cid, code=code, pkg_id=f"wg-{key}-20261018",
        workspace=f"work/character_packs/wg-{key}", template_id=template_id,
        template_code=template_code, template_element=template_element,
        template_identity=template_id, element=element, element_token=ELEMENT_TOKENS[element],
        rarity=5, pf_type=pf_type, stance=stance, identity=cid, theme=theme,
        texts={"name": name, "furigana": furigana, "title": title, "profile": profile,
               "leader": leader, "skill1": None, "desc1": None, "skill2": None, "desc2": None, "cv": None},
        backdrop_colors=backdrop, requires_client_base=REQUIRES_CLIENT_BASE, package_version="1.0.0")


SPECS = {s.key: s for s in (
    _spec("aqua", 129989, "white_wolf_gerald_aqua", "杰拉德", "JIELADE", "雨后天台的白狼骑士",
          "穿越到人类世界、和罗卜同住的白狼骑士。换上现代的短夹克后依旧坐姿笔直，"
          "把看家当成岗哨、把奶茶当成配给。下雨的日子他会守在天台，用水的魔法替同伴挡下每一滴雨。",
          "潮汐守誓",
          template_id=121007, template_code="drawing_witch", template_element=1, element=1,
          pf_type=3, stance="Supporter", theme="现代·水·治疗护盾辅助",
          backdrop=((70, 140, 220), (16, 28, 52))),
)}


def get_spec(key: str) -> SeasonalSpec:
    return SPECS[key]


def all_keys():
    return list(SPECS)
