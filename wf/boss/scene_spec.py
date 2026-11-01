"""Portable scene specifications and explicit semantic-to-wire bindings."""
from __future__ import annotations

import copy
import io
import csv
import json
import math
import re
from pathlib import Path, PurePosixPath

import jsonschema
from .schema import parse_rows
from .scene_types import (
    AE,
    CAS,
    CONTINUE_PREFIX,
    DATE_COLUMNS,
    DATE_WINDOWS,
    parse_continue_cost,
    parse_jst_datetime,
    validate_date_cell,
    validate_event_code,
    validate_event_original,
)

SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "boss-scene.schema.json"
GENERATED_KEY = re.compile(r"^mod_(?:studio_)?scene_([0-9]{6})(?:_|$)")
GENERATED_CONTINUE = re.compile(r"^continue_cost_([3-9][0-9]{5})[0-9]{3}$")
GENERATED_RESOURCE = re.compile(r"/mod/studio_scene_([0-9]{6})/")


def schema():
    return json.loads(SCHEMA.read_text("utf8"))


def logical_path(value):
    path = PurePosixPath(value)
    if not value or "\\" in value or ":" in value or path.is_absolute() or ".." in path.parts:
        raise ValueError("资源必须是相对逻辑路径")
    return value


def settings(spec):
    yield from spec["event"]["settings"]
    for group in ("tiers", "phases", "shops", "drops"):
        for item in spec[group]:
            yield from item["settings"]
    for group in ("summons", "mechanisms", "trials"):
        yield from spec[group]


def creation_targets(spec):
    """Creation intent comes from emitted identities, not editable UI metadata."""
    event = spec["event"]["id"]
    table_targets, resources, namespaces = set(), set(), set()
    for table in spec["tables"]:
        for entry in table["entries"]:
            generated = [GENERATED_KEY.match(key) for key in entry["path"]]
            continued = [GENERATED_CONTINUE.match(key) for key in entry["path"]]
            namespaces.update(match[1] for match in generated if match)
            namespaces.update(match[1] for match in continued if match and match[1] != "300097")
            if (any(generated) or any(key.startswith(event) for key in entry["path"])
                    or any(key.startswith(CONTINUE_PREFIX + event) for key in entry["path"])):
                table_targets.add((table["logical"], tuple(entry["path"])))
    for resource in spec["resources"]:
        match = GENERATED_RESOURCE.search(resource["logical"])
        if match:
            namespaces.add(match[1])
            resources.add(resource["logical"])
    return table_targets, resources, namespaces


def validate_creation(spec):
    tables, resources, namespaces = creation_targets(spec)
    inferred = bool(namespaces or any(tier.get("sourceQuest") for tier in spec["tiers"]))
    creation = spec.get("creation")
    if inferred and not creation:
        raise ValueError("新场景命名空间或母本引用要求创建防撞声明，不能通过移除标题或来源信息绕过")
    if not creation:
        return
    if namespaces - {spec["event"]["id"]}:
        raise ValueError("新场景逻辑命名空间必须属于当前活动")
    declared = {(entry["logical"], tuple(entry["path"])) for entry in creation["tableTargets"]}
    if not tables <= declared:
        raise ValueError("新场景缺少完整表键防撞声明")
    if not resources <= set(creation["resourceTargets"]):
        raise ValueError("新场景缺少完整资源防撞声明")


def validate_spec(spec):
    json.dumps(spec, allow_nan=False)
    try:
        jsonschema.Draft202012Validator(schema()).validate(spec)
    except jsonschema.ValidationError as exc:
        raise ValueError("规格 schema 错误 /" + "/".join(map(str, exc.absolute_path)) + ": " + exc.message) from exc
    paths, entries = set(), set()
    if spec["requirements"]:
        raise ValueError("此版客户端要求由交付扫描自动推导；尚不接受手填 requirements")
    if (spec.get("provenance", {}).get("kind") == "scene-clone"
            or spec["id"] == "scene-" + spec["event"]["id"]) and not spec.get("creation"):
        raise ValueError("新场景不能移除创建防撞声明")
    validate_creation(spec)
    for table in spec["tables"]:
        logical_path(table["logical"])
        if table["logical"] in paths:
            raise ValueError("重复表：" + table["logical"])
        paths.add(table["logical"])
        for entry in table["entries"]:
            key = (table["logical"], tuple(entry["path"]))
            if key in entries:
                raise ValueError("重复表键")
            entries.add(key)
    for resource in spec["resources"]:
        logical_path(resource["logical"])
        if resource["logical"] in paths:
            raise ValueError("重复资源：" + resource["logical"])
        paths.add(resource["logical"])
    if len({tier["quest"] for tier in spec["tiers"]}) != 5:
        raise ValueError("五档必须是五个不同的 quest")
    bound_dates = {}
    for setting in settings(spec):
        if not setting["bindings"]:
            raise ValueError("语义设置必须绑定实际输出：" + setting["id"])
        if setting["kind"] in {"hp", "attack", "level", "time", "threshold"}:
            number = setting["value"]
            if type(number) not in (str, int, float) or not math.isfinite(float(number)) or not 0 < float(number) <= 2147483647:
                raise ValueError("数值必须为有限正数：" + setting["id"])
            if setting["kind"] in {"level", "time", "threshold"} and not float(number).is_integer():
                raise ValueError("等级、帧数与计数试炼阈值必须是整数：" + setting["id"])
        for binding in setting["bindings"]:
            if "table" not in binding:
                continue
            b_table, b_path, b_col = binding["table"], tuple(binding["path"]), binding["column"]
            b_row = binding.get("row", 0)
            mode = DATE_COLUMNS.get((b_table, b_col))
            if mode is not None:
                validate_date_cell(b_table, b_col, setting["value"], setting["id"])
                if mode in {"required", "optional"}:
                    bound_dates.setdefault((b_table, b_path, b_row), {})[b_col] = parse_jst_datetime(
                        setting["value"], setting["id"], allow_none=mode == "optional")
            if (b_table, b_col) == (AE, 0):
                validate_event_code(setting["value"], setting["id"])
            elif (b_table, b_col) == (AE, 1):
                validate_event_original(setting["value"], setting["id"])
            elif b_table == CAS and b_col == 0 and b_path and b_path[0].startswith(CONTINUE_PREFIX):
                parse_continue_cost(setting["value"], setting["id"])
    for (b_table, b_path, _), cols in bound_dates.items():
        for start_col, end_col in DATE_WINDOWS.get(b_table, ()):
            start, end = cols.get(start_col), cols.get(end_col)
            if start is not None and end is not None and end < start:
                raise ValueError(f"{b_table} {'/'.join(b_path)} c{start_col}..c{end_col} 结束时间早于开始时间")
    return spec


def materialize(spec):
    """Apply semantic settings to a copied graph; reject collisions and dead bindings."""
    validate_spec(spec)
    tables = {t["logical"]: {tuple(e["path"]): copy.deepcopy(e["value"])
                            for e in t["entries"]} for t in spec["tables"]}
    resources = {r["logical"]: copy.deepcopy(r["value"]) for r in spec["resources"]}
    written = {}
    for setting in settings(spec):
        for binding in setting["bindings"]:
            canonical = {**binding, **({"row": binding.get("row", 0)} if "table" in binding else {})}
            identity = json.dumps(canonical, sort_keys=True)
            if identity in written and written[identity] != setting["value"]:
                raise ValueError("语义设置重复绑定且值冲突：" + setting["id"])
            written[identity] = setting["value"]
            if "resource" in binding:
                for previous in written:
                    other = json.loads(previous)
                    if other.get("resource") != binding["resource"] or previous == identity:
                        continue
                    a, b = other["path"], binding["path"]
                    if a[:len(b)] == b or b[:len(a)] == a:
                        raise ValueError("资源父子路径重复绑定：" + setting["id"])
            if "table" in binding:
                table, path = binding["table"], tuple(binding["path"])
                if table not in tables or path not in tables[table]:
                    raise ValueError("绑定未包含在规格表键中：" + setting["id"])
                rows = parse_rows(tables[table][path])
                row, column = binding.get("row", 0), binding["column"]
                if row >= len(rows) or column >= len(rows[row]):
                    raise ValueError("CSV 绑定列不存在：" + setting["id"])
                text = str(setting["value"])
                if rows[row][column] == text:
                    continue  # Preserve original CSV formatting when unchanged.
                rows[row][column] = text
                buffer = io.StringIO()
                csv.writer(buffer, lineterminator="\n").writerows(rows)
                tables[table][path] = buffer.getvalue()
            else:
                logical, path = binding["resource"], binding["path"]
                if logical not in resources or not path:
                    raise ValueError("资源绑定未包含在规格中：" + setting["id"])
                node = resources[logical]
                try:
                    for key in path[:-1]:
                        node = node[key]
                    old = node[path[-1]]
                    if type(old) is not type(setting["value"]):
                        raise ValueError("资源绑定值类型不可改变：" + setting["id"])
                    node[path[-1]] = copy.deepcopy(setting["value"])
                except (KeyError, IndexError, TypeError) as exc:
                    raise ValueError("资源绑定路径不存在：" + setting["id"]) from exc
    return tables, resources
