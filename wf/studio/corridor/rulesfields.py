"""Editable rules fields (rogue_corridor_v1.json) grouped for the balance pages.

Only paths listed here may be written by ``rules.set``; everything else in the rules file is
shown read-only (protocol/host/data_dir/revision constants, deprecated blocks, v3-fixed values).
Types: int, number, bool, enum, range (two ints), weights4 (four tier weights), int_list, element_rules.
"""
from __future__ import annotations

TIER4 = ["T1", "T2", "T3", "T4"]


def _f(path, label, kind, group, **extra):
    return {"path": path, "label": label, "type": kind, "group": group, **extra}


FIELDS = [
    # 生命与金币
    _f("/lives/max", "生命上限", "int", "economy", min=1, max=999),
    _f("/lives/start", "初始生命", "int", "economy", min=1, max=999),
    _f("/gold/start", "初始金币", "int", "economy", min=0, max=1000000),
    _f("/gold/battle", "普通战金币（区间）", "range", "economy"),
    _f("/gold/elite", "精英战金币（区间）", "range", "economy"),
    _f("/gold/boss", "首领战金币（区间）", "range", "economy"),
    _f("/gold/event_battle", "伏击战金币（区间）", "range", "economy"),
    _f("/gold/flawless_bonus", "无人阵亡额外金币", "int", "economy", min=0, max=1000000),
    _f("/rest/heal", "休息回复生命", "int", "economy", min=0, max=999),
    # 商店
    _f("/shop/characters", "角色货架数", "int", "shop", min=0, max=12),
    _f("/shop/weapons", "武器货架数", "int", "shop", min=0, max=12),
    _f("/shop/relics", "遗物货架数", "int", "shop", min=0, max=12),
    _f("/shop/souls", "魂珠货架数", "int", "shop", min=0, max=12),
    _f("/shop/half_price_items", "半价商品数", "int", "shop", min=0, max=12),
    *[_f(f"/shop/character_prices/{t}", f"角色价 · {n}", "int", "shop", min=0, max=1000000)
      for t, n in (("1", "普通"), ("2", "稀有"), ("3", "传说"), ("4", "强化传说"))],
    *[_f(f"/shop/weapon_prices/{t}", f"武器价 · {n}", "int", "shop", min=0, max=1000000)
      for t, n in (("1", "普通"), ("2", "稀有"), ("3", "史诗"), ("4", "传说"))],
    *[_f(f"/shop/relic_prices/{r}", f"遗物价 · {n}", "int", "shop", min=0, max=1000000)
      for r, n in (("common", "普通"), ("rare", "稀有"), ("boss", "首领"))],
    _f("/shop/soul_price", "魂珠价", "int", "shop", min=0, max=1000000),
    _f("/shop/extract_soul_price", "提取魂珠价", "int", "shop", min=0, max=1000000),
    _f("/shop/level_up_base", "强化基础价（角色/武器共用）", "int", "shop", min=0, max=1000000,
       hint="服务：角色强化与武器强化共用「基础价 + 已购次数×增量」"),
    _f("/shop/level_up_increment", "强化每次加价", "int", "shop", min=0, max=1000000),
    _f("/shop/heal_amount", "治疗服务回复", "int", "shop", min=0, max=1000000),
    _f("/shop/heal_price", "治疗服务价", "int", "shop", min=0, max=1000000),
    _f("/shop/refresh_price", "刷新货架价", "int", "shop", min=0, max=1000000),
    _f("/shop/character_element_rules", "角色货架属性规则（逐格）", "element_rules", "shop"),
    # 奖励
    _f("/rewards/battle_step_weights/character", "普通战奖励：角色权重", "number", "rewards", min=0, max=1000000),
    _f("/rewards/battle_step_weights/weapon", "普通战奖励：武器权重", "number", "rewards", min=0, max=1000000),
    _f("/rewards/tier_weights_by_floor", "分层四档权重", "tier_bands", "rewards", labels=TIER4),
    _f("/rewards/tier_weights_chest_boss", "宝箱/首领四档权重", "weights4", "rewards", labels=TIER4),
    _f("/rewards/elite_tier_shift", "精英档位上移", "int", "rewards", min=0, max=3),
    _f("/rewards/pity/after", "保底：连续几次", "int", "rewards", min=1, max=100),
    _f("/rewards/pity/tier", "保底：至少档位", "int", "rewards", min=1, max=4),
    *[_f(f"/rewards/relic_rarity_weights/{src}/{r}", f"遗物稀有度 · {sn} · {rn}", "number", "rewards", min=0, max=1000000,
         optional=True)
      for src, sn in (("elite", "精英"), ("chest", "宝箱"), ("boss", "首领"), ("event", "事件"), ("shop", "商店"))
      for r, rn in (("common", "普通"), ("rare", "稀有"), ("boss", "首领"))],
    _f("/rewards/elite_relic_choices", "精英遗物选项数", "int", "rewards", min=0, max=6),
    _f("/rewards/chest_relic_choices", "宝箱遗物选项数", "int", "rewards", min=0, max=6),
    _f("/rewards/boss_relic_choices", "首领遗物选项数", "int", "rewards", min=0, max=6),
    _f("/rewards/event_battle_relic_choices", "伏击遗物选项数", "int", "rewards", min=0, max=6),
    _f("/rewards/max_enhanced_per_offer", "每组最多强化传说", "int", "rewards", min=0, max=1),
    _f("/rewards/start_element_weight", "角色卡：开局属性概率", "number", "rewards", min=0, max=1),
    _f("/rewards/chest_weapon_chance", "宝箱追加武器概率", "number", "rewards", min=0, max=1),
    _f("/rewards/elite_soul_chance", "精英额外魂珠概率", "number", "rewards", min=0, max=1),
    _f("/rewards/weapon_element_weights/preferred", "武器：偏好属性权重", "number", "rewards", min=0, max=1000000),
    _f("/rewards/weapon_element_weights/other", "武器：其他属性权重", "number", "rewards", min=0, max=1000000),
    _f("/rewards/character_element_rules", "角色奖励属性规则（逐卡）", "element_rules", "rewards"),
    # 地图
    *[_f(f"/map/acts/{i}/weights/{k}", f"第{i + 1}幕 · {kn}权重", "number", "map", min=0, max=1000000, optional=True)
      for i in range(3) for k, kn in (("battle", "战斗"), ("event", "事件"), ("elite", "精英"), ("rest", "休息"), ("shop", "商店"))],
    *[_f(f"/map/acts/{i}/encounter_ranks", f"第{i + 1}幕遭遇排名段", "range", "encounters") for i in range(3)],
    _f("/map/elite_min_floor", "精英最早层（幕内）", "int", "map", min=1, max=45),
    _f("/map/min_nodes", "每层最少节点", "int", "map", min=1, max=8),
    _f("/map/max_nodes", "每层最多节点", "int", "map", min=1, max=8),
    _f("/map/paths", "路径条数", "int", "map", min=2, max=12),
    _f("/map/between_act_recovery", "幕间恢复", "enum", "map", options=["none", "full"]),
    # 遭遇/首领
    _f("/encounters/exclude_rounds", "全局排除轮次", "int_list", "encounters"),
    _f("/encounters/boss_rounds", "首领轮次（需在宿主文件夹且不被排除）", "int_list", "encounters"),
    _f("/v3f/boss_elements/threshold", "首领属性无效阈值", "number", "encounters", min=0, max=0.99),
    _f("/v3f/boss_elements/exclude_act1", "第1幕跳过对开局属性无效的首领", "bool", "encounters"),
    _f("/v3f/boss_elements/boost_acts", "加权的幕", "int_list", "encounters"),
    _f("/v3f/boss_elements/effective_share", "有效属性合计概率下限", "number", "encounters", min=0, max=1),
    # 角色池（v3f 组级开关）
    _f("/v3f/boss_playable/enabled", "boss 转可玩角色进池", "bool", "pool"),
    _f("/v3f/boss_playable/min_act", "boss 转可玩最早出现幕", "int", "pool", min=1, max=3),
    # 难度
    _f("/difficulty/active_profile", "生效难度档", "enum", "difficulty", options=["test", "formal"],
       hint="test=试验倍率（默认 hp 0.001/atk 0.05）；formal=三幕目标曲线"),
    _f("/difficulty/profiles/test/hp", "测试档 HP 倍率", "number", "difficulty", min=0.0001, max=100),
    _f("/difficulty/profiles/test/atk", "测试档 ATK 倍率", "number", "difficulty", min=0.0001, max=100),
    *[_f(f"/difficulty/profiles/formal/act_targets/{i}", f"正式档 · 第{i + 1}幕目标 D", "number", "difficulty",
         min=0.0001, max=100) for i in range(3)],
    _f("/difficulty/profiles/formal/hp_exponent", "正式档 HP 指数 p", "number", "difficulty", min=0, max=2,
       hint="D=√(hp×atk)，hp=D^p，atk=D^(2−p)；相对所选原生遭遇，未标定实战耗时"),
]
BY_PATH = {f["path"]: f for f in FIELDS}
GROUPS = {"economy": "生命与金币", "shop": "商店", "rewards": "奖励", "map": "地图", "encounters": "遭遇/首领",
          "pool": "角色池", "difficulty": "难度"}


def get(rules: dict, path: str, default=None):
    node = rules
    for part in path.strip("/").split("/"):
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return default
    return node


def check_value(field: dict, value):
    """Shape check only; ranges and cross-field rules are reported by validation, not refused."""
    kind = field["type"]

    def is_num(v):
        return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")

    if kind == "int" and not (isinstance(value, int) and not isinstance(value, bool)):
        return "需要整数"
    if kind == "number" and not is_num(value):
        return "需要数字"
    if kind == "bool" and not isinstance(value, bool):
        return "需要布尔值"
    if kind == "enum" and value not in field["options"]:
        return "取值只能是 " + "/".join(field["options"])
    if kind == "range" and not (isinstance(value, list) and len(value) == 2 and all(isinstance(v, int) and not isinstance(v, bool) for v in value)):
        return "需要两个整数 [下限, 上限]"
    if kind == "weights4" and not (isinstance(value, list) and len(value) == 4 and all(is_num(v) for v in value)):
        return "需要 4 个数字"
    if kind == "int_list" and not (isinstance(value, list) and all(isinstance(v, int) and not isinstance(v, bool) for v in value)):
        return "需要整数列表"
    if kind == "tier_bands":
        if not isinstance(value, list) or not value:
            return "需要分段列表"
        for band in value:
            if not isinstance(band, dict) or set(band) - {"floors", "weights"}:
                return "每段只能有 floors 与 weights"
            if not (isinstance(band.get("floors"), list) and len(band["floors"]) == 2):
                return "floors 需要两个整数"
            if not (isinstance(band.get("weights"), list) and len(band["weights"]) == 4 and all(is_num(v) for v in band["weights"])):
                return "weights 需要 4 个数字"
    if kind == "element_rules":
        if not isinstance(value, list) or not value:
            return "需要规则列表"
        for rule in value:
            if rule in ("preferred", "secondary", "any"):
                continue
            if not isinstance(rule, dict) or not all(k in ("preferred", "secondary", "any") and is_num(v) for k, v in rule.items()):
                return "规则只能是 preferred/secondary/any 或其权重对象"
    return None


def view(rules: dict) -> list[dict]:
    return [{**f, "value": get(rules, f["path"]), "present": get(rules, f["path"], KeyError) is not KeyError}
            for f in FIELDS]
