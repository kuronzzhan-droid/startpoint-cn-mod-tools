"""Port of the trial server's load-time config validation (rogue-corridor-v1.js validateConfig,
rogue-config-v3.js, rogue-rules-v3f.js validateConfig).

Any failure here makes the server refuse the whole config ("module inert"), so each one is a
publish blocker. The JS stops at the first failure; this port keeps going and reports them all.
"""
from __future__ import annotations

import math

RANDOM_KINDS = ("battle", "event", "elite", "rest", "shop")
NODE_KINDS = ("battle", "elite", "event", "shop", "rest", "chest", "boss")
RARITIES = ("common", "rare", "boss")


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and abs(v) <= 2 ** 53 - 1


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def check_rules(c: dict, host_rounds: list[int]) -> list[dict]:
    out: list[dict] = []

    def fail(path, message):
        out.append({"path": "/data/rules" + path, "message": message})

    def get(path, default=None):
        node = c
        for part in path.strip("/").split("/"):
            if isinstance(node, dict) and part in node:
                node = node[part]
            elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
                node = node[int(part)]
            else:
                return default
        return node

    def int_(path, lo, hi, name=None):
        v = get(path)
        if not _is_int(v) or v < lo or v > hi:
            fail(path, f"{name or path[1:].replace('/', '.')} 必须是 {lo}..{hi} 的整数（当前 {v!r}）")
            return None
        return v

    def num(path, lo, hi, name=None):
        v = get(path)
        if not _is_num(v) or v < lo or v > hi:
            fail(path, f"{name or path[1:].replace('/', '.')} 必须是 {lo}..{hi} 的数（当前 {v!r}）")
            return None
        return v

    def rng(path):
        v = get(path)
        if not isinstance(v, list) or len(v) != 2 or not all(_is_int(x) for x in v) or v[0] < 0 or v[0] > v[1]:
            fail(path, f"{path[1:].replace('/', '.')} 必须是 [下限, 上限]（含两端，下限≤上限）")

    if c.get("version") != 1 or c.get("protocol") != "v1":
        fail("/version", '配置必须是 "version": 1 与 "protocol": "v1"')
    if not isinstance(c.get("enabled"), bool) or not isinstance(c.get("owned_only"), bool):
        fail("/enabled", "enabled/owned_only 必须是布尔值")
    if not isinstance(c.get("data_dir"), str) or not c.get("data_dir"):
        fail("/data_dir", "data_dir 必须是路径")
    if c.get("missing_statistics_policy") not in ("assume_all_fallen", "assume_none_fallen"):
        fail("/missing_statistics_policy", "missing_statistics_policy 无效")
    if get("/host/event_id") != 700110 or get("/host/folder_id") != 1:
        fail("/host", "宿主必须是独立模式 700110/1（服务端硬编码）")
    lmax = int_("/lives/max", 1, 999)
    int_("/lives/start", 1, lmax if lmax else 999)
    int_("/gold/start", 0, 10 ** 6)
    for k in ("battle", "elite", "boss", "event_battle"):
        rng(f"/gold/{k}")
    int_("/gold/flawless_bonus", 0, 10 ** 6)
    if get("/roster/start_level") != 80 or get("/roster/max_level") != 100 or get("/roster/level_step") != 20:
        fail("/roster", "v3c 要求 Lv80 → Lv100 一次强化（start_level/max_level/level_step 固定 80/100/20）")
    int_("/weapons/max_enhancement_step", 1, 10)
    int_("/weapons/max_enhancement_level", 0, 999)
    num("/rewards/start_element_weight", 0, 1)
    num("/rewards/chest_weapon_chance", 0, 1)

    # rogue-config-v3.js
    m = c.get("map") or {}
    acts = m.get("acts")
    if c.get("rules_revision") != 3 or m.get("floors") != 45 or m.get("act_floors") != 15 or not isinstance(acts, list) or len(acts) != 3:
        fail("/map", "v3 要求三幕各 15 层（rules_revision=3, floors=45, act_floors=15, acts 三条）")
    if m.get("between_act_recovery") not in ("none", "full"):
        fail("/map/between_act_recovery", "between_act_recovery 只能是 none 或 full")
    for i, a in enumerate(acts if isinstance(acts, list) else []):
        r = a.get("encounter_ranks") if isinstance(a, dict) else None
        if not isinstance(r, list) or len(r) != 2 or not all(_is_int(x) for x in r) or r[0] < 1 or r[1] > 28 or r[1] - r[0] < 3:
            fail(f"/map/acts/{i}/encounter_ranks", f"第{i + 1}幕遭遇排名段无效（1 ≤ 下限，上限 ≤ 28，跨度 ≥ 3）")
        w = a.get("weights") if isinstance(a, dict) else None
        if (not isinstance(w, dict) or any(k not in RANDOM_KINDS for k in w) or not all(_is_num(v) and v >= 0 for v in w.values())
                or sum(v for v in w.values() if _is_num(v)) <= 0):
            fail(f"/map/acts/{i}/weights", f"第{i + 1}幕节点权重无效（只能是 {'/'.join(RANDOM_KINDS)}，非负且总和 > 0）")
    fixed = m.get("fixed") if isinstance(m.get("fixed"), dict) else {}
    if fixed.get("5") != "chest" or fixed.get("8") != "chest":
        fail("/map/fixed", "v3 魂珠保底要求每幕第 5、8 层固定宝箱")
    rw = c.get("rewards") or {}
    if rw.get("character_cards") != 3 or rw.get("character_max_picks") != 1 or rw.get("elite_character_rounds") != 3:
        fail("/rewards", "v3 角色奖励固定为三选一、精英三轮（character_cards=3, character_max_picks=1, elite_character_rounds=3）")
    num("/rewards/elite_soul_chance", 0, 1)
    for key in ("souls", "soul_price", "extract_soul_price"):
        v = get(f"/shop/{key}")
        if not _is_int(v) or v < 0:
            fail(f"/shop/{key}", f"shop.{key} 必须是非负整数")
    teams = c.get("teams") or {}
    dup = teams.get("allow_cross_team_duplicates") or {}
    if teams.get("count") != 3 or not all(isinstance(dup.get(k), bool) for k in ("characters", "weapons", "souls")):
        fail("/teams", "三队政策无效（count=3，三个布尔开关）")
    d = c.get("difficulty") or {}
    if d.get("active_profile") not in ("test", "formal"):
        fail("/difficulty/active_profile", "难度档只能是 test 或 formal")
    test = (d.get("profiles") or {}).get("test")
    if not isinstance(test, dict) or not all(_is_num(test.get(k)) and 0.0001 <= test.get(k) <= 100 for k in ("hp", "atk")):
        fail("/difficulty/profiles/test", "测试档 hp/atk 必须在 0.0001..100")
    formal = (d.get("profiles") or {}).get("formal")
    targets = formal.get("act_targets") if isinstance(formal, dict) else None
    if (not isinstance(targets, list) or len(targets) != 3 or not all(_is_num(v) and 0 < v <= 100 for v in targets)
            or not _is_num(formal.get("hp_exponent")) or not 0 <= formal.get("hp_exponent") <= 2):
        fail("/difficulty/profiles/formal", "正式档三幕目标须为 (0,100]，hp_exponent 0..2")

    # rogue-rules-v3f.js
    v = c.get("v3f")
    if not isinstance(v, dict) or not isinstance(v.get("pool_file"), str) or not v.get("pool_file"):
        fail("/v3f/pool_file", "v3f.pool_file 必填")
    else:
        bp, be = v.get("boss_playable"), v.get("boss_elements")
        n_acts = len(acts) if isinstance(acts, list) else 3
        if not isinstance(bp, dict) or not isinstance(bp.get("enabled"), bool) or not _is_int(bp.get("min_act")) or not 1 <= bp["min_act"] <= n_acts:
            fail("/v3f/boss_playable", "v3f.boss_playable 需要 enabled 布尔值与 min_act 1..幕数")
        if not isinstance(be, dict) or not _is_num(be.get("threshold")) or not 0 <= be["threshold"] < 1:
            fail("/v3f/boss_elements/threshold", "v3f.boss_elements.threshold 必须在 [0,1)")
        elif not isinstance(be.get("exclude_act1"), bool):
            fail("/v3f/boss_elements/exclude_act1", "exclude_act1 必须是布尔值")
        elif not isinstance(be.get("boost_acts"), list) or not all(_is_int(a) and 1 <= a <= n_acts for a in be["boost_acts"]):
            fail("/v3f/boss_elements/boost_acts", "boost_acts 无效")
        elif not _is_num(be.get("effective_share")) or not 0 <= be["effective_share"] <= 1:
            fail("/v3f/boss_elements/effective_share", "effective_share 必须在 0..1")

    if (c.get("weapons") or {}).get("max_count") is not None:
        int_("/weapons/max_count", 3, 100)
    st = c.get("start") or {}
    for k in ("leaders_per_element", "support_count", "weapon_count"):
        int_(f"/start/{k}", 1 if k == "leaders_per_element" else 0, 10)
    if _is_int(st.get("support_count")) and st["support_count"] > 2:
        fail("/start/support_count", "start.support_count 必须 ≤ 2")
    if _is_int(st.get("weapon_count")) and st["weapon_count"] > 3:
        fail("/start/weapon_count", "start.weapon_count 必须 ≤ 3")
    for k in ("leader_tier", "support_tier", "weapon_tier"):
        int_(f"/start/{k}", 1, 4)
    floors = int_("/map/floors", 3, 90)
    lanes = int_("/map/lanes", 2, 8)
    int_("/map/paths", 2, 12)
    mn = int_("/map/min_nodes", 1, lanes or 8)
    int_("/map/max_nodes", mn or 1, lanes or 8)
    int_("/map/max_attempts", 1, 100000)
    int_("/map/boss_lane", 0, (lanes or 8) - 1)
    int_("/map/elite_min_floor", 1, floors or 90)
    if not isinstance(m.get("fixed"), dict):
        fail("/map/fixed", "map.fixed 必须是对象")
    for f, kind in fixed.items():
        fl = int(f) if str(f).isdigit() else None
        if fl is None or fl < 1 or fl >= (floors or 45):
            fail("/map/fixed", f"map.fixed 层 {f} 超出 1..{(floors or 45) - 1}")
        if kind not in ("battle", "elite", "event", "shop", "rest", "chest"):
            fail("/map/fixed", f"map.fixed 类型 {kind} 无效")
    weights = m.get("weights")
    if not isinstance(weights, dict) or not weights:
        fail("/map/weights", "map.weights 必须是对象")
    else:
        for k, w in weights.items():
            if k not in RANDOM_KINDS:
                fail("/map/weights", f"map.weights 类型 {k} 无效")
            elif not _is_num(w) or not 0 <= w <= 10 ** 6:
                fail(f"/map/weights/{k}", f"map.weights.{k} 必须是 0..1000000")
    nc = m.get("no_consecutive")
    if not isinstance(nc, list) or not all(k in NODE_KINDS for k in nc):
        fail("/map/no_consecutive", "map.no_consecutive 无效")
    e = c.get("encounters") or {}
    num("/encounters/normal_slope", -10, 10)
    num("/encounters/normal_offset", -100, 100)
    int_("/encounters/elite_round_bonus", 0, 30)
    num("/encounters/hint_penalty", 0, 100)
    num("/encounters/near_window", 0, 30)
    boss_rounds, exclude = e.get("boss_rounds"), e.get("exclude_rounds")
    if not isinstance(boss_rounds, list) or not boss_rounds or not all(_is_int(x) for x in boss_rounds):
        fail("/encounters/boss_rounds", "encounters.boss_rounds 无效（非空整数列表）")
        boss_rounds = []
    if not isinstance(exclude, list) or not all(_is_int(x) for x in exclude):
        fail("/encounters/exclude_rounds", "encounters.exclude_rounds 无效")
        exclude = []
    if any(r in exclude for r in boss_rounds):
        fail("/encounters/boss_rounds", "首领轮次不能被排除（boss_rounds 与 exclude_rounds 有交集）——服务端会拒绝加载，等于回廊整体不可用")
    int_("/encounters/boss_top_threat", 0, 10)
    p = c.get("preference") or {}
    num("/preference/main_points", 0, 100)
    num("/preference/unison_points", 0, 100)
    num("/preference/decay", 0.01, 1)
    int_("/preference/min_battles", 0, 100)
    int_("/rewards/choices", 1, 6)
    int_("/rewards/max_enhanced_per_offer", 0, 1)

    def tier_weights(path):
        w = get(path)
        if not isinstance(w, list) or len(w) != 4 or not all(_is_num(x) and x >= 0 for x in w) or sum(w) <= 0:
            fail(path, f"{path[1:].replace('/', '.')} 必须是 4 个非负权重且总和 > 0")

    bands = rw.get("tier_weights_by_floor")
    if not isinstance(bands, list) or not bands:
        fail("/rewards/tier_weights_by_floor", "rewards.tier_weights_by_floor 无效")
        bands = []
    for i, band in enumerate(bands):
        if not isinstance(band, dict) or not isinstance(band.get("floors"), list) or len(band["floors"]) != 2 or not all(_is_int(x) for x in band["floors"]):
            fail(f"/rewards/tier_weights_by_floor/{i}/floors", f"第 {i + 1} 段的楼层区间无效")
        tier_weights(f"/rewards/tier_weights_by_floor/{i}/weights")
    good = [b for b in bands if isinstance(b, dict) and isinstance(b.get("floors"), list) and len(b["floors"]) == 2
            and all(_is_int(x) for x in b["floors"])]
    for f in range(1, (floors or 45) + 1):
        if not any(b["floors"][0] <= f <= b["floors"][1] for b in good):
            fail("/rewards/tier_weights_by_floor", f"分档权重没有覆盖第 {f} 层")
            break
    tier_weights("/rewards/tier_weights_chest_boss")
    int_("/rewards/elite_tier_shift", 0, 3)
    int_("/rewards/pity/after", 1, 100)
    int_("/rewards/pity/tier", 1, 4)

    def element_rules(path):
        rules = get(path)
        if not isinstance(rules, list) or not rules:
            fail(path, f"{path[1:].replace('/', '.')} 必须是列表")
            return
        for rule in rules:
            if rule in ("preferred", "secondary", "any"):
                continue
            if not isinstance(rule, dict) or not all(k in ("preferred", "secondary", "any") and _is_num(w) and w >= 0 for k, w in rule.items()):
                fail(path, f"{path[1:].replace('/', '.')} 的规则无效")
    element_rules("/rewards/character_element_rules")
    element_rules("/shop/character_element_rules")
    bsw = rw.get("battle_step_weights")
    if not isinstance(bsw, dict) or not all(k in ("character", "weapon") and _is_num(w) and w >= 0 for k, w in bsw.items()):
        fail("/rewards/battle_step_weights", "rewards.battle_step_weights 无效")
    wew = rw.get("weapon_element_weights")
    if not isinstance(wew, dict) or not _is_num(wew.get("preferred")) or not _is_num(wew.get("other")):
        fail("/rewards/weapon_element_weights", "rewards.weapon_element_weights 无效")
    for src in ("elite", "chest", "boss", "event", "shop"):
        w = (rw.get("relic_rarity_weights") or {}).get(src)
        if not isinstance(w, dict) or not all(k in RARITIES and _is_num(v) and v >= 0 for k, v in w.items()):
            fail(f"/rewards/relic_rarity_weights/{src}", f"rewards.relic_rarity_weights.{src} 无效")
    for k in ("elite_relic_choices", "chest_relic_choices", "boss_relic_choices", "event_battle_relic_choices"):
        int_(f"/rewards/{k}", 0, 6)
    s = c.get("shop") or {}
    for k in ("characters", "weapons", "relics", "half_price_items"):
        int_(f"/shop/{k}", 0, 12)
    for t in ("1", "2", "3", "4"):
        int_(f"/shop/character_prices/{t}", 0, 10 ** 6)
        int_(f"/shop/weapon_prices/{t}", 0, 10 ** 6)
    for t in RARITIES:
        int_(f"/shop/relic_prices/{t}", 0, 10 ** 6)
    for k in ("level_up_base", "level_up_increment", "heal_amount", "heal_price", "refresh_price"):
        int_(f"/shop/{k}", 0, 10 ** 6)
    int_("/rest/heal", 0, 999)
    es = d.get("enemy_scale")
    if not isinstance(es, dict):
        fail("/difficulty/enemy_scale", "difficulty.enemy_scale 必须是对象（已弃用但服务端仍校验）")
    else:
        lo = num("/difficulty/enemy_scale/min", 0.0001, 5)
        hi = num("/difficulty/enemy_scale/max", lo or 0.0001, 5)
        lo, hi = lo or 0.0001, hi or 5
        pts = es.get("points")
        if not isinstance(pts, list) or not pts:
            fail("/difficulty/enemy_scale/points", "enemy_scale.points 必须非空")
        else:
            prev = None
            for i, pt in enumerate(pts):
                int_(f"/difficulty/enemy_scale/points/{i}/floor", 1, (floors or 45) - 1)
                num(f"/difficulty/enemy_scale/points/{i}/hp", lo, hi)
                num(f"/difficulty/enemy_scale/points/{i}/atk", lo, hi)
                if prev is not None and isinstance(pt, dict) and _is_int(pt.get("floor")) and pt["floor"] <= prev:
                    fail("/difficulty/enemy_scale/points", "enemy_scale.points 楼层必须递增")
                prev = pt.get("floor") if isinstance(pt, dict) else prev
        num("/difficulty/enemy_scale/elite/hp_mult", 0.01, 100)
        num("/difficulty/enemy_scale/elite/atk_mult", 0.01, 100)
        num("/difficulty/enemy_scale/boss/hp", lo, hi)
        num("/difficulty/enemy_scale/boss/atk", lo, hi)
        num("/difficulty/enemy_scale/ascension_step/hp", 0, 10)
        num("/difficulty/enemy_scale/ascension_step/atk", 0, 10)
    if not isinstance(c.get("relic_effect_aliases"), dict) or not isinstance(c.get("event_effect_aliases"), dict):
        fail("/relic_effect_aliases", "*_effect_aliases 必须是对象")
    if not isinstance(c.get("debug"), dict) or not isinstance((c.get("debug") or {}).get("allow_seed_param"), bool):
        fail("/debug", "debug.allow_seed_param 必须是布尔值")
    # host folder: rounds present in the corridor encounter copy.
    if len(host_rounds) < 4:
        fail("/encounters", f"宿主文件夹只有 {len(host_rounds)} 轮")
    for b in boss_rounds:
        if b not in host_rounds:
            fail("/encounters/boss_rounds", f"首领轮次 {b} 不在宿主文件夹（700110/1）里")
    for b in exclude:
        if b < 1 or b > 30:
            fail("/encounters/exclude_rounds", f"排除轮次 {b} 超出 1..30")
    if len(host_rounds) - len(exclude) < 8:
        fail("/encounters/exclude_rounds", "排除后剩下不足 8 个遭遇")
    return out
