"""Named terrain references reachable through GeneralBoss and Funnel actions."""
from __future__ import annotations

from wf.rules.boss_common import CandidateView, cell
from wf.rules.boss_preload import programs, tier, walk
from .behavior_identity import GENERAL_FUNNEL, WATCH
from .behavior_model import Programs


def watch_programs(view, code, routine):
    watches = CandidateView(view).table(WATCH) or {}
    node = watches.get('1', {}).get(code, {}).get(routine, {})
    return [p for value in walk(node) if isinstance(value, str) for p in programs(value)]


class PositionReferences:
    """Resolve one candidate view, retaining source paths for missing inputs."""

    def __init__(self, view):
        self.view = CandidateView(view)
        self.graph = Programs(view)
        self.funnels = None
        self.watches = None

    def general(self, enemy):
        row, code = enemy.get('row', []), enemy.get('code')
        roots = [p for value in row for p in programs(value)]
        if self.watches is None:
            self.watches = self.view.table(WATCH) or {}
        watches = self.watches.get('1', {}).get(code, {}).get(cell(row, 42), {})
        roots.extend(p for value in walk(watches) if isinstance(value, str) for p in programs(value))
        closure, seen, missing = {}, set(), set()
        while roots:
            current = self.graph.closure(roots)
            closure.update(current)
            missing.update(p for p, tree in current.items() if tree is None)
            roots = []
            for tree in current.values():
                for node in walk(tree):
                    if not (isinstance(node, list) and len(node) > 1 and node[0] == 'SpawnFunnel'
                            and isinstance(node[1], list) and len(node[1]) > 1
                            and node[1][0] == 'Funnel'):
                        continue
                    funnel = node[1][1]
                    if funnel in seen:
                        continue
                    seen.add(funnel)
                    if self.funnels is None:
                        self.funnels = self.view.table(GENERAL_FUNNEL) or {}
                    frow = tier(self.funnels.get(funnel), enemy.get('level', 1))
                    if not frow:
                        missing.add(f'{GENERAL_FUNNEL}/{funnel}')
                    roots.extend(p for value in frow for p in programs(value))
        positions = {node[1] for tree in closure.values() for node in walk(tree)
                     if isinstance(node, list) and len(node) == 2 and node[0] == 'CustomPosition'
                     and isinstance(node[1], str)}
        return positions, sorted(missing)
