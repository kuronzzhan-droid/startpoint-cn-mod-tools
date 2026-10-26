"""Native summon rows and additive, byte-preserving table compilation."""
from __future__ import annotations

import copy
import math

import wf_mod_tool as core
import wf_quest_lib as codec
from wf.text.edit import _encode

from .drafts import DraftError, sha256

CHAR = "master/character/character.orderedmap"
TEXT = "master/character/character_text.orderedmap"
STATUS = "master/character/character_status.orderedmap"
SKILL = "master/skill/action_skill.orderedmap"
BALL = "master/battle/multiball/multiball.orderedmap"
LEVEL = "master/battle/multiball/multiball_level.orderedmap"
HP = "master/battle/multiball/multiball_hp_curve.orderedmap"
ATK = "master/battle/multiball/multiball_atk_curve.orderedmap"
CUSTOM = "master/string/custom_ability_string.orderedmap"
PF = "master/skill/power_flip_action.orderedmap"
EMPTY = {"", "0", "(None)"}
INT_MAX = 2147483647


def csv(rows):
    return core.write_csv_lines(rows).rstrip("\n")


def single(value, label, width=None):
    rows = core.read_csv_lines(value) if isinstance(value, str) else []
    if len(rows) != 1 or (width is not None and len(rows[0]) != width):
        raise DraftError(f"{label} 必须是单条 {width or ''} 列记录")
    return rows[0]


def number(value, label, minimum=0):
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise DraftError(f"{label} 需要有限数值") from exc
    if isinstance(value, bool) or not math.isfinite(result) or result < minimum or result > INT_MAX:
        raise DraftError(f"{label} 数值越界")
    return result


def numeric(value):
    value = float(value)
    return str(int(value)) if value.is_integer() else repr(value)


class Tables:
    """Only record reads used by this recipe, and only insert new outer keys."""

    def __init__(self, source):
        self.source, self.original, self.parsed, self.additions = source, {}, {}, {}

    def table(self, logical, *, required=True):
        if logical not in self.original:
            raw = self.source.raw(logical)
            self.original[logical] = raw
            try:
                self.parsed[logical] = codec.parse_node(raw) if raw is not None else {}
            except (ValueError, TypeError) as exc:
                raise DraftError(f"输入表无法解码：{logical}：{exc}") from exc
            if not isinstance(self.parsed[logical], dict):
                raise DraftError(f"输入不是 orderedmap：{logical}")
        if required and self.original[logical] is None:
            raise DraftError(f"缺少完整基线表：{logical}")
        return self.parsed[logical]

    def get(self, logical, key):
        table = self.table(logical)
        if key not in table:
            raise DraftError(f"母本或引用键不存在：{logical}/{key}")
        return table[key]

    def add(self, logical, key, value):
        before = self.table(logical)
        if key in before or key in self.additions.get(logical, {}):
            raise DraftError(f"新增键已占用：{logical}/{key}")
        self.additions.setdefault(logical, {})[key] = copy.deepcopy(value)

    def inputs(self):
        return {key: sha256(raw) if raw is not None else None for key, raw in self.original.items()}

    def compile(self, members=None):
        result = {}
        for logical, additions in self.additions.items():
            raw = (members or {}).get(("common", logical), self.original[logical])
            before = codec.parse_node(raw)
            if set(before) & set(additions):
                raise DraftError(f"多个草稿操作写入同一键：{logical}")
            result[logical] = _encode(raw, before, {**before, **additions})
        return result

    def planned(self):
        result = []
        for logical, additions in self.additions.items():
            for key, value in additions.items():
                item = {"logical": logical, "key": key}
                item["rows" if isinstance(value, str) else "levels"] = (
                    core.read_csv_lines(value) if isinstance(value, str) else value)
                result.append(item)
        return result


def skill(tables, key, level=None):
    levels = tables.get(SKILL, key)
    if not isinstance(levels, dict) or not levels or any(not k.isdigit() for k in levels):
        raise DraftError(f"action_skill 档位结构无效：{key}")
    level = str(level) if level is not None else max(levels, key=int)
    if level not in levels:
        raise DraftError(f"action_skill 档位不存在：{key}/{level}")
    row = single(levels[level], f"action_skill/{key}/{level}")
    if len(row) < 16 or row[7] in EMPTY:
        raise DraftError(f"action_skill 缺少路径或自动施放列：{key}/{level}")
    # A multiball has one fixed weight; the max evolution's c5 is the native
    # maximum skill-level endpoint. Its DSL still receives the caller's slv.
    weight = number(row[5], "action_skill weight", minimum=1)
    return {"key": key, "level": level, "name": row[0], "path": row[7]}, [
        row[7], row[0], numeric(weight), *row[8:16]]


def ball_skill(tables, row, spec):
    if spec.get("mode", "inherit") == "specified":
        return skill(tables, spec["key"], spec.get("level"))
    if "level" in spec:
        if row[9] in EMPTY:
            raise DraftError("母本 multiball 无主动技能，无法指定继承档位；请使用 skill.mode='specified'")
        def matches_path(value):
            rows = core.read_csv_lines(value) if isinstance(value, str) else []
            return len(rows) == 1 and len(rows[0]) > 7 and rows[0][7] == row[9]

        matches = [key for key, levels in tables.table(SKILL).items() if isinstance(levels, dict)
                   and any(matches_path(value) for value in levels.values())]
        if len(matches) != 1:
            raise DraftError("母本 multiball 技能键不能唯一反查；请指定 skill.key")
        return skill(tables, matches[0], spec["level"])
    return {"key": None, "level": None, "name": row[10], "path": row[9]}, row[9:20]


def native_row(tables, spec):
    template = spec["template"]
    selected = spec.get("skill", {})
    if template["kind"] == "character":
        donor = single(tables.get(CHAR, template["id"]), "character", 37)
        key = selected.get("key", donor[8])
        active, action = skill(tables, key, selected.get("level"))
        row = [*donor[:8], "true", *action, *(["(None)"] * 4), "1", "0", "false", "false"]
        name = donor[0]
        text = tables.table(TEXT, required=False).get(template["id"])
        if isinstance(text, str):
            name_row = single(text, "character_text")
            if name_row:
                name = name_row[0]
        preserved = {f"c{i}": row[i] for i in (2, 4, 5, 7, *range(20, 28))}
    else:
        row = single(tables.get(BALL, template["id"]), "multiball", 28)
        active, action = ball_skill(tables, row, selected)
        row[9:20] = action
        name = row[0]
        original = tables.table(CUSTOM).get(row[0])
        if isinstance(original, str):
            name = single(original, "custom_ability_string")[0]
        preserved = {f"c{i}": row[i] for i in (2, 4, 5, 7, *range(20, 28))}
    identity = spec["id"]
    row[0] = "studio_summon_" + identity
    row[1] = spec.get("image_prefix", row[1] if template["kind"] == "multiball" else donor[0])
    row[3], row[6] = str(int(spec.get("element", row[3]))), str(int(spec.get("pf_type", row[6])))
    if row[3] not in tuple(map(str, range(6))) or row[6] not in tuple(map(str, range(5))):
        raise DraftError("召唤角色属性须为 0..5，PF 类型须为 0..4")
    if "assist" in spec:
        row[8] = str(spec["assist"]).lower()
    tables.add(CUSTOM, row[0], csv([[name]]))
    tables.add(BALL, identity, csv([row]))
    return row, active, preserved
