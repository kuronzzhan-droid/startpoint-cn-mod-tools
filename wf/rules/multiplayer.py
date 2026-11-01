"""Read-only multiplayer advisories, separate from the five-state gates."""
from __future__ import annotations

import json

from .catalog import result
from .multiplayer_patterns import BASIS, scan_tree
from .multiplayer_summary import summarize


class _ReadOnlyCandidate:
    """Read candidate bytes without enrolling advisory inputs in draft locks."""

    def __init__(self, view):
        from wf.boss.edit_state import BossEditState
        self.source = getattr(view, "view", view)
        self.edit = self.source if isinstance(self.source, BossEditState) else None
        self.reads = set()

    def raw(self, logical):
        from .boss_common import CandidateView
        self.reads.add(logical)
        if self.edit is not None:
            if logical in self.edit.client:
                return self.edit.client[logical]
            return CandidateView(self.edit.base).raw(logical)
        return CandidateView(self.source).raw(logical)


def _signature(document):
    """Behavior and funnel level selection affect hints; HP/attack values do not."""
    from wf.boss import schema as s
    from .boss_common import cell
    from .boss_preload import programs, walk
    enemies = []
    for enemy in document.get("enemies", []):
        if enemy.get("kind") not in {"boss", "funnel", "zako"}:
            continue
        table, row = enemy.get("table"), enemy.get("row", [])
        columns = (25, 42, 109, *range(111, 161)) if table == s.GENERAL_BOSS else range(len(row))
        entry = [table, enemy.get("code"), enemy.get("level"), [cell(row, index) for index in columns]]
        if entry not in enemies:
            enemies.append(entry)
    roots = sorted({p for node in walk(document) if isinstance(node, str) for p in programs(node)})
    level = document.get("quest", {}).get("fields", {}).get("level")
    return json.dumps([enemies, roots, level], sort_keys=True, ensure_ascii=True)


class MultiplayerScanner:
    """One candidate replay, reusing equivalent tiers and their baseline scans."""

    def __init__(self, view):
        self.view, self.cache, self.baseline_cache = _ReadOnlyCandidate(view), {}, {}
        self.baseline_view = (_ReadOnlyCandidate(self.view.edit.base)
                              if self.view.edit is not None else self.view)

    @staticmethod
    def _cached(document, view, cache):
        key = _signature(document)
        if key not in cache:
            view.reads.clear()
            hits = _scan(document, view)
            cache[key] = (hits, set(view.reads))
        return cache[key]

    def check(self, document, baseline=None):
        try:
            hits, reads = self._cached(document, self.view, self.cache)
            edit = self.view.edit
            if edit is None or not edit.client:
                return summarize(hits, hits, comparison="baseline")
            if baseline is None:
                from wf.boss.reader import BossReader
                baseline = BossReader(edit.source).show(document["quest"]["selector"])
            # HP/reward edits reuse the scan when the actual advisory read set
            # and behavior roots are unchanged. No additional draft locks.
            same = _signature(document) == _signature(baseline) and all(
                logical not in edit.client or edit.client[logical] == self.baseline_view.raw(logical)
                for logical in reads)
            before = hits if same else self._cached(baseline, self.baseline_view, self.baseline_cache)[0]
            return summarize(hits, before, comparison="candidate")
        except Exception as exc:  # noqa: BLE001 - advisory scans must never block editing.
            # A failed comparison must not erase successfully scanned candidate hits.
            current = locals().get("hits", [])
            return summarize([*current, _incomplete(exc)], None, comparison="unavailable")


def _incomplete(exc):
    return result("multiplayer.incomplete", "待验证",
                  f"联机风险扫描不完整：{type(exc).__name__}: {exc}；可能有遗漏。",
                  category="联机风险", source=BASIS)


def check_multiplayer(document, view, baseline=None):
    """Scan native behavior and action closures; never assert runtime safety."""
    if view is None:
        return []
    try:
        scanner = view if isinstance(view, MultiplayerScanner) else MultiplayerScanner(view)
        return scanner.check(document, baseline)
    except Exception as exc:  # noqa: BLE001 - isolate setup errors as well as scanning.
        return [_incomplete(exc)]


def _scan(document, view):
    from .multiplayer_inputs import collect_inputs
    checks = []
    try:
        inputs, issues = collect_inputs(document, view)
        for logical, tree in inputs.items():
            try:
                checks.extend(scan_tree(tree, logical))
            except Exception as exc:  # noqa: BLE001 - preserve other readable files.
                issues.append(f"{logical}: {type(exc).__name__}: {exc}")
        if issues:
            checks.append(result("multiplayer.incomplete", "待验证",
                                 "联机风险扫描不完整：部分输入缺失或无法解析；可能有遗漏。",
                                 category="联机风险", issues=sorted(set(issues)), source=BASIS))
    except Exception as exc:  # noqa: BLE001
        checks.append(_incomplete(exc))
    return checks
