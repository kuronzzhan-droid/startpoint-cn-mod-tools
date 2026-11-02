#!/usr/bin/env python3
"""Compile and audit the Deep Abyss 30-floor reward schedule.

This module is deliberately pure: callers pass decoded server JSON or raw
OrderedMap payloads and receive new values. It never publishes a patch or
touches a runtime mirror by itself.
"""
from __future__ import annotations

import copy
import csv
import io
from pathlib import Path
from typing import Any

import wf_mod_tool as core


EVENT_ID = 700099
EVENT_KEY = str(EVENT_ID)
TOKEN_ID = 2370099
SINGLE_TICKET_ID = 999013
TEN_TICKET_ID = 999014
ADDITIONAL_GROUP_ID = 237009900
FOLDER_LOGICAL = "master/quest/event/rush_event_quest_folder.orderedmap"
ADDITIONAL_LOGICAL = "master/reward/event/additional_reward.orderedmap"

FINAL_FIXED_REWARDS = (
    {"type": 0, "id": 99, "count": 1000},
    {"type": 0, "id": TOKEN_ID, "count": 100},
    {"type": 0, "id": 10002, "count": 2},
    {"type": 0, "id": 12001, "count": 2},
)
FINAL_CHANCE_REWARDS = (
    {"type": 0, "id": TEN_TICKET_ID, "count": 1, "chance": 0.10},
    {"type": 0, "id": 11003, "count": 1, "chance": 0.50},
)


def token_optional_chance(round_number: int) -> float:
    if 2 <= round_number <= 14:
        return 0.12 + (round_number - 2) * 0.03
    if round_number == 15:
        return 0.50
    if 16 <= round_number <= 29:
        return 0.51 + (round_number - 16) * 0.01
    return 0.0


def token_slots(round_number: int) -> tuple[int, int]:
    if round_number == 1:
        return 1, 1
    if 2 <= round_number <= 10:
        return 5, 3
    if 11 <= round_number <= 20:
        return 6, 4
    if 21 <= round_number <= 29:
        return 8, 5
    return 0, 0


def single_ticket_chance(round_number: int) -> float:
    if 1 <= round_number <= 29 and round_number % 5 != 0:
        return 0.01 + (round_number - 1) * 0.005
    return 0.0


def ten_ticket_chance(round_number: int) -> float:
    if round_number in (5, 10, 15, 20, 25):
        return round_number / 500.0
    if round_number == 30:
        return 0.10
    return 0.0


def expected_per_round_drops() -> list[dict[str, Any]]:
    common = {
        "type": "item",
        "count": 1,
        "additional_reward_group_id": ADDITIONAL_GROUP_ID,
    }
    token = {**common, "id": TOKEN_ID, "additional_reward_index_start": 1}
    ticket = {**common, "slots": 1, "guaranteed_slots": 0}
    return [
        {**token, "rounds": [1, 1], "slots": 1, "guaranteed_slots": 1},
        {**token, "rounds": [2, 10], "slots": 5, "guaranteed_slots": 3,
         "chance": {"start": 0.12, "per_round": 0.03, "base_round": 2}},
        {**token, "rounds": [11, 14], "slots": 6, "guaranteed_slots": 4,
         "chance": {"start": 0.39, "per_round": 0.03, "base_round": 11}},
        {**token, "rounds": [15, 15], "slots": 6, "guaranteed_slots": 4,
         "chance": 0.50},
        {**token, "rounds": [16, 20], "slots": 6, "guaranteed_slots": 4,
         "chance": {"start": 0.51, "per_round": 0.01, "base_round": 16}},
        {**token, "rounds": [21, 29], "slots": 8, "guaranteed_slots": 5,
         "chance": {"start": 0.56, "per_round": 0.01, "base_round": 21}},
        {**ticket, "id": SINGLE_TICKET_ID, "rounds": [1, 29],
         "chance": {"start": 0.01, "per_round": 0.005, "base_round": 1},
         "exclude_rounds": [5, 10, 15, 20, 25],
         "additional_reward_index_start": 9},
        *[
            {**ticket, "id": TEN_TICKET_ID, "rounds": [floor, floor],
             "chance": floor / 500.0, "additional_reward_index_start": 10}
            for floor in (5, 10, 15, 20, 25)
        ],
    ]


def build_rogue_event(source: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(source)
    event = result.get("events", {}).get(EVENT_KEY)
    if not isinstance(event, dict):
        raise ValueError(f"rogue_event 缺少 events.{EVENT_KEY}")
    event["per_round_drops"] = expected_per_round_drops()
    event["folder_clear_chance"] = [copy.deepcopy(row) for row in FINAL_CHANCE_REWARDS]
    validate_rogue_event(result)
    return result


def validate_rogue_event(source: dict[str, Any]) -> None:
    event = source.get("events", {}).get(EVENT_KEY)
    if not isinstance(event, dict):
        raise ValueError(f"rogue_event 缺少 events.{EVENT_KEY}")
    if event.get("per_round_drops") != expected_per_round_drops():
        raise ValueError("深渊逐层掉落表与定稿曲线不一致")
    if event.get("folder_clear_chance") != list(FINAL_CHANCE_REWARDS):
        raise ValueError("第30关概率奖励与定稿不一致")
    if token_optional_chance(15) != 0.50 or token_optional_chance(16) != 0.51:
        raise ValueError("代币概率拐点错误")
    if token_optional_chance(29) != 0.64:
        raise ValueError("第29关代币概率必须为64%")


def validate_rogue_event_extension(source: dict[str, Any]) -> None:
    event = source.get("events", {}).get(EVENT_KEY)
    if not isinstance(event, dict):
        raise ValueError(f"rogue_event_cnmod 缺少 events.{EVENT_KEY}")
    if event.get("folder_clear_chance") != [FINAL_CHANCE_REWARDS[0]]:
        raise ValueError("rogue_event_cnmod 第30关深渊十连券概率必须与主配置同为10%")


def build_server_folder(source: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(source)
    event = result.get(EVENT_KEY)
    if not isinstance(event, dict) or "1" not in event:
        raise ValueError("rush_event_quest_folder 缺少 700099/1")
    event["1"] = [copy.deepcopy(row) for row in FINAL_FIXED_REWARDS]
    validate_server_folder(result)
    return result


def validate_server_folder(source: dict[str, Any]) -> None:
    actual = source.get(EVENT_KEY, {}).get("1")
    if actual != list(FINAL_FIXED_REWARDS):
        raise ValueError(f"第30关固定奖励漂移: {actual!r}")


def _csv_cells(raw: bytes) -> list[str]:
    return next(csv.reader(io.StringIO(raw.decode("utf-8"))))


def _csv_raw(cells: list[str]) -> bytes:
    stream = io.StringIO()
    csv.writer(stream, lineterminator="").writerow(cells)
    return stream.getvalue().encode("utf-8")


def build_client_folder_payload(raw: bytes) -> bytes:
    outer = core.read_orderedmap_raw_rows_from_bytes(raw, FOLDER_LOGICAL)
    if EVENT_KEY not in outer.keys:
        raise ValueError("客户端 rush folder 缺少 700099")
    outer_pos = outer.keys.index(EVENT_KEY)
    inner_keys, inner_rows = core._strict_orderedmap_rows(
        outer.rows[outer_pos], label="deep-abyss-folder", compressed_rows=True
    )
    if "1" not in inner_keys:
        raise ValueError("客户端 rush folder 缺少 700099/1")
    row_pos = inner_keys.index("1")
    cells = _csv_cells(inner_rows[row_pos])
    if len(cells) != 37:
        raise ValueError(f"客户端 rush folder 行宽错误: {len(cells)}")
    for base in range(7, 37, 3):
        cells[base:base + 3] = ["(None)", "", "(None)"]
    fixed: list[str] = []
    for reward in FINAL_FIXED_REWARDS:
        fixed.extend((str(reward["type"]), str(reward["id"]), str(reward["count"])))
    cells[7:19] = fixed
    inner_rows[row_pos] = _csv_raw(cells)
    inner = core.OrderedMap(
        "<deep-abyss-folder>", inner_keys, inner_rows, Path("<memory>")
    )
    outer.rows[outer_pos] = core.build_orderedmap(inner)
    result = core.build_orderedmap_raw_rows(outer)
    validate_client_folder_payload(result)
    return result


def validate_client_folder_payload(raw: bytes) -> None:
    outer = core.read_orderedmap_raw_rows_from_bytes(raw, FOLDER_LOGICAL)
    outer_pos = outer.keys.index(EVENT_KEY)
    inner_keys, inner_rows = core._strict_orderedmap_rows(
        outer.rows[outer_pos], label="deep-abyss-folder", compressed_rows=True
    )
    cells = _csv_cells(inner_rows[inner_keys.index("1")])
    expected: list[str] = []
    for reward in FINAL_FIXED_REWARDS:
        expected.extend((str(reward["type"]), str(reward["id"]), str(reward["count"])))
    if cells[7:19] != expected:
        raise ValueError(f"客户端第30关奖励预览漂移: {cells[7:19]!r}")


def additional_reward_rows() -> dict[str, str]:
    rows = {
        str(index): f"abyss_token_slot_{index},0,{TOKEN_ID},5,1"
        for index in range(1, 9)
    }
    rows["9"] = f"abyss_single_ticket,0,{SINGLE_TICKET_ID},5,1"
    rows["10"] = f"abyss_ten_ticket,0,{TEN_TICKET_ID},5,1"
    return rows


def build_additional_reward_payload(raw: bytes) -> bytes:
    outer = core.read_orderedmap_raw_rows_from_bytes(raw, ADDITIONAL_LOGICAL)
    key = str(ADDITIONAL_GROUP_ID)
    rows = additional_reward_rows()
    inner = core.OrderedMap(
        "<deep-abyss-additional>", list(rows),
        [value.encode("utf-8") for value in rows.values()], Path("<memory>")
    )
    encoded = core.build_orderedmap(inner)
    if key in outer.keys:
        outer.rows[outer.keys.index(key)] = encoded
    else:
        outer.keys.append(key)
        outer.rows.append(encoded)
    result = core.build_orderedmap_raw_rows(outer)
    validate_additional_reward_payload(result)
    return result


def validate_additional_reward_payload(raw: bytes) -> None:
    outer = core.read_orderedmap_raw_rows_from_bytes(raw, ADDITIONAL_LOGICAL)
    key = str(ADDITIONAL_GROUP_ID)
    if key not in outer.keys:
        raise ValueError("客户端深渊逐层奖励组缺失")
    keys, rows = core._strict_orderedmap_rows(
        outer.rows[outer.keys.index(key)], label="deep-abyss-additional", compressed_rows=True
    )
    actual = {index: row.decode("utf-8") for index, row in zip(keys, rows)}
    if actual != additional_reward_rows():
        raise ValueError(f"客户端深渊逐层奖励组漂移: {actual!r}")


def probability_report() -> dict[str, Any]:
    floors = []
    guaranteed_total = 0
    optional_expected = 0.0
    for floor in range(1, 31):
        slots, guaranteed = token_slots(floor)
        chance = token_optional_chance(floor)
        optional = slots - guaranteed
        guaranteed_total += guaranteed
        optional_expected += optional * chance
        floors.append({
            "round": floor,
            "token_slots": slots,
            "guaranteed_token_slots": guaranteed,
            "optional_token_slots": optional,
            "optional_token_chance": chance,
            "single_ticket_chance": single_ticket_chance(floor),
            "ten_ticket_chance": ten_ticket_chance(floor),
        })
    return {
        "floors": floors,
        "token_before_final_guaranteed": guaranteed_total,
        "token_before_final_optional_expected": optional_expected,
        "token_final_fixed": 100,
        "token_full_run_minimum": guaranteed_total + 100,
        "token_full_run_maximum": 178 + 100,
        "token_full_run_expected": guaranteed_total + optional_expected + 100,
        "single_ticket_expected": sum(single_ticket_chance(floor) for floor in range(1, 30)),
        "ten_ticket_expected": sum(ten_ticket_chance(floor) for floor in range(1, 31)),
    }
