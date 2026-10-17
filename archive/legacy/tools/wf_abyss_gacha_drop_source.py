#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Strict custom client source for the abyss final-folder ticket drop."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import wf_mod_tool as core


LOGICAL_PATH = "master/quest/event/cnmod_rogue_event.orderedmap"
EVENT_KEY = "700099"
EXPECTED_REWARDS = (
    {"type": 0, "id": 999014, "count": 1, "chance": 0.05},
    {"type": 0, "id": 11003, "count": 1, "chance": 0.5},
)
EXPECTED_ROWS = (
    ("1", "0", "999014", "1", "0.05"),
    ("1", "0", "11003", "1", "0.5"),
)


def _server_rewards(server: Mapping[str, object]) -> list[object]:
    events = server.get("events") if isinstance(server, Mapping) else None
    event = events.get(EVENT_KEY) if isinstance(events, Mapping) else None
    rewards = event.get("folder_clear_chance") if isinstance(event, Mapping) else None
    if not isinstance(rewards, list):
        raise ValueError("server rogue mirror lacks 700099 folder_clear_chance")
    return rewards


def build_drop_source(server: Mapping[str, object]) -> bytes:
    rewards = _server_rewards(server)
    if len(rewards) != 2:
        raise ValueError("server rogue mirror must contain exactly two chance rewards")
    if tuple(rewards) != EXPECTED_REWARDS:
        raise ValueError("server rogue mirror rewards are not canonical or ordered")
    row = core.write_csv_lines([list(cells) for cells in EXPECTED_ROWS]).encode(
        "utf-8"
    )
    payload = core.build_orderedmap(core.OrderedMap(
        LOGICAL_PATH, [EVENT_KEY], [row], Path("<abyss-drop-source>")
    ))
    parse_drop_source(payload)
    return payload


def parse_drop_source(raw: bytes) -> dict[str, object]:
    try:
        keys, rows = core._strict_orderedmap_rows(  # type: ignore[attr-defined]
            raw, label=LOGICAL_PATH, compressed_rows=True
        )
    except ValueError as exc:
        raise ValueError(f"custom rogue source is malformed: {exc}") from exc
    if keys != [EVENT_KEY] or len(rows) != 1:
        raise ValueError("custom rogue source must contain exactly one 700099 row")
    try:
        csv_rows = core.read_csv_lines(rows[0].decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise ValueError("custom rogue source row must be UTF-8") from exc
    if tuple(tuple(row) for row in csv_rows) != EXPECTED_ROWS:
        raise ValueError(
            "custom rogue source rows are not canonical folder/type/id/count/chance"
        )
    return {
        "event_id": int(EVENT_KEY),
        "rewards": [
            {
                "folder_id": int(row[0]),
                "type": int(row[1]),
                "id": int(row[2]),
                "count": int(row[3]),
                "chance": float(row[4]),
            }
            for row in EXPECTED_ROWS
        ],
    }


def validate_drop_mirror(client_raw: bytes, server: Mapping[str, object]) -> None:
    client = parse_drop_source(client_raw)
    rewards = _server_rewards(server)
    if len(rewards) != 2 or tuple(rewards) != EXPECTED_REWARDS:
        raise ValueError("server rogue mirror is not canonical or ordered")
    expected_client_rewards = [
        {"folder_id": 1, **reward} for reward in EXPECTED_REWARDS
    ]
    if client != {
        "event_id": int(EVENT_KEY), "rewards": expected_client_rewards
    }:
        raise ValueError("custom rogue source fields drifted from the server mirror")


__all__ = [
    "LOGICAL_PATH", "EVENT_KEY", "EXPECTED_ROWS", "EXPECTED_REWARDS",
    "build_drop_source", "parse_drop_source", "validate_drop_mirror",
]
