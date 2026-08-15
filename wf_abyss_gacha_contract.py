#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Immutable product contract for the custom abyss ticket-only gacha."""
from __future__ import annotations

import zlib


GACHA_ID = 990001
GACHA_KEY = str(GACHA_ID)
CODE_NAME = "cnmod_abyss_limited_gacha"
TITLE = "深渊限定扭蛋"
CHARACTER_IDS = (
    129999, 139998, 139999, 149998,
    149999, 169998, 169999, 179999,
)
SINGLE_TICKET_ID = 999013
TEN_TICKET_ID = 999014

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
TOP_BANNER_LOGICAL = f"dynamic/gacha_banner/{CODE_NAME}"

START_DATE = "2026-08-15 00:00:00"
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
        CODE_NAME, TITLE, "100", LIST_BANNER_LOGICAL, "2", "", "", "", "",
        "1", "5", RARITY_ODDS_ID, RICH_TEXT_ID, "0",
        CHARACTER_3_ODDS_ID, CHARACTER_4_ODDS_ID, CHARACTER_5_ODDS_ID,
        "normal", "normal_guarantee", "false", "false", "false",
        "", "", "", "", "", str(SINGLE_TICKET_ID), str(TEN_TICKET_ID),
        START_DATE, END_DATE, "(None)", "false", "116", "117", "169", "170",
        "(None)", "false", "(None)", "(None)", "(None)", "(None)",
        "false", "false", "(None)", "false",
    ]


def build_feature_cells() -> list[str]:
    """Mirror official ticket pages with a static kind-1 top banner."""
    return [
        "1", TOP_BANNER_LOGICAL, "",
        "", "", "", "(None)", "", "",
    ]


def build_rarity_odds_rows() -> dict[str, str]:
    return {"0": "5,100", "1": "4,0", "2": "3,0"}


def build_character_odds_rows(rarity: int) -> dict[str, str]:
    if rarity in (3, 4):
        return {}
    if rarity != 5:
        raise ValueError(f"unsupported abyss gacha rarity: {rarity}")
    return {
        str(index): f"{character_id},5,100,true,true,false,false"
        for index, character_id in enumerate(CHARACTER_IDS)
    }


def build_server_runtime() -> dict:
    pool = [
        {
            "id": character_id,
            "rank": 5,
            "odds": 100,
            "isRateUp": True,
            "isLimited": True,
            "isExchangeable": False,
            "rarity": 125.0,
            "trialReadingForced": False,
        }
        for character_id in CHARACTER_IDS
    ]
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
        "guaranteeRarity": 5,
        "rankRates": {"normal": [1000, 0, 0], "multiGuarantee": [1000, 0]},
        "movieName": "normal",
        "guaranteeMovieName": "normal_guarantee",
        "toUseOddsUpAsTrialReading": False,
        "canBeStartDashExchange": False,
        "startDate": START_DATE,
        "endDate": END_DATE,
        "name": TITLE,
        "pool": {"1": pool, "2": [], "3": []},
    }


def build_rich_text_body() -> bytes:
    html = """<!DOCTYPE html/>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <title>深渊限定扭蛋注意事项</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body class="body" style_id="1">
  <div class="container">
    <p>・本扭蛋仅可使用深渊单抽券或深渊十连券。</p><br/>
    <p>・本扭蛋不接受星导石，也不接受通用角色扭蛋券。</p><br/>
    <p>・卡池仅包含指定的8名限定★5角色，每名角色的获得概率均为12.5%。</p><br/>
    <p>・使用1张深渊单抽券可抽取1次；使用1张深渊十连券可连续抽取10次。</p><br/>
    <p>・重复获得已有角色时，按游戏现有角色重复获得规则处理。</p>
  </div>
</body>
</html>
"""
    compressor = zlib.compressobj(level=9, wbits=-15)
    raw = html.encode("utf-8")
    return compressor.compress(raw) + compressor.flush()


__all__ = [name for name in globals() if name.isupper() or name.startswith("build_")]
