"""Prove C8016 shims from decoded candidate DSL and marker action slots."""
from __future__ import annotations

import copy
import re
import zlib

from .boss_common import CandidateView, EMPTY, cell, cells, fields
from .catalog import result

GENERAL = "master/battle/boss/general_boss.orderedmap"
FUNNEL = "master/battle/boss/funnel/general_funnel.orderedmap"
ELEMENT_NODES = {"ResolveByElement": 2, "CreateNormalAttack": 2}


def walk(value):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def recommended(document):
    quest = document.get("quest", {})
    indexes = {"boss_battle": 72, "hard_multi": 73, "hard_multi_event": 73, "practice": 73}
    if quest.get("kind") in indexes and len(cells(quest)) > indexes[quest["kind"]]:
        return cell(quest, indexes[quest["kind"]])
    value = fields(document)
    for key in ("recommended_element", "recommendedElement", "battle_recommended_element"):
        if key in value:
            return value[key]
    return None


def tier(node, level):
    if not isinstance(node, dict):
        return cells(node)
    keys = sorted((int(k), k) for k in node if str(k).isdigit())
    for number, key in keys:
        if number >= int(level or 1):
            return cells(node[key])
    return []


class DslEvidence:
    def __init__(self, view):
        self.view, self.cache, self.missing = CandidateView(view), {}, set()

    def tree(self, logical):
        if logical not in self.cache:
            raw = self.view.raw(logical)
            if raw is None:
                self.missing.add(logical)
                self.cache[logical] = None
            else:
                import wf_dsl
                try:
                    self.cache[logical] = wf_dsl.parse_dsl(zlib.decompress(raw, -15))["tree"]
                except (ValueError, EOFError, IndexError, KeyError, zlib.error) as error:
                    raise ValueError(f"无法解码候选预载资源 {logical}: {error}") from error
        return self.cache[logical]

    def dsl(self, program):
        suffix = ".action.dsl.amf3.deflate"
        return self.tree(program if program.endswith(suffix) else program + suffix)

    def closure(self, roots):
        found, queue = {}, list(roots)
        while queue:
            program = queue.pop()
            if program in found:
                continue
            if len(found) >= 800:
                raise ValueError("boss DSL closure exceeds 800 programs")
            tree = self.dsl(program)
            found[program] = tree
            queue.extend(n for n in walk(tree) if isinstance(n, str)
                         and n.startswith("battle/action/") and n not in found)
        return found

    def fired_slots(self, row):
        marker = cell(row, 25)
        if marker in EMPTY:
            return None
        tree = self.tree(marker + ".timeline.amf3.deflate")
        if not isinstance(tree, dict):
            return None
        fired = set()
        for point in tree.get("points", []):
            match = re.fullmatch(r"enemy_action(\d+)", point.get("path", ""))
            if match and any(frame.get("data") for frame in point.get("frames", [])):
                fired.add(int(match.group(1)))
        return fired


def _expected(tree, element):
    fixed, changed = copy.deepcopy(tree), False
    for node in walk(fixed):
        if isinstance(node, list) and node and isinstance(node[0], str):
            index = ELEMENT_NODES.get(node[0])
            if index is not None and len(node) > index and node[index] == 255:
                node[index], changed = int(element), True
    return fixed if changed else None


def _enemy_changed(document, baseline):
    previous = {e.get("code"): e for e in baseline.get("enemies", [])}
    return any(e.get("code") in previous and cell(e, 0) != cell(previous[e["code"]], 0)
               for e in document.get("enemies", []))


def preload_check(document, *, view=None, baseline=None):
    rule = "boss.element-preload"
    if baseline is None:
        return result(rule, "未执行", "缺少属性修改前快照，不能断言召唤物预载不受影响")
    changed = recommended(document) != recommended(baseline) or _enemy_changed(document, baseline)
    if not changed:
        return result(rule, "不适用", "推荐属性及已知敌人属性未变；编队限定属性不等于敌方属性")
    if view is None:
        return result(rule, "待验证", "属性发生变化，缺少候选 DSL/marker 资源，预载垫片尚未验证")
    evidence = DslEvidence(view)
    general = evidence.view.table(GENERAL) or {}
    funnels = evidence.view.table(FUNNEL)
    problems, pending, proofs, checked = [], [], [], set()
    for enemy in document.get("enemies", []):
        if enemy.get("kind") == "zako":
            continue
        code = enemy.get("code")
        if code in checked:
            continue
        checked.add(code)
        row = tier(general.get(code), enemy.get("level", 1))
        if not row:
            pending.append(f"{code} 不在 general_boss；esdl/特殊 boss 动态召唤预载尚未证明")
            continue
        roots = [s for s in str(cell(row, 109, "")).split(",") if s not in EMPTY]
        actions = {i - 110: program for i, program in enumerate(row) if 111 <= i <= 160 and program not in EMPTY}
        programs = evidence.closure([*roots, *actions.values()])
        spawned = set()
        for tree in programs.values():
            for node in walk(tree):
                if isinstance(node, list) and len(node) > 1 and node[0] == "SpawnFunnel" \
                        and isinstance(node[1], list) and len(node[1]) > 1:
                    if node[1][0] == "Funnel":
                        spawned.add(node[1][1])
                    else:
                        pending.append(f"{code} 的 {node[1][0]} 召唤物须核对动态属性预载")
        fired = evidence.fired_slots(row) if spawned else set()
        for funnel in sorted(spawned):
            frow = tier((funnels or {}).get(funnel), enemy.get("level", 1))
            own, element = cell(row, 0), cell(frow, 0)
            if not frow or element in EMPTY:
                pending.append(f"{code}/{funnel} 缺少召唤物属性行")
                continue
            if element == "0" or element == own:
                continue
            fprograms = evidence.closure(value for value in frow if value.startswith("battle/action/"))
            if not fprograms:
                pending.append(f"{code}/{funnel} 没有可核对的召唤物程序")
            for program, tree in fprograms.items():
                expected = _expected(tree, element)
                if expected is None:
                    continue
                matches = [slot for slot, action in actions.items() if evidence.dsl(action) == expected]
                idle = [slot for slot in matches if fired is not None and slot not in fired]
                if not matches or fired is not None and not idle:
                    problems.append(f"{code}/{funnel}/{program} 缺少未触发槽位中的固定属性 {element} 预载垫片（C8016）")
                elif fired is None:
                    pending.append(f"{code} 垫片树匹配，但缺少 marker，无法证明槽位不触发")
                else:
                    proofs.append({"boss": code, "funnel": funnel, "program": program, "element": element, "slots": idle})
    if not checked:
        pending.append("没有可读取的敌人，未执行召唤闭包核对")
    pending.extend(f"缺少候选资源 {path}" for path in sorted(evidence.missing))
    state = "问题" if problems else "待验证" if pending else "满足"
    return result(rule, state, "属性改动后按实际 DSL、固定属性替换和 marker 空槽核对召唤物预载",
                  blocking=bool(problems), issues=problems, limitations=pending, proofs=proofs)
