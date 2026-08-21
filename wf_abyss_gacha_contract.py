#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Immutable product contract for the always-visible custom abyss gacha."""
from __future__ import annotations

import zlib
from fractions import Fraction

import wf_abyss_gacha_pool as pool_contract


GACHA_ID = 990001
GACHA_KEY = str(GACHA_ID)
CODE_NAME = "cnmod_abyss_limited_gacha"
TITLE = "深渊限定扭蛋"
# 泳皇女EX（莉莉丝）, code_name resistance_princess_ex, thunder ★5.
SWIM_PRINCESS_EX_CHARACTER_ID = 139997
SWIM_PRINCESS_EX_NAME = "泳皇女EX（莉莉丝）"
CHARACTER_IDS = (
    129999, SWIM_PRINCESS_EX_CHARACTER_ID, 139998, 139999, 149998,
    149999, 169998, 169999, 179999,
)
# Pickups that draw normally but are never offered in the 250-point exchange.
NON_EXCHANGEABLE_CHARACTER_IDS = (SWIM_PRINCESS_EX_CHARACTER_ID,)
STANDARD_EXCHANGE_CHARACTER_IDS = (141129, 161141, 123001, 131182)
EXCHANGEABLE_CHARACTER_IDS = tuple(
    value for value in CHARACTER_IDS
    if value not in NON_EXCHANGEABLE_CHARACTER_IDS
)
SINGLE_TICKET_ID = 999013
TEN_TICKET_ID = 999014
STANDARD_POOL_DONOR_ID = "700004"

GACHA_MASTER_LOGICAL = "master/gacha/gacha.orderedmap"
FEATURE_LOGICAL = "master/gacha/gacha_feature_content.orderedmap"
CHARACTER_MASTER_LOGICAL = "master/character/character.orderedmap"
RICH_TEXT_MASTER_LOGICAL = "master/rich_text/rich_text_html.orderedmap"

RARITY_ODDS_ID = f"{CODE_NAME}_rarity"
CHARACTER_3_ODDS_ID = f"{CODE_NAME}_character_3"
CHARACTER_4_ODDS_ID = f"{CODE_NAME}_character_4"
CHARACTER_5_ODDS_ID = f"{CODE_NAME}_character_5"
RARITY_ODDS_LOGICAL = f"master/gacha_odds/{RARITY_ODDS_ID}.orderedmap"
CHARACTER_3_ODDS_LOGICAL = (
    f"master/gacha_odds/{CHARACTER_3_ODDS_ID}.orderedmap"
)
CHARACTER_4_ODDS_LOGICAL = (
    f"master/gacha_odds/{CHARACTER_4_ODDS_ID}.orderedmap"
)
CHARACTER_5_ODDS_LOGICAL = (
    f"master/gacha_odds/{CHARACTER_5_ODDS_ID}.orderedmap"
)

RICH_TEXT_ID = f"rich_text/{CODE_NAME}_note"
RICH_TEXT_BODY_LOGICAL = f"{RICH_TEXT_ID}.html.deflate"
LIST_BANNER_LOGICAL = f"dynamic/gacha_list_banner/{CODE_NAME}"
LIST_BANNER_PAYLOAD_LOGICAL = f"{LIST_BANNER_LOGICAL}.png"
TOP_BANNER_LOGICAL = f"dynamic/gacha_banner/{CODE_NAME}"
TOP_BANNER_PAYLOAD_LOGICAL = f"{TOP_BANNER_LOGICAL}.png"

START_DATE = "2020-12-31 12:00:00"
END_DATE = "2199-12-31 23:59:59"

OFFICIAL_57_CLIENT_ROW = (
    "fukubukuro_gacha_ny2021", "2021年福袋扭蛋", "97",
    "dynamic/gacha_list_banner/fukubukuro_gacha_ny2021", "2",
    "", "", "", "", "1", "4", "normal_rarity", "rich_text/gacha_note", "0",
    "new_character_pickup_28_character_3",
    "new_character_pickup_28_character_4",
    "new_character_pickup_28_character_5",
    "normal", "normal_guarantee", "false", "false", "false",
    "", "", "", "", "", "20065", "20064",
    "2020-12-31 12:00:00", "2023-12-31 11:59:59", "(None)", "false",
    "116", "117", "169", "170", "(None)", "false", "(None)", "(None)",
    "(None)", "(None)", "false", "false", "(None)", "false",
)
OFFICIAL_57_RUNTIME_NONPOOL = {
    "type": 0,
    "paymentType": 0,
    "pageKind": 2,
    "singleCost": 150,
    "multiCost": 1500,
    "discountCost": 50,
    "onceTicketItemId": 20065,
    "tenTicketItemId": 20064,
    "wildcardTicketAvailable": False,
    "rarityOddsId": "normal_rarity",
    "guaranteeRarity": 4,
    "rankRates": {"normal": [50, 250, 700], "multiGuarantee": [50, 950]},
    "movieName": "normal",
    "guaranteeMovieName": "normal_guarantee",
    "toUseOddsUpAsTrialReading": False,
    "canBeStartDashExchange": False,
    "startDate": "2020-12-31 12:00:00",
    "endDate": "2023-12-31 11:59:59",
    "name": "2021年福袋扭蛋",
}

COMMON_OUTPUT_PATHS = (
    GACHA_MASTER_LOGICAL,
    FEATURE_LOGICAL,
    RARITY_ODDS_LOGICAL,
    CHARACTER_3_ODDS_LOGICAL,
    CHARACTER_4_ODDS_LOGICAL,
    CHARACTER_5_ODDS_LOGICAL,
    RICH_TEXT_MASTER_LOGICAL,
    RICH_TEXT_BODY_LOGICAL,
)
SERVER_OUTPUT_PATHS = (
    "gacha.json",
    "cdndata/gacha.json",
    "cdndata/gacha_feature_content.json",
)
NEW_COMMON_PATHS = (
    RARITY_ODDS_LOGICAL,
    CHARACTER_3_ODDS_LOGICAL,
    CHARACTER_4_ODDS_LOGICAL,
    CHARACTER_5_ODDS_LOGICAL,
    RICH_TEXT_BODY_LOGICAL,
)


def build_gacha_master_row() -> list[str]:
    """Return the exact 47-column client row, based on official gacha 57."""
    return [
        CODE_NAME, TITLE, "100", LIST_BANNER_LOGICAL, "2",
        "", "", "", "",
        "1", "4", RARITY_ODDS_ID, RICH_TEXT_ID, "0",
        CHARACTER_3_ODDS_ID, CHARACTER_4_ODDS_ID, CHARACTER_5_ODDS_ID,
        "normal", "normal_guarantee", "false", "false", "false",
        "", "", "", "", "", str(SINGLE_TICKET_ID), str(TEN_TICKET_ID),
        START_DATE, END_DATE, "(None)", "false", "116", "117", "169", "170",
        "(None)", "false", "(None)", "(None)", "(None)", "(None)",
        "false", "true", "(None)", "false",
    ]


def build_feature_cells() -> list[str]:
    """Mirror official ticket pages with a static kind-1 top banner."""
    return [
        "1", TOP_BANNER_LOGICAL, "",
        "", "", "", "(None)", "", "",
    ]


def build_rarity_odds_rows() -> dict[str, str]:
    return {"0": "5,50", "1": "4,250", "2": "3,700"}


def build_runtime_pool(donor_runtime: object) -> dict[str, list[dict[str, object]]]:
    return pool_contract.build_pickup_pool(
        donor_runtime,
        CHARACTER_IDS,
        STANDARD_EXCHANGE_CHARACTER_IDS,
        NON_EXCHANGEABLE_CHARACTER_IDS,
    )


def build_character_odds_rows(
    rarity: int, runtime_pool: dict[str, list[dict[str, object]]]
) -> dict[str, str]:
    return pool_contract.build_character_rows(runtime_pool, rarity)


def build_server_runtime(
    runtime_pool: dict[str, list[dict[str, object]]]
) -> dict:
    return {
        "type": 0,
        "paymentType": 0,
        "pageKind": 2,
        "singleCost": 150,
        "multiCost": 1500,
        "discountCost": 50,
        "onceTicketItemId": SINGLE_TICKET_ID,
        "tenTicketItemId": TEN_TICKET_ID,
        "wildcardTicketAvailable": False,
        "rarityOddsId": RARITY_ODDS_ID,
        "guaranteeRarity": 4,
        "rankRates": pool_contract.STANDARD_RANK_RATES,
        "movieName": "normal",
        "guaranteeMovieName": "normal_guarantee",
        "toUseOddsUpAsTrialReading": False,
        "canBeStartDashExchange": False,
        "startDate": START_DATE,
        "endDate": END_DATE,
        "name": TITLE,
        "pool": runtime_pool,
    }


def build_rich_text_body() -> bytes:
    pickup_count = len(CHARACTER_IDS)
    exchangeable_count = len(EXCHANGEABLE_CHARACTER_IDS)
    rank_rates = pool_contract.STANDARD_RANK_RATES["normal"]
    five_percent = 100 * Fraction(rank_rates[0], sum(rank_rates))
    pickup_percent = 100 * pool_contract.PICKUP_TOTAL_RATE
    each_percent = float(100 * pool_contract.PICKUP_EACH_RATE)
    standard_percent = five_percent - pickup_percent
    locked_names = "、".join(
        SWIM_PRINCESS_EX_NAME if value == SWIM_PRINCESS_EX_CHARACTER_ID
        else str(value)
        for value in NON_EXCHANGEABLE_CHARACTER_IDS
    )
    standard_exchange = "、".join(
        str(value) for value in STANDARD_EXCHANGE_CHARACTER_IDS
    )
    html = f"""<!DOCTYPE html/>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <title>深渊限定扭蛋注意事项</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body class="body" style_id="1">
  <div class="container">
    <p>・本扭蛋长期开放，仅可使用深渊单抽券或深渊十连券抽取。</p><br/>
    <p>・本扭蛋不接受星导石或付费星导石抽取。</p><br/>
    <p>・本扭蛋不接受通用角色扭蛋券。</p><br/>
    <p>・★5角色总出现概率为5%，★4角色为25%，★3角色为70%。</p><br/>
    <p>・{pickup_count}名深渊限定角色合计出现概率为{pickup_percent}%，\
单人均为1/{pickup_count}%（约{each_percent:.3f}%）；\
其余{standard_percent}%由普通★5角色均分。</p><br/>
    <p>・使用1张深渊单抽券可抽取1次；使用1张深渊十连券可连续抽取10次。</p><br/>
    <p>・每次抽取累计1点兑换点数；其中{exchangeable_count}名深渊限定角色各需250点兑换。</p><br/>
    <p>・{locked_names}不可用兑换点数兑换，仅能通过抽取获得。</p><br/>
    <p>・{standard_exchange}四名普通★5角色同样各需250点兑换。</p><br/>
    <p>・重复获得已有角色时，按游戏现有角色重复获得规则处理。</p>
  </div>
</body>
</html>
"""
    compressor = zlib.compressobj(level=9, wbits=-15)
    raw = html.encode("utf-8")
    return compressor.compress(raw) + compressor.flush()


__all__ = [name for name in globals() if name.isupper() or name.startswith("build_")]
