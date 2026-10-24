"""Verified special reward schedules and cumulative event-score rewards."""
from __future__ import annotations

import re

from wf_wiki_dungeon_rewards_rules import blank_quest
from wf_wiki_dungeon_rewards_schema import require


def fantasy_schedule(source):
    """Parse only the simple constants/itemSet reward declaration; never execute TS."""
    constants = {key: int(value) for key, value in re.findall(r"const (MODE15_[A-Z_]+) = (\d+);", source)}
    arrays = {key: [int(x) for x in values.split(",") if x.strip()] for key, values in
              re.findall(r"const ((?:ELEMENT|ETHER)_TIER_\d) = \[([\d, ]+)\] as const", source)}
    block = re.search(r"MODE15_SOLO_FIXED_REWARDS:[^=]+=(.*?)\n};", source, re.S)
    require(block is not None, "Fantasy reward declaration missing")
    stages = {}
    for match in re.finditer(r"^    (\d+): (.*?)(?=^    \d+:|\Z)", block[1], re.S | re.M):
        stage, expression = int(match[1]), match[2]
        rewards = []
        for name, count in re.findall(r"itemSet\(([A-Z_0-9]+), (\d+)\)", expression):
            require(name in arrays, "Unknown Fantasy reward group")
            rewards += [(raw_id, int(count)) for raw_id in arrays[name]]
        for name, count in re.findall(r"\{ id: (MODE15_[A-Z_]+), count: (\d+) \}", expression):
            require(name in constants, "Unknown Fantasy reward constant")
            rewards.append((constants[name], int(count)))
        stripped = re.sub(r"itemSet\([A-Z_0-9]+, \d+\)|\{ id: MODE15_[A-Z_]+, count: \d+ \}", "", expression)
        require(not stripped.translate(str.maketrans("", "", "[],. \r\n\t")), "Unsupported Fantasy reward expression")
        stages[stage] = rewards
    require(set(stages) == {1, 2, 3, 4, 6, 7, 8, 9, 11, 12, 13, 14}, "Fantasy stage schedule changed")
    return stages


def special_mode_rewards(names, gray_source):
    source = (gray_source / "lib/mode15.ts").read_text(encoding="utf-8-sig")
    schedule = fantasy_schedule(source)
    solo, multi = [], []
    for stage, rewards in schedule.items():
        quest = blank_quest(f"幻想连战 · 第 {stage} 轮固定奖励")
        quest["drops"] = [names.reward("item", raw_id, count, "每次成功通关") for raw_id, count in rewards]
        solo.append(quest)
    for stage, count in ((5, 5), (10, 10), (15, 20)):
        quest = blank_quest(f"幻想协力 · 第 {stage} 轮")
        quest["drops"] = [names.reward("item", 2370098, count, "成功通关／救援可得")]
        multi.append(quest)
    quest = blank_quest("幻想连战 · 完整通关额外奖励")
    quest["drops"] = [names.reward("item", raw_id, count, "完成本人整轮连战；救援不发此额外奖励")
                      for raw_id, count in ((99, 200), (2370097, 1), (10000143, 1))]
    solo.append(quest)
    multi.append(quest)
    five = blank_quest("五重决战 · 全部战胜后结算")
    five["firstClear"] = [names.reward("item", 10000146, 1)]
    five["drops"] = [names.reward("item", 10000144, 1, "每次通关独立 50%；不受手动倍率影响"),
                     names.reward("item", 10000145, "5／10", "基础 5；手动奖励倍率为 2 时 10"),
                     names.reward("item", 10000147, "1／2", "每次通关独立 25%；手动奖励倍率为 2 时 2")]
    return {"event-rush-700098": solo, "event-advent-300098": multi, "boss-1-99": [five]}


def score_rewards(assets, names, leaf_id, mapped):
    output = []
    if leaf_id.startswith("event-carnival-"):
        event_id = leaf_id.removeprefix("event-carnival-")
        kinds = {0: "item", 1: "equipment", 2: "beads", 3: "mana", 4: "exp", 6: "character", 7: "degree"}
        for _, score, rewards in assets.get("carnival_event_total_score_rewards.json").get(event_id, []):
            quest = blank_quest(f"累计最佳分数达到 {score:,}")
            quest["firstClear"] = [names.reward(kinds.get(kind, "unknown"), raw_id, count)
                                   for kind, raw_id, count in rewards]
            quest["notes"].append("此档累计积分奖励仅领取一次；奖励类型按灰服累计分数结算规则。")
            output.append(quest)
    if leaf_id.startswith("event-score-attack-"):
        tiers = assets.get("score_attack_border_reward.json")
        for _, _, record, title in mapped:
            key = f"{record.get('eventId')}_{record.get('scoreAttackQuestId')}"
            quest = blank_quest(f"{title} · 累计分数奖励")
            for tier in tiers.get(key, []):
                quest["firstClear"] += [names.reward("item", row["id"], row["amount"],
                    f"个人最高分首次达到 {tier['score']:,}") for row in tier["rewards"]]
            if quest["firstClear"]:
                quest["notes"].append("个人最高分首次跨过此档时领取一次。")
                output.append(quest)
    return output
