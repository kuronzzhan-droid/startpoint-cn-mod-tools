#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""深渊连战最终普通关十连券概率掉落的纯内存编译门禁。"""
from __future__ import annotations

import copy
from types import MappingProxyType
from typing import Mapping


EVENT_ID = 700099
EVENT_KEY = str(EVENT_ID)
FINAL_QUEST_ID = "700099030"
ENDLESS_QUEST_ID = "700099099"
LEGACY_TICKET_ID = 999001
TARGET_TICKET_ID = 999014
LEGACY_REWARD: Mapping[str, int | float] = MappingProxyType(
    {"type": 0, "id": LEGACY_TICKET_ID, "count": 1, "chance": 0.3}
)
TARGET_REWARD: Mapping[str, int | float] = MappingProxyType(
    {"type": 0, "id": TARGET_TICKET_ID, "count": 1, "chance": 0.05}
)


def _event_config(source: dict[str, object]) -> dict[str, object]:
    if not isinstance(source, dict):
        raise TypeError("rogue_event 必须是 dict")
    events = source.get("events")
    if not isinstance(events, dict):
        raise TypeError("rogue_event.events 必须是 dict")
    event = events.get(EVENT_KEY)
    if not isinstance(event, dict):
        raise TypeError(f"rogue_event.events[{EVENT_KEY}] 必须是 dict")
    chance = event.get("folder_clear_chance")
    if not isinstance(chance, list):
        raise TypeError(
            f"rogue_event.events[{EVENT_KEY}].folder_clear_chance 必须是 list"
        )
    return event


def _indices_for_id(entries: list[object], item_id: int) -> list[int]:
    return [
        index
        for index, entry in enumerate(entries)
        if isinstance(entry, dict) and entry.get("id") == item_id
    ]


def validate_final_normal_boundary(rush_event_quests: dict[str, object]) -> None:
    """证明 event 700099 只有普通 1..30 与无尽 099 两条运行时路径。"""
    if not isinstance(rush_event_quests, dict):
        raise TypeError("rush_event_quest 服务端镜像必须是 dict")

    final = rush_event_quests.get(FINAL_QUEST_ID)
    final_fields = (EVENT_ID, 1, 30)
    if not isinstance(final, dict) or tuple(
        final.get(field)
        for field in ("rushEventId", "rushEventFolderId", "rushEventRound")
    ) != final_fields:
        raise ValueError(
            f"{FINAL_QUEST_ID} 必须是 event {EVENT_ID}/folder 1/round 30"
        )

    expected_normal_ids = {
        str(700_099_000 + round_number): round_number
        for round_number in range(1, 31)
    }
    for quest_id, round_number in expected_normal_ids.items():
        row = rush_event_quests.get(quest_id)
        fields = (EVENT_ID, 1, round_number)
        if not isinstance(row, dict) or tuple(
            row.get(field)
            for field in ("rushEventId", "rushEventFolderId", "rushEventRound")
        ) != fields:
            raise ValueError(
                f"event {EVENT_ID} 普通关必须精确连续覆盖 folder 1/round 1..30; "
                f"坏行={quest_id}"
            )

    endless = rush_event_quests.get(ENDLESS_QUEST_ID)
    endless_fields = (EVENT_ID, 2, 0)
    if not isinstance(endless, dict) or tuple(
        endless.get(field)
        for field in ("rushEventId", "rushEventFolderId", "rushEventRound")
    ) != endless_fields:
        raise ValueError(
            f"{ENDLESS_QUEST_ID} 必须保持 event {EVENT_ID}/folder 2/round 0"
        )

    allowed_ids = set(expected_normal_ids) | {ENDLESS_QUEST_ID}
    extra_ids = sorted(
        quest_id
        for quest_id, row in rush_event_quests.items()
        if isinstance(row, dict)
        and row.get("rushEventId") == EVENT_ID
        and quest_id not in allowed_ids
    )
    if extra_ids:
        raise ValueError(
            f"event {EVENT_ID} 普通关必须只有 1..30; "
            f"存在额外普通/无尽路径,事件级掉落会越界: {extra_ids}"
        )


def build_final_ticket_drop(
    source: dict[str, object], rush_event_quests: dict[str, object]
) -> dict[str, object]:
    """把 30% 通用十连券原位替换为 5% 深渊十连券。"""
    validate_final_normal_boundary(rush_event_quests)
    event = _event_config(source)
    entries = event["folder_clear_chance"]
    legacy_indices = _indices_for_id(entries, LEGACY_TICKET_ID)
    target_indices = _indices_for_id(entries, TARGET_TICKET_ID)

    if legacy_indices and target_indices:
        raise ValueError("999001 与 999014 不得并存")
    if len(legacy_indices) > 1:
        raise ValueError("999001 概率奖励重复,拒绝猜测替换目标")
    if len(target_indices) > 1:
        raise ValueError("999014 概率奖励重复,拒绝视为幂等状态")

    if target_indices:
        target = entries[target_indices[0]]
        if target != dict(TARGET_REWARD):
            raise ValueError(f"999014 概率奖励漂移: {target!r}")
        return copy.deepcopy(source)

    if not legacy_indices:
        raise ValueError("缺少精确的 999001 旧概率奖励基线")
    legacy_index = legacy_indices[0]
    legacy = entries[legacy_index]
    if legacy != dict(LEGACY_REWARD):
        raise ValueError(f"999001 旧概率奖励漂移: {legacy!r}")

    result = copy.deepcopy(source)
    result["events"][EVENT_KEY]["folder_clear_chance"][legacy_index] = dict(
        TARGET_REWARD
    )
    validate_final_ticket_drop(result, rush_event_quests)
    return result


def validate_final_ticket_drop(
    source: dict[str, object], rush_event_quests: dict[str, object]
) -> None:
    """校验目标券唯一、旧券消失，以及 normal/endless 运行时边界。"""
    validate_final_normal_boundary(rush_event_quests)
    event = _event_config(source)
    entries = event["folder_clear_chance"]
    legacy_indices = _indices_for_id(entries, LEGACY_TICKET_ID)
    target_indices = _indices_for_id(entries, TARGET_TICKET_ID)
    if legacy_indices:
        raise ValueError("999001 旧通用十连券仍存在")
    if len(target_indices) != 1:
        raise ValueError(f"999014 深渊十连券必须恰好一条,实际 {len(target_indices)}")
    target = entries[target_indices[0]]
    if target != dict(TARGET_REWARD):
        raise ValueError(f"999014 概率奖励漂移: {target!r}")
