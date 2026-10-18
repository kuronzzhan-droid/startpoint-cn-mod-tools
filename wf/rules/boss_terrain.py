"""Inspect actual terrain objects, field cells and per-mode boss slots."""
from __future__ import annotations

from collections import Counter
import re

from .boss_common import EMPTY, cell, cells, wave_name
from .catalog import result


def _waves(document):
    terrain = document.get("terrain") or {}
    if terrain.get("missing") is True:
        return None
    return terrain.get("waves", terrain.get("layers"))


def terrain_checks(document):
    waves = _waves(document)
    if waves is None:
        return [result(rule, "未执行", "缺少已解码地形，不能从 zone 行数推断波次")
                for rule in ("boss.multiwave-field", "boss.terrain-layers")]
    waves = [w for w in waves if w.get("type", "objectgroup") == "objectgroup"]
    waves.sort(key=lambda w: (0, int(w.get("name", "0"))) if str(w.get("name", "0")).isdigit()
               else (1, str(w.get("name", ""))))
    if not waves:
        return [result(rule, "问题", "地形没有 objectgroup 战斗层", blocking=True)
                for rule in ("boss.multiwave-field", "boss.terrain-layers")]
    field = document.get("field") or {}
    missing = [f"c{i}" for i in (7, 8) if cell(field, i) in EMPTY]
    if len(waves) == 1:
        multi = result("boss.multiwave-field", "不适用", "地形仅一波，客户端不读取多波 gate/transit 动画")
    elif missing:
        multi = result("boss.multiwave-field", "问题", "多波 field 缺少 " + "/".join(missing) + "（C8251）",
                       blocking=True, waves=len(waves), missing=missing)
    else:
        multi = result("boss.multiwave-field", "满足", "实际多波地形与 field c7/c8 已核对", waves=len(waves))
    issues, incomplete = [], []
    names = [str(w.get("name", "")) for w in waves]
    if len(set(names)) != len(names):
        issues.append("地形 objectgroup 层名重复")
    zone_rows = (document.get("zone") or {}).get("rows")
    zone_names = {wave_name(z) for z in zone_rows} if zone_rows is not None else None
    for index, wave in enumerate(waves):
        label = str(wave.get("name", index))
        objects = wave.get("objects")
        if objects is None:
            incomplete.append(f"层 {label} 缺少原始 objects")
            continue
        counts = Counter(o.get("type") for o in objects)
        counts["WALL"] = sum(count for token, count in counts.items()
                             if isinstance(token, str) and re.fullmatch(r"WALL\d*", token))
        for token in ("BOUNDS", "WALL", "RETURN_LANE_GUIDE", "CUSTOM_POSITION"):
            if not counts[token]:
                issues.append(f"层 {label} 缺 {token}（C14102）")
        if counts["BOUNDS"] > 1:
            issues.append(f"层 {label} 重复 BOUNDS（C10000）")
        positions = [o.get("name") for o in objects if o.get("type") == "CUSTOM_POSITION"]
        if any(not name for name in positions):
            issues.append(f"层 {label} CUSTOM_POSITION 名称为空")
        multiplayer = document.get("quest", {}).get("kind") not in {"practice", "practice_quest"}
        if multiplayer and counts["COFFIN"] != 9:
            issues.append(f"层 {label} 协力复活位须为 9 个，实际 {counts['COFFIN']}")
        for token in ("GATE", "TRANSIT"):
            if index < len(waves) - 1 and not counts[token]:
                issues.append(f"非末层 {label} 缺 {token}")
            elif len(waves) > 1 and index == len(waves) - 1 and counts[token]:
                issues.append(f"末层 {label} 不应保留 {token}")
        if zone_names is not None and label not in zone_names:
            issues.append(f"地形层 {label} 没有同名 zone 行")
        for enemy in document.get("enemies", []):
            if str(enemy.get("wave", "0")) != label:
                continue
            name = enemy.get("position_name")
            if name not in EMPTY and name not in positions:
                issues.append(f"层 {label} 敌人 {enemy.get('code')} 引用不存在的站位 {name}")
    if zone_names is None:
        incomplete.append("缺少 zone 波次行，未验证地形层引用闭合")
    state = "问题" if issues else "待验证" if incomplete else "满足"
    return [multi, result("boss.terrain-layers", state,
                          "逐层检查边界、站位、9 个复活位及波次出口", blocking=bool(issues),
                          issues=issues, limitations=incomplete)]


def concurrent_positions(document):
    rows = (document.get("zone") or {}).get("rows")
    if rows is None:
        return result("boss.concurrent-positions", "未执行", "缺少 zone 原始行")
    enemies = document.get("enemies", [])
    issues, pending, checked = [], [], 0
    for zone in rows:
        if str(cell(zone, 22)) != "0":
            continue
        wave = wave_name(zone)
        for mode, offset in (("single", 24), ("multi", 26)):
            codes = [cell(zone, offset + 4 * slot) for slot in range(3)]
            codes = [code for code in codes if code not in EMPTY]
            if len(codes) < 2:
                continue
            checked += 1
            names = []
            for code in codes:
                matches = [enemy for enemy in enemies if enemy.get("code") == code
                           and str(enemy.get("wave", "0")) == wave
                           and enemy.get("mode", mode) == mode]
                name = matches[0].get("position_name") if matches else None
                if name in EMPTY:
                    pending.append(f"层 {wave}/{mode}/{code} 缺少初始站位证据")
                else:
                    names.append(name)
            if len(names) != len(set(names)):
                issues.append(f"层 {wave}/{mode} 同屏 boss 站位同名: {names}")
    state = "问题" if issues else "待验证" if pending else "满足" if checked else "不适用"
    return result("boss.concurrent-positions", state, "按单人/多人各自槽位检查同屏 boss 站位",
                  blocking=bool(issues), checked_groups=checked, issues=issues, limitations=pending)
