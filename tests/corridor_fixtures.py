"""Synthetic 深渊回廊 runtime files for offline tests (no game data: invented IDs and names).

Shapes mirror the trial server's inputs (rogue_corridor_v1.json, rogue_pool_v3f.json, relics/events/
locales/encounter pool, schema_version=2 tier table, v3c soul catalog). Files are written with
CRLF + indent 2 like the real ones so byte-identical rebuilds are exercised.
"""
from __future__ import annotations

import json
from pathlib import Path

PLAYABLE = "非官方键且 code 含 _playable：boss/敌人转可玩变体。"


def write(path: Path, value, indent=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=indent) + "\n"
    path.write_bytes(text.replace("\n", "\r\n").encode("utf-8"))


def rules():
    w = {"battle": 45, "event": 22, "elite": 16, "rest": 12, "shop": 5}
    return {
        "_readme": "fixture", "version": 1, "protocol": "v1", "enabled": True,
        "host": {"event_id": 700110, "folder_id": 1}, "data_dir": "fixture-data", "owned_only": False,
        "missing_statistics_policy": "assume_all_fallen", "lives": {"max": 20, "start": 20},
        "gold": {"start": 99, "battle": [15, 25], "elite": [30, 40], "boss": [100, 100], "event_battle": [30, 40], "flawless_bonus": 10},
        "roster": {"max": None, "start_level": 80, "max_level": 100, "level_step": 20},
        "weapons": {"max_enhancement_step": 3, "max_enhancement_level": 120, "max_count": None},
        "start": {"leaders_per_element": 3, "leader_tier": 2, "support_count": 2, "support_tier": 1, "weapon_count": 3, "weapon_tier": 1},
        "map": {"floors": 45, "lanes": 4, "paths": 6, "min_nodes": 2, "max_nodes": 4, "max_attempts": 500, "boss_lane": 1,
                "fixed": {"1": "battle", "5": "chest", "8": "chest", "14": "rest"}, "weights": dict(w), "elite_min_floor": 5,
                "no_consecutive": ["elite", "rest", "shop"], "act_floors": 15, "between_act_recovery": "none",
                "acts": [{"encounter_ranks": [1, 10], "weights": dict(w)}, {"encounter_ranks": [10, 19], "weights": dict(w)},
                         {"encounter_ranks": [19, 28], "weights": dict(w)}]},
        "encounters": {"normal_slope": 1.5, "normal_offset": -0.5, "elite_round_bonus": 3, "boss_rounds": [29],
                       "boss_top_threat": 2, "exclude_rounds": [27, 30], "hint_penalty": 3, "near_window": 1},
        "preference": {"main_points": 2, "unison_points": 1, "decay": 0.8, "min_battles": 2},
        "rewards": {"choices": 3, "battle_step_weights": {"character": 60, "weapon": 40},
                    "tier_weights_by_floor": [{"floors": [1, 15], "weights": [50, 35, 14.9, 0.1]},
                                              {"floors": [16, 30], "weights": [30, 40, 29.5, 0.5]},
                                              {"floors": [31, 45], "weights": [20, 35, 44, 1]}],
                    "tier_weights_chest_boss": [10, 30, 59, 1], "elite_tier_shift": 0, "pity": {"after": 3, "tier": 3},
                    "character_element_rules": ["preferred", {"preferred": 70, "secondary": 30}, "any"],
                    "weapon_element_weights": {"preferred": 70, "other": 30},
                    "relic_rarity_weights": {"elite": {"common": 65, "rare": 35}, "chest": {"common": 50, "rare": 50},
                                             "boss": {"rare": 60, "boss": 40}, "event": {"common": 60, "rare": 40},
                                             "shop": {"common": 60, "rare": 40}},
                    "elite_relic_choices": 1, "chest_relic_choices": 3, "boss_relic_choices": 3, "event_battle_relic_choices": 1,
                    "max_enhanced_per_offer": 1, "start_element_weight": 0.7, "chest_weapon_chance": 0.35, "character_cards": 3,
                    "character_max_picks": 1, "elite_soul_chance": 0.35, "elite_character_rounds": 3},
        "shop": {"characters": 5, "weapons": 3, "relics": 3, "half_price_items": 1,
                 "character_element_rules": ["preferred", "any"],
                 "character_prices": {"1": 50, "2": 80, "3": 130, "4": 300}, "weapon_prices": {"1": 40, "2": 65, "3": 100, "4": 240},
                 "relic_prices": {"common": 100, "rare": 150, "boss": 220}, "level_up_base": 75, "level_up_increment": 25,
                 "heal_amount": 3, "heal_price": 75, "refresh_price": 30, "souls": 3, "soul_price": 45, "extract_soul_price": 45},
        "rest": {"heal": 6},
        "difficulty": {"enemy_scale": {"points": [{"floor": 1, "hp": 0.001, "atk": 0.05}, {"floor": 44, "hp": 0.001, "atk": 0.05}],
                                       "elite": {"hp_mult": 1, "atk_mult": 1}, "boss": {"hp": 0.001, "atk": 0.05},
                                       "ascension_step": {"hp": 0, "atk": 0}, "min": 0.0001, "max": 5},
                       "active_profile": "test",
                       "profiles": {"test": {"hp": 0.001, "atk": 0.05},
                                    "formal": {"act_targets": [1.0, 3.0, 10.0], "hp_exponent": 1.0, "formula": "fixture"}}},
        "relic_effect_aliases": {"_readme": "fixture"}, "event_effect_aliases": {"_readme": "fixture"},
        "debug": {"allow_seed_param": True}, "rules_revision": 3,
        "souls": {"guaranteed_chests_per_act": 2, "source": "rules_v3_metadata.json", "duplicates": False},
        "teams": {"count": 3, "allow_cross_team_duplicates": {"characters": True, "weapons": True, "souls": True}},
        "v3f": {"pool_file": "rogue_pool_v3f.json", "boss_playable": {"enabled": True, "min_act": 2},
                "boss_elements": {"threshold": 0.1, "exclude_act1": True, "boost_acts": [2, 3], "effective_share": 0.5}},
    }


def relics():
    return [
        {"relic_id": "r001", "name": "测试瓶", "rarity": "common", "desc": "获得时，生命上限+5。",
         "effect": {"type": "max_lives_bonus", "value": 5}, "name_key": "rogue.relic.r001.name", "desc_key": "rogue.relic.r001.desc"},
        {"relic_id": "r004", "name": "测试徽章", "rarity": "rare", "desc": "商店八折。",
         "effect": {"type": "shop_discount", "value": 0.8}, "name_key": "rogue.relic.r004.name", "desc_key": "rogue.relic.r004.desc"},
        {"relic_id": "r006", "name": "测试人偶", "rarity": "boss", "desc": "每场首个阵亡不扣生命，休息回复-1。",
         "effect": {"type": "ignore_first_death_per_battle", "value": {"free_deaths": 1, "penalty_type": "rest_heal_bonus", "penalty_value": -1}},
         "name_key": "rogue.relic.r006.name", "desc_key": "rogue.relic.r006.desc"},
        {"relic_id": "r007", "name": "测试锤", "rarity": "boss", "desc": "获得时金币+100，生命上限-3。",
         "effects": [{"type": "gold_on_pickup", "value": 100}, {"type": "max_lives_up", "value": -3}],
         "name_key": "rogue.relic.r007.name", "desc_key": "rogue.relic.r007.desc"},
        {"relic_id": "r103", "name": "测试线圈", "desc": "每50连击充能5%。", "rarity": "rare", "name_en": "Test Coil",
         "desc_en": "5% per 50 combos.", "effects": [{"type": "combo_recharge_pct", "value": 5, "scope": "party",
                                                       "runtime": "client_pending", "combo_threshold": 50}],
         "name_key": "rogue.relic.r103.name", "desc_key": "rogue.relic.r103.desc"},
        {"relic_id": "r120", "name": "测试储备", "desc": "获得150金币。", "rarity": "boss",
         "effects": [{"type": "gold_on_pickup", "value": 150}], "name_key": "rogue.relic.r120.name", "desc_key": "rogue.relic.r120.desc"},
    ]


def events():
    def opt(eid, i, label, effects, requires=None):
        o = {"label": label}
        if requires is not None:
            o["requires"] = requires
        o["effects"] = effects
        o["label_key"] = f"rogue.event.{eid}.option.{i}"
        return o
    return [
        {"event_id": "e001", "title": "测试契约", "text": "以血为代价。", "options": [
            opt("e001", 0, "签约", [{"type": "lose_lives", "value": 3}, {"type": "gain_relic", "value": {"rarity": "rare"}}]),
            opt("e001", 1, "离开", [{"type": "leave", "value": True}])],
         "title_key": "rogue.event.e001.title", "text_key": "rogue.event.e001.text"},
        {"event_id": "e002", "title": "测试铁匠", "text": "铁匠。", "options": [
            opt("e002", 0, "强化", [{"type": "enhance_weapon"}]),
            opt("e002", 1, "买武器", [{"type": "lose_gold", "value": 40}, {"type": "gain_weapon", "value": {"tier": "T2", "element": "preferred"}}],
                {"min_gold": 40}),
            opt("e002", 2, "离开", [{"type": "leave"}]),
            opt("e002", 3, "提取魂珠", [{"type": "extract_soul"}])],
         "title_key": "rogue.event.e002.title", "text_key": "rogue.event.e002.text"},
        {"event_id": "e004", "title": "测试赌局", "text": "赌一把。", "options": [
            opt("e004", 0, "押上", [{"type": "gamble_gold", "value": {"win_chance": 0.5, "win_multiplier": 2.0, "lose_multiplier": 0.5}}],
                {"min_gold": 2}),
            opt("e004", 1, "离开", [{"type": "leave", "value": True}])],
         "title_key": "rogue.event.e004.title", "text_key": "rogue.event.e004.text"},
        {"event_id": "e006", "title": "测试伏击", "text": "敌人。", "options": [
            opt("e006", 0, "迎战", [{"type": "fight_elite", "value": True}, {"type": "gain_relic", "value": {"rarity": "random"}}])],
         "title_key": "rogue.event.e006.title", "text_key": "rogue.event.e006.text"},
    ]


def locales(rs, es):
    zh, en = {}, {}
    for r in rs:
        zh[r["name_key"]], zh[r["desc_key"]] = r["name"], r["desc"]
        en[r["name_key"]], en[r["desc_key"]] = "EN " + r["relic_id"], "EN desc " + r["relic_id"]
    for e in es:
        zh[e["title_key"]], zh[e["text_key"]] = e["title"], e["text"]
        en[e["title_key"]], en[e["text_key"]] = "EN " + e["event_id"], "EN text"
        for o in e["options"]:
            zh[o["label_key"]] = o["label"]
            en[o["label_key"]] = "EN " + o["label_key"].rsplit(".", 1)[-1]
    return {"zh": zh, "en": en}


def encounter_pool():
    rounds = [r for r in range(1, 30) if r != 27]
    out = []
    for r in rounds:
        curses = [{"name": "测试诅咒", "effect": "火伤害降至1/10" if r == 10 else "能耐50%", "hard": False}]
        out.append({"quest_id": f"7001100{r:02d}", "round": r, "boss_codes": [], "element": (r % 6) + 1, "field": f"f{r}",
                    "curses": ["测试诅咒"], "threat": float(r), "kind_hint": "boss" if r == 29 else ("normal" if r < 5 else "elite"),
                    "mechanic_text": "测试遭遇", "curse_details": curses, "enemy_label": f"测试敌人{r}",
                    "source_quest_id": f"7000990{r:02d}"})
    return {"schema_version": 1, "meta": {"source_version": "9.9.9", "event_id": "700099", "folder": 1}, "encounters": out}


def tier_table():
    chars, weapons = [], []
    for el in range(1, 7):
        for i, tier in enumerate([1, 1, 1, 2, 2, 2, 3, 4]):
            cid = 900000 + el * 100 + i
            chars.append({"id": str(cid), "tier": tier, "element": el, "rarity": 4 + (tier > 1), "name": f"测试角色{cid}",
                          "code": f"test_{cid}", "official": True, "category": ["common", "rare", "legendary", "enhanced"][tier - 1],
                          "rule_tier": tier, "pool_check": {"ok": True, "reasons": []},
                          "starter_profile": {"role": "Attacker", "scores": {"skill": i, "direct": 0, "power_flip": 0}}})
        for i, tier in enumerate([1, 1, 2, 2]):
            wid = 8000000 + el * 100 + i
            weapons.append({"id": str(wid), "tier": tier, "element": el, "rarity": 4, "name": f"测试武器{wid}", "code": f"w_{wid}",
                            "official": True, "category": "common", "level_min": 1, "level_max": 5, "awakening_max": 4,
                            "enhancement_cap": 0, "pool_check": {"ok": True, "reasons": []}})
    excluded = [{"id": "990001", "tier": 4, "element": 1, "rarity": 5, "name": "测试首领甲", "code": "boss_a_playable", "official": False,
                 "category": "enhanced", "pool_check": {"ok": False, "reasons": [PLAYABLE]}},
                {"id": "990002", "tier": 2, "element": 2, "rarity": 5, "name": "测试排除乙", "code": "other_b", "official": True,
                 "category": "rare", "pool_check": {"ok": False, "reasons": ["资源缺失"]}}]
    pending = [{"id": "100001", "tier": 2, "element": None, "rarity": 5, "name": "测试通用武器", "code": "orb", "official": True,
                "category": "rare", "pool_check": {"ok": True, "reasons": []}}]
    return {"schema_version": 2, "meta": {"source_version": "9.9.9", "runtime_tested": False, "status": "fixture"},
            "characters": chars, "weapons": weapons, "weapons_pending_element_policy": pending,
            "excluded_characters": excluded, "excluded_weapons": []}


def soul_catalog(tt):
    souls = [{"ability_soul_id": int(w["id"]), "name": w["name"] + "的魂珠", "source_equipment_ids": [int(w["id"])], "level": 1,
              "level_max": 1, "upgradeable": False, "ability_power_mode": "MinimumLevel", "element": w["element"]} for w in tt["weapons"]]
    return {"schema_version": 3, "growth_revision": "v3c", "selected_version": "9.9.9",
            "equipment_to_soul": {w["id"]: int(w["id"]) for w in tt["weapons"]}, "souls": souls, "characters": {},
            "excluded_soul_weapons": []}


def pool_overlay():
    return {"boss_playable": {"category": "enhanced", "characters": [
        {"id": 990001, "element": 1, "code": "boss_a_playable", "name": "测试首领甲", "previous_exclusion": [PLAYABLE], "tier": 4,
         "mana": {"boards": {"1": []}, "has_awakening": False}, "official": False}]},
        "decision": "fixture", "rule_revision": "v3f", "schema_version": 1, "source": {},
        "tier_overrides": {"characters": {"900103": {"element": 1, "from_tier": 2, "name": "测试角色900103", "reason": "fixture", "tier": 3}},
                           "weapons": {}}}


def build(root: Path) -> dict:
    """Create data_dir + proto_server under ``root``; returns their paths."""
    data, proto = root / "data", root / "proto-server"
    rs, es = relics(), events()
    config = rules()
    config["data_dir"] = data.as_posix()
    write(proto / "src" / "rogue_corridor_v1.json", config)
    write(proto / "src" / "rogue_pool_v3f.json", pool_overlay(), indent=1)
    write(data / "relics.json", rs)
    write(data / "events.json", es)
    write(data / "tier_overrides.json", {"characters": {}, "weapons": {}})
    write(data / "locales_v3.json", locales(rs, es))
    write(data / "new-mode" / "encounter_pool.json", encounter_pool())
    tt = tier_table()
    write(data / "tier_table.json", tt)
    write(data / "rules_v3_metadata.json", soul_catalog(tt))
    return {"data": data, "proto": proto}
