"""引用完整性门禁 + 发布完整性自检回归测试。

事故背景(2026-07-26):
  缺陷1 关13 被随机到 field water_sphere,其 boss water_sphere_single 在
        general_boss/standard_boss/general_zako 三表全缺 → 真机 U_50fc52 进本崩;
  缺陷2 构建写了 mod_rogue_f9 等克隆进 store,发布清单没带 battle 表 →
        客户端 C8601「指定的Key不存在。key=mod_rogue_f9」。
"""

from __future__ import annotations

import copy

import csv

import io

import os

import json

import math

import random

import re

import subprocess

import sys

import tempfile

import unittest

import zipfile

import zlib

from dataclasses import replace

from pathlib import Path

from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from wf.tools.core import quest_lib as q  # noqa: E402

from wf.tools.rogue import rogue_build as rb  # noqa: E402

from wf.tools.rogue import rogue_bundle as rbb  # noqa: E402

from wf.tools.rogue import rogue_reroll as rr  # noqa: E402

from wf.tools.rogue import rogue_save as rsave  # noqa: E402

import wf_dsl  # noqa: E402

def _store_available() -> bool:
    """本机/CI 是否装了数据包。没装时依赖 store 的用例只能跳过,不能算失败。"""
    try:
        q.store_path(rb.GENERAL_BOSS)
    except FileNotFoundError:
        return False
    return True

requires_store = unittest.skipUnless(_store_available(), "store 不可用")

def quest_hp_row(enemy: float = 1.0, device: float = 1.0,
                 boss: float = 1.0) -> list[str]:
    row = ["(None)"] * 110
    row[86], row[87], row[88] = map(rb.fmt, (enemy, device, boss))
    return row

def wave(zakos: tuple = (), bosses: tuple = ()) -> str:
    """41 列 zone wave 行:zako 填 c2/4/…偶数列,boss 填 (c23,c24)/(c27,c28)/(c31,c32)。"""
    row = [""] * 41
    for n, z in enumerate(zakos):
        row[2 + 2 * n] = z
    slots = ((23, 24), (27, 28), (31, 32))
    for n, b in enumerate(bosses):
        gate, code = slots[n]
        row[gate] = "1"
        row[code] = b
    return ",".join(row)

FD = {
    "f_ok": "f_ok,terrain_a,z_ok",
    "f_bad": "f_bad,terrain_a,z_bad",              # boss 三表全缺且无专用表 = 真悬空
    "f_std": "f_std,terrain_a,z_std",              # boss 只在 standard_boss(误报回归)
    "f_zk": "f_zk,terrain_a,z_zk",                 # boss 槽放 zako 代号(并集第三表)
    "f_nozone": "f_nozone,terrain_a,z_ghost",      # zone 缺失
    "f_badzako": "f_badzako,terrain_a,z_badzako",  # zako 槽悬空
    "f_sp": "f_sp,terrain_a,z_sp",                 # boss 只在专用表(orochi/kraken 型)
}

ZONE = {
    "z_ok": {"0": wave(zakos=("zk1",), bosses=("boss_g",))},
    "z_bad": {"0": wave(bosses=("ghost_boss",))},
    "z_std": {"0": wave(bosses=("boss_s",))},
    "z_zk": {"0": wave(bosses=("zk1",))},
    "z_badzako": {"0": wave(zakos=("zk_ghost",))},
    "z_sp": {"0": wave(bosses=("sp_boss",))},
}

ENEMIES = {"boss_g", "boss_s", "zk1"}   # general ∪ standard ∪ zako

ZAKOS = {"zk1"}

def quest_row(field: str) -> list[str]:
    row = ["700099001"] + [""] * 98
    row[98] = field
    return row

def thumbnail_pick_fields(field: str) -> dict:
    thumbnail = "quest/thumbnail/test/boss"
    return {
        "thumb": thumbnail,
        "thumbnail_field": field,
        "thumbnail_evidence": {
            "schema": rb.THUMBNAIL_EVIDENCE_SCHEMA,
            "field": field,
            "thumbnail": thumbnail,
            "asset_logical": thumbnail + ".png",
            "asset_exists": True,
            "source_match": "exact_field",
            "source_category": "test",
            "source_logical": "master/quest/test.orderedmap",
            "source_path": ["test"],
            "source_level": 100,
            "floor_key": None,
            "static_verified": True,
            "runtime_simulated": False,
            "gameplay_verified": False,
        },
    }

def native_bundle(field: str, boss: str, *, family: str = "family",
                  kind: int = 1, bgm: str = "bgm_safe",
                  thumbnail: str = "thumb_safe") \
        -> rbb.NativeBossBundle:
    return rbb.NativeBossBundle(
        family_id=family,
        family_name=family,
        variant_id=f"{family}-variant",
        variant_name=f"{family}-variant",
        source_field=field,
        source_zone=f"zone-{field}",
        terrain_logical=f"battle/field/{field}.terrain.amf3.deflate",
        active_layers=("0",),
        slots=(rbb.ActiveBossSlot(
            "0", 1, 0, rbb.BossRef(kind, boss), rbb.BossRef(kind, boss)),),
        bgm=bgm,
        thumbnail=thumbnail,
        source_category="rush",
        selected_levels=(("0", 1, 100),),
        terrain_requirements=rbb.BossTerrainRequirements(
            layers=(rbb.LayerTerrainRequirements(
                "0",
                funnels=(rbb.FunnelRequirement("1", 1, ("safe_funnel",)),),
                spawned_refs=(rbb.SpawnedRef("AlterEgo", "safe_shadow"),)),),
            action_roots=("battle/action/safe",),
            action_closure=("battle/action/safe",)),
    )

def wave_pair(bosses: tuple = ()) -> str:
    """41 列 zone wave 行,boss 槽的**单人+多人两列**都填(官方常态)。

    槽位 = (单人kind, 单人列, 多人kind, 多人列)。
    """
    row = [""] * 41
    for n, b in enumerate(bosses):
        single_kind, single, multi_kind, multi = (
            (23, 24, 25, 26), (27, 28, 29, 30), (31, 32, 33, 34))[n]
        row[single_kind] = "1"
        row[multi_kind] = "1"
        row[single] = b
        row[multi] = b
    return ",".join(row)

__all__ = [name for name in globals() if not name.startswith("__")]
