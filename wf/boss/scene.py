"""Pure scene compilation against a read-only view; no store/server writes."""
from __future__ import annotations

from types import SimpleNamespace
import wf_quest_lib as codec
from wf.tools.boss.five_boss_v2 import decode_amf, encode_dsl
from wf.rules.catalog import result
from .edit_state import BossEditState, leaf, put
from .scene_spec import materialize, settings
from .scene_import import walk


def _audit(loader, spec):
    differences = []
    new = spec.get("creation", {})
    new_keys = {(t["logical"], tuple(t["path"])) for t in new.get("tableTargets", [])}
    new_resources = set(new.get("resourceTargets", []))
    for table in spec["tables"]:
        try:
            current = codec.parse_node(loader(table["logical"]))
        except FileNotFoundError:
            current = {}
        for entry in table["entries"]:
            actual = leaf(current, entry["path"])
            if (table["logical"], tuple(entry["path"])) in new_keys and actual is not None:
                differences.append({"logical": table["logical"], "path": "/".join(entry["path"]), "reason": "新场景 ID 已占用"})
            # New keys are permitted; existing baselines must match before
            # semantic settings are applied, preventing stale graph rollback.
            if actual is not None and actual != entry["value"]:
                differences.append({"logical": table["logical"], "path": "/".join(entry["path"]),
                                    "current": actual, "spec": entry["value"]})
    for resource in spec["resources"]:
        try:
            actual = decode_amf(loader(resource["logical"]))
        except FileNotFoundError:
            continue
        if resource["logical"] in new_resources:
            differences.append({"logical": resource["logical"], "path": "", "reason": "新场景资源路径已占用"})
        if actual != resource["value"]:
            differences.append({"logical": resource["logical"], "path": "", "reason": "原始资源图不同于当前视图"})
    return {"aligned": not differences, "differences": differences,
            "note": "逐键/解码 AMF 对比原始图；语义 value 为明确编辑，当前导入往返不代表旧构建器复现。"}


def compile_scene(loader, spec, *, source=None, check_encounters=True, server_dir=None):
    tables, resources = materialize(spec)
    view = SimpleNamespace(tip=spec["sourceVersion"], zips=[], read_raw=lambda p: (loader(p), "scene-baseline"))
    source = source or SimpleNamespace(view=view, version=spec["sourceVersion"])
    state = BossEditState(source)
    audit = _audit(loader, spec)
    for logical, entries in tables.items():
        from wf.text.edit import _encode
        before = state.table(logical)
        current = __import__("copy").deepcopy(before)
        for path, value in entries.items():
            old = leaf(current, path)
            if old != value:
                put(current, path, value)
                state.changes.append({"table": logical, "path": list(path), "old": old, "new": value})
        if current != before:
            raw = state.raw(logical)
            state.client[logical] = _encode(raw, before, current) if raw is not None else codec.build_node(current)
            state.trees[logical] = current
    for logical, value in resources.items():
        # Keep unchanged wire bytes; semantic equality is the contract.
        before = state.raw(logical)
        if before is None or decode_amf(before) != value:
            state.set_raw(logical, encode_dsl(value))
    from .scene_dsl import references
    problems = references(state, resources)
    if check_encounters:
        from .scene_graph import graph_problems
        problems.extend(graph_problems(state, spec, tables))
    checks = [result("scene.spec", "问题" if problems else "满足", "规格、绑定与 DSL 引用检查",
                     blocking=bool(problems), issues=problems)]
    if check_encounters:
        from .scene_checks import scene_checks
        checks.extend(scene_checks(state, spec))
    checks.append(result("scene.baseline", "满足" if audit["aligned"] else "问题",
                         "原始资源图与当前链尾对比", blocking=not audit["aligned"]))
    if source.version != spec["sourceVersion"]:
        checks.append(result("scene.version", "问题", "规格来源版本与当前视图不符", blocking=True))
    from .scene_server import server_candidate
    servers, server_before, server_checks = server_candidate(state, spec, server_dir)
    checks.extend(server_checks)
    blockers = [c["message"] for c in checks if c.get("blocking")]
    files = dict(state.client)
    if not files:
        blockers.append("规格尚未产生客户端变化，请编辑语义设置或克隆新活动后生成")
    return {"ok": not any(c.get("blocking") for c in checks if c["rule"] != "scene.baseline"),
            "canGenerate": not blockers, "blockers": blockers, "checks": checks, "audit": audit,
            "files": files, "servers": servers, "serverBefore": server_before,
            "changes": state.changes, "diff": state.changes,
            "summary": {**{k: len(spec[k]) for k in ("tables", "resources", "phases", "tiers", "summons", "mechanisms", "trials", "shops", "drops")},
                        "tableEntries": sum(len(t["entries"]) for t in spec["tables"]), "changedFiles": len(files), "serverFiles": len(servers)},
            "runtime": "未执行"}
