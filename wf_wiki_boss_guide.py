"""Export the current five-boss guide after checking its live data and programs."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import wf_five_boss_v2 as builder
from wf_wiki_catalog_source import WikiSource
from wf_wiki_equipment_helpers import cell, nested
from wf_wiki_boss_text import affix_texts, enemy_conditions, reward_text

ELEMENTS = {1: "火", 2: "水", 3: "雷", 4: "风", 5: "光", 6: "暗", 0: "无"}
HP_CURVE = "master/battle/enemy/hp/hit_hp_correction_curve.orderedmap"


def require(condition, message):
    if not condition:
        raise ValueError("五重决战配置与当前生效数据不符：" + message)


def verify_affixes(source, params):
    for key, tree in builder.affix_library(params).items():
        path = builder.affix_program(key) + ".action.dsl.amf3.deflate"
        require(source.tree(path) == tree, "战场机制已变化，请更新攻略")


def verify_trials(source, boss):
    routine = boss.get("routine")
    if not routine:
        return []
    tiers = nested(source, builder.T_GBS).get(routine["out"], {})
    require(bool(tiers), "试炼状态缺失")
    descriptions = []
    for states in tiers.values():
        for state, cfg in routine["trials"].items():
            row = builder.one_row(states.get(state, ""))
            require(len(row) >= 48 and row[22] == builder.TRIAL_KINDS[cfg["kind"]]
                    and row[23] == str(cfg["count"]) and row[24] == "true"
                    and row[29] == "12" and row[47] == str(cfg["frames"]), "试炼门槛变化")
            kind = {"skill": "技能命中", "pf": "强化弹射命中", "direct": "直接攻击命中"}[cfg["kind"]]
            text = f"蓄力试炼：{cfg['frames'] / 60:g} 秒内达成 {cfg['count']} 次{kind}，成功则跳过对应大招。"
            if text not in descriptions:
                descriptions.append(text)
    return descriptions


def build_boss_guide(repo: Path, media, source=None):
    repo = Path(repo)
    source = source or WikiSource(repo, media.store)
    tracked = {}

    def read(relative):
        raw = (repo / relative).read_bytes()
        tracked[relative] = hashlib.sha256(raw).hexdigest()
        return raw.decode("utf-8")

    spec_path = "mod-tools/five_boss_v2_spec.json"
    read(spec_path)
    spec = builder.load_spec(repo / spec_path)
    config = json.loads(read("modes.d/five-boss-gauntlet.config.json"))
    rewards = read("src/multi/five-boss/rewards.ts")
    for path in ("src/multi/five-boss/contract.ts", "src/multi/five-boss/battle-runtime.ts",
                 "src/multi/five-boss/solo-ledger.ts", "src/multi/five-boss/solo-rewards.ts",
                 "mod-tools/wf_five_boss_v2.py"):
        read(path)
    live = builder.Live(loader=source.raw)
    affixes = affix_texts(spec["affix_params"])
    verify_affixes(source, spec["affix_params"])
    curve = nested(source, HP_CURVE)
    expected_routes = {(a.quest, b.quest) for a in spec["_variants"] if a.round == "r0"
                       for b in spec["_variants"] if b.round == "r1"}
    group = builder.one_row(live.table(builder.T_BBG)[str(spec["entry_quest"])])
    route_ids = group[1].split(",")
    routes = live.table(builder.T_BBM)
    actual_routes = set()
    for route_id in route_ids:
        if int(route_id) != spec["fallback_map_id"]:
            row = builder.one_row(routes[route_id])
            actual_routes.add((int(row[11]), int(row[12])))
    require(actual_routes == expected_routes, "随机路线组合变化")
    stages = []
    unique_bosses = {}
    for variant in spec["_variants"]:
        round_data = spec["rounds"][variant.round]
        quest = builder.one_row(live.table(builder.T_BBQ)["1"]["99"][str(variant.quest - 1099000)])
        require(float(quest[111]) == spec["time_limit_frames"] and quest[106] == "80", "关卡等级或限时变化")
        require([float(v) for v in quest[97:100]] == round_data["hp_mult"], "关卡血量修正变化")
        require([float(v) for v in quest[100:103]] == round_data["atk_mult"], "关卡攻击修正变化")
        for index, (kind, value) in enumerate(variant.enemy_states):
            require(quest[74 + index * 2] == str(kind), "敌方耐性类型变化")
            if value is not None:
                require(float(quest[75 + index * 2]) == value, "敌方耐性数值变化")
        zones = live.table(builder.T_ZONE)[f"mod_fb2_zone_{variant.quest}"]
        waves = []
        for wave_index, wave in enumerate(variant.waves):
            zone = builder.one_row(zones[str(wave_index)])
            require(int(zone[22]) == variant.group_kind, "敌方出场顺序变化")
            bosses = []
            for slot, boss_slot in enumerate(wave):
                definition = spec["bosses"][boss_slot.alias]
                code = builder.clone_code(variant, boss_slot.alias, wave_index, slot)
                k1, i1, k2, i2 = builder.Z_BOSS_SLOTS[slot]
                require(zone[i1] == code and zone[i2] == code, "敌方阵容变化")
                tiers = builder.gb_tiers(live, code)
                row = tiers[builder.tier_for_level(tiers)]
                level = builder.one_row(live.table(builder.T_BL)[code])
                values = curve[level[4]]
                curve_level = min(int(v) for v in values if int(v) >= 80)
                actual_hp = 2250 * float(level[3]) * float(values[str(curve_level)]) * float(level[2])
                require(abs(actual_hp / 1e8 - boss_slot.hp_e8) < .001, "敌方生命值变化")
                expected = list(definition.get("signature", []))
                if variant.group_kind == 1 or slot == 0:
                    expected += variant.affixes + (variant.entry_affixes if wave_index == 0 else [])
                attached = builder.split_programs(row[109])
                actual = {a for a in attached if a.startswith(builder.affix_program(""))}
                require(actual == {builder.affix_program(a) for a in expected}, "敌方机制挂载变化")
                mechanics = [affixes[a] for a in definition.get("signature", [])]
                trial_text = verify_trials(source, definition)
                if definition.get("routine"):
                    require(row[42] == definition["routine"]["out"], "敌方试炼未挂载")
                boss = {"name": row[1], "element": ELEMENTS.get(int(row[0]), "未知"),
                        "hp": round(actual_hp), "hpText": f"{boss_slot.hp_e8:g} 亿",
                        "soloHp": round(actual_hp * .55), "soloHpText": f"{boss_slot.hp_e8 * .55:g} 亿",
                        "mechanics": mechanics, "trials": trial_text}
                bosses.append(boss)
                unique_bosses.setdefault(row[1], {"name": row[1], "element": boss["element"],
                                                   "mechanics": mechanics, "trials": trial_text})
            waves.append({"order": wave_index + 1, "simultaneous": variant.group_kind == 0,
                          "bosses": bosses})
        name = re.sub(r"::[^:]+::", "", quest[2]).strip()
        stages.append({"id": str(variant.quest), "name": name,
                       "round": 1 if variant.round == "r0" else 2,
                       "waves": waves, "affixes": [affixes[a] for a in variant.affixes],
                       "entryMechanics": [affixes[a] for a in variant.entry_affixes],
                       "enemyConditions": enemy_conditions(variant.enemy_states),
                       "timeLimitSeconds": spec["time_limit_frames"] // 60,
                       "feverCapacity": int(quest[108])})
    names = {key: cell(rows[0], 2) for key, rows in source.table(builder.T_ITEM).items() if rows}
    result = {
        "title": "五重决战 · 试炼回廊与深界王座",
        "summary": "第一场随机匹配九条试炼回廊之一，第二场随机匹配七条王座路线之一，共 63 种组合。回廊三王顺序出场；王座先战同屏双王，再迎战深界王。",
        "entry": {"enabled": config["enabled"], "soloAvailable": config["solo_entry"] == "allow",
                  "maxPlayers": 3, "questId": str(spec["entry_quest"]),
                  "ticketName": names["10000143"], "notes": [
                      "单人和三人联机均可进入；联机房间两分钟后可由 AI 补位。",
                      "入场凭证可选；无凭证可练习，但不计本模式通关奖励与首通。联机以房主凭证为准。",
                      "奖励倍率：全程手动 2 倍、AUTO 1 倍；只作用于注明倍率的奖励，单人中途开启 AUTO 也按 1 倍结算。"]},
        "stages": stages, "bosses": list(unique_bosses.values()), "rewards": reward_text(rewards, names),
        "notes": ["血量按当前敌方数据与等级曲线核验；多人血量为基准，原生单人模式为 55%。",
                  "每场限时 30 分钟；阵容、耐性与场地机制应一起查看。",
                  "试炼次数为命中次数，不能按技能施放次数计算。资料为静态数据与实现核对，不代表实战通关保证。"],
        "meta": {"sourceHashes": dict(source.live_hashes), "sourceMissing": sorted(source.missing),
                 "sourceFiles": tracked, "verifiedStages": len(stages), "verifiedLiveMechanisms": len(affixes)},
    }
    source.verify_unchanged()
    for relative, expected in tracked.items():
        require(hashlib.sha256((repo / relative).read_bytes()).hexdigest() == expected, "导出过程中源码发生变化")
    return result
