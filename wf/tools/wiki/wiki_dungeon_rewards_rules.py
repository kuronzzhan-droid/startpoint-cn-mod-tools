"""Public reward projection of the copied gray runtime's quest settlement rules."""
from __future__ import annotations

import re


def percent(value):
    return f"{value * 100:.6g}%"


def scalar(value):
    return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)


def blank_quest(name, difficulty=""):
    return {"name": name, "difficulty": difficulty, "firstClear": [], "sPlus": [], "drops": [], "notes": []}


class QuestRewards:
    def __init__(self, assets, names):
        self.assets, self.names = assets, names
        self.clear = assets.get("clear_reward.json")
        self.score = assets.merged("score_reward.json", "score_reward_cnmod.json")
        self.rare = assets.merged("rare_score_reward.json", "rare_score_reward_cnmod.json")
        self.element = assets.get("reward_element_map.json")

    def regular(self, kind, quest_id, record, name):
        match = re.search(r"地狱级|超级\+?|高级\+?|中级|初级", name)
        out = blank_quest(name, record.get("_wikiDifficulty") or (match[0] if match else ""))
        if kind == "rush" and quest_id == "700100099":
            out["notes"].append("深渊 EX 无尽入口不结算常规关卡、首通、SS 或每轮掉落奖励。")
            return out
        for source, dest in (("clearRewardId", "firstClear"), ("sPlusRewardId", "sPlus")):
            reward = self.clear.get(str(record.get(source)))
            if reward:
                if kind == "expert_single" and dest == "sPlus":
                    reward = {"type": 0, "id": 14040, "count": 3}
                out[dest].append(self.names.raw_reward(reward))
        for field, reward_kind in (("manaReward", "mana"), ("poolExpReward", "exp")):
            if record.get(field, 0) > 0:
                out["drops"].append(self.names.reward(reward_kind, amount=record[field], probability="基础通关奖励"))
        group_id = str(record.get("scoreRewardGroupId"))
        for reward in self.score.get(group_id, []):
            if reward.get("type") == 0:
                raw = {**reward, "type": reward.get("reward_type")}
                if raw["type"] in (6, 7):
                    enemy = {0: 3, 1: 0, 2: 1, 3: 2, 4: 5, 5: 4}.get(record.get("element", 0), 3)
                    rows = self.element.get(str(raw["type"] - 5), {}).get(str(raw.get("id")), {}).get(str(enemy), [])
                    if not rows:
                        out["notes"].append("部分属性素材映射尚未对应。")
                        continue
                    raw = {**raw, "type": 0, "id": rows[0][0]}
                if quest_id == "1020004" and group_id == "209990" and raw.get("id") == 40193:
                    raw["count"] = "单人 1／协力 3"
                    note = "固定数量，不受掉落倍率或加倍影响"
                else:
                    note = "基础数量；加倍另计" if reward.get("ignore_drop_multiplier") else "基础数量；活动掉落倍率及加倍另计"
                out["drops"].append(self.names.raw_reward(raw, probability=note))
            elif reward.get("type") == 1:
                pool = self.rare.get(str(reward.get("id")), [])
                # Runtime uses randomInt(0,100)/100 <= rarity (inclusive), then uniform pool choice.
                rarity = float(reward.get("rarity", 0))
                chance = sum(rarity >= draw / 100 for draw in range(100)) / 100
                if quest_id == "1020004" and group_id == "209990" and reward.get("id") == 3099900:
                    chance = 0.01
                for entry in pool:
                    out["drops"].append(self.names.raw_reward(entry, probability=
                        f"此奖池每次判定 {percent(chance)}；池内 {len(pool)} 项等概率抽 1 项"))
        return out


def range_text(value, fallback=1):
    if isinstance(value, list) and len(value) >= 2:
        return scalar(value[0]) if value[0] == value[1] else f"{scalar(value[0])}–{scalar(value[1])}"
    return scalar(value if isinstance(value, (int, float)) else fallback)


def rogue_round(names, config, round_number):
    out = []
    for row in config.get("per_round_drops", []):
        rounds = row.get("rounds")
        if rounds and not min(rounds[:2]) <= round_number <= max(rounds[:2]):
            continue
        if round_number in row.get("exclude_rounds", []):
            continue
        chance = row.get("chance")
        slots = max(0, int(row.get("slots", 1)))
        guaranteed = max(0, min(slots, int(row.get("guaranteed_slots", slots if chance is None else 0))))
        if isinstance(chance, dict):
            chance = chance["start"] + (round_number - chance.get("base_round", round_number)) * chance.get("per_round", 0)
        chance = max(0, min(1, chance or 0))
        count = max(1, row.get("count", 1))
        minimum, maximum = guaranteed * count, (slots if chance else guaranteed) * count
        if maximum <= 0:
            continue
        if chance == 1:
            minimum = maximum
        amount = range_text([minimum, maximum])
        note = "每轮固定掉落" if minimum == maximum else f"{guaranteed} 槽必得，其余 {slots - guaranteed} 槽各独立 {percent(chance)}"
        out.append(names.reward(row["type"], row["id"], amount, note))
    draws = max(0, int(config.get("pool_draws", 0)))
    if draws:
        for row in config.get("drop_pool", []):
            note = f"每轮随机池抽 {draws} 次；该项权重 {row.get('weight', 1)}"
            if config.get("match_party_element", True):
                note += "，按队伍属性筛选候选"
            if config.get("guarantee_weapon", True):
                note += "，首抽优先武器"
            out.append(names.reward(row["type"], row["id"], max(1, row.get("count", 1)), note))
    return out


def folder_rewards(names, assets, event_id, config):
    folders = assets.get("rush_event_quest_folder.json").get(event_id, {})
    if not folders and event_id.isdigit() and 700010 <= int(event_id) <= 700019:
        folders = assets.get("rush_event_quest_folder.json").get(str(int(event_id) - 10), {})
    if config and not folders:
        folders = {"1": []}
    result = []
    for folder, rewards in folders.items():
        if event_id in ("700099", "700100") and folder != "1":
            continue
        out = blank_quest("连战全通奖励" if config else f"第 {folder} 组连战全通奖励")
        out["drops"] = [names.raw_reward(row, probability="完成整组连战后结算") for row in rewards]
        for row in config.get("folder_clear_chance", []):
            out["drops"].append(names.raw_reward(row, probability=f"全通独立判定 {percent(row['chance'])}"))
        for row in config.get("folder_clear_random", []):
            for raw_id in row.get("pool", []):
                out["drops"].append(names.raw_reward({**row, "id": raw_id, "count": range_text(row.get("count"))},
                    probability=f"全通 {percent(row.get('chance', 1))} 进入此池；不重复抽 {range_text(row.get('pick'), len(row['pool']))} 项"))
        if out["drops"]:
            result.append(out)
    return result
