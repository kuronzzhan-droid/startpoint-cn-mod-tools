"""Project boss state triggers onto the shared L2 ActionDsl event format."""
from __future__ import annotations

import copy

from wf.boss.behavior_model import Programs, read_behavior
from wf.rules.boss_preload import programs

from .effect_render import read_parts, read_timeline
from .timeline import build_timeline


def _place(timeline, state, action):
    """Known triggers use state-entry frames; conditional ones stay action-local."""
    result = copy.deepcopy(timeline)
    begin = action.get("begin")
    known = isinstance(begin, (int, float)) and not isinstance(begin, bool)
    offset = begin if known else 0
    for event in result["events"]:
        event["t"] += offset
        for key in ("hiddenAt", "erasedAt"):
            if event.get(key) is not None:
                event[key] += offset
        for motion in event.get("motions", []):
            motion["t"] += offset
    for subprogram in result["subprograms"]:
        subprogram["t"] += offset
    result["duration"] += offset
    result["timeOrigin"] = "state_entry" if known else "action_entry"
    result["stateInterval"] = {
        "id": state.get("id"), "begin": 0 if state else None,
        "end": state.get("end"), "triggerFrame": begin,
        "semantics": state.get("interval_semantics", "trigger_unknown"),
        "termination": state.get("termination"), "next": state.get("next"),
        "back": state.get("back"), "event": action.get("event"),
    }
    result["notes"].append(
        "事件帧相对当前状态进入；状态结束仅为配置上界，未模拟实际退出或分支。" if known else
        "触发帧未知，事件帧相对动作开始；不将条件触发标成状态第 0 帧。")
    return result


def timeline_summary(source, document):
    """Return independent moves, preserving conditional states and missing DSLs."""
    behavior = read_behavior(source, document)
    graph, cache, effects, moves = Programs(source), {}, {}, []

    def effect_info(path):
        if path not in effects:
            timeline = read_timeline(source, path)
            parts = read_parts(source, path) if timeline is not None else None
            effects[path] = None if timeline is None or parts is None else {
                "sequences": timeline.get("sequences", []),
                "sounds": timeline.get("sounds", []), "defaultScale": parts.get("s", 1)}
        return effects[path]

    def build(program, element):
        key = program, element
        if key not in cache:
            tree = graph.load(program)
            timeline = build_timeline(tree, kind="boss", path=program, element=element,
                                      effects=effect_info, programs=graph.load)
            if tree is None:
                timeline["issues"].append({"level": "问题", "node": "根",
                                           "text": "当前视图缺少动作 DSL，无法生成事件。"})
            if "$" not in program:
                timeline["issues"].append({"level": "待验证", "node": "根",
                    "text": "裸路径动作的加载仅有源码推断；派生目录尚无真机加载证据。"})
            cache[key] = timeline
        return cache[key]

    for enemy in behavior["enemies"]:
        code, wave, level = enemy["enemyCode"], enemy["wave"], enemy["level"]
        row = next((item.get("row", []) for item in document.get("enemies", [])
                    if (item.get("code"), item.get("wave"), item.get("level")) == (code, wave, level)), [])
        # GeneralBoss masters use 1..7; build_timeline consumes internal 0..6.
        element = int(row[0]) - 1 if enemy["kind"] == "general" and row and row[0] in set("1234567") else None
        triggered = set()

        def add(program, state, action, index):
            suffix = str(state.get("id", "unmapped"))
            name = f"{wave}/{code}/{level}/{suffix}/{index}/{program}"
            moves.append({"name": name, "label": f"{code} · {suffix} · {program.rsplit('/', 1)[-1]}",
                          "enemyCode": code, "wave": wave, "level": level,
                          "slot": action.get("slot"),
                          "timeline": _place(build(program, element), state, action)})

        for state in enemy["states"]:
            for index, action in enumerate(state.get("actions", [])):
                for program in action["dsl"]:
                    triggered.add(program)
                    add(program, state, action, index)
        # Keep slots without a resolved marker visible, without inventing a trigger.
        for slot in enemy.get("slots", []):
            for program in programs(slot["program"]):
                if program not in triggered:
                    triggered.add(program)
                    add(program, {}, {"slot": slot["slot"]}, slot["slot"])
        for index, program in enumerate(enemy.get("preload_roots", [])):
            if program not in triggered:
                triggered.add(program)
                add(program, {}, {"event": ["InitializationOrWatch"]}, f"preload{index}")
    return {"moves": moves, "note": "按状态分别展示招式；条件、循环、命中与实际状态选择未模拟。",
            "runtime": "未执行", "limitations": behavior["timeline"]["limitations"]}
