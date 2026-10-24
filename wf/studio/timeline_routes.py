"""HTTP surface of the L2 编排级 preview (read-only).

| GET | path | |
|---|---|---|
| ``/api/characters/<cid>/programs`` | skill tiers, switched skills, native and override PF levels, kind-629 programs |
| ``/api/studio/timeline?path=&kind=&cid=`` | :mod:`wf.studio.timeline` event list for one program |
| ``/api/studio/effect?path=`` | baked flatomo effect (per-frame draw commands, cells) |
| ``/api/studio/effect.png?path=`` | the effect's repacked, un-rotated image cells |
"""
from __future__ import annotations

import re
import threading

from wf.view.layout import col
from wf_wiki_catalog import LEVELS

from .effect_render import bake, read_parts, read_timeline
from .timeline import DSL_SUFFIX, build_timeline, program_logical

PF_TYPES = {"0": "knight", "1": "fighter", "2": "ranged", "3": "supporter", "4": "special"}
PF_TYPE_CN = {"knight": "剑士", "fighter": "格斗", "ranged": "射击", "supporter": "辅助", "special": "特殊"}
KINDS = ("skill", "pf", "ability_skill", "subprogram")
SAFE_PATH = re.compile(r"^battle/[A-Za-z0-9_./$-]+$")


def _cell(row, index):
    return row[index].strip() if len(row) > index else ""


def _exists(source, program: str) -> bool:
    return source.raw(program_logical(program)) is not None


def character_programs(source, cid: str) -> dict | None:
    rows = source.table("character").get(cid)
    if not rows or not rows[0]:
        return None
    row = rows[0]
    code, kind_code = row[0], _cell(row, 6)
    programs: list[dict] = []

    def add(group, label, path, kind, note="", **extra):
        if not path or path in ("(None)",):
            return
        path = path.removesuffix(DSL_SUFFIX)
        programs.append({"id": f"{kind}:{path}", "group": group, "label": label, "path": path, "kind": kind,
                         "exists": _exists(source, path), "note": note, **extra})

    for level, data in sorted(source.table("skill").get(_cell(row, 8), {}).items()):
        fields = data[0] if data else []
        add("技能", f"{LEVELS.get(level, '档位 ' + level)}（Lv{level}）", _cell(fields, 7), "skill",
            name=_cell(fields, 0))
    for level, data in sorted(source.table("switched").get(_cell(row, 14), {}).items()):
        fields = data[0] if data else []
        if _cell(fields, 0) and not any(p["path"] == _cell(fields, 0).removesuffix(DSL_SUFFIX) for p in programs):
            add("技能", f"切换后技能 Lv{level}", _cell(fields, 0), "skill")

    flips = source.table("power_flip")
    native = flips.get(code) if kind_code == "4" else None
    template = PF_TYPES.get(kind_code)
    if native:
        for level, path in enumerate(native[0], 1):
            add("强化弹射", f"原生 Lv{level}（power_flip 表 {code}）", path, "pf")
    elif template:
        entries = flips.get(template, [[f"battle/action/power_flip/action/{template}${template}_lv{i}" for i in (1, 2, 3)]])
        for level, path in enumerate(entries[0], 1):
            add("强化弹射", f"原生 Lv{level}（{PF_TYPE_CN[template]}族模板）", path, "pf",
                note="" if _exists(source, path) else "官方基础模板在 APK 内，当前视图里没有，无法预览")

    leader = source.table("leader").get(_cell(row, 17), [])
    for index, line in enumerate(leader):
        for block, kind in (("instant_content", "722"), ("during_content", "419")):
            if _cell(line, col("leader_ability", block, "kind")) != kind:
                continue
            key = _cell(line, col("leader_ability", block, "powerflip_override.id"))
            levels = [v.strip() for v in _cell(line, col("leader_ability", block, "powerflip_override.levels")).split(",") if v.strip()]
            entries = flips.get(key)
            if not entries:
                programs.append({"id": f"pf-missing:{key}", "group": "强化弹射", "label": f"特殊强化弹射 {key}",
                                 "path": "", "kind": "pf", "exists": False,
                                 "note": f"队长技第 {index + 1} 行 {kind} 指向的 power_flip 键不存在"})
                continue
            for slot, path in enumerate(entries[0], 1):
                if path.endswith("/empty"):
                    continue
                if levels == ["4"] and slot == 3:
                    label, note = f"特殊强化弹射 Lv4 · {key}", "forLevels=4：Lv4 客户端补丁读第 3 槽（推定）"
                else:
                    label, note = f"特殊强化弹射 Lv{slot} · {key}", ""
                    if str(slot) not in levels:
                        note = f"forLevels={','.join(levels)}：这一档不替换"
                add("强化弹射", label, path, "pf", note=note, overrideKind=kind, row=index,
                    forLevels=levels, mainOnly=True)

    for table, name, keys in (("leader_ability", "leader", [_cell(row, 17)]),
                              ("ability", "ability", [_cell(row, i) for i in range(19, 25)])):
        data = source.table(name)
        for slot, key in enumerate(keys, 1):
            for index, line in enumerate(data.get(key, [])):
                if _cell(line, col(table, "instant_content", "kind")) != "629":
                    continue
                action = _cell(line, col(table, "instant_content", "action_path"))
                skill = _cell(line, col(table, "instant_content", "string_id"))
                where = ("队长技" if table == "leader_ability" else f"能力 {slot}") + f" 第 {index + 1} 行"
                if action and action != "(None)":
                    add("能力技（629）", f"{where} · {action.rsplit('$', 1)[-1]}", action, "ability_skill")
                elif skill.startswith("battle/"):
                    add("能力技（629）", f"{where} · {skill.rsplit('$', 1)[-1]}", skill, "ability_skill")
                elif skill:
                    for level, tier in sorted(source.table("skill").get(skill, {}).items()):
                        add("能力技（629）", f"{where} · 技能键 {skill} Lv{level}", _cell(tier[0], 7) if tier else "",
                            "ability_skill")
    seen, unique = set(), []
    for program in programs:
        if program["id"] not in seen:
            seen.add(program["id"])
            unique.append(program)
    return {"characterId": cid, "code": code, "element": _cell(row, 3), "programs": unique,
            "note": "强化弹射覆盖（722/419）只在队长位生效；629 能力技由词条触发，伤害按技能结算。"}


class TimelineRoutes:
    def __init__(self, app):
        self.app = app
        self._lock = threading.Lock()
        self._effects: dict[str, tuple[dict, bytes | None]] = {}
        self._infos: dict[str, dict | None] = {}
        self._timelines: dict[tuple, dict] = {}

    def routes(self):
        return [
            ("GET", re.compile(r"^/api/characters/(?P<cid>\d+)/programs$"), self.programs),
            ("GET", re.compile(r"^/api/studio/timeline$"), self.timeline),
            ("GET", re.compile(r"^/api/studio/effect$"), self.effect),
            ("GET", re.compile(r"^/api/studio/effect\.png$"), self.effect_png),
        ]

    @staticmethod
    def _path(query) -> str:
        from .drafts import DraftError
        value = (query.get("path") or [""])[0].strip().removesuffix(DSL_SUFFIX)
        if not SAFE_PATH.match(value) or ".." in value.split("/"):
            raise DraftError("路径必须是 battle/ 下的逻辑路径")
        return value

    def info(self, path: str) -> dict | None:
        with self._lock:
            if path in self._infos:
                return self._infos[path]
        timeline = read_timeline(self.app.source, path)
        parts = read_parts(self.app.source, path) if timeline is not None else None
        result = None if timeline is None or parts is None else {
            "sequences": timeline.get("sequences", []), "sounds": timeline.get("sounds", []),
            "defaultScale": parts.get("s", 1)}
        with self._lock:
            self._infos[path] = result
        return result

    def build(self, path: str, kind: str, element) -> dict:
        key = path, kind, element
        with self._lock:
            if key in self._timelines:
                return self._timelines[key]
        tree = self.app.source.tree(program_logical(path))
        if tree is None:
            from .drafts import DraftError
            raise DraftError(f"当前视图里没有这个程序：{path}")
        result = build_timeline(tree, kind=kind, path=path, element=element, effects=self.info,
                                programs=self.app.source.tree)
        with self._lock:
            self._timelines[key] = result
        return result

    def programs(self, query, cid):
        from .server import error, json_response
        result = character_programs(self.app.source, cid)
        return json_response(result) if result else error(404, f"角色 {cid} 不存在于当前视图")

    def timeline(self, query):
        from .drafts import DraftError
        from .server import json_response
        path = self._path(query)
        kind = (query.get("kind") or ["skill"])[0]
        if kind not in KINDS:
            raise DraftError("kind 只能是 " + " / ".join(KINDS))
        element = None
        cid = (query.get("cid") or [""])[0]
        if cid:
            rows = self.app.source.table("character").get(cid)
            if rows and rows[0] and _cell(rows[0], 3).isdigit():
                element = int(_cell(rows[0], 3))
        return json_response(self.build(path, kind, element))

    def _baked(self, path):
        with self._lock:
            if path in self._effects:
                return self._effects[path]
        result = bake(self.app.source, path)
        with self._lock:
            self._effects[path] = result
        return result

    def effect(self, query):
        from .server import json_response
        path = self._path(query)
        meta, _ = self._baked(path)
        return json_response(meta)

    def effect_png(self, query):
        from .server import Response, error
        path = self._path(query)
        _, png = self._baked(path)
        if png is None:
            return error(404, "这个特效没有可用的贴图")
        return Response(200, png, "image/png")
