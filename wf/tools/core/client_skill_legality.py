"""ActionSkillValues parser guards, separate from ability/leader row layouts."""
from __future__ import annotations

import math
import re


def action_skill_problems(row: list[str]) -> list[str]:
    """Check the fields parsed by generated ActionSkillValues (c0..c23).

    Conditional area parameters are checked only when the client consumes them;
    unused cells may be empty in official rows. Asset existence is a separate gate.
    """
    if len(row) != 24:
        return [f"action_skill 需要 24 列，实际 {len(row)} 列"]
    problems = []
    if row[3] not in {"true", "True", "TRUE", "false", "False", "FALSE"}:
        problems.append(f"c3 unisonable={row[3]!r} 不能解析为 Bool（C7101）")

    def integer(column):
        if not re.fullmatch(r"[+-]?[0-9]+", row[column]):
            problems.append(f"c{column}={row[column]!r} 必须为整数")

    for column in (4, 5, 6):
        integer(column)
    for condition in (8, 16):
        value = row[condition]
        if condition == 16 and value == "(None)":
            continue
        if value not in {"0", "1"}:
            problems.append(f"c{condition} 自动施放条件={value!r} 不在 0/1 枚举内（C7050）")
            continue
        if value == "0":
            continue
        area = condition + 1
        if row[area] not in {"0", "1", "2", "3", "4"}:
            problems.append(f"c{area} 自动施放区域={row[area]!r} 不在 0..4 枚举内（C7050）")
            continue
        for offset in ((1, 3, 4) if row[area] == "0" else (1, 2, 3, 4, 5)):
            integer(area + offset)
        if row[area] != "0":
            try:
                finite = math.isfinite(float(row[area + 6]))
            except ValueError:
                finite = False
            if not finite:
                problems.append(f"c{area + 6} 方向角必须为有限数值")
    return problems
