"""Translate native character/ball curves without modifying their donor keys."""
from __future__ import annotations

import math

from .drafts import DraftError
from .summon_tables import ATK, HP, INT_MAX, LEVEL, STATUS, csv, number, numeric, single


def curve(value, label):
    if not isinstance(value, dict) or not value:
        raise DraftError(f"{label} 缺少等级曲线")
    points = {}
    for level, text in value.items():
        if not level.isdigit() or str(int(level)) != level or not 1 <= int(level) <= INT_MAX:
            raise DraftError(f"{label} 等级须为规范正 int32")
        row = single(text, label, 1)
        points[int(level)] = number(row[0], label)
    return dict(sorted(points.items()))


def interpolate(points, level, *, character=False):
    keys = sorted(points)
    if not keys[0] <= level <= keys[-1]:
        raise DraftError("HP/ATK 曲线定义域不一致，无法保证召唤上下文等级有效")
    if level in points:
        return points[level]
    upper = next(i for i in keys if i > level)
    lower = keys[keys.index(upper) - 1]
    # Match the two native evaluators' arithmetic order: equivalent algebra
    # can differ by one after ceil/floor at an integer floating-point boundary.
    if character:
        ratio = (level - lower) / (upper - lower)
        return points[lower] * (1 - ratio) + points[upper] * ratio
    return (points[upper] - points[lower]) / (upper - lower) * (level - lower) + points[lower]


def prepare_panel(tables, spec):
    template, panel = spec["template"], spec.get("panel", {"mode": "source"})
    mode, identity = panel.get("mode", "source"), spec["id"]
    scale_hp, scale_atk = panel.get("hp_scale", 1), panel.get("attack_scale", 1)
    if mode == "scaled":
        number(scale_hp, "hp_scale", 0.000000000000001)
        number(scale_atk, "attack_scale", 0.000000000000001)
    if mode == "manual":
        levels = panel["levels"]
        if len({point["level"] for point in levels}) != len(levels):
            raise DraftError("手填面板不能有重复等级断点")
        points = {int(point["level"]): (number(point["hp"], "HP", 1),
                                   number(point["attack"], "ATK")) for point in levels}
    elif template["kind"] == "character":
        status = tables.get(STATUS, template["id"])
        if not isinstance(status, dict) or not status:
            raise DraftError("母本角色缺少 status 曲线")
        points = {}
        for level, value in status.items():
            if not level.isdigit() or str(int(level)) != level or not 1 <= int(level) <= INT_MAX:
                raise DraftError("母本角色 status 等级无效")
            hp, atk = single(value, "character_status", 2)
            points[int(level)] = number(hp, "HP", 1), number(atk, "ATK")
    else:
        row = single(tables.get(LEVEL, template["id"]), "multiball_level", 6)
        hp = curve(tables.get(HP, row[0]), "multiball_hp_curve")
        atk = curve(tables.get(ATK, row[3]), "multiball_atk_curve")
        factors = [number(row[i], "multiball_level") for i in (1, 2, 4, 5)]
        points = {level: (factors[0] * interpolate(hp, level),
                          factors[2] * interpolate(atk, level)) for level in sorted(hp.keys() | atk.keys())}
        if mode == "scaled":
            row[2] = numeric(factors[1] * scale_hp)
            row[5] = numeric(factors[3] * scale_atk)
        correction_hp, correction_atk = float(row[2]), float(row[5])
        _validate_values(points, correction_hp, correction_atk)
        tables.add(LEVEL, identity, csv([row]))
        return _summary(points, correction_hp, correction_atk, "native-floor")
    _validate_values(points, scale_hp, scale_atk)
    # Native character status uses ceil interpolation. Multiballs use floor;
    # materialise every integer level to preserve the character's exact panel.
    if mode != "manual":
        hp = {level: values[0] for level, values in points.items()}
        atk = {level: values[1] for level, values in points.items()}
        if max(points) - min(points) > 10000:
            raise DraftError("角色 status 定义域过大，拒绝展开超过 10001 个等级")
        points = {level: (math.ceil(interpolate(hp, level, character=True)),
                          math.ceil(interpolate(atk, level, character=True)))
                  for level in range(min(points), max(points) + 1)}
    key = "studio_summon_" + identity
    for logical, index in ((HP, 0), (ATK, 1)):
        tables.add(logical, key, {str(level): numeric(values[index]) for level, values in sorted(points.items())})
    tables.add(LEVEL, identity, csv([[key, "1", numeric(scale_hp), key, "1", numeric(scale_atk)]]))
    return _summary(points, scale_hp, scale_atk, "native-floor" if mode == "manual" else "character-ceil-then-scale-floor")


def _validate_values(points, hp_scale, attack_scale):
    number(hp_scale, "hp_scale", 0.000000000000001)
    number(attack_scale, "attack_scale", 0)
    for hp, atk in points.values():
        number(hp * hp_scale, "缩放后 HP", 1)
        number(atk * attack_scale, "缩放后 ATK")


def _summary(points, hp_scale, attack_scale, rounding):
    def item(level):
        hp, atk = points[level]
        return {"level": level, "hp": math.floor(hp * hp_scale + 1e-10 + 1e-10),
                "attack": math.floor(atk * attack_scale + 1e-10 + 1e-10)}
    return {"count": len(points), "first": item(min(points)), "last": item(max(points)),
            "rounding": rounding, "contextLevel": "clv", "outsideDomain": "rejected by native client (14520)"}
