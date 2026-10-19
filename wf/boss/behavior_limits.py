"""Bound repeated work across nested events and referenced action programs."""
from __future__ import annotations

import math

from wf.rules.boss_preload import programs, walk

REPEAT_LIMIT = 999


def reject_loops(closure):
    edges = {program: {p for item in walk(tree) if isinstance(item, str) for p in programs(item)}
             for program, tree in closure.items()}
    visiting, totals = set(), {}

    def budget(value, program):
        if isinstance(value, str):
            return sum(visit(child) for child in programs(value))
        if isinstance(value, dict):
            return sum(budget(child, program) for child in value.values())
        if not isinstance(value, list):
            return 0
        if value[:1] == ['Repeat']:
            count = value[2] if len(value) > 2 else None
            if (isinstance(count, bool) or not isinstance(count, (int, float))
                    or not math.isfinite(count) or count != int(count) or not 0 < count <= REPEAT_LIMIT):
                raise ValueError(f'borrowed infinite/unbounded Repeat is forbidden: {program}')
            total = int(count) * max(1, sum(budget(child, program) for child in value[3:]))
        else:
            total = sum(budget(child, program) for child in value)
        if total > REPEAT_LIMIT:
            raise ValueError(f'borrowed Repeat closure budget exceeds {REPEAT_LIMIT}: {program}')
        return total

    def visit(program):
        if program in visiting:
            raise ValueError(f'borrowed recursive DSL cycle is forbidden: {program}')
        if program in totals:
            return totals[program]
        if program not in closure:
            raise ValueError(f'borrowed DSL closure missing: {program}')
        visiting.add(program)
        totals[program] = budget(closure[program], program)
        visiting.remove(program)
        return totals[program]

    for program in closure:
        visit(program)
    children = set().union(*edges.values()) if edges else set()
    total = sum(totals[program] for program in set(closure) - children)
    if total > REPEAT_LIMIT:
        raise ValueError(f'borrowed Repeat closure budget exceeds {REPEAT_LIMIT}: {total}')
